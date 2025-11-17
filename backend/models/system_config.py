"""
SystemConfig model for storing runtime configuration.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base


class SystemConfig(Base):
    """
    SystemConfig model for runtime configuration key-value pairs.

    Provides runtime configuration that can be modified via admin UI without
    redeploying. Environment variables serve as defaults, database values override.
    """
    __tablename__ = "system_config"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Configuration key-value
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # Stored as string, parsed by application
    value_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'string', 'integer', 'boolean', 'json', 'list'

    # Metadata
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_secret: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Mask in UI

    # Update tracking
    updated_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False
    )

    # Relationships
    updated_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[updated_by],
        lazy="joined"
    )

    # Indexes
    __table_args__ = (
        Index("ix_system_config_key", "key", unique=True),
        Index("ix_system_config_updated_at", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<SystemConfig(key={self.key}, value_type={self.value_type})>"
