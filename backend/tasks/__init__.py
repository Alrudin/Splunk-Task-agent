"""
Celery tasks package for asynchronous background processing.

This module contains task definitions for:
- TA validation in Splunk sandbox containers
- Debug bundle generation
- Other async operations
"""

from backend.tasks.validation import validate_ta_task

__all__ = ["validate_ta_task"]
