"""
Configuration management using pydantic-settings.
Loads settings from environment variables and .env file.
"""
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore"
    )

    # Database Settings
    database_url: str = Field(..., description="PostgreSQL connection string")
    database_pool_size: int = Field(default=10, description="Connection pool size")
    database_max_overflow: int = Field(default=20, description="Max overflow connections")
    database_echo: bool = Field(default=False, description="Echo SQL queries")

    # JWT Settings
    jwt_secret_key: str = Field(..., description="Secret key for JWT signing")
    jwt_algorithm: str = Field(default="HS256", description="JWT signing algorithm")
    jwt_expiration_minutes: int = Field(default=60, description="Access token expiration in minutes")
    jwt_refresh_expiration_days: int = Field(default=7, description="Refresh token expiration in days")

    # Auth Provider Settings - Local
    local_auth_enabled: bool = Field(default=True, description="Enable local username/password auth")

    # Auth Provider Settings - SAML
    saml_enabled: bool = Field(default=False, description="Enable SAML SSO")
    saml_metadata_url: Optional[str] = Field(default=None, description="SAML IdP metadata URL")
    saml_entity_id: Optional[str] = Field(default=None, description="SAML Service Provider entity ID")

    # Auth Provider Settings - OAuth
    oauth_enabled: bool = Field(default=False, description="Enable OAuth authentication")
    oauth_client_id: Optional[str] = Field(default=None, description="OAuth client ID")
    oauth_client_secret: Optional[str] = Field(default=None, description="OAuth client secret")
    oauth_authorize_url: Optional[str] = Field(default=None, description="OAuth authorization endpoint")
    oauth_token_url: Optional[str] = Field(default=None, description="OAuth token endpoint")
    oauth_user_info_url: Optional[str] = Field(default=None, description="OAuth user info endpoint")

    # Auth Provider Settings - OIDC
    oidc_enabled: bool = Field(default=False, description="Enable OIDC authentication")
    oidc_client_id: Optional[str] = Field(default=None, description="OIDC client ID")
    oidc_client_secret: Optional[str] = Field(default=None, description="OIDC client secret")
    oidc_discovery_url: Optional[str] = Field(default=None, description="OIDC discovery URL")

    # Application Settings
    app_name: str = Field(default="Splunk TA Generator", description="Application name")
    app_version: str = Field(default="0.1.0", description="Application version")
    backend_host: str = Field(default="0.0.0.0", description="Backend host")
    backend_port: int = Field(default=8000, description="Backend port")
    frontend_url: str = Field(default="http://localhost:5173", description="Frontend URL")
    cors_origins: str = Field(default="http://localhost:5173", description="Comma-separated CORS origins")
    api_version: str = Field(default="v1", description="API version")

    # Logging Settings
    log_level: str = Field(default="INFO", description="Logging level")
    log_format: str = Field(default="json", description="Log format (json or text)")
    enable_audit_logging: bool = Field(default=True, description="Enable audit logging")

    @field_validator("jwt_secret_key")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Validate JWT secret key is not default/empty."""
        if not v or v == "change-me-in-production":
            raise ValueError("JWT_SECRET_KEY must be set to a secure value")
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters long")
        return v

    @field_validator("saml_metadata_url")
    @classmethod
    def validate_saml_config(cls, v: Optional[str], info) -> Optional[str]:
        """Validate SAML configuration when enabled."""
        if info.data.get("saml_enabled") and not v:
            raise ValueError("SAML_METADATA_URL is required when SAML_ENABLED=true")
        return v

    @field_validator("oauth_client_id")
    @classmethod
    def validate_oauth_config(cls, v: Optional[str], info) -> Optional[str]:
        """Validate OAuth configuration when enabled."""
        if info.data.get("oauth_enabled") and not v:
            raise ValueError("OAUTH_CLIENT_ID is required when OAUTH_ENABLED=true")
        return v

    @field_validator("oidc_client_id")
    @classmethod
    def validate_oidc_config(cls, v: Optional[str], info) -> Optional[str]:
        """Validate OIDC configuration when enabled."""
        if info.data.get("oidc_enabled") and not v:
            raise ValueError("OIDC_CLIENT_ID is required when OIDC_ENABLED=true")
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def api_prefix(self) -> str:
        """Get API prefix path."""
        return f"/api/{self.api_version}"


# Singleton settings instance
settings = Settings()
