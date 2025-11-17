"""
Base repository providing common CRUD operations.

This module defines the BaseRepository abstract class that provides standard
database operations for all repository implementations.
"""
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.base import Base


ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """
    Base repository class providing common CRUD operations.

    Subclass this to create model-specific repositories with additional queries.
    """

    def __init__(self, session: AsyncSession, model: Type[ModelType]):
        """
        Initialize repository with database session and model class.

        Args:
            session: SQLAlchemy async session
            model: SQLAlchemy model class
        """
        self.session = session
        self.model = model

    async def get_by_id(self, id: UUID) -> Optional[ModelType]:
        """
        Retrieve single record by primary key.

        Args:
            id: Primary key UUID

        Returns:
            Model instance or None if not found
        """
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """
        Retrieve paginated list of records.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of model instances
        """
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelType:
        """
        Create new record from keyword arguments.

        Args:
            **kwargs: Field values as keyword arguments

        Returns:
            Created model instance
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def update(self, id: UUID, **kwargs) -> Optional[ModelType]:
        """
        Update existing record.

        Args:
            id: Primary key UUID
            **kwargs: Field values to update

        Returns:
            Updated model instance or None if not found
        """
        await self.session.execute(
            update(self.model).where(self.model.id == id).values(**kwargs)
        )
        await self.session.flush()
        return await self.get_by_id(id)

    async def delete(self, id: UUID) -> bool:
        """
        Delete record by ID.

        Args:
            id: Primary key UUID

        Returns:
            True if deleted, False if not found
        """
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def exists(self, id: UUID) -> bool:
        """
        Check if record exists.

        Args:
            id: Primary key UUID

        Returns:
            True if exists, False otherwise
        """
        result = await self.session.execute(
            select(func.count()).select_from(self.model).where(self.model.id == id)
        )
        count = result.scalar()
        return count > 0

    async def count(self, filters: Optional[Dict[str, Any]] = None) -> int:
        """
        Count records with optional filters.

        Args:
            filters: Dictionary of field: value filters

        Returns:
            Count of matching records
        """
        query = select(func.count()).select_from(self.model)
        if filters:
            query = self._apply_filters(query, filters)
        result = await self.session.execute(query)
        return result.scalar()

    def _apply_filters(self, query, filters: Dict[str, Any]):
        """
        Apply WHERE clauses from filter dictionary.

        Args:
            query: SQLAlchemy query object
            filters: Dictionary of field: value filters

        Returns:
            Modified query with filters applied
        """
        for field, value in filters.items():
            if hasattr(self.model, field):
                query = query.where(getattr(self.model, field) == value)
        return query

    def _apply_ordering(self, query, order_by: str, desc: bool = False):
        """
        Apply ORDER BY clause.

        Args:
            query: SQLAlchemy query object
            order_by: Field name to order by
            desc: If True, order descending

        Returns:
            Modified query with ordering applied
        """
        if hasattr(self.model, order_by):
            field = getattr(self.model, order_by)
            if desc:
                query = query.order_by(field.desc())
            else:
                query = query.order_by(field)
        return query
