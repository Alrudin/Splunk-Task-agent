"""
TARevisionRepository for TARevision-specific database operations.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.models import TARevision
from backend.models.enums import TARevisionType
from backend.repositories.base import BaseRepository


class TARevisionRepository(BaseRepository[TARevision]):
    """Repository for TARevision model with TA revision-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, TARevision)

    async def get_by_request(
        self, request_id: UUID, order_by_version: bool = True
    ) -> List[TARevision]:
        """Get all revisions for a request, optionally ordered by version DESC."""
        stmt = select(TARevision).where(TARevision.request_id == request_id)

        if order_by_version:
            stmt = stmt.order_by(TARevision.version.desc())

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_latest_revision(self, request_id: UUID) -> Optional[TARevision]:
        """Get the revision with highest version number for a request."""
        result = await self.session.execute(
            select(TARevision)
            .where(TARevision.request_id == request_id)
            .order_by(TARevision.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_by_version(
        self, request_id: UUID, version: int
    ) -> Optional[TARevision]:
        """Get specific version of a request's TA."""
        result = await self.session.execute(
            select(TARevision).where(
                TARevision.request_id == request_id,
                TARevision.version == version
            )
        )
        return result.scalar_one_or_none()

    async def get_next_version(self, request_id: UUID) -> int:
        """Calculate next version number (max(version) + 1)."""
        result = await self.session.execute(
            select(func.max(TARevision.version))
            .where(TARevision.request_id == request_id)
        )
        max_version = result.scalar()
        return (max_version or 0) + 1

    async def get_by_type(
        self, generated_by: TARevisionType, skip: int = 0, limit: int = 100
    ) -> List[TARevision]:
        """Get revisions by type (AUTO or MANUAL)."""
        result = await self.session.execute(
            select(TARevision)
            .where(TARevision.generated_by == generated_by)
            .order_by(TARevision.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_with_validations(self, revision_id: UUID) -> Optional[TARevision]:
        """Get revision with eagerly loaded validation_runs."""
        result = await self.session.execute(
            select(TARevision)
            .options(selectinload(TARevision.validation_runs))
            .where(TARevision.id == revision_id)
        )
        return result.scalar_one_or_none()

    async def get_auto_generated(self, request_id: UUID) -> List[TARevision]:
        """Get all AUTO-generated revisions for a request."""
        result = await self.session.execute(
            select(TARevision).where(
                TARevision.request_id == request_id,
                TARevision.generated_by == TARevisionType.AUTO
            ).order_by(TARevision.version.desc())
        )
        return list(result.scalars().all())

    async def get_manual_overrides(self, request_id: UUID) -> List[TARevision]:
        """Get all MANUAL revisions for a request."""
        result = await self.session.execute(
            select(TARevision).where(
                TARevision.request_id == request_id,
                TARevision.generated_by == TARevisionType.MANUAL
            ).order_by(TARevision.version.desc())
        )
        return list(result.scalars().all())

    async def get_revision_history(self, request_id: UUID) -> List[TARevision]:
        """Get complete revision history with validation status."""
        result = await self.session.execute(
            select(TARevision)
            .options(selectinload(TARevision.validation_runs))
            .where(TARevision.request_id == request_id)
            .order_by(TARevision.version.desc())
        )
        return list(result.scalars().all())
