"""
Custom exception classes for authentication and authorization.
"""
from typing import Dict, Optional
from fastapi import Request, status
from fastapi.responses import JSONResponse


class AppException(Exception):
    """Base application exception."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        headers: Optional[Dict[str, str]] = None
    ):
        self.status_code = status_code
        self.detail = detail
        self.headers = headers
        super().__init__(detail)


class InvalidCredentialsError(AppException):
    """Invalid username or password."""

    def __init__(self, detail: str = "Invalid username or password"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class UserNotFoundError(AppException):
    """User not found."""

    def __init__(self, detail: str = "User not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class TokenExpiredError(AppException):
    """Token has expired."""

    def __init__(self, detail: str = "Token has expired"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class InvalidTokenError(AppException):
    """Invalid authentication token."""

    def __init__(self, detail: str = "Invalid authentication token"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"}
        )


class InsufficientPermissionsError(AppException):
    """Insufficient permissions."""

    def __init__(self, detail: str = "Insufficient permissions"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class ProviderNotEnabledError(AppException):
    """Authentication provider not enabled."""

    def __init__(self, provider: str = "Provider"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{provider} authentication is not enabled"
        )


class UserInactiveError(AppException):
    """User account is inactive."""

    def __init__(self, detail: str = "User account is inactive"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail
        )


class UserAlreadyExistsError(AppException):
    """User already exists."""

    def __init__(self, detail: str = "User already exists"):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail
        )


class NotImplementedEndpointError(AppException):
    """Endpoint not yet implemented."""

    def __init__(self, detail: str = "This endpoint is not yet implemented"):
        super().__init__(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=detail
        )


# Request-related exceptions
class RequestNotFoundError(AppException):
    """Request not found."""

    def __init__(self, detail: str = "Request not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class SampleNotFoundError(AppException):
    """Sample not found."""

    def __init__(self, detail: str = "Sample not found"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail
        )


class InvalidRequestStateError(AppException):
    """Operation not allowed in current request state."""

    def __init__(self, detail: str = "Operation not allowed in current request state"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class FileSizeExceededError(AppException):
    """File size exceeds maximum allowed."""

    def __init__(self, max_size_mb: int = 500):
        super().__init__(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {max_size_mb}MB"
        )


class InvalidFileTypeError(AppException):
    """File type not allowed."""

    def __init__(self, detail: str = "File type not allowed"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


class NoSamplesAttachedError(AppException):
    """No samples attached to request."""

    def __init__(self, detail: str = "At least one sample must be attached before submission"):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail
        )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """
    Global exception handler for AppException instances.

    Args:
        request: FastAPI request object
        exc: AppException instance

    Returns:
        JSONResponse with error details
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )
