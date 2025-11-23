"""
FastAPI router for admin knowledge management endpoints
"""

import json
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile, HTTPException, Query, Path, Request, status
from backend.core.dependencies import (
    get_current_user,
    require_any_role,
    get_audit_service,
    get_storage_client,
    get_knowledge_service,
    get_db
)
from backend.models.enums import UserRoleEnum, AuditAction
from backend.models.user import User
from backend.schemas.knowledge import (
    KnowledgeDocumentResponse,
    KnowledgeDocumentListResponse,
    KnowledgeDocumentStatisticsResponse
)
from backend.services.audit import AuditService
from backend.services.knowledge_service import KnowledgeService
from backend.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from backend.integrations.object_storage_client import ObjectStorageClient
from sqlalchemy.ext.asyncio import AsyncSession
from backend.tasks.index_knowledge_task import index_knowledge_document_task
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.core.exceptions import NotFoundError, StorageError, ValidationError

logger = get_logger(__name__)

# Create router with prefix and tags
router = APIRouter(
    prefix="/admin/knowledge",
    tags=["Admin - Knowledge Management"]
)


@router.post("/upload", response_model=KnowledgeDocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_knowledge_document(
    request: Request,
    file: UploadFile = File(...),
    title: str = Form(..., max_length=500),
    description: Optional[str] = Form(None),
    document_type: str = Form(...),
    extra_metadata: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.KNOWLEDGE_MANAGER)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """Upload a new knowledge document

    Requires ADMIN or KNOWLEDGE_MANAGER role.

    Args:
        file: The document file to upload
        title: Document title
        description: Optional document description
        document_type: Type of document (pdf, markdown, ta_archive)
        extra_metadata: Optional JSON string with additional metadata

    Returns:
        The created knowledge document

    Raises:
        HTTPException: If validation fails or upload errors occur
    """
    logger.info(
        "Knowledge document upload requested",
        user_id=str(current_user.id),
        username=current_user.username,
        title=title,
        document_type=document_type,
        filename=file.filename
    )

    # Validate document type
    allowed_types = ["pdf", "markdown", "ta_archive"]
    if document_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type. Must be one of: {', '.join(allowed_types)}"
        )

    # Validate file extension matches document type
    filename_lower = file.filename.lower() if file.filename else ""

    if document_type == "pdf" and not filename_lower.endswith('.pdf'):
        raise HTTPException(
            status_code=400,
            detail="PDF document type requires .pdf file extension"
        )
    elif document_type == "markdown" and not (filename_lower.endswith('.md') or filename_lower.endswith('.markdown')):
        raise HTTPException(
            status_code=400,
            detail="Markdown document type requires .md or .markdown file extension"
        )
    elif document_type == "ta_archive" and not (filename_lower.endswith('.tgz') or filename_lower.endswith('.tar.gz')):
        raise HTTPException(
            status_code=400,
            detail="TA archive document type requires .tgz or .tar.gz file extension"
        )

    # Note: File size validation is handled by KnowledgeService.upload_document
    # which checks the actual byte length against MAX_SAMPLE_SIZE_MB

    # Parse extra metadata if provided
    parsed_metadata = None
    if extra_metadata:
        try:
            parsed_metadata = json.loads(extra_metadata)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid JSON in extra_metadata field"
            )

    try:
        # Upload document
        document = await knowledge_service.upload_document(
            file=file,
            title=title,
            description=description,
            document_type=document_type,
            uploaded_by=current_user.id,
            extra_metadata=parsed_metadata
        )

        # Enqueue background indexing task
        index_knowledge_document_task.delay(str(document.id))

        # Log audit event
        await audit_service.log_upload(
            user_id=current_user.id,
            resource_type="KnowledgeDocument",
            resource_id=document.id,
            details={
                "title": title,
                "document_type": document_type,
                "file_size": file.size,
                "filename": file.filename
            },
            request=request
        )

        logger.info(
            "Knowledge document uploaded successfully",
            document_id=str(document.id),
            user_id=str(current_user.id)
        )

        return KnowledgeDocumentResponse.model_validate(document)

    except ValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except StorageError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during upload: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during upload")


@router.get("/", response_model=KnowledgeDocumentListResponse)
async def list_knowledge_documents(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=100, description="Maximum number of records to return"),
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    search: Optional[str] = Query(None, description="Search in title and description"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.KNOWLEDGE_MANAGER)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    db: AsyncSession = Depends(get_db)
):
    """List knowledge documents with optional filtering

    Requires ADMIN or KNOWLEDGE_MANAGER role.

    Args:
        skip: Number of records to skip for pagination
        limit: Maximum number of records to return
        document_type: Optional filter by document type
        search: Optional search query for title/description

    Returns:
        Paginated list of knowledge documents
    """
    # Get documents
    documents = await knowledge_service.list_documents(
        skip=skip,
        limit=limit,
        document_type=document_type,
        search_query=search
    )

    # Get total count
    repository = KnowledgeDocumentRepository(db)
    if search:
        total = await repository.count_search_results(search)
    elif document_type:
        total = await repository.count_by_type(document_type)
    else:
        total = await repository.count_active()

    return KnowledgeDocumentListResponse(
        documents=[KnowledgeDocumentResponse.model_validate(doc) for doc in documents],
        total=total,
        skip=skip,
        limit=limit
    )


@router.get("/statistics", response_model=KnowledgeDocumentStatisticsResponse)
async def get_knowledge_statistics(
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.KNOWLEDGE_MANAGER)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """Get knowledge document statistics

    Requires ADMIN or KNOWLEDGE_MANAGER role.

    Returns:
        Statistics about knowledge documents
    """
    statistics = await knowledge_service.get_statistics()
    return KnowledgeDocumentStatisticsResponse(
        by_type=statistics.get("by_type", {}),
        indexing_status=statistics.get("indexing_status", {"indexed": 0, "unindexed": 0})
    )


@router.get("/{document_id}", response_model=KnowledgeDocumentResponse)
async def get_knowledge_document(
    document_id: UUID = Path(..., description="ID of the document to retrieve"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.KNOWLEDGE_MANAGER)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service)
):
    """Get a specific knowledge document by ID

    Requires ADMIN or KNOWLEDGE_MANAGER role.

    Args:
        document_id: ID of the document to retrieve

    Returns:
        The knowledge document

    Raises:
        HTTPException: If document not found
    """
    try:
        document = await knowledge_service.get_document_by_id(document_id)
        return KnowledgeDocumentResponse.model_validate(document)
    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Knowledge document {document_id} not found")


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_document(
    request: Request,
    document_id: UUID = Path(..., description="ID of the document to delete"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.KNOWLEDGE_MANAGER)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """Soft delete a knowledge document

    Requires ADMIN or KNOWLEDGE_MANAGER role.

    Args:
        document_id: ID of the document to delete

    Raises:
        HTTPException: If document not found
    """
    logger.info(
        "Knowledge document deletion requested",
        document_id=str(document_id),
        user_id=str(current_user.id),
        username=current_user.username
    )

    try:
        document = await knowledge_service.delete_document(document_id, current_user.id)

        # Log audit event
        await audit_service.log_action(
            user_id=current_user.id,
            action=AuditAction.DELETE,
            resource_type="KnowledgeDocument",
            resource_id=document_id,
            request=request
        )

        logger.info(
            "Knowledge document deleted successfully",
            document_id=str(document_id),
            user_id=str(current_user.id)
        )

        return None

    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Knowledge document {document_id} not found or already deleted")


@router.post("/{document_id}/reindex", status_code=status.HTTP_202_ACCEPTED)
async def reindex_knowledge_document(
    request: Request,
    document_id: UUID = Path(..., description="ID of the document to reindex"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.KNOWLEDGE_MANAGER)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    audit_service: AuditService = Depends(get_audit_service)
):
    """Trigger re-indexing for a knowledge document

    Requires ADMIN or KNOWLEDGE_MANAGER role.

    Args:
        document_id: ID of the document to reindex

    Returns:
        Message confirming reindexing was queued

    Raises:
        HTTPException: If document not found or inactive
    """
    logger.info(
        "Knowledge document reindex requested",
        document_id=str(document_id),
        user_id=str(current_user.id),
        username=current_user.username
    )

    try:
        # Verify document exists and is active
        document = await knowledge_service.get_document_by_id(document_id)
        if not document.is_active:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot reindex inactive document {document_id}"
            )

        # Enqueue reindexing task
        index_knowledge_document_task.delay(str(document_id))

        # Log audit event
        await audit_service.log_action(
            user_id=current_user.id,
            action=AuditAction.UPDATE,
            resource_type="KnowledgeDocument",
            resource_id=document_id,
            details={"action": "reindex_triggered"},
            request=request
        )

        logger.info(
            "Knowledge document reindexing queued",
            document_id=str(document_id),
            user_id=str(current_user.id)
        )

        return {
            "message": "Reindexing queued",
            "document_id": str(document_id)
        }

    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Knowledge document {document_id} not found")


@router.get("/{document_id}/download")
async def get_knowledge_document_download_url(
    request: Request,
    document_id: UUID = Path(..., description="ID of the document to download"),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_any_role(UserRoleEnum.ADMIN, UserRoleEnum.KNOWLEDGE_MANAGER)),
    knowledge_service: KnowledgeService = Depends(get_knowledge_service),
    storage_client: ObjectStorageClient = Depends(get_storage_client),
    audit_service: AuditService = Depends(get_audit_service)
):
    """Generate a presigned URL for document download

    Requires ADMIN or KNOWLEDGE_MANAGER role.

    Args:
        document_id: ID of the document to download

    Returns:
        Presigned download URL and expiration time

    Raises:
        HTTPException: If document not found
    """
    logger.info(
        "Knowledge document download requested",
        document_id=str(document_id),
        user_id=str(current_user.id),
        username=current_user.username
    )

    try:
        # Get document
        document = await knowledge_service.get_document_by_id(document_id)

        # Generate presigned URL
        url = await storage_client.generate_presigned_url(
            bucket_name=document.storage_bucket,
            object_name=document.storage_key,
            expires_in=3600  # 1 hour
        )

        # Log audit event
        await audit_service.log_download(
            user_id=current_user.id,
            resource_type="KnowledgeDocument",
            resource_id=document_id,
            details={"title": document.title},
            request=request
        )

        logger.info(
            "Knowledge document download URL generated",
            document_id=str(document_id),
            user_id=str(current_user.id)
        )

        return {
            "download_url": url,
            "expires_in": 3600
        }

    except NotFoundError:
        raise HTTPException(status_code=404, detail=f"Knowledge document {document_id} not found")