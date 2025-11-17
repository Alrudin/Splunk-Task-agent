# Database Layer Quick Start Guide

Quick reference for using the database models and repositories.

## Setup

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment
Create `.env` file:
```bash
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/splunk_ta_generator
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20
DATABASE_ECHO=false
```

### 3. Run Migrations
```bash
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### 4. Initialize Default Roles
```python
from backend.database import async_session_factory
from backend.repositories import RoleRepository

async with async_session_factory() as session:
    role_repo = RoleRepository(session)
    await role_repo.ensure_default_roles()
    await session.commit()
```

## Common Usage Patterns

### Creating a User

```python
from backend.repositories import UserRepository
from backend.database import async_session_factory

async with async_session_factory() as session:
    user_repo = UserRepository(session)

    user = await user_repo.create({
        "username": "john_doe",
        "email": "john@example.com",
        "full_name": "John Doe",
        "is_active": True,
        "auth_provider": "local"
    })

    await session.commit()
```

### Assigning Roles

```python
from backend.repositories import RoleRepository
from backend.models.enums import UserRoleEnum

role_repo = RoleRepository(session)

# Get role
role = await role_repo.get_by_name(UserRoleEnum.REQUESTOR)

# Assign to user
await role_repo.assign_role_to_user(user_id, role.id, assigned_by=admin_id)
await session.commit()
```

### Creating a Request

```python
from backend.repositories import RequestRepository
from backend.models.enums import RequestStatus

request_repo = RequestRepository(session)

request = await request_repo.create({
    "created_by": user_id,
    "status": RequestStatus.NEW,
    "source_system": "Apache",
    "description": "Generate TA for Apache access logs",
    "cim_required": True
})

await session.commit()
```

### Approving a Request

```python
# Approve
approved = await request_repo.approve_request(request_id, approver_id)

# Or reject
rejected = await request_repo.reject_request(
    request_id,
    approver_id,
    "Insufficient log samples provided"
)

await session.commit()
```

### Creating a TA Revision

```python
from backend.repositories import TARevisionRepository
from backend.models.enums import TARevisionType

ta_repo = TARevisionRepository(session)

# Get next version
version = await ta_repo.get_next_version(request_id)

# Create revision
revision = await ta_repo.create({
    "request_id": request_id,
    "version": version,
    "storage_key": f"tas/request-{request_id}-v{version}.tgz",
    "storage_bucket": "ta-artifacts",
    "generated_by": TARevisionType.AUTO,
    "file_size": 1024000,
    "checksum": "sha256hash...",
    "config_summary": {
        "inputs": ["monitor:///var/log/apache/*"],
        "sourcetypes": ["apache:access"],
        "cim_fields": ["src", "dest", "user"]
    }
})

await session.commit()
```

### Running Validation

```python
from backend.repositories import ValidationRunRepository
from backend.models.enums import ValidationStatus

validation_repo = ValidationRunRepository(session)

# Create validation run
validation = await validation_repo.create({
    "request_id": request_id,
    "ta_revision_id": revision_id,
    "status": ValidationStatus.QUEUED
})
await session.commit()

# Start validation
await validation_repo.start_validation(validation.id, "k8s-job-abc123")
await session.commit()

# Complete validation
await validation_repo.complete_validation(
    validation.id,
    status=ValidationStatus.PASSED,
    results={
        "fields_extracted": 15,
        "errors": 0,
        "events_indexed": 1000
    },
    debug_bundle_key="debug/request-123-v1.zip"
)
await session.commit()
```

### Creating Audit Logs

```python
from backend.repositories import AuditLogRepository
from backend.models.enums import AuditAction

audit_repo = AuditLogRepository(session)

await audit_repo.create_log(
    user_id=user_id,
    action=AuditAction.APPROVE,
    entity_type="request",
    entity_id=request_id,
    details={
        "previous_status": "PENDING_APPROVAL",
        "new_status": "APPROVED"
    },
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0..."
)

await session.commit()
```

### Querying with Relationships

```python
# Get request with all log samples
request = await request_repo.get_with_samples(request_id)
for sample in request.log_samples:
    print(f"Sample: {sample.filename}, {sample.file_size} bytes")

# Get request with all TA revisions
request = await request_repo.get_with_revisions(request_id)
for revision in request.ta_revisions:
    print(f"Version {revision.version}: {revision.generated_by.value}")

# Get full request details
request = await request_repo.get_full_details(request_id)
# Has log_samples, ta_revisions, and validation_runs loaded
```

### Search and Filtering

```python
# Search users
users = await user_repo.search_users("john", skip=0, limit=10)

# Search requests
requests = await request_repo.search_requests(
    "apache",
    status=RequestStatus.COMPLETED,
    skip=0,
    limit=20
)

# Get pending approvals
pending = await request_repo.get_pending_approval()

# Get failed validations
failed = await validation_repo.get_failed_validations(request_id)
```

### Statistics and Monitoring

```python
# Request statistics
stats = await request_repo.get_statistics()
# {"NEW": 5, "PENDING_APPROVAL": 2, "COMPLETED": 10, ...}

# Validation statistics
val_stats = await validation_repo.get_validation_statistics()
# {"QUEUED": 3, "RUNNING": 2, "PASSED": 50, "FAILED": 5}

# Knowledge document statistics
doc_stats = await knowledge_doc_repo.get_statistics()
# {"by_type": {"pdf": 10, "markdown": 5}, "indexing_status": {...}}

# Check validation concurrency
running = await validation_repo.get_running_count()
if running < MAX_PARALLEL_VALIDATIONS:
    # Start new validation
    pass
```

## FastAPI Integration

### Setup

```python
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db, check_db_connection, dispose_engine

app = FastAPI()

@app.on_event("startup")
async def startup():
    if not await check_db_connection():
        raise RuntimeError("Database connection failed")

@app.on_event("shutdown")
async def shutdown():
    await dispose_engine()
```

### Route Example

```python
from uuid import UUID
from backend.repositories import RequestRepository

@app.get("/requests/{request_id}")
async def get_request(
    request_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    request_repo = RequestRepository(db)
    request = await request_repo.get_by_id(request_id)

    if not request:
        raise HTTPException(status_code=404, detail="Request not found")

    return request

@app.post("/requests")
async def create_request(
    request_data: dict,
    db: AsyncSession = Depends(get_db)
):
    request_repo = RequestRepository(db)
    request = await request_repo.create(request_data)
    await db.commit()
    return request

@app.post("/requests/{request_id}/approve")
async def approve_request(
    request_id: UUID,
    approver_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    request_repo = RequestRepository(db)
    audit_repo = AuditLogRepository(db)

    # Approve request
    request = await request_repo.approve_request(request_id, approver_id)

    # Create audit log
    await audit_repo.create_log(
        user_id=approver_id,
        action=AuditAction.APPROVE,
        entity_type="request",
        entity_id=request_id,
        details={"status": "APPROVED"}
    )

    await db.commit()
    return request
```

## Common Patterns

### Transaction Management

```python
async with async_session_factory() as session:
    try:
        # Multiple operations
        user = await user_repo.create({...})
        request = await request_repo.create({...})
        await audit_repo.create_log({...})

        # Commit all changes
        await session.commit()
    except Exception as e:
        # Rollback on error
        await session.rollback()
        raise
```

### Pagination

```python
# Standard pagination
page = 1
page_size = 20
skip = (page - 1) * page_size

requests = await request_repo.get_all(skip=skip, limit=page_size)
```

### Error Handling

```python
try:
    user = await user_repo.create({
        "username": "john_doe",
        "email": "john@example.com"
    })
    await session.commit()
except IntegrityError:
    await session.rollback()
    raise HTTPException(
        status_code=400,
        detail="User with this username or email already exists"
    )
```

## Useful Queries

### Get Recent Activity
```python
recent = await audit_repo.get_recent_activity(hours=24, limit=50)
```

### Get User Activity
```python
user_activity = await audit_repo.get_by_user(user_id, skip=0, limit=100)
```

### Get Entity Audit Trail
```python
trail = await audit_repo.get_by_entity("request", request_id)
```

### Get Correlated Actions
```python
flow = await audit_repo.get_by_correlation_id(correlation_uuid)
```

### Get Active Documents for Indexing
```python
unindexed = await knowledge_doc_repo.get_unindexed_documents()
for doc in unindexed:
    # Process and index
    await knowledge_doc_repo.mark_as_indexed(
        doc.id,
        "splunk_docs_index",
        150  # embedding count
    )
```

## Testing

### Unit Test Example

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from backend.models import Base
from backend.repositories import UserRepository

@pytest.fixture
async def db_session():
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost/test_db")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = async_sessionmaker(engine, class_=AsyncSession)
    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest.mark.asyncio
async def test_create_user(db_session):
    user_repo = UserRepository(db_session)
    user = await user_repo.create({
        "username": "testuser",
        "email": "test@example.com"
    })
    await db_session.commit()

    assert user.id is not None
    retrieved = await user_repo.get_by_username("testuser")
    assert retrieved.id == user.id
```

## Reference

- **Full Documentation**: See `README_MODELS.md`
- **Implementation Details**: See `IMPLEMENTATION_SUMMARY.md`
- **Verification**: Run `python backend/verify_models.py`
- **Migration Commands**: Run `alembic --help`

## Status Flows

### Request Status Flow
```
NEW → PENDING_APPROVAL → APPROVED → GENERATING_TA → VALIDATING → COMPLETED
                      ↓
                   REJECTED
```

### Validation Status Flow
```
QUEUED → RUNNING → PASSED
                ↓
              FAILED
```

## Enums Quick Reference

```python
from backend.models.enums import (
    RequestStatus,        # NEW, PENDING_APPROVAL, APPROVED, REJECTED, GENERATING_TA, VALIDATING, COMPLETED, FAILED
    ValidationStatus,     # QUEUED, RUNNING, PASSED, FAILED
    TARevisionType,       # AUTO, MANUAL
    UserRoleEnum,         # REQUESTOR, APPROVER, ADMIN, KNOWLEDGE_MANAGER
    AuditAction,          # CREATE, UPDATE, DELETE, APPROVE, REJECT, DOWNLOAD, UPLOAD, LOGIN, LOGOUT
)
```

## Tips

1. **Always commit**: Don't forget `await session.commit()` after write operations
2. **Use relationships**: Leverage `get_with_*()` methods to avoid N+1 queries
3. **Paginate**: Always use skip/limit for large result sets
4. **Audit everything**: Use AuditLogRepository for all human actions
5. **Handle errors**: Wrap database operations in try/except blocks
6. **Test locally**: Use SQLite for fast local testing: `sqlite+aiosqlite:///test.db`

## Need Help?

- Check `README_MODELS.md` for detailed documentation
- Run verification: `python backend/verify_models.py`
- SQLAlchemy docs: https://docs.sqlalchemy.org/
- Alembic docs: https://alembic.sqlalchemy.org/
