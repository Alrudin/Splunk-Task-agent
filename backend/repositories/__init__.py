"""
Repositories package for data access layer.

This module exports all repository classes for easy importing
throughout the application.
"""
from backend.repositories.base import BaseRepository
from backend.repositories.user_repository import UserRepository
from backend.repositories.role_repository import RoleRepository
from backend.repositories.request_repository import RequestRepository
from backend.repositories.log_sample_repository import LogSampleRepository
from backend.repositories.ta_revision_repository import TARevisionRepository
from backend.repositories.validation_run_repository import ValidationRunRepository
from backend.repositories.knowledge_document_repository import KnowledgeDocumentRepository
from backend.repositories.audit_log_repository import AuditLogRepository
from backend.repositories.system_config_repository import SystemConfigRepository

__all__ = [
    "BaseRepository",
    "UserRepository",
    "RoleRepository",
    "RequestRepository",
    "LogSampleRepository",
    "TARevisionRepository",
    "ValidationRunRepository",
    "KnowledgeDocumentRepository",
    "AuditLogRepository",
    "SystemConfigRepository",
]
