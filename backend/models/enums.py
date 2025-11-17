"""
Enum definitions for database models.

This module defines Python enums for status and type fields to ensure
type safety and consistency across the application.
"""
from enum import Enum


class RequestStatus(str, Enum):
    """Status values for Request entity."""
    NEW = "NEW"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    GENERATING_TA = "GENERATING_TA"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ValidationStatus(str, Enum):
    """Status values for ValidationRun entity."""
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PASSED = "PASSED"
    FAILED = "FAILED"


class TARevisionType(str, Enum):
    """Type values for TARevision entity."""
    AUTO = "AUTO"  # AI-generated
    MANUAL = "MANUAL"  # Human override


class UserRoleEnum(str, Enum):
    """Role values for Role entity."""
    REQUESTOR = "REQUESTOR"
    APPROVER = "APPROVER"
    ADMIN = "ADMIN"
    KNOWLEDGE_MANAGER = "KNOWLEDGE_MANAGER"


class AuditAction(str, Enum):
    """Action values for AuditLog entity."""
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    DOWNLOAD = "DOWNLOAD"
    UPLOAD = "UPLOAD"
    LOGIN = "LOGIN"
    LOGOUT = "LOGOUT"
