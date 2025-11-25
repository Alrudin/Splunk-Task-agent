"""
API endpoints for user-related operations, including notification preferences.
"""
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import (
    get_db,
    get_current_active_user,
    get_audit_service,
)
from backend.models.user import User
from backend.models.enums import AuditAction
from backend.repositories.user_repository import UserRepository
from backend.schemas.user import (
    NotificationPreferencesResponse,
    UpdateNotificationPreferencesRequest,
)
from backend.services.audit_service import AuditService

router = APIRouter(prefix="/users", tags=["Users"])


@router.get(
    "/me/notification-preferences",
    response_model=NotificationPreferencesResponse,
    summary="Get current user's notification preferences",
    description="Retrieve the notification preferences for the authenticated user",
)
async def get_notification_preferences(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> NotificationPreferencesResponse:
    """Get current user's notification preferences."""
    user_repository = UserRepository(db)
    user = await user_repository.get_by_id(current_user.id)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return NotificationPreferencesResponse(
        email_notifications_enabled=user.email_notifications_enabled,
        webhook_url=user.webhook_url,
        notification_events=user.notification_events,
    )


@router.put(
    "/me/notification-preferences",
    response_model=NotificationPreferencesResponse,
    summary="Update current user's notification preferences",
    description="Update notification preferences for the authenticated user",
)
async def update_notification_preferences(
    preferences: UpdateNotificationPreferencesRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    audit_service: AuditService = Depends(get_audit_service),
) -> NotificationPreferencesResponse:
    """Update current user's notification preferences."""
    user_repository = UserRepository(db)

    # Get current user from database
    user = await user_repository.get_by_id(current_user.id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Store old values for audit
    old_values = {
        "email_notifications_enabled": user.email_notifications_enabled,
        "webhook_url": user.webhook_url,
        "notification_events": user.notification_events,
    }

    # Update only provided fields
    update_data = preferences.model_dump(exclude_unset=True)
    new_values = {}

    if "email_notifications_enabled" in update_data:
        user.email_notifications_enabled = update_data["email_notifications_enabled"]
        new_values["email_notifications_enabled"] = update_data["email_notifications_enabled"]

    if "webhook_url" in update_data:
        # Allow empty string to clear webhook
        user.webhook_url = update_data["webhook_url"] if update_data["webhook_url"] else None
        new_values["webhook_url"] = user.webhook_url

    if "notification_events" in update_data:
        user.notification_events = update_data["notification_events"]
        new_values["notification_events"] = update_data["notification_events"]

    # Save changes
    await db.commit()
    await db.refresh(user)

    # Log audit event for preference changes
    await audit_service.log_action(
        action=AuditAction.CONFIG_UPDATE,
        user_id=current_user.id,
        resource_id=str(current_user.id),
        resource_type="user_preferences",
        details={
            "old_values": old_values,
            "new_values": new_values,
            "changed_fields": list(update_data.keys()),
        },
    )

    return NotificationPreferencesResponse(
        email_notifications_enabled=user.email_notifications_enabled,
        webhook_url=user.webhook_url,
        notification_events=user.notification_events,
    )


@router.post(
    "/me/test-notification",
    summary="Send a test notification",
    description="Send a test notification to verify settings are working correctly",
    response_model=dict,
)
async def test_notification(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Send a test notification to the current user.

    This endpoint is useful for users to verify their notification settings
    are working correctly (email and/or webhook).
    """
    from backend.tasks.send_notification_task import send_notification_task
    from datetime import datetime

    # Enqueue test notification task
    try:
        task = send_notification_task.apply_async(
            args=[
                str(current_user.id),
                "TEST",
                f"test_{datetime.utcnow().isoformat()}",
                {
                    "message": "This is a test notification from Splunk TA Generator",
                    "timestamp": datetime.utcnow().isoformat(),
                },
            ],
            queue="default",
        )

        return {
            "message": "Test notification has been queued for delivery",
            "task_id": task.id,
            "details": {
                "email_enabled": current_user.email_notifications_enabled,
                "has_webhook": bool(current_user.webhook_url),
            },
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send test notification: {str(e)}",
        )