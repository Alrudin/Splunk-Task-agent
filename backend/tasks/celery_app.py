"""
Celery application configuration for background task processing.

This module configures the Celery application with Redis as the message broker
and result backend. Tasks are auto-discovered from the backend.tasks module.

Usage:
    Start worker: celery -A backend.tasks.celery_app worker --loglevel=info
    Start beat: celery -A backend.tasks.celery_app beat --loglevel=info
"""

import structlog
from celery import Celery

from backend.core.config import settings

logger = structlog.get_logger(__name__)

# Initialize Celery application
celery_app = Celery(
    "splunk_ta_generator",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
celery_app.conf.update(
    # Serialization settings
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timezone settings
    timezone="UTC",
    enable_utc=True,

    # Task execution settings
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,

    # Reliability settings
    task_acks_late=True,  # Acknowledge after task completion
    task_reject_on_worker_lost=True,  # Reject task if worker dies
    worker_prefetch_multiplier=1,  # Prevent task hoarding

    # Result settings
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store additional task metadata

    # Task routing
    task_routes={
        "backend.tasks.generate_ta_task.generate_ta": {"queue": "ta_generation"},
        "backend.tasks.validate_ta_task.validate_ta": {"queue": "validation"},
    },

    # Default queue
    task_default_queue="default",

    # Worker settings
    worker_max_tasks_per_child=100,  # Restart worker after 100 tasks to prevent memory leaks
    worker_disable_rate_limits=True,

    # Logging
    worker_hijack_root_logger=False,  # Don't hijack root logger (use structlog)
)

# Auto-discover tasks in the backend.tasks module
celery_app.autodiscover_tasks(["backend.tasks"])

logger.info(
    "celery_app_configured",
    broker_url=settings.celery_broker_url,
    result_backend=settings.celery_result_backend,
    task_time_limit=settings.celery_task_time_limit,
    worker_concurrency=settings.celery_worker_concurrency,
)
