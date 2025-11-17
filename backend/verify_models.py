#!/usr/bin/env python3
"""
Verification script to check if all models and repositories can be imported.

This script verifies that:
1. All models can be imported without errors
2. All repositories can be imported without errors
3. All enums are defined correctly
4. Database configuration is valid
"""
import sys
from typing import List, Tuple


def verify_imports() -> List[Tuple[str, bool, str]]:
    """
    Verify that all modules can be imported.

    Returns:
        List of (module_name, success, error_message) tuples
    """
    results = []

    # Test model imports
    model_tests = [
        "backend.models.base",
        "backend.models.enums",
        "backend.models.user",
        "backend.models.role",
        "backend.models.user_role",
        "backend.models.request",
        "backend.models.log_sample",
        "backend.models.ta_revision",
        "backend.models.validation_run",
        "backend.models.knowledge_document",
        "backend.models.audit_log",
        "backend.models.system_config",
        "backend.models",
    ]

    for module in model_tests:
        try:
            __import__(module)
            results.append((module, True, ""))
        except Exception as e:
            results.append((module, False, str(e)))

    # Test repository imports
    repo_tests = [
        "backend.repositories.base",
        "backend.repositories.user_repository",
        "backend.repositories.role_repository",
        "backend.repositories.request_repository",
        "backend.repositories.log_sample_repository",
        "backend.repositories.ta_revision_repository",
        "backend.repositories.validation_run_repository",
        "backend.repositories.knowledge_document_repository",
        "backend.repositories.audit_log_repository",
        "backend.repositories.system_config_repository",
        "backend.repositories",
    ]

    for module in repo_tests:
        try:
            __import__(module)
            results.append((module, True, ""))
        except Exception as e:
            results.append((module, False, str(e)))

    # Test database module
    try:
        __import__("backend.database")
        results.append(("backend.database", True, ""))
    except Exception as e:
        results.append(("backend.database", False, str(e)))

    return results


def verify_enums() -> List[Tuple[str, bool, str]]:
    """Verify that all enums are defined correctly."""
    results = []

    try:
        from backend.models.enums import (
            RequestStatus,
            ValidationStatus,
            TARevisionType,
            UserRoleEnum,
            AuditAction,
        )

        # Test RequestStatus
        assert hasattr(RequestStatus, "NEW")
        assert hasattr(RequestStatus, "PENDING_APPROVAL")
        assert hasattr(RequestStatus, "APPROVED")
        assert hasattr(RequestStatus, "REJECTED")
        assert hasattr(RequestStatus, "GENERATING_TA")
        assert hasattr(RequestStatus, "VALIDATING")
        assert hasattr(RequestStatus, "COMPLETED")
        assert hasattr(RequestStatus, "FAILED")
        results.append(("RequestStatus enum", True, ""))

        # Test ValidationStatus
        assert hasattr(ValidationStatus, "QUEUED")
        assert hasattr(ValidationStatus, "RUNNING")
        assert hasattr(ValidationStatus, "PASSED")
        assert hasattr(ValidationStatus, "FAILED")
        results.append(("ValidationStatus enum", True, ""))

        # Test TARevisionType
        assert hasattr(TARevisionType, "AUTO")
        assert hasattr(TARevisionType, "MANUAL")
        results.append(("TARevisionType enum", True, ""))

        # Test UserRoleEnum
        assert hasattr(UserRoleEnum, "REQUESTOR")
        assert hasattr(UserRoleEnum, "APPROVER")
        assert hasattr(UserRoleEnum, "ADMIN")
        assert hasattr(UserRoleEnum, "KNOWLEDGE_MANAGER")
        results.append(("UserRoleEnum enum", True, ""))

        # Test AuditAction
        assert hasattr(AuditAction, "CREATE")
        assert hasattr(AuditAction, "UPDATE")
        assert hasattr(AuditAction, "DELETE")
        assert hasattr(AuditAction, "APPROVE")
        assert hasattr(AuditAction, "REJECT")
        assert hasattr(AuditAction, "DOWNLOAD")
        assert hasattr(AuditAction, "UPLOAD")
        assert hasattr(AuditAction, "LOGIN")
        assert hasattr(AuditAction, "LOGOUT")
        results.append(("AuditAction enum", True, ""))

    except Exception as e:
        results.append(("Enums verification", False, str(e)))

    return results


def verify_model_relationships() -> List[Tuple[str, bool, str]]:
    """Verify that model relationships are defined correctly."""
    results = []

    try:
        from backend.models import User, Role, Request, LogSample, TARevision, ValidationRun

        # Check User model
        assert hasattr(User, "roles")
        assert hasattr(User, "requests")
        assert hasattr(User, "audit_logs")
        results.append(("User relationships", True, ""))

        # Check Role model
        assert hasattr(Role, "users")
        results.append(("Role relationships", True, ""))

        # Check Request model
        assert hasattr(Request, "created_by_user")
        assert hasattr(Request, "approved_by_user")
        assert hasattr(Request, "log_samples")
        assert hasattr(Request, "ta_revisions")
        assert hasattr(Request, "validation_runs")
        results.append(("Request relationships", True, ""))

        # Check LogSample model
        assert hasattr(LogSample, "request")
        results.append(("LogSample relationships", True, ""))

        # Check TARevision model
        assert hasattr(TARevision, "request")
        assert hasattr(TARevision, "uploaded_by_user")
        assert hasattr(TARevision, "validation_runs")
        results.append(("TARevision relationships", True, ""))

        # Check ValidationRun model
        assert hasattr(ValidationRun, "request")
        assert hasattr(ValidationRun, "ta_revision")
        results.append(("ValidationRun relationships", True, ""))

    except Exception as e:
        results.append(("Model relationships", False, str(e)))

    return results


def main():
    """Run all verification checks."""
    print("=" * 80)
    print("Database Models & Repositories Verification")
    print("=" * 80)
    print()

    all_passed = True

    # Test imports
    print("1. Testing imports...")
    import_results = verify_imports()
    for module, success, error in import_results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {module}")
        if not success:
            print(f"    Error: {error}")
            all_passed = False
    print()

    # Test enums
    print("2. Testing enums...")
    enum_results = verify_enums()
    for name, success, error in enum_results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {name}")
        if not success:
            print(f"    Error: {error}")
            all_passed = False
    print()

    # Test relationships
    print("3. Testing model relationships...")
    relationship_results = verify_model_relationships()
    for name, success, error in relationship_results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"  {status}: {name}")
        if not success:
            print(f"    Error: {error}")
            all_passed = False
    print()

    # Summary
    print("=" * 80)
    if all_passed:
        print("✓ All verification checks passed!")
        print("=" * 80)
        return 0
    else:
        print("✗ Some verification checks failed. Please review the errors above.")
        print("=" * 80)
        return 1


if __name__ == "__main__":
    sys.exit(main())
