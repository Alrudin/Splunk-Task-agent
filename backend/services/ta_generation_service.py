"""
TA Generation Service for managing TA packaging and manual override logic.

This service handles business logic for:
- Creating manual TA revisions from uploaded files
- Getting TA revisions for download
- Triggering re-validation of TA revisions
"""
import hashlib
from typing import Optional, Tuple
from uuid import UUID

import structlog
from fastapi import UploadFile

from backend.core.config import settings
from backend.core.exceptions import (
    InsufficientPermissionsError,
    InvalidRequestStateError,
    RequestNotFoundError,
    TARevisionNotFoundError,
    InvalidTAFileError,
    TAFileSizeExceededError,
)
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.models.enums import (
    RequestStatus,
    TARevisionType,
    UserRoleEnum,
    ValidationStatus,
)
from backend.models.ta_revision import TARevision
from backend.models.user import User
from backend.models.validation_run import ValidationRun
from backend.repositories.request_repository import RequestRepository
from backend.repositories.ta_revision_repository import TARevisionRepository
from backend.repositories.validation_run_repository import ValidationRunRepository

logger = structlog.get_logger(__name__)

# Allowed states for manual override
ALLOWED_OVERRIDE_STATES = {
    RequestStatus.APPROVED,
    RequestStatus.GENERATING_TA,
    RequestStatus.VALIDATING,
    RequestStatus.COMPLETED,
    RequestStatus.FAILED,
}


class TAGenerationService:
    """Service for managing TA generation and manual overrides."""

    # Allowed file extensions for TA uploads
    ALLOWED_EXTENSIONS = (".tgz", ".tar.gz")

    def __init__(
        self,
        ta_revision_repository: TARevisionRepository,
        request_repository: RequestRepository,
        validation_run_repository: ValidationRunRepository,
        storage_client: ObjectStorageClient,
    ):
        """
        Initialize TA generation service.

        Args:
            ta_revision_repository: Repository for TA revision operations
            request_repository: Repository for request operations
            validation_run_repository: Repository for validation run operations
            storage_client: Client for object storage operations
        """
        self.ta_revision_repo = ta_revision_repository
        self.request_repo = request_repository
        self.validation_run_repo = validation_run_repository
        self.storage = storage_client

    async def create_manual_revision(
        self,
        request_id: UUID,
        file: UploadFile,
        current_user: User,
    ) -> Tuple[TARevision, ValidationRun]:
        """
        Process manual TA override upload.

        Args:
            request_id: Parent request ID
            file: Uploaded TA package file
            current_user: User performing the override

        Returns:
            Tuple of (TARevision, ValidationRun)

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't have access
            InvalidRequestStateError: If request state doesn't allow override
            InvalidTAFileError: If file is not a valid TA package
            TAFileSizeExceededError: If file exceeds size limit
        """
        log = logger.bind(
            request_id=str(request_id),
            user_id=str(current_user.id),
            filename=file.filename,
        )
        log.info("create_manual_revision_started")

        # Validate request exists
        request = await self.request_repo.get_by_id(request_id)
        if not request:
            log.warning("create_manual_revision_request_not_found")
            raise RequestNotFoundError()

        # Check authorization (APPROVER or ADMIN role)
        user_roles = [role.name for role in current_user.roles]
        is_authorized = (
            UserRoleEnum.APPROVER.value in user_roles
            or UserRoleEnum.ADMIN.value in user_roles
            or current_user.is_superuser
        )
        if not is_authorized:
            log.warning("create_manual_revision_unauthorized")
            raise InsufficientPermissionsError(
                "Manual override requires APPROVER or ADMIN role"
            )

        # Validate request state allows manual override
        if request.status not in ALLOWED_OVERRIDE_STATES:
            log.warning(
                "create_manual_revision_invalid_state",
                status=request.status.value
            )
            raise InvalidRequestStateError(
                f"Cannot upload manual override in {request.status.value} state. "
                f"Allowed states: {', '.join(s.value for s in ALLOWED_OVERRIDE_STATES)}"
            )

        # Validate file extension
        self._validate_file_extension(file.filename)

        # Pre-upload file size validation
        # Check if UploadFile.size is available (populated from Content-Length header)
        # or determine size by seeking to end of file
        max_size_bytes = getattr(settings, 'max_ta_file_size_mb', 100) * 1024 * 1024
        apparent_size = None

        if hasattr(file, 'size') and file.size is not None:
            apparent_size = file.size
        else:
            # Try to determine size by seeking to end of file
            try:
                current_pos = file.file.tell()
                file.file.seek(0, 2)  # Seek to end
                apparent_size = file.file.tell()
                file.file.seek(current_pos)  # Reset to original position
            except Exception:
                # If seek fails (e.g., non-seekable stream), skip pre-upload check
                pass

        if apparent_size is not None and apparent_size > max_size_bytes:
            log.warning(
                "create_manual_revision_file_too_large_pre_upload",
                apparent_size=apparent_size,
                max_size=max_size_bytes,
            )
            raise TAFileSizeExceededError(
                getattr(settings, 'max_ta_file_size_mb', 100)
            )

        # Get next version number
        next_version = await self.ta_revision_repo.get_next_version(request_id)

        # Generate storage key
        source_system_slug = request.source_system.lower().replace(" ", "-")
        storage_key = (
            f"tas/{request_id}/v{next_version}/"
            f"ta-{source_system_slug}-v{next_version}.tgz"
        )

        # Upload to storage with checksum calculation
        log.info("create_manual_revision_uploading_to_storage")
        upload_result = await self.storage.upload_file_async(
            file_obj=file.file,
            bucket=self.storage.bucket_tas,
            key=storage_key,
            content_type="application/gzip",
        )

        checksum = upload_result["checksum"]
        file_size = upload_result["size"]

        # Post-upload file size validation (fallback for cases where pre-upload check wasn't possible)
        # This catches cases where the file was streamed without a known size upfront.
        # Oversize files are deleted immediately after upload to cap storage usage.
        if file_size > max_size_bytes:
            log.warning(
                "create_manual_revision_file_too_large_post_upload",
                file_size=file_size,
                max_size=max_size_bytes,
            )
            # Clean up uploaded file immediately
            try:
                await self.storage.delete_file_async(
                    bucket=self.storage.bucket_tas,
                    key=storage_key,
                )
            except Exception:
                log.warning("create_manual_revision_cleanup_failed")
            raise TAFileSizeExceededError(
                getattr(settings, 'max_ta_file_size_mb', 100)
            )

        # Create TARevision record
        ta_revision = await self.ta_revision_repo.create(
            request_id=request_id,
            version=next_version,
            storage_key=storage_key,
            storage_bucket=self.storage.bucket_tas,
            generated_by=TARevisionType.MANUAL,
            generated_by_user=current_user.id,
            file_size=file_size,
            checksum=f"sha256:{checksum}",
        )

        # Create ValidationRun record with QUEUED status
        validation_run = await self.validation_run_repo.create(
            request_id=request_id,
            ta_revision_id=ta_revision.id,
            status=ValidationStatus.QUEUED,
        )

        # Update request status to VALIDATING
        await self.request_repo.update_status(request_id, RequestStatus.VALIDATING)

        # Enqueue Celery validation task
        # Using local import to avoid circular dependencies
        from backend.tasks.validation import validate_ta_task
        validate_ta_task.delay(str(validation_run.id))

        log.info(
            "create_manual_revision_completed",
            revision_id=str(ta_revision.id),
            version=next_version,
            validation_run_id=str(validation_run.id),
            validation_task_enqueued=True,
        )

        return ta_revision, validation_run

    async def get_ta_for_download(
        self,
        request_id: UUID,
        version: int,
        current_user: User,
    ) -> TARevision:
        """
        Get TA revision for download with authorization check.

        Args:
            request_id: Parent request ID
            version: TA version number
            current_user: Current user

        Returns:
            TARevision object

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't have access
            TARevisionNotFoundError: If TA revision not found
        """
        log = logger.bind(
            request_id=str(request_id),
            version=version,
            user_id=str(current_user.id),
        )
        log.info("get_ta_for_download_started")

        # Validate request exists
        request = await self.request_repo.get_by_id(request_id)
        if not request:
            log.warning("get_ta_for_download_request_not_found")
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
            log.warning("get_ta_for_download_unauthorized")
            raise InsufficientPermissionsError(
                "You don't have permission to download this TA"
            )

        # Get TA revision by version
        ta_revision = await self.ta_revision_repo.get_by_version(request_id, version)
        if not ta_revision:
            log.warning("get_ta_for_download_revision_not_found")
            raise TARevisionNotFoundError()

        log.info(
            "get_ta_for_download_completed",
            revision_id=str(ta_revision.id),
        )
        return ta_revision

    async def get_revision_by_id(
        self,
        request_id: UUID,
        revision_id: UUID,
        current_user: User,
    ) -> TARevision:
        """
        Get TA revision by ID with authorization check.

        Args:
            request_id: Parent request ID
            revision_id: TA revision ID
            current_user: Current user

        Returns:
            TARevision object

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't have access
            TARevisionNotFoundError: If TA revision not found
        """
        log = logger.bind(
            request_id=str(request_id),
            revision_id=str(revision_id),
            user_id=str(current_user.id),
        )
        log.info("get_revision_by_id_started")

        # Validate request exists
        request = await self.request_repo.get_by_id(request_id)
        if not request:
            log.warning("get_revision_by_id_request_not_found")
            raise RequestNotFoundError()

        # Check authorization
        user_roles = [role.name for role in current_user.roles]
        is_creator = request.created_by == current_user.id
        is_authorized = (
            is_creator
            or UserRoleEnum.APPROVER.value in user_roles
            or UserRoleEnum.ADMIN.value in user_roles
            or current_user.is_superuser
        )

        if not is_authorized:
            log.warning("get_revision_by_id_unauthorized")
            raise InsufficientPermissionsError(
                "You don't have permission to access this TA revision"
            )

        # Get TA revision by ID
        ta_revision = await self.ta_revision_repo.get_by_id(revision_id)
        if not ta_revision or ta_revision.request_id != request_id:
            log.warning("get_revision_by_id_revision_not_found")
            raise TARevisionNotFoundError()

        log.info("get_revision_by_id_completed")
        return ta_revision

    async def trigger_revalidation(
        self,
        request_id: UUID,
        revision_id: UUID,
        current_user: User,
    ) -> ValidationRun:
        """
        Trigger re-validation for existing TA revision.

        Args:
            request_id: Parent request ID
            revision_id: TA revision ID to re-validate
            current_user: User triggering re-validation

        Returns:
            Created ValidationRun

        Raises:
            RequestNotFoundError: If request doesn't exist
            TARevisionNotFoundError: If TA revision not found
            InsufficientPermissionsError: If user doesn't have access
            InvalidRequestStateError: If request state doesn't allow re-validation
        """
        log = logger.bind(
            request_id=str(request_id),
            revision_id=str(revision_id),
            user_id=str(current_user.id),
        )
        log.info("trigger_revalidation_started")

        # Validate request exists
        request = await self.request_repo.get_by_id(request_id)
        if not request:
            log.warning("trigger_revalidation_request_not_found")
            raise RequestNotFoundError()

        # Check authorization (APPROVER or ADMIN role)
        user_roles = [role.name for role in current_user.roles]
        is_authorized = (
            UserRoleEnum.APPROVER.value in user_roles
            or UserRoleEnum.ADMIN.value in user_roles
            or current_user.is_superuser
        )
        if not is_authorized:
            log.warning("trigger_revalidation_unauthorized")
            raise InsufficientPermissionsError(
                "Re-validation requires APPROVER or ADMIN role"
            )

        # Validate request state allows re-validation
        allowed_states = {
            RequestStatus.VALIDATING,
            RequestStatus.COMPLETED,
            RequestStatus.FAILED,
        }
        if request.status not in allowed_states:
            log.warning(
                "trigger_revalidation_invalid_state",
                status=request.status.value
            )
            raise InvalidRequestStateError(
                f"Cannot trigger re-validation in {request.status.value} state"
            )

        # Validate TA revision exists
        ta_revision = await self.ta_revision_repo.get_by_id(revision_id)
        if not ta_revision or ta_revision.request_id != request_id:
            log.warning("trigger_revalidation_revision_not_found")
            raise TARevisionNotFoundError()

        # Create new ValidationRun with QUEUED status
        validation_run = await self.validation_run_repo.create(
            request_id=request_id,
            ta_revision_id=revision_id,
            status=ValidationStatus.QUEUED,
        )

        # Update request status to VALIDATING
        await self.request_repo.update_status(request_id, RequestStatus.VALIDATING)

        # Enqueue Celery validation task
        # Using local import to avoid circular dependencies
        from backend.tasks.validation import validate_ta_task
        validate_ta_task.delay(str(validation_run.id))

        log.info(
            "trigger_revalidation_completed",
            validation_run_id=str(validation_run.id),
            validation_task_enqueued=True,
        )

        return validation_run

    async def get_revisions(
        self,
        request_id: UUID,
        current_user: User,
        skip: int = 0,
        limit: int = 100,
    ) -> Tuple[list, int]:
        """
        Get all TA revisions for a request with validation status.

        Args:
            request_id: Parent request ID
            current_user: Current user
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            Tuple of (revisions list, total count)

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't have access
        """
        log = logger.bind(
            request_id=str(request_id),
            user_id=str(current_user.id),
        )
        log.info("get_revisions_started")

        # Validate request exists
        request = await self.request_repo.get_by_id(request_id)
        if not request:
            log.warning("get_revisions_request_not_found")
            raise RequestNotFoundError()

        # Check authorization
        user_roles = [role.name for role in current_user.roles]
        is_creator = request.created_by == current_user.id
        is_authorized = (
            is_creator
            or UserRoleEnum.APPROVER.value in user_roles
            or UserRoleEnum.ADMIN.value in user_roles
            or current_user.is_superuser
        )

        if not is_authorized:
            log.warning("get_revisions_unauthorized")
            raise InsufficientPermissionsError(
                "You don't have permission to view TA revisions"
            )

        # Get revision history with validation runs eagerly loaded
        revisions = await self.ta_revision_repo.get_revision_history(request_id)

        # Apply pagination
        total = len(revisions)
        revisions = revisions[skip:skip + limit]

        # Compute latest validation status for each revision
        for revision in revisions:
            if revision.validation_runs:
                # Sort by created_at desc and get first
                latest_run = max(
                    revision.validation_runs,
                    key=lambda r: r.created_at
                )
                revision.latest_validation_status = latest_run.status
            else:
                revision.latest_validation_status = None

        log.info("get_revisions_completed", count=len(revisions), total=total)
        return revisions, total

    async def get_revision_detail(
        self,
        request_id: UUID,
        version: int,
        current_user: User,
    ) -> TARevision:
        """
        Get detailed TA revision with validation runs.

        Args:
            request_id: Parent request ID
            version: TA version number
            current_user: Current user

        Returns:
            TARevision with validation_runs loaded

        Raises:
            RequestNotFoundError: If request doesn't exist
            TARevisionNotFoundError: If revision not found
            InsufficientPermissionsError: If user doesn't have access
        """
        log = logger.bind(
            request_id=str(request_id),
            version=version,
            user_id=str(current_user.id),
        )
        log.info("get_revision_detail_started")

        # Get basic TA revision first (handles auth)
        ta_revision = await self.get_ta_for_download(request_id, version, current_user)

        # Get revision with validation runs eagerly loaded
        ta_revision_with_runs = await self.ta_revision_repo.get_with_validations(
            ta_revision.id
        )

        if ta_revision_with_runs and ta_revision_with_runs.validation_runs:
            latest_run = max(
                ta_revision_with_runs.validation_runs,
                key=lambda r: r.created_at
            )
            ta_revision_with_runs.latest_validation_status = latest_run.status
        else:
            if ta_revision_with_runs:
                ta_revision_with_runs.latest_validation_status = None

        log.info("get_revision_detail_completed")
        return ta_revision_with_runs or ta_revision

    async def get_validation_run_for_request(
        self,
        request_id: UUID,
        validation_run_id: UUID,
        current_user: User,
    ) -> "ValidationRun":
        """
        Get validation run by ID with request access verification.

        Args:
            request_id: Parent request ID for access check
            validation_run_id: Validation run ID to fetch
            current_user: Current user for authorization

        Returns:
            ValidationRun object

        Raises:
            RequestNotFoundError: If request doesn't exist
            InsufficientPermissionsError: If user doesn't have access
            ValidationRunNotFoundError: If validation run not found or doesn't belong to request
        """
        from backend.core.exceptions import ValidationRunNotFoundError

        log = logger.bind(
            request_id=str(request_id),
            validation_run_id=str(validation_run_id),
            user_id=str(current_user.id),
        )
        log.info("get_validation_run_for_request_started")

        # Validate request exists and user has access
        request = await self.request_repo.get_by_id(request_id)
        if not request:
            log.warning("get_validation_run_for_request_request_not_found")
            raise RequestNotFoundError()

        # Check authorization
        user_roles = [role.name for role in current_user.roles]
        is_creator = request.created_by == current_user.id
        is_authorized = (
            is_creator
            or UserRoleEnum.APPROVER.value in user_roles
            or UserRoleEnum.ADMIN.value in user_roles
            or current_user.is_superuser
        )

        if not is_authorized:
            log.warning("get_validation_run_for_request_unauthorized")
            raise InsufficientPermissionsError(
                "You don't have permission to access this validation run"
            )

        # Fetch validation run directly by ID
        validation_run = await self.validation_run_repo.get_by_id(validation_run_id)
        if not validation_run or validation_run.request_id != request_id:
            log.warning("get_validation_run_for_request_not_found")
            raise ValidationRunNotFoundError()

        log.info("get_validation_run_for_request_completed")
        return validation_run

    def _validate_file_extension(self, filename: Optional[str]) -> None:
        """
        Validate file extension is allowed for TA uploads.

        Args:
            filename: Original filename

        Raises:
            InvalidTAFileError: If file extension not allowed
        """
        if not filename:
            raise InvalidTAFileError()

        filename_lower = filename.lower()
        if not any(filename_lower.endswith(ext) for ext in self.ALLOWED_EXTENSIONS):
            raise InvalidTAFileError(
                f"File extension not allowed. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}"
            )
