"""
Request model representing TA generation requests.
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.models.enums import RequestStatus


class Request(Base, TimestampMixin):
    """
    Request model for TA generation requests.

    Tracks the full lifecycle from submission through approval, generation,
    validation, and completion.
    """
    __tablename__ = "requests"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Request fields
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, native_enum=False, length=50),
        nullable=False,
        default=RequestStatus.NEW,
        index=True
    )
    source_system: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g., 'Apache', 'Cisco ASA'
    description: Mapped[str] = mapped_column(Text, nullable=False)
    cim_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Approval tracking
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Completion tracking
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Additional metadata (note: using 'extra_metadata' to avoid SQLAlchemy reserved word)
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)

    # Relationships
    created_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="requests",
        lazy="joined"
    )

    approved_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="joined"
    )

    log_samples: Mapped[List["LogSample"]] = relationship(
        "LogSample",
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="select"
    )

    ta_revisions: Mapped[List["TARevision"]] = relationship(
        "TARevision",
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="select"
    )

    validation_runs: Mapped[List["ValidationRun"]] = relationship(
        "ValidationRun",
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="select"
    )

    # Indexes
    __table_args__ = (
        Index("ix_requests_status_created_at", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Request(id={self.id}, source_system={self.source_system}, status={self.status.value})>"
