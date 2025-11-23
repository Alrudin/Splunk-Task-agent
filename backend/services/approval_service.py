"""
Approval service for managing approval workflow operations.

This service orchestrates approve/reject logic, validates state transitions,
and coordinates with repositories for audit logging. Upon approval, it
enqueues the TA generation background task.
"""

import structlog
from typing import Optional, List
from uuid import UUID

from backend.models.user import User
from backend.models.request import Request
from backend.models.enums import RequestStatus, AuditAction, UserRoleEnum
from backend.repositories.request_repository import RequestRepository
from backend.repositories.audit_log_repository import AuditLogRepository
from backend.core.exceptions import (
    RequestNotFoundError,
    InvalidRequestStateError,
    InsufficientPermissionsError,
)
from backend.tasks.generate_ta_task import generate_ta

logger = structlog.get_logger(__name__)


class ApprovalService:
    """Service for managing approval workflow operations."""

    def __init__(
        self,
        request_repository: RequestRepository,
        audit_log_repository: AuditLogRepository,
    ):
        """Initialize with injected dependencies.

        Args:
            request_repository: Repository for request operations
            audit_log_repository: Repository for audit logging
        """
        self.request_repository = request_repository
        self.audit_log_repository = audit_log_repository

    def _verify_approver_role(self, user: User) -> None:
        """Verify user has APPROVER or ADMIN role.

        Args:
            user: User to verify

        Raises:
            InsufficientPermissionsError: If user lacks required role
        """
        user_roles = {role.name for role in user.roles}
        required_roles = {UserRoleEnum.APPROVER.value, UserRoleEnum.ADMIN.value}

        if not user_roles.intersection(required_roles):
            logger.warning(
                "User lacks approver permissions",
                user_id=str(user.id),
                username=user.username,
                user_roles=list(user_roles),
            )
            raise InsufficientPermissionsError(
                "User must have APPROVER or ADMIN role to perform approval operations"
            )

    async def get_pending_approvals(
        self,
        skip: int = 0,
        limit: int = 100,
        current_user: User = None,
    ) -> List[Request]:
        """List requests with status=PENDING_APPROVAL.

        Args:
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
            current_user: User making the request

        Returns:
            List of pending approval requests

        Raises:
            InsufficientPermissionsError: If user lacks APPROVER/ADMIN role
        """
        self._verify_approver_role(current_user)

        logger.info(
            "Fetching pending approvals",
            skip=skip,
            limit=limit,
            user_id=str(current_user.id),
            username=current_user.username,
        )

        requests = await self.request_repository.get_pending_approval(
            skip=skip,
            limit=limit,
        )

        logger.info(
            "Fetched pending approvals",
            count=len(requests),
            user_id=str(current_user.id),
        )

        return requests

    async def get_approval_detail(
        self,
        request_id: UUID,
        current_user: User,
    ) -> Request:
        """Get request details with samples for approval review.

        Args:
            request_id: ID of request to retrieve
            current_user: User making the request

        Returns:
            Request with eagerly loaded samples

        Raises:
            InsufficientPermissionsError: If user lacks APPROVER/ADMIN role
            RequestNotFoundError: If request doesn't exist
        """
        self._verify_approver_role(current_user)

        logger.info(
            "Fetching approval detail",
            request_id=str(request_id),
            user_id=str(current_user.id),
            username=current_user.username,
        )

        request = await self.request_repository.get_with_samples(request_id)

        if not request:
            logger.warning(
                "Request not found for approval detail",
                request_id=str(request_id),
                user_id=str(current_user.id),
            )
            raise RequestNotFoundError(f"Request {request_id} not found")

        logger.info(
            "Fetched approval detail",
            request_id=str(request_id),
            status=request.status.value,
            sample_count=len(request.log_samples) if request.log_samples else 0,
        )

        return request

    async def approve_request(
        self,
        request_id: UUID,
        approver_user: User,
        comment: Optional[str] = None,
    ) -> Request:
        """Approve a request.

        Args:
            request_id: ID of request to approve
            approver_user: User approving the request
            comment: Optional approval comment

        Returns:
            Updated request

        Raises:
            InsufficientPermissionsError: If user lacks APPROVER/ADMIN role
            RequestNotFoundError: If request doesn't exist
            InvalidRequestStateError: If request not in PENDING_APPROVAL state
        """
        self._verify_approver_role(approver_user)

        logger.info(
            "Approving request",
            request_id=str(request_id),
            approver_id=str(approver_user.id),
            approver_username=approver_user.username,
            comment=comment,
        )

        # Fetch request to validate state
        request = await self.request_repository.get_by_id(request_id)

        if not request:
            logger.warning(
                "Request not found for approval",
                request_id=str(request_id),
                approver_id=str(approver_user.id),
            )
            raise RequestNotFoundError(f"Request {request_id} not found")

        if request.status != RequestStatus.PENDING_APPROVAL:
            logger.warning(
                "Invalid request state for approval",
                request_id=str(request_id),
                current_status=request.status.value,
                approver_id=str(approver_user.id),
            )
            raise InvalidRequestStateError(
                f"Request must be in PENDING_APPROVAL state to approve. "
                f"Current state: {request.status.value}"
            )

        # Approve request
        updated_request = await self.request_repository.approve_request(
            request_id=request_id,
            approver_id=approver_user.id,
        )

        # Log approval action
        await self.audit_log_repository.create(
            user_id=approver_user.id,
            action=AuditAction.APPROVE,
            entity_type="request",
            entity_id=str(request_id),
            details={
                "approver": approver_user.username,
                "comment": comment,
                "previous_status": request.status.value,
                "new_status": RequestStatus.APPROVED.value,
            },
        )

        logger.info(
            "Request approved successfully",
            request_id=str(request_id),
            approver_id=str(approver_user.id),
            approver_username=approver_user.username,
        )

        # Enqueue TA generation background task
        try:
            task_result = generate_ta.delay(request_id=str(request_id))
            logger.info(
                "TA generation task enqueued",
                request_id=str(request_id),
                task_id=task_result.id,
                approver_id=str(approver_user.id),
            )
        except Exception as e:
            # Log error but don't fail the approval - task can be retried manually
            logger.error(
                "Failed to enqueue TA generation task",
                request_id=str(request_id),
                error=str(e),
                approver_id=str(approver_user.id),
            )

        return updated_request

    async def reject_request(
        self,
        request_id: UUID,
        approver_user: User,
        reason: str,
    ) -> Request:
        """Reject a request.

        Args:
            request_id: ID of request to reject
            approver_user: User rejecting the request
            reason: Required rejection reason

        Returns:
            Updated request

        Raises:
            InsufficientPermissionsError: If user lacks APPROVER/ADMIN role
            RequestNotFoundError: If request doesn't exist
            InvalidRequestStateError: If request not in PENDING_APPROVAL state
        """
        self._verify_approver_role(approver_user)

        logger.info(
            "Rejecting request",
            request_id=str(request_id),
            approver_id=str(approver_user.id),
            approver_username=approver_user.username,
            reason=reason,
        )

        # Fetch request to validate state
        request = await self.request_repository.get_by_id(request_id)

        if not request:
            logger.warning(
                "Request not found for rejection",
                request_id=str(request_id),
                approver_id=str(approver_user.id),
            )
            raise RequestNotFoundError(f"Request {request_id} not found")

        if request.status != RequestStatus.PENDING_APPROVAL:
            logger.warning(
                "Invalid request state for rejection",
                request_id=str(request_id),
                current_status=request.status.value,
                approver_id=str(approver_user.id),
            )
            raise InvalidRequestStateError(
                f"Request must be in PENDING_APPROVAL state to reject. "
                f"Current state: {request.status.value}"
            )

        # Reject request
        updated_request = await self.request_repository.reject_request(
            request_id=request_id,
            approver_id=approver_user.id,
            reason=reason,
        )

        # Log rejection action
        await self.audit_log_repository.create(
            user_id=approver_user.id,
            action=AuditAction.REJECT,
            entity_type="request",
            entity_id=str(request_id),
            details={
                "approver": approver_user.username,
                "reason": reason,
                "previous_status": request.status.value,
                "new_status": RequestStatus.REJECTED.value,
            },
        )

        logger.info(
            "Request rejected successfully",
            request_id=str(request_id),
            approver_id=str(approver_user.id),
            approver_username=approver_user.username,
        )

        return updated_request

    async def get_approval_statistics(
        self,
        current_user: User,
    ) -> dict:
        """Get counts of requests by status for dashboard metrics.

        Args:
            current_user: User making the request

        Returns:
            Dictionary with counts by status

        Raises:
            InsufficientPermissionsError: If user lacks APPROVER/ADMIN role
        """
        self._verify_approver_role(current_user)

        logger.info(
            "Fetching approval statistics",
            user_id=str(current_user.id),
            username=current_user.username,
        )

        statistics = await self.request_repository.get_statistics()

        logger.info(
            "Fetched approval statistics",
            user_id=str(current_user.id),
            statistics=statistics,
        )

        return statistics
