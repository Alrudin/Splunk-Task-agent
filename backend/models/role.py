"""
Role model for role-based access control (RBAC).
"""
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import Enum, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.models.enums import UserRoleEnum


class Role(Base, TimestampMixin):
    """
    Role model for RBAC.

    Predefined roles: REQUESTOR, APPROVER, ADMIN, KNOWLEDGE_MANAGER.
    """
    __tablename__ = "roles"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Role fields
    name: Mapped[UserRoleEnum] = mapped_column(
        Enum(UserRoleEnum, native_enum=False, length=50),
        unique=True,
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    permissions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # For future fine-grained permissions

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User",
        secondary="user_roles",
        back_populates="roles",
        lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<Role(id={self.id}, name={self.name.value})>"
