"""
AuditLog model for tracking all human actions.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, func, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base
from backend.models.enums import AuditAction


class AuditLog(Base):
    """
    AuditLog model for audit trail.

    Tracks all human actions for compliance and security.
    This table is append-only (no updates/deletes) for audit integrity.
    """
    __tablename__ = "audit_logs"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # User tracking
    user_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )  # Nullable for system actions

    # Action details
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, native_enum=False, length=50),
        nullable=False,
        index=True
    )
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., 'request', 'ta_revision'
    entity_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, index=True)  # ID of affected entity

    # Additional details
    details: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Action-specific details

    # Request context
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Correlation
    correlation_id: Mapped[Optional[UUID]] = mapped_column(nullable=True, index=True)  # For tracing related actions

    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="audit_logs",
        lazy="joined"
    )

    # Indexes
    __table_args__ = (
        Index("ix_audit_logs_user_id_timestamp", "user_id", "timestamp"),
        Index("ix_audit_logs_entity_type_entity_id", "entity_type", "entity_id"),
        Index("ix_audit_logs_correlation_id", "correlation_id"),
    )

    def __repr__(self) -> str:
        return f"<AuditLog(id={self.id}, action={self.action.value}, entity_type={self.entity_type}, timestamp={self.timestamp})>"
