# Phase Breakdown

## Task 1: Project Foundation & Infrastructure Setup

Set up monorepo structure with `backend/` (Python FastAPI) and `frontend/` (React TypeScript Vite)
Create `docker-compose.yml` with PostgreSQL, Redis, MinIO (S3-compatible storage)
Add `backend/requirements.txt` with FastAPI, SQLAlchemy, Alembic, Celery, httpx, structlog
Add `frontend/package.json` with React, TypeScript, Tailwind CSS, React Router, React Query
Create base Dockerfiles for backend and frontend services

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 2: Database Schema & Models Implementation

Create SQLAlchemy models in `backend/models/`: `User`, `Role`, `Request`, `LogSample`, `TARevision`, `ValidationRun`, `KnowledgeDocument`, `AuditLog`, `SystemConfig`
Implement Alembic migrations for all tables
Add repository pattern classes in `backend/repositories/` for data access
Include enums for request status, validation status, TA revision types

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`


## Task 3: Authentication & Authorization System

Implement auth service in `backend/services/auth_service.py` supporting SAML, OAuth2/OIDC, and local users
Create middleware for JWT token validation using `python-jose` or `authlib`
Add RBAC decorator for role-based access (requestor, approver, admin, knowledge_manager)
Create auth API routes in `backend/api/auth.py` for login, logout, token refresh
Build frontend auth context and login page in `frontend/src/pages/Login.tsx`

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`


## Task 4: Object Storage Integration

Create `backend/integrations/object_storage_client.py` with S3-compatible API using `boto3`
Implement methods for uploading/downloading log samples, TA bundles, and debug artifacts
Add configuration for MinIO/S3 endpoint, credentials, and bucket names
Include sample retention toggle logic (auto-delete vs persist)

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 5: Request Submission & Sample Upload Flow

Create `backend/services/request_service.py` for request lifecycle management
Implement API routes in `backend/api/requests.py` for creating requests and uploading samples (max 500MB)
Build frontend request form wizard in `frontend/src/pages/NewRequest/` with multi-step flow
Add sample upload component with progress tracking and validation
Store request metadata in database and samples in object storage

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`


## Task 6: Audit Logging & System Logging Infrastructure

Create `backend/services/audit_service.py` for logging all human actions (approvals, overrides, downloads)
Implement structured logging using `structlog` with correlation IDs
Add audit log API routes in `backend/api/audit.py` for querying logs
Configure log levels via environment variables
Store audit events in `audit_logs` table with user identity, action, entity, timestamp

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`


## Task 7: Human Approval Workflow & Dashboard

Create approval service in `backend/services/approval_service.py` with approve/reject logic
Add API routes in `backend/api/approvals.py` for listing pending requests and approval actions
Build approver dashboard in `frontend/src/pages/ApproverDashboard.tsx` showing `PENDING_APPROVAL` requests
Create approval detail view with request metadata, sample info, and approve/reject buttons
Log all approval actions via `audit_service`

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`


## Task 8: Pinecone Vector Database Integration

Create `backend/integrations/pinecone_client.py` for vector search operations
Implement methods for querying embeddings (Splunk docs, historical TAs, sample logs)
Add configuration for Pinecone API key, environment, and index names
Create embedding generation utility using a suitable embedding model
Support retrieval of top-N similar documents for RAG context

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 9: Ollama LLM Integration & Prompt Builder

Create `backend/integrations/ollama_client.py` for calling Ollama API with configurable host/IP/port
Implement `backend/services/prompt_builder.py` for constructing prompts with request metadata, log samples, and Pinecone context
Add prompt templates for TA generation (inputs.conf, props.conf, transforms.conf, CIM mappings)
Include structured JSON response parsing from LLM output
Add URL whitelist/blacklist enforcement for web browsing

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 10: Celery Worker Setup & Task Infrastructure

Configure Celery worker in `backend/worker/celery_app.py` with Redis/RabbitMQ broker
Create base task classes in `backend/tasks/base.py` with error handling and retry logic
Add task monitoring and status tracking in database
Implement task result storage and retrieval
Configure concurrency limits via `MAX_PARALLEL_VALIDATIONS` setting

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 11: TA Generation Engine & Packaging

Create `backend/tasks/generate_ta_task.py` as Celery task for TA generation workflow
Implement `backend/services/ta_generation_service.py` orchestrating Pinecone retrieval, prompt building, and Ollama calls
Build TA packaging logic in `backend/services/ta_packager.py` creating proper directory structure (inputs.conf, props.conf, transforms.conf, default.meta, app.conf)
Add versioning logic (TA-<source>-v1, v2, etc.) in `backend/services/ta_version_manager.py`
Store generated TA bundles (.tgz) in object storage and create `TARevision` records

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 12: Splunk Sandbox Orchestration & Container Management

Create `backend/integrations/splunk_sandbox_client.py` for launching ephemeral Splunk containers
Implement Kubernetes Job orchestration or Docker SDK integration for container lifecycle
Add TA installation logic via Splunk REST API or CLI
Implement log ingestion into test index
Create container cleanup and resource management logic
Support configurable Splunk container image and license acceptance

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 13: TA Validation Pipeline & Testing Engine

Create `backend/tasks/validate_ta_task.py` as Celery task for validation workflow
Implement `backend/services/validation_service.py` orchestrating sandbox launch, TA installation, log ingestion, and field validation
Build validation logic using Splunk REST API searches to verify parsing, field extraction, and CIM compliance
Generate structured pass/fail reports with field coverage analysis
Create debug bundle on failure containing TA, Splunk logs, and validation errors
Update request status to `COMPLETED` or `FAILED` based on results

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 14: Notification Service & User Alerts

Create `backend/services/notification_service.py` for sending completion/failure notifications
Support email notifications (SMTP configuration)
Add webhook support for external integrations
Implement notification templates for different event types
Trigger notifications from validation task completion
Add notification preferences to user model

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`


## Task 15: Manual Override & Re-validation Workflow

Add API routes in `backend/api/ta.py` for downloading TA revisions and uploading manual overrides
Implement override logic in `backend/services/ta_generation_service.py` creating new `TARevision` with `generated_by=MANUAL`
Trigger re-validation task for manually uploaded TAs
Build frontend override interface in `frontend/src/pages/TAOverride/` with upload form and version history
Display validation results and debug bundles for each revision

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`


## Task 16: Knowledge Management System & Admin Upload

Create `backend/services/knowledge_service.py` for managing knowledge documents
Add API routes in `backend/api/admin/knowledge.py` for uploading PDFs, Markdown, and TA archives
Implement document parsing and embedding generation for Pinecone indexing
Build admin knowledge upload UI in `frontend/src/pages/Admin/KnowledgeUpload.tsx`
Add knowledge document listing and management interface
Restrict access to admin and knowledge_manager roles

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`


## Task 17: System Configuration Management & Admin Settings

Create `backend/services/config_service.py` for managing system configuration
Add API routes in `backend/api/config.py` for reading/updating settings
Implement configuration for: sample retention toggle, `MAX_PARALLEL_VALIDATIONS`, URL whitelist/blacklist, Ollama endpoint
Build admin settings page in `frontend/src/pages/Admin/Settings.tsx`
Store configuration in `system_config` table with environment variable fallbacks

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`


## Task 18: Frontend Dashboard & Request Status Views

Build requestor dashboard in `frontend/src/pages/Dashboard.tsx` showing user's requests with status badges
Create request detail view in `frontend/src/pages/RequestDetail.tsx` with timeline, validation results, and TA download
Add TA revision history component showing v1, v2, v3 versions
Implement debug bundle download links for failed validations
Use React Query for data fetching and real-time status updates

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 19: Kubernetes Deployment Manifests & Production Configuration

Create Kubernetes manifests in `k8s/` directory: Deployments for backend, frontend, worker; Services; ConfigMaps; Secrets templates
Add Kubernetes Job template for Splunk sandbox validation runs
Create Helm chart (optional) for easier deployment
Document environment variables and configuration requirements
Add health check endpoints to backend API
Create production-ready `docker-compose.yml` for local testing

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`


## Task 20: End-to-End System Integration & Testing Review

Review complete workflow: request submission → approval → TA generation → validation → notification
Verify all P1 requirements are implemented and functional
Test authentication flows (SAML, OAuth, local)
Validate audit logging captures all required events
Test manual override and re-validation workflow
Verify configuration management and admin features
Document any integration issues or edge cases discovered

Relevant Files:
- `/Users/johan/src/Splunk-Task-agent/PO-folder/PRD.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Design.md`
- `/Users/johan/src/Splunk-Task-agent/PO-folder/Epic-story.md`