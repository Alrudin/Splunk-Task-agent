"""
Pydantic schemas for user notification preferences.
"""
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict, HttpUrl


class NotificationPreferencesResponse(BaseModel):
    """Response schema for user notification preferences."""

    email_notifications_enabled: bool = Field(
        ...,
        description="Whether email notifications are enabled"
    )
    webhook_url: Optional[str] = Field(
        None,
        description="Webhook URL for external integrations"
    )
    notification_events: Optional[List[str]] = Field(
        None,
        description="List of event types user wants notifications for"
    )

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "email_notifications_enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX",
                "notification_events": ["COMPLETED", "FAILED", "APPROVED", "REJECTED"]
            }
        }
    )


class UpdateNotificationPreferencesRequest(BaseModel):
    """Request schema for updating notification preferences."""

    email_notifications_enabled: Optional[bool] = Field(
        None,
        description="Whether to enable email notifications"
    )
    webhook_url: Optional[str] = Field(
        None,
        max_length=2048,
        description="Webhook URL for external integrations (e.g., Slack, Teams)"
    )
    notification_events: Optional[List[str]] = Field(
        None,
        description="List of event types to receive notifications for"
    )

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: Optional[str]) -> Optional[str]:
        """Validate webhook URL format."""
        if v is None or v == "":
            return None

        # Basic URL validation
        if not v.startswith(("http://", "https://")):
            raise ValueError("Webhook URL must start with http:// or https://")

        # Check for common invalid patterns
        if " " in v or "\n" in v or "\t" in v:
            raise ValueError("Webhook URL cannot contain whitespace")

        if len(v) > 2048:
            raise ValueError("Webhook URL cannot exceed 2048 characters")

        return v

    @field_validator("notification_events")
    @classmethod
    def validate_notification_events(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        """Validate notification event types."""
        if v is None:
            return None

        allowed_events = {"COMPLETED", "FAILED", "APPROVED", "REJECTED"}
        invalid_events = set(v) - allowed_events

        if invalid_events:
            raise ValueError(
                f"Invalid event types: {', '.join(invalid_events)}. "
                f"Allowed events: {', '.join(sorted(allowed_events))}"
            )

        # Remove duplicates while preserving order
        seen = set()
        unique_events = []
        for event in v:
            if event not in seen:
                seen.add(event)
                unique_events.append(event)

        return unique_events

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email_notifications_enabled": True,
                "webhook_url": "https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX",
                "notification_events": ["COMPLETED", "FAILED"]
            }
        }
    )