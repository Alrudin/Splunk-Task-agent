"""
KnowledgeDocument model for admin-uploaded knowledge base documents.
"""
from typing import Optional, Dict, Any
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, Boolean, ForeignKey, Index, Integer, String, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.models.base import Base, TimestampMixin


class KnowledgeDocument(Base, TimestampMixin):
    """
    KnowledgeDocument model for knowledge base documents.

    Stores documents uploaded by admins for RAG (Retrieval-Augmented Generation).
    Tracks Pinecone indexing status for vector embeddings.
    """
    __tablename__ = "knowledge_documents"

    # Primary key
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    # Document metadata
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    document_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # 'pdf', 'markdown', 'ta_archive', 'splunk_doc'

    # Storage fields
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False)  # S3 key
    storage_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)

    # Upload tracking
    uploaded_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    # Pinecone indexing
    pinecone_indexed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    pinecone_index_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Which Pinecone index
    embedding_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Number of chunks/embeddings

    # Additional metadata (note: using 'extra_metadata' to avoid SQLAlchemy reserved word)
    extra_metadata: Mapped[Optional[Dict[str, Any]]] = mapped_column("metadata", JSON, nullable=True)  # Tags, categories, source URL, etc.

    # Soft delete
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    uploaded_by_user: Mapped["User"] = relationship(
        "User",
        foreign_keys=[uploaded_by],
        lazy="joined"
    )

    # Indexes
    __table_args__ = (
        Index("ix_knowledge_documents_document_type", "document_type"),
        Index("ix_knowledge_documents_uploaded_by", "uploaded_by"),
        Index("ix_knowledge_documents_pinecone_indexed", "pinecone_indexed"),
        Index("ix_knowledge_documents_is_active", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeDocument(id={self.id}, title={self.title}, type={self.document_type})>"
