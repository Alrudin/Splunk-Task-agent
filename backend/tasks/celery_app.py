"""
Celery application configuration for background task processing.

This module configures the Celery application with Redis as broker and backend,
defines task routing, and sets up worker configuration.
"""
import os

from celery import Celery

# Get Redis URL from environment
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/1")

# Create Celery application
celery_app = Celery(
    "splunk_ta_generator",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,

    # Task routing - route tasks to specific queues
    task_routes={
        "generate_ta": {"queue": "ta_generation"},
        "validate_ta": {"queue": "validation"},
    },

    # Task time limits
    task_time_limit=int(os.getenv("CELERY_TASK_TIME_LIMIT", 3600)),  # Hard limit (1 hour default)
    task_soft_time_limit=int(os.getenv("CELERY_TASK_SOFT_TIME_LIMIT", 3300)),  # Soft limit (55 min)

    # Worker settings
    worker_prefetch_multiplier=1,  # Fetch one task at a time for long-running tasks
    worker_max_tasks_per_child=int(os.getenv("CELERY_WORKER_MAX_TASKS", 10)),  # Restart after 10 tasks
    worker_concurrency=int(os.getenv("CELERY_WORKER_CONCURRENCY", 4)),

    # Result settings
    result_expires=86400,  # Results expire after 24 hours
    result_extended=True,  # Store additional task metadata

    # Task tracking
    task_track_started=True,
    task_send_sent_event=True,

    # Beat scheduler (if using periodic tasks)
    beat_scheduler="celery.beat:PersistentScheduler",
)

# Define task queues
celery_app.conf.task_queues = {
    "default": {"exchange": "default", "routing_key": "default"},
    "ta_generation": {"exchange": "ta_generation", "routing_key": "ta_generation"},
    "validation": {"exchange": "validation", "routing_key": "validation"},
}

# Default queue for tasks without explicit routing
celery_app.conf.task_default_queue = "default"


# Import tasks to register them with Celery
# Note: These imports must happen after celery_app is created to avoid circular imports
def register_tasks():
    """Register all task modules with Celery."""
    # Import tasks here to register them
    from backend.tasks import generate_ta_task  # noqa: F401
    from backend.tasks import validate_ta_task  # noqa: F401


# Auto-discover tasks when Celery starts
@celery_app.on_after_configure.connect
def setup_tasks(sender, **kwargs):
    """Called after Celery is configured."""
    register_tasks()
