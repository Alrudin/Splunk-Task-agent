"""
RequestRepository for Request-specific database operations.
"""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import Request
from backend.models.enums import RequestStatus
from backend.repositories.base import BaseRepository


class RequestRepository(BaseRepository[Request]):
    """Repository for Request model with request-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Request)

    async def get_by_status(
        self, status: RequestStatus, skip: int = 0, limit: int = 100
    ) -> List[Request]:
        """Get requests by status with pagination."""
        result = await self.session.execute(
            select(Request)
            .where(Request.status == status)
            .order_by(Request.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[Request]:
        """Get all requests created by user."""
        result = await self.session.execute(
            select(Request)
            .where(Request.created_by == user_id)
            .order_by(Request.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_pending_approval(self, skip: int = 0, limit: int = 100) -> List[Request]:
        """Get requests with status=PENDING_APPROVAL."""
        return await self.get_by_status(RequestStatus.PENDING_APPROVAL, skip, limit)

    async def get_with_samples(self, request_id: UUID) -> Optional[Request]:
        """Get request with eagerly loaded log_samples."""
        result = await self.session.execute(
            select(Request)
            .options(selectinload(Request.log_samples))
            .where(Request.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_with_revisions(self, request_id: UUID) -> Optional[Request]:
        """Get request with eagerly loaded ta_revisions."""
        result = await self.session.execute(
            select(Request)
            .options(selectinload(Request.ta_revisions))
            .where(Request.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_with_validations(self, request_id: UUID) -> Optional[Request]:
        """Get request with eagerly loaded validation_runs."""
        result = await self.session.execute(
            select(Request)
            .options(selectinload(Request.validation_runs))
            .where(Request.id == request_id)
        )
        return result.scalar_one_or_none()

    async def get_full_details(self, request_id: UUID) -> Optional[Request]:
        """Get request with all relationships loaded."""
        result = await self.session.execute(
            select(Request)
            .options(
                selectinload(Request.log_samples),
                selectinload(Request.ta_revisions),
                selectinload(Request.validation_runs)
            )
            .where(Request.id == request_id)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, request_id: UUID, new_status: RequestStatus
    ) -> Optional[Request]:
        """Update request status and updated_at."""
        await self.session.execute(
            update(Request)
            .where(Request.id == request_id)
            .values(status=new_status, updated_at=datetime.utcnow())
        )
        await self.session.flush()
        return await self.get_by_id(request_id)

    async def approve_request(
        self, request_id: UUID, approved_by: UUID
    ) -> Optional[Request]:
        """Set status=APPROVED, approved_by, approved_at."""
        await self.session.execute(
            update(Request)
            .where(Request.id == request_id)
            .values(
                status=RequestStatus.APPROVED,
                approved_by=approved_by,
                approved_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
        )
        await self.session.flush()
        return await self.get_by_id(request_id)

    async def reject_request(
        self, request_id: UUID, rejected_by: UUID, reason: str
    ) -> Optional[Request]:
        """Set status=REJECTED, rejection_reason."""
        await self.session.execute(
            update(Request)
            .where(Request.id == request_id)
            .values(
                status=RequestStatus.REJECTED,
                approved_by=rejected_by,
                approved_at=datetime.utcnow(),
                rejection_reason=reason,
                updated_at=datetime.utcnow()
            )
        )
        await self.session.flush()
        return await self.get_by_id(request_id)

    async def get_statistics(self) -> Dict[str, int]:
        """Get request counts by status for dashboard."""
        stats = {}
        for status in RequestStatus:
            result = await self.session.execute(
                select(func.count())
                .select_from(Request)
                .where(Request.status == status)
            )
            stats[status.value] = result.scalar()
        return stats

    async def search_requests(
        self,
        query: str,
        status: Optional[RequestStatus] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[Request]:
        """Search by source_system or description."""
        search_pattern = f"%{query}%"
        stmt = select(Request).where(
            or_(
                Request.source_system.ilike(search_pattern),
                Request.description.ilike(search_pattern)
            )
        )

        if status:
            stmt = stmt.where(Request.status == status)

        stmt = stmt.order_by(Request.created_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
