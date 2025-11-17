# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an **AI-Assisted Splunk TA (Technology Add-on) Generator** - an internal system that automates the process of ingesting new log sources into Splunk. The system uses an LLM agent, vectorized Splunk knowledge, and automated validation to reduce manual TA development effort by 80%.

## Architecture

### System Components

The system follows a microservices architecture with the following key components:

1. **Frontend Web App**: React + TypeScript with Tailwind CSS
2. **Backend API Service**: Python with FastAPI
3. **Worker/Orchestrator Service**: Python with Celery (Redis/RabbitMQ)
4. **Vector Database**: Pinecone (stores Splunk docs, historical TAs, sample logs)
5. **Relational Database**: PostgreSQL (users, requests, artifacts, audit logs)
6. **Object Storage**: S3-compatible store (log samples, TA bundles, debug bundles)
7. **LLM Runtime**: Ollama (configurable host/IP/port)
8. **Splunk Sandbox**: Ephemeral Splunk containers for validation (K8s Jobs or Docker containers)
9. **Auth Provider**: SAML/OAuth/OIDC support + local users for dev/test

### Core Workflow

1. Requestor submits log onboarding request via guided AI interview
2. Uploads log samples (max 500 MB)
3. **Human approval gate** - Splunk expert must approve before generation
4. System generates complete TA structure:
   - `inputs.conf`
   - `props.conf`
   - `transforms.conf`
   - CIM mappings
   - Full TA directory structure
5. Launches standalone Splunk container for validation
6. Produces downloadable `.tgz` TA package
7. Supports manual override and re-validation by experts

### Key Backend Modules

- **API Layer** (`api/`): FastAPI routers for `/auth`, `/requests`, `/samples`, `/ta`, `/validation`, `/admin/knowledge`, `/config`
- **Domain Logic** (`services/`): Request, TA generation, validation, knowledge, audit, auth services
- **Persistence** (`models/`, `repositories/`): SQLAlchemy models and repository classes
- **Integrations** (`integrations/`): Clients for Ollama, Pinecone, Splunk sandbox, object storage
- **Tasks** (`tasks/`): Celery tasks for TA generation, validation, debug bundle creation

### Database Schema (Key Entities)

- `users`, `roles`, `user_roles`
- `requests` - Status flow: `NEW` → `PENDING_APPROVAL` → `APPROVED` → `GENERATING_TA` → `VALIDATING` → `COMPLETED`/`FAILED`
- `log_samples`
- `ta_artifacts`, `ta_revisions` (versioned as `TA-<source>-v1`, `TA-<source>-v2`, etc.)
- `validation_runs`
- `knowledge_documents`
- `audit_logs` (captures ALL human actions)
- `system_config`

## Development Requirements

### Technology Stack

**Backend:**
- Python 3.11+
- FastAPI (async, OpenAPI auto-gen)
- Celery (task queue)
- SQLAlchemy + Alembic (ORM + migrations)
- Authlib/python-jose (JWT validation, OIDC)
- httpx (async HTTP client for Ollama, Splunk REST API, Pinecone)
- structlog (structured logging)

**Frontend:**
- TypeScript
- React
- Vite (build tool)
- Tailwind CSS
- React Query or Redux Toolkit (state management)
- oidc-client-ts (auth)

**Infrastructure:**
- PostgreSQL
- S3-compatible object storage (MinIO for dev)
- Pinecone vector database
- Docker + Kubernetes (K8s Jobs for Splunk validation)

### Configuration

System is configured via environment variables and `system_config` table:

- `OLLAMA_HOST`, `OLLAMA_PORT` - Ollama LLM endpoint
- `PINECONE_API_KEY`, `PINECONE_ENV` - Vector database credentials
- `SAMPLE_RETENTION_ENABLED` - Toggle for sample storage (compliance requirement)
- `MAX_PARALLEL_VALIDATIONS` - Concurrency control for Splunk containers
- `ALLOWED_WEB_DOMAINS` - Whitelist for external access (e.g., splunkbase.splunk.com)

### Deployment

- Must run fully containerized
- Kubernetes-compatible artifacts required
- On-prem deployment expected
- Support for SAML, OAuth, and local user authentication

## Security & Compliance

### Critical Requirements

1. **Authentication**: MUST support SAML, OAuth, and local users
2. **Audit Logging**: MUST log ALL human actions (approver identity, TA generation, manual overrides, re-validation triggers)
3. **Debug Logging**: MUST log ALL agent and system events (configurable log level)
4. **Sample Retention**: Configurable enable/disable (compliance requirement)
5. **Web Access Control**: Whitelist/blacklist for external URLs
6. **No Credential Hardcoding**: Store as K8s secrets or .env
7. **Data Isolation**: Uploaded logs never leave on-prem environment

### Audit Log Requirements

Must capture:
- Identity of approving human reviewer
- TA generation start/end timestamps
- Manual override uploads
- Re-validation triggers
- Debug bundle downloads

## AI & RAG Implementation

### Prompt Construction

Inputs to LLM prompt:
- Request metadata (log source, format, required fields)
- Sample log snippets (sampled lines, not full 500MB)
- Relevant Splunk doc excerpts from Pinecone (props, transforms, CIM docs, similar TAs)
- Internal guidelines (CIM compliance preference)

Output format: Structured JSON containing config file definitions

### Pinecone Indexes

- `splunk_docs_index` - Splunk Platform documentation from docs.splunk.com
- `ta_examples_index` - Previously developed TAs
- `sample_logs_index` - Historical log samples (if enabled)

## Validation Pipeline

### Splunk Sandbox Orchestration

**Kubernetes Strategy** (preferred):
- K8s Job per validation run
- Image: `splunk/splunk:latest` (or pinned version)
- TA mounted + logs ingested via init container or sidecar
- Validation queries via Splunk REST API
- Results captured + job terminated

**Docker Alternative**: Use Docker SDK to manage containers

### Validation Checks

- Logs indexed without errors
- Key fields extracted (timestamp, host/source/sourcetype, CIM-relevant fields)
- Baseline search returns data
- Results captured as structured JSON with field coverage report

### Debug Bundle Contents

On validation failure, bundle must include:
- Full generated TA (even if invalid)
- Splunk internal error logs
- Validation engine logs
- Optional: prompt parameters used

## TA Versioning

- Each generation creates new version: `TA-<source>-v1`, `TA-<source>-v2`
- Manual override MUST increment version
- All versions tracked in `ta_revisions` table

## Manual Override Workflow

1. Engineer downloads TA from `/ta/{request_id}/revisions/{version}`
2. Edits configs locally **without restrictions**
3. Re-uploads via `/ta/{request_id}/override` (creates new TARevision with `generated_by=MANUAL`)
4. System re-runs validation pipeline
5. New version tagged and available for download

## Success Metrics

| Metric | Goal |
|--------|------|
| Time to onboard new logs | ↓ 80% versus current manual process |
| Splunk engineering effort | ↓ minimum 20% |
| Production ingestion & extraction errors | Strong downward reduction |
| % automated TA delivery | Increases quarterly |

## Implementation Phases

1. **Phase 0**: Manual prototype
2. **Phase 1**: MVP - TA generation only
3. **Phase 2**: Sandbox validation
4. **Phase 3**: Full human approval workflow
5. **Phase 4**: Internal rollout
6. **Phase 5**: Continuous improvement



## Known Constraints

- Log samples limited to 500 MB
- System MAY browse internet (whitelist-controlled)
- CIM compliance required when possible
- Requestors do NOT track status (notification-based workflow)
- Human approval required before TA generation begins
