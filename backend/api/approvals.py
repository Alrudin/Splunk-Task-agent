"""
FastAPI router for approval operations.

Provides endpoints for listing pending approvals, viewing request details,
and performing approve/reject actions.
"""

import structlog
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.user import User
from backend.models.enums import UserRoleEnum
from backend.core.dependencies import require_any_role, get_current_user
from backend.services.approval_service import ApprovalService
from backend.repositories.request_repository import RequestRepository
from backend.repositories.audit_log_repository import AuditLogRepository
from backend.repositories.log_sample_repository import LogSampleRepository
from backend.schemas.approval import (
    ApproveRequestRequest,
    RejectRequestRequest,
    ApprovalResponse,
    PendingApprovalListResponse,
    ApprovalStatisticsResponse,
)
from backend.schemas.request import RequestResponse, RequestDetailResponse

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


def get_approval_service(
    db: AsyncSession = Depends(get_db),
) -> ApprovalService:
    """Factory function to create ApprovalService with injected dependencies.

    Args:
        db: Database session

    Returns:
        ApprovalService instance
    """
    request_repo = RequestRepository(db)
    audit_repo = AuditLogRepository(db)
    return ApprovalService(
        request_repository=request_repo,
        audit_log_repository=audit_repo,
    )


@router.get(
    "/pending",
    response_model=PendingApprovalListResponse,
    summary="List pending approval requests",
    description="Get paginated list of requests awaiting approval. Requires APPROVER or ADMIN role.",
)
async def list_pending_approvals(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    approval_service: ApprovalService = Depends(get_approval_service),
    sample_repo: LogSampleRepository = Depends(lambda db=Depends(get_db): LogSampleRepository(db)),
    current_user: User = Depends(
        require_any_role([UserRoleEnum.APPROVER, UserRoleEnum.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    """List pending approval requests.

    Args:
        skip: Number of records to skip (pagination)
        limit: Maximum number of records to return
        approval_service: Approval service instance
        sample_repo: Log sample repository for fetching sample stats
        current_user: Authenticated user
        db: Database session

    Returns:
        PendingApprovalListResponse with paginated results
    """
    logger.info(
        "Listing pending approvals",
        skip=skip,
        limit=limit,
        user_id=str(current_user.id),
        username=current_user.username,
    )

    # Fetch pending approvals
    requests = await approval_service.get_pending_approvals(
        skip=skip,
        limit=limit,
        current_user=current_user,
    )

    # Get total count
    total = await RequestRepository(db).count_pending_approval()

    # Fetch sample stats for each request
    request_ids = [req.id for req in requests]
    sample_stats = {}
    if request_ids:
        stats = await sample_repo.get_aggregated_stats_by_requests(request_ids)
        sample_stats = {stat["request_id"]: stat for stat in stats}

    # Build response items
    items = []
    for req in requests:
        stats = sample_stats.get(req.id, {})
        items.append(
            RequestResponse(
                id=req.id,
                source_system=req.source_system,
                description=req.description,
                cim_required=req.cim_required,
                status=req.status,
                submitted_by=req.submitted_by,
                submitted_at=req.submitted_at,
                approved_by=req.approved_by,
                approved_at=req.approved_at,
                rejection_reason=req.rejection_reason,
                created_at=req.created_at,
                updated_at=req.updated_at,
                sample_count=stats.get("sample_count", 0),
                total_sample_size=stats.get("total_size", 0),
            )
        )

    logger.info(
        "Listed pending approvals",
        count=len(items),
        total=total,
        user_id=str(current_user.id),
    )

    return PendingApprovalListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{request_id}",
    response_model=RequestDetailResponse,
    summary="Get request details for approval",
    description="Get detailed information about a request pending approval, including samples.",
)
async def get_approval_detail(
    request_id: UUID,
    approval_service: ApprovalService = Depends(get_approval_service),
    current_user: User = Depends(
        require_any_role([UserRoleEnum.APPROVER, UserRoleEnum.ADMIN])
    ),
):
    """Get request details for approval review.

    Args:
        request_id: UUID of request to retrieve
        approval_service: Approval service instance
        current_user: Authenticated user

    Returns:
        RequestDetailResponse with request details and samples
    """
    logger.info(
        "Getting approval detail",
        request_id=str(request_id),
        user_id=str(current_user.id),
        username=current_user.username,
    )

    request = await approval_service.get_approval_detail(
        request_id=request_id,
        current_user=current_user,
    )

    # Build sample responses
    from backend.schemas.sample import SampleResponse

    samples = []
    if request.log_samples:
        for sample in request.log_samples:
            samples.append(
                SampleResponse(
                    id=sample.id,
                    request_id=sample.request_id,
                    filename=sample.filename,
                    size_bytes=sample.size_bytes,
                    content_type=sample.content_type,
                    storage_path=sample.storage_path,
                    uploaded_at=sample.uploaded_at,
                    created_at=sample.created_at,
                )
            )

    response = RequestDetailResponse(
        id=request.id,
        source_system=request.source_system,
        description=request.description,
        cim_required=request.cim_required,
        status=request.status,
        submitted_by=request.submitted_by,
        submitted_at=request.submitted_at,
        approved_by=request.approved_by,
        approved_at=request.approved_at,
        rejection_reason=request.rejection_reason,
        created_at=request.created_at,
        updated_at=request.updated_at,
        samples=samples,
    )

    logger.info(
        "Retrieved approval detail",
        request_id=str(request_id),
        sample_count=len(samples),
        user_id=str(current_user.id),
    )

    return response


@router.post(
    "/{request_id}/approve",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Approve a request",
    description="Approve a request and transition status to APPROVED. Requires APPROVER or ADMIN role.",
)
async def approve_request(
    request_id: UUID,
    data: ApproveRequestRequest,
    approval_service: ApprovalService = Depends(get_approval_service),
    current_user: User = Depends(
        require_any_role([UserRoleEnum.APPROVER, UserRoleEnum.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Approve a request.

    Args:
        request_id: UUID of request to approve
        data: Approval request data (optional comment)
        approval_service: Approval service instance
        current_user: Authenticated user
        db: Database session

    Returns:
        ApprovalResponse with updated request details
    """
    logger.info(
        "Approving request",
        request_id=str(request_id),
        user_id=str(current_user.id),
        username=current_user.username,
        comment=data.comment,
    )

    updated_request = await approval_service.approve_request(
        request_id=request_id,
        approver_user=current_user,
        comment=data.comment,
    )

    # Commit transaction
    await db.commit()
    await db.refresh(updated_request)

    # Load approver relationship for response
    if updated_request.approved_by_user:
        approver_username = updated_request.approved_by_user.username
        approver_full_name = updated_request.approved_by_user.full_name
    else:
        approver_username = None
        approver_full_name = None

    response = ApprovalResponse(
        id=updated_request.id,
        source_system=updated_request.source_system,
        description=updated_request.description,
        cim_required=updated_request.cim_required,
        status=updated_request.status,
        submitted_by=updated_request.submitted_by,
        submitted_at=updated_request.submitted_at,
        approved_by=updated_request.approved_by,
        approved_at=updated_request.approved_at,
        rejection_reason=updated_request.rejection_reason,
        created_at=updated_request.created_at,
        updated_at=updated_request.updated_at,
        approver_username=approver_username,
        approver_full_name=approver_full_name,
    )

    logger.info(
        "Request approved successfully",
        request_id=str(request_id),
        user_id=str(current_user.id),
    )

    return response


@router.post(
    "/{request_id}/reject",
    response_model=ApprovalResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject a request",
    description="Reject a request and transition status to REJECTED. Requires APPROVER or ADMIN role.",
)
async def reject_request(
    request_id: UUID,
    data: RejectRequestRequest,
    approval_service: ApprovalService = Depends(get_approval_service),
    current_user: User = Depends(
        require_any_role([UserRoleEnum.APPROVER, UserRoleEnum.ADMIN])
    ),
    db: AsyncSession = Depends(get_db),
):
    """Reject a request.

    Args:
        request_id: UUID of request to reject
        data: Rejection request data (required reason)
        approval_service: Approval service instance
        current_user: Authenticated user
        db: Database session

    Returns:
        ApprovalResponse with updated request details
    """
    logger.info(
        "Rejecting request",
        request_id=str(request_id),
        user_id=str(current_user.id),
        username=current_user.username,
        reason=data.reason,
    )

    updated_request = await approval_service.reject_request(
        request_id=request_id,
        approver_user=current_user,
        reason=data.reason,
    )

    # Commit transaction
    await db.commit()
    await db.refresh(updated_request)

    # Load approver relationship for response
    if updated_request.approved_by_user:
        approver_username = updated_request.approved_by_user.username
        approver_full_name = updated_request.approved_by_user.full_name
    else:
        approver_username = None
        approver_full_name = None

    response = ApprovalResponse(
        id=updated_request.id,
        source_system=updated_request.source_system,
        description=updated_request.description,
        cim_required=updated_request.cim_required,
        status=updated_request.status,
        submitted_by=updated_request.submitted_by,
        submitted_at=updated_request.submitted_at,
        approved_by=updated_request.approved_by,
        approved_at=updated_request.approved_at,
        rejection_reason=updated_request.rejection_reason,
        created_at=updated_request.created_at,
        updated_at=updated_request.updated_at,
        approver_username=approver_username,
        approver_full_name=approver_full_name,
    )

    logger.info(
        "Request rejected successfully",
        request_id=str(request_id),
        user_id=str(current_user.id),
    )

    return response


@router.get(
    "/statistics",
    response_model=ApprovalStatisticsResponse,
    summary="Get approval statistics",
    description="Get counts of requests by status for dashboard metrics.",
)
async def get_approval_statistics(
    approval_service: ApprovalService = Depends(get_approval_service),
    current_user: User = Depends(
        require_any_role([UserRoleEnum.APPROVER, UserRoleEnum.ADMIN])
    ),
):
    """Get approval statistics for dashboard.

    Args:
        approval_service: Approval service instance
        current_user: Authenticated user

    Returns:
        ApprovalStatisticsResponse with counts by status
    """
    logger.info(
        "Getting approval statistics",
        user_id=str(current_user.id),
        username=current_user.username,
    )

    statistics = await approval_service.get_approval_statistics(
        current_user=current_user,
    )

    response = ApprovalStatisticsResponse(
        pending_approval=statistics.get("pending_approval", 0),
        approved=statistics.get("approved", 0),
        rejected=statistics.get("rejected", 0),
        total=statistics.get("total", 0),
    )

    logger.info(
        "Retrieved approval statistics",
        user_id=str(current_user.id),
        statistics=statistics,
    )

    return response
