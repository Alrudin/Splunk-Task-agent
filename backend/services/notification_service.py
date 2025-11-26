"""
Notification service for sending email and webhook notifications.
Handles user preferences, template rendering, and audit logging.
"""
import json
import hashlib
import hmac
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

import aiosmtplib
import httpx
from jinja2 import Environment, FileSystemLoader, Template
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.repositories.user_repository import UserRepository
from backend.services.audit_service import AuditService
from backend.repositories.request_repository import RequestRepository
from backend.core.config import settings
from backend.models.enums import AuditAction
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for handling notifications via email and webhooks."""

    def __init__(
        self,
        user_repository: UserRepository,
        request_repository: RequestRepository,
        audit_service: AuditService,
        db: AsyncSession
    ):
        """
        Initialize NotificationService.

        Args:
            user_repository: Repository for user operations
            request_repository: Repository for request operations
            audit_service: Service for audit logging
            db: Database session
        """
        self.user_repository = user_repository
        self.request_repository = request_repository
        self.audit_service = audit_service
        self.db = db

        # Initialize Jinja2 template environment
        self.jinja_env = Environment(
            loader=FileSystemLoader("backend/templates"),
            autoescape=True
        )

    async def send_notification(
        self,
        user_id: str,
        event_type: str,
        subject: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Send notification to user based on preferences.

        Args:
            user_id: User ID to notify
            event_type: Type of event (COMPLETED, FAILED, APPROVED, REJECTED)
            subject: Email subject line
            context: Context data for template rendering

        Returns:
            True if notification sent successfully, False otherwise
        """
        try:
            # Check if notifications are globally enabled
            if not settings.notification_enabled:
                logger.info(f"Notifications globally disabled, skipping notification for user {user_id}")
                return False

            # Fetch user preferences
            user = await self.user_repository.get_by_id(user_id)
            if not user:
                logger.error(f"User {user_id} not found")
                return False

            # Check if user wants notifications for this event type
            if not self.should_notify(user, event_type):
                logger.info(f"User {user_id} has disabled notifications for event {event_type}")
                return False

            # Add user info to context
            context["user_name"] = user.full_name or user.username
            context["user_email"] = user.email
            context["frontend_url"] = settings.frontend_url

            # Ensure required template fields are set
            context.setdefault("subject", subject)
            context.setdefault("app_name", settings.app_name)
            context.setdefault("app_version", settings.app_version)

            success = False
            errors = []

            # Send email notification if enabled
            if user.email_notifications_enabled and settings.smtp_enabled:
                try:
                    # Render email templates
                    html_template_name = f"request_{event_type.lower()}.html"
                    text_template_name = f"request_{event_type.lower()}.txt"

                    html_body = self.render_template(html_template_name, context)
                    text_body = self.render_template(text_template_name, context)

                    # Send email
                    await self.send_email(user.email, subject, html_body, text_body)
                    logger.info(f"Email notification sent to user {user_id} for event {event_type}")
                    success = True
                except Exception as e:
                    logger.error(f"Failed to send email notification: {str(e)}")
                    errors.append(f"Email: {str(e)}")

            # Send webhook notification if configured
            if user.webhook_url:
                try:
                    # Prepare webhook payload
                    payload = {
                        "event_type": event_type,
                        "timestamp": datetime.utcnow().isoformat(),
                        "user_id": str(user_id),
                        "subject": subject,
                        **context
                    }

                    await self.send_webhook(user.webhook_url, payload)
                    logger.info(f"Webhook notification sent to user {user_id} for event {event_type}")
                    success = True
                except Exception as e:
                    logger.error(f"Failed to send webhook notification: {str(e)}")
                    errors.append(f"Webhook: {str(e)}")

            # Log audit event
            audit_action = AuditAction.NOTIFICATION_SENT if success else AuditAction.NOTIFICATION_FAILED
            audit_details = {
                "event_type": event_type,
                "user_id": str(user_id),
                "email_sent": user.email_notifications_enabled and settings.smtp_enabled and not any("Email" in e for e in errors),
                "webhook_sent": bool(user.webhook_url) and not any("Webhook" in e for e in errors),
                "errors": errors if errors else None
            }

            await self.audit_service.log_action(
                user_id=user_id,
                action=audit_action,
                entity_type="request",
                entity_id=context.get("request_id"),
                details=audit_details
            )

            return success

        except Exception as e:
            logger.error(f"Unexpected error in send_notification: {str(e)}")
            return False

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> None:
        """
        Send email via SMTP.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML email body
            text_body: Plain text email body
        """
        from email.message import EmailMessage
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText

        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{settings.notification_from_name} <{settings.smtp_from}>"
        msg["To"] = to_email

        # Add text and HTML parts
        text_part = MIMEText(text_body, "plain")
        html_part = MIMEText(html_body, "html")
        msg.attach(text_part)
        msg.attach(html_part)

        # Send email via SMTP
        smtp_client = aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            use_tls=settings.smtp_use_tls
        )

        async with smtp_client:
            # Authenticate if credentials provided
            if settings.smtp_user and settings.smtp_password:
                await smtp_client.login(settings.smtp_user, settings.smtp_password)

            await smtp_client.send_message(msg)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10)
    )
    async def send_webhook(
        self,
        webhook_url: str,
        payload: Dict[str, Any]
    ) -> None:
        """
        Send webhook notification with retries.

        Args:
            webhook_url: Webhook endpoint URL
            payload: JSON payload to send
        """
        # Generate HMAC signature for webhook security
        payload_json = json.dumps(payload, sort_keys=True)
        signature = self._generate_webhook_signature(payload_json)

        headers = {
            "Content-Type": "application/json",
            "X-Signature": signature,
            "X-Event-Type": payload["event_type"],
            "User-Agent": f"{settings.app_name}/{settings.app_version}"
        }

        async with httpx.AsyncClient(timeout=settings.webhook_timeout) as client:
            response = await client.post(
                webhook_url,
                json=payload,
                headers=headers
            )
            response.raise_for_status()

    def render_template(self, template_name: str, context: Dict[str, Any]) -> str:
        """
        Render Jinja2 template with context.

        Args:
            template_name: Name of template file
            context: Context data for template

        Returns:
            Rendered template string
        """
        try:
            template = self.jinja_env.get_template(template_name)
            return template.render(**context)
        except Exception as e:
            logger.error(f"Failed to render template {template_name}: {str(e)}")
            # Fallback to simple text if template fails
            return f"Notification for {context.get('user_name', 'user')}: {context.get('event_type', 'event')} - {context.get('request_id', 'request')}"

    async def get_user_preferences(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch user notification preferences.

        Args:
            user_id: User ID

        Returns:
            Dictionary of user preferences or None
        """
        user = await self.user_repository.get_by_id(user_id)
        if not user:
            return None

        return {
            "email_notifications_enabled": user.email_notifications_enabled,
            "webhook_url": user.webhook_url,
            "notification_events": user.notification_events or ["COMPLETED", "FAILED", "APPROVED", "REJECTED"]
        }

    def should_notify(self, user, event_type: str) -> bool:
        """
        Check if user wants notifications for this event type.

        Args:
            user: User model instance
            event_type: Event type to check

        Returns:
            True if user should be notified
        """
        # If user has disabled email notifications and no webhook, don't notify
        if not user.email_notifications_enabled and not user.webhook_url:
            return False

        # If no specific events configured, notify for all
        if not user.notification_events:
            return True

        # Check if event type is in user's selected events
        return event_type in user.notification_events

    def _generate_webhook_signature(self, payload: str) -> str:
        """
        Generate HMAC-SHA256 signature for webhook payload.

        Args:
            payload: JSON string payload

        Returns:
            Hex-encoded signature
        """
        # Use JWT secret as signing key (in production, use a separate webhook secret)
        key = settings.jwt_secret_key.encode('utf-8')
        message = payload.encode('utf-8')
        signature = hmac.new(key, message, hashlib.sha256).hexdigest()
        return f"sha256={signature}"