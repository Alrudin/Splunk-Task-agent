"""
Pydantic schemas for request and sample operations.

These schemas define the structure for request/response data validation,
serialization, and documentation in the FastAPI application.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.models.enums import RequestStatus


# Request Schemas
class CreateRequestRequest(BaseModel):
    """Schema for creating a new request."""

    source_system: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Name of the log source system",
        examples=["Apache Web Server", "Cisco ASA", "AWS CloudTrail"]
    )
    description: str = Field(
        ...,
        min_length=10,
        max_length=5000,
        description="Detailed description of ingestion requirements",
        examples=["Ingest Apache access logs from production web servers"]
    )
    cim_required: bool = Field(
        default=True,
        description="Whether CIM compliance is required"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata as JSON object"
    )

    @field_validator("source_system")
    @classmethod
    def validate_source_system(cls, v: str) -> str:
        """Validate source_system contains only allowed characters."""
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', v):
            raise ValueError(
                "source_system must contain only alphanumeric characters, "
                "spaces, hyphens, and underscores"
            )
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: str) -> str:
        """Validate description is not just whitespace."""
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("description must be at least 10 characters long")
        return stripped

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source_system": "Apache Web Server",
                "description": "Ingest Apache access logs from production web servers with CIM compliance",
                "cim_required": True,
                "metadata": {
                    "environment": "production",
                    "log_format": "combined"
                }
            }
        }
    )


class UpdateRequestRequest(BaseModel):
    """Schema for updating a request."""

    source_system: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Name of the log source system"
    )
    description: Optional[str] = Field(
        default=None,
        min_length=10,
        max_length=5000,
        description="Detailed description of ingestion requirements"
    )
    cim_required: Optional[bool] = Field(
        default=None,
        description="Whether CIM compliance is required"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional metadata as JSON object"
    )

    @field_validator("source_system")
    @classmethod
    def validate_source_system(cls, v: Optional[str]) -> Optional[str]:
        """Validate source_system contains only allowed characters."""
        if v is None:
            return v
        import re
        if not re.match(r'^[a-zA-Z0-9\s\-_]+$', v):
            raise ValueError(
                "source_system must contain only alphanumeric characters, "
                "spaces, hyphens, and underscores"
            )
        return v.strip()

    @field_validator("description")
    @classmethod
    def validate_description(cls, v: Optional[str]) -> Optional[str]:
        """Validate description is not just whitespace."""
        if v is None:
            return v
        stripped = v.strip()
        if len(stripped) < 10:
            raise ValueError("description must be at least 10 characters long")
        return stripped


class RequestResponse(BaseModel):
    """Schema for request response."""

    id: UUID = Field(..., description="Request unique identifier")
    created_by: UUID = Field(..., description="ID of user who created the request")
    status: RequestStatus = Field(..., description="Current status of the request")
    source_system: str = Field(..., description="Name of the log source system")
    description: str = Field(..., description="Description of ingestion requirements")
    cim_required: bool = Field(..., description="Whether CIM compliance is required")
    approved_by: Optional[UUID] = Field(None, description="ID of approver (if approved)")
    approved_at: Optional[datetime] = Field(None, description="Approval timestamp")
    rejection_reason: Optional[str] = Field(None, description="Rejection reason (if rejected)")
    completed_at: Optional[datetime] = Field(None, description="Completion timestamp")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    sample_count: int = Field(0, description="Number of attached samples")
    total_sample_size: int = Field(0, description="Total size of all samples in bytes")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_by": "550e8400-e29b-41d4-a716-446655440001",
                "status": "PENDING_APPROVAL",
                "source_system": "Apache Web Server",
                "description": "Ingest Apache access logs from production web servers",
                "cim_required": True,
                "approved_by": None,
                "approved_at": None,
                "rejection_reason": None,
                "completed_at": None,
                "metadata": {"environment": "production"},
                "created_at": "2025-01-17T10:00:00Z",
                "updated_at": "2025-01-17T10:05:00Z",
                "sample_count": 2,
                "total_sample_size": 1048576
            }
        }
    )


class RequestListResponse(BaseModel):
    """Schema for paginated request list response."""

    items: List[RequestResponse] = Field(..., description="List of requests")
    total: int = Field(..., description="Total number of requests")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 42,
                "skip": 0,
                "limit": 100
            }
        }
    )


# Sample Schemas
class SampleResponse(BaseModel):
    """Schema for sample response."""

    id: UUID = Field(..., description="Sample unique identifier")
    request_id: UUID = Field(..., description="Parent request ID")
    filename: str = Field(..., description="Original filename")
    file_size: int = Field(..., description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    storage_key: str = Field(..., description="Object storage key")
    storage_bucket: str = Field(..., description="Object storage bucket")
    checksum: str = Field(..., description="SHA-256 checksum")
    sample_preview: Optional[str] = Field(None, description="Preview of file content")
    retention_until: Optional[datetime] = Field(None, description="Retention expiration date")
    deleted_at: Optional[datetime] = Field(None, description="Soft deletion timestamp")
    created_at: datetime = Field(..., description="Upload timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440002",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "filename": "apache_access.log",
                "file_size": 524288,
                "mime_type": "text/plain",
                "storage_key": "samples/550e8400/apache_access.log",
                "storage_bucket": "log-samples",
                "checksum": "abc123...",
                "sample_preview": "127.0.0.1 - - [17/Jan/2025:10:00:00 +0000]...",
                "retention_until": "2025-04-17T10:00:00Z",
                "deleted_at": None,
                "created_at": "2025-01-17T10:00:00Z",
                "updated_at": "2025-01-17T10:00:00Z"
            }
        }
    )


class SampleListResponse(BaseModel):
    """Schema for sample list response."""

    items: List[SampleResponse] = Field(..., description="List of samples")
    total: int = Field(..., description="Total number of samples")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 2
            }
        }
    )


class UploadSampleResponse(BaseModel):
    """Schema for upload sample response."""

    sample: SampleResponse = Field(..., description="Uploaded sample details")
    upload_url: Optional[str] = Field(None, description="Presigned URL for download (optional)")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sample": {
                    "id": "550e8400-e29b-41d4-a716-446655440002",
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                    "filename": "apache_access.log",
                    "file_size": 524288,
                    "mime_type": "text/plain",
                    "storage_key": "samples/550e8400/apache_access.log",
                    "storage_bucket": "log-samples",
                    "checksum": "abc123...",
                    "sample_preview": "127.0.0.1 - - [17/Jan/2025:10:00:00 +0000]...",
                    "retention_until": "2025-04-17T10:00:00Z",
                    "deleted_at": None,
                    "created_at": "2025-01-17T10:00:00Z",
                    "updated_at": "2025-01-17T10:00:00Z"
                },
                "upload_url": None
            }
        }
    )


class RequestDetailResponse(RequestResponse):
    """Schema for detailed request response with related entities."""

    samples: List[SampleResponse] = Field(default_factory=list, description="Attached samples")
    ta_revisions: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="TA revisions (future implementation)"
    )
    validation_runs: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Validation runs (future implementation)"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "created_by": "550e8400-e29b-41d4-a716-446655440001",
                "status": "PENDING_APPROVAL",
                "source_system": "Apache Web Server",
                "description": "Ingest Apache access logs",
                "cim_required": True,
                "approved_by": None,
                "approved_at": None,
                "rejection_reason": None,
                "completed_at": None,
                "metadata": {},
                "created_at": "2025-01-17T10:00:00Z",
                "updated_at": "2025-01-17T10:00:00Z",
                "sample_count": 1,
                "total_sample_size": 524288,
                "samples": [],
                "ta_revisions": None,
                "validation_runs": None
            }
        }
    )