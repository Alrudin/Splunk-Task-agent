"""
Pydantic schemas for authentication API requests and responses.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


class LocalLoginRequest(BaseModel):
    """Request schema for local login."""

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    password: str = Field(..., min_length=1, description="Password")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "admin",
                "password": "securepassword123"
            }
        }
    )


class RegisterRequest(BaseModel):
    """Request schema for user registration."""

    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: EmailStr = Field(..., description="Email address")
    password: str = Field(..., min_length=8, description="Password (min 8 characters)")
    full_name: Optional[str] = Field(None, max_length=100, description="Full name")

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")

        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)

        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one digit"
            )

        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """Validate username format."""
        if not v.replace("_", "").replace("-", "").isalnum():
            raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "johndoe",
                "email": "john.doe@example.com",
                "password": "SecurePass123",
                "full_name": "John Doe"
            }
        }
    )


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh."""

    refresh_token: str = Field(..., description="Refresh token")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }
    )


class ChangePasswordRequest(BaseModel):
    """Request schema for password change."""

    old_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=8, description="New password")

    @field_validator("new_password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")

        has_upper = any(c.isupper() for c in v)
        has_lower = any(c.islower() for c in v)
        has_digit = any(c.isdigit() for c in v)

        if not (has_upper and has_lower and has_digit):
            raise ValueError(
                "Password must contain at least one uppercase letter, "
                "one lowercase letter, and one digit"
            )

        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "old_password": "OldPass123",
                "new_password": "NewSecurePass456"
            }
        }
    )


class SAMLCallbackRequest(BaseModel):
    """Request schema for SAML callback."""

    saml_response: str = Field(..., description="SAML response")
    relay_state: Optional[str] = Field(None, description="Relay state")


class OAuthCallbackRequest(BaseModel):
    """Request schema for OAuth callback."""

    code: str = Field(..., description="OAuth authorization code")
    state: Optional[str] = Field(None, description="State parameter")


class OIDCCallbackRequest(BaseModel):
    """Request schema for OIDC callback."""

    id_token: str = Field(..., description="OIDC ID token")
    state: Optional[str] = Field(None, description="State parameter")


class TokenResponse(BaseModel):
    """Response schema for token data."""

    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 3600
            }
        }
    )


class UserResponse(BaseModel):
    """Response schema for user data."""

    id: UUID = Field(..., description="User ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    is_active: bool = Field(..., description="Account active status")
    auth_provider: str = Field(..., description="Authentication provider")
    roles: List[str] = Field(..., description="User roles")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "username": "johndoe",
                "email": "john.doe@example.com",
                "full_name": "John Doe",
                "is_active": True,
                "auth_provider": "local",
                "roles": ["REQUESTOR"],
                "last_login": "2025-01-15T10:30:00Z",
                "created_at": "2025-01-01T00:00:00Z"
            }
        }
    )


class LoginResponse(BaseModel):
    """Response schema for login."""

    user: UserResponse = Field(..., description="User information")
    tokens: TokenResponse = Field(..., description="Authentication tokens")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "username": "johndoe",
                    "email": "john.doe@example.com",
                    "full_name": "John Doe",
                    "is_active": True,
                    "auth_provider": "local",
                    "roles": ["REQUESTOR"],
                    "last_login": "2025-01-15T10:30:00Z",
                    "created_at": "2025-01-01T00:00:00Z"
                },
                "tokens": {
                    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "token_type": "bearer",
                    "expires_in": 3600
                }
            }
        }
    )


class AuthProvidersResponse(BaseModel):
    """Response schema for available authentication providers."""

    local_enabled: bool = Field(..., description="Local authentication enabled")
    saml_enabled: bool = Field(..., description="SAML SSO enabled")
    oauth_enabled: bool = Field(..., description="OAuth enabled")
    oidc_enabled: bool = Field(..., description="OIDC enabled")
    saml_login_url: Optional[str] = Field(None, description="SAML login URL")
    oauth_authorize_url: Optional[str] = Field(None, description="OAuth authorization URL")
    oidc_authorize_url: Optional[str] = Field(None, description="OIDC authorization URL")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "local_enabled": True,
                "saml_enabled": False,
                "oauth_enabled": False,
                "oidc_enabled": False,
                "saml_login_url": None,
                "oauth_authorize_url": None,
                "oidc_authorize_url": None
            }
        }
    )
