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
    USER_CREATED = "USER_CREATED"
    PASSWORD_CHANGED = "PASSWORD_CHANGED"
    TA_GENERATION_START = "TA_GENERATION_START"
    TA_GENERATION_COMPLETE = "TA_GENERATION_COMPLETE"
    TA_GENERATION_FAILED = "TA_GENERATION_FAILED"
    VALIDATION_START = "VALIDATION_START"
    VALIDATION_COMPLETE = "VALIDATION_COMPLETE"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    MANUAL_OVERRIDE = "MANUAL_OVERRIDE"
    REVALIDATION_TRIGGER = "REVALIDATION_TRIGGER"
    DEBUG_BUNDLE_DOWNLOAD = "DEBUG_BUNDLE_DOWNLOAD"
    TA_DOWNLOAD = "TA_DOWNLOAD"
    SAMPLE_UPLOAD = "SAMPLE_UPLOAD"
    KNOWLEDGE_UPLOAD = "KNOWLEDGE_UPLOAD"
    CONFIG_UPDATE = "CONFIG_UPDATE"
