# Manual TA Override and Re-validation

This document describes the manual TA override feature that allows Splunk experts to upload manually edited TA packages and trigger re-validation.

## Overview

The system supports both auto-generated TAs (via LLM) and manual overrides by Splunk experts. Each TA is versioned (v1, v2, v3, etc.), and all versions are retained with their validation history.

## User Roles

| Role | Permissions |
|------|-------------|
| **APPROVER** | Upload manual TA overrides, trigger re-validation, download TAs and debug bundles |
| **ADMIN** | All APPROVER permissions plus system administration |
| **REQUESTOR** | View TA revisions, download TA packages (for their own requests) |

## Workflow

### 1. View Revision History

Navigate to `/requests/{request_id}/ta-override` to see all TA versions for a request.

The revision history displays:
- Version number (v1, v2, v3, etc.)
- Generation type (Auto-generated or Manual Override)
- Latest validation status (Queued, Running, Passed, Failed)
- File size and creation timestamp
- Expandable validation run details

### 2. Download TA

Click the "Download" button on any revision to get the `.tgz` package. The download is served via a presigned URL that expires in 1 hour.

### 3. Edit Locally

After downloading, extract and modify the TA files locally:
- `inputs.conf` - Input configurations
- `props.conf` - Field extraction properties
- `transforms.conf` - Field transformation rules
- Other TA components as needed

### 4. Upload Override

Drag-and-drop or select the edited `.tgz` file (max 100MB) in the upload form. The system will:
1. Validate the file format and size
2. Create a new TA revision with incremented version number
3. Store the TA in object storage
4. Create a queued validation run

### 5. Automatic Validation

After upload, the system automatically validates the TA in a Splunk sandbox:
1. Launches an ephemeral Splunk container
2. Installs the uploaded TA
3. Ingests sample logs from the request
4. Runs validation searches to check field extraction
5. Produces results with field coverage report

### 6. Review Results

View validation results in the expanded revision details:
- **Pass/Fail status** based on field coverage threshold (70%)
- **Field coverage report** showing extracted vs expected fields
- **Event ingestion count** and any errors
- **CIM compliance results** (if applicable)
- **Debug bundle download** (on failure)

### 7. Re-validate

Trigger re-validation for any existing revision by clicking "Re-validate". This creates a new validation run and re-executes the validation pipeline.

## API Endpoints

### List TA Revisions
```
GET /api/v1/ta/requests/{request_id}/revisions
```

Query parameters:
- `skip` (int): Number of records to skip (default: 0)
- `limit` (int): Maximum records to return (default: 100)

Response:
```json
{
  "items": [
    {
      "id": "uuid",
      "request_id": "uuid",
      "version": 1,
      "storage_key": "tas/{request_id}/v1/ta-source-v1.tgz",
      "storage_bucket": "ta-artifacts",
      "generated_by": "AUTO",
      "generated_by_user": null,
      "file_size": 52428,
      "checksum": "sha256:abc123...",
      "config_summary": {},
      "generation_metadata": {},
      "created_at": "2025-01-17T10:00:00Z",
      "updated_at": "2025-01-17T10:00:00Z",
      "latest_validation_status": "PASSED"
    }
  ],
  "total": 3,
  "skip": 0,
  "limit": 100
}
```

### Get TA Revision Details
```
GET /api/v1/ta/requests/{request_id}/revisions/{version}
```

Returns revision details including all validation runs.

### Download TA Package
```
GET /api/v1/ta/requests/{request_id}/revisions/{version}/download
```

Returns a redirect to a presigned URL (expires in 1 hour).

### Upload Manual Override
```
POST /api/v1/ta/requests/{request_id}/revisions/override
Content-Type: multipart/form-data
```

Form data:
- `file`: TA package file (.tgz or .tar.gz, max 100MB)

Response:
```json
{
  "revision": { ... },
  "validation_run": {
    "id": "uuid",
    "status": "QUEUED",
    ...
  }
}
```

### Trigger Re-validation
```
POST /api/v1/ta/requests/{request_id}/revisions/{revision_id}/revalidate
```

Response:
```json
{
  "validation_run": {
    "id": "uuid",
    "status": "QUEUED",
    ...
  }
}
```

### Download Debug Bundle
```
GET /api/v1/ta/requests/{request_id}/validation-runs/{validation_run_id}/debug-bundle
```

Returns a redirect to a presigned URL for the debug bundle (only available for failed validations).

## Validation Results

Each validation run produces structured results:

```json
{
  "overall_status": "PASSED",
  "field_coverage": 85.5,
  "events_ingested": 1250,
  "cim_compliance": true,
  "extracted_fields": ["timestamp", "src_ip", "dest_ip", "action"],
  "expected_fields": ["timestamp", "src_ip", "dest_ip", "action", "user"],
  "errors": []
}
```

### Pass/Fail Criteria
- **Pass**: Field coverage >= 70% and no critical errors
- **Fail**: Field coverage < 70% or critical extraction errors

## Debug Bundle Contents

When validation fails, a debug bundle is created containing:
- Full generated TA (even if invalid)
- Splunk internal error logs (`_internal` index)
- Validation engine logs
- Search results and field extraction details
- Optional: LLM prompt parameters used for generation

## Audit Logging

All manual override actions are logged for compliance:

| Action | Details Captured |
|--------|------------------|
| Manual TA Upload | User ID, timestamp, file size, version number |
| Re-validation Trigger | User ID, timestamp, revision ID |
| TA Download | User ID, timestamp, version number |
| Debug Bundle Download | User ID, timestamp, validation run ID |

## File Requirements

| Requirement | Value |
|-------------|-------|
| **Format** | `.tgz` or `.tar.gz` |
| **Max Size** | 100MB (configurable via `MAX_TA_FILE_SIZE_MB`) |
| **Structure** | Standard Splunk TA directory structure |

### Expected TA Structure
```
TA-{name}/
├── app.conf
├── default/
│   ├── inputs.conf
│   ├── props.conf
│   └── transforms.conf
├── metadata/
│   └── default.meta
└── README.txt (optional)
```

## Configuration

Environment variables:
- `MAX_TA_FILE_SIZE_MB`: Maximum TA file size in MB (default: 100)

## Troubleshooting

### Upload Fails

1. **File too large**: Ensure file is under 100MB
2. **Invalid extension**: Must be `.tgz` or `.tar.gz`
3. **Invalid state**: Request must be in APPROVED, GENERATING_TA, VALIDATING, COMPLETED, or FAILED state

### Validation Fails

1. Download the debug bundle for detailed error logs
2. Check Splunk internal logs for parsing errors
3. Verify field extraction regex patterns
4. Ensure sample logs match expected format

### Re-validation Stuck

1. Check Celery worker logs for errors
2. Verify validation queue is processing
3. Check for resource constraints on Splunk sandbox containers

## Frontend Components

| Component | Path | Description |
|-----------|------|-------------|
| TAOverride | `/pages/TAOverride/index.tsx` | Main page component |
| RevisionHistory | `/pages/TAOverride/RevisionHistory.tsx` | Revision list with actions |
| UploadOverrideForm | `/pages/TAOverride/UploadOverrideForm.tsx` | File upload form |
| ValidationResults | `/pages/TAOverride/ValidationResults.tsx` | Validation run details |

## Backend Components

| Component | Path | Description |
|-----------|------|-------------|
| TA Router | `/api/ta.py` | API endpoints |
| TAGenerationService | `/services/ta_generation_service.py` | Business logic |
| TA Schemas | `/schemas/ta.py` | Pydantic models |
| Exceptions | `/core/exceptions.py` | TA-specific errors |
