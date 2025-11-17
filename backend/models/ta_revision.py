"""
TARevision model for TA package versions.
"""
from typing import Optional, List, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, String, UniqueConstraint, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin
from backend.models.enums import TARevisionType


class TARevision(Base, TimestampMixin):
    """
    TARevision model for TA package versions.

    Each generation creates a new version (TA-<source>-v1, TA-<source>-v2, etc.).
    Supports both AI-generated and manual override versions.
    """
    __tablename__ = "ta_revisions"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Foreign key
    request_id: Mapped[UUID] = mapped_column(
        ForeignKey("requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Version fields
    version: Mapped[int] = mapped_column(Integer, nullable=False)  # 1, 2, 3, etc.

    # Storage fields
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)  # S3 key for .tgz bundle
    storage_bucket: Mapped[str] = mapped_column(String(100), nullable=False)

    # Generation tracking
    generated_by: Mapped[TARevisionType] = mapped_column(
        Enum(TARevisionType, native_enum=False, length=50),
        nullable=False
    )
    generated_by_user: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id"),
        nullable=True
    )  # For manual overrides

    # File metadata
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)  # bytes
    checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # SHA-256 hash

    # Configuration summary
    config_summary: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Summary of inputs.conf, props.conf, transforms.conf
    generation_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # LLM model, prompt version, Pinecone context

    # Relationships
    request: Mapped["Request"] = relationship(
        "Request",
        back_populates="ta_revisions",
        lazy="joined"
    )

    uploaded_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[generated_by_user],
        lazy="joined"
    )

    validation_runs: Mapped[List["ValidationRun"]] = relationship(
        "ValidationRun",
        back_populates="ta_revision",
        cascade="all, delete-orphan",
        lazy="select"
    )

    # Constraints and indexes
    __table_args__ = (
        UniqueConstraint("request_id", "version", name="uq_request_version"),
        Index("ix_ta_revisions_request_id_version", "request_id", "version"),
        Index("ix_ta_revisions_generated_by", "generated_by"),
    )

    def __repr__(self) -> str:
        return f"<TARevision(id={self.id}, request_id={self.request_id}, version={self.version}, type={self.generated_by.value})>"
