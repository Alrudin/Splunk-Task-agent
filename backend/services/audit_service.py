"""
Centralized AuditService for standardized audit logging across the application.

This service wraps the AuditLogRepository and provides high-level methods
for logging different types of actions with automatic request context extraction.
"""

from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import Request

from backend.core.audit_utils import get_client_ip, get_correlation_id, get_user_agent
from backend.core.logging import get_logger
from backend.models.audit_log import AuditLog
from backend.models.enums import AuditAction
from backend.repositories.audit_log_repository import AuditLogRepository

logger = get_logger(__name__)


class AuditService:
    """
    Service for centralized audit logging with automatic context extraction.

    Wraps AuditLogRepository and provides convenience methods for common
    audit actions while automatically extracting IP address, user agent,
    and correlation ID from FastAPI Request objects.
    """

    def __init__(self, repository: AuditLogRepository):
        """
        Initialize AuditService with repository dependency.

        Args:
            repository: AuditLogRepository instance for database operations
        """
        self.repository = repository

    async def log_action(
        self,
        user_id: Optional[UUID],
        action: AuditAction,
        entity_type: str,
        entity_id: Optional[UUID] = None,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log an audit action with automatic context extraction from request.

        Args:
            user_id: ID of the user performing the action (None for system actions)
            action: AuditAction enum value
            entity_type: Type of entity being acted upon (e.g., "Request", "TARevision")
            entity_id: ID of the specific entity (optional)
            details: Additional context as dictionary (optional)
            request: FastAPI Request object for automatic context extraction (optional)

        Returns:
            Created AuditLog object

        Example:
            audit_log = await audit_service.log_action(
                user_id=current_user.id,
                action=AuditAction.APPROVE,
                entity_type="Request",
                entity_id=request_id,
                details={"comment": "Approved after review"},
                request=request
            )
        """
        # Extract context from request if provided
        ip_address = get_client_ip(request) if request else None
        user_agent = get_user_agent(request) if request else None
        correlation_id = get_correlation_id(request) if request else None

        # Create audit log in database
        audit_log = await self.repository.create_log(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )

        # Emit structured log for observability
        logger.info(
            f"audit_action_{action.value.lower()}",
            user_id=str(user_id) if user_id else None,
            action=action.value,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id else None,
            ip_address=ip_address,
            correlation_id=correlation_id,  # Already a string from request
            audit_log_id=str(audit_log.id),
        )

        return audit_log

    async def log_approval(
        self,
        user_id: UUID,
        request_id: UUID,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log a request approval action.

        Args:
            user_id: ID of the approving user
            request_id: ID of the request being approved
            details: Additional approval details (e.g., comments)
            request: FastAPI Request object for context

        Returns:
            Created AuditLog object
        """
        return await self.log_action(
            user_id=user_id,
            action=AuditAction.APPROVE,
            entity_type="Request",
            entity_id=request_id,
            details=details,
            request=request,
        )

    async def log_rejection(
        self,
        user_id: UUID,
        request_id: UUID,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log a request rejection action.

        Args:
            user_id: ID of the rejecting user
            request_id: ID of the request being rejected
            details: Rejection reason and additional details
            request: FastAPI Request object for context

        Returns:
            Created AuditLog object
        """
        return await self.log_action(
            user_id=user_id,
            action=AuditAction.REJECT,
            entity_type="Request",
            entity_id=request_id,
            details=details,
            request=request,
        )

    async def log_download(
        self,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log a download action (TA, debug bundle, etc.).

        Args:
            user_id: ID of the user downloading
            entity_type: Type of entity ("TARevision", "DebugBundle", etc.)
            entity_id: ID of the entity being downloaded
            details: Additional download details (e.g., file name, size)
            request: FastAPI Request object for context

        Returns:
            Created AuditLog object
        """
        # Determine specific download action type
        action = AuditAction.TA_DOWNLOAD if entity_type == "TARevision" else AuditAction.DOWNLOAD

        if entity_type == "DebugBundle":
            action = AuditAction.DEBUG_BUNDLE_DOWNLOAD

        return await self.log_action(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            request=request,
        )

    async def log_upload(
        self,
        user_id: UUID,
        entity_type: str,
        entity_id: UUID,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log an upload action (log sample, knowledge document, etc.).

        Args:
            user_id: ID of the user uploading
            entity_type: Type of entity ("LogSample", "KnowledgeDocument", etc.)
            entity_id: ID of the entity being uploaded
            details: Additional upload details (e.g., file name, size)
            request: FastAPI Request object for context

        Returns:
            Created AuditLog object
        """
        # Determine specific upload action type
        action = AuditAction.SAMPLE_UPLOAD if entity_type == "LogSample" else AuditAction.UPLOAD

        if entity_type == "KnowledgeDocument":
            action = AuditAction.KNOWLEDGE_UPLOAD

        return await self.log_action(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            request=request,
        )

    async def log_ta_generation_start(
        self,
        request_id: UUID,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log the start of TA generation (system action).

        Args:
            request_id: ID of the request for which TA is being generated
            details: Additional generation details (e.g., model, parameters)

        Returns:
            Created AuditLog object
        """
        return await self.log_action(
            user_id=None,  # System action
            action=AuditAction.TA_GENERATION_START,
            entity_type="Request",
            entity_id=request_id,
            details=details,
        )

    async def log_ta_generation_complete(
        self,
        request_id: UUID,
        ta_revision_id: UUID,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log successful completion of TA generation (system action).

        Args:
            request_id: ID of the request
            ta_revision_id: ID of the generated TARevision
            details: Additional completion details (e.g., duration, files created)

        Returns:
            Created AuditLog object
        """
        if details is None:
            details = {}
        details["ta_revision_id"] = str(ta_revision_id)

        return await self.log_action(
            user_id=None,  # System action
            action=AuditAction.TA_GENERATION_COMPLETE,
            entity_type="Request",
            entity_id=request_id,
            details=details,
        )

    async def log_ta_generation_failed(
        self,
        request_id: UUID,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log TA generation failure (system action).

        Args:
            request_id: ID of the request
            details: Error details and failure reason

        Returns:
            Created AuditLog object
        """
        return await self.log_action(
            user_id=None,  # System action
            action=AuditAction.TA_GENERATION_FAILED,
            entity_type="Request",
            entity_id=request_id,
            details=details,
        )

    async def log_manual_override(
        self,
        user_id: UUID,
        request_id: UUID,
        ta_revision_id: UUID,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log a manual TA override upload by an engineer.

        Args:
            user_id: ID of the engineer performing the override
            request_id: ID of the associated request
            ta_revision_id: ID of the new TARevision from manual override
            details: Override details (e.g., reason, changes made)
            request: FastAPI Request object for context

        Returns:
            Created AuditLog object
        """
        if details is None:
            details = {}
        details["ta_revision_id"] = str(ta_revision_id)
        details["request_id"] = str(request_id)

        return await self.log_action(
            user_id=user_id,
            action=AuditAction.MANUAL_OVERRIDE,
            entity_type="TARevision",
            entity_id=ta_revision_id,
            details=details,
            request=request,
        )

    async def log_revalidation_trigger(
        self,
        user_id: UUID,
        request_id: UUID,
        ta_revision_id: UUID,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log triggering of re-validation by a user.

        Args:
            user_id: ID of the user triggering re-validation
            request_id: ID of the associated request
            ta_revision_id: ID of the TARevision being re-validated
            details: Re-validation details (e.g., reason)
            request: FastAPI Request object for context

        Returns:
            Created AuditLog object
        """
        if details is None:
            details = {}
        details["ta_revision_id"] = str(ta_revision_id)
        details["request_id"] = str(request_id)

        return await self.log_action(
            user_id=user_id,
            action=AuditAction.REVALIDATION_TRIGGER,
            entity_type="TARevision",
            entity_id=ta_revision_id,
            details=details,
            request=request,
        )

    async def log_validation_start(
        self,
        ta_revision_id: UUID,
        validation_run_id: UUID,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log the start of validation (system action).

        Args:
            ta_revision_id: ID of the TARevision being validated
            validation_run_id: ID of the ValidationRun
            details: Validation configuration details

        Returns:
            Created AuditLog object
        """
        if details is None:
            details = {}
        details["validation_run_id"] = str(validation_run_id)

        return await self.log_action(
            user_id=None,  # System action
            action=AuditAction.VALIDATION_START,
            entity_type="TARevision",
            entity_id=ta_revision_id,
            details=details,
        )

    async def log_validation_complete(
        self,
        ta_revision_id: UUID,
        validation_run_id: UUID,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log successful validation completion (system action).

        Args:
            ta_revision_id: ID of the TARevision validated
            validation_run_id: ID of the ValidationRun
            details: Validation results summary

        Returns:
            Created AuditLog object
        """
        if details is None:
            details = {}
        details["validation_run_id"] = str(validation_run_id)

        return await self.log_action(
            user_id=None,  # System action
            action=AuditAction.VALIDATION_COMPLETE,
            entity_type="TARevision",
            entity_id=ta_revision_id,
            details=details,
        )

    async def log_validation_failed(
        self,
        ta_revision_id: UUID,
        validation_run_id: UUID,
        details: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log validation failure (system action).

        Args:
            ta_revision_id: ID of the TARevision that failed validation
            validation_run_id: ID of the ValidationRun
            details: Failure details and error information

        Returns:
            Created AuditLog object
        """
        if details is None:
            details = {}
        details["validation_run_id"] = str(validation_run_id)

        return await self.log_action(
            user_id=None,  # System action
            action=AuditAction.VALIDATION_FAILED,
            entity_type="TARevision",
            entity_id=ta_revision_id,
            details=details,
        )

    async def log_config_update(
        self,
        user_id: UUID,
        config_key: str,
        details: Optional[Dict[str, Any]] = None,
        request: Optional[Request] = None,
    ) -> AuditLog:
        """
        Log system configuration update.

        Args:
            user_id: ID of the admin user updating config
            config_key: Configuration key being updated
            details: Old and new values, update reason
            request: FastAPI Request object for context

        Returns:
            Created AuditLog object
        """
        if details is None:
            details = {}
        details["config_key"] = config_key

        return await self.log_action(
            user_id=user_id,
            action=AuditAction.CONFIG_UPDATE,
            entity_type="SystemConfig",
            entity_id=None,
            details=details,
            request=request,
        )
