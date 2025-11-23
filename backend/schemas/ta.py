"""
Pydantic schemas for TA revision and validation operations.

These schemas define the structure for request/response data validation,
serialization, and documentation in the FastAPI application.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from backend.models.enums import TARevisionType, ValidationStatus


# Validation Run Schemas
class ValidationRunResponse(BaseModel):
    """Schema for validation run response."""

    id: UUID = Field(..., description="Validation run unique identifier")
    request_id: UUID = Field(..., description="Parent request ID")
    ta_revision_id: UUID = Field(..., description="TA revision being validated")
    status: ValidationStatus = Field(..., description="Validation status")
    results_json: Optional[Dict[str, Any]] = Field(
        None,
        description="""Validation results as JSON. Expected shape (all fields optional except overall_status):
        {
            "overall_status": "PASSED" | "FAILED",  # Required
            "field_coverage": number,               # Percentage (0-100)
            "events_ingested": number,              # Count of indexed events
            "cim_compliance": boolean,              # CIM compliance status
            "extracted_fields": string[],           # Fields found in data
            "expected_fields": string[],            # Fields expected by TA
            "errors": string[]                      # Error messages if any
        }
        Note: Backend uses snake_case keys which are transformed to camelCase on frontend."""
    )
    debug_bundle_key: Optional[str] = Field(
        None, description="Object storage key for debug bundle"
    )
    debug_bundle_bucket: Optional[str] = Field(
        None, description="Object storage bucket for debug bundle"
    )
    error_message: Optional[str] = Field(
        None, description="Error message if validation failed"
    )
    started_at: Optional[datetime] = Field(
        None, description="Validation start timestamp"
    )
    completed_at: Optional[datetime] = Field(
        None, description="Validation completion timestamp"
    )
    duration_seconds: Optional[int] = Field(
        None, description="Validation duration in seconds"
    )
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440010",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "ta_revision_id": "550e8400-e29b-41d4-a716-446655440005",
                "status": "PASSED",
                "results_json": {
                    "overall_status": "PASSED",
                    "field_coverage": 85.5,
                    "events_ingested": 1250,
                    "cim_compliance": True
                },
                "debug_bundle_key": None,
                "debug_bundle_bucket": None,
                "error_message": None,
                "started_at": "2025-01-17T10:05:00Z",
                "completed_at": "2025-01-17T10:08:30Z",
                "duration_seconds": 210,
                "created_at": "2025-01-17T10:00:00Z"
            }
        }
    )


# TA Revision Schemas
class TARevisionResponse(BaseModel):
    """Schema for TA revision response."""

    id: UUID = Field(..., description="TA revision unique identifier")
    request_id: UUID = Field(..., description="Parent request ID")
    version: int = Field(..., description="Version number (1, 2, 3, ...)")
    storage_key: str = Field(..., description="Object storage key for TA package")
    storage_bucket: str = Field(..., description="Object storage bucket")
    generated_by: TARevisionType = Field(
        ..., description="How revision was generated (AUTO or MANUAL)"
    )
    generated_by_user: Optional[UUID] = Field(
        None, description="User ID for manual overrides"
    )
    file_size: Optional[int] = Field(None, description="TA package size in bytes")
    checksum: Optional[str] = Field(None, description="SHA-256 checksum")
    config_summary: Optional[Dict[str, Any]] = Field(
        None, description="Summary of config files in TA"
    )
    generation_metadata: Optional[Dict[str, Any]] = Field(
        None, description="Generation metadata (model, parameters, etc.)"
    )
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    latest_validation_status: Optional[ValidationStatus] = Field(
        None, description="Status of most recent validation run"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440005",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "version": 1,
                "storage_key": "tas/550e8400/v1/ta-apache-v1.tgz",
                "storage_bucket": "ta-artifacts",
                "generated_by": "AUTO",
                "generated_by_user": None,
                "file_size": 52428,
                "checksum": "sha256:abc123...",
                "config_summary": {
                    "inputs_conf": True,
                    "props_conf": True,
                    "transforms_conf": True
                },
                "generation_metadata": {
                    "model": "llama2",
                    "duration_seconds": 45
                },
                "created_at": "2025-01-17T10:00:00Z",
                "updated_at": "2025-01-17T10:00:00Z",
                "latest_validation_status": "PASSED"
            }
        }
    )


class TARevisionDetailResponse(TARevisionResponse):
    """Schema for detailed TA revision response with validation runs."""

    validation_runs: List[ValidationRunResponse] = Field(
        default_factory=list, description="Validation runs for this revision"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440005",
                "request_id": "550e8400-e29b-41d4-a716-446655440000",
                "version": 1,
                "storage_key": "tas/550e8400/v1/ta-apache-v1.tgz",
                "storage_bucket": "ta-artifacts",
                "generated_by": "AUTO",
                "generated_by_user": None,
                "file_size": 52428,
                "checksum": "sha256:abc123...",
                "config_summary": {},
                "generation_metadata": {},
                "created_at": "2025-01-17T10:00:00Z",
                "updated_at": "2025-01-17T10:00:00Z",
                "latest_validation_status": "PASSED",
                "validation_runs": []
            }
        }
    )


class TARevisionListResponse(BaseModel):
    """Schema for paginated TA revision list response."""

    items: List[TARevisionResponse] = Field(..., description="List of TA revisions")
    total: int = Field(..., description="Total number of revisions")
    skip: int = Field(..., description="Number of items skipped")
    limit: int = Field(..., description="Maximum number of items returned")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 3,
                "skip": 0,
                "limit": 100
            }
        }
    )


class UploadTAOverrideResponse(BaseModel):
    """Schema for manual TA override upload response."""

    revision: TARevisionResponse = Field(
        ..., description="Created TA revision from manual override"
    )
    validation_run: ValidationRunResponse = Field(
        ..., description="Queued validation run for the new revision"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "revision": {
                    "id": "550e8400-e29b-41d4-a716-446655440006",
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                    "version": 2,
                    "storage_key": "tas/550e8400/v2/ta-apache-v2.tgz",
                    "storage_bucket": "ta-artifacts",
                    "generated_by": "MANUAL",
                    "generated_by_user": "550e8400-e29b-41d4-a716-446655440001",
                    "file_size": 54321,
                    "checksum": "sha256:def456...",
                    "config_summary": None,
                    "generation_metadata": None,
                    "created_at": "2025-01-17T12:00:00Z",
                    "updated_at": "2025-01-17T12:00:00Z",
                    "latest_validation_status": "QUEUED"
                },
                "validation_run": {
                    "id": "550e8400-e29b-41d4-a716-446655440011",
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                    "ta_revision_id": "550e8400-e29b-41d4-a716-446655440006",
                    "status": "QUEUED",
                    "results_json": None,
                    "debug_bundle_key": None,
                    "debug_bundle_bucket": None,
                    "error_message": None,
                    "started_at": None,
                    "completed_at": None,
                    "duration_seconds": None,
                    "created_at": "2025-01-17T12:00:00Z"
                }
            }
        }
    )


class RevalidateResponse(BaseModel):
    """Schema for re-validation trigger response."""

    validation_run: ValidationRunResponse = Field(
        ..., description="Queued validation run"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "validation_run": {
                    "id": "550e8400-e29b-41d4-a716-446655440012",
                    "request_id": "550e8400-e29b-41d4-a716-446655440000",
                    "ta_revision_id": "550e8400-e29b-41d4-a716-446655440005",
                    "status": "QUEUED",
                    "results_json": None,
                    "debug_bundle_key": None,
                    "debug_bundle_bucket": None,
                    "error_message": None,
                    "started_at": None,
                    "completed_at": None,
                    "duration_seconds": None,
                    "created_at": "2025-01-17T14:00:00Z"
                }
            }
        }
    )
