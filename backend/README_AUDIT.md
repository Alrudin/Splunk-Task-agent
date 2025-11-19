# Audit Logging System

## Overview

The audit logging system provides comprehensive tracking of all human actions and critical system events within the Splunk TA Generator application. It ensures compliance, security, and full traceability of operations by capturing detailed information about who did what, when, and from where.

### Key Features

- **Immutable Audit Trail**: Audit logs cannot be modified or deleted once created
- **Automatic Context Capture**: IP address, user agent, and correlation IDs are automatically extracted from requests
- **Structured Logging**: Integration with structlog for both database and log file output
- **Role-Based Access**: Audit log queries restricted to ADMIN and APPROVER roles
- **Comprehensive Coverage**: All critical actions including approvals, downloads, TA generation, and configuration changes

## Architecture

### Components

1. **AuditLog Model** (`backend/models/audit_log.py`)
   - Database entity with fields: user_id, action, entity_type, entity_id, details, ip_address, user_agent, correlation_id, timestamp
   - Indexed for fast querying by user, entity, action, date range, and correlation ID

2. **AuditLogRepository** (`backend/repositories/audit_log_repository.py`)
   - Data access layer with specialized query methods
   - Enforces immutability by disabling update and delete operations

3. **AuditService** (`backend/services/audit_service.py`)
   - High-level service layer providing convenience methods for common actions
   - Automatically extracts context from FastAPI Request objects
   - Emits structured logs for observability

4. **Audit API Router** (`backend/api/audit.py`)
   - REST endpoints for querying audit logs
   - Supports filtering by user, entity, action, date range, and correlation ID
   - Role-based access control (ADMIN/APPROVER)

5. **Audit Utilities** (`backend/core/audit_utils.py`)
   - Helper functions for extracting IP address, user agent, and correlation ID from requests

6. **Centralized Logging** (`backend/core/logging.py`)
   - Configures structlog with custom processors for audit context
   - Supports JSON and console output formats

## Usage Guide

### Logging Actions with AuditService

#### Basic Usage

```python
from fastapi import APIRouter, Depends, Request
from backend.services.audit_service import AuditService
from backend.core.dependencies import get_audit_service, get_current_active_user
from backend.models.enums import AuditAction
from backend.models.user import User

router = APIRouter()

@router.post("/approve/{request_id}")
async def approve_request(
    request_id: UUID,
    request: Request,
    current_user: User = Depends(get_current_active_user),
    audit_service: AuditService = Depends(get_audit_service)
):
    # Perform approval logic here...

    # Log the approval action
    await audit_service.log_approval(
        user_id=current_user.id,
        request_id=request_id,
        details={"comment": "Approved after review", "priority": "high"},
        request=request  # Automatically captures IP, user agent, correlation ID
    )

    return {"status": "approved"}
```

#### Manual Action Logging

For custom actions, use the generic `log_action` method:

```python
await audit_service.log_action(
    user_id=current_user.id,
    action=AuditAction.CONFIG_UPDATE,
    entity_type="SystemConfig",
    entity_id=None,
    details={"key": "ollama_host", "old_value": "localhost", "new_value": "10.0.0.5"},
    request=request
)
```

### Automatic Context Extraction

The AuditService automatically extracts request context when you pass a FastAPI `Request` object:

- **IP Address**: Extracted from `X-Forwarded-For`, `X-Real-IP`, or `request.client.host`
- **User Agent**: Extracted from `User-Agent` header
- **Correlation ID**: Retrieved from `request.state.correlation_id` (set by middleware)

If you don't pass a `request` object, these fields will be `None`:

```python
# System action without request context
await audit_service.log_ta_generation_start(
    request_id=request_id,
    details={"model": "llama3", "temperature": 0.7}
)
```

### Convenience Methods

The AuditService provides specialized methods for common actions:

| Method | Use Case | Action Type |
|--------|----------|-------------|
| `log_approval()` | User approves a request | APPROVE |
| `log_rejection()` | User rejects a request | REJECT |
| `log_download()` | User downloads TA or debug bundle | TA_DOWNLOAD, DEBUG_BUNDLE_DOWNLOAD |
| `log_upload()` | User uploads log sample or knowledge | SAMPLE_UPLOAD, KNOWLEDGE_UPLOAD |
| `log_ta_generation_start()` | System starts TA generation | TA_GENERATION_START |
| `log_ta_generation_complete()` | TA generation succeeds | TA_GENERATION_COMPLETE |
| `log_ta_generation_failed()` | TA generation fails | TA_GENERATION_FAILED |
| `log_manual_override()` | Engineer uploads manual TA revision | MANUAL_OVERRIDE |
| `log_revalidation_trigger()` | User triggers re-validation | REVALIDATION_TRIGGER |
| `log_validation_start()` | System starts validation | VALIDATION_START |
| `log_validation_complete()` | Validation succeeds | VALIDATION_COMPLETE |
| `log_validation_failed()` | Validation fails | VALIDATION_FAILED |
| `log_config_update()` | Admin updates system configuration | CONFIG_UPDATE |

## Querying Audit Logs

### API Endpoints

#### Query All Logs with Filters

```bash
GET /api/audit?user_id=<uuid>&action=APPROVE&start_date=2025-01-01T00:00:00Z&limit=50
```

**Query Parameters:**
- `user_id`: Filter by user ID
- `action`: Filter by action type (e.g., APPROVE, LOGIN, TA_DOWNLOAD)
- `entity_type`: Filter by entity type (e.g., Request, TARevision)
- `entity_id`: Filter by specific entity ID
- `start_date`: Filter logs after this date (ISO format)
- `end_date`: Filter logs before this date (ISO format)
- `correlation_id`: Filter by correlation ID
- `skip`: Pagination offset (default: 0)
- `limit`: Max results (default: 100, max: 1000)

**Response:**
```json
{
  "items": [
    {
      "id": "789e0123-e89b-12d3-a456-426614174999",
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "action": "APPROVE",
      "entity_type": "Request",
      "entity_id": "456e7890-e89b-12d3-a456-426614174111",
      "details": {"comment": "Approved after review"},
      "ip_address": "192.168.1.100",
      "user_agent": "Mozilla/5.0",
      "correlation_id": "999e8888-e89b-12d3-a456-426614174222",
      "timestamp": "2025-01-15T14:30:00Z"
    }
  ],
  "total": 150,
  "skip": 0,
  "limit": 100
}
```

#### Get Audit Log by ID

```bash
GET /api/audit/{audit_id}
```

#### Get Logs for a User

```bash
GET /api/audit/user/{user_id}?skip=0&limit=100
```

Users can view their own logs. ADMIN/APPROVER can view any user's logs.

#### Get Audit Trail for an Entity

```bash
GET /api/audit/entity/Request/{request_id}
```

Returns all actions performed on a specific Request, TARevision, etc.

#### Trace Related Actions by Correlation ID

```bash
GET /api/audit/correlation/{correlation_id}
```

Returns all logs with the same correlation ID, enabling end-to-end workflow tracking.

### Programmatic Access

```python
from backend.repositories.audit_log_repository import AuditLogRepository
from backend.models.enums import AuditAction

# Get logs by user
logs = await audit_repo.get_by_user(user_id=user_id, skip=0, limit=100)

# Get logs by entity
logs = await audit_repo.get_by_entity(
    entity_type="Request",
    entity_id=request_id,
    skip=0,
    limit=100
)

# Get logs by action
logs = await audit_repo.get_by_action(action=AuditAction.APPROVE, skip=0, limit=50)

# Get recent activity
logs = await audit_repo.get_recent_activity(hours=24, skip=0, limit=100)

# Advanced search with filters
filters = {
    "user_id": user_id,
    "action": "APPROVE",
    "entity_type": "Request",
    "start_date": datetime(2025, 1, 1),
    "end_date": datetime(2025, 1, 31)
}
logs = await audit_repo.search_logs(filters=filters, skip=0, limit=100)
```

## Best Practices

### When to Log

**MUST log:**
- All human actions (approvals, rejections, downloads, uploads, overrides)
- Manual TA revisions and re-validation triggers
- Configuration changes
- Authentication events (login, logout, password changes)

**SHOULD log:**
- TA generation start/complete/failed
- Validation run lifecycle events
- Debug bundle creation and downloads

**NO NEED to log:**
- Read-only operations (viewing lists, retrieving details)
- Health checks and monitoring endpoints

### What to Include in Details

The `details` field is a JSON dictionary for additional context:

```python
details = {
    "comment": "Approved based on sample review",
    "priority": "high",
    "reviewer_notes": "Validated against CIM requirements"
}
```

**Do:**
- Include relevant context (comments, reasons, configuration values)
- Use structured keys for consistency
- Include old/new values for updates

**Don't:**
- Include sensitive data (passwords, API keys, secrets)
- Include large payloads (full file contents)
- Use inconsistent field names

### Using Correlation IDs

Correlation IDs link related operations across requests:

1. **Automatic Correlation**: The `correlation_id_middleware` in `main.py` automatically generates or extracts correlation IDs from `X-Correlation-ID` headers
2. **Cross-Request Tracing**: Pass the same correlation ID through multiple related API calls to trace a complete workflow
3. **Debugging**: Query logs by correlation ID to see all actions in a single request lifecycle

Example workflow:
```
1. User submits request → correlation_id: abc-123
2. Approver approves → correlation_id: abc-123 (same)
3. System generates TA → correlation_id: abc-123
4. System validates → correlation_id: abc-123
5. User downloads TA → correlation_id: abc-123
```

Query: `GET /api/audit/correlation/abc-123` returns all 5 actions.

## Audit Actions Reference

All available audit actions are defined in `backend/models/enums.py`:

| Action | Description | Typical Entity Type |
|--------|-------------|-------------------|
| `CREATE` | Generic entity creation | Any |
| `UPDATE` | Generic entity update | Any |
| `DELETE` | Generic entity deletion | Any |
| `APPROVE` | Request approval | Request |
| `REJECT` | Request rejection | Request |
| `DOWNLOAD` | Generic download | Any |
| `UPLOAD` | Generic upload | Any |
| `LOGIN` | User login | User |
| `LOGOUT` | User logout | User |
| `USER_CREATED` | User registration | User |
| `PASSWORD_CHANGED` | Password change | User |
| `TA_GENERATION_START` | TA generation begins | Request |
| `TA_GENERATION_COMPLETE` | TA generation succeeds | Request |
| `TA_GENERATION_FAILED` | TA generation fails | Request |
| `VALIDATION_START` | Validation begins | TARevision |
| `VALIDATION_COMPLETE` | Validation succeeds | TARevision |
| `VALIDATION_FAILED` | Validation fails | TARevision |
| `MANUAL_OVERRIDE` | Engineer uploads manual TA | TARevision |
| `REVALIDATION_TRIGGER` | User triggers re-validation | TARevision |
| `DEBUG_BUNDLE_DOWNLOAD` | Debug bundle download | DebugBundle |
| `TA_DOWNLOAD` | TA package download | TARevision |
| `SAMPLE_UPLOAD` | Log sample upload | LogSample |
| `KNOWLEDGE_UPLOAD` | Knowledge document upload | KnowledgeDocument |
| `CONFIG_UPDATE` | System config change | SystemConfig |

## Structured Logging

Audit events are logged both to the database and to structured logs via structlog:

```python
logger.info(
    f"audit_action_approve",
    user_id=str(user_id),
    action="APPROVE",
    entity_type="Request",
    entity_id=str(request_id),
    ip_address="192.168.1.100",
    correlation_id=str(correlation_id),
    audit_log_id=str(audit_log.id)
)
```

**Benefits:**
- Centralized log aggregation (Splunk, ELK, etc.)
- Real-time monitoring and alerting
- Correlation with application logs

**Configuration:**
- `LOG_LEVEL`: Set log verbosity (DEBUG, INFO, WARNING, ERROR)
- `LOG_FORMAT`: Choose output format (json, console)

## Compliance Considerations

### Immutability

Audit logs are **immutable** to ensure integrity:

```python
# These operations are BLOCKED:
await audit_repo.update(audit_id, {...})  # Raises NotImplementedError
await audit_repo.delete(audit_id)  # Raises NotImplementedError
```

Only `create` operations are allowed.

### Retention

Implement retention policies based on compliance requirements:

```python
# Example: Delete logs older than 2 years
cutoff_date = datetime.now() - timedelta(days=730)
old_logs = await audit_repo.get_logs_for_cleanup(cutoff_date)
# Archive to cold storage or delete
```

### Access Control

- **Query Access**: ADMIN and APPROVER roles only
- **Self-Service**: Users can view their own logs
- **API Security**: All endpoints require authentication

## Integration Examples

### Approval Workflow Service

```python
class ApprovalService:
    def __init__(self, request_repo, audit_service):
        self.request_repo = request_repo
        self.audit_service = audit_service

    async def approve_request(
        self,
        request_id: UUID,
        approver_id: UUID,
        comment: str,
        request: Request
    ):
        # Update request status
        await self.request_repo.update_status(request_id, RequestStatus.APPROVED)

        # Log approval
        await self.audit_service.log_approval(
            user_id=approver_id,
            request_id=request_id,
            details={"comment": comment, "approved_at": datetime.utcnow().isoformat()},
            request=request
        )
```

### TA Generation Task (Celery)

```python
@celery_app.task
def generate_ta(request_id: str):
    # Start generation
    audit_service.log_ta_generation_start(
        request_id=UUID(request_id),
        details={"model": "llama3", "worker": socket.gethostname()}
    )

    try:
        # Generate TA...
        ta_revision_id = create_ta_revision(...)

        # Success
        audit_service.log_ta_generation_complete(
            request_id=UUID(request_id),
            ta_revision_id=ta_revision_id,
            details={"duration_seconds": elapsed_time}
        )
    except Exception as e:
        # Failure
        audit_service.log_ta_generation_failed(
            request_id=UUID(request_id),
            details={"error": str(e), "traceback": traceback.format_exc()}
        )
        raise
```

## Troubleshooting

### No Correlation ID in Logs

**Cause**: Request object not passed to audit service method

**Solution**: Always pass the `request` parameter:
```python
await audit_service.log_action(..., request=request)
```

### Audit Logs Not Appearing

**Check:**
1. Database transaction committed: `await db.commit()`
2. No exceptions during log creation
3. Structured logs enabled: Check `LOG_LEVEL` environment variable

### Query Performance Issues

**Solutions:**
1. Use indexed fields (user_id, entity_type, entity_id, action, timestamp)
2. Add pagination with `skip` and `limit`
3. Use specific filters instead of broad queries
4. Consider archiving old logs to improve query speed

## Further Reading

- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [Structlog Documentation](https://www.structlog.org/)
- [Audit Logging Best Practices (OWASP)](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)
