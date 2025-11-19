"""
FastAPI router for audit log API endpoints.

Provides endpoints for querying and filtering audit logs with role-based access control.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.dependencies import get_current_active_user, require_any_role
from backend.core.exceptions import NotFoundError
from backend.database import get_db
from backend.models.audit_log import AuditLog
from backend.models.enums import UserRoleEnum
from backend.models.user import User
from backend.repositories.audit_log_repository import AuditLogRepository
from backend.schemas.audit import AuditLogListResponse, AuditLogQueryParams, AuditLogResponse

router = APIRouter(prefix="/audit", tags=["Audit Logs"])


@router.get(
    "",
    response_model=AuditLogListResponse,
    summary="Query audit logs",
    description="""
    Query audit logs with flexible filtering and pagination.

    Supports filtering by:
    - user_id: Filter logs by specific user
    - action: Filter by action type (e.g., APPROVE, LOGIN)
    - entity_type: Filter by entity type (e.g., Request, TARevision)
    - entity_id: Filter by specific entity ID
    - start_date: Filter logs after this date (inclusive)
    - end_date: Filter logs before this date (inclusive)
    - correlation_id: Filter by correlation ID for tracing related actions

    Requires ADMIN or APPROVER role for access.
    """,
)
async def query_audit_logs(
    params: AuditLogQueryParams = Depends(),
    current_user: User = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.APPROVER)),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """
    Query audit logs with filtering and pagination.

    Accessible by ADMIN and APPROVER roles only.
    """
    # Build filters dictionary from params
    filters = {}
    if params.user_id:
        filters["user_id"] = params.user_id
    if params.action:
        filters["action"] = params.action
    if params.entity_type:
        filters["entity_type"] = params.entity_type
    if params.entity_id:
        filters["entity_id"] = params.entity_id
    if params.correlation_id:
        filters["correlation_id"] = params.correlation_id
    if params.start_date:
        filters["start_date"] = params.start_date
    if params.end_date:
        filters["end_date"] = params.end_date

    # Query audit logs
    audit_repo = AuditLogRepository(db)
    audit_logs = await audit_repo.search_logs(filters=filters, skip=params.skip, limit=params.limit)

    # Count total matching records
    count_stmt = select(func.count(AuditLog.id))
    if filters:
        if "user_id" in filters:
            count_stmt = count_stmt.where(AuditLog.user_id == filters["user_id"])
        if "action" in filters:
            count_stmt = count_stmt.where(AuditLog.action == filters["action"])
        if "entity_type" in filters:
            count_stmt = count_stmt.where(AuditLog.entity_type == filters["entity_type"])
        if "entity_id" in filters:
            count_stmt = count_stmt.where(AuditLog.entity_id == filters["entity_id"])
        if "correlation_id" in filters:
            count_stmt = count_stmt.where(AuditLog.correlation_id == filters["correlation_id"])
        if "start_date" in filters:
            count_stmt = count_stmt.where(AuditLog.timestamp >= filters["start_date"])
        if "end_date" in filters:
            count_stmt = count_stmt.where(AuditLog.timestamp <= filters["end_date"])

    result = await db.execute(count_stmt)
    total = result.scalar() or 0

    # Convert to response schema
    items = [AuditLogResponse.model_validate(log) for log in audit_logs]

    return AuditLogListResponse(
        items=items,
        total=total,
        skip=params.skip,
        limit=params.limit,
    )


@router.get(
    "/{audit_id}",
    response_model=AuditLogResponse,
    summary="Get audit log by ID",
    description="Retrieve a specific audit log entry by its ID. Requires ADMIN or APPROVER role.",
)
async def get_audit_log_by_id(
    audit_id: UUID,
    current_user: User = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.APPROVER)),
    db: AsyncSession = Depends(get_db),
) -> AuditLogResponse:
    """Get a single audit log by ID."""
    audit_repo = AuditLogRepository(db)
    audit_log = await audit_repo.get_by_id(audit_id)

    if not audit_log:
        raise NotFoundError(f"Audit log with ID {audit_id} not found")

    return AuditLogResponse.model_validate(audit_log)


@router.get(
    "/user/{user_id}",
    response_model=AuditLogListResponse,
    summary="Get audit logs for a user",
    description="""
    Retrieve all audit logs for a specific user with pagination.

    Requires ADMIN or APPROVER role for access.
    Users can access their own audit logs without elevated permissions.
    """,
)
async def get_audit_logs_by_user(
    user_id: UUID,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Get audit logs for a specific user."""
    # Check permissions: user can view own logs, or must be ADMIN/APPROVER
    user_roles = [role.name for role in current_user.roles]
    is_admin_or_approver = UserRoleEnum.ADMIN.value in user_roles or UserRoleEnum.APPROVER.value in user_roles

    if current_user.id != user_id and not is_admin_or_approver:
        from backend.core.exceptions import InsufficientPermissionsError
        raise InsufficientPermissionsError("You can only view your own audit logs")

    # Query audit logs
    audit_repo = AuditLogRepository(db)
    audit_logs = await audit_repo.get_by_user(user_id=user_id, skip=skip, limit=limit)

    # Count total
    count_stmt = select(func.count(AuditLog.id)).where(AuditLog.user_id == user_id)
    result = await db.execute(count_stmt)
    total = result.scalar() or 0

    # Convert to response schema
    items = [AuditLogResponse.model_validate(log) for log in audit_logs]

    return AuditLogListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/entity/{entity_type}/{entity_id}",
    response_model=AuditLogListResponse,
    summary="Get audit trail for an entity",
    description="""
    Retrieve the complete audit trail for a specific entity.

    Useful for tracking all actions performed on a Request, TARevision, etc.
    Requires ADMIN or APPROVER role.
    """,
)
async def get_audit_logs_by_entity(
    entity_type: str,
    entity_id: UUID,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records to return"),
    current_user: User = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.APPROVER)),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Get audit trail for a specific entity."""
    # Query audit logs
    audit_repo = AuditLogRepository(db)
    audit_logs = await audit_repo.get_by_entity(
        entity_type=entity_type,
        entity_id=entity_id,
        skip=skip,
        limit=limit
    )

    # Count total
    count_stmt = select(func.count(AuditLog.id)).where(
        AuditLog.entity_type == entity_type,
        AuditLog.entity_id == entity_id
    )
    result = await db.execute(count_stmt)
    total = result.scalar() or 0

    # Convert to response schema
    items = [AuditLogResponse.model_validate(log) for log in audit_logs]

    return AuditLogListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/correlation/{correlation_id}",
    response_model=AuditLogListResponse,
    summary="Get audit logs by correlation ID",
    description="""
    Retrieve all audit logs with the same correlation ID for tracing related actions.

    Correlation IDs link related operations across multiple requests and services,
    enabling end-to-end tracking of a workflow (e.g., request submission -> approval -> TA generation -> validation).

    Requires ADMIN or APPROVER role.
    """,
)
async def get_audit_logs_by_correlation(
    correlation_id: str,
    current_user: User = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.APPROVER)),
    db: AsyncSession = Depends(get_db),
) -> AuditLogListResponse:
    """Get all audit logs with the same correlation ID."""
    # Query audit logs
    audit_repo = AuditLogRepository(db)
    audit_logs = await audit_repo.get_by_correlation_id(correlation_id=correlation_id)

    # Count total (same as length since we don't paginate correlation queries)
    total = len(audit_logs)

    # Convert to response schema
    items = [AuditLogResponse.model_validate(log) for log in audit_logs]

    return AuditLogListResponse(
        items=items,
        total=total,
        skip=0,
        limit=total,
    )
