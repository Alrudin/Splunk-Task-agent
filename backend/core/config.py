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
    saml_login_url: Optional[str] = Field(default=None, description="SAML SP-initiated login URL")

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
    oidc_authorize_url: Optional[str] = Field(default=None, description="OIDC authorization endpoint URL")

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

    # MinIO / S3 Object Storage Settings
    minio_endpoint: str = Field(default="localhost:9000", description="MinIO endpoint (host:port)")
    minio_access_key: str = Field(..., description="MinIO access key")
    minio_secret_key: str = Field(..., description="MinIO secret key")
    minio_bucket_samples: str = Field(default="log-samples", description="Bucket for log samples")
    minio_bucket_tas: str = Field(default="ta-artifacts", description="Bucket for TA artifacts")
    minio_bucket_debug: str = Field(default="debug-bundles", description="Bucket for debug bundles")
    minio_use_ssl: bool = Field(default=False, description="Use SSL for MinIO connections")
    minio_region: str = Field(default="us-east-1", description="MinIO region")

    # Pinecone API Settings
    pinecone_api_key: str = Field(..., description="Pinecone API key for authentication")
    pinecone_environment: Optional[str] = Field(
        default=None,
        description="Pinecone environment (legacy, for non-serverless indexes; use cloud/region for serverless)"
    )
    pinecone_cloud: str = Field(default="aws", description="Cloud provider for serverless Pinecone")
    pinecone_region: str = Field(default="us-east-1", description="Region for serverless Pinecone deployment")

    # Pinecone Index Configuration
    pinecone_index_docs: str = Field(default="splunk-docs-index", description="Index name for Splunk documentation")
    pinecone_index_tas: str = Field(default="ta-examples-index", description="Index name for historical TA examples")
    pinecone_index_samples: str = Field(default="sample-logs-index", description="Index name for sample logs")
    pinecone_dimension: int = Field(default=768, description="Embedding dimension (768 for all-mpnet-base-v2)")
    pinecone_metric: str = Field(default="cosine", description="Distance metric for vector similarity")

    # Embedding Model Settings
    embedding_model_name: str = Field(
        default="sentence-transformers/all-mpnet-base-v2",
        description="Sentence transformer model for embedding generation"
    )
    embedding_batch_size: int = Field(default=32, description="Batch size for embedding encoding")
    embedding_normalize: bool = Field(default=True, description="Normalize embeddings to unit vectors")

    # Chunking Configuration
    chunk_size_words: int = Field(default=300, description="Number of words per document chunk")
    chunk_overlap_words: int = Field(default=50, description="Number of words to overlap between chunks")
    max_chunks_per_document: int = Field(default=100, description="Maximum number of chunks per document")

    # Query Settings
    pinecone_top_k: int = Field(default=10, description="Default number of results to return from queries")
    pinecone_query_timeout: int = Field(default=10, description="Query timeout in seconds")

    # Sample Retention & Upload Settings
    sample_retention_enabled: bool = Field(default=True, description="Enable sample retention policy")
    sample_retention_days: int = Field(default=90, description="Days to retain samples")
    max_sample_size_mb: int = Field(default=500, description="Maximum sample file size in MB")
    upload_chunk_size: int = Field(default=1048576, description="Upload chunk size in bytes (default 1MB)")

    # Ollama LLM Settings
    ollama_host: str = Field(default="localhost", description="Ollama server host")
    ollama_port: int = Field(default=11434, description="Ollama server port")
    ollama_model: str = Field(default="llama2", description="Ollama model name for TA generation")
    ollama_timeout: int = Field(default=300, description="Ollama request timeout in seconds")
    ollama_temperature: float = Field(default=0.7, description="LLM temperature for generation")
    ollama_max_tokens: int = Field(default=4096, description="Maximum tokens for LLM responses")
    ollama_use_ssl: bool = Field(default=False, description="Use HTTPS for Ollama connection")

    # Splunk Sandbox Settings
    splunk_image: str = Field(default="splunk/splunk:9.1.0", description="Splunk Docker image for validation")
    splunk_startup_timeout: int = Field(default=300, description="Splunk container startup timeout in seconds")
    splunk_admin_password: str = Field(default="admin123", description="Splunk admin password for sandbox")
    splunk_management_port_range_start: int = Field(default=18089, description="Start of port range for Splunk management")
    splunk_management_port_range_end: int = Field(default=18189, description="End of port range for Splunk management")
    docker_network: str = Field(default="splunk-ta-network", description="Docker network for Splunk containers")
    splunk_host: str = Field(default="localhost", description="Host address for Splunk REST API (use host.docker.internal in containers)")
    splunk_use_ssl: bool = Field(default=False, description="Use HTTPS for Splunk REST API connections")
    splunk_verify_ssl: bool = Field(default=False, description="Verify SSL certificates for Splunk REST API")

    # Validation Settings
    max_parallel_validations: int = Field(default=3, description="Maximum concurrent validation runs")
    validation_timeout: int = Field(default=1800, description="Validation timeout in seconds (30 minutes)")
    validation_retry_delay: int = Field(default=60, description="Delay before retrying queued validation (seconds)")
    validation_index_name: str = Field(default="ta_validation_test", description="Index name for validation tests")
    validation_field_coverage_threshold: float = Field(default=0.7, description="Minimum field coverage for PASSED (0.0-1.0)")

    # Web Browsing Control Settings
    allowed_web_domains: str = Field(
        default="splunk.com,splunkbase.splunk.com,github.com",
        description="Comma-separated list of allowed domains for web browsing"
    )
    blocked_web_domains: str = Field(
        default="",
        description="Comma-separated list of blocked domains (takes precedence over allowed)"
    )

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

    @field_validator("pinecone_api_key")
    @classmethod
    def validate_pinecone_api_key(cls, v: str) -> str:
        """Validate Pinecone API key is not empty."""
        if not v or v.strip() == "":
            raise ValueError("PINECONE_API_KEY must be set to a valid API key")
        return v

    @field_validator("ollama_temperature")
    @classmethod
    def validate_ollama_temperature(cls, v: float) -> float:
        """Validate Ollama temperature is in valid range."""
        if not 0.0 <= v <= 2.0:
            raise ValueError("OLLAMA_TEMPERATURE must be between 0.0 and 2.0")
        return v

    @field_validator("ollama_max_tokens")
    @classmethod
    def validate_ollama_max_tokens(cls, v: int) -> int:
        """Validate Ollama max tokens is positive."""
        if v <= 0:
            raise ValueError("OLLAMA_MAX_TOKENS must be positive")
        return v

    @field_validator("validation_field_coverage_threshold")
    @classmethod
    def validate_coverage_threshold(cls, v: float) -> float:
        """Validate field coverage threshold is between 0 and 1."""
        if not 0.0 <= v <= 1.0:
            raise ValueError("VALIDATION_FIELD_COVERAGE_THRESHOLD must be between 0.0 and 1.0")
        return v

    @field_validator("max_parallel_validations")
    @classmethod
    def validate_max_parallel_validations(cls, v: int) -> int:
        """Validate max parallel validations is positive."""
        if v <= 0:
            raise ValueError("MAX_PARALLEL_VALIDATIONS must be positive")
        return v

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def api_prefix(self) -> str:
        """Get API prefix path."""
        return f"/api/{self.api_version}"

    @property
    def ollama_base_url(self) -> str:
        """Get Ollama base URL for OpenAI client."""
        protocol = "https" if self.ollama_use_ssl else "http"
        return f"{protocol}://{self.ollama_host}:{self.ollama_port}/v1"

    @property
    def allowed_domains_list(self) -> List[str]:
        """Parse allowed domains from comma-separated string."""
        if not self.allowed_web_domains:
            return []
        return [domain.strip().lower() for domain in self.allowed_web_domains.split(",") if domain.strip()]

    @property
    def blocked_domains_list(self) -> List[str]:
        """Parse blocked domains from comma-separated string."""
        if not self.blocked_web_domains:
            return []
        return [domain.strip().lower() for domain in self.blocked_web_domains.split(",") if domain.strip()]


# Singleton settings instance
settings = Settings()


def get_settings() -> Settings:
    """
    Get the singleton settings instance.

    This function provides a consistent way to access settings
    and is useful for dependency injection in FastAPI.

    Returns:
        Settings instance loaded from environment
    """
    return settings
