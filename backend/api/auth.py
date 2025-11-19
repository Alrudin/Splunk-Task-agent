"""
FastAPI router for authentication endpoints.
"""
from typing import Dict
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.models.enums import AuditAction
from backend.repositories.user_repository import UserRepository
from backend.repositories.role_repository import RoleRepository
from backend.services.auth_service import AuthService
from backend.services.audit_service import AuditService
from backend.schemas.auth import (
    LocalLoginRequest,
    RegisterRequest,
    RefreshTokenRequest,
    ChangePasswordRequest,
    SAMLCallbackRequest,
    OAuthCallbackRequest,
    OIDCCallbackRequest,
    LoginResponse,
    TokenResponse,
    UserResponse,
    AuthProvidersResponse
)
from backend.core.config import settings
from backend.core.dependencies import get_current_active_user, get_audit_service
from backend.core.exceptions import InvalidCredentialsError, ProviderNotEnabledError


router = APIRouter(prefix="/auth", tags=["Authentication"])


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Dependency to get AuthService instance."""
    user_repo = UserRepository(db)
    role_repo = RoleRepository(db)
    return AuthService(user_repo, role_repo)


@router.get(
    "/providers",
    response_model=AuthProvidersResponse,
    summary="Get available authentication providers",
    description="Returns configuration of enabled authentication providers and their login URLs"
)
async def get_auth_providers() -> AuthProvidersResponse:
    """Get available authentication providers and their configuration."""
    return AuthProvidersResponse(
        local_enabled=settings.local_auth_enabled,
        saml_enabled=settings.saml_enabled,
        oauth_enabled=settings.oauth_enabled,
        oidc_enabled=settings.oidc_enabled,
        saml_login_url=settings.saml_login_url if settings.saml_enabled else None,
        oauth_authorize_url=settings.oauth_authorize_url if settings.oauth_enabled else None,
        oidc_authorize_url=settings.oidc_authorize_url if settings.oidc_enabled else None
    )


@router.post(
    "/login/local",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Login with local credentials",
    description="Authenticate with username and password. Returns user info and JWT tokens."
)
async def login_local(
    login_request: LocalLoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    audit_service: AuditService = Depends(get_audit_service)
) -> LoginResponse:
    """Login with local username/password."""
    # Authenticate user
    user = await auth_service.authenticate_local(login_request.username, login_request.password)

    # Generate tokens
    roles = [role.name for role in user.roles]
    access_token = auth_service.create_access_token(user.id, roles)
    refresh_token = auth_service.create_refresh_token(user.id)

    # Update last login
    await auth_service.update_last_login(user.id)

    # Log audit event
    await audit_service.log_action(
        user_id=user.id,
        action=AuditAction.LOGIN,
        entity_type="user",
        entity_id=user.id,
        details={"auth_provider": "local", "username": user.username},
        request=request
    )
    await db.commit()

    # Build response
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        auth_provider=user.auth_provider,
        roles=roles,
        last_login=user.last_login,
        created_at=user.created_at
    )

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60
    )

    return LoginResponse(user=user_response, tokens=token_response)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register new user",
    description="Register a new user with local authentication. Returns created user info."
)
async def register(
    register_request: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    audit_service: AuditService = Depends(get_audit_service)
) -> UserResponse:
    """Register a new local user."""
    # Create user
    user = await auth_service.register_local_user(
        username=register_request.username,
        email=register_request.email,
        password=register_request.password,
        full_name=register_request.full_name
    )

    # Log audit event
    await audit_service.log_action(
        user_id=user.id,
        action=AuditAction.USER_CREATED,
        entity_type="user",
        entity_id=user.id,
        details={"username": user.username, "auth_provider": "local"},
        request=request
    )
    await db.commit()

    # Build response
    roles = [role.name for role in user.roles]
    return UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        auth_provider=user.auth_provider,
        roles=roles,
        last_login=user.last_login,
        created_at=user.created_at
    )


@router.post(
    "/callback/saml",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="SAML SSO callback",
    description="Handle SAML SSO callback. Returns user info and JWT tokens."
)
async def saml_callback(
    saml_request: SAMLCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    audit_service: AuditService = Depends(get_audit_service)
) -> LoginResponse:
    """Handle SAML SSO callback."""
    # Check if SAML is enabled
    if not settings.saml_enabled:
        raise ProviderNotEnabledError("SAML")

    # TODO: Implement real SAML response parsing and validation
    # The following is a placeholder implementation:
    # 1. Decode base64-encoded SAML response
    # 2. Parse XML and validate signature
    # 3. Extract user attributes (subject, email, name)
    # 4. Validate assertions and conditions
    #
    # For production, integrate with python3-saml or similar library:
    # from onelogin.saml2.auth import OneLogin_Saml2_Auth
    # from onelogin.saml2.utils import OneLogin_Saml2_Utils
    #
    # Example:
    # auth = OneLogin_Saml2_Auth(request_data, saml_settings)
    # auth.process_response()
    # errors = auth.get_errors()
    # if len(errors) == 0:
    #     saml_data = {
    #         "subject": auth.get_nameid(),
    #         "email": auth.get_attribute("email")[0],
    #         "name": auth.get_attribute("name")[0]
    #     }

    # Placeholder: This will fail in production until real SAML parsing is implemented
    from backend.core.exceptions import NotImplementedEndpointError
    raise NotImplementedEndpointError(
        "SAML authentication requires integration with a SAML library. "
        "Please configure python3-saml or onelogin-saml and implement response parsing."
    )

    # Generate tokens
    roles = [role.name for role in user.roles]
    access_token = auth_service.create_access_token(user.id, roles)
    refresh_token = auth_service.create_refresh_token(user.id)

    # This code is unreachable due to NotImplementedEndpointError above
    # But keeping the pattern for when SAML is implemented
    # Log audit event
    # await audit_service.log_action(
    #     user_id=user.id,
    #     action=AuditAction.LOGIN,
    #     entity_type="user",
    #     entity_id=user.id,
    #     details={"auth_provider": "saml", "username": user.username},
    #     request=request
    # )
    # await db.commit()

    # Build response
    # user_response = UserResponse(
    #     id=user.id,
    #     username=user.username,
    #     email=user.email,
    #     full_name=user.full_name,
    #     is_active=user.is_active,
    #     auth_provider=user.auth_provider,
    #     roles=roles,
    #     last_login=user.last_login,
    #     created_at=user.created_at
    # )

    # token_response = TokenResponse(
    #     access_token=access_token,
    #     refresh_token=refresh_token,
    #     token_type="bearer",
    #     expires_in=settings.jwt_expiration_minutes * 60
    # )

    # return LoginResponse(user=user_response, tokens=token_response)


@router.post(
    "/callback/oauth",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="OAuth callback",
    description="Handle OAuth callback. Returns user info and JWT tokens."
)
async def oauth_callback(
    oauth_request: OAuthCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    audit_service: AuditService = Depends(get_audit_service)
) -> LoginResponse:
    """Handle OAuth callback."""
    # Check if OAuth is enabled
    if not settings.oauth_enabled:
        raise ProviderNotEnabledError("OAuth")

    # Authenticate user
    user = await auth_service.authenticate_oauth(oauth_request.code)

    # Generate tokens
    roles = [role.name for role in user.roles]
    access_token = auth_service.create_access_token(user.id, roles)
    refresh_token = auth_service.create_refresh_token(user.id)

    # Log audit event
    await audit_service.log_action(
        user_id=user.id,
        action=AuditAction.LOGIN,
        entity_type="user",
        entity_id=user.id,
        details={"auth_provider": "oauth", "username": user.username},
        request=request
    )
    await db.commit()

    # Build response
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        auth_provider=user.auth_provider,
        roles=roles,
        last_login=user.last_login,
        created_at=user.created_at
    )

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60
    )

    return LoginResponse(user=user_response, tokens=token_response)


@router.post(
    "/callback/oidc",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="OIDC callback",
    description="Handle OIDC callback. Returns user info and JWT tokens."
)
async def oidc_callback(
    oidc_request: OIDCCallbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    audit_service: AuditService = Depends(get_audit_service)
) -> LoginResponse:
    """Handle OIDC callback."""
    # Check if OIDC is enabled
    if not settings.oidc_enabled:
        raise ProviderNotEnabledError("OIDC")

    # Authenticate user
    user = await auth_service.authenticate_oidc(oidc_request.id_token)

    # Generate tokens
    roles = [role.name for role in user.roles]
    access_token = auth_service.create_access_token(user.id, roles)
    refresh_token = auth_service.create_refresh_token(user.id)

    # Log audit event
    await audit_service.log_action(
        user_id=user.id,
        action=AuditAction.LOGIN,
        entity_type="user",
        entity_id=user.id,
        details={"auth_provider": "oidc", "username": user.username},
        request=request
    )
    await db.commit()

    # Build response
    user_response = UserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        auth_provider=user.auth_provider,
        roles=roles,
        last_login=user.last_login,
        created_at=user.created_at
    )

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60
    )

    return LoginResponse(user=user_response, tokens=token_response)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token",
    description="Generate a new access token using a valid refresh token."
)
async def refresh_token(
    request: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> TokenResponse:
    """Refresh access token."""
    # Generate new access token
    access_token = await auth_service.refresh_access_token(request.refresh_token)

    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,
        token_type="bearer",
        expires_in=settings.jwt_expiration_minutes * 60
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user",
    description="Get information about the currently authenticated user."
)
async def get_me(
    current_user: User = Depends(get_current_active_user)
) -> UserResponse:
    """Get current user information."""
    roles = [role.name for role in current_user.roles]
    return UserResponse(
        id=current_user.id,
        username=current_user.username,
        email=current_user.email,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        auth_provider=current_user.auth_provider,
        roles=roles,
        last_login=current_user.last_login,
        created_at=current_user.created_at
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Logout",
    description="Logout current user. Client should discard tokens."
)
async def logout(
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service)
) -> Dict[str, str]:
    """Logout current user."""
    # Log audit event
    await audit_service.log_action(
        user_id=current_user.id,
        action=AuditAction.LOGOUT,
        entity_type="user",
        entity_id=current_user.id,
        details={"username": current_user.username},
        request=request
    )
    await db.commit()

    return {"message": "Successfully logged out"}


@router.post(
    "/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change password",
    description="Change password for local users."
)
async def change_password(
    password_request: ChangePasswordRequest,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
    audit_service: AuditService = Depends(get_audit_service)
) -> Dict[str, str]:
    """Change user password."""
    # Verify user has local auth
    if current_user.auth_provider != "local":
        raise ProviderNotEnabledError(
            f"Password change not supported for {current_user.auth_provider} users"
        )

    # Change password
    await auth_service.change_password(
        current_user.id,
        password_request.old_password,
        password_request.new_password
    )

    # Log audit event
    await audit_service.log_action(
        user_id=current_user.id,
        action=AuditAction.PASSWORD_CHANGED,
        entity_type="user",
        entity_id=current_user.id,
        details={"username": current_user.username},
        request=request
    )
    await db.commit()

    return {"message": "Password changed successfully"}
