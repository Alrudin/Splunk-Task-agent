"""
ValidationRunRepository for ValidationRun-specific database operations.
"""
from datetime import datetime
from typing import Dict, List, Optional, Any
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ValidationRun
from backend.models.enums import ValidationStatus
from backend.repositories.base import BaseRepository


class ValidationRunRepository(BaseRepository[ValidationRun]):
    """Repository for ValidationRun model with validation-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, ValidationRun)

    async def get_by_request(
        self, request_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[ValidationRun]:
        """Get all validation runs for a request."""
        result = await self.session.execute(
            select(ValidationRun)
            .where(ValidationRun.request_id == request_id)
            .order_by(ValidationRun.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_revision(self, ta_revision_id: UUID) -> List[ValidationRun]:
        """Get all validation runs for a specific TA revision."""
        result = await self.session.execute(
            select(ValidationRun)
            .where(ValidationRun.ta_revision_id == ta_revision_id)
            .order_by(ValidationRun.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_by_status(
        self, status: ValidationStatus, skip: int = 0, limit: int = 100
    ) -> List[ValidationRun]:
        """Get validations by status."""
        result = await self.session.execute(
            select(ValidationRun)
            .where(ValidationRun.status == status)
            .order_by(ValidationRun.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_validations(self) -> List[ValidationRun]:
        """Get all QUEUED or RUNNING validations."""
        result = await self.session.execute(
            select(ValidationRun).where(
                ValidationRun.status.in_([
                    ValidationStatus.QUEUED,
                    ValidationStatus.RUNNING
                ])
            )
        )
        return list(result.scalars().all())

    async def get_latest_for_revision(
        self, ta_revision_id: UUID
    ) -> Optional[ValidationRun]:
        """Get most recent validation run for a revision."""
        result = await self.session.execute(
            select(ValidationRun)
            .where(ValidationRun.ta_revision_id == ta_revision_id)
            .order_by(ValidationRun.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, validation_id: UUID, status: ValidationStatus
    ) -> Optional[ValidationRun]:
        """Update validation status."""
        await self.session.execute(
            update(ValidationRun)
            .where(ValidationRun.id == validation_id)
            .values(status=status, updated_at=datetime.utcnow())
        )
        await self.session.flush()
        return await self.get_by_id(validation_id)

    async def start_validation(
        self, validation_id: UUID, container_id: str
    ) -> Optional[ValidationRun]:
        """Set status=RUNNING, started_at, splunk_container_id."""
        await self.session.execute(
            update(ValidationRun)
            .where(ValidationRun.id == validation_id)
            .values(
                status=ValidationStatus.RUNNING,
                started_at=datetime.utcnow(),
                splunk_container_id=container_id,
                updated_at=datetime.utcnow()
            )
        )
        await self.session.flush()
        return await self.get_by_id(validation_id)

    async def complete_validation(
        self,
        validation_id: UUID,
        status: ValidationStatus,
        results: Dict[str, Any],
        debug_bundle_key: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[ValidationRun]:
        """Set completed_at, results_json, debug_bundle_key, calculate duration_seconds."""
        validation = await self.get_by_id(validation_id)
        if not validation:
            return None

        completed_at = datetime.utcnow()
        duration_seconds = None
        if validation.started_at:
            duration_seconds = int((completed_at - validation.started_at).total_seconds())

        update_data = {
            "status": status,
            "completed_at": completed_at,
            "results_json": results,
            "duration_seconds": duration_seconds,
            "updated_at": datetime.utcnow()
        }

        if debug_bundle_key:
            update_data["debug_bundle_key"] = debug_bundle_key

        if error_message:
            update_data["error_message"] = error_message

        await self.session.execute(
            update(ValidationRun)
            .where(ValidationRun.id == validation_id)
            .values(**update_data)
        )
        await self.session.flush()
        return await self.get_by_id(validation_id)

    async def get_running_count(self) -> int:
        """Count validations with status=RUNNING."""
        result = await self.session.execute(
            select(func.count())
            .select_from(ValidationRun)
            .where(ValidationRun.status == ValidationStatus.RUNNING)
        )
        return result.scalar()

    async def get_active_count(self) -> int:
        """Count validations with status=QUEUED or RUNNING (for concurrency control)."""
        result = await self.session.execute(
            select(func.count())
            .select_from(ValidationRun)
            .where(ValidationRun.status.in_([
                ValidationStatus.QUEUED,
                ValidationStatus.RUNNING
            ]))
        )
        return result.scalar()

    async def set_container_id(
        self, validation_id: UUID, container_id: str
    ) -> Optional[ValidationRun]:
        """Set splunk_container_id without changing status (for recording sandbox info)."""
        await self.session.execute(
            update(ValidationRun)
            .where(ValidationRun.id == validation_id)
            .values(
                splunk_container_id=container_id,
                updated_at=datetime.utcnow()
            )
        )
        await self.session.flush()
        return await self.get_by_id(validation_id)

    async def get_validation_statistics(self) -> Dict[str, int]:
        """Get counts by status for monitoring dashboard."""
        stats = {}
        for status in ValidationStatus:
            result = await self.session.execute(
                select(func.count())
                .select_from(ValidationRun)
                .where(ValidationRun.status == status)
            )
            stats[status.value] = result.scalar()
        return stats

    async def get_failed_validations(self, request_id: UUID) -> List[ValidationRun]:
        """Get all FAILED validations for a request with debug bundle info."""
        result = await self.session.execute(
            select(ValidationRun).where(
                ValidationRun.request_id == request_id,
                ValidationRun.status == ValidationStatus.FAILED
            ).order_by(ValidationRun.created_at.desc())
        )
        return list(result.scalars().all())
