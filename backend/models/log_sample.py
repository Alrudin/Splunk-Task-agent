"""
LogSample model for uploaded log samples.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class LogSample(Base, TimestampMixin):
    """
    LogSample model for uploaded log files.

    Tracks log samples uploaded by requestors, stored in S3-compatible storage.
    Supports retention policies and soft deletion.
    """
    __tablename__ = "log_samples"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign key
    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # File metadata
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(BigInteger, nullable=False)  # bytes
    mime_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Storage fields
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)  # S3/MinIO object key
    storage_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256 hash

    # Preview and retention
    sample_preview: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # First few lines
    retention_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Soft delete

    # Relationships
    request: Mapped["Request"] = relationship(
        "Request",
        back_populates="log_samples",
        lazy="joined"
    )

    # Indexes
    __table_args__ = (
        Index("ix_log_samples_retention_until", "retention_until"),
    )

    def __repr__(self) -> str:
        return f"<LogSample(id={self.id}, filename={self.filename}, request_id={self.request_id})>"
