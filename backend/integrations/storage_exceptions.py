"""
Object Storage Exception Classes

Custom exceptions for object storage operations with context data
and HTTP status code mappings for API responses.
"""

from typing import Any, Dict, Optional


class StorageException(Exception):
    """Base exception class for all storage-related errors."""

    def __init__(
        self,
        message: str,
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
        status_code: int = 500,
    ):
        """
        Initialize storage exception.

        Args:
            message: Human-readable error message
            original_exception: Original exception that was caught (if applicable)
            context: Additional context data (bucket, key, operation, etc.)
            status_code: HTTP status code for API responses
        """
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception
        self.context = context or {}
        self.status_code = status_code

    def __str__(self) -> str:
        """Return formatted error message with context."""
        base_msg = self.message
        if self.context:
            context_str = ", ".join(f"{k}={v}" for k, v in self.context.items())
            base_msg = f"{base_msg} ({context_str})"
        if self.original_exception:
            base_msg = f"{base_msg} - Original error: {str(self.original_exception)}"
        return base_msg

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON serialization."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "context": self.context,
            "status_code": self.status_code,
        }


class StorageConnectionError(StorageException):
    """Raised when connection to MinIO/S3 fails."""

    def __init__(
        self,
        message: str = "Failed to connect to object storage",
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            original_exception=original_exception,
            context=context,
            status_code=503,  # Service Unavailable
        )


class StorageUploadError(StorageException):
    """Raised when upload operation fails."""

    def __init__(
        self,
        message: str = "Failed to upload object to storage",
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            original_exception=original_exception,
            context=context,
            status_code=500,  # Internal Server Error
        )


class StorageDownloadError(StorageException):
    """Raised when download operation fails."""

    def __init__(
        self,
        message: str = "Failed to download object from storage",
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            original_exception=original_exception,
            context=context,
            status_code=500,  # Internal Server Error
        )


class StorageNotFoundError(StorageException):
    """Raised when requested object doesn't exist."""

    def __init__(
        self,
        message: str = "Object not found in storage",
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            original_exception=original_exception,
            context=context,
            status_code=404,  # Not Found
        )


class StorageBucketError(StorageException):
    """Raised when bucket operations fail."""

    def __init__(
        self,
        message: str = "Bucket operation failed",
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            original_exception=original_exception,
            context=context,
            status_code=500,  # Internal Server Error
        )


class StorageRetentionError(StorageException):
    """Raised when retention cleanup fails."""

    def __init__(
        self,
        message: str = "Retention cleanup operation failed",
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            original_exception=original_exception,
            context=context,
            status_code=500,  # Internal Server Error
        )


class StorageQuotaExceededError(StorageException):
    """Raised when upload exceeds size limits."""

    def __init__(
        self,
        message: str = "Upload exceeds size limit",
        original_exception: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            original_exception=original_exception,
            context=context,
            status_code=413,  # Payload Too Large
        )
