"""
Celery tasks module for background task processing.

This module contains:
- celery_app: Celery application configuration
- generate_ta_task: TA generation background task
- validate_ta_task: TA validation background task (future)
"""

from backend.tasks.celery_app import celery_app

__all__ = ["celery_app"]
