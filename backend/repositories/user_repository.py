"""
UserRepository for User-specific database operations.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, update, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.models import User, Role, UserRole
from backend.models.enums import UserRoleEnum
from backend.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User model with user-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID with eagerly loaded roles."""
        result = await self.session.execute(
            select(User)
            .options(joinedload(User.roles))
            .where(User.id == user_id)
        )
        return result.unique().scalar_one_or_none()

    async def get_by_username(self, username: str) -> Optional[User]:
        """Find user by username with eagerly loaded roles."""
        result = await self.session.execute(
            select(User)
            .options(joinedload(User.roles))
            .where(User.username == username)
        )
        return result.unique().scalar_one_or_none()

    async def get_by_email(self, email: str) -> Optional[User]:
        """Find user by email."""
        result = await self.session.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def get_by_external_id(
        self, external_id: str, auth_provider: str
    ) -> Optional[User]:
        """Find user by SSO external ID and provider."""
        result = await self.session.execute(
            select(User).where(
                User.external_id == external_id,
                User.auth_provider == auth_provider
            )
        )
        return result.scalar_one_or_none()

    async def get_with_roles(self, user_id: UUID) -> Optional[User]:
        """Get user with eagerly loaded roles."""
        result = await self.session.execute(
            select(User)
            .options(joinedload(User.roles))
            .where(User.id == user_id)
        )
        return result.unique().scalar_one_or_none()

    async def search_users(
        self, query: str, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """Search users by username, email, or full_name."""
        search_pattern = f"%{query}%"
        result = await self.session.execute(
            select(User).where(
                or_(
                    User.username.ilike(search_pattern),
                    User.email.ilike(search_pattern),
                    User.full_name.ilike(search_pattern)
                )
            ).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all active users."""
        result = await self.session.execute(
            select(User).where(User.is_active == True).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def update_last_login(self, user_id: UUID) -> None:
        """Update last_login timestamp to current time."""
        await self.session.execute(
            update(User)
            .where(User.id == user_id)
            .values(last_login=datetime.utcnow())
        )
        await self.session.flush()

    async def get_users_by_role(
        self, role_name: UserRoleEnum, skip: int = 0, limit: int = 100
    ) -> List[User]:
        """Get all users with specific role."""
        result = await self.session.execute(
            select(User)
            .join(UserRole, User.id == UserRole.user_id)
            .join(Role, UserRole.role_id == Role.id)
            .where(Role.name == role_name)
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def add_role(self, user_id: UUID, role_id: UUID) -> None:
        """Add a role to a user."""
        # Check if user-role relationship already exists
        existing = await self.session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id
            )
        )
        if existing.scalar_one_or_none():
            return  # Already exists

        # Create new user-role relationship
        user_role = UserRole(user_id=user_id, role_id=role_id)
        self.session.add(user_role)
        await self.session.flush()

    async def remove_role(self, user_id: UUID, role_id: UUID) -> None:
        """Remove a role from a user."""
        await self.session.execute(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id
            ).delete()
        )
        await self.session.flush()
