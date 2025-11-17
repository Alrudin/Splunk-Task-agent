# Integrations Module

This module provides client classes for external service integrations used by the AI-Assisted Splunk TA Generator.

## Overview

The integrations module implements the following service clients:

- **Object Storage (MinIO/S3)**: For storing log samples, TA bundles, and debug artifacts
- **Vector Database (Pinecone)**: For RAG knowledge retrieval *(planned)*
- **LLM Runtime (Ollama)**: For TA generation *(planned)*
- **Splunk Sandbox**: For validation orchestration *(planned)*

Each integration is implemented as a standalone client with configuration management, comprehensive error handling, and async support for FastAPI integration.

## Object Storage Client

### Quick Start

```python
from backend.integrations import ObjectStorageClient, StorageConfig

# Initialize client from environment variables
client = ObjectStorageClient()

# Or with explicit configuration
config = StorageConfig.from_env()
client = ObjectStorageClient(config)

# Initialize buckets (first-time setup)
results = client.initialize_buckets()

# Upload log sample
with open("sample.log", "rb") as f:
    storage_key = client.upload_log_sample(
        request_id=request_uuid,
        file_stream=f,
        filename="sample.log",
        metadata={"user_id": str(user_uuid)}
    )

# Generate presigned URL for download
download_url = client.get_log_sample_presigned_url(
    storage_key=storage_key,
    expiration=3600  # 1 hour
)

# Download directly
content = client.download_log_sample(storage_key)

# List samples for a request
samples = client.list_log_samples(request_id=request_uuid)
```

### Configuration

The object storage client is configured via environment variables in `.env`:

#### Required Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `MINIO_ENDPOINT` | MinIO/S3 endpoint URL | `localhost:9000` |
| `MINIO_ACCESS_KEY` | Access key ID | `minioadmin` |
| `MINIO_SECRET_KEY` | Secret access key | `minioadmin` |
| `MINIO_BUCKET_SAMPLES` | Bucket for log samples | `log-samples` |
| `MINIO_BUCKET_TAS` | Bucket for TA bundles | `ta-artifacts` |
| `MINIO_BUCKET_DEBUG` | Bucket for debug bundles | `debug-bundles` |

#### Optional Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIO_USE_SSL` | `false` | Enable SSL/TLS |
| `MINIO_REGION` | `us-east-1` | AWS region |
| `SAMPLE_RETENTION_ENABLED` | `true` | Enable retention cleanup |
| `SAMPLE_RETENTION_DAYS` | `30` | Days to retain samples |
| `MINIO_MAX_UPLOAD_SIZE_MB` | `500` | Max upload size |
| `MINIO_PRESIGNED_URL_EXPIRATION` | `3600` | Presigned URL expiration (seconds) |
| `MINIO_MULTIPART_THRESHOLD_MB` | `5` | Multipart upload threshold |
| `MINIO_MULTIPART_CHUNK_SIZE_MB` | `5` | Multipart chunk size |
| `MINIO_CONNECTION_TIMEOUT` | `30` | Connection timeout (seconds) |
| `MINIO_READ_TIMEOUT` | `60` | Read timeout (seconds) |

### API Reference

#### Log Sample Operations

**`upload_log_sample(request_id, file_stream, filename, content_type, metadata)`**
- Uploads a log sample to storage
- Validates file size (max 500MB by default)
- Returns storage key for future retrieval
- Raises `StorageQuotaExceededError` if file too large

**`download_log_sample(storage_key)`**
- Downloads log sample by storage key
- Returns file contents as bytes
- Raises `StorageNotFoundError` if not found

**`get_log_sample_presigned_url(storage_key, expiration)`**
- Generates presigned URL for secure download
- Default expiration: 1 hour (configurable)
- Use for client-side downloads without exposing credentials

**`delete_log_sample(storage_key)`**
- Deletes log sample from storage
- Used by retention cleanup
- Returns True on success

**`list_log_samples(request_id)`**
- Lists all samples for a request
- Returns list with metadata (size, last modified, custom metadata)

#### TA Bundle Operations

**`upload_ta_bundle(request_id, revision_id, file_stream, version, metadata)`**
- Uploads TA bundle (.tgz)
- Storage key format: `tas/{request_id}/v{version}/{revision_id}.tgz`
- Returns storage key

**`download_ta_bundle(storage_key)`**
- Downloads TA bundle
- Returns bundle contents as bytes

**`get_ta_bundle_presigned_url(storage_key, expiration)`**
- Generates presigned URL for TA download

**`list_ta_revisions(request_id)`**
- Lists all TA versions for a request

#### Debug Bundle Operations

**`upload_debug_bundle(validation_run_id, file_stream, filename, metadata)`**
- Uploads debug bundle (.zip)
- Contains validation failure diagnostics
- Returns storage key

**`download_debug_bundle(storage_key)`**
- Downloads debug bundle

**`get_debug_bundle_presigned_url(storage_key, expiration)`**
- Generates presigned URL for debug bundle download

#### Retention & Cleanup

**`cleanup_expired_samples()`**
- Deletes samples older than `SAMPLE_RETENTION_DAYS`
- Only runs if `SAMPLE_RETENTION_ENABLED=true`
- Returns count of deleted samples
- Schedule via cron for automated cleanup

**`get_storage_stats()`**
- Returns statistics for all buckets
- Total objects, total size, oldest/newest objects
- Use for monitoring and capacity planning

### Error Handling

The client raises custom exceptions with context data:

```python
from backend.integrations.storage_exceptions import (
    StorageConnectionError,     # Cannot connect to storage
    StorageUploadError,         # Upload failed
    StorageDownloadError,       # Download failed
    StorageNotFoundError,       # Object not found (404)
    StorageBucketError,         # Bucket operation failed
    StorageRetentionError,      # Retention cleanup failed
    StorageQuotaExceededError,  # File too large (413)
)

try:
    storage_key = client.upload_log_sample(...)
except StorageQuotaExceededError as e:
    print(f"File too large: {e.message}")
    print(f"Context: {e.context}")
    print(f"HTTP status: {e.status_code}")  # 413
except StorageUploadError as e:
    print(f"Upload failed: {e}")
```

All exceptions include:
- Human-readable message
- Original exception (if applicable)
- Context dictionary (bucket, key, operation, etc.)
- HTTP status code for API responses

### Usage Examples

#### FastAPI Integration

```python
from fastapi import APIRouter, Depends, UploadFile, HTTPException
from backend.core.dependencies import get_storage_client
from backend.integrations import ObjectStorageClient, StorageQuotaExceededError

router = APIRouter()

@router.post("/upload")
async def upload_sample(
    request_id: UUID,
    file: UploadFile,
    storage: ObjectStorageClient = Depends(get_storage_client)
):
    """Upload log sample with automatic dependency injection."""
    try:
        storage_key = storage.upload_log_sample(
            request_id=request_id,
            file_stream=file.file,
            filename=file.filename,
            content_type=file.content_type
        )
        return {"storage_key": storage_key}
    except StorageQuotaExceededError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)

@router.get("/download/{storage_key}")
async def get_download_url(
    storage_key: str,
    storage: ObjectStorageClient = Depends(get_storage_client)
):
    """Generate presigned URL for client-side download."""
    url = storage.get_log_sample_presigned_url(storage_key)
    return {"download_url": url}
```

#### Celery Background Task

```python
from celery import shared_task
from backend.integrations import ObjectStorageClient

@shared_task
def generate_ta_bundle(request_id: UUID, revision_id: UUID):
    """Generate TA bundle in background."""
    client = ObjectStorageClient()

    # Generate bundle (implementation details omitted)
    bundle_data = generate_bundle_logic(request_id)

    # Upload to storage
    storage_key = client.upload_ta_bundle(
        request_id=request_id,
        revision_id=revision_id,
        file_stream=bundle_data,
        version=1,
        metadata={"generated_by": "AI"}
    )

    return storage_key
```

#### Async Usage

```python
from backend.core.dependencies import storage_client_context

async def process_upload():
    """Use async context manager for proper resource cleanup."""
    async with storage_client_context() as storage:
        storage_key = storage.upload_log_sample(...)
        # Client automatically cleaned up after this block
```

### Bucket Structure

The system uses three separate buckets for artifact isolation:

**`log-samples` bucket:**
```
samples/{request_id}/{filename}
```

**`ta-artifacts` bucket:**
```
tas/{request_id}/v{version}/{revision_id}.tgz
```

**`debug-bundles` bucket:**
```
debug/{validation_run_id}/{filename}
```

### Retention Policy

The retention policy is configurable and applies to log samples:

1. **Enabled**: Set `SAMPLE_RETENTION_ENABLED=true` in `.env`
2. **Period**: Configure retention days with `SAMPLE_RETENTION_DAYS`
3. **Cleanup**: Run manually via script or schedule with cron
4. **Audit**: All deletions are logged with structured logging

TA bundles and debug bundles are NOT subject to automatic retention cleanup - they must be deleted explicitly via the API.

### Maintenance

#### Initialize Storage Buckets

After starting docker-compose services, initialize the storage buckets:

```bash
# From project root
python -m backend.scripts.init_storage

# Verify connectivity only
python -m backend.scripts.init_storage --verify-only

# Force recreate buckets
python -m backend.scripts.init_storage --force
```

#### Run Retention Cleanup

Execute cleanup manually or via cron:

```bash
# Preview cleanup (dry run)
python -m backend.scripts.cleanup_storage cleanup all --dry-run

# Execute cleanup
python -m backend.scripts.cleanup_storage cleanup all

# Clean only expired samples
python -m backend.scripts.cleanup_storage cleanup samples

# Generate detailed report
python -m backend.scripts.cleanup_storage cleanup all --report cleanup_report.json
```

#### Schedule Automated Cleanup

Add to crontab for automated cleanup:

```cron
# Run daily at 2 AM
0 2 * * * cd /app && python -m backend.scripts.cleanup_storage cleanup all
```

#### Monitor Storage Usage

```python
client = ObjectStorageClient()
stats = client.get_storage_stats()

for bucket_type, data in stats.items():
    print(f"{bucket_type}:")
    print(f"  Objects: {data['total_objects']}")
    print(f"  Size: {data['total_size_formatted']}")
```

### Testing

#### Local MinIO (docker-compose)

The system includes MinIO in `docker-compose.yml`:

```yaml
services:
  minio:
    image: minio/minio
    ports:
      - "9000:9000"  # API
      - "9001:9001"  # Console
    environment:
      MINIO_ROOT_USER: minioadmin
      MINIO_ROOT_PASSWORD: minioadmin
```

Access MinIO console at http://localhost:9001

#### Unit Testing with Mocks

```python
import pytest
from unittest.mock import Mock, patch
from backend.integrations import ObjectStorageClient

def test_upload_log_sample():
    """Test log sample upload with mocked S3 client."""
    with patch('boto3.client') as mock_boto:
        mock_s3 = Mock()
        mock_boto.return_value = mock_s3

        client = ObjectStorageClient()
        storage_key = client.upload_log_sample(...)

        assert mock_s3.upload_fileobj.called
```

#### AWS S3 Testing

To test with AWS S3 instead of MinIO:

```bash
# Update .env
MINIO_ENDPOINT=s3.amazonaws.com
MINIO_USE_SSL=true
MINIO_ACCESS_KEY=<your-aws-access-key>
MINIO_SECRET_KEY=<your-aws-secret-key>
```

### Security

#### Credential Management

- Store credentials in `.env` file (never commit to git)
- Use Kubernetes secrets in production deployments
- Rotate credentials regularly
- Use IAM roles when running on AWS

#### Presigned URLs

- Default expiration: 1 hour (configurable)
- URLs are time-limited and cannot be extended
- Generate new URLs if expired
- URLs grant temporary access without exposing credentials
- Consider shorter expiration for sensitive data

#### Bucket Policies

All buckets are private by default. Access is granted via:
- AWS/MinIO credentials for server-side operations
- Presigned URLs for client-side downloads

Recommended MinIO policy (applied automatically):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"AWS": ["*"]},
      "Action": ["s3:GetObject"],
      "Resource": ["arn:aws:s3:::log-samples/*"],
      "Condition": {
        "StringLike": {"s3:prefix": ["samples/*"]}
      }
    }
  ]
}
```

#### Audit Logging

All storage operations are logged with structured logging:

```json
{
  "event": "log_sample_uploaded",
  "request_id": "uuid",
  "storage_key": "samples/uuid/file.log",
  "timestamp": "2025-01-15T10:30:00Z",
  "user_id": "uuid"
}
```

Enable audit logging:
```bash
ENABLE_AUDIT_LOGGING=true
AUDIT_LOG_RETENTION_DAYS=365
```

### Troubleshooting

#### Connection Errors

**Symptom**: `StorageConnectionError: Failed to connect to object storage`

**Solutions**:
1. Verify MinIO/S3 service is running: `docker-compose ps`
2. Check `MINIO_ENDPOINT` in `.env` file
3. Test network connectivity: `curl http://localhost:9000`
4. Check firewall rules

#### Bucket Permission Errors

**Symptom**: `StorageBucketError: Bucket operation failed`

**Solutions**:
1. Verify `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY`
2. Check bucket permissions in MinIO console
3. Try `--force` flag to recreate buckets

#### Upload Failures

**Symptom**: `StorageUploadError: Failed to upload object to storage`

**Solutions**:
1. Check file size limits (`MAX_SAMPLE_SIZE_MB`)
2. Verify bucket exists and is accessible
3. Check disk space on MinIO server
4. Review structured logs for detailed error

#### Presigned URL Expiration

**Symptom**: URLs return 403 Forbidden

**Solutions**:
1. Generate new presigned URL
2. Adjust `MINIO_PRESIGNED_URL_EXPIRATION` if needed
3. Verify system clocks are synchronized

## Future Integrations

### Vector Database (Pinecone)

*Coming soon* - Client for RAG knowledge retrieval

### LLM Runtime (Ollama)

*Coming soon* - Client for TA generation

### Splunk Sandbox

*Coming soon* - Orchestration client for validation containers
