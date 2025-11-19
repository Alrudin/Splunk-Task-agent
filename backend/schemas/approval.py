"""
Pydantic schemas for approval API request/response validation.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict, field_validator

from backend.schemas.request import RequestResponse


class ApproveRequestRequest(BaseModel):
    """Request body for approving a request."""

    comment: Optional[str] = Field(
        None,
        max_length=1000,
        description="Optional approval comment",
    )

    @field_validator("comment")
    @classmethod
    def strip_comment(cls, v: Optional[str]) -> Optional[str]:
        """Strip whitespace from comment."""
        if v is not None:
            return v.strip() if v.strip() else None
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "comment": "Request looks good, proceeding with TA generation",
            }
        }
    )


class RejectRequestRequest(BaseModel):
    """Request body for rejecting a request."""

    reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Required rejection reason (minimum 10 characters)",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate rejection reason is not just whitespace."""
        stripped = v.strip()
        if not stripped:
            raise ValueError("Rejection reason cannot be empty or whitespace")
        if len(stripped) < 10:
            raise ValueError("Rejection reason must be at least 10 characters")
        return stripped

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "Log samples do not contain sufficient fields for CIM mapping. Please upload more comprehensive samples.",
            }
        }
    )


class ApprovalResponse(RequestResponse):
    """Response for approve/reject actions.

    Extends RequestResponse with approver information.
    """

    approver_username: Optional[str] = Field(
        None,
        description="Username of approver (if approved/rejected)",
    )
    approver_full_name: Optional[str] = Field(
        None,
        description="Full name of approver (if approved/rejected)",
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "550e8400-e29b-41d4-a716-446655440000",
                "source_system": "Palo Alto Networks",
                "description": "Firewall logs from production environment",
                "cim_required": True,
                "status": "APPROVED",
                "submitted_by": "550e8400-e29b-41d4-a716-446655440001",
                "submitted_at": "2025-01-15T10:30:00Z",
                "approved_by": "550e8400-e29b-41d4-a716-446655440002",
                "approved_at": "2025-01-15T11:00:00Z",
                "rejection_reason": None,
                "approver_username": "john.doe",
                "approver_full_name": "John Doe",
                "created_at": "2025-01-15T10:00:00Z",
                "updated_at": "2025-01-15T11:00:00Z",
            }
        },
    )


class PendingApprovalListResponse(BaseModel):
    """Paginated list of pending approvals."""

    items: List[RequestResponse] = Field(
        ...,
        description="List of requests with status=PENDING_APPROVAL",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total count of pending approvals",
    )
    skip: int = Field(
        ...,
        ge=0,
        description="Pagination offset",
    )
    limit: int = Field(
        ...,
        ge=1,
        description="Page size",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "source_system": "Palo Alto Networks",
                        "description": "Firewall logs",
                        "cim_required": True,
                        "status": "PENDING_APPROVAL",
                        "submitted_by": "550e8400-e29b-41d4-a716-446655440001",
                        "submitted_at": "2025-01-15T10:30:00Z",
                        "sample_count": 3,
                        "total_sample_size": 1048576,
                    }
                ],
                "total": 15,
                "skip": 0,
                "limit": 100,
            }
        }
    )


class ApprovalStatisticsResponse(BaseModel):
    """Dashboard statistics for approval counts."""

    pending_approval: int = Field(
        ...,
        ge=0,
        description="Count of PENDING_APPROVAL requests",
    )
    approved: int = Field(
        ...,
        ge=0,
        description="Count of APPROVED requests",
    )
    rejected: int = Field(
        ...,
        ge=0,
        description="Count of REJECTED requests",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total requests",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pending_approval": 15,
                "approved": 42,
                "rejected": 8,
                "total": 65,
            }
        }
    )
