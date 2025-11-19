"""
Pydantic schemas for audit log API requests and responses.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditLogResponse(BaseModel):
    """Response schema for audit log data."""

    id: UUID = Field(..., description="Audit log ID")
    user_id: Optional[UUID] = Field(None, description="ID of user who performed the action (None for system actions)")
    action: str = Field(..., description="Action type (e.g., APPROVE, REJECT, LOGIN)")
    entity_type: str = Field(..., description="Type of entity acted upon (e.g., Request, TARevision)")
    entity_id: Optional[UUID] = Field(None, description="ID of specific entity")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional action context as JSON")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="User agent string")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing related actions")
    timestamp: datetime = Field(..., description="Timestamp of action")

    # Optional nested user information
    user: Optional[Dict[str, Any]] = Field(None, description="User information if available")

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "789e0123-e89b-12d3-a456-426614174999",
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "action": "APPROVE",
                "entity_type": "Request",
                "entity_id": "456e7890-e89b-12d3-a456-426614174111",
                "details": {"comment": "Approved after review", "priority": "high"},
                "ip_address": "192.168.1.100",
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "correlation_id": "999e8888-e89b-12d3-a456-426614174222",
                "timestamp": "2025-01-15T14:30:00Z",
                "user": {
                    "username": "johndoe",
                    "email": "john.doe@example.com"
                }
            }
        }
    )


class AuditLogListResponse(BaseModel):
    """Response schema for paginated audit log list."""

    items: List[AuditLogResponse] = Field(..., description="List of audit log entries")
    total: int = Field(..., description="Total number of matching audit logs")
    skip: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Maximum number of records returned")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [
                    {
                        "id": "789e0123-e89b-12d3-a456-426614174999",
                        "user_id": "123e4567-e89b-12d3-a456-426614174000",
                        "action": "APPROVE",
                        "entity_type": "Request",
                        "entity_id": "456e7890-e89b-12d3-a456-426614174111",
                        "details": {"comment": "Approved after review"},
                        "ip_address": "192.168.1.100",
                        "user_agent": "Mozilla/5.0",
                        "correlation_id": "999e8888-e89b-12d3-a456-426614174222",
                        "timestamp": "2025-01-15T14:30:00Z"
                    }
                ],
                "total": 150,
                "skip": 0,
                "limit": 100
            }
        }
    )


class AuditLogQueryParams(BaseModel):
    """Query parameters for filtering audit logs."""

    user_id: Optional[UUID] = Field(None, description="Filter by user ID")
    action: Optional[str] = Field(None, description="Filter by action type (e.g., APPROVE, LOGIN)")
    entity_type: Optional[str] = Field(None, description="Filter by entity type (e.g., Request, TARevision)")
    entity_id: Optional[UUID] = Field(None, description="Filter by specific entity ID")
    start_date: Optional[datetime] = Field(None, description="Filter logs after this date (inclusive)")
    end_date: Optional[datetime] = Field(None, description="Filter logs before this date (inclusive)")
    correlation_id: Optional[str] = Field(None, description="Filter by correlation ID")
    skip: int = Field(0, ge=0, description="Number of records to skip for pagination")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of records to return")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "user_id": "123e4567-e89b-12d3-a456-426614174000",
                "action": "APPROVE",
                "entity_type": "Request",
                "start_date": "2025-01-01T00:00:00Z",
                "end_date": "2025-01-31T23:59:59Z",
                "skip": 0,
                "limit": 100
            }
        }
    )
