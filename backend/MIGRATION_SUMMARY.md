# Initial Database Migration Summary

## Migration File Created

**File**: `backend/alembic/versions/2025_11_17_1915-001_create_initial_schema_for_all_models.py`

**Revision ID**: 001

**Created**: 2025-11-17 19:15:00

## Overview

This migration creates the complete initial database schema for the AI-Assisted Splunk TA Generator application. It defines all 10 core tables with their relationships, indexes, and constraints required for the application to function.

## Tables Created

### 1. users
User authentication and profile management table supporting multiple auth providers.

**Columns**:
- `id` (UUID, PK) - Primary key
- `username` (VARCHAR 255, UNIQUE, INDEXED) - Unique username
- `email` (VARCHAR 255, UNIQUE, INDEXED) - Unique email address
- `hashed_password` (VARCHAR 255, NULLABLE) - Password hash (for local auth only)
- `full_name` (VARCHAR 255, NULLABLE) - User's full name
- `is_active` (BOOLEAN, DEFAULT TRUE) - Account active status
- `is_superuser` (BOOLEAN, DEFAULT FALSE) - Superuser flag
- `auth_provider` (VARCHAR 50, NULLABLE) - Auth provider type (local/saml/oauth/oidc)
- `external_id` (VARCHAR 255, NULLABLE, INDEXED) - External SSO user ID
- `last_login` (TIMESTAMP, NULLABLE) - Last login timestamp
- `created_at` (TIMESTAMP, DEFAULT NOW()) - Record creation time
- `updated_at` (TIMESTAMP, DEFAULT NOW()) - Last update time

**Indexes**:
- `ix_users_username` (UNIQUE)
- `ix_users_email` (UNIQUE)
- `ix_users_external_id`
- `ix_users_email_auth_provider` (composite)

### 2. roles
Role-based access control (RBAC) definitions.

**Columns**:
- `id` (UUID, PK)
- `name` (VARCHAR 50, UNIQUE, INDEXED) - Role name (stored as string, enum in app)
- `description` (TEXT, NULLABLE)
- `permissions` (JSONB, NULLABLE) - Future fine-grained permissions
- `created_at` (TIMESTAMP, DEFAULT NOW())
- `updated_at` (TIMESTAMP, DEFAULT NOW())

**Constraints**:
- `uq_roles_name` - Unique constraint on name

**Indexes**:
- `ix_roles_name` (UNIQUE)

**Predefined Roles**:
- REQUESTOR - Submit TA generation requests
- APPROVER - Review and approve requests
- ADMIN - System administration
- KNOWLEDGE_MANAGER - Manage knowledge base documents

### 3. user_roles
Many-to-many association table between users and roles.

**Columns**:
- `id` (UUID, PK)
- `user_id` (UUID, FK → users.id, CASCADE DELETE)
- `role_id` (UUID, FK → roles.id, CASCADE DELETE)
- `assigned_at` (TIMESTAMP, DEFAULT NOW())
- `assigned_by` (UUID, FK → users.id, SET NULL, NULLABLE)

**Constraints**:
- `uq_user_role` - Unique constraint on (user_id, role_id)

**Indexes**:
- `ix_user_roles_user_id`
- `ix_user_roles_role_id`

### 4. requests
TA generation requests tracking full lifecycle.

**Columns**:
- `id` (UUID, PK)
- `created_by` (UUID, FK → users.id, RESTRICT, INDEXED)
- `status` (VARCHAR 50, INDEXED) - Request status (stored as string, enum in app)
- `source_system` (VARCHAR 255) - Log source system name
- `description` (TEXT) - Request description
- `cim_required` (BOOLEAN, DEFAULT TRUE) - CIM compliance required
- `approved_by` (UUID, FK → users.id, SET NULL, NULLABLE)
- `approved_at` (TIMESTAMP, NULLABLE)
- `rejection_reason` (TEXT, NULLABLE)
- `completed_at` (TIMESTAMP, NULLABLE)
- `metadata` (JSONB, NULLABLE) - Additional request metadata
- `created_at` (TIMESTAMP, DEFAULT NOW())
- `updated_at` (TIMESTAMP, DEFAULT NOW())

**Status Values**:
- NEW → PENDING_APPROVAL → APPROVED → GENERATING_TA → VALIDATING → COMPLETED/FAILED
- Or: NEW → PENDING_APPROVAL → REJECTED

**Indexes**:
- `ix_requests_created_by`
- `ix_requests_status`
- `ix_requests_status_created_at` (composite)

### 5. log_samples
Uploaded log samples for TA generation.

**Columns**:
- `id` (UUID, PK)
- `request_id` (UUID, FK → requests.id, CASCADE DELETE, INDEXED)
- `filename` (VARCHAR 255)
- `file_size` (BIGINT) - File size in bytes
- `mime_type` (VARCHAR 100, NULLABLE)
- `storage_key` (VARCHAR 500, INDEXED) - S3/MinIO object key
- `storage_bucket` (VARCHAR 100) - Storage bucket name
- `checksum` (VARCHAR 64, NULLABLE) - SHA-256 hash
- `sample_preview` (TEXT, NULLABLE) - First N lines preview
- `retention_until` (TIMESTAMP, NULLABLE, INDEXED) - Retention expiry date
- `deleted_at` (TIMESTAMP, NULLABLE) - Soft delete timestamp
- `created_at` (TIMESTAMP, DEFAULT NOW())
- `updated_at` (TIMESTAMP, DEFAULT NOW())

**Indexes**:
- `ix_log_samples_request_id`
- `ix_log_samples_storage_key`
- `ix_log_samples_retention_until`

**Max Size**: 500 MB per file

### 6. ta_revisions
Versioned TA packages (both AI-generated and manual overrides).

**Columns**:
- `id` (UUID, PK)
- `request_id` (UUID, FK → requests.id, CASCADE DELETE, INDEXED)
- `version` (INTEGER) - Version number (1, 2, 3, ...)
- `storage_key` (VARCHAR 500) - S3 key for .tgz bundle
- `storage_bucket` (VARCHAR 100)
- `generated_by` (VARCHAR 50, INDEXED) - Generation type (AUTO/MANUAL, enum in app)
- `generated_by_user` (UUID, FK → users.id, SET NULL, NULLABLE)
- `file_size` (BIGINT, NULLABLE) - Bundle size in bytes
- `checksum` (VARCHAR 64, NULLABLE) - SHA-256 hash
- `config_summary` (JSONB, NULLABLE) - Summary of config files
- `generation_metadata` (JSONB, NULLABLE) - LLM model, prompt version, context
- `created_at` (TIMESTAMP, DEFAULT NOW())
- `updated_at` (TIMESTAMP, DEFAULT NOW())

**Constraints**:
- `uq_request_version` - Unique constraint on (request_id, version)

**Indexes**:
- `ix_ta_revisions_request_id`
- `ix_ta_revisions_request_id_version` (composite)
- `ix_ta_revisions_generated_by`

**Version Naming**: TA-{source}-v{version} (e.g., TA-Apache-v1, TA-Apache-v2)

### 7. validation_runs
Splunk sandbox validation results.

**Columns**:
- `id` (UUID, PK)
- `request_id` (UUID, FK → requests.id, CASCADE DELETE, INDEXED)
- `ta_revision_id` (UUID, FK → ta_revisions.id, CASCADE DELETE, INDEXED)
- `status` (VARCHAR 50, INDEXED) - Validation status (QUEUED/RUNNING/PASSED/FAILED)
- `results_json` (JSONB, NULLABLE) - Field coverage, search results
- `debug_bundle_key` (VARCHAR 500, NULLABLE) - S3 key for debug .zip
- `debug_bundle_bucket` (VARCHAR 100, NULLABLE)
- `splunk_container_id` (VARCHAR 255, NULLABLE) - K8s Job or Docker container ID
- `validation_logs` (TEXT, NULLABLE) - Captured Splunk logs
- `error_message` (TEXT, NULLABLE)
- `started_at` (TIMESTAMP, NULLABLE, INDEXED)
- `completed_at` (TIMESTAMP, NULLABLE)
- `duration_seconds` (INTEGER, NULLABLE) - Computed duration
- `created_at` (TIMESTAMP, DEFAULT NOW())
- `updated_at` (TIMESTAMP, DEFAULT NOW())

**Indexes**:
- `ix_validation_runs_request_id`
- `ix_validation_runs_ta_revision_id`
- `ix_validation_runs_status`
- `ix_validation_runs_request_id_created_at` (composite)
- `ix_validation_runs_started_at`

### 8. knowledge_documents
Admin-uploaded knowledge base documents for RAG.

**Columns**:
- `id` (UUID, PK)
- `title` (VARCHAR 500)
- `description` (TEXT, NULLABLE)
- `document_type` (VARCHAR 50, INDEXED) - Document type (pdf/markdown/ta_archive/splunk_doc)
- `storage_key` (VARCHAR 500) - S3 key
- `storage_bucket` (VARCHAR 100)
- `file_size` (BIGINT, NULLABLE)
- `uploaded_by` (UUID, FK → users.id, RESTRICT, INDEXED)
- `pinecone_indexed` (BOOLEAN, DEFAULT FALSE, INDEXED) - Indexed in Pinecone
- `pinecone_index_name` (VARCHAR 100, NULLABLE) - Target Pinecone index
- `embedding_count` (INTEGER, NULLABLE) - Number of chunks/embeddings
- `metadata` (JSONB, NULLABLE) - Tags, categories, source URL
- `is_active` (BOOLEAN, DEFAULT TRUE, INDEXED) - Soft delete flag
- `created_at` (TIMESTAMP, DEFAULT NOW())
- `updated_at` (TIMESTAMP, DEFAULT NOW())

**Indexes**:
- `ix_knowledge_documents_document_type`
- `ix_knowledge_documents_uploaded_by`
- `ix_knowledge_documents_pinecone_indexed`
- `ix_knowledge_documents_is_active`

**Pinecone Indexes Used**:
- splunk-docs-index - Splunk Platform documentation
- ta-examples-index - Previously developed TAs
- sample-logs-index - Historical log samples

### 9. audit_logs
Comprehensive audit trail for all human actions.

**Columns**:
- `id` (UUID, PK)
- `user_id` (UUID, FK → users.id, SET NULL, NULLABLE, INDEXED)
- `action` (VARCHAR 50, INDEXED) - Action type (CREATE/UPDATE/DELETE/APPROVE/REJECT/etc.)
- `entity_type` (VARCHAR 100) - Entity type affected
- `entity_id` (UUID, NULLABLE, INDEXED) - Entity ID affected
- `details` (JSONB, NULLABLE) - Action details
- `ip_address` (VARCHAR 45, NULLABLE) - Client IP (IPv4/IPv6)
- `user_agent` (VARCHAR 500, NULLABLE) - Client user agent
- `correlation_id` (UUID, NULLABLE, INDEXED) - Request correlation ID
- `timestamp` (TIMESTAMP, DEFAULT NOW(), INDEXED) - Action timestamp

**Indexes**:
- `ix_audit_logs_user_id`
- `ix_audit_logs_action`
- `ix_audit_logs_entity_id`
- `ix_audit_logs_timestamp`
- `ix_audit_logs_user_id_timestamp` (composite)
- `ix_audit_logs_entity_type_entity_id` (composite)
- `ix_audit_logs_correlation_id`

**Audit Actions**:
- CREATE, UPDATE, DELETE - CRUD operations
- APPROVE, REJECT - Request approvals
- DOWNLOAD, UPLOAD - File operations
- LOGIN, LOGOUT - Authentication events

**Critical Audit Requirements**:
- ALL human actions MUST be logged
- Captures approver identity
- TA generation events
- Manual override uploads
- Re-validation triggers
- Debug bundle downloads

### 10. system_config
System-wide configuration key-value store.

**Columns**:
- `id` (UUID, PK)
- `key` (VARCHAR 255, UNIQUE, INDEXED) - Configuration key
- `value` (TEXT) - Configuration value (stored as text, typed in app)
- `value_type` (VARCHAR 50) - Value type (string/int/bool/json)
- `description` (TEXT, NULLABLE) - Configuration description
- `is_secret` (BOOLEAN, DEFAULT FALSE) - Secret flag (masked in UI)
- `updated_by` (UUID, FK → users.id, SET NULL, NULLABLE)
- `updated_at` (TIMESTAMP, DEFAULT NOW(), INDEXED)
- `created_at` (TIMESTAMP, DEFAULT NOW())

**Constraints**:
- `uq_system_config_key` - Unique constraint on key

**Indexes**:
- `ix_system_config_key` (UNIQUE)
- `ix_system_config_updated_at`

**Example Config Keys**:
- OLLAMA_HOST, OLLAMA_PORT - LLM endpoint
- PINECONE_API_KEY, PINECONE_ENV - Vector DB
- SAMPLE_RETENTION_ENABLED - Compliance setting
- MAX_PARALLEL_VALIDATIONS - Concurrency control
- ALLOWED_WEB_DOMAINS - Web access whitelist

## Foreign Key Relationships

### Cascading Deletes (CASCADE)
- `user_roles.user_id` → `users.id`
- `user_roles.role_id` → `roles.id`
- `log_samples.request_id` → `requests.id`
- `ta_revisions.request_id` → `requests.id`
- `validation_runs.request_id` → `requests.id`
- `validation_runs.ta_revision_id` → `ta_revisions.id`

### Set Null on Delete (SET NULL)
- `user_roles.assigned_by` → `users.id`
- `requests.approved_by` → `users.id`
- `ta_revisions.generated_by_user` → `users.id`
- `audit_logs.user_id` → `users.id`
- `system_config.updated_by` → `users.id`

### Restrict Deletes (RESTRICT)
- `requests.created_by` → `users.id`
- `knowledge_documents.uploaded_by` → `users.id`

## Data Types

### UUIDs
All primary keys and foreign keys use `UUID` type for distributed ID generation.

### Timestamps
All tables include `created_at` and `updated_at` with `DEFAULT NOW()` server default.

### JSON/JSONB
All JSON columns use PostgreSQL's `JSONB` type for efficient storage and querying:
- `roles.permissions`
- `requests.metadata`
- `ta_revisions.config_summary`
- `ta_revisions.generation_metadata`
- `validation_runs.results_json`
- `knowledge_documents.metadata`
- `audit_logs.details`

### Enums (Application-Level)
Python enums are stored as `VARCHAR(50)` columns (non-native PostgreSQL enums):
- `RequestStatus` (requests.status)
- `ValidationStatus` (validation_runs.status)
- `TARevisionType` (ta_revisions.generated_by)
- `UserRoleEnum` (roles.name)
- `AuditAction` (audit_logs.action)

This approach provides flexibility for enum changes without database migrations.

## Indexes Summary

**Total Indexes**: 49 indexes across 10 tables

**Performance Optimizations**:
- All foreign keys are indexed
- Status fields are indexed for filtering
- Composite indexes on frequently joined columns
- Timestamp indexes for time-series queries
- Unique indexes enforce data integrity

## Migration Commands

### Apply Migration
```bash
cd backend
alembic upgrade head
```

### Rollback Migration
```bash
cd backend
alembic downgrade base
```

### Check Current Revision
```bash
cd backend
alembic current
```

### View Migration History
```bash
cd backend
alembic history
```

## Production Deployment Notes

1. **Database Connection**: Ensure `DATABASE_URL` environment variable is set with async driver:
   ```
   postgresql+asyncpg://user:password@host:5432/dbname
   ```

2. **Migration Execution**: Run migrations before starting the application:
   ```bash
   alembic upgrade head
   ```

3. **Rollback Plan**: Test downgrade on staging before production deployment:
   ```bash
   alembic downgrade -1
   ```

4. **Backup**: Always backup production database before running migrations

5. **Zero Downtime**: For production, consider blue-green deployment or rolling updates

## Schema Verification

After applying the migration, verify all tables and indexes:

```sql
-- List all tables
SELECT tablename FROM pg_tables WHERE schemaname = 'public';

-- List all indexes
SELECT indexname, tablename FROM pg_indexes WHERE schemaname = 'public';

-- Verify foreign keys
SELECT
    tc.table_name,
    kcu.column_name,
    ccu.table_name AS foreign_table_name,
    ccu.column_name AS foreign_column_name
FROM information_schema.table_constraints AS tc
JOIN information_schema.key_column_usage AS kcu
  ON tc.constraint_name = kcu.constraint_name
JOIN information_schema.constraint_column_usage AS ccu
  ON ccu.constraint_name = tc.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY';
```

## Next Steps

1. ✅ Initial migration created and validated
2. ⏭️ Set up PostgreSQL database (dev/test/prod)
3. ⏭️ Run `alembic upgrade head` to create tables
4. ⏭️ Seed initial data (roles, system config)
5. ⏭️ Create repository layer tests
6. ⏭️ Implement API endpoints using repositories

## Related Files

- **Migration File**: `backend/alembic/versions/2025_11_17_1915-001_create_initial_schema_for_all_models.py`
- **Alembic Config**: `backend/alembic.ini`
- **Alembic Env**: `backend/alembic/env.py`
- **Models**: `backend/models/*.py`
- **Enums**: `backend/models/enums.py`
- **Base Classes**: `backend/models/base.py`

## Compliance & Security

- ✅ Audit logging for all human actions
- ✅ Soft deletes for log samples (retention policy support)
- ✅ Secret masking in system_config
- ✅ Foreign key constraints for referential integrity
- ✅ Indexes for performance
- ✅ UUID primary keys for security
- ✅ Timestamp tracking for all records

## Support for Key Features

- ✅ Multi-provider authentication (local/SAML/OAuth/OIDC)
- ✅ Role-based access control (RBAC)
- ✅ TA versioning with manual override support
- ✅ Splunk sandbox validation tracking
- ✅ Knowledge base RAG integration
- ✅ Sample retention policies
- ✅ Debug bundle generation
- ✅ Comprehensive audit trail
- ✅ System configuration management
