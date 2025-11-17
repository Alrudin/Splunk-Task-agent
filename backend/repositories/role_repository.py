"""
RoleRepository for Role-specific database operations.
"""
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from backend.models import Role, User, UserRole
from backend.models.enums import UserRoleEnum
from backend.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    """Repository for Role model with role-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, Role)

    async def get_by_name(self, name: UserRoleEnum) -> Optional[Role]:
        """Find role by name enum value."""
        result = await self.session.execute(
            select(Role).where(Role.name == name)
        )
        return result.scalar_one_or_none()

    async def get_with_users(self, role_id: UUID) -> Optional[Role]:
        """Get role with eagerly loaded users."""
        result = await self.session.execute(
            select(Role)
            .options(joinedload(Role.users))
            .where(Role.id == role_id)
        )
        return result.unique().scalar_one_or_none()

    async def assign_role_to_user(
        self, user_id: UUID, role_id: UUID, assigned_by: Optional[UUID] = None
    ) -> UserRole:
        """Create UserRole association."""
        user_role = UserRole(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
            assigned_at=datetime.utcnow()
        )
        self.session.add(user_role)
        await self.session.flush()
        await self.session.refresh(user_role)
        return user_role

    async def remove_role_from_user(self, user_id: UUID, role_id: UUID) -> bool:
        """Delete UserRole association."""
        result = await self.session.execute(
            delete(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role_id
            )
        )
        await self.session.flush()
        return result.rowcount > 0

    async def get_user_roles(self, user_id: UUID) -> List[Role]:
        """Get all roles for a user."""
        result = await self.session.execute(
            select(Role)
            .join(UserRole, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id)
        )
        return list(result.scalars().all())

    async def ensure_default_roles(self) -> None:
        """
        Create default roles if they don't exist.

        This should be called during application initialization.
        """
        default_roles = [
            {
                "name": UserRoleEnum.REQUESTOR,
                "description": "Can submit TA generation requests and upload log samples",
                "permissions": {"can_create_request": True, "can_upload_samples": True}
            },
            {
                "name": UserRoleEnum.APPROVER,
                "description": "Can approve or reject TA generation requests",
                "permissions": {"can_approve_request": True, "can_reject_request": True}
            },
            {
                "name": UserRoleEnum.ADMIN,
                "description": "Full system access including user and configuration management",
                "permissions": {"full_access": True}
            },
            {
                "name": UserRoleEnum.KNOWLEDGE_MANAGER,
                "description": "Can upload and manage knowledge base documents",
                "permissions": {"can_upload_knowledge": True, "can_manage_knowledge": True}
            }
        ]

        for role_data in default_roles:
            existing = await self.get_by_name(role_data["name"])
            if not existing:
                role = Role(**role_data)
                self.session.add(role)

        await self.session.flush()
