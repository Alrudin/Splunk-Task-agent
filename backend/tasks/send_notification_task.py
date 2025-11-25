"""
Celery task for asynchronous notification sending.
Handles email and webhook notifications with retry logic.
"""
import asyncio
from typing import Dict, Any, Optional
import logging

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from backend.tasks.celery_app import celery_app
from backend.services.notification_service import NotificationService
from backend.services.audit_service import AuditService
from backend.repositories.user_repository import UserRepository
from backend.repositories.request_repository import RequestRepository
from backend.repositories.audit_log_repository import AuditLogRepository
from backend.core.config import settings
from backend.models.enums import AuditAction

logger = logging.getLogger(__name__)


class SendNotificationTask(Task):
    """Custom task class for notification sending with database session management."""

    def __init__(self):
        super().__init__()
        self.engine = None
        self.async_session_maker = None

    def initialize_db(self):
        """Initialize database connection if not already done."""
        if not self.engine:
            self.engine = create_async_engine(
                settings.database_url,
                echo=settings.database_echo,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True
            )
            self.async_session_maker = sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )

    async def get_session(self) -> AsyncSession:
        """Get a new database session."""
        self.initialize_db()
        return self.async_session_maker()


@celery_app.task(
    name="send_notification",
    bind=True,
    base=SendNotificationTask,
    max_retries=3,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    time_limit=60,  # Hard limit of 60 seconds
    soft_time_limit=50  # Soft limit of 50 seconds
)
def send_notification_task(
    self,
    user_id: str,
    event_type: str,
    request_id: str,
    context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Send notification to user asynchronously.

    Args:
        self: Celery task instance
        user_id: ID of user to notify
        event_type: Type of event (COMPLETED, FAILED, APPROVED, REJECTED)
        request_id: ID of the request
        context: Additional context data for the notification

    Returns:
        Dictionary with notification status and details
    """
    try:
        # Run async function in sync context
        return asyncio.run(
            _send_notification_async(
                self,
                user_id,
                event_type,
                request_id,
                context or {}
            )
        )
    except SoftTimeLimitExceeded:
        logger.error(f"Notification task timed out for user {user_id}, event {event_type}")
        return {
            "success": False,
            "error": "Task timed out",
            "user_id": user_id,
            "event_type": event_type
        }
    except Exception as e:
        logger.error(f"Failed to send notification for user {user_id}: {str(e)}")

        # Check if we should retry
        if self.request.retries < self.max_retries:
            logger.info(f"Retrying notification task (attempt {self.request.retries + 1}/{self.max_retries})")
            raise self.retry(exc=e)

        return {
            "success": False,
            "error": str(e),
            "user_id": user_id,
            "event_type": event_type
        }


async def _send_notification_async(
    task_instance: SendNotificationTask,
    user_id: str,
    event_type: str,
    request_id: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Async implementation of notification sending.

    Args:
        task_instance: Celery task instance with database session
        user_id: ID of user to notify
        event_type: Type of event
        request_id: ID of the request
        context: Additional context data

    Returns:
        Dictionary with notification status
    """
    async with await task_instance.get_session() as db:
        try:
            # Check if notifications are globally enabled
            if not settings.notification_enabled:
                logger.info(f"Notifications globally disabled, skipping for user {user_id}")
                return {
                    "success": True,
                    "skipped": True,
                    "reason": "Notifications globally disabled"
                }

            # Initialize repositories and services
            user_repo = UserRepository(db)
            request_repo = RequestRepository(db)
            audit_repo = AuditLogRepository(db)
            audit_service = AuditService(audit_repo)

            # Fetch user and request details
            user = await user_repo.get_by_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return {
                    "success": False,
                    "error": "User not found",
                    "user_id": user_id
                }

            request = await request_repo.get_by_id(request_id)
            if not request:
                logger.error(f"Request {request_id} not found")
                return {
                    "success": False,
                    "error": "Request not found",
                    "request_id": request_id
                }

            # Build notification context
            notification_context = {
                "request_id": request_id,
                "source_system": request.source_system,
                "submission_date": request.created_at.isoformat() if request.created_at else None,
                "app_name": settings.app_name,
                "app_version": settings.app_version,
                **context
            }

            # Add event-specific context
            if event_type == "COMPLETED":
                notification_context["completion_date"] = request.updated_at.isoformat() if request.updated_at else None
                if "ta_download_url" not in notification_context:
                    notification_context["ta_download_url"] = f"{settings.frontend_url}/requests/{request_id}/ta"
            elif event_type == "FAILED":
                notification_context["failure_date"] = request.updated_at.isoformat() if request.updated_at else None
                if "debug_bundle_url" not in notification_context:
                    notification_context["debug_bundle_url"] = f"{settings.frontend_url}/requests/{request_id}/debug-bundle"
            elif event_type == "APPROVED":
                notification_context["approval_date"] = request.approved_at.isoformat() if request.approved_at else None
            elif event_type == "REJECTED":
                notification_context["rejection_date"] = request.rejected_at.isoformat() if request.rejected_at else None

            # Initialize notification service
            notification_service = NotificationService(
                user_repository=user_repo,
                request_repository=request_repo,
                audit_service=audit_service,
                db=db
            )

            # Determine subject line based on event type
            subject_map = {
                "COMPLETED": f"TA Generation Completed - {request.source_system}",
                "FAILED": f"TA Generation Failed - {request.source_system}",
                "APPROVED": f"Request Approved - {request.source_system}",
                "REJECTED": f"Request Rejected - {request.source_system}"
            }
            subject = subject_map.get(event_type, f"Request Update - {request.source_system}")

            # Send notification
            success = await notification_service.send_notification(
                user_id=user_id,
                event_type=event_type,
                subject=subject,
                context=notification_context
            )

            # Log result
            if success:
                logger.info(f"Notification sent successfully for user {user_id}, event {event_type}")
            else:
                logger.warning(f"Notification failed for user {user_id}, event {event_type}")

            return {
                "success": success,
                "user_id": user_id,
                "event_type": event_type,
                "request_id": request_id,
                "subject": subject
            }

        except Exception as e:
            logger.error(f"Error in notification task: {str(e)}")

            # Log failure to audit log
            try:
                audit_repo = AuditLogRepository(db)
                audit_service = AuditService(audit_repo)
                await audit_service.log_action(
                    action=AuditAction.NOTIFICATION_FAILED,
                    user_id=user_id,
                    resource_id=request_id,
                    resource_type="request",
                    details={
                        "event_type": event_type,
                        "error": str(e)
                    }
                )
                await db.commit()
            except Exception as audit_error:
                logger.error(f"Failed to log notification failure: {str(audit_error)}")

            raise