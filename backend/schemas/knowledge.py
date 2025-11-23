"""
Pydantic schemas for knowledge document API request/response validation
"""

from datetime import datetime
from typing import Optional, Dict, Any, List, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class KnowledgeDocumentUploadRequest(BaseModel):
    """Request schema for uploading a knowledge document"""

    title: str = Field(..., max_length=500, description="Document title")
    description: Optional[str] = Field(None, description="Document description")
    document_type: Literal["pdf", "markdown", "ta_archive"] = Field(
        ...,
        description="Type of document being uploaded"
    )
    extra_metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata for the document"
    )

    @field_validator("title")
    @classmethod
    def validate_title(cls, v: str) -> str:
        """Ensure title is not empty or whitespace"""
        if not v or not v.strip():
            raise ValueError("Title must not be empty or whitespace")
        return v.strip()

    @field_validator("document_type")
    @classmethod
    def validate_document_type(cls, v: str) -> str:
        """Ensure document type is valid"""
        allowed_types = ["pdf", "markdown", "ta_archive"]
        if v not in allowed_types:
            raise ValueError(f"Document type must be one of: {', '.join(allowed_types)}")
        return v


class KnowledgeDocumentResponse(BaseModel):
    """Response schema for a knowledge document"""

    id: UUID
    title: str
    description: Optional[str]
    document_type: str
    storage_key: str
    storage_bucket: str
    file_size: Optional[int]
    uploaded_by: UUID
    uploaded_by_username: str = Field(default="", description="Username of uploader")
    pinecone_indexed: bool
    pinecone_index_name: Optional[str]
    embedding_count: Optional[int]
    extra_metadata: Optional[Dict[str, Any]]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

    @model_validator(mode='before')
    @classmethod
    def extract_username(cls, values):
        """Extract username from uploaded_by_user relationship"""
        if hasattr(values, 'uploaded_by_user') and values.uploaded_by_user:
            values.uploaded_by_username = values.uploaded_by_user.username
        elif isinstance(values, dict) and 'uploaded_by_user' in values and values['uploaded_by_user']:
            values['uploaded_by_username'] = values['uploaded_by_user'].username
        return values


class KnowledgeDocumentListResponse(BaseModel):
    """Response schema for paginated list of knowledge documents"""

    documents: List[KnowledgeDocumentResponse]
    total: int
    skip: int
    limit: int


class KnowledgeDocumentStatisticsResponse(BaseModel):
    """Response schema for knowledge document statistics"""

    by_type: Dict[str, int] = Field(
        ...,
        description="Document counts by type"
    )
    indexing_status: Dict[str, int] = Field(
        ...,
        description="Counts of indexed vs unindexed documents",
        example={"indexed": 10, "unindexed": 5}
    )


class KnowledgeDocumentSearchRequest(BaseModel):
    """Request schema for searching knowledge documents"""

    query: str = Field(..., min_length=1, description="Search query")
    document_type: Optional[str] = Field(None, description="Filter by document type")
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(50, ge=1, le=100, description="Maximum number of records to return")

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Ensure query is not empty"""
        if not v or not v.strip():
            raise ValueError("Search query must not be empty")
        return v.strip()