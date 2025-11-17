"""
FastAPI Dependency Injection

Dependency injection functions for FastAPI endpoints to provide
configured service clients including object storage, database sessions,
and other shared resources.

Note: The object storage client currently uses synchronous boto3 operations.
For async FastAPI endpoints, file I/O operations will be executed synchronously
within the async context. For large file operations, consider using
asyncio.to_thread() or run_in_executor() to avoid blocking the event loop.
"""

from typing import Optional

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
