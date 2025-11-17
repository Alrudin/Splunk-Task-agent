"""
Request service for managing request lifecycle and sample uploads.

This service handles business logic for:
- Creating and updating requests
- Uploading and managing log samples
- State transitions (NEW → PENDING_APPROVAL)
- Sample retention and validation
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID

import structlog
from fastapi import UploadFile

from backend.core.config import settings
from backend.core.exceptions import (
    FileSizeExceededError,
    InsufficientPermissionsError,
    InvalidFileTypeError,
    InvalidRequestStateError,
    NoSamplesAttachedError,
    RequestNotFoundError,
    SampleNotFoundError,
)
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.models.enums import RequestStatus, UserRoleEnum
from backend.models.log_sample import LogSample
from backend.models.request import Request
from backend.models.user import User
from backend.repositories.log_sample_repository import LogSampleRepository
from backend.repositories.request_repository import RequestRepository

logger = structlog.get_logger(__name__)


class RequestService:
    """Service for managing requests and samples."""

    # Allowed MIME types for sample uploads
    ALLOWED_MIME_TYPES = {
        "text/plain",
        "text/x-log",
        "text/csv",
        "application/x-log",
        "application/gzip",
        "application/x-gzip",
        "application/zip",
        "application/octet-stream",  # Generic binary, check extension
    }

    # Allowed file extensions
    ALLOWED_EXTENSIONS = {
        ".log",
        ".txt",
        ".csv",
        ".gz",
        ".gzip",
        ".zip",
        ".json",
    }

    def __init__(
        self,
        request_repository: RequestRepository,
        sample_repository: LogSampleRepository,
        storage_client: ObjectStorageClient,
    ):
        """
        Initialize request service.

        Args:
            request_repository: Repository for request operations
            sample_repository: Repository for sample operations
            storage_client: Client for object storage operations
        """
        self.request_repo = request_repository
        self.sample_repo = sample_repository
        self.storage = storage_client

    async def create_request(
        self,
        source_system: str,
        description: str,
        cim_required: bool,
        metadata: Optional[Dict],
        current_user: User,
    ) -> Request:
        """
        Create a new request.

        Args:
            source_system: Name of the log source system
            description: Detailed description
            cim_required: Whether CIM compliance is required
            metadata: Additional metadata
            current_user: User creating the request

        Returns:
            Created request

        Raises:
            InsufficientPermissionsError: If user doesn't have REQUESTOR role
        """
        log = logger.bind(
            user_id=str(current_user.id),
            source_system=source_system,
        )
        log.info("create_request_started")

        # Verify user has REQUESTOR role
        user_roles = [role.name for role in current_user.roles]
        if UserRoleEnum.REQUESTOR.value not in user_roles:
            log.warning("create_request_insufficient_permissions")
            raise InsufficientPermissionsError(
                "Creating requests requires REQUESTOR role"
            )

        # Create request with NEW status
        request = await self.request_repo.create(
            created_by=current_user.id,
            source_system=source_system,
            description=description,
            cim_required=cim_required,
            metadata=metadata,
            status=RequestStatus.NEW,
        )

        log.info("create_request_completed", request_id=str(request.id))
        return request

    async def get_request(
        self,
        request_id: UUID,
        current_user: User,
    ) -> Request:
        """
        Get request by ID with authorization check.

        Args:
            request_id: Request ID
            current_user: Current user

        Returns:
            Request object

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't have access
        """
        log = logger.bind(request_id=str(request_id), user_id=str(current_user.id))
        log.info("get_request_started")

        request = await self.request_repo.get_by_id(request_id)
        if not request:
            log.warning("get_request_not_found")
            raise RequestNotFoundError()

        # Check authorization: user must be creator or have APPROVER/ADMIN role
        user_roles = [role.name for role in current_user.roles]
        is_creator = request.created_by == current_user.id
        is_authorized = (
            is_creator
            or UserRoleEnum.APPROVER.value in user_roles
            or UserRoleEnum.ADMIN.value in user_roles
            or current_user.is_superuser
        )

        if not is_authorized:
            log.warning("get_request_unauthorized")
            raise InsufficientPermissionsError(
                "You don't have permission to view this request"
            )

        log.info("get_request_completed")
        return request

    async def list_user_requests(
        self,
        current_user: User,
        skip: int = 0,
        limit: int = 100,
        status: Optional[RequestStatus] = None,
    ) -> tuple[List[Request], int]:
        """
        List requests for current user with pagination.

        Args:
            current_user: Current user
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Optional status filter

        Returns:
            Tuple of (requests list, total count)
        """
        log = logger.bind(user_id=str(current_user.id), skip=skip, limit=limit)
        log.info("list_user_requests_started")

        # Check if user has APPROVER/ADMIN role (can see all requests)
        user_roles = [role.name for role in current_user.roles]
        can_see_all = (
            UserRoleEnum.APPROVER.value in user_roles
            or UserRoleEnum.ADMIN.value in user_roles
            or current_user.is_superuser
        )

        if can_see_all:
            requests = await self.request_repo.list_all(
                skip=skip,
                limit=limit,
                status=status,
            )
            total = await self.request_repo.count(status=status)
        else:
            requests = await self.request_repo.list_by_user(
                user_id=current_user.id,
                skip=skip,
                limit=limit,
                status=status,
            )
            total = await self.request_repo.count_by_user(
                user_id=current_user.id,
                status=status,
            )

        log.info("list_user_requests_completed", count=len(requests), total=total)
        return requests, total

    async def update_request(
        self,
        request_id: UUID,
        current_user: User,
        source_system: Optional[str] = None,
        description: Optional[str] = None,
        cim_required: Optional[bool] = None,
        metadata: Optional[Dict] = None,
    ) -> Request:
        """
        Update request metadata.

        Args:
            request_id: Request ID
            current_user: Current user
            source_system: Updated source system
            description: Updated description
            cim_required: Updated CIM requirement
            metadata: Updated metadata

        Returns:
            Updated request

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't own request
            InvalidRequestStateError: If request status is not NEW
        """
        log = logger.bind(request_id=str(request_id), user_id=str(current_user.id))
        log.info("update_request_started")

        # Get request and check ownership
        request = await self.get_request(request_id, current_user)
        if request.created_by != current_user.id:
            log.warning("update_request_not_owner")
            raise InsufficientPermissionsError("Only request creator can update it")

        # Only allow updates when status is NEW
        if request.status != RequestStatus.NEW:
            log.warning("update_request_invalid_state", status=request.status.value)
            raise InvalidRequestStateError(
                f"Cannot update request in {request.status.value} state. "
                "Only NEW requests can be updated."
            )

        # Prepare update data
        update_data = {}
        if source_system is not None:
            update_data["source_system"] = source_system
        if description is not None:
            update_data["description"] = description
        if cim_required is not None:
            update_data["cim_required"] = cim_required
        if metadata is not None:
            update_data["metadata"] = metadata

        # Update request
        updated_request = await self.request_repo.update(request_id, **update_data)

        log.info("update_request_completed")
        return updated_request

    async def upload_sample(
        self,
        request_id: UUID,
        file: UploadFile,
        current_user: User,
    ) -> LogSample:
        """
        Upload log sample file.

        Args:
            request_id: Parent request ID
            file: Uploaded file
            current_user: Current user

        Returns:
            Created LogSample

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't own request
            InvalidRequestStateError: If request not in NEW state
            FileSizeExceededError: If file too large
            InvalidFileTypeError: If file type not allowed
        """
        log = logger.bind(
            request_id=str(request_id),
            user_id=str(current_user.id),
            filename=file.filename,
        )
        log.info("upload_sample_started")

        # Get request and verify ownership
        request = await self.get_request(request_id, current_user)
        if request.created_by != current_user.id:
            log.warning("upload_sample_not_owner")
            raise InsufficientPermissionsError("Only request creator can upload samples")

        # Only allow uploads when status is NEW
        if request.status != RequestStatus.NEW:
            log.warning("upload_sample_invalid_state", status=request.status.value)
            raise InvalidRequestStateError(
                f"Cannot upload samples to request in {request.status.value} state"
            )

        # Validate file type
        self._validate_file_type(file.filename, file.content_type)

        # Generate storage key
        storage_key = f"samples/{request_id}/{file.filename}"

        # Upload to storage with streaming, checksum calculation, and preview capture
        # The storage client handles single-pass streaming: reads file once while
        # computing checksum, capturing preview, and uploading to S3 without buffering
        log.info("upload_sample_uploading_to_storage")
        upload_result = await self.storage.upload_file_async(
            file_obj=file.file,
            bucket=self.storage.bucket_samples,
            key=storage_key,
            content_type=file.content_type,
            capture_preview=1000,  # Capture first 1000 bytes for preview
        )

        # Extract results from upload
        checksum = upload_result["checksum"]
        file_size = upload_result["size"]
        preview_bytes = upload_result.get("preview_bytes", b"")

        # Validate file size after upload
        await self._validate_sample_size(request_id, file_size)

        # Generate preview from captured bytes
        preview = self._generate_sample_preview(preview_bytes)

        # Calculate retention date
        retention_until = self._calculate_retention_date()

        # Create sample record
        sample = await self.sample_repo.create(
            request_id=request_id,
            filename=file.filename,
            file_size=file_size,
            mime_type=file.content_type,
            storage_key=storage_key,
            storage_bucket=self.storage.bucket_samples,
            checksum=checksum,
            sample_preview=preview,
            retention_until=retention_until,
        )

        log.info("upload_sample_completed", sample_id=str(sample.id))
        return sample

    async def get_samples(
        self,
        request_id: UUID,
        current_user: User,
    ) -> List[LogSample]:
        """
        Get all samples for a request.

        Args:
            request_id: Request ID
            current_user: Current user

        Returns:
            List of samples

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't have access
        """
        log = logger.bind(request_id=str(request_id), user_id=str(current_user.id))
        log.info("get_samples_started")

        # Verify access to request
        await self.get_request(request_id, current_user)

        # Get samples
        samples = await self.sample_repo.get_by_request(request_id)

        log.info("get_samples_completed", count=len(samples))
        return samples

    async def get_sample(
        self,
        request_id: UUID,
        sample_id: UUID,
        current_user: User,
    ) -> LogSample:
        """
        Get sample by ID.

        Args:
            request_id: Parent request ID
            sample_id: Sample ID
            current_user: Current user

        Returns:
            LogSample

        Raises:
            SampleNotFoundError: If sample doesn't exist
            InsufficientPermissionsError: If user doesn't have access
        """
        log = logger.bind(
            request_id=str(request_id),
            sample_id=str(sample_id),
            user_id=str(current_user.id),
        )
        log.info("get_sample_started")

        # Verify access to request
        await self.get_request(request_id, current_user)

        # Get sample
        sample = await self.sample_repo.get_by_id(sample_id)
        if not sample or sample.request_id != request_id:
            log.warning("get_sample_not_found")
            raise SampleNotFoundError()

        log.info("get_sample_completed")
        return sample

    async def delete_sample(
        self,
        request_id: UUID,
        sample_id: UUID,
        current_user: User,
    ) -> None:
        """
        Delete (soft delete) a sample.

        Args:
            request_id: Parent request ID
            sample_id: Sample ID
            current_user: Current user

        Raises:
            SampleNotFoundError: If sample doesn't exist
            InsufficientPermissionsError: If user doesn't own request
            InvalidRequestStateError: If request not in NEW state
        """
        log = logger.bind(
            request_id=str(request_id),
            sample_id=str(sample_id),
            user_id=str(current_user.id),
        )
        log.info("delete_sample_started")

        # Get request and verify ownership
        request = await self.get_request(request_id, current_user)
        if request.created_by != current_user.id:
            log.warning("delete_sample_not_owner")
            raise InsufficientPermissionsError("Only request creator can delete samples")

        # Only allow deletion when status is NEW
        if request.status != RequestStatus.NEW:
            log.warning("delete_sample_invalid_state", status=request.status.value)
            raise InvalidRequestStateError(
                f"Cannot delete samples from request in {request.status.value} state"
            )

        # Get sample
        sample = await self.get_sample(request_id, sample_id, current_user)

        # Soft delete
        await self.sample_repo.soft_delete(sample_id)

        # Optionally delete from storage if retention disabled
        if not settings.sample_retention_enabled:
            log.info("delete_sample_removing_from_storage")
            try:
                await self.storage.delete_file_async(
                    bucket=sample.storage_bucket,
                    key=sample.storage_key,
                )
            except Exception as e:
                log.warning("delete_sample_storage_deletion_failed", error=str(e))
                # Continue anyway, soft delete succeeded

        log.info("delete_sample_completed")

    async def submit_for_approval(
        self,
        request_id: UUID,
        current_user: User,
    ) -> Request:
        """
        Submit request for approval.

        Args:
            request_id: Request ID
            current_user: Current user

        Returns:
            Updated request

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't own request
            InvalidRequestStateError: If request not in NEW state
            NoSamplesAttachedError: If no samples attached
        """
        log = logger.bind(request_id=str(request_id), user_id=str(current_user.id))
        log.info("submit_for_approval_started")

        # Get request and verify ownership
        request = await self.get_request(request_id, current_user)
        if request.created_by != current_user.id:
            log.warning("submit_for_approval_not_owner")
            raise InsufficientPermissionsError("Only request creator can submit it")

        # Verify status is NEW
        if request.status != RequestStatus.NEW:
            log.warning("submit_for_approval_invalid_state", status=request.status.value)
            raise InvalidRequestStateError(
                f"Cannot submit request in {request.status.value} state. "
                "Only NEW requests can be submitted."
            )

        # Verify at least one sample is attached
        samples = await self.sample_repo.get_by_request(request_id)
        if not samples:
            log.warning("submit_for_approval_no_samples")
            raise NoSamplesAttachedError()

        # Update status to PENDING_APPROVAL
        updated_request = await self.request_repo.update_status(
            request_id,
            RequestStatus.PENDING_APPROVAL,
        )

        log.info("submit_for_approval_completed")
        return updated_request

    def _validate_file_type(self, filename: str, content_type: Optional[str]) -> None:
        """
        Validate file type by MIME type and extension.

        Args:
            filename: Original filename
            content_type: MIME type

        Raises:
            InvalidFileTypeError: If file type not allowed
        """
        # Check MIME type
        if content_type and content_type not in self.ALLOWED_MIME_TYPES:
            # Allow if extension is valid
            extension = self._get_file_extension(filename)
            if extension not in self.ALLOWED_EXTENSIONS:
                raise InvalidFileTypeError(
                    f"File type '{content_type}' is not allowed. "
                    f"Allowed types: text/*, application/gzip, application/zip"
                )

        # Check extension
        extension = self._get_file_extension(filename)
        if extension not in self.ALLOWED_EXTENSIONS:
            raise InvalidFileTypeError(
                f"File extension '{extension}' is not allowed. "
                f"Allowed extensions: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )

    def _get_file_extension(self, filename: str) -> str:
        """Get lowercase file extension including dot."""
        if "." not in filename:
            return ""
        return "." + filename.rsplit(".", 1)[-1].lower()

    async def _validate_sample_size(self, request_id: UUID, new_file_size: int) -> None:
        """
        Validate sample size doesn't exceed limits.

        Args:
            request_id: Request ID
            new_file_size: Size of new file in bytes

        Raises:
            FileSizeExceededError: If total size exceeds limit
        """
        max_size_bytes = settings.max_sample_size_mb * 1024 * 1024

        # Check single file size
        if new_file_size > max_size_bytes:
            raise FileSizeExceededError(settings.max_sample_size_mb)

        # Check total size for request
        existing_samples = await self.sample_repo.get_by_request(request_id)
        total_size = sum(sample.file_size for sample in existing_samples) + new_file_size

        if total_size > max_size_bytes:
            raise FileSizeExceededError(settings.max_sample_size_mb)

    def _generate_sample_preview(self, content: bytes, max_chars: int = 1000) -> str:
        """
        Generate preview of file content.

        Args:
            content: File content as bytes
            max_chars: Maximum characters to extract

        Returns:
            Preview string (first N characters)
        """
        try:
            # Try to decode as UTF-8
            text = content.decode("utf-8")
            return text[:max_chars]
        except UnicodeDecodeError:
            # Binary file, return hex preview
            return content[:max_chars].hex()

    def _calculate_retention_date(self) -> Optional[datetime]:
        """
        Calculate retention expiration date based on settings.

        Returns:
            Retention date or None if retention disabled
        """
        if not settings.sample_retention_enabled:
            return None

        return datetime.utcnow() + timedelta(days=settings.sample_retention_days)