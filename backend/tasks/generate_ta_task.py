"""
Celery task for TA (Technology Add-on) generation.

This task orchestrates the complete TA generation workflow:
1. Fetch request and log samples from database
2. Download sample content preview from object storage
3. Retrieve RAG context from Pinecone
4. Build prompt and call Ollama LLM
5. Generate TA package with TAGenerationService
6. Upload package to object storage
7. Create TARevision record
8. Update request status and log audit events

Usage:
    from backend.tasks.generate_ta_task import generate_ta
    result = generate_ta.delay(request_id="uuid-string")
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

import structlog
from celery import Task

from backend.tasks.celery_app import celery_app
from backend.core.config import settings
from backend.database import get_async_session_for_task
from backend.models.enums import RequestStatus, AuditAction, TARevisionType
from backend.models.ta_revision import TARevision
from backend.repositories.request_repository import RequestRepository
from backend.repositories.ta_revision_repository import TARevisionRepository
from backend.repositories.log_sample_repository import LogSampleRepository
from backend.repositories.audit_log_repository import AuditLogRepository
from backend.integrations.ollama_client import OllamaClient
from backend.integrations.pinecone_client import PineconeClient
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.services.prompt_builder import PromptBuilder
from backend.services.ta_generation_service import TAGenerationService

logger = structlog.get_logger(__name__)


class TAGenerationTask(Task):
    """Custom Celery task class with async support and error handling."""

    abstract = True
    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600  # Max 10 minutes between retries
    retry_jitter = True
    max_retries = 3

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        request_id = kwargs.get("request_id") or (args[0] if args else None)
        logger.error(
            "ta_generation_task_failed",
            task_id=task_id,
            request_id=request_id,
            error=str(exc),
            exc_info=einfo,
        )

    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success."""
        request_id = kwargs.get("request_id") or (args[0] if args else None)
        logger.info(
            "ta_generation_task_succeeded",
            task_id=task_id,
            request_id=request_id,
        )


def run_async(coro):
    """Run async coroutine in sync context for Celery."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    base=TAGenerationTask,
    name="backend.tasks.generate_ta_task.generate_ta",
    queue="ta_generation",
)
def generate_ta(self, request_id: str) -> Dict[str, Any]:
    """
    Generate a Splunk TA for the given request.

    This task:
    1. Updates request status to GENERATING_TA
    2. Logs TA_GENERATION_START audit event
    3. Fetches request with log samples
    4. Downloads sample content preview
    5. Retrieves RAG context from Pinecone
    6. Builds prompt and calls Ollama LLM
    7. Creates TA package using TAGenerationService
    8. Uploads package to object storage
    9. Creates TARevision record
    10. Updates status to VALIDATING
    11. Logs TA_GENERATION_COMPLETE audit event

    Args:
        request_id: UUID string of the request to process

    Returns:
        Dict with ta_revision_id, version, and storage_key

    Raises:
        Exception: If any step fails, status is set to FAILED
    """
    return run_async(_generate_ta_async(self, request_id))


async def _generate_ta_async(task: Task, request_id: str) -> Dict[str, Any]:
    """Async implementation of TA generation."""
    task_log = logger.bind(
        task_id=task.request.id,
        request_id=request_id,
        component="generate_ta_task",
    )
    task_log.info("ta_generation_started")

    request_uuid = UUID(request_id)

    async with get_async_session_for_task() as session:
        try:
            # Initialize repositories
            request_repo = RequestRepository(session)
            ta_revision_repo = TARevisionRepository(session)
            log_sample_repo = LogSampleRepository(session)
            audit_repo = AuditLogRepository(session)

            # Initialize integration clients
            ollama_client = OllamaClient()
            pinecone_client = PineconeClient()
            storage_client = ObjectStorageClient()
            ta_service = TAGenerationService(storage_client)
            prompt_builder = PromptBuilder(pinecone_client)

            # Step 1: Update status to GENERATING_TA
            task_log.info("updating_status_to_generating")
            await request_repo.update_status(request_uuid, RequestStatus.GENERATING_TA)

            # Step 2: Log audit event
            await audit_repo.create(
                user_id=None,  # System-initiated
                action=AuditAction.TA_GENERATION_START,
                entity_type="request",
                entity_id=request_id,
                details={
                    "task_id": task.request.id,
                    "started_at": datetime.utcnow().isoformat(),
                },
            )
            await session.commit()

            # Step 3: Fetch request with samples
            task_log.info("fetching_request_with_samples")
            request = await request_repo.get_with_samples(request_uuid)
            if not request:
                raise ValueError(f"Request {request_id} not found")

            log_samples = request.log_samples or []
            task_log.info(
                "request_fetched",
                source_system=request.source_system,
                sample_count=len(log_samples),
            )

            # Step 4: Get sample content preview
            sample_preview = await log_sample_repo.get_sample_preview(request_uuid)

            # Fallback: if no preview in DB, download first 50 lines from storage
            if not sample_preview:
                sample_preview = await _download_sample_preview_fallback(
                    log_samples, storage_client, task_log
                )

            # Step 5: Retrieve RAG context from Pinecone
            task_log.info("retrieving_pinecone_context")
            pinecone_context = await prompt_builder.retrieve_context_from_pinecone(
                request=request,
                log_samples=log_samples,
                top_k_per_source=5,
            )

            # Step 6: Build prompt
            task_log.info("building_ta_generation_prompt")
            prompt = await prompt_builder.build_ta_generation_prompt(
                request=request,
                log_samples=log_samples,
                sample_content_preview=sample_preview,
                pinecone_context=pinecone_context,
            )

            # Step 7: Call Ollama LLM
            task_log.info("calling_ollama_llm")
            system_prompt = prompt_builder.get_system_prompt()
            schema = prompt_builder.get_ta_generation_schema()

            llm_response = await ollama_client.generate_structured_response(
                prompt=prompt,
                system_prompt=system_prompt,
                response_schema=schema,
            )

            ta_config = _parse_llm_response(llm_response, task_log)
            task_log.info(
                "llm_response_received",
                ta_name=ta_config.get("ta_name"),
            )

            # Step 8: Create TA package
            task_log.info("creating_ta_package")
            ta_name = ta_config.get("ta_name", f"TA-{request.source_system or 'custom'}")
            package_path, package_checksum = await ta_service.create_ta_package(
                ta_name=ta_name,
                ta_config=ta_config,
            )

            # Step 9: Upload to object storage
            task_log.info("uploading_ta_package")
            next_version = await ta_revision_repo.get_next_version(request_uuid)
            storage_key = f"requests/{request_id}/revisions/{ta_name}-v{next_version}.tgz"

            with open(package_path, "rb") as f:
                upload_result = await storage_client.upload_file_async(
                    file_obj=f,
                    bucket=settings.minio_bucket_tas,
                    key=storage_key,
                    content_type="application/gzip",
                )

            # Verify checksum integrity
            uploaded_checksum = upload_result.get("checksum")
            if uploaded_checksum and uploaded_checksum != package_checksum:
                task_log.warning(
                    "checksum_mismatch",
                    expected=package_checksum,
                    actual=uploaded_checksum,
                )

            task_log.info(
                "ta_package_uploaded",
                storage_key=upload_result.get("storage_key"),
                checksum=uploaded_checksum,
                size=upload_result.get("size"),
            )

            # Step 10: Create TARevision record
            task_log.info("creating_ta_revision_record")
            ta_revision = TARevision(
                request_id=request_uuid,
                version=next_version,
                storage_key=storage_key,
                generated_by=TARevisionType.AUTO,
                config_summary=_create_config_summary(ta_config),
                generation_metadata={
                    "task_id": task.request.id,
                    "model": settings.ollama_model,
                    "generated_at": datetime.utcnow().isoformat(),
                    "checksum": package_checksum,
                    "pinecone_context_size": {
                        "docs": len(pinecone_context.get("docs", [])),
                        "tas": len(pinecone_context.get("tas", [])),
                        "samples": len(pinecone_context.get("samples", [])),
                    },
                },
            )
            session.add(ta_revision)

            # Step 11: Update status to VALIDATING
            await request_repo.update_status(request_uuid, RequestStatus.VALIDATING)

            # Step 12: Log completion audit event
            await audit_repo.create(
                user_id=None,
                action=AuditAction.TA_GENERATION_COMPLETE,
                entity_type="request",
                entity_id=request_id,
                details={
                    "task_id": task.request.id,
                    "ta_revision_id": str(ta_revision.id),
                    "version": next_version,
                    "storage_key": storage_key,
                    "completed_at": datetime.utcnow().isoformat(),
                },
            )

            await session.commit()

            # Cleanup temporary files
            await ta_service.cleanup_temp_files(package_path)

            task_log.info(
                "ta_generation_completed",
                ta_revision_id=str(ta_revision.id),
                version=next_version,
            )

            # TODO: Enqueue validation task (Phase 2)
            # from backend.tasks.validate_ta_task import validate_ta
            # validate_ta.delay(request_id=request_id, revision_id=str(ta_revision.id))

            return {
                "ta_revision_id": str(ta_revision.id),
                "version": next_version,
                "storage_key": storage_key,
                "ta_name": ta_name,
            }

        except Exception as e:
            task_log.error(
                "ta_generation_failed",
                error=str(e),
                exc_info=True,
            )

            # Update status to FAILED
            try:
                await request_repo.update_status(request_uuid, RequestStatus.FAILED)
                await audit_repo.create(
                    user_id=None,
                    action=AuditAction.TA_GENERATION_FAILED,
                    entity_type="request",
                    entity_id=request_id,
                    details={
                        "task_id": task.request.id,
                        "error": str(e),
                        "failed_at": datetime.utcnow().isoformat(),
                    },
                )
                await session.commit()
            except Exception as commit_error:
                task_log.error(
                    "failed_to_update_failure_status",
                    error=str(commit_error),
                )

            raise


async def _download_sample_preview_fallback(
    log_samples,
    storage_client: ObjectStorageClient,
    task_log,
) -> str:
    """
    Fallback: download first 50 lines from storage for up to 3 samples.

    Used when LogSampleRepository.get_sample_preview returns None/empty.
    """
    if not log_samples:
        task_log.warning("no_log_samples_found")
        return "No log samples available."

    previews = []
    for sample in log_samples[:3]:  # Limit to first 3 samples
        try:
            if not sample.storage_key:
                continue

            # Download first ~50KB from storage
            content_chunks = []
            bytes_read = 0
            max_bytes = 50000

            async for chunk in storage_client.download_file_async(
                bucket=settings.minio_bucket_samples,
                key=sample.storage_key,
            ):
                content_chunks.append(chunk)
                bytes_read += len(chunk)
                if bytes_read >= max_bytes:
                    break

            content = b"".join(content_chunks)[:max_bytes]
            lines = content.decode("utf-8", errors="replace").split("\n")[:50]
            preview = "\n".join(lines)
            previews.append(f"### {sample.original_filename or 'Sample'}\n{preview}")

        except Exception as e:
            task_log.warning(
                "failed_to_download_sample_preview",
                sample_id=str(sample.id),
                error=str(e),
            )

    return "\n\n".join(previews) if previews else "Unable to retrieve sample content."


def _parse_llm_response(response: Dict[str, Any], task_log) -> Dict[str, Any]:
    """Parse and validate LLM response."""
    if isinstance(response, str):
        try:
            response = json.loads(response)
        except json.JSONDecodeError as e:
            task_log.error("failed_to_parse_llm_response", error=str(e))
            raise ValueError(f"Invalid JSON response from LLM: {e}")

    # Ensure required fields exist
    required_fields = ["inputs_conf", "props_conf", "transforms_conf"]
    for field in required_fields:
        if field not in response:
            response[field] = {"stanzas": []}

    # Ensure cim_mappings exists
    if "cim_mappings" not in response:
        response["cim_mappings"] = {
            "data_models": [],
            "field_aliases": {},
            "eventtypes": [],
            "tags": {},
        }

    return response


def _create_config_summary(ta_config: Dict[str, Any]) -> Dict[str, Any]:
    """Create a summary of the TA configuration for storage."""
    return {
        "ta_name": ta_config.get("ta_name", "unknown"),
        "inputs_stanza_count": len(ta_config.get("inputs_conf", {}).get("stanzas", [])),
        "props_stanza_count": len(ta_config.get("props_conf", {}).get("stanzas", [])),
        "transforms_stanza_count": len(ta_config.get("transforms_conf", {}).get("stanzas", [])),
        "cim_data_models": ta_config.get("cim_mappings", {}).get("data_models", []),
        "field_alias_count": len(ta_config.get("cim_mappings", {}).get("field_aliases", {})),
    }
