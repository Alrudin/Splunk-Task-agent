"""
FastAPI dependency functions for authentication and authorization.
"""
from typing import Callable
from uuid import UUID
from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.models.enums import UserRoleEnum
from backend.repositories.user_repository import UserRepository
from backend.repositories.request_repository import RequestRepository
from backend.repositories.log_sample_repository import LogSampleRepository
from backend.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from backend.core.security import decode_jwt_token
from backend.core.exceptions import (
    InvalidTokenError,
    UserNotFoundError,
    UserInactiveError,
    InsufficientPermissionsError
)
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.integrations.pinecone_client import PineconeClient
from backend.integrations.ollama_client import OllamaClient
from backend.services.request_service import RequestService


def get_token_from_header(authorization: str = Header(None)) -> str:
    """
    Extract Bearer token from Authorization header.

    Args:
        authorization: Authorization header value (optional)

    Returns:
        JWT token string

    Raises:
        InvalidTokenError: If header is missing or malformed
    """
    if not authorization:
        raise InvalidTokenError("Authorization header is missing")

    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise InvalidTokenError("Invalid authorization header format. Expected 'Bearer <token>'")

    return parts[1]


async def get_current_user(
    token: str = Depends(get_token_from_header),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        Current user with roles

    Raises:
        InvalidTokenError: If token is invalid
        UserNotFoundError: If user not found
        UserInactiveError: If user is inactive
    """
    try:
        # Decode token
        payload = decode_jwt_token(token)

        # Extract user ID
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise InvalidTokenError("Token missing 'sub' claim")

        user_id = UUID(user_id_str)

        # Fetch user with roles
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)

        if not user:
            raise UserNotFoundError()

        if not user.is_active:
            raise UserInactiveError()

        return user

    except ValueError:
        raise InvalidTokenError("Invalid user ID in token")


async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Get current active user.

    Args:
        current_user: Current user from get_current_user dependency

    Returns:
        Current active user

    Raises:
        UserInactiveError: If user is inactive
    """
    if not current_user.is_active:
        raise UserInactiveError()

    return current_user


def require_role(required_role: UserRoleEnum) -> Callable:
    """
    Factory function to create role-based dependency.

    Args:
        required_role: Required role enum

    Returns:
        Dependency function that checks for required role
    """
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        """Check if user has required role."""
        user_roles = [role.name for role in current_user.roles]

        if required_role.value not in user_roles:
            raise InsufficientPermissionsError(
                f"This action requires {required_role.value} role"
            )

        return current_user

    return role_checker


def require_any_role(*roles: UserRoleEnum) -> Callable:
    """
    Factory function to create dependency that checks for any of multiple roles.

    Args:
        roles: Required roles (user must have at least one)

    Returns:
        Dependency function that checks for any of the required roles
    """
    async def role_checker(current_user: User = Depends(get_current_active_user)) -> User:
        """Check if user has any of the required roles."""
        user_roles = [role.name for role in current_user.roles]
        required_role_names = [role.value for role in roles]

        if not any(role in user_roles for role in required_role_names):
            roles_str = ", ".join(required_role_names)
            raise InsufficientPermissionsError(
                f"This action requires one of the following roles: {roles_str}"
            )

        return current_user

    return role_checker


async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """
    Get current superuser.

    Args:
        current_user: Current active user

    Returns:
        Current superuser

    Raises:
        InsufficientPermissionsError: If user is not a superuser
    """
    if not current_user.is_superuser:
        raise InsufficientPermissionsError("This action requires superuser privileges")

    return current_user


# Pre-configured role dependencies
get_current_requestor = Depends(require_role(UserRoleEnum.REQUESTOR))
get_current_approver = Depends(require_role(UserRoleEnum.APPROVER))
get_current_admin = Depends(require_role(UserRoleEnum.ADMIN))
get_current_knowledge_manager = Depends(require_role(UserRoleEnum.KNOWLEDGE_MANAGER))


# Service dependencies

# Singleton instances
_storage_client: ObjectStorageClient = None
_pinecone_client: PineconeClient = None
_ollama_client: OllamaClient = None


def get_storage_client() -> ObjectStorageClient:
    """
    Get object storage client singleton instance.

    This function returns a singleton instance to avoid reinitializing
    the storage client on every request.

    Returns:
        ObjectStorageClient instance configured with settings
    """
    global _storage_client
    if _storage_client is None:
        _storage_client = ObjectStorageClient()
    return _storage_client


def get_pinecone_client() -> PineconeClient:
    """
    Get Pinecone client singleton instance.

    This function returns a singleton instance to avoid reinitializing
    the embedding model on every request, which would be expensive.

    Use with FastAPI's Depends() for dependency injection.

    Example:
        @app.get("/search")
        async def search(pc: PineconeClient = Depends(get_pinecone_client)):
            ...

    Returns:
        PineconeClient instance configured with settings
    """
    global _pinecone_client
    if _pinecone_client is None:
        _pinecone_client = PineconeClient()
    return _pinecone_client


def get_ollama_client() -> OllamaClient:
    """
    Get Ollama client singleton instance.

    This function returns a singleton instance to avoid reinitializing
    the OpenAI client on every request.

    Use with FastAPI's Depends() for dependency injection.

    Example:
        @app.post("/generate")
        async def generate(ollama: OllamaClient = Depends(get_ollama_client)):
            ...

    Returns:
        OllamaClient instance configured with settings
    """
    global _ollama_client
    if _ollama_client is None:
        _ollama_client = OllamaClient()
    return _ollama_client


async def get_sample_repository(
    db: AsyncSession = Depends(get_db),
) -> LogSampleRepository:
    """
    Get log sample repository instance.

    Args:
        db: Database session

    Returns:
        LogSampleRepository instance
    """
    return LogSampleRepository(db)

async def get_request_service(
    db: AsyncSession = Depends(get_db),
) -> RequestService:
    """
    Get request service instance with injected dependencies.

    Args:
        db: Database session

    Returns:
        RequestService instance
    """

    request_repo = RequestRepository(db)
    sample_repo = LogSampleRepository(db)
    storage_client = get_storage_client()

    return RequestService(
        request_repository=request_repo,
        sample_repository=sample_repo,
        storage_client=storage_client,
    )


async def get_approval_service(
    db: AsyncSession = Depends(get_db),
) -> "ApprovalService":
    """Get approval service instance with injected dependencies.

    Args:
        db: Database session

    Returns:
        ApprovalService instance with injected repositories
    """
    from backend.services.approval_service import ApprovalService
    from backend.repositories.audit_log_repository import AuditLogRepository

    request_repo = RequestRepository(db)
    audit_repo = AuditLogRepository(db)

    return ApprovalService(
        request_repository=request_repo,
        audit_log_repository=audit_repo,
    )


async def get_knowledge_service(
    db: AsyncSession = Depends(get_db)
) -> "KnowledgeService":
    """Get knowledge service instance with injected dependencies.

    Args:
        db: Database session

    Returns:
        KnowledgeService instance with injected repositories and clients
    """
    from backend.services.knowledge_service import KnowledgeService

    knowledge_repository = KnowledgeDocumentRepository(db)
    storage_client = get_storage_client()
    pinecone_client = get_pinecone_client()

    return KnowledgeService(
        knowledge_document_repository=knowledge_repository,
        storage_client=storage_client,
        pinecone_client=pinecone_client
    )


async def get_audit_service(
    db: AsyncSession = Depends(get_db)
) -> "AuditService":
    """Get audit service instance with injected dependencies.

    Args:
        db: Database session

    Returns:
        AuditService instance with injected repositories
    """
    from backend.services.audit_service import AuditService
    from backend.repositories.audit_log_repository import AuditLogRepository

    audit_repo = AuditLogRepository(db)

    return AuditService(audit_repository=audit_repo)


async def get_notification_service(
    db: AsyncSession = Depends(get_db)
) -> "NotificationService":
    """Get notification service instance with injected dependencies.

    Args:
        db: Database session

    Returns:
        NotificationService instance with injected repositories
    """
    from backend.services.notification_service import NotificationService
    from backend.services.audit_service import AuditService
    from backend.repositories.audit_log_repository import AuditLogRepository

    user_repo = UserRepository(db)
    request_repo = RequestRepository(db)
    audit_repo = AuditLogRepository(db)
    audit_service = AuditService(audit_repository=audit_repo)

    return NotificationService(
        user_repository=user_repo,
        request_repository=request_repo,
        audit_service=audit_service,
        db=db
    )
