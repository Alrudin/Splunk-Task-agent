"""
Knowledge Management Service
Handles document upload, parsing, and indexing for RAG system
"""

import uuid
import tarfile
from io import BytesIO
from typing import Optional, Dict, Any, List
from uuid import UUID

import PyPDF2
from fastapi import UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.integrations.pinecone_client import PineconeClient
from backend.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from backend.models.knowledge_document import KnowledgeDocument
from backend.core.exceptions import NotFoundError, StorageError, ValidationError

logger = get_logger(__name__)


class KnowledgeService:
    """Service for managing knowledge document lifecycle"""

    def __init__(
        self,
        knowledge_document_repository: KnowledgeDocumentRepository,
        storage_client: ObjectStorageClient,
        pinecone_client: PineconeClient
    ):
        """Initialize KnowledgeService with dependencies

        Args:
            knowledge_document_repository: Repository for knowledge document operations
            storage_client: Client for object storage operations
            pinecone_client: Client for vector database operations
        """
        self.repository = knowledge_document_repository
        self.storage_client = storage_client
        self.pinecone_client = pinecone_client
        self.logger = logger.bind(service="KnowledgeService")

    def parse_document(self, content: bytes, document_type: str, filename: str) -> str:
        """Parse document content and extract text

        Args:
            content: Raw file content as bytes
            document_type: Type of document (pdf/markdown/ta_archive)
            filename: Original filename for context

        Returns:
            Extracted text string

        Raises:
            ValidationError: If document parsing fails
        """
        correlation_id = str(uuid.uuid4())
        self.logger.info(
            "Parsing document",
            document_type=document_type,
            filename=filename,
            size=len(content),
            correlation_id=correlation_id
        )

        try:
            if document_type == "pdf":
                return self._parse_pdf(content)
            elif document_type == "markdown":
                return self._parse_markdown(content)
            elif document_type == "ta_archive":
                return self._parse_ta_archive(content)
            else:
                raise ValidationError(f"Unsupported document type: {document_type}")

        except Exception as e:
            self.logger.error(
                "Document parsing failed",
                document_type=document_type,
                filename=filename,
                error=str(e),
                correlation_id=correlation_id
            )
            raise ValidationError(f"Failed to parse {document_type} document: {str(e)}")

    def _parse_pdf(self, content: bytes) -> str:
        """Extract text from PDF using PyPDF2

        Args:
            content: PDF file content

        Returns:
            Extracted text from all pages
        """
        try:
            pdf_file = BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)

            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                self.logger.warning("Encountered encrypted PDF, attempting to decrypt with empty password")
                if not pdf_reader.decrypt(""):
                    raise ValidationError("Cannot decrypt password-protected PDF")

            # Extract text from all pages
            text_parts = []
            for page_num, page in enumerate(pdf_reader.pages, 1):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                except Exception as e:
                    self.logger.warning(f"Failed to extract text from page {page_num}: {e}")
                    continue

            if not text_parts:
                raise ValidationError("No text could be extracted from PDF")

            return "\n".join(text_parts)

        except PyPDF2.errors.PdfReadError as e:
            raise ValidationError(f"Invalid PDF file: {str(e)}")

    def _parse_markdown(self, content: bytes) -> str:
        """Extract text from Markdown file

        Args:
            content: Markdown file content

        Returns:
            Decoded text content
        """
        try:
            return content.decode('utf-8')
        except UnicodeDecodeError as e:
            raise ValidationError(f"Invalid Markdown file encoding: {str(e)}")

    def _parse_ta_archive(self, content: bytes) -> str:
        """Extract relevant text from TA archive

        Args:
            content: TA archive (.tgz) content

        Returns:
            Concatenated text from conf files and README
        """
        text_parts = []
        relevant_files = ['inputs.conf', 'props.conf', 'transforms.conf']

        try:
            archive = tarfile.open(fileobj=BytesIO(content), mode='r:gz')

            for member in archive.getmembers():
                if member.isfile():
                    filename = member.name.lower()

                    # Check if it's a relevant conf file or README
                    if any(filename.endswith(conf) for conf in relevant_files) or 'readme' in filename:
                        try:
                            file_obj = archive.extractfile(member)
                            if file_obj:
                                file_content = file_obj.read().decode('utf-8', errors='ignore')
                                text_parts.append(f"=== {member.name} ===\n{file_content}\n")
                        except Exception as e:
                            self.logger.warning(f"Failed to extract {member.name}: {e}")
                            continue

            archive.close()

            if not text_parts:
                raise ValidationError("No relevant files found in TA archive")

            return "\n".join(text_parts)

        except tarfile.TarError as e:
            raise ValidationError(f"Invalid TA archive: {str(e)}")

    async def upload_document(
        self,
        file: UploadFile,
        title: str,
        description: Optional[str],
        document_type: str,
        uploaded_by: UUID,
        extra_metadata: Optional[Dict[str, Any]] = None
    ) -> KnowledgeDocument:
        """Upload a knowledge document to storage and create DB record

        Args:
            file: Uploaded file from FastAPI
            title: Document title
            description: Optional description
            document_type: Type of document (pdf/markdown/ta_archive)
            uploaded_by: User ID who uploaded the document
            extra_metadata: Optional additional metadata

        Returns:
            Created KnowledgeDocument record

        Raises:
            ValidationError: If file validation fails
            StorageError: If storage operations fail
        """
        correlation_id = str(uuid.uuid4())
        self.logger.info(
            "Uploading knowledge document",
            title=title,
            document_type=document_type,
            filename=file.filename,
            uploaded_by=str(uploaded_by),
            correlation_id=correlation_id
        )

        # Validate file size
        file_content = await file.read()
        file_size = len(file_content)
        max_size = settings.max_sample_size_mb * 1024 * 1024

        if file_size > max_size:
            raise ValidationError(f"File size {file_size} bytes exceeds maximum {max_size} bytes")

        # Generate unique storage key
        storage_key = f"knowledge/{document_type}/{uuid.uuid4()}/{file.filename}"
        bucket = settings.minio_bucket_knowledge

        try:
            # Stream upload to MinIO
            file_stream = BytesIO(file_content)
            upload_result = await self.storage_client.upload_file_async(
                file_stream,  # First positional argument
                bucket=bucket,
                key=storage_key,
                content_type=file.content_type or 'application/octet-stream'
            )

            # Use the size from upload result for consistency
            actual_file_size = upload_result.get('size', file_size)

            # Create database record
            document = await self.repository.create_knowledge_document(
                title=title,
                description=description,
                document_type=document_type,
                storage_key=storage_key,
                storage_bucket=bucket,
                file_size=actual_file_size,
                uploaded_by=uploaded_by,
                extra_metadata=extra_metadata,
                pinecone_indexed=False
            )

            self.logger.info(
                "Knowledge document uploaded successfully",
                document_id=str(document.id),
                storage_key=storage_key,
                correlation_id=correlation_id
            )

            return document

        except Exception as e:
            # Clean up storage on DB failure
            self.logger.error(
                "Failed to upload knowledge document, cleaning up",
                error=str(e),
                correlation_id=correlation_id
            )

            try:
                await self.storage_client.delete_file_async(bucket, storage_key)
            except Exception as cleanup_error:
                self.logger.warning(f"Failed to cleanup storage after error: {cleanup_error}")

            raise StorageError(f"Failed to upload document: {str(e)}")

    async def index_document_async(self, document_id: UUID) -> KnowledgeDocument:
        """Index a knowledge document in Pinecone

        Args:
            document_id: ID of document to index

        Returns:
            Updated KnowledgeDocument with indexing status

        Raises:
            NotFoundError: If document not found
            StorageError: If storage operations fail
        """
        correlation_id = str(uuid.uuid4())
        self.logger.info(
            "Starting document indexing",
            document_id=str(document_id),
            correlation_id=correlation_id
        )

        # Retrieve document from repository
        document = await self.repository.get_by_id(document_id)
        if not document:
            raise NotFoundError(f"Knowledge document {document_id} not found")

        try:
            # Download file from storage
            file_stream = await self.storage_client.download_file_async(
                bucket_name=document.storage_bucket,
                object_name=document.storage_key
            )

            # Accumulate chunks into bytes
            file_content = b""
            async for chunk in file_stream:
                file_content += chunk

            # Parse document
            parsed_text = self.parse_document(
                content=file_content,
                document_type=document.document_type,
                filename=document.storage_key.split('/')[-1]
            )

            # Determine target Pinecone index
            if document.document_type in ['pdf', 'markdown']:
                index_name = settings.pinecone_index_docs
            elif document.document_type == 'ta_archive':
                index_name = settings.pinecone_index_tas
            else:
                raise ValidationError(f"Unknown document type for indexing: {document.document_type}")

            # Ensure index exists before upsert
            await self.pinecone_client.ensure_index_exists(index_name=index_name)

            # Prepare document for Pinecone
            pinecone_document = {
                'id': str(document_id),
                'text': parsed_text,
                'metadata': {
                    'title': document.title,
                    'document_type': document.document_type,
                    'uploaded_at': document.created_at.isoformat(),
                    'parent_doc_id': str(document_id),
                    **(document.extra_metadata or {})
                }
            }

            # Index in Pinecone
            result = await self.pinecone_client.upsert_documents(
                index_name=index_name,
                documents=[pinecone_document]
            )

            # Extract vector count from result
            vector_count = result.get('upserted_count', 0)

            # Update document as indexed
            document = await self.repository.mark_as_indexed(
                document_id=document_id,
                index_name=index_name,
                embedding_count=vector_count
            )

            self.logger.info(
                "Document indexed successfully",
                document_id=str(document_id),
                index_name=index_name,
                vector_count=vector_count,
                correlation_id=correlation_id
            )

            return document

        except Exception as e:
            self.logger.error(
                "Failed to index document",
                document_id=str(document_id),
                error=str(e),
                correlation_id=correlation_id
            )
            raise

    async def list_documents(
        self,
        skip: int = 0,
        limit: int = 50,
        document_type: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> List[KnowledgeDocument]:
        """List knowledge documents with optional filtering

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            document_type: Optional filter by document type
            search_query: Optional search query for title/description

        Returns:
            List of KnowledgeDocument records
        """
        if search_query:
            return await self.repository.search_documents(
                search_query=search_query,
                skip=skip,
                limit=limit
            )
        elif document_type:
            return await self.repository.get_by_type(
                document_type=document_type,
                skip=skip,
                limit=limit
            )
        else:
            return await self.repository.get_active_documents(
                skip=skip,
                limit=limit
            )

    async def get_document_by_id(self, document_id: UUID) -> KnowledgeDocument:
        """Get a specific knowledge document by ID

        Args:
            document_id: ID of document to retrieve

        Returns:
            KnowledgeDocument record

        Raises:
            NotFoundError: If document not found
        """
        document = await self.repository.get_by_id(document_id)
        if not document:
            raise NotFoundError(f"Knowledge document {document_id} not found")
        return document

    async def delete_document(self, document_id: UUID, user_id: UUID) -> KnowledgeDocument:
        """Soft delete a knowledge document

        Args:
            document_id: ID of document to delete
            user_id: ID of user performing deletion (for audit)

        Returns:
            Deactivated KnowledgeDocument record

        Raises:
            NotFoundError: If document not found or already inactive
        """
        self.logger.info(
            "Deleting knowledge document",
            document_id=str(document_id),
            user_id=str(user_id)
        )

        # Retrieve and verify document
        document = await self.get_document_by_id(document_id)
        if not document.is_active:
            raise NotFoundError(f"Knowledge document {document_id} is already deleted")

        # Soft delete in database
        document = await self.repository.deactivate_document(document_id)

        # Optionally delete from Pinecone
        try:
            if document.pinecone_indexed and document.pinecone_index_name:
                await self.pinecone_client.delete_by_filter(
                    index_name=document.pinecone_index_name,
                    filter={'parent_doc_id': str(document_id)}
                )
                self.logger.info(f"Deleted vectors from Pinecone for document {document_id}")
        except Exception as e:
            self.logger.warning(f"Failed to delete vectors from Pinecone: {e}")

        return document

    async def get_statistics(self) -> Dict[str, Any]:
        """Get knowledge document statistics

        Returns:
            Dictionary with document statistics
        """
        return await self.repository.get_statistics()