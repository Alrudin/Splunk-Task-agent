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

### 4. Backend Setup

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

# Run database migrations
alembic upgrade head

# Seed initial roles
python -m backend.scripts.seed_roles

# Create admin user
python -m backend.scripts.create_admin

# Start the FastAPI server
uvicorn backend.main:app --reload --port 8000
```

### 5. Frontend Setup

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

## Authentication Setup

The system supports multiple authentication methods:

### Initial Setup

1. **Run database migrations**:

   ```bash
   cd backend
   alembic upgrade head
   ```

2. **Seed roles**:

   ```bash
   python -m backend.scripts.seed_roles
   ```

   This creates four roles:
   - `REQUESTOR`: Can submit TA generation requests
   - `APPROVER`: Can approve/reject requests
   - `ADMIN`: Full system access
   - `KNOWLEDGE_MANAGER`: Can manage knowledge documents

3. **Create admin user**:

   ```bash
   python -m backend.scripts.create_admin
   ```

   Follow the prompts to create your first admin user.

### Configuration

Copy `.env.example` to `.env` and configure authentication:

**JWT Configuration** (required):

```bash
# Generate a secure secret key
JWT_SECRET_KEY=$(openssl rand -hex 32)
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=60
JWT_REFRESH_EXPIRATION_DAYS=7
```

**Local Authentication** (enabled by default):

```bash
LOCAL_AUTH_ENABLED=true
```

**SAML Configuration** (optional):

```bash
SAML_ENABLED=true
SAML_METADATA_URL=https://your-idp.com/metadata
SAML_ENTITY_ID=https://your-app.com/saml
```

**OAuth Configuration** (optional):

```bash
OAUTH_ENABLED=true
OAUTH_CLIENT_ID=your-client-id
OAUTH_CLIENT_SECRET=your-client-secret
OAUTH_AUTHORIZE_URL=https://oauth-provider.com/authorize
OAUTH_TOKEN_URL=https://oauth-provider.com/token
OAUTH_USER_INFO_URL=https://oauth-provider.com/userinfo
```

**OIDC Configuration** (optional):

```bash
OIDC_ENABLED=true
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_DISCOVERY_URL=https://oidc-provider.com/.well-known/openid-configuration
```

### Frontend Configuration

Copy `frontend/.env.example` to `frontend/.env.local`:

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_APP_NAME=Splunk TA Generator
```

### Running the Application

**Backend**:

```bash
cd backend
uvicorn backend.main:app --reload
```

**Frontend**:

```bash
cd frontend
npm run dev
```

### Testing Authentication

1. Access the frontend at <http://localhost:5173/login>
2. Login with your admin credentials
3. Navigate to different sections to test role-based access
4. Access API docs with authentication: <http://localhost:8000/api/docs>

### User Management

Create additional users via:
- Admin panel (coming soon)
- Registration page (if local auth enabled)
- SSO providers (automatic user creation on first login)

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
