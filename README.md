# AI-Assisted Splunk TA Generator

An intelligent system that automates the process of creating Splunk Technology Add-ons (TAs) for ingesting new log sources. This system leverages AI/LLM capabilities, vectorized Splunk knowledge, and automated validation to reduce manual TA development effort by 80%.

## Overview

The AI-Assisted Splunk TA Generator streamlines the traditionally manual and time-consuming process of onboarding new log sources into Splunk. Using a combination of AI-powered configuration generation, knowledge retrieval from Splunk documentation, and automated validation, the system produces production-ready TA packages that can be immediately deployed to Splunk environments.

For detailed requirements and design specifications, see:

- [Product Requirements Document (PRD)](./PO-folder/PRD.md)
- [Technical Design Document](./PO-folder/Design.md)

## Architecture

### System Components

- **Frontend Web App**: React 18 with TypeScript, Vite, and Tailwind CSS
- **Backend API Service**: Python 3.11+ with FastAPI and SQLAlchemy
- **Worker Service**: Celery with Redis for asynchronous task processing
- **Vector Database**: Pinecone for storing and retrieving Splunk documentation and historical TAs
- **Relational Database**: PostgreSQL for storing users, requests, artifacts, and audit logs
- **Object Storage**: MinIO (S3-compatible) for log samples and TA bundles
- **LLM Runtime**: Ollama for local LLM inference
- **Validation Environment**: Ephemeral Splunk containers for TA testing

### Technology Stack

**Backend:**

- Python 3.11+
- FastAPI (async web framework)
- SQLAlchemy 2.0 (ORM)
- Celery (distributed task queue)
- Alembic (database migrations)

**Frontend:**

- React 18
- TypeScript
- Vite (build tool)
- Tailwind CSS (styling)
- React Query (data fetching)

**Infrastructure:**

- Docker & Docker Compose
- PostgreSQL 15
- Redis 7
- MinIO
- Kubernetes (production deployment)

## Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local frontend development)
- Python 3.11+ (for local backend development)
- Git

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd Splunk-Task-agent
```

### 2. Environment Configuration

Copy the example environment file and configure:

```bash
cp .env.example .env
# Edit .env with your configuration
```

### 3. Start Infrastructure Services

Launch PostgreSQL, Redis, and MinIO:

```bash
docker-compose up -d
```

Verify services are running:

```bash
docker-compose ps
```

### 4. Object Storage Setup

After starting docker-compose services, initialize the storage buckets:

```bash
# From project root
python -m backend.scripts.init_storage

# Verify connectivity only
python -m backend.scripts.init_storage --verify-only

# Force recreate buckets
python -m backend.scripts.init_storage --force
```

#### Access MinIO Console

MinIO provides a web console for managing buckets and objects:

- URL: <http://localhost:9001>
- Username: `minioadmin` (from `.env` `MINIO_ACCESS_KEY`)
- Password: `minioadmin` (from `.env` `MINIO_SECRET_KEY`)

### 5. Backend Setup

```bash
# Navigate to backend directory
cd backend/

# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Linux/Mac:
source venv/bin/activate
# On Windows:
# venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations (when available)
# alembic upgrade head

# Start the FastAPI server
# uvicorn main:app --reload --port 8000
```

### 6. Frontend Setup

In a new terminal:

```bash
# Navigate to frontend directory
cd frontend/

# Install dependencies
npm install

# Start development server
npm run dev
```

The application will be available at:

- Frontend: <http://localhost:5173>
- Backend API: <http://localhost:8000>
- API Documentation: <http://localhost:8000/docs>

## Project Structure

```text
Splunk-Task-agent/
├── backend/              # Python FastAPI backend
│   ├── api/             # API endpoints
│   ├── services/        # Business logic
│   ├── models/          # Database models
│   ├── repositories/    # Data access layer
│   ├── integrations/    # External service clients
│   ├── tasks/           # Celery background tasks
│   └── requirements.txt # Python dependencies
├── frontend/            # React TypeScript frontend
│   ├── src/            # Source code
│   ├── public/         # Static assets
│   ├── package.json    # Node dependencies
│   └── vite.config.ts  # Build configuration
├── PO-folder/          # Product documentation
│   ├── PRD.md         # Product requirements
│   └── Design.md      # Technical design
├── docker-compose.yml  # Local development services
├── .env.example       # Environment configuration template
└── README.md          # This file
```

## Infrastructure Services

### PostgreSQL

- **Port**: 5432
- **Database**: splunk_ta_generator
- **Default credentials**: postgres/postgres123 (change in production)

### Redis

- **Port**: 6379
- **Purpose**: Celery task broker and result backend

### MinIO (S3-compatible storage)

- **API Port**: 9000
- **Console Port**: 9001 (<http://localhost:9001>)
- **Default credentials**: minioadmin/minioadmin (change in production)
- **Buckets**: log-samples, ta-artifacts, debug-bundles

## Development Workflow

### Running Tests

```bash
# Backend tests
cd backend/
pytest

# Frontend tests
cd frontend/
npm test
```

### Code Formatting

```bash
# Backend (Python)
cd backend/
black .
ruff check .

# Frontend (TypeScript)
cd frontend/
npm run lint
npm run format
```

### Database Migrations

```bash
cd backend/
# Create new migration
alembic revision --autogenerate -m "Description"

# Apply migrations
alembic upgrade head
```

### Storage Maintenance

Run periodic cleanup to enforce retention policies:

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

#### Configuration

Storage settings are configured in `.env` (copy from `.env.example`):

- `SAMPLE_RETENTION_ENABLED`: Enable/disable automatic sample deletion
- `SAMPLE_RETENTION_DAYS`: Days to keep samples before deletion
- `MAX_SAMPLE_SIZE_MB`: Maximum upload size (default 500MB)
- `MINIO_BUCKET_*`: Bucket names for different artifact types

See `backend/integrations/README.md` for detailed storage client documentation.

## Core Workflow

1. **Request Submission**: User submits log onboarding request through guided interview
2. **Log Upload**: User uploads sample logs (max 500MB)
3. **Human Approval**: Splunk expert reviews and approves the request
4. **TA Generation**: System generates complete TA structure using AI
5. **Validation**: Automated testing in ephemeral Splunk container
6. **Download**: User receives packaged TA (.tgz file)

## API Documentation

Once the backend is running, interactive API documentation is available at:

- Swagger UI: <http://localhost:8000/docs>
- ReDoc: <http://localhost:8000/redoc>

## Security Considerations

- All user actions are audit logged
- JWT-based authentication with configurable expiration
- Support for SAML/OAuth/OIDC enterprise SSO
- Non-root container execution
- Secrets management via environment variables
- Sample retention policies for compliance

## Deployment

For production deployment:

1. Build Docker images:

```bash
docker build -t splunk-ta-backend ./backend
docker build -t splunk-ta-frontend ./frontend
```

2. Deploy to Kubernetes using provided manifests (to be added)

3. Configure production environment variables

4. Set up SSL/TLS termination

5. Configure authentication providers

## Contributing

1. Follow the existing code style and conventions
2. Write tests for new functionality
3. Update documentation as needed
4. Submit pull requests for review

## Support

For issues and questions:

- Check the [Design Document](./PO-folder/Design.md) for technical details
- Review the [PRD](./PO-folder/PRD.md) for product requirements
- Create an issue in the repository

## License

Internal use only - proprietary software
