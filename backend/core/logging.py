"""
Centralized logging configuration using structlog.

This module configures structured logging for the entire application,
including custom processors for audit context (correlation_id, user_id, request_path).
"""

import logging
import sys
from typing import Any, Dict

import structlog
from structlog.types import EventDict, Processor

from backend.core.config import settings


def add_correlation_id(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add correlation_id to log context if present."""
    correlation_id = event_dict.get("correlation_id")
    if correlation_id:
        event_dict["correlation_id"] = str(correlation_id)
    return event_dict


def add_user_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add user_id to log context if present."""
    user_id = event_dict.get("user_id")
    if user_id:
        event_dict["user_id"] = str(user_id)
    return event_dict


def add_request_context(logger: logging.Logger, method_name: str, event_dict: EventDict) -> EventDict:
    """Add request path and method to log context if present."""
    request_path = event_dict.get("request_path")
    if request_path:
        event_dict["request_path"] = request_path

    request_method = event_dict.get("request_method")
    if request_method:
        event_dict["request_method"] = request_method

    return event_dict


def configure_logging() -> None:
    """
    Configure structlog for the application.

    Sets up processors including:
    - TimeStamper with ISO format
    - Log level addition
    - Stack info rendering (in dev mode)
    - Exception formatting
    - Custom audit context processors (correlation_id, user_id, request_path)
    - JSON or Console rendering based on settings

    Uses LOG_LEVEL and LOG_FORMAT from environment variables via settings.
    """
    # Determine log level from settings
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Build processor chain
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        add_correlation_id,
        add_user_context,
        add_request_context,
    ]

    # Add appropriate renderer based on format setting
    if settings.log_format.lower() == "json":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    """
    Get a configured structlog logger instance.

    Args:
        name: Logger name, typically __name__ of the calling module

    Returns:
        Configured structlog BoundLogger instance
    """
    return structlog.get_logger(name)


def bind_audit_context(**kwargs: Any) -> None:
    """
    Bind audit-specific context variables to the current context.

    Useful for adding context that should persist across multiple log calls
    within a request or task.

    Example:
        bind_audit_context(
            user_id="123e4567-e89b-12d3-a456-426614174000",
            correlation_id="789e0123-e89b-12d3-a456-426614174999",
            action="APPROVE"
        )

    Args:
        **kwargs: Key-value pairs to bind to logging context
    """
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_audit_context(*keys: str) -> None:
    """
    Remove specific keys from the logging context.

    Args:
        *keys: Keys to remove from context
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_audit_context() -> None:
    """Clear all bound context variables."""
    structlog.contextvars.clear_contextvars()
