# Request Submission & Sample Upload - Backend API

## Overview

This module implements the complete request submission and sample upload workflow for the Splunk TA Generator. It allows requestors to create new log onboarding requests, upload sample files, and submit them for approval.

## Request Lifecycle

```
NEW → PENDING_APPROVAL → APPROVED → GENERATING_TA → VALIDATING → COMPLETED/FAILED
```

This phase implements the first transition: **NEW → PENDING_APPROVAL**

## Architecture

### Components

1. **ObjectStorageClient** (`backend/integrations/object_storage_client.py`)
   - Async S3-compatible storage operations using aioboto3
   - Handles file uploads, downloads, deletions, and presigned URLs
   - Integrates with MinIO for on-prem deployment

2. **RequestService** (`backend/services/request_service.py`)
   - Business logic for request lifecycle management
   - Validates file sizes, types, and request states
   - Calculates retention dates and sample previews
   - Enforces authorization rules (REQUESTOR role required)

3. **API Routes** (`backend/api/requests.py`)
   - RESTful endpoints for CRUD operations
   - Streaming file uploads with progress tracking
   - Sample download via presigned URLs

4. **Pydantic Schemas** (`backend/schemas/request.py`)
   - Request/response validation
   - Automatic OpenAPI documentation
   - Type safety across API boundaries

## API Endpoints

### Request Management

#### `POST /api/v1/requests`
Create a new request (status=NEW).

**Request Body:**
```json
{
  "source_system": "Apache Web Server",
  "description": "Ingest Apache access logs from production",
  "cim_required": true,
  "metadata": {"environment": "production"}
}
```

**Response:** `201 Created` with RequestResponse

**Auth:** Requires REQUESTOR role

---

#### `GET /api/v1/requests`
List requests (paginated, filtered by status).

**Query Params:**
- `skip` (int): Number to skip (default: 0)
- `limit` (int): Max results (default: 100, max: 1000)
- `status` (RequestStatus): Filter by status

**Response:** `200 OK` with RequestListResponse

**Auth:** Authenticated user (REQUESTOR sees own, APPROVER/ADMIN see all)

---

#### `GET /api/v1/requests/{request_id}`
Get request details with samples.

**Response:** `200 OK` with RequestDetailResponse

**Auth:** Creator, APPROVER, or ADMIN

---

#### `PUT /api/v1/requests/{request_id}`
Update request metadata (only when status=NEW).

**Response:** `200 OK` with RequestResponse

**Auth:** Creator with REQUESTOR role

---

#### `POST /api/v1/requests/{request_id}/submit`
Submit request for approval (NEW → PENDING_APPROVAL).

**Validation:**
- At least one sample must be attached
- Request must be in NEW status

**Response:** `200 OK` with RequestResponse

**Auth:** Creator with REQUESTOR role

---

### Sample Management

#### `POST /api/v1/requests/{request_id}/samples`
Upload log sample file.

**Request:** `multipart/form-data` with file field

**Constraints:**
- Max file size: 500MB (configurable via `MAX_SAMPLE_SIZE_MB`)
- Max total size per request: 500MB
- Allowed formats: `.log`, `.txt`, `.csv`, `.gz`, `.gzip`, `.zip`, `.json`
- Only allowed when request status=NEW

**Response:** `201 Created` with UploadSampleResponse

**Auth:** Creator with REQUESTOR role

---

#### `GET /api/v1/requests/{request_id}/samples`
List all samples for a request.

**Response:** `200 OK` with SampleListResponse

**Auth:** User with access to request

---

#### `GET /api/v1/requests/{request_id}/samples/{sample_id}`
Get sample details.

**Response:** `200 OK` with SampleResponse

**Auth:** User with access to request

---

#### `GET /api/v1/requests/{request_id}/samples/{sample_id}/download`
Download sample file (redirects to presigned URL, expires in 1 hour).

**Response:** `302 Found` (redirect)

**Auth:** User with access to request

---

#### `DELETE /api/v1/requests/{request_id}/samples/{sample_id}`
Soft delete a sample (only when status=NEW).

**Response:** `204 No Content`

**Auth:** Creator with REQUESTOR role

---

## Configuration

Add these environment variables to `.env`:

```bash
# MinIO / S3 Object Storage
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123
MINIO_BUCKET_SAMPLES=log-samples
MINIO_BUCKET_TAS=ta-artifacts
MINIO_BUCKET_DEBUG=debug-bundles
MINIO_USE_SSL=false
MINIO_REGION=us-east-1

# Sample Retention & Upload Settings
SAMPLE_RETENTION_ENABLED=true
SAMPLE_RETENTION_DAYS=90
MAX_SAMPLE_SIZE_MB=500
UPLOAD_CHUNK_SIZE=1048576
```

## Sample Retention Policy

- **Enabled (`SAMPLE_RETENTION_ENABLED=true`):** Samples stored for `SAMPLE_RETENTION_DAYS` (default: 90)
- **Disabled:** Samples deleted immediately when soft-deleted from request
- Retention date calculated on upload: `retention_until = now() + timedelta(days=SAMPLE_RETENTION_DAYS)`

## Error Handling

Custom exceptions with appropriate HTTP status codes:

- `RequestNotFoundError` → 404
- `SampleNotFoundError` → 404
- `InvalidRequestStateError` → 400 (e.g., trying to upload to non-NEW request)
- `FileSizeExceededError` → 413
- `InvalidFileTypeError` → 400
- `NoSamplesAttachedError` → 400 (on submit without samples)
- `InsufficientPermissionsError` → 403

## Example Workflow (cURL)

```bash
# 1. Create request
REQUEST_ID=$(curl -X POST http://localhost:8000/api/v1/requests \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_system":"Apache","description":"Production logs","cim_required":true}' \
  | jq -r '.id')

# 2. Upload sample
curl -X POST http://localhost:8000/api/v1/requests/$REQUEST_ID/samples \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@apache_access.log"

# 3. Submit for approval
curl -X POST http://localhost:8000/api/v1/requests/$REQUEST_ID/submit \
  -H "Authorization: Bearer $TOKEN"
```

## Testing

```bash
# Install dependencies
pip install -r requirements.txt

# Run backend
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Access API docs
open http://localhost:8000/api/docs
```

## Security

- All endpoints require JWT authentication
- RBAC enforced (REQUESTOR, APPROVER, ADMIN roles)
- File uploads validated (size, type, total quota)
- Ownership checks prevent unauthorized access
- Object storage uses presigned URLs (expire after 1 hour)
- All operations logged with correlation IDs

## Next Steps

Future phases will implement:
- Approval workflow (APPROVER role transitions to APPROVED/REJECTED)
- TA generation (APPROVED → GENERATING_TA → VALIDATING)
- Validation pipeline (ephemeral Splunk containers)
- Manual override uploads
- Debug bundle generation