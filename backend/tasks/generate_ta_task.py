"""
Celery task for asynchronous TA generation.

This task orchestrates the complete TA generation pipeline,
including LLM interaction, TA packaging, and enqueueing validation.
"""
import asyncio
from typing import Any, Dict
from uuid import UUID

import structlog
from celery import Task

from backend.core.config import settings
from backend.database import async_session_factory
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.models.enums import AuditAction, RequestStatus, ValidationStatus
from backend.repositories.log_sample_repository import LogSampleRepository
from backend.repositories.request_repository import RequestRepository
from backend.repositories.ta_revision_repository import TARevisionRepository
from backend.repositories.validation_run_repository import ValidationRunRepository
from backend.tasks.celery_app import celery_app

logger = structlog.get_logger(__name__)


class TAGenerationTask(Task):
    """Custom Celery task class for TA generation."""

    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        logger.error(
            "ta_generation_task_failed",
            task_id=task_id,
            args=args,
            error=str(exc),
            traceback=str(einfo),
        )

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        logger.info(
            "ta_generation_task_succeeded",
            task_id=task_id,
            args=args,
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
    name="generate_ta",
    bind=True,
    base=TAGenerationTask,
    max_retries=2,
    default_retry_delay=30,
    time_limit=600,  # 10 minutes hard limit
    soft_time_limit=540,  # 9 minutes soft limit
)
def generate_ta_task(
    self: Task,
    request_id: str,
) -> Dict[str, Any]:
    """
    Celery task for generating a TA from a request.

    This task:
    1. Fetches request and sample data
    2. Queries RAG for relevant context
    3. Generates TA configuration via LLM
    4. Packages TA as tarball
    5. Uploads to object storage
    6. Creates TARevision record
    7. Enqueues validation task

    Args:
        request_id: UUID string of the Request record

    Returns:
        Dictionary with ta_revision_id and status

    Note:
        This is a placeholder implementation. The actual LLM integration
        and TA generation logic should be implemented based on your
        specific requirements.
    """
    log = logger.bind(
        task_id=self.request.id,
        request_id=request_id,
    )
    log.info("generate_ta_task_started")

    return run_async(_generate_ta_async(self, UUID(request_id)))


async def _generate_ta_async(
    task: Task,
    request_id: UUID,
) -> Dict[str, Any]:
    """
    Async implementation of TA generation.

    Args:
        task: Celery task instance
        request_id: Request record UUID

    Returns:
        Dictionary with ta_revision_id and status
    """
    log = logger.bind(
        task_id=task.request.id,
        request_id=str(request_id),
    )

    async with async_session_factory() as session:
        # Initialize repositories
        request_repo = RequestRepository(session)
        ta_revision_repo = TARevisionRepository(session)
        sample_repo = LogSampleRepository(session)
        validation_repo = ValidationRunRepository(session)
        storage_client = ObjectStorageClient()

        try:
            # Update request status to GENERATING_TA
            await request_repo.update_status(request_id, RequestStatus.GENERATING_TA)
            await session.commit()

            task.update_state(
                state="PROGRESS",
                meta={"step": "fetching_data", "progress": 10},
            )

            # Fetch request with samples
            request = await request_repo.get_with_samples(request_id)
            if not request:
                raise ValueError(f"Request {request_id} not found")

            log.info("audit_ta_generation_start", action=AuditAction.TA_GENERATION_START.value)

            # Get samples
            samples = await sample_repo.get_active_samples(request_id)
            if not samples:
                raise ValueError("No active samples found for request")

            task.update_state(
                state="PROGRESS",
                meta={"step": "generating_ta", "progress": 30},
            )

            # TODO: Implement actual TA generation logic
            # This should:
            # 1. Query Pinecone for relevant documentation
            # 2. Build prompt with request metadata and sample snippets
            # 3. Call Ollama LLM to generate TA configuration
            # 4. Parse and validate the generated configuration
            # 5. Package into a proper TA directory structure
            # 6. Create tarball

            # Placeholder: Create a minimal TA structure
            # In production, this would be generated by the LLM
            ta_config = {
                "props": {
                    f"sourcetype::{request.source_system}": {
                        "TIME_FORMAT": "%Y-%m-%d %H:%M:%S",
                        "MAX_TIMESTAMP_LOOKAHEAD": "30",
                        "SHOULD_LINEMERGE": "false",
                    }
                },
                "transforms": {},
                "inputs": {},
            }

            task.update_state(
                state="PROGRESS",
                meta={"step": "packaging_ta", "progress": 60},
            )

            # Get next version number
            next_version = await ta_revision_repo.get_next_version(request_id)

            # TODO: Package TA and upload to MinIO
            # For now, we'll create a placeholder storage key
            ta_name = f"TA-{request.source_system.replace(' ', '_')}"
            storage_key = f"ta/{request_id}/v{next_version}/{ta_name}.tgz"

            task.update_state(
                state="PROGRESS",
                meta={"step": "saving_revision", "progress": 80},
            )

            # Create TARevision record
            from backend.models import TARevision
            from backend.models.enums import TARevisionType

            ta_revision = TARevision(
                request_id=request_id,
                version=next_version,
                ta_name=ta_name,
                storage_key=storage_key,
                config_content=ta_config,
                generated_by=TARevisionType.AUTO,
                sourcetype=request.source_system,
            )
            session.add(ta_revision)
            await session.flush()

            log.info(
                "ta_revision_created",
                ta_revision_id=str(ta_revision.id),
                version=next_version,
                ta_name=ta_name,
            )

            # Update request status to VALIDATING
            await request_repo.update_status(request_id, RequestStatus.VALIDATING)

            # Create ValidationRun record
            from backend.models import ValidationRun

            validation_run = ValidationRun(
                request_id=request_id,
                ta_revision_id=ta_revision.id,
                status=ValidationStatus.QUEUED,
            )
            session.add(validation_run)
            await session.flush()

            # Commit before enqueueing validation task
            await session.commit()

            log.info(
                "enqueueing_validation_task",
                validation_run_id=str(validation_run.id),
                ta_revision_id=str(ta_revision.id),
                request_id=str(request_id),
            )

            # Enqueue validation task
            from backend.tasks.validate_ta_task import validate_ta_task

            validate_ta_task.apply_async(
                args=[str(validation_run.id), str(ta_revision.id), str(request_id)],
                queue="validation",
            )

            log.info(
                "audit_ta_generation_complete",
                action=AuditAction.TA_GENERATION_COMPLETE.value,
            )

            return {
                "status": "success",
                "ta_revision_id": str(ta_revision.id),
                "validation_run_id": str(validation_run.id),
                "ta_name": ta_name,
                "version": next_version,
            }

        except Exception as e:
            log.error("ta_generation_failed", error=str(e), error_type=type(e).__name__)

            # Update request status to FAILED
            try:
                await request_repo.update_status(request_id, RequestStatus.FAILED)
                await session.commit()
            except Exception as commit_error:
                log.error("failed_to_update_status_on_error", error=str(commit_error))

            log.info("audit_ta_generation_failed", action=AuditAction.TA_GENERATION_FAILED.value)

            raise
