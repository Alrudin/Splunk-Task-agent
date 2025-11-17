"""
Custom exceptions for object storage operations.
"""
from typing import Any, Dict, Optional


class StorageError(Exception):
    """Base exception for storage errors."""

    def __init__(
        self,
        message: str,
        original_exception: Optional[Exception] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception
        self.metadata = metadata or {}

    def __str__(self) -> str:
        base = self.message
        if self.metadata:
            base += f" | Metadata: {self.metadata}"
        if self.original_exception:
            base += f" | Original: {str(self.original_exception)}"
        return base


class FileNotFoundError(StorageError):
    """Raised when object doesn't exist in storage."""

    def __init__(
        self,
        bucket: str,
        key: str,
        original_exception: Optional[Exception] = None,
    ):
        message = f"File not found in bucket '{bucket}' with key '{key}'"
        metadata = {"bucket": bucket, "key": key}
        super().__init__(message, original_exception, metadata)


class UploadError(StorageError):
    """Raised on upload failures."""

    def __init__(
        self,
        bucket: str,
        key: str,
        original_exception: Optional[Exception] = None,
        size: Optional[int] = None,
    ):
        message = f"Failed to upload file to bucket '{bucket}' with key '{key}'"
        metadata = {"bucket": bucket, "key": key}
        if size is not None:
            metadata["size"] = size
        super().__init__(message, original_exception, metadata)


class DownloadError(StorageError):
    """Raised on download failures."""

    def __init__(
        self,
        bucket: str,
        key: str,
        original_exception: Optional[Exception] = None,
    ):
        message = f"Failed to download file from bucket '{bucket}' with key '{key}'"
        metadata = {"bucket": bucket, "key": key}
        super().__init__(message, original_exception, metadata)


class QuotaExceededError(StorageError):
    """Raised when storage quota is exceeded."""

    def __init__(
        self,
        message: str = "Storage quota exceeded",
        current_size: Optional[int] = None,
        max_size: Optional[int] = None,
    ):
        metadata = {}
        if current_size is not None:
            metadata["current_size"] = current_size
        if max_size is not None:
            metadata["max_size"] = max_size
        super().__init__(message, metadata=metadata)