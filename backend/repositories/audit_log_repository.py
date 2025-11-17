"""
AuditLogRepository for AuditLog-specific database operations.
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import AuditLog
from backend.models.enums import AuditAction
from backend.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    """
    Repository for AuditLog model with audit log-specific queries.

    NOTE: This repository does NOT implement update or delete methods,
    as audit logs are immutable for integrity.
    """

    def __init__(self, session: AsyncSession):
        super().__init__(session, AuditLog)

    # Override base delete to prevent deletion
    async def delete(self, id: UUID) -> bool:
        """Audit logs cannot be deleted."""
        raise NotImplementedError("Audit logs are immutable and cannot be deleted")

    # Override base update to prevent updates
    async def update(self, id: UUID, data: Dict[str, Any]) -> Optional[AuditLog]:
        """Audit logs cannot be updated."""
        raise NotImplementedError("Audit logs are immutable and cannot be updated")

    async def create_log(
        self,
        user_id: Optional[UUID],
        action: AuditAction,
        entity_type: str,
        entity_id: Optional[UUID],
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        correlation_id: Optional[UUID] = None
    ) -> AuditLog:
        """Create audit log entry with all fields."""
        audit_log = AuditLog(
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
            timestamp=datetime.utcnow()
        )
        self.session.add(audit_log)
        await self.session.flush()
        await self.session.refresh(audit_log)
        return audit_log

    async def get_by_user(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        """Get audit logs for a user."""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.user_id == user_id)
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_entity(
        self, entity_type: str, entity_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        """Get audit trail for an entity."""
        result = await self.session.execute(
            select(AuditLog)
            .where(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id
            )
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_action(
        self, action: AuditAction, skip: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        """Get logs by action type."""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.action == action)
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_correlation_id(self, correlation_id: UUID) -> List[AuditLog]:
        """Get all logs in a correlated flow."""
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.correlation_id == correlation_id)
            .order_by(AuditLog.timestamp)
        )
        return list(result.scalars().all())

    async def get_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Get logs within date range."""
        result = await self.session.execute(
            select(AuditLog)
            .where(
                AuditLog.timestamp >= start_date,
                AuditLog.timestamp <= end_date
            )
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_activity(
        self, hours: int = 24, skip: int = 0, limit: int = 100
    ) -> List[AuditLog]:
        """Get recent activity for dashboard."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        result = await self.session.execute(
            select(AuditLog)
            .where(AuditLog.timestamp >= cutoff)
            .order_by(AuditLog.timestamp.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_logs_for_cleanup(self, cutoff_date: datetime) -> List[AuditLog]:
        """Get logs older than retention period for cleanup."""
        result = await self.session.execute(
            select(AuditLog).where(AuditLog.timestamp < cutoff_date)
        )
        return list(result.scalars().all())

    async def search_logs(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[AuditLog]:
        """Advanced search with multiple filters."""
        stmt = select(AuditLog)

        # Apply filters if provided
        if filters:
            if "user_id" in filters:
                stmt = stmt.where(AuditLog.user_id == filters["user_id"])
            if "action" in filters:
                stmt = stmt.where(AuditLog.action == filters["action"])
            if "entity_type" in filters:
                stmt = stmt.where(AuditLog.entity_type == filters["entity_type"])
            if "entity_id" in filters:
                stmt = stmt.where(AuditLog.entity_id == filters["entity_id"])
            if "start_date" in filters:
                stmt = stmt.where(AuditLog.timestamp >= filters["start_date"])
            if "end_date" in filters:
                stmt = stmt.where(AuditLog.timestamp <= filters["end_date"])

        stmt = stmt.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())
