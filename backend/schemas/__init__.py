# Schemas package

# Auth schemas
from backend.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
)

# Request schemas
from backend.schemas.request import (
    CreateRequestRequest,
    UpdateRequestRequest,
    RequestResponse,
    RequestListResponse,
    RequestDetailResponse,
    SampleResponse,
    SampleListResponse,
    UploadSampleResponse,
)

# Approval schemas
from backend.schemas.approval import (
    ApproveRequestRequest,
    RejectRequestRequest,
    ApprovalResponse,
    PendingApprovalListResponse,
    ApprovalStatisticsResponse,
)

__all__ = [
    # Auth
    "LoginRequest",
    "RegisterRequest",
    "TokenResponse",
    "UserResponse",
    # Requests
    "CreateRequestRequest",
    "UpdateRequestRequest",
    "RequestResponse",
    "RequestListResponse",
    "RequestDetailResponse",
    "SampleResponse",
    "SampleListResponse",
    "UploadSampleResponse",
    # Approvals
    "ApproveRequestRequest",
    "RejectRequestRequest",
    "ApprovalResponse",
    "PendingApprovalListResponse",
    "ApprovalStatisticsResponse",
]
