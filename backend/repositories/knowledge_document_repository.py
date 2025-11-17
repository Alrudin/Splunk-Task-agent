"""
KnowledgeDocumentRepository for KnowledgeDocument-specific database operations.
"""
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import KnowledgeDocument
from backend.repositories.base import BaseRepository


class KnowledgeDocumentRepository(BaseRepository[KnowledgeDocument]):
    """Repository for KnowledgeDocument model with knowledge document-specific queries."""

    def __init__(self, session: AsyncSession):
        super().__init__(session, KnowledgeDocument)

    async def get_by_type(
        self, document_type: str, skip: int = 0, limit: int = 100
    ) -> List[KnowledgeDocument]:
        """Get documents by type."""
        result = await self.session.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.document_type == document_type)
            .order_by(KnowledgeDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_uploader(
        self, user_id: UUID, skip: int = 0, limit: int = 100
    ) -> List[KnowledgeDocument]:
        """Get documents uploaded by specific user."""
        result = await self.session.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.uploaded_by == user_id)
            .order_by(KnowledgeDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_active_documents(
        self, skip: int = 0, limit: int = 100
    ) -> List[KnowledgeDocument]:
        """Get documents where is_active=True."""
        result = await self.session.execute(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.is_active == True)
            .order_by(KnowledgeDocument.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_unindexed_documents(self) -> List[KnowledgeDocument]:
        """Get documents where pinecone_indexed=False for processing queue."""
        result = await self.session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.pinecone_indexed == False,
                KnowledgeDocument.is_active == True
            )
        )
        return list(result.scalars().all())

    async def mark_as_indexed(
        self, document_id: UUID, index_name: str, embedding_count: int
    ) -> Optional[KnowledgeDocument]:
        """Set pinecone_indexed=True, pinecone_index_name, embedding_count."""
        await self.session.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(
                pinecone_indexed=True,
                pinecone_index_name=index_name,
                embedding_count=embedding_count,
                updated_at=func.now()
            )
        )
        await self.session.flush()
        return await self.get_by_id(document_id)

    async def search_documents(
        self,
        query: str,
        document_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[KnowledgeDocument]:
        """Search by title/description."""
        search_pattern = f"%{query}%"
        stmt = select(KnowledgeDocument).where(
            or_(
                KnowledgeDocument.title.ilike(search_pattern),
                KnowledgeDocument.description.ilike(search_pattern)
            ),
            KnowledgeDocument.is_active == True
        )

        if document_type:
            stmt = stmt.where(KnowledgeDocument.document_type == document_type)

        stmt = stmt.order_by(KnowledgeDocument.created_at.desc()).offset(skip).limit(limit)

        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def deactivate_document(self, document_id: UUID) -> Optional[KnowledgeDocument]:
        """Set is_active=False (soft delete)."""
        await self.session.execute(
            update(KnowledgeDocument)
            .where(KnowledgeDocument.id == document_id)
            .values(is_active=False, updated_at=func.now())
        )
        await self.session.flush()
        return await self.get_by_id(document_id)

    async def get_statistics(self) -> Dict[str, Dict[str, int]]:
        """Get document counts by type and indexing status."""
        # Get counts by type
        type_result = await self.session.execute(
            select(
                KnowledgeDocument.document_type,
                func.count(KnowledgeDocument.id)
            )
            .where(KnowledgeDocument.is_active == True)
            .group_by(KnowledgeDocument.document_type)
        )
        type_stats = {row[0]: row[1] for row in type_result.all()}

        # Get counts by indexing status
        indexed_result = await self.session.execute(
            select(func.count())
            .select_from(KnowledgeDocument)
            .where(
                KnowledgeDocument.is_active == True,
                KnowledgeDocument.pinecone_indexed == True
            )
        )
        indexed_count = indexed_result.scalar()

        unindexed_result = await self.session.execute(
            select(func.count())
            .select_from(KnowledgeDocument)
            .where(
                KnowledgeDocument.is_active == True,
                KnowledgeDocument.pinecone_indexed == False
            )
        )
        unindexed_count = unindexed_result.scalar()

        return {
            "by_type": type_stats,
            "indexing_status": {
                "indexed": indexed_count,
                "unindexed": unindexed_count
            }
        }

    async def get_by_storage_key(self, storage_key: str) -> Optional[KnowledgeDocument]:
        """Find document by storage key."""
        result = await self.session.execute(
            select(KnowledgeDocument).where(
                KnowledgeDocument.storage_key == storage_key
            )
        )
        return result.scalar_one_or_none()
