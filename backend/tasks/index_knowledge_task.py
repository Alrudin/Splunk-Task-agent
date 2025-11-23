"""
Celery task for background knowledge document indexing
"""

import uuid
from typing import Optional
from uuid import UUID

from celery import Task
from celery.utils.log import get_task_logger

from backend.database import get_async_session_context
from backend.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from backend.integrations.object_storage_client import get_storage_client
from backend.integrations.pinecone_client import get_pinecone_client
from backend.services.knowledge_service import KnowledgeService
from backend.tasks.celery_app import celery_app
from backend.core.exceptions import PineconeClientError

logger = get_task_logger(__name__)


@celery_app.task(
    name="tasks.index_knowledge_document",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="knowledge_indexing"
)
async def index_knowledge_document_task(
    self: Task,
    document_id: str
) -> Optional[dict]:
    """Index a knowledge document in Pinecone vector database

    Args:
        self: Celery task instance (for retry mechanism)
        document_id: ID of the knowledge document to index

    Returns:
        Dictionary with indexing results or None if failed

    Raises:
        PineconeClientError: If Pinecone operations fail (will retry)
    """
    correlation_id = str(uuid.uuid4())
    task_id = self.request.id

    logger.info(
        "Starting knowledge document indexing task",
        task_id=task_id,
        document_id=document_id,
        correlation_id=correlation_id
    )

    try:
        # Convert string ID to UUID
        doc_uuid = UUID(document_id)

        # Create async database session
        async with get_async_session_context() as db_session:
            # Initialize repositories and clients
            knowledge_repository = KnowledgeDocumentRepository(db_session)
            storage_client = get_storage_client()
            pinecone_client = get_pinecone_client()

            # Create knowledge service
            knowledge_service = KnowledgeService(
                knowledge_document_repository=knowledge_repository,
                storage_client=storage_client,
                pinecone_client=pinecone_client
            )

            # Perform indexing
            document = await knowledge_service.index_document_async(doc_uuid)

            # Commit the session
            await db_session.commit()

            logger.info(
                "Knowledge document indexed successfully",
                task_id=task_id,
                document_id=document_id,
                vector_count=document.embedding_count,
                index_name=document.pinecone_index_name,
                correlation_id=correlation_id
            )

            return {
                "document_id": str(document.id),
                "title": document.title,
                "indexed": document.pinecone_indexed,
                "index_name": document.pinecone_index_name,
                "vector_count": document.embedding_count
            }

    except PineconeClientError as e:
        logger.error(
            "Pinecone error during indexing, will retry",
            task_id=task_id,
            document_id=document_id,
            error=str(e),
            retry_count=self.request.retries,
            correlation_id=correlation_id
        )

        # Retry with exponential backoff
        retry_delay = 60 * (2 ** self.request.retries)  # 60s, 120s, 240s
        raise self.retry(exc=e, countdown=retry_delay)

    except Exception as e:
        logger.error(
            "Failed to index knowledge document",
            task_id=task_id,
            document_id=document_id,
            error=str(e),
            correlation_id=correlation_id
        )

        # Log failure but don't retry for non-Pinecone errors
        # Could optionally update document with failed_reason if field exists
        try:
            async with get_async_session_context() as db_session:
                repository = KnowledgeDocumentRepository(db_session)
                document = await repository.get_by_id(UUID(document_id))
                if document:
                    # Log the failure (could add failed_reason field to model if needed)
                    logger.error(
                        "Marking document indexing as failed",
                        document_id=document_id,
                        document_title=document.title,
                        error=str(e)
                    )
                await db_session.commit()
        except Exception as log_error:
            logger.error(f"Failed to log indexing failure: {log_error}")

        return None