"""
Utility functions for extracting audit-related context from FastAPI Request objects.

These utilities help capture client information (IP address, user agent)
and correlation IDs for comprehensive audit logging.
"""

from typing import Optional

from fastapi import Request


def get_client_ip(request: Request) -> Optional[str]:
    """
    Extract the client IP address from a FastAPI Request.

    Handles proxy scenarios by checking X-Forwarded-For and X-Real-IP headers
    before falling back to request.client.host.

    Args:
        request: FastAPI Request object

    Returns:
        Client IP address as string, or None if not available

    Example:
        ip_address = get_client_ip(request)
        # Returns: "192.168.1.100" or "10.0.0.5"
    """
    if request is None:
        return None

    # Check X-Forwarded-For header (comma-separated list, first is original client)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header (single IP)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fall back to direct client host
    if request.client and request.client.host:
        return request.client.host

    return None


def get_user_agent(request: Request) -> Optional[str]:
    """
    Extract the User-Agent header from a FastAPI Request.

    Args:
        request: FastAPI Request object

    Returns:
        User-Agent string, or None if not present

    Example:
        user_agent = get_user_agent(request)
        # Returns: "Mozilla/5.0 (Windows NT 10.0; Win64; x64)..."
    """
    if request is None:
        return None

    return request.headers.get("User-Agent")


def get_correlation_id(request: Request) -> Optional[str]:
    """
    Retrieve the correlation ID from the request state.

    The correlation ID is set by the correlation_id_middleware in main.py
    and stored in request.state.correlation_id as a string.

    Args:
        request: FastAPI Request object

    Returns:
        Correlation ID as string, or None if not available

    Example:
        correlation_id = get_correlation_id(request)
        # Returns: "123e4567-e89b-12d3-a456-426614174000"
    """
    if request is None:
        return None

    # Correlation ID is set by middleware in main.py as a string
    return getattr(request.state, "correlation_id", None)
