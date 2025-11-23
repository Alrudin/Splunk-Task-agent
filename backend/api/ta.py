"""
FastAPI routes for TA revision and manual override operations.

This module provides RESTful API endpoints for:
- Listing TA revisions for a request
- Getting specific TA revision details
- Downloading TA packages
- Uploading manual TA overrides
- Triggering re-validation
"""
from uuid import UUID

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    Request,
    UploadFile,
    status as http_status,
)
from fastapi.responses import RedirectResponse

from backend.core.dependencies import (
    get_audit_service,
    get_current_active_user,
    get_storage_client,
    get_ta_generation_service,
    require_any_role,
)
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.models.enums import UserRoleEnum, ValidationStatus
from backend.models.user import User
from backend.schemas.ta import (
    RevalidateResponse,
    TARevisionDetailResponse,
    TARevisionListResponse,
    TARevisionResponse,
    UploadTAOverrideResponse,
    ValidationRunResponse,
)
from backend.services.audit_service import AuditService
from backend.services.ta_generation_service import TAGenerationService

logger = structlog.get_logger(__name__)

# Create router
router = APIRouter(prefix="/ta/requests", tags=["TA Revisions"])


@router.get(
    "/{request_id}/revisions",
    response_model=TARevisionListResponse,
    summary="List TA revisions",
    description="List all TA revisions for a request with pagination and validation status.",
)
async def list_ta_revisions(
    request_id: UUID,
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    current_user: User = Depends(get_current_active_user),
    service: TAGenerationService = Depends(get_ta_generation_service),
) -> TARevisionListResponse:
    """
    List all TA revisions for a request.

    Returns revisions in reverse chronological order (newest first)
    with the latest validation status for each revision.

    **Required role:** Authenticated user (creator, approver, or admin)
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
    )
    log.info("api_list_ta_revisions")

    revisions, total = await service.get_revisions(
        request_id=request_id,
        current_user=current_user,
        skip=skip,
        limit=limit,
    )

    # Convert to response schemas
    items = []
    for revision in revisions:
        response = TARevisionResponse.model_validate(revision)
        response.latest_validation_status = getattr(
            revision, 'latest_validation_status', None
        )
        items.append(response)

    return TARevisionListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{request_id}/revisions/{version}",
    response_model=TARevisionDetailResponse,
    summary="Get TA revision details",
    description="Get detailed information about a specific TA revision including validation runs.",
)
async def get_ta_revision(
    request_id: UUID,
    version: int,
    current_user: User = Depends(get_current_active_user),
    service: TAGenerationService = Depends(get_ta_generation_service),
) -> TARevisionDetailResponse:
    """
    Get detailed TA revision information.

    Returns revision details with all validation runs.

    **Required role:** Authenticated user (creator, approver, or admin)
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
        version=version,
    )
    log.info("api_get_ta_revision")

    revision = await service.get_revision_detail(
        request_id=request_id,
        version=version,
        current_user=current_user,
    )

    # Build response with validation runs
    response = TARevisionDetailResponse.model_validate(revision)
    if hasattr(revision, 'validation_runs') and revision.validation_runs:
        response.validation_runs = [
            ValidationRunResponse.model_validate(run)
            for run in sorted(
                revision.validation_runs,
                key=lambda r: r.created_at,
                reverse=True
            )
        ]
        response.latest_validation_status = response.validation_runs[0].status
    else:
        response.validation_runs = []

    return response


@router.get(
    "/{request_id}/revisions/{version}/download",
    summary="Download TA package",
    description="Download a TA package (.tgz file). Returns redirect to presigned URL.",
)
async def download_ta_revision(
    request_id: UUID,
    version: int,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    service: TAGenerationService = Depends(get_ta_generation_service),
    storage: ObjectStorageClient = Depends(get_storage_client),
    audit_service: AuditService = Depends(get_audit_service),
) -> RedirectResponse:
    """
    Download TA package.

    Returns a redirect to a presigned URL that expires in 1 hour.
    Logs download action for audit purposes.

    **Required role:** Authenticated user (creator, approver, or admin)
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
        version=version,
    )
    log.info("api_download_ta_revision")

    # Get TA revision (handles authorization)
    ta_revision = await service.get_ta_for_download(
        request_id=request_id,
        version=version,
        current_user=current_user,
    )

    # Generate presigned URL (expires in 1 hour)
    presigned_url = await storage.generate_presigned_url(
        bucket=ta_revision.storage_bucket,
        key=ta_revision.storage_key,
        expires_in=3600,
    )

    # Log download action
    await audit_service.log_download(
        user_id=current_user.id,
        entity_type="TARevision",
        entity_id=ta_revision.id,
        details={
            "version": version,
            "request_id": str(request_id),
            "file_size": ta_revision.file_size,
        },
        request=request,
    )

    return RedirectResponse(url=presigned_url)


@router.post(
    "/{request_id}/revisions/override",
    response_model=UploadTAOverrideResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Upload manual TA override",
    description="Upload a manually edited TA package. Max size: 100MB. Format: .tgz or .tar.gz.",
)
async def upload_ta_override(
    request_id: UUID,
    request: Request,
    file: UploadFile = File(..., description="TA package file (.tgz or .tar.gz)"),
    current_user: User = Depends(require_any_role(UserRoleEnum.APPROVER, UserRoleEnum.ADMIN)),
    service: TAGenerationService = Depends(get_ta_generation_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> UploadTAOverrideResponse:
    """
    Upload manual TA override.

    Creates a new TA revision from the uploaded package and
    automatically queues validation. The new revision will be
    versioned incrementally (v1 → v2 → v3, etc.).

    **Constraints:**
    - Max file size: 100MB (configurable)
    - Allowed formats: .tgz, .tar.gz
    - Request must be in APPROVED, GENERATING_TA, VALIDATING, COMPLETED, or FAILED state

    **Required role:** APPROVER or ADMIN
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
        filename=file.filename,
    )
    log.info("api_upload_ta_override")

    # Create manual revision (handles validation and storage)
    ta_revision, validation_run = await service.create_manual_revision(
        request_id=request_id,
        file=file,
        current_user=current_user,
    )

    # Log manual override action
    await audit_service.log_manual_override(
        user_id=current_user.id,
        request_id=request_id,
        ta_revision_id=ta_revision.id,
        details={
            "version": ta_revision.version,
            "filename": file.filename,
            "file_size": ta_revision.file_size,
        },
        request=request,
    )

    return UploadTAOverrideResponse(
        revision=TARevisionResponse.model_validate(ta_revision),
        validation_run=ValidationRunResponse.model_validate(validation_run),
    )


@router.post(
    "/{request_id}/revisions/{revision_id}/revalidate",
    response_model=RevalidateResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Trigger re-validation",
    description="Trigger re-validation for an existing TA revision.",
)
async def revalidate_ta_revision(
    request_id: UUID,
    revision_id: UUID,
    request: Request,
    current_user: User = Depends(require_any_role(UserRoleEnum.APPROVER, UserRoleEnum.ADMIN)),
    service: TAGenerationService = Depends(get_ta_generation_service),
    audit_service: AuditService = Depends(get_audit_service),
) -> RevalidateResponse:
    """
    Trigger re-validation for a TA revision.

    Creates a new validation run with QUEUED status. The validation
    will be picked up by the Celery worker and executed in a
    Splunk sandbox container.

    **Requirements:**
    - Request must be in VALIDATING, COMPLETED, or FAILED state
    - User must have APPROVER or ADMIN role

    **Required role:** APPROVER or ADMIN
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
        revision_id=str(revision_id),
    )
    log.info("api_revalidate_ta_revision")

    # Trigger re-validation (handles authorization and state validation)
    validation_run = await service.trigger_revalidation(
        request_id=request_id,
        revision_id=revision_id,
        current_user=current_user,
    )

    # Log re-validation trigger
    await audit_service.log_revalidation_trigger(
        user_id=current_user.id,
        request_id=request_id,
        ta_revision_id=revision_id,
        details={
            "validation_run_id": str(validation_run.id),
        },
        request=request,
    )

    return RevalidateResponse(
        validation_run=ValidationRunResponse.model_validate(validation_run),
    )


@router.get(
    "/{request_id}/validation-runs/{validation_run_id}/debug-bundle",
    summary="Download debug bundle",
    description="Download debug bundle for a failed validation run. Returns redirect to presigned URL.",
)
async def download_debug_bundle(
    request_id: UUID,
    validation_run_id: UUID,
    request: Request,
    current_user: User = Depends(require_any_role(UserRoleEnum.APPROVER, UserRoleEnum.ADMIN)),
    service: TAGenerationService = Depends(get_ta_generation_service),
    storage: ObjectStorageClient = Depends(get_storage_client),
    audit_service: AuditService = Depends(get_audit_service),
) -> RedirectResponse:
    """
    Download debug bundle for a failed validation run.

    Returns a redirect to a presigned URL that expires in 1 hour.
    Debug bundles contain TA files, Splunk logs, and validation errors.

    **Required role:** APPROVER or ADMIN
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
        validation_run_id=str(validation_run_id),
    )
    log.info("api_download_debug_bundle")

    from backend.core.exceptions import AppException

    # Get validation run directly via service (handles authorization and request ownership check)
    validation_run = await service.get_validation_run_for_request(
        request_id=request_id,
        validation_run_id=validation_run_id,
        current_user=current_user,
    )

    if not validation_run.debug_bundle_key:
        raise AppException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail="Debug bundle not available for this validation run"
        )

    # Generate presigned URL
    presigned_url = await storage.generate_presigned_url(
        bucket=validation_run.debug_bundle_bucket or storage.bucket_debug,
        key=validation_run.debug_bundle_key,
        expires_in=3600,
    )

    # Log debug bundle download
    await audit_service.log_download(
        user_id=current_user.id,
        entity_type="DebugBundle",
        entity_id=validation_run_id,
        details={
            "request_id": str(request_id),
            "validation_status": validation_run.status.value,
        },
        request=request,
    )

    return RedirectResponse(url=presigned_url)
