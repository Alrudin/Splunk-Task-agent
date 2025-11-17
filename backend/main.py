"""
FastAPI application entry point.
"""
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from jose import JWTError
from sqlalchemy.exc import SQLAlchemyError
import structlog

from backend.core.config import settings
from backend.core.exceptions import AppException, app_exception_handler
from backend.api.auth import router as auth_router
from backend.api.requests import router as requests_router
from backend.database import check_db_connection, dispose_engine


# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.add_log_level,
        structlog.processors.JSONRenderer() if settings.log_format == "json" else structlog.dev.ConsoleRenderer()
    ]
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    logger.info("application_starting", version=settings.app_version)
    try:
        await check_db_connection()
        logger.info("database_connection_successful")
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
        raise

    yield

    # Shutdown
    logger.info("application_shutting_down")
    await dispose_engine()
    logger.info("database_engine_disposed")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)


# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Correlation ID middleware
@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    """Add correlation ID to request and response headers."""
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
    request.state.correlation_id = correlation_id

    # Bind correlation ID to structlog context
    structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

    response = await call_next(request)
    response.headers["X-Correlation-ID"] = correlation_id

    # Clear structlog context
    structlog.contextvars.clear_contextvars()

    return response


# Request logging middleware
@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    """Log all requests."""
    logger.info(
        "request_started",
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else None
    )

    response = await call_next(request)

    logger.info(
        "request_completed",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code
    )

    return response


# Exception handlers
app.add_exception_handler(AppException, app_exception_handler)


@app.exception_handler(JWTError)
async def jwt_exception_handler(request: Request, exc: JWTError):
    """Handle JWT errors."""
    logger.warning("jwt_error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={"detail": "Invalid authentication credentials"},
        headers={"WWW-Authenticate": "Bearer"}
    )


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    """Handle database errors."""
    logger.error("database_error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred"}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    logger.error("unexpected_error", error=str(exc), error_type=type(exc).__name__)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred"}
    )


# Include routers
app.include_router(auth_router, prefix=settings.api_prefix)
app.include_router(requests_router, prefix=settings.api_prefix)

# TODO: Add more routers here as they are implemented
# app.include_router(approvals_router, prefix=settings.api_prefix)
# app.include_router(admin_router, prefix=settings.api_prefix)


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": settings.app_version,
        "docs": "/api/docs",
        "redoc": "/api/redoc",
        "openapi": "/api/openapi.json"
    }


# Health check endpoints
@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check."""
    return {
        "status": "healthy",
        "version": settings.app_version
    }


@app.get(f"{settings.api_prefix}/health", tags=["Health"])
async def detailed_health_check():
    """Detailed health check with component status."""
    db_healthy = False
    try:
        await check_db_connection()
        db_healthy = True
    except Exception as e:
        logger.warning("health_check_db_failed", error=str(e))

    return {
        "status": "healthy" if db_healthy else "degraded",
        "version": settings.app_version,
        "components": {
            "database": "healthy" if db_healthy else "unhealthy"
        }
    }


# Run with uvicorn for development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=settings.backend_host,
        port=settings.backend_port,
        reload=True,
        log_level=settings.log_level.lower()
    )
