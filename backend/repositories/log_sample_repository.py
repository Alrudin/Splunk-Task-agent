"""
LogSampleRepository for LogSample-specific database operations.
"""
from datetime import datetime
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import LogSample
from backend.repositories.base import BaseRepository


class LogSampleRepository(BaseRepository[LogSample]):
    """Repository for LogSample model with log sample-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, LogSample)

    async def get_by_request(self, request_id: UUID) -> List[LogSample]:
        """Get all log samples for a request."""
        result = await self.session.execute(
            select(LogSample)
            .where(LogSample.request_id == request_id)
            .order_by(LogSample.created_at)
        )
        return list(result.scalars().all())

    async def get_by_storage_key(self, storage_key: str) -> Optional[LogSample]:
        """Find sample by storage key."""
        result = await self.session.execute(
            select(LogSample).where(LogSample.storage_key == storage_key)
        )
        return result.scalar_one_or_none()

    async def get_samples_for_cleanup(self, cutoff_date: datetime) -> List[LogSample]:
        """Get samples where retention_until < cutoff_date and deleted_at is NULL."""
        result = await self.session.execute(
            select(LogSample).where(
                LogSample.retention_until < cutoff_date,
                LogSample.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())

    async def mark_as_deleted(self, sample_id: UUID) -> Optional[LogSample]:
        """Set deleted_at to current timestamp (soft delete)."""
        await self.session.execute(
            update(LogSample)
            .where(LogSample.id == sample_id)
            .values(deleted_at=datetime.utcnow())
        )
        await self.session.flush()
        return await self.get_by_id(sample_id)

    async def get_total_size_by_request(self, request_id: UUID) -> int:
        """Sum file_size for all samples in a request."""
        result = await self.session.execute(
            select(func.sum(LogSample.file_size))
            .where(LogSample.request_id == request_id)
        )
        total = result.scalar()
        return total or 0

    async def get_active_samples(self, request_id: UUID) -> List[LogSample]:
        """Get samples where deleted_at is NULL."""
        result = await self.session.execute(
            select(LogSample).where(
                LogSample.request_id == request_id,
                LogSample.deleted_at.is_(None)
            )
        )
        return list(result.scalars().all())

    async def update_retention_date(
        self, sample_id: UUID, retention_until: datetime
    ) -> Optional[LogSample]:
        """Update retention_until timestamp."""
        await self.session.execute(
            update(LogSample)
            .where(LogSample.id == sample_id)
            .values(retention_until=retention_until)
        )
        await self.session.flush()
        return await self.get_by_id(sample_id)

    async def get_aggregated_stats_by_requests(
        self, request_ids: List[UUID]
    ) -> Dict[UUID, Dict[str, int]]:
        """
        Get aggregated sample statistics for multiple requests in a single query.

        Args:
            request_ids: List of request IDs to get stats for

        Returns:
            Dict mapping request_id to {"count": int, "total_size": int}
        """
        if not request_ids:
            return {}

        result = await self.session.execute(
            select(
                LogSample.request_id,
                func.count(LogSample.id).label("count"),
                func.coalesce(func.sum(LogSample.file_size), 0).label("total_size"),
            )
            .where(
                LogSample.request_id.in_(request_ids),
                LogSample.deleted_at.is_(None),
            )
            .group_by(LogSample.request_id)
        )

        stats = {}
        for row in result:
            stats[row.request_id] = {
                "count": row.count,
                "total_size": row.total_size,
            }

        # Fill in zeros for request_ids with no samples
        for request_id in request_ids:
            if request_id not in stats:
                stats[request_id] = {"count": 0, "total_size": 0}

        return stats
