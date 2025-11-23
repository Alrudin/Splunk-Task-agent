# Splunk Validation Infrastructure

This document describes the Splunk sandbox orchestration and validation pipeline for the AI-Assisted Splunk TA Generator.

## Overview

The validation infrastructure automatically validates generated TAs by:
1. Launching ephemeral Splunk Enterprise containers
2. Installing the generated TA
3. Ingesting sample logs
4. Running validation searches
5. Generating field coverage reports
6. Creating debug bundles on failure

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  TA Generation  │────▶│  Validation Task │────▶│  Request Status │
│      Task       │     │    (Celery)      │     │   COMPLETED/    │
└─────────────────┘     └────────┬─────────┘     │     FAILED      │
                                 │               └─────────────────┘
                                 ▼
                        ┌────────────────┐
                        │ Validation     │
                        │ Service        │
                        └───────┬────────┘
                                │
         ┌──────────────────────┼──────────────────────┐
         ▼                      ▼                      ▼
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐
│ SplunkSandbox   │   │ Object Storage  │   │   Database      │
│ Client (Docker) │   │ (MinIO)         │   │  (PostgreSQL)   │
└────────┬────────┘   └─────────────────┘   └─────────────────┘
         │
         ▼
┌─────────────────┐
│ Ephemeral       │
│ Splunk Container│
└─────────────────┘
```

## Components

### SplunkSandboxClient (`backend/integrations/splunk_sandbox_client.py`)

Orchestrates Docker container lifecycle for Splunk Enterprise instances:

- **Container Management**: Create, start, stop, and cleanup Splunk containers
- **TA Installation**: Copy and install TAs via container exec
- **Log Ingestion**: Ingest sample files using Splunk's oneshot command
- **Search Execution**: Run SPL searches via Splunk REST API
- **Log Collection**: Retrieve splunkd.log, metrics.log, and TA-specific logs

### ValidationService (`backend/services/validation_service.py`)

High-level validation workflow orchestration:

- **Validation Workflow**: Coordinates sandbox creation, TA installation, and testing
- **Search Execution**: Runs validation searches (ingestion, timestamp, field extraction)
- **Field Coverage Analysis**: Compares extracted fields against expected fields
- **Report Generation**: Creates structured validation reports
- **Debug Bundle Creation**: Packages artifacts for troubleshooting failures

### validate_ta_task (`backend/tasks/validate_ta_task.py`)

Celery task for asynchronous validation:

- **Concurrency Control**: Limits parallel validations via configurable setting
- **Status Management**: Updates ValidationRun and Request status
- **Error Handling**: Graceful failure handling with status updates
- **Task Monitoring**: Reports progress via Celery task states

## Validation Workflow

### Status Transitions

```
Request Status:
APPROVED → GENERATING_TA → VALIDATING → COMPLETED
                                     ↘ FAILED

ValidationRun Status:
QUEUED → RUNNING → PASSED
                 ↘ FAILED
```

### Workflow Steps

1. **TA Generation Task** creates a TARevision and enqueues validation
2. **Validation Task** checks concurrency limits (requeues if exceeded)
3. **Create Sandbox**: Launch Splunk Enterprise container
4. **Wait for Ready**: Poll REST API until Splunk services are available
5. **Install TA**: Copy tarball, extract, restart Splunk
6. **Create Index**: Create test index for validation
7. **Ingest Samples**: Load sample files via oneshot command
8. **Wait for Indexing**: Ensure events are indexed
9. **Execute Searches**: Run validation searches
10. **Analyze Results**: Calculate field coverage
11. **Generate Report**: Create validation report
12. **Update Status**: Mark as PASSED or FAILED
13. **Create Debug Bundle**: On failure, package all artifacts
14. **Cleanup**: Remove container and temp files

## Validation Criteria

### PASSED Conditions

- Events successfully indexed (count > 0)
- Timestamp parsed correctly (_time field present)
- Field coverage >= 70% (configurable via `VALIDATION_FIELD_COVERAGE_THRESHOLD`)
- No critical Splunk errors in logs

### FAILED Conditions

- Zero events indexed
- Timestamp parsing failed
- Field coverage < threshold
- TA installation errors
- Splunk container crashes

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SPLUNK_IMAGE` | `splunk/splunk:9.1.0` | Docker image for Splunk containers |
| `SPLUNK_STARTUP_TIMEOUT` | `300` | Container startup timeout (seconds) |
| `SPLUNK_ADMIN_PASSWORD` | `admin123` | Splunk admin password |
| `SPLUNK_MANAGEMENT_PORT_RANGE_START` | `18089` | Port range start |
| `SPLUNK_MANAGEMENT_PORT_RANGE_END` | `18189` | Port range end |
| `DOCKER_NETWORK` | `splunk-ta-network` | Docker network name |
| `MAX_PARALLEL_VALIDATIONS` | `3` | Max concurrent validations |
| `VALIDATION_TIMEOUT` | `1800` | Overall timeout (30 min) |
| `VALIDATION_RETRY_DELAY` | `60` | Retry delay (seconds) |
| `VALIDATION_INDEX_NAME` | `ta_validation_test` | Test index name |
| `VALIDATION_FIELD_COVERAGE_THRESHOLD` | `0.7` | Min coverage (0.0-1.0) |

### Recommended Settings by Environment

**Development:**
```bash
MAX_PARALLEL_VALIDATIONS=2
VALIDATION_TIMEOUT=1200
SPLUNK_STARTUP_TIMEOUT=180
```

**Production:**
```bash
MAX_PARALLEL_VALIDATIONS=5
VALIDATION_TIMEOUT=1800
SPLUNK_STARTUP_TIMEOUT=300
SPLUNK_ADMIN_PASSWORD=<strong-password>
```

## Debug Bundles

When validation fails, a debug bundle is created containing:

```
debug-bundle-{validation_run_id}/
├── ta.tgz                    # Original TA tarball
├── validation_report.json    # Detailed validation results
├── error_summary.txt         # Human-readable error summary
└── logs/
    ├── splunkd.log          # Splunk daemon logs
    └── {ta_name}.log        # TA-specific logs (if any)
```

### Accessing Debug Bundles

Debug bundles are stored in MinIO under the `debug-bundles` bucket:
- Key format: `debug/{request_id}/{validation_run_id}.zip`
- Download via: `/ta/{request_id}/debug/{validation_run_id}`

## Monitoring

### Celery Flower Dashboard

Access the Flower dashboard at `http://localhost:5555` to monitor:
- Active workers and their status
- Task queues (default, ta_generation, validation)
- Task history and results
- Worker resource usage

### Structured Logs

All operations are logged with structlog using correlation IDs:
- `validation_run_id`: Unique identifier for each validation
- `container_id`: Docker container ID (truncated)
- `ta_name`: Name of the TA being validated

Example log entry:
```json
{
  "event": "validation_searches_complete",
  "validation_run_id": "550e8400-e29b-41d4-a716-446655440000",
  "container_id": "abc123def456",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Key Metrics to Monitor

- **Validation success rate**: `PASSED / (PASSED + FAILED)`
- **Average validation duration**: Time from QUEUED to completion
- **Concurrency utilization**: Running validations / max allowed
- **Common failure reasons**: Group by error type

## Troubleshooting

### Common Issues

#### Splunk Container Startup Failure

**Symptoms:** Container exits immediately or times out waiting for ready

**Solutions:**
1. Check Docker logs: `docker logs splunk-validation-{id}`
2. Verify Docker has sufficient resources (RAM, CPU)
3. Ensure Splunk image is available: `docker pull splunk/splunk:9.1.0`
4. Check network connectivity to Docker daemon

#### TA Installation Errors

**Symptoms:** TA not found after installation

**Solutions:**
1. Verify TA tarball structure (top-level directory must match TA name)
2. Check for extraction errors in debug bundle logs
3. Ensure Splunk user has write permissions to apps directory

#### Search Execution Timeouts

**Symptoms:** Searches fail or return empty results

**Solutions:**
1. Increase `VALIDATION_TIMEOUT` if needed
2. Check if indexing is complete before searching
3. Verify index exists and has correct permissions

#### Field Extraction Issues

**Symptoms:** Low field coverage despite correct props.conf

**Solutions:**
1. Check sourcetype assignment in sample ingestion
2. Verify EXTRACT/REPORT stanzas in transforms.conf
3. Review sample events in debug bundle

#### Docker Socket Permission Errors

**Symptoms:** "Permission denied" when creating containers

**Solutions:**
1. Ensure Docker socket is mounted: `-v /var/run/docker.sock:/var/run/docker.sock`
2. Add user to docker group: `usermod -aG docker $USER`
3. Check socket permissions: `ls -la /var/run/docker.sock`

### Manual Testing

To manually test validation:

```python
import asyncio
from backend.integrations.splunk_sandbox_client import SplunkSandboxClient

async def test_sandbox():
    client = SplunkSandboxClient()

    # Create sandbox
    sandbox = await client.create_sandbox("test-123")
    print(f"Container: {sandbox['container_id']}")

    # Wait for ready
    await client.wait_for_ready(
        sandbox['container_id'],
        sandbox['management_port']
    )

    # Run test search
    results = await client.execute_search(
        sandbox['container_id'],
        "search index=_internal | head 5",
        sandbox['management_port']
    )
    print(f"Results: {results}")

    # Cleanup
    await client.cleanup_sandbox(sandbox['container_id'])

asyncio.run(test_sandbox())
```

## Development

### Running Validation Locally

1. Start infrastructure:
```bash
docker-compose up -d postgres redis minio
```

2. Start validation worker:
```bash
celery -A backend.tasks.celery_app worker --loglevel=debug --queues=validation
```

3. Submit test validation (via API or directly):
```python
from backend.tasks.validate_ta_task import validate_ta_task

validate_ta_task.apply_async(
    args=["validation-run-id", "ta-revision-id", "request-id"],
    queue="validation"
)
```

### Adding New Validation Checks

To add a new validation check:

1. Add search query in `ValidationService.execute_validation_searches()`
2. Add analysis logic in `ValidationService.analyze_field_coverage()` if needed
3. Update `ValidationService.generate_validation_report()` to include new check
4. Update pass/fail criteria if the check is critical

### Testing with Sample TAs

Create a minimal test TA:
```bash
mkdir -p TA-test/default
echo '[source::test]
TIME_FORMAT = %Y-%m-%d %H:%M:%S
SHOULD_LINEMERGE = false' > TA-test/default/props.conf
tar -czvf TA-test.tgz TA-test/
```

## Production Deployment

### Scaling Validation Workers

For high-throughput environments:

```yaml
# docker-compose.override.yml
services:
  validation-worker:
    deploy:
      replicas: 3
    environment:
      - MAX_PARALLEL_VALIDATIONS=5
```

### Resource Requirements

Per validation worker:
- **CPU**: 2 cores recommended
- **Memory**: 4GB minimum (Splunk containers need ~2GB each)
- **Disk**: 10GB for temp files and container images

### Security Considerations

1. **Docker Socket Access**: The validation worker needs Docker socket access. In production:
   - Consider using Docker-out-of-Docker (DooD) with a remote Docker daemon
   - Or use Kubernetes Jobs instead of Docker for container orchestration
   - Apply least-privilege principles

2. **Splunk Admin Password**: Change default password in production
   - Use secrets management (K8s secrets, Vault)
   - Rotate credentials periodically

3. **Network Isolation**: Splunk containers should be on isolated network
   - Use Docker network segmentation
   - Firewall rules to restrict access

## API Reference

### Validation Task

```python
validate_ta_task.apply_async(
    args=[validation_run_id, ta_revision_id, request_id],
    queue='validation'
)
```

### Validation Report Schema

```json
{
  "status": "PASSED | FAILED",
  "timestamp": "ISO8601 timestamp",
  "summary": {
    "total_events": 1000,
    "ta_name": "TA-myapp",
    "index_name": "ta_validation_test",
    "fields_extracted": 8,
    "fields_expected": 10,
    "coverage_pct": 80.0
  },
  "field_coverage": {
    "overall_coverage": 80.0,
    "fields_extracted": 8,
    "fields_expected": 10,
    "fields": {
      "user": {"status": "extracted", "coverage_pct": 100},
      "action": {"status": "missing", "error": "Not found"}
    },
    "meets_threshold": true
  },
  "checks": [
    {"name": "ingestion", "passed": true, "details": "Event count: 1000"},
    {"name": "timestamp_parsing", "passed": true, "details": "Valid: 10/10"},
    {"name": "field_extraction", "passed": true, "details": "Coverage: 80%"}
  ],
  "errors": [],
  "warnings": [],
  "sample_events": [...]
}
```
