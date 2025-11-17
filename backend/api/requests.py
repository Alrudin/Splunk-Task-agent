"""
FastAPI routes for request and sample operations.

This module provides RESTful API endpoints for:
- Creating and managing requests
- Uploading and downloading log samples
- Submitting requests for approval
"""
from typing import Optional
from uuid import UUID

import structlog
from fastapi import (
    APIRouter,
    Depends,
    File,
    Query,
    UploadFile,
    status as http_status,
)
from fastapi.responses import RedirectResponse

from backend.core.dependencies import (
    get_current_active_user,
    get_request_service,
    get_sample_repository,
    get_storage_client,
    require_role,
)
from backend.integrations.object_storage_client import ObjectStorageClient
from backend.models.enums import RequestStatus, UserRoleEnum
from backend.models.user import User
from backend.repositories.log_sample_repository import LogSampleRepository
from backend.schemas.request import (
    CreateRequestRequest,
    RequestDetailResponse,
    RequestListResponse,
    RequestResponse,
    SampleListResponse,
    SampleResponse,
    UpdateRequestRequest,
    UploadSampleResponse,
)
from backend.services.request_service import RequestService

logger = structlog.get_logger(__name__)

# Create router
router = APIRouter(prefix="/requests", tags=["Requests"])


@router.post(
    "",
    response_model=RequestResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Create new request",
    description="Create a new log onboarding request. Requires REQUESTOR role.",
)
async def create_request(
    data: CreateRequestRequest,
    current_user: User = Depends(require_role(UserRoleEnum.REQUESTOR)),
    service: RequestService = Depends(get_request_service),
) -> RequestResponse:
    """
    Create a new request.

    The request is created with status=NEW and can be updated before submission.

    **Required role:** REQUESTOR
    """
    log = logger.bind(user_id=str(current_user.id), source_system=data.source_system)
    log.info("api_create_request")

    request = await service.create_request(
        source_system=data.source_system,
        description=data.description,
        cim_required=data.cim_required,
        metadata=data.metadata,
        current_user=current_user,
    )

    # Calculate sample stats for response
    samples = await service.get_samples(request.id, current_user)
    response = RequestResponse.model_validate(request)
    response.sample_count = len(samples)
    response.total_sample_size = sum(s.file_size for s in samples)

    return response


@router.get(
    "",
    response_model=RequestListResponse,
    summary="List requests",
    description="List requests for current user. Approvers and admins see all requests.",
)
async def list_requests(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum records to return"),
    status: Optional[RequestStatus] = Query(None, description="Filter by status"),
    current_user: User = Depends(get_current_active_user),
    service: RequestService = Depends(get_request_service),
    sample_repo: LogSampleRepository = Depends(get_sample_repository),
) -> RequestListResponse:
    """
    List requests with pagination.

    - Regular users see only their own requests
    - Approvers and admins see all requests

    **Required role:** Authenticated user
    """
    log = logger.bind(user_id=str(current_user.id), skip=skip, limit=limit)
    log.info("api_list_requests")

    requests, total = await service.list_user_requests(
        current_user=current_user,
        skip=skip,
        limit=limit,
        status=status,
    )

    # Get aggregated sample stats for all requests in a single query
    request_ids = [request.id for request in requests]
    stats_by_request = await sample_repo.get_aggregated_stats_by_requests(request_ids)

    # Build response items with stats
    items = []
    for request in requests:
        response = RequestResponse.model_validate(request)
        stats = stats_by_request.get(request.id, {"count": 0, "total_size": 0})
        response.sample_count = stats["count"]
        response.total_sample_size = stats["total_size"]
        items.append(response)

    return RequestListResponse(
        items=items,
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/{request_id}",
    response_model=RequestDetailResponse,
    summary="Get request details",
    description="Get detailed information about a specific request including samples.",
)
async def get_request(
    request_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: RequestService = Depends(get_request_service),
) -> RequestDetailResponse:
    """
    Get request details with related entities.

    Returns request with all attached samples.

    **Required role:** Authenticated user (must be creator, approver, or admin)
    """
    log = logger.bind(user_id=str(current_user.id), request_id=str(request_id))
    log.info("api_get_request")

    request = await service.get_request(request_id, current_user)
    samples = await service.get_samples(request_id, current_user)

    # Build response
    response = RequestDetailResponse.model_validate(request)
    response.samples = [SampleResponse.model_validate(s) for s in samples]
    response.sample_count = len(samples)
    response.total_sample_size = sum(s.file_size for s in samples)

    return response


@router.put(
    "/{request_id}",
    response_model=RequestResponse,
    summary="Update request",
    description="Update request metadata. Only allowed when status=NEW.",
)
async def update_request(
    request_id: UUID,
    data: UpdateRequestRequest,
    current_user: User = Depends(require_role(UserRoleEnum.REQUESTOR)),
    service: RequestService = Depends(get_request_service),
) -> RequestResponse:
    """
    Update request metadata.

    Only the request creator can update, and only when status=NEW.

    **Required role:** REQUESTOR (must be creator)
    """
    log = logger.bind(user_id=str(current_user.id), request_id=str(request_id))
    log.info("api_update_request")

    request = await service.update_request(
        request_id=request_id,
        current_user=current_user,
        source_system=data.source_system,
        description=data.description,
        cim_required=data.cim_required,
        metadata=data.metadata,
    )

    # Calculate sample stats
    samples = await service.get_samples(request_id, current_user)
    response = RequestResponse.model_validate(request)
    response.sample_count = len(samples)
    response.total_sample_size = sum(s.file_size for s in samples)

    return response


@router.post(
    "/{request_id}/samples",
    response_model=UploadSampleResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Upload log sample",
    description="Upload a log sample file. Max size: 500MB. Allowed types: text, gzip, zip.",
)
async def upload_sample(
    request_id: UUID,
    file: UploadFile = File(..., description="Log sample file"),
    current_user: User = Depends(require_role(UserRoleEnum.REQUESTOR)),
    service: RequestService = Depends(get_request_service),
) -> UploadSampleResponse:
    """
    Upload a log sample file.

    **Constraints:**
    - Max file size: 500MB (configurable)
    - Max total size per request: 500MB
    - Allowed formats: .log, .txt, .csv, .gz, .gzip, .zip, .json
    - Only allowed when request status=NEW

    **Required role:** REQUESTOR (must be creator)
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
        filename=file.filename,
    )
    log.info("api_upload_sample")

    sample = await service.upload_sample(
        request_id=request_id,
        file=file,
        current_user=current_user,
    )

    return UploadSampleResponse(
        sample=SampleResponse.model_validate(sample),
        upload_url=None,  # Not generating presigned URL for upload response
    )


@router.get(
    "/{request_id}/samples",
    response_model=SampleListResponse,
    summary="List samples",
    description="List all samples attached to a request.",
)
async def list_samples(
    request_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: RequestService = Depends(get_request_service),
) -> SampleListResponse:
    """
    List all samples for a request.

    **Required role:** Authenticated user (must have access to request)
    """
    log = logger.bind(user_id=str(current_user.id), request_id=str(request_id))
    log.info("api_list_samples")

    samples = await service.get_samples(request_id, current_user)

    return SampleListResponse(
        items=[SampleResponse.model_validate(s) for s in samples],
        total=len(samples),
    )


@router.get(
    "/{request_id}/samples/{sample_id}",
    response_model=SampleResponse,
    summary="Get sample details",
    description="Get details about a specific sample.",
)
async def get_sample(
    request_id: UUID,
    sample_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: RequestService = Depends(get_request_service),
) -> SampleResponse:
    """
    Get sample details.

    **Required role:** Authenticated user (must have access to request)
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
        sample_id=str(sample_id),
    )
    log.info("api_get_sample")

    sample = await service.get_sample(request_id, sample_id, current_user)

    return SampleResponse.model_validate(sample)


@router.get(
    "/{request_id}/samples/{sample_id}/download",
    summary="Download sample",
    description="Download a sample file. Returns redirect to presigned URL.",
)
async def download_sample(
    request_id: UUID,
    sample_id: UUID,
    current_user: User = Depends(get_current_active_user),
    service: RequestService = Depends(get_request_service),
    storage: ObjectStorageClient = Depends(get_storage_client),
) -> RedirectResponse:
    """
    Download sample file.

    Returns a redirect to a presigned URL that expires in 1 hour.

    **Required role:** Authenticated user (must have access to request)
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
        sample_id=str(sample_id),
    )
    log.info("api_download_sample")

    sample = await service.get_sample(request_id, sample_id, current_user)

    # Generate presigned URL (expires in 1 hour)
    presigned_url = await storage.generate_presigned_url(
        bucket=sample.storage_bucket,
        key=sample.storage_key,
        expires_in=3600,
    )

    return RedirectResponse(url=presigned_url)


@router.delete(
    "/{request_id}/samples/{sample_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Delete sample",
    description="Delete a sample. Only allowed when request status=NEW.",
)
async def delete_sample(
    request_id: UUID,
    sample_id: UUID,
    current_user: User = Depends(require_role(UserRoleEnum.REQUESTOR)),
    service: RequestService = Depends(get_request_service),
) -> None:
    """
    Delete (soft delete) a sample.

    Only the request creator can delete samples, and only when status=NEW.

    **Required role:** REQUESTOR (must be creator)
    """
    log = logger.bind(
        user_id=str(current_user.id),
        request_id=str(request_id),
        sample_id=str(sample_id),
    )
    log.info("api_delete_sample")

    await service.delete_sample(request_id, sample_id, current_user)


@router.post(
    "/{request_id}/submit",
    response_model=RequestResponse,
    summary="Submit for approval",
    description="Submit request for approval. Transitions status from NEW to PENDING_APPROVAL.",
)
async def submit_request(
    request_id: UUID,
    current_user: User = Depends(require_role(UserRoleEnum.REQUESTOR)),
    service: RequestService = Depends(get_request_service),
) -> RequestResponse:
    """
    Submit request for approval.

    **Requirements:**
    - Request must be in NEW status
    - At least one sample must be attached
    - Only request creator can submit

    **Status transition:** NEW → PENDING_APPROVAL

    **Required role:** REQUESTOR (must be creator)
    """
    log = logger.bind(user_id=str(current_user.id), request_id=str(request_id))
    log.info("api_submit_request")

    request = await service.submit_for_approval(request_id, current_user)

    # Calculate sample stats
    samples = await service.get_samples(request_id, current_user)
    response = RequestResponse.model_validate(request)
    response.sample_count = len(samples)
    response.total_sample_size = sum(s.file_size for s in samples)

    return response