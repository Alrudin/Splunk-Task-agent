"""
Database configuration module with async SQLAlchemy engine and session management.

This module provides the database connection, session factory, and utility
functions for database initialization and health checks.
"""
import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy import text

from backend.models import Base


# Database configuration from environment variables
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/splunk_ta_generator")
DATABASE_POOL_SIZE = int(os.getenv("DATABASE_POOL_SIZE", "10"))
DATABASE_MAX_OVERFLOW = int(os.getenv("DATABASE_MAX_OVERFLOW", "20"))
DATABASE_ECHO = os.getenv("DATABASE_ECHO", "false").lower() == "true"


# Create async engine
engine: AsyncEngine = create_async_engine(
    DATABASE_URL,
    echo=DATABASE_ECHO,
    pool_size=DATABASE_POOL_SIZE,
    max_overflow=DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using them
)


# Create async session factory
async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Better async performance
    autoflush=False,
    autocommit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency function that yields AsyncSession instances.

    Use this with FastAPI's Depends() for dependency injection.

    Example:
        @app.get("/users")
        async def get_users(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize the database by creating all tables.

    NOTE: This is for development only. In production, use Alembic migrations.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """
    Drop all database tables.

    WARNING: This will delete all data. Use with caution!
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def check_db_connection() -> bool:
    """
    Health check function to verify database connectivity.

    Returns:
        bool: True if connection is successful, False otherwise.
    """
    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        print(f"Database connection check failed: {e}")
        return False


async def dispose_engine() -> None:
    """
    Dispose of the database engine and close all connections.

    Call this during application shutdown.
    """
    await engine.dispose()
