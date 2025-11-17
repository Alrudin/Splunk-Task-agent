"""
Integrations Module

This module provides client classes for external service integrations including:
- Object Storage (MinIO/S3) for artifacts and log samples
- Vector Database (Pinecone) for RAG knowledge retrieval
- LLM Runtime (Ollama) for TA generation
- Splunk Sandbox orchestration for validation

Each integration is implemented as a standalone client with configuration management,
error handling, and async support for FastAPI integration.
"""

from backend.integrations.object_storage_client import ObjectStorageClient, StorageConfig
from backend.integrations.storage_exceptions import (
    StorageException,
    StorageConnectionError,
    StorageUploadError,
    StorageDownloadError,
    StorageNotFoundError,
    StorageBucketError,
    StorageRetentionError,
    StorageQuotaExceededError,
)

__all__ = [
    "ObjectStorageClient",
    "StorageConfig",
    "StorageException",
    "StorageConnectionError",
    "StorageUploadError",
    "StorageDownloadError",
    "StorageNotFoundError",
    "StorageBucketError",
    "StorageRetentionError",
    "StorageQuotaExceededError",
]
