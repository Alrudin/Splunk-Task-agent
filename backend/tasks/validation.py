"""
Celery task for TA validation in Splunk sandbox containers.

This task handles:
- Launching ephemeral Splunk containers
- Installing TA packages
- Ingesting sample logs
- Running validation searches
- Producing validation results and debug bundles
"""

import structlog
from celery import Celery
from backend.core.config import settings

logger = structlog.get_logger(__name__)

# Initialize Celery app
# Configuration should be loaded from settings
celery_app = Celery(
    "ta_validation",
    broker=getattr(settings, "celery_broker_url", "redis://localhost:6379/0"),
    backend=getattr(settings, "celery_result_backend", "redis://localhost:6379/0"),
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=600,  # 10 minutes max per validation
    task_soft_time_limit=540,  # Soft limit at 9 minutes
)


@celery_app.task(
    bind=True,
    name="tasks.validate_ta",
    max_retries=2,
    default_retry_delay=30,
)
def validate_ta_task(self, validation_run_id: str) -> dict:
    """
    Execute TA validation in a Splunk sandbox container.

    This task:
    1. Updates validation status to RUNNING
    2. Launches ephemeral Splunk container
    3. Installs the TA package
    4. Ingests sample logs from the request
    5. Runs validation searches
    6. Produces results with field coverage report
    7. Creates debug bundle on failure
    8. Updates validation status to PASSED/FAILED

    Args:
        validation_run_id: UUID string of the validation run to execute

    Returns:
        dict with validation results including:
        - overall_status: "PASSED" or "FAILED"
        - field_coverage: percentage of expected fields extracted
        - events_ingested: number of events indexed
        - cim_compliance: boolean indicating CIM compliance
        - extracted_fields: list of fields found
        - expected_fields: list of expected fields
        - errors: list of error messages (if any)
    """
    log = logger.bind(
        task_id=self.request.id,
        validation_run_id=validation_run_id,
    )
    log.info("validate_ta_task_started")

    try:
        # Import here to avoid circular dependencies and ensure
        # database session is created within the task context
        from backend.tasks._validation_executor import execute_validation

        result = execute_validation(validation_run_id)
        log.info("validate_ta_task_completed", result=result)
        return result

    except Exception as exc:
        log.exception("validate_ta_task_failed", error=str(exc))
        # Retry on transient failures
        raise self.retry(exc=exc)
