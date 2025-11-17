"""
FastAPI Dependency Injection

Dependency injection functions for FastAPI endpoints to provide
configured service clients including object storage, database sessions,
and other shared resources.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

import structlog

from backend.integrations.object_storage_client import ObjectStorageClient, StorageConfig

logger = structlog.get_logger(__name__)

# Singleton storage client instance
_storage_client: Optional[ObjectStorageClient] = None


def get_storage_client() -> ObjectStorageClient:
    """
    FastAPI dependency for object storage client.

    Returns a configured ObjectStorageClient instance using singleton pattern
    to reuse the client across requests.

    Returns:
        ObjectStorageClient: Configured storage client

    Raises:
        RuntimeError: If client initialization fails

    Example:
        ```python
        from fastapi import APIRouter, Depends, UploadFile
        from backend.core.dependencies import get_storage_client
        from backend.integrations.object_storage_client import ObjectStorageClient

        router = APIRouter()

        @router.post("/upload")
        async def upload_file(
            file: UploadFile,
            storage: ObjectStorageClient = Depends(get_storage_client)
        ):
            # Use storage client
            storage_key = storage.upload_log_sample(...)
            return {"storage_key": storage_key}
        ```
    """
    global _storage_client

    if _storage_client is None:
        try:
            logger.info("initializing_storage_client_dependency")
            config = StorageConfig.from_env()
            _storage_client = ObjectStorageClient(config)
            logger.info("storage_client_dependency_initialized")
        except Exception as e:
            logger.error(
                "storage_client_initialization_failed",
                error=str(e),
            )
            raise RuntimeError(
                f"Failed to initialize storage client: {str(e)}"
            ) from e

    return _storage_client


def get_storage_config() -> StorageConfig:
    """
    FastAPI dependency for storage configuration (read-only).

    Returns:
        StorageConfig: Storage configuration object

    Example:
        ```python
        @router.get("/config/storage")
        async def get_storage_settings(
            config: StorageConfig = Depends(get_storage_config)
        ):
            return {
                "retention_enabled": config.retention_enabled,
                "retention_days": config.retention_days,
                "max_upload_size_mb": config.max_upload_size_mb,
            }
        ```
    """
    return StorageConfig.from_env()


@asynccontextmanager
async def storage_client_context() -> AsyncGenerator[ObjectStorageClient, None]:
    """
    Async context manager for object storage client.

    Provides proper resource cleanup for storage operations. Use this in
    async contexts where you need fine-grained control over client lifecycle.

    Yields:
        ObjectStorageClient: Configured storage client

    Example:
        ```python
        async def process_upload():
            async with storage_client_context() as storage:
                storage_key = storage.upload_log_sample(...)
                # Client will be properly cleaned up after this block
        ```
    """
    client = None
    try:
        config = StorageConfig.from_env()
        client = ObjectStorageClient(config)
        logger.debug("storage_client_context_created")
        yield client
    finally:
        # Note: boto3 clients don't require explicit cleanup,
        # but we log for observability
        if client:
            logger.debug("storage_client_context_closed")


def reset_storage_client() -> None:
    """
    Reset the singleton storage client instance.

    Used primarily for testing to force reinitialization of the client
    with different configuration.

    Warning:
        This should only be used in test scenarios. Do not use in production code.
    """
    global _storage_client
    _storage_client = None
    logger.debug("storage_client_singleton_reset")
