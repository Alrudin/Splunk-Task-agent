"""
User model representing system users with authentication and profile information.
"""
from datetime import datetime
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    """
    User model for authentication and profile management.

    Supports multiple authentication providers: local, SAML, OAuth, OIDC.
    """
    __tablename__ = "users"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Authentication fields
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # For local auth only

    # Profile fields
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # SSO fields
    auth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # 'local', 'saml', 'oauth', 'oidc'
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, index=True)  # For SSO user mapping

    # Login tracking
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    roles: Mapped[List["Role"]] = relationship(
        "Role",
        secondary="user_roles",
        back_populates="users",
        lazy="selectin"
    )

    requests: Mapped[List["Request"]] = relationship(
        "Request",
        foreign_keys="[Request.created_by]",
        back_populates="created_by_user",
        lazy="select"
    )

    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="user",
        lazy="select"
    )

    # Indexes
    __table_args__ = (
        Index("ix_users_email_auth_provider", "email", "auth_provider"),
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, email={self.email})>"
