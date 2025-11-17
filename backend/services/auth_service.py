"""
Authentication service for multi-provider authentication and token management.
"""
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID

from backend.models.user import User
from backend.models.role import Role
from backend.models.enums import UserRoleEnum
from backend.repositories.user_repository import UserRepository
from backend.repositories.role_repository import RoleRepository
from backend.core.security import (
    hash_password,
    verify_password,
    create_jwt_token,
    decode_jwt_token
)
from backend.core.config import settings
from backend.core.exceptions import (
    InvalidCredentialsError,
    UserNotFoundError,
    TokenExpiredError,
    InvalidTokenError,
    ProviderNotEnabledError,
    UserAlreadyExistsError,
    UserInactiveError
)


class AuthService:
    """Service for authentication and authorization operations."""

    def __init__(self, user_repository: UserRepository, role_repository: RoleRepository):
        """
        Initialize auth service.

        Args:
            user_repository: User repository instance
            role_repository: Role repository instance
        """
        self.user_repo = user_repository
        self.role_repo = role_repository

    async def authenticate_local(self, username: str, password: str) -> User:
        """
        Authenticate user with local username/password.

        Args:
            username: Username
            password: Plain text password

        Returns:
            Authenticated user with roles

        Raises:
            ProviderNotEnabledError: If local auth is disabled
            InvalidCredentialsError: If credentials are invalid
            UserInactiveError: If user account is inactive
        """
        if not settings.local_auth_enabled:
            raise ProviderNotEnabledError("Local authentication")

        user = await self.user_repo.get_by_username(username)
        if not user:
            raise InvalidCredentialsError()

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError()

        if not user.is_active:
            raise UserInactiveError()

        return user

    async def register_local_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None
    ) -> User:
        """
        Register a new local user.

        Args:
            username: Username
            email: Email address
            password: Plain text password
            full_name: Full name (optional)

        Returns:
            Created user

        Raises:
            ProviderNotEnabledError: If local auth is disabled
            UserAlreadyExistsError: If user already exists
        """
        if not settings.local_auth_enabled:
            raise ProviderNotEnabledError("Local authentication")

        # Check if user already exists
        existing_user = await self.user_repo.get_by_username(username)
        if existing_user:
            raise UserAlreadyExistsError(f"Username '{username}' already exists")

        existing_email = await self.user_repo.get_by_email(email)
        if existing_email:
            raise UserAlreadyExistsError(f"Email '{email}' already exists")

        # Hash password
        hashed_password = hash_password(password)

        # Create user
        user = await self.user_repo.create(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            auth_provider="local",
            is_active=True
        )

        # Assign default REQUESTOR role
        requestor_role = await self.role_repo.get_by_name(UserRoleEnum.REQUESTOR)
        if requestor_role:
            await self.user_repo.add_role(user.id, requestor_role.id)

        # Reload user with roles
        user = await self.user_repo.get_by_id(user.id)
        return user

    async def change_password(
        self,
        user_id: UUID,
        old_password: str,
        new_password: str
    ) -> None:
        """
        Change user password.

        Args:
            user_id: User ID
            old_password: Current password
            new_password: New password

        Raises:
            UserNotFoundError: If user not found
            InvalidCredentialsError: If old password is incorrect
        """
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        if not verify_password(old_password, user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect")

        # Update password
        hashed_password = hash_password(new_password)
        await self.user_repo.update(user_id, hashed_password=hashed_password)

    async def authenticate_saml(self, saml_response: Dict[str, Any]) -> User:
        """
        Authenticate user with SAML response.

        Args:
            saml_response: Parsed SAML assertion

        Returns:
            Authenticated user

        Raises:
            ProviderNotEnabledError: If SAML is not enabled
        """
        if not settings.saml_enabled:
            raise ProviderNotEnabledError("SAML")

        # Extract user attributes from SAML response
        external_id = saml_response.get("subject")
        email = saml_response.get("email")
        full_name = saml_response.get("name")

        # Find or create user
        user = await self.user_repo.get_by_external_id(external_id, "saml")
        if not user:
            user = await self._create_sso_user(
                external_id=external_id,
                email=email,
                full_name=full_name,
                auth_provider="saml"
            )

        # Update last login
        await self.update_last_login(user.id)

        return user

    async def authenticate_oauth(self, code: str, provider: str = "oauth") -> User:
        """
        Authenticate user with OAuth code.

        Args:
            code: OAuth authorization code
            provider: OAuth provider name

        Returns:
            Authenticated user

        Raises:
            ProviderNotEnabledError: If OAuth is not enabled
        """
        if not settings.oauth_enabled:
            raise ProviderNotEnabledError("OAuth")

        # TODO: Implement OAuth token exchange using authlib
        # This is a placeholder for the OAuth flow:
        # 1. Exchange code for access token
        # 2. Fetch user info from provider
        # 3. Find or create user
        # 4. Update last login

        # For now, raise NotImplementedError
        raise NotImplementedError("OAuth authentication not yet implemented")

    async def authenticate_oidc(self, id_token: str) -> User:
        """
        Authenticate user with OIDC ID token.

        Args:
            id_token: OIDC ID token

        Returns:
            Authenticated user

        Raises:
            ProviderNotEnabledError: If OIDC is not enabled
        """
        if not settings.oidc_enabled:
            raise ProviderNotEnabledError("OIDC")

        # TODO: Implement OIDC token validation using authlib
        # This is a placeholder for the OIDC flow:
        # 1. Validate ID token
        # 2. Extract claims (sub, email, name)
        # 3. Find or create user
        # 4. Update last login

        # For now, raise NotImplementedError
        raise NotImplementedError("OIDC authentication not yet implemented")

    async def _create_sso_user(
        self,
        external_id: str,
        email: str,
        full_name: Optional[str],
        auth_provider: str
    ) -> User:
        """
        Create a new user from SSO authentication.

        Args:
            external_id: External user ID from SSO provider
            email: Email address
            full_name: Full name
            auth_provider: Auth provider (saml, oauth, oidc)

        Returns:
            Created user
        """
        # Generate username from email
        username = email.split("@")[0]

        # Create user
        user = await self.user_repo.create(
            username=username,
            email=email,
            full_name=full_name,
            auth_provider=auth_provider,
            external_id=external_id,
            is_active=True
        )

        # Assign default REQUESTOR role
        requestor_role = await self.role_repo.get_by_name(UserRoleEnum.REQUESTOR)
        if requestor_role:
            await self.user_repo.add_role(user.id, requestor_role.id)

        # Reload user with roles
        user = await self.user_repo.get_by_id(user.id)
        return user

    def create_access_token(self, user_id: UUID, roles: List[str]) -> str:
        """
        Create JWT access token.

        Args:
            user_id: User ID
            roles: List of role names

        Returns:
            JWT access token
        """
        expires_delta = timedelta(minutes=settings.jwt_expiration_minutes)
        token_data = {
            "sub": str(user_id),
            "roles": roles,
            "type": "access"
        }
        return create_jwt_token(token_data, expires_delta)

    def create_refresh_token(self, user_id: UUID) -> str:
        """
        Create JWT refresh token.

        Args:
            user_id: User ID

        Returns:
            JWT refresh token
        """
        expires_delta = timedelta(days=settings.jwt_refresh_expiration_days)
        token_data = {
            "sub": str(user_id),
            "type": "refresh"
        }
        return create_jwt_token(token_data, expires_delta)

    def verify_token(self, token: str) -> Dict[str, Any]:
        """
        Verify and decode JWT token.

        Args:
            token: JWT token

        Returns:
            Token payload

        Raises:
            TokenExpiredError: If token has expired
            InvalidTokenError: If token is invalid
        """
        return decode_jwt_token(token)

    async def refresh_access_token(self, refresh_token: str) -> str:
        """
        Generate new access token from refresh token.

        Args:
            refresh_token: Refresh token

        Returns:
            New access token

        Raises:
            InvalidTokenError: If refresh token is invalid
        """
        payload = self.verify_token(refresh_token)

        # Verify token type
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Invalid token type")

        # Get user ID
        user_id = UUID(payload.get("sub"))

        # Get user with roles
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        if not user.is_active:
            raise UserInactiveError()

        # Create new access token
        roles = [role.name for role in user.roles]
        return self.create_access_token(user_id, roles)

    async def get_current_user(self, token: str) -> User:
        """
        Get current user from token.

        Args:
            token: JWT token

        Returns:
            User with roles

        Raises:
            InvalidTokenError: If token is invalid
            UserNotFoundError: If user not found
            UserInactiveError: If user is inactive
        """
        payload = self.verify_token(token)

        # Get user ID from token
        user_id = UUID(payload.get("sub"))

        # Fetch user with roles
        user = await self.user_repo.get_by_id(user_id)
        if not user:
            raise UserNotFoundError()

        if not user.is_active:
            raise UserInactiveError()

        return user

    async def update_last_login(self, user_id: UUID) -> None:
        """
        Update user's last login timestamp.

        Args:
            user_id: User ID
        """
        await self.user_repo.update(user_id, last_login=datetime.utcnow())

    async def deactivate_user(self, user_id: UUID) -> None:
        """
        Deactivate a user account.

        Args:
            user_id: User ID
        """
        await self.user_repo.update(user_id, is_active=False)
