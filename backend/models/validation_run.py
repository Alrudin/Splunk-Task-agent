"""
ValidationRun model for Splunk sandbox validation results.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.models.enums import ValidationStatus


class ValidationRun(Base, TimestampMixin):
    """
    ValidationRun model for Splunk sandbox validation results.

    Tracks validation runs in ephemeral Splunk containers, including results,
    debug bundles, and timing information.
    """
    __tablename__ = "validation_runs"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign keys
    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    ta_revision_id: Mapped[UUID] = mapped_column(
        ForeignKey("ta_revisions.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Validation status
    status: Mapped[ValidationStatus] = mapped_column(
        Enum(ValidationStatus, native_enum=False, length=50),
        nullable=False,
        default=ValidationStatus.QUEUED,
        index=True
    )

    # Results
    results_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Field coverage, errors, search results

    # Debug bundle
    debug_bundle_key: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)  # S3 key for debug .zip
    debug_bundle_bucket: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Container tracking
    splunk_container_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)  # K8s Job name or Docker container ID

    # Logs and errors
    validation_logs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # Captured Splunk logs
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Computed from started_at/completed_at

    # Relationships
    request: Mapped["Request"] = relationship(
        "Request",
        back_populates="validation_runs",
        lazy="joined"
    )

    ta_revision: Mapped["TARevision"] = relationship(
        "TARevision",
        back_populates="validation_runs",
        lazy="joined"
    )

    # Indexes
    __table_args__ = (
        Index("ix_validation_runs_request_id_created_at", "request_id", "created_at"),
        Index("ix_validation_runs_started_at", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<ValidationRun(id={self.id}, ta_revision_id={self.ta_revision_id}, status={self.status.value})>"
