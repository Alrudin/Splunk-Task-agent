"""
Models package for database entities.

This module exports all SQLAlchemy models and enums for easy importing
throughout the application.
"""
from backend.models.base import Base, TimestampMixin
from backend.models.enums import (
    AuditAction,
    RequestStatus,
    TARevisionType,
    UserRoleEnum,
    ValidationStatus,
)
from backend.models.user import User
from backend.models.role import Role
from backend.models.user_role import UserRole
from backend.models.request import Request
from backend.models.log_sample import LogSample
from backend.models.ta_revision import TARevision
from backend.models.validation_run import ValidationRun
from backend.models.knowledge_document import KnowledgeDocument
from backend.models.audit_log import AuditLog
from backend.models.system_config import SystemConfig

__all__ = [
    # Base classes
    "Base",
    "TimestampMixin",

    # Enums
    "AuditAction",
    "RequestStatus",
    "TARevisionType",
    "UserRoleEnum",
    "ValidationStatus",

    # Models
    "User",
    "Role",
    "UserRole",
    "Request",
    "LogSample",
    "TARevision",
    "ValidationRun",
    "KnowledgeDocument",
    "AuditLog",
    "SystemConfig",
]
