"""
Celery task for asynchronous TA generation.

This task orchestrates the complete TA generation pipeline,
including LLM interaction, TA packaging, and enqueueing validation.
"""
import asyncio
import os
import shutil
import tarfile
import tempfile
from pathlib import Path
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

            # Create TA name (sanitize source_system for directory name)
            ta_name = f"TA-{request.source_system.replace(' ', '_').replace('/', '-')}"
            storage_key = f"ta/{request_id}/v{next_version}/{ta_name}.tgz"

            # Create TA directory structure and package as tarball
            temp_dir = None
            try:
                temp_dir = Path(tempfile.mkdtemp(prefix=f"ta-gen-{request_id}-"))
                ta_dir = temp_dir / ta_name
                default_dir = ta_dir / "default"
                default_dir.mkdir(parents=True)

                # Create app.conf
                app_conf_path = default_dir / "app.conf"
                with open(app_conf_path, "w") as f:
                    f.write(f"[install]\n")
                    f.write(f"is_configured = 0\n")
                    f.write(f"build = {next_version}\n\n")
                    f.write(f"[ui]\n")
                    f.write(f"is_visible = 0\n")
                    f.write(f"label = {ta_name}\n\n")
                    f.write(f"[launcher]\n")
                    f.write(f"author = Splunk TA Generator\n")
                    f.write(f"description = Auto-generated TA for {request.source_system}\n")
                    f.write(f"version = 1.0.{next_version}\n")

                # Create props.conf from ta_config
                props_conf_path = default_dir / "props.conf"
                with open(props_conf_path, "w") as f:
                    props_config = ta_config.get("props", {})
                    for stanza, settings_dict in props_config.items():
                        f.write(f"[{stanza}]\n")
                        for key, value in settings_dict.items():
                            f.write(f"{key} = {value}\n")
                        f.write("\n")

                # Create transforms.conf if present
                transforms_config = ta_config.get("transforms", {})
                if transforms_config:
                    transforms_conf_path = default_dir / "transforms.conf"
                    with open(transforms_conf_path, "w") as f:
                        for stanza, settings_dict in transforms_config.items():
                            f.write(f"[{stanza}]\n")
                            for key, value in settings_dict.items():
                                f.write(f"{key} = {value}\n")
                            f.write("\n")

                # Create inputs.conf if present
                inputs_config = ta_config.get("inputs", {})
                if inputs_config:
                    inputs_conf_path = default_dir / "inputs.conf"
                    with open(inputs_conf_path, "w") as f:
                        for stanza, settings_dict in inputs_config.items():
                            f.write(f"[{stanza}]\n")
                            for key, value in settings_dict.items():
                                f.write(f"{key} = {value}\n")
                            f.write("\n")

                # Create tarball
                tarball_path = temp_dir / f"{ta_name}.tgz"
                with tarfile.open(tarball_path, "w:gz") as tar:
                    tar.add(ta_dir, arcname=ta_name)

                log.info("ta_tarball_created", path=str(tarball_path), size=tarball_path.stat().st_size)

                task.update_state(
                    state="PROGRESS",
                    meta={"step": "uploading_ta", "progress": 70},
                )

                # Upload tarball to MinIO
                with open(tarball_path, "rb") as f:
                    await storage_client.upload_file_async(
                        file_obj=f,
                        bucket=settings.minio_bucket_tas,
                        key=storage_key,
                        content_type="application/gzip",
                    )

                log.info("ta_uploaded_to_storage", storage_key=storage_key)

            except Exception as upload_error:
                log.error("ta_packaging_or_upload_failed", error=str(upload_error))
                raise ValueError(f"Failed to package or upload TA: {str(upload_error)}")
            finally:
                # Clean up temp directory
                if temp_dir and temp_dir.exists():
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception as cleanup_error:
                        log.warning("temp_cleanup_failed", error=str(cleanup_error))

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
