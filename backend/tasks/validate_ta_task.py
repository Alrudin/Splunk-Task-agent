"""
Celery task for asynchronous TA validation.

This task orchestrates the complete validation pipeline from queueing
to completion/failure, including concurrency control and status management.
"""
import asyncio
from typing import Any, Dict
from uuid import UUID

import structlog
from celery import Task
from celery.exceptions import Retry

from backend.core.config import settings
from backend.database import async_session_factory
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.integrations.splunk_sandbox_client import SplunkSandboxClient
from backend.models.enums import AuditAction, RequestStatus, ValidationStatus
from backend.repositories.log_sample_repository import LogSampleRepository
from backend.repositories.request_repository import RequestRepository
from backend.repositories.ta_revision_repository import TARevisionRepository
from backend.repositories.validation_run_repository import ValidationRunRepository
from backend.services.validation_service import ValidationError, ValidationService
from backend.tasks.celery_app import celery_app
from backend.tasks.send_notification_task import send_notification_task

logger = structlog.get_logger(__name__)


class ValidationTask(Task):
    """Custom Celery task class with async support and cleanup handling."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure - cleanup and logging."""
        logger.error(
            "validation_task_failed",
            task_id=task_id,
            args=args,
            error=str(exc),
            traceback=str(einfo),
        )

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success - logging."""
        logger.info(
            "validation_task_succeeded",
            task_id=task_id,
            args=args,
            result_status=retval.get("status") if isinstance(retval, dict) else None,
        )


def run_async(coro):
    """Run an async coroutine in a new event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    name="validate_ta",
    bind=True,
    base=ValidationTask,
    max_retries=3,
    default_retry_delay=60,
    time_limit=1800,  # 30 minutes hard limit
    soft_time_limit=1500,  # 25 minutes soft limit for cleanup
)
def validate_ta_task(
    self: Task,
    validation_run_id: str,
    ta_revision_id: str,
    request_id: str,
) -> Dict[str, Any]:
    """
    Celery task for validating a TA revision.

    This task:
    1. Checks concurrency limits
    2. Creates a Splunk sandbox container
    3. Installs the TA
    4. Ingests sample logs
    5. Runs validation searches
    6. Generates a validation report
    7. Creates debug bundle on failure
    8. Updates request and validation status

    Args:
        validation_run_id: UUID string of the ValidationRun record
        ta_revision_id: UUID string of the TARevision record
        request_id: UUID string of the Request record

    Returns:
        Validation report dictionary

    Raises:
        Retry: When concurrency limit is reached
    """
    log = logger.bind(
        task_id=self.request.id,
        validation_run_id=validation_run_id,
        ta_revision_id=ta_revision_id,
        request_id=request_id,
    )
    log.info("validate_ta_task_started")

    # Run the async validation
    return run_async(
        _validate_ta_async(
            self,
            UUID(validation_run_id),
            UUID(ta_revision_id),
            UUID(request_id),
        )
    )


async def _validate_ta_async(
    task: Task,
    validation_run_id: UUID,
    ta_revision_id: UUID,
    request_id: UUID,
) -> Dict[str, Any]:
    """
    Async implementation of TA validation.

    Args:
        task: Celery task instance
        validation_run_id: ValidationRun record UUID
        ta_revision_id: TARevision record UUID
        request_id: Request record UUID

    Returns:
        Validation report dictionary
    """
    log = logger.bind(
        task_id=task.request.id,
        validation_run_id=str(validation_run_id),
        ta_revision_id=str(ta_revision_id),
        request_id=str(request_id),
    )

    async with async_session_factory() as session:
        # Initialize repositories
        validation_repo = ValidationRunRepository(session)
        request_repo = RequestRepository(session)
        ta_revision_repo = TARevisionRepository(session)
        sample_repo = LogSampleRepository(session)

        # Initialize clients
        splunk_client = SplunkSandboxClient()
        storage_client = ObjectStorageClient()

        # Initialize validation service
        validation_service = ValidationService(
            splunk_client=splunk_client,
            storage_client=storage_client,
            validation_repo=validation_repo,
            ta_revision_repo=ta_revision_repo,
            sample_repo=sample_repo,
        )

        try:
            # Check concurrency limit using active count (QUEUED + RUNNING)
            # Subtract 1 because this validation is already QUEUED
            active_count = await validation_repo.get_active_count()
            running_count = active_count - 1  # Exclude this task from count
            log.info("checking_concurrency", active=active_count, running=running_count, max=settings.max_parallel_validations)

            if running_count >= settings.max_parallel_validations:
                log.info(
                    "concurrency_limit_reached",
                    running=running_count,
                    max=settings.max_parallel_validations,
                    retry_in=settings.validation_retry_delay,
                )
                # Requeue the task with a delay
                raise task.retry(
                    countdown=settings.validation_retry_delay,
                    exc=Exception(f"Concurrency limit reached: {running_count}/{settings.max_parallel_validations}"),
                )

            # Transition status to RUNNING immediately after passing concurrency check
            # This ensures the record is counted as active before any expensive operations
            await validation_repo.update_status(validation_run_id, ValidationStatus.RUNNING)
            await session.commit()
            log.info("status_transitioned_to_running")

            # Update task state to show progress
            task.update_state(
                state="PROGRESS",
                meta={"step": "starting", "progress": 5},
            )

            # Log audit event - VALIDATION_START
            log.info("audit_validation_start", action=AuditAction.VALIDATION_START.value)

            # Execute validation
            task.update_state(
                state="PROGRESS",
                meta={"step": "validating", "progress": 20},
            )

            validation_report = await validation_service.validate_ta_revision(
                validation_run_id=validation_run_id,
                ta_revision_id=ta_revision_id,
                request_id=request_id,
            )

            task.update_state(
                state="PROGRESS",
                meta={"step": "finalizing", "progress": 90},
            )

            # Determine final status
            final_status = (
                ValidationStatus.PASSED
                if validation_report["status"] == "PASSED"
                else ValidationStatus.FAILED
            )

            # Update ValidationRun with results
            await validation_repo.complete_validation(
                validation_id=validation_run_id,
                status=final_status,
                results=validation_report,
                debug_bundle_key=validation_report.get("debug_bundle_key"),
            )

            # Update Request status
            if final_status == ValidationStatus.PASSED:
                await request_repo.update_status(request_id, RequestStatus.COMPLETED)
                log.info("audit_validation_complete", action=AuditAction.VALIDATION_COMPLETE.value)

                # Get request details for notification
                request = await request_repo.get_by_id(request_id)
                if request and request.created_by:
                    # Send completion notification
                    try:
                        send_notification_task.apply_async(
                            args=[
                                str(request.created_by),
                                "COMPLETED",
                                str(request_id),
                                {
                                    "validation_summary": validation_report.get("summary", {}),
                                    "ta_download_url": f"{settings.frontend_url}/requests/{request_id}/ta"
                                }
                            ],
                            queue="default"
                        )
                        log.info("completion_notification_enqueued", user_id=str(request.created_by))
                    except Exception as e:
                        log.error("failed_to_enqueue_completion_notification", error=str(e))
            else:
                await request_repo.update_status(request_id, RequestStatus.FAILED)
                log.info("audit_validation_failed", action=AuditAction.VALIDATION_FAILED.value)

                # Get request details for notification
                request = await request_repo.get_by_id(request_id)
                if request and request.created_by:
                    # Send failure notification
                    try:
                        send_notification_task.apply_async(
                            args=[
                                str(request.created_by),
                                "FAILED",
                                str(request_id),
                                {
                                    "error_message": validation_report.get("error", "Validation failed"),
                                    "validation_results": validation_report,
                                    "debug_bundle_url": f"{settings.frontend_url}/requests/{request_id}/debug-bundle"
                                }
                            ],
                            queue="default"
                        )
                        log.info("failure_notification_enqueued", user_id=str(request.created_by))
                    except Exception as e:
                        log.error("failed_to_enqueue_failure_notification", error=str(e))

            # Commit transaction
            await session.commit()

            log.info(
                "validate_ta_task_completed",
                status=validation_report["status"],
                event_count=validation_report.get("summary", {}).get("total_events", 0),
                coverage=validation_report.get("summary", {}).get("coverage_pct", 0),
            )

            return validation_report

        except Retry:
            # Re-raise retry exceptions
            raise

        except ValidationError as e:
            log.error("validation_error", error=str(e), details=e.details)

            # Create minimal debug bundle for early failures
            debug_bundle_key = None
            try:
                debug_bundle_key = await validation_service.create_early_failure_debug_bundle(
                    validation_run_id=validation_run_id,
                    request_id=request_id,
                    ta_revision_id=ta_revision_id,
                    error_message=str(e),
                    error_details=e.details,
                )
                log.info("early_failure_debug_bundle_created", key=debug_bundle_key)
            except Exception as bundle_error:
                log.warning("failed_to_create_debug_bundle", error=str(bundle_error))

            # Update ValidationRun with error
            await validation_repo.complete_validation(
                validation_id=validation_run_id,
                status=ValidationStatus.FAILED,
                results={"error": str(e), "details": e.details},
                error_message=str(e),
                debug_bundle_key=debug_bundle_key,
            )

            # Update Request status to FAILED
            await request_repo.update_status(request_id, RequestStatus.FAILED)

            await session.commit()

            # Send failure notification
            request = await request_repo.get_by_id(request_id)
            if request and request.created_by:
                try:
                    send_notification_task.apply_async(
                        args=[
                            str(request.created_by),
                            "FAILED",
                            str(request_id),
                            {
                                "error_message": str(e),
                                "debug_bundle_url": f"{settings.frontend_url}/requests/{request_id}/debug-bundle"
                            }
                        ],
                        queue="default"
                    )
                    log.info("failure_notification_enqueued", user_id=str(request.created_by))
                except Exception as notif_error:
                    log.error("failed_to_enqueue_failure_notification", error=str(notif_error))

            log.info("audit_validation_failed", action=AuditAction.VALIDATION_FAILED.value)

            return {
                "status": "FAILED",
                "error": str(e),
                "details": e.details,
                "debug_bundle_key": debug_bundle_key,
            }

        except Exception as e:
            log.error("unexpected_validation_error", error=str(e), error_type=type(e).__name__)

            # Create minimal debug bundle for unexpected failures
            debug_bundle_key = None
            try:
                debug_bundle_key = await validation_service.create_early_failure_debug_bundle(
                    validation_run_id=validation_run_id,
                    request_id=request_id,
                    ta_revision_id=ta_revision_id,
                    error_message=str(e),
                    error_details={"error_type": type(e).__name__},
                )
                log.info("early_failure_debug_bundle_created", key=debug_bundle_key)
            except Exception as bundle_error:
                log.warning("failed_to_create_debug_bundle", error=str(bundle_error))

            # Update ValidationRun with error
            try:
                await validation_repo.complete_validation(
                    validation_id=validation_run_id,
                    status=ValidationStatus.FAILED,
                    results={"error": str(e), "error_type": type(e).__name__},
                    error_message=str(e),
                    debug_bundle_key=debug_bundle_key,
                )

                # Update Request status to FAILED
                await request_repo.update_status(request_id, RequestStatus.FAILED)

                await session.commit()

                # Send failure notification
                request = await request_repo.get_by_id(request_id)
                if request and request.created_by:
                    try:
                        send_notification_task.apply_async(
                            args=[
                                str(request.created_by),
                                "FAILED",
                                str(request_id),
                                {
                                    "error_message": str(e),
                                    "debug_bundle_url": f"{settings.frontend_url}/requests/{request_id}/debug-bundle"
                                }
                            ],
                            queue="default"
                        )
                        log.info("failure_notification_enqueued", user_id=str(request.created_by))
                    except Exception as notif_error:
                        log.error("failed_to_enqueue_failure_notification", error=str(notif_error))
            except Exception as commit_error:
                log.error("failed_to_update_status_on_error", error=str(commit_error))

            log.info("audit_validation_failed", action=AuditAction.VALIDATION_FAILED.value)

            raise
