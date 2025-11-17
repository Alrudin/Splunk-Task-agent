# Database Models & Repository Layer Documentation

This document provides comprehensive documentation for the database architecture, SQLAlchemy models, and repository pattern implementation for the AI-Assisted Splunk TA Generator.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Data Model](#data-model)
- [Models Reference](#models-reference)
- [Enums Reference](#enums-reference)
- [Repository Pattern](#repository-pattern)
- [Database Migrations](#database-migrations)
- [Common Queries](#common-queries)
- [Testing](#testing)
- [Configuration](#configuration)

## Overview

The database layer implements a comprehensive data model for managing the full lifecycle of Splunk TA generation requests, from submission through validation and completion. It uses:

- **SQLAlchemy 2.0+** with async support (asyncpg driver)
- **PostgreSQL** as the relational database
- **Alembic** for database migrations
- **Repository pattern** for clean data access abstraction

### Key Features

- ✅ Async/await support throughout
- ✅ Type-safe Python enums for status fields
- ✅ UUID primary keys for distributed system compatibility
- ✅ Comprehensive audit logging (immutable, append-only)
- ✅ Soft deletes where appropriate
- ✅ Proper indexes and foreign key constraints
- ✅ Automatic timestamp tracking
- ✅ Repository pattern for testable, maintainable code

## Architecture

### Technology Stack

**Backend:**
- Python 3.11+
- SQLAlchemy 2.0+ (async ORM)
- asyncpg (PostgreSQL async driver)
- Alembic (migrations)
- FastAPI (web framework)

**Database:**
- PostgreSQL 14+

### Layered Architecture

```
┌─────────────────────────────────────┐
│         FastAPI Routes              │
│    (API endpoints, validation)      │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      Service Layer (Business Logic) │
│    (orchestration, domain logic)    │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│    Repository Layer (Data Access)   │
│  (CRUD operations, query logic)     │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│      SQLAlchemy Models (ORM)        │
│    (table definitions, relations)   │
└──────────────┬──────────────────────┘
               │
┌──────────────▼──────────────────────┐
│          PostgreSQL Database        │
└─────────────────────────────────────┘
```

## Data Model

The system includes 9 core entities:

1. **User** - System users with authentication
2. **Role** - RBAC roles (REQUESTOR, APPROVER, ADMIN, KNOWLEDGE_MANAGER)
3. **UserRole** - User-Role association (many-to-many)
4. **Request** - TA generation requests
5. **LogSample** - Uploaded log samples
6. **TARevision** - TA package versions
7. **ValidationRun** - Splunk sandbox validation results
8. **KnowledgeDocument** - RAG knowledge base documents
9. **AuditLog** - Immutable audit trail
10. **SystemConfig** - Runtime configuration key-value pairs

### Entity Relationship Diagram

```mermaid
erDiagram
    User ||--o{ UserRole : "has"
    Role ||--o{ UserRole : "assigned to"
    User ||--o{ Request : "creates"
    User ||--o{ Request : "approves"
    User ||--o{ TARevision : "uploads (manual)"
    User ||--o{ KnowledgeDocument : "uploads"
    User ||--o{ AuditLog : "performs"
    User ||--o{ SystemConfig : "updates"

    Request ||--o{ LogSample : "contains"
    Request ||--o{ TARevision : "has versions"
    Request ||--o{ ValidationRun : "validated by"

    TARevision ||--o{ ValidationRun : "tested in"

    User {
        uuid id PK
        string username UK
        string email UK
        string hashed_password
        string full_name
        boolean is_active
        boolean is_superuser
        string auth_provider
        string external_id
        datetime last_login
        datetime created_at
        datetime updated_at
    }

    Role {
        uuid id PK
        enum name UK
        text description
        json permissions
        datetime created_at
        datetime updated_at
    }

    Request {
        uuid id PK
        uuid created_by FK
        enum status
        string source_system
        text description
        boolean cim_required
        uuid approved_by FK
        datetime approved_at
        text rejection_reason
        datetime completed_at
        json metadata
        datetime created_at
        datetime updated_at
    }

    TARevision {
        uuid id PK
        uuid request_id FK
        int version
        string storage_key
        string storage_bucket
        enum generated_by
        uuid generated_by_user FK
        bigint file_size
        string checksum
        json config_summary
        json generation_metadata
        datetime created_at
        datetime updated_at
    }

    ValidationRun {
        uuid id PK
        uuid request_id FK
        uuid ta_revision_id FK
        enum status
        json results_json
        string debug_bundle_key
        string splunk_container_id
        text validation_logs
        text error_message
        datetime started_at
        datetime completed_at
        int duration_seconds
        datetime created_at
        datetime updated_at
    }
```

## Models Reference

### User Model

**Purpose:** Represents system users with authentication and profile information. Supports multiple authentication providers (local, SAML, OAuth, OIDC).

**Table:** `users`

**Key Columns:**
- `id` (UUID, PK) - Primary key
- `username` (String, unique, indexed) - Login username
- `email` (String, unique, indexed) - Email address
- `hashed_password` (String, nullable) - For local auth only
- `full_name` (String, nullable) - User's full name
- `is_active` (Boolean, default=True) - Account active status
- `is_superuser` (Boolean, default=False) - Superuser flag
- `auth_provider` (String, nullable) - 'local', 'saml', 'oauth', 'oidc'
- `external_id` (String, indexed, nullable) - SSO user mapping
- `last_login` (DateTime, nullable) - Last login timestamp

**Relationships:**
- `roles` → Many-to-many with Role
- `requests` → One-to-many with Request (created requests)
- `audit_logs` → One-to-many with AuditLog

**Indexes:**
- Composite: (email, auth_provider)
- Single: external_id, username, email

**Usage Example:**
```python
from backend.repositories import UserRepository

# Get user with roles
user = await user_repo.get_with_roles(user_id)

# Search users
users = await user_repo.search_users("john", skip=0, limit=10)

# Update last login
await user_repo.update_last_login(user_id)
```

---

### Role Model

**Purpose:** RBAC role definitions with predefined roles (REQUESTOR, APPROVER, ADMIN, KNOWLEDGE_MANAGER).

**Table:** `roles`

**Key Columns:**
- `id` (UUID, PK) - Primary key
- `name` (Enum, unique) - UserRoleEnum value
- `description` (Text, nullable) - Role description
- `permissions` (JSON, nullable) - Fine-grained permissions

**Relationships:**
- `users` → Many-to-many with User

**Usage Example:**
```python
from backend.repositories import RoleRepository
from backend.models.enums import UserRoleEnum

# Get role by name
role = await role_repo.get_by_name(UserRoleEnum.APPROVER)

# Assign role to user
await role_repo.assign_role_to_user(user_id, role_id, assigned_by=admin_id)

# Ensure default roles exist (run at startup)
await role_repo.ensure_default_roles()
```

---

### Request Model

**Purpose:** Tracks TA generation requests through their full lifecycle.

**Table:** `requests`

**Status Flow:**
```
NEW → PENDING_APPROVAL → APPROVED → GENERATING_TA → VALIDATING → COMPLETED/FAILED
                     ↓
                  REJECTED
```

**Key Columns:**
- `id` (UUID, PK)
- `created_by` (UUID, FK to users)
- `status` (Enum, indexed) - RequestStatus
- `source_system` (String) - e.g., 'Apache', 'Cisco ASA'
- `description` (Text)
- `cim_required` (Boolean, default=True)
- `approved_by` (UUID, FK to users, nullable)
- `approved_at` (DateTime, nullable)
- `rejection_reason` (Text, nullable)
- `completed_at` (DateTime, nullable)
- `metadata` (JSON, nullable)

**Relationships:**
- `created_by_user` → Many-to-one with User
- `approved_by_user` → Many-to-one with User
- `log_samples` → One-to-many with LogSample
- `ta_revisions` → One-to-many with TARevision
- `validation_runs` → One-to-many with ValidationRun

**Indexes:**
- Composite: (status, created_at) - for dashboard queries

**Usage Example:**
```python
from backend.repositories import RequestRepository
from backend.models.enums import RequestStatus

# Get pending approvals
pending = await request_repo.get_pending_approval(skip=0, limit=20)

# Approve request
request = await request_repo.approve_request(request_id, approver_id)

# Get full details with all relationships
request = await request_repo.get_full_details(request_id)

# Get statistics
stats = await request_repo.get_statistics()
# Returns: {"NEW": 5, "PENDING_APPROVAL": 2, "COMPLETED": 10, ...}
```

---

### LogSample Model

**Purpose:** Tracks uploaded log samples stored in S3-compatible storage.

**Table:** `log_samples`

**Key Columns:**
- `id` (UUID, PK)
- `request_id` (UUID, FK to requests)
- `filename` (String)
- `file_size` (BigInteger) - bytes
- `mime_type` (String, nullable)
- `storage_key` (String, indexed) - S3 object key
- `storage_bucket` (String)
- `checksum` (String, nullable) - SHA-256 hash
- `sample_preview` (Text, nullable) - first few lines
- `retention_until` (DateTime, indexed, nullable)
- `deleted_at` (DateTime, nullable) - soft delete

**Relationships:**
- `request` → Many-to-one with Request

**Usage Example:**
```python
from backend.repositories import LogSampleRepository

# Get samples for request
samples = await log_sample_repo.get_by_request(request_id)

# Get samples for cleanup
cutoff = datetime.utcnow() - timedelta(days=90)
old_samples = await log_sample_repo.get_samples_for_cleanup(cutoff)

# Soft delete
await log_sample_repo.mark_as_deleted(sample_id)
```

---

### TARevision Model

**Purpose:** Tracks TA package versions. Each generation creates a new version (v1, v2, v3, etc.).

**Table:** `ta_revisions`

**Key Columns:**
- `id` (UUID, PK)
- `request_id` (UUID, FK to requests)
- `version` (Integer) - 1, 2, 3, etc.
- `storage_key` (String) - S3 key for .tgz bundle
- `storage_bucket` (String)
- `generated_by` (Enum) - TARevisionType (AUTO or MANUAL)
- `generated_by_user` (UUID, FK to users, nullable) - for manual overrides
- `file_size` (BigInteger, nullable)
- `checksum` (String, nullable)
- `config_summary` (JSON, nullable) - inputs.conf, props.conf, transforms.conf summary
- `generation_metadata` (JSON, nullable) - LLM model, prompt version, Pinecone context

**Relationships:**
- `request` → Many-to-one with Request
- `uploaded_by_user` → Many-to-one with User
- `validation_runs` → One-to-many with ValidationRun

**Constraints:**
- Unique: (request_id, version)

**Usage Example:**
```python
from backend.repositories import TARevisionRepository

# Get latest revision
latest = await ta_revision_repo.get_latest_revision(request_id)

# Get next version number
next_version = await ta_revision_repo.get_next_version(request_id)

# Get revision history
history = await ta_revision_repo.get_revision_history(request_id)
```

---

### ValidationRun Model

**Purpose:** Tracks Splunk sandbox validation runs with results and debug information.

**Table:** `validation_runs`

**Key Columns:**
- `id` (UUID, PK)
- `request_id` (UUID, FK to requests)
- `ta_revision_id` (UUID, FK to ta_revisions)
- `status` (Enum, indexed) - ValidationStatus (QUEUED, RUNNING, PASSED, FAILED)
- `results_json` (JSON, nullable) - field coverage, errors, search results
- `debug_bundle_key` (String, nullable) - S3 key for debug .zip
- `debug_bundle_bucket` (String, nullable)
- `splunk_container_id` (String, nullable) - K8s Job name or Docker container ID
- `validation_logs` (Text, nullable)
- `error_message` (Text, nullable)
- `started_at` (DateTime, indexed, nullable)
- `completed_at` (DateTime, nullable)
- `duration_seconds` (Integer, nullable) - computed

**Relationships:**
- `request` → Many-to-one with Request
- `ta_revision` → Many-to-one with TARevision

**Usage Example:**
```python
from backend.repositories import ValidationRunRepository
from backend.models.enums import ValidationStatus

# Start validation
await validation_repo.start_validation(validation_id, container_id="job-abc-123")

# Complete validation
await validation_repo.complete_validation(
    validation_id,
    status=ValidationStatus.PASSED,
    results={"fields_extracted": 15, "errors": 0},
    debug_bundle_key="debug/request-123-v1.zip"
)

# Check concurrency
running_count = await validation_repo.get_running_count()
```

---

### KnowledgeDocument Model

**Purpose:** Manages knowledge base documents for RAG (Retrieval-Augmented Generation).

**Table:** `knowledge_documents`

**Key Columns:**
- `id` (UUID, PK)
- `title` (String)
- `description` (Text, nullable)
- `document_type` (String, indexed) - 'pdf', 'markdown', 'ta_archive', 'splunk_doc'
- `storage_key` (String)
- `storage_bucket` (String)
- `file_size` (BigInteger, nullable)
- `uploaded_by` (UUID, FK to users)
- `pinecone_indexed` (Boolean, indexed, default=False)
- `pinecone_index_name` (String, nullable)
- `embedding_count` (Integer, nullable)
- `metadata` (JSON, nullable)
- `is_active` (Boolean, indexed, default=True)

**Usage Example:**
```python
from backend.repositories import KnowledgeDocumentRepository

# Get unindexed documents for processing
unindexed = await knowledge_doc_repo.get_unindexed_documents()

# Mark as indexed
await knowledge_doc_repo.mark_as_indexed(doc_id, "splunk_docs_index", 150)

# Get statistics
stats = await knowledge_doc_repo.get_statistics()
# Returns: {"by_type": {"pdf": 10, "markdown": 5}, "indexing_status": {"indexed": 12, "unindexed": 3}}
```

---

### AuditLog Model

**Purpose:** Immutable audit trail for all human actions. Append-only, no updates or deletes.

**Table:** `audit_logs`

**Key Columns:**
- `id` (UUID, PK)
- `user_id` (UUID, FK to users, nullable) - nullable for system actions
- `action` (Enum, indexed) - AuditAction
- `entity_type` (String) - e.g., 'request', 'ta_revision'
- `entity_id` (UUID, indexed, nullable)
- `details` (JSON, nullable)
- `ip_address` (String, nullable)
- `user_agent` (String, nullable)
- `correlation_id` (UUID, indexed, nullable) - for tracing
- `timestamp` (DateTime, indexed)

**Indexes:**
- Composite: (user_id, timestamp), (entity_type, entity_id)

**Usage Example:**
```python
from backend.repositories import AuditLogRepository
from backend.models.enums import AuditAction

# Create audit log
await audit_log_repo.create_log(
    user_id=user_id,
    action=AuditAction.APPROVE,
    entity_type="request",
    entity_id=request_id,
    details={"previous_status": "PENDING_APPROVAL", "new_status": "APPROVED"},
    ip_address="192.168.1.100",
    user_agent="Mozilla/5.0...",
    correlation_id=correlation_uuid
)

# Get entity audit trail
trail = await audit_log_repo.get_by_entity("request", request_id)

# Get recent activity
recent = await audit_log_repo.get_recent_activity(hours=24, limit=50)
```

---

### SystemConfig Model

**Purpose:** Runtime configuration key-value store. Database values override environment variables.

**Table:** `system_config`

**Key Columns:**
- `id` (UUID, PK)
- `key` (String, unique, indexed)
- `value` (Text) - stored as string
- `value_type` (String) - 'string', 'integer', 'boolean', 'json', 'list'
- `description` (Text, nullable)
- `is_secret` (Boolean, default=False) - mask in UI
- `updated_by` (UUID, FK to users, nullable)
- `updated_at` (DateTime)
- `created_at` (DateTime)

**Usage Example:**
```python
from backend.repositories import SystemConfigRepository

# Get value with type parsing
max_validations = await system_config_repo.get_value(
    "MAX_PARALLEL_VALIDATIONS",
    default=5
)

# Set value
await system_config_repo.set_value(
    key="SAMPLE_RETENTION_ENABLED",
    value=True,
    value_type="boolean",
    updated_by=admin_id,
    description="Enable log sample retention"
)

# Get all public configs for UI
configs = await system_config_repo.get_public_configs()
```

## Enums Reference

### RequestStatus

Status values for Request entity:
- `NEW` - Initial state after submission
- `PENDING_APPROVAL` - Awaiting human approval
- `APPROVED` - Approved by human reviewer
- `REJECTED` - Rejected by human reviewer
- `GENERATING_TA` - AI agent is generating TA
- `VALIDATING` - TA is being validated in Splunk sandbox
- `COMPLETED` - Successfully completed
- `FAILED` - Failed during generation or validation

### ValidationStatus

Status values for ValidationRun entity:
- `QUEUED` - Waiting to start
- `RUNNING` - Currently executing
- `PASSED` - Validation successful
- `FAILED` - Validation failed

### TARevisionType

Type values for TARevision entity:
- `AUTO` - AI-generated TA
- `MANUAL` - Human-uploaded override

### UserRoleEnum

Role values for Role entity:
- `REQUESTOR` - Can submit requests and upload samples
- `APPROVER` - Can approve/reject requests
- `ADMIN` - Full system access
- `KNOWLEDGE_MANAGER` - Can manage knowledge base

### AuditAction

Action values for AuditLog entity:
- `CREATE`, `UPDATE`, `DELETE` - CRUD operations
- `APPROVE`, `REJECT` - Request approval actions
- `DOWNLOAD`, `UPLOAD` - File operations
- `LOGIN`, `LOGOUT` - Authentication events

## Repository Pattern

### BaseRepository

All repositories extend `BaseRepository[ModelType]` which provides:

**Standard Methods:**
- `get_by_id(id)` - Retrieve by primary key
- `get_all(skip, limit)` - Paginated list
- `create(data)` - Create from dict
- `update(id, data)` - Update from dict
- `delete(id)` - Delete by ID
- `exists(id)` - Check existence
- `count(filters)` - Count with filters

**Helper Methods:**
- `_apply_filters(query, filters)` - Apply WHERE clauses
- `_apply_ordering(query, order_by, desc)` - Apply ORDER BY

### Using Repositories

```python
from sqlalchemy.ext.asyncio import AsyncSession
from backend.repositories import UserRepository, RequestRepository

async def example_usage(session: AsyncSession):
    # Initialize repositories
    user_repo = UserRepository(session)
    request_repo = RequestRepository(session)

    # Use repository methods
    user = await user_repo.get_by_username("john_doe")
    requests = await request_repo.get_by_user(user.id)

    # Commit changes
    await session.commit()
```

### FastAPI Integration

```python
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from backend.database import get_db
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
```

## Database Migrations

### Alembic Setup

The project uses Alembic for database migrations with async support.

**Configuration files:**
- `backend/alembic.ini` - Alembic configuration
- `backend/alembic/env.py` - Migration environment (async)
- `backend/alembic/script.py.mako` - Migration template
- `backend/alembic/versions/` - Migration scripts

### Common Commands

**Create a new migration (autogenerate):**
```bash
cd backend
alembic revision --autogenerate -m "Add user table"
```

**Apply migrations:**
```bash
# Upgrade to latest
alembic upgrade head

# Upgrade by 1 version
alembic upgrade +1

# Upgrade to specific revision
alembic upgrade abc123
```

**Rollback migrations:**
```bash
# Downgrade by 1 version
alembic downgrade -1

# Downgrade to specific revision
alembic downgrade abc123

# Downgrade all
alembic downgrade base
```

**View migration history:**
```bash
alembic history

alembic current
```

**Create empty migration (manual):**
```bash
alembic revision -m "Add custom index"
```

### Migration Best Practices

1. **Review autogenerated migrations** - Always check before applying
2. **Use transactions** - Alembic wraps migrations in transactions automatically
3. **Test rollbacks** - Ensure downgrade() works correctly
4. **Avoid data migrations in schema migrations** - Use separate data migration scripts
5. **Never edit applied migrations** - Create new ones instead
6. **Use meaningful names** - Describe what the migration does

### Example Migration

```python
"""add user roles

Revision ID: abc123def456
Revises: xyz789
Create Date: 2025-01-15 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade() -> None:
    # Create roles table
    op.create_table(
        'roles',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('name', sa.String(50), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    # Add index
    op.create_index('ix_roles_name', 'roles', ['name'])

def downgrade() -> None:
    op.drop_index('ix_roles_name', 'roles')
    op.drop_table('roles')
```

## Common Queries

### User Queries

```python
# Find user by username
user = await user_repo.get_by_username("john_doe")

# Find user by email and SSO provider
user = await user_repo.get_by_external_id("ext-123", "saml")

# Search users
users = await user_repo.search_users("john", skip=0, limit=10)

# Get users with specific role
approvers = await user_repo.get_users_by_role(UserRoleEnum.APPROVER)

# Update last login
await user_repo.update_last_login(user_id)
```

### Request Queries

```python
# Get pending approvals
pending = await request_repo.get_pending_approval()

# Approve request
request = await request_repo.approve_request(request_id, approver_id)

# Get full request details
request = await request_repo.get_full_details(request_id)

# Search requests
requests = await request_repo.search_requests("apache", status=RequestStatus.COMPLETED)

# Get dashboard statistics
stats = await request_repo.get_statistics()
```

### Validation Queries

```python
# Check concurrency limit
running = await validation_repo.get_running_count()
if running < MAX_PARALLEL_VALIDATIONS:
    # Start new validation
    await validation_repo.start_validation(validation_id, container_id)

# Complete validation
await validation_repo.complete_validation(
    validation_id,
    status=ValidationStatus.PASSED,
    results=results_dict
)

# Get failed validations
failed = await validation_repo.get_failed_validations(request_id)
```

## Testing

### Unit Testing Repositories

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.models import Base
from backend.repositories import UserRepository

@pytest.fixture
async def db_session():
    """Create test database session."""
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost/test_db")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()

@pytest.mark.asyncio
async def test_create_user(db_session):
    """Test user creation."""
    user_repo = UserRepository(db_session)

    user_data = {
        "username": "testuser",
        "email": "test@example.com",
        "is_active": True
    }

    user = await user_repo.create(user_data)
    await db_session.commit()

    assert user.id is not None
    assert user.username == "testuser"

    # Verify retrieval
    retrieved = await user_repo.get_by_username("testuser")
    assert retrieved.id == user.id
```

### Integration Testing

```python
@pytest.mark.asyncio
async def test_request_approval_workflow(db_session):
    """Test complete request approval workflow."""
    user_repo = UserRepository(db_session)
    request_repo = RequestRepository(db_session)
    audit_repo = AuditLogRepository(db_session)

    # Create users
    requester = await user_repo.create({"username": "requester", "email": "req@test.com"})
    approver = await user_repo.create({"username": "approver", "email": "app@test.com"})
    await db_session.commit()

    # Create request
    request_data = {
        "created_by": requester.id,
        "status": RequestStatus.PENDING_APPROVAL,
        "source_system": "Apache",
        "description": "Test request",
        "cim_required": True
    }
    request = await request_repo.create(request_data)
    await db_session.commit()

    # Approve request
    approved = await request_repo.approve_request(request.id, approver.id)
    await db_session.commit()

    assert approved.status == RequestStatus.APPROVED
    assert approved.approved_by == approver.id
    assert approved.approved_at is not None

    # Verify audit log
    audit = await audit_repo.create_log(
        user_id=approver.id,
        action=AuditAction.APPROVE,
        entity_type="request",
        entity_id=request.id,
        details={"status": "APPROVED"}
    )
    await db_session.commit()

    logs = await audit_repo.get_by_entity("request", request.id)
    assert len(logs) > 0
```

## Configuration

### Environment Variables

Configure the database connection via environment variables (see `.env.example`):

```bash
# Database connection
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/splunk_ta_generator

# Connection pool settings
DATABASE_POOL_SIZE=10
DATABASE_MAX_OVERFLOW=20

# Development: enable SQL echo
DATABASE_ECHO=false

# Alembic uses the same DATABASE_URL
```

### Database Initialization

**Development (create tables directly):**
```python
from backend.database import init_db

async def startup():
    await init_db()
```

**Production (use Alembic migrations):**
```bash
alembic upgrade head
```

### FastAPI Integration

```python
from fastapi import FastAPI
from backend.database import engine, check_db_connection, dispose_engine
from backend.repositories import RoleRepository
from backend.database import async_session_factory

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    # Check database connection
    if not await check_db_connection():
        raise RuntimeError("Database connection failed")

    # Ensure default roles exist
    async with async_session_factory() as session:
        role_repo = RoleRepository(session)
        await role_repo.ensure_default_roles()
        await session.commit()

@app.on_event("shutdown")
async def shutdown_event():
    await dispose_engine()
```

---

## Summary

This database layer provides:

✅ **Comprehensive data model** for TA generation lifecycle
✅ **Async/await support** throughout for high concurrency
✅ **Repository pattern** for clean, testable code
✅ **Type safety** with Python enums
✅ **Audit trail** for compliance
✅ **Migration support** with Alembic
✅ **Production-ready** indexes and constraints

For questions or issues, refer to the main project documentation or the SQLAlchemy and Alembic official docs.
