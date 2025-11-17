"""
FastAPI dependency functions for authentication and authorization.
"""
from typing import Callable
from uuid import UUID
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.models.enums import UserRoleEnum
from backend.repositories.user_repository import UserRepository
from backend.core.security import decode_jwt_token
from backend.core.exceptions import (
    InvalidTokenError,
    UserNotFoundError,
    UserInactiveError,
    InsufficientPermissionsError
)


def get_token_from_header(authorization: str = Header(...)) -> str:
    """
    Extract Bearer token from Authorization header.

    Args:
        authorization: Authorization header value

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
