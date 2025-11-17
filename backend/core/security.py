"""
Security utilities for password hashing and JWT token management.
"""
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
from passlib.context import CryptContext
from jose import jwt, JWTError
from jose.exceptions import ExpiredSignatureError

from backend.core.config import settings
from backend.core.exceptions import TokenExpiredError, InvalidTokenError


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password
    """
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against its hash.

    Args:
        plain_password: Plain text password
        hashed_password: Hashed password to verify against

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def create_jwt_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    """
    Create a JWT token with the given data and expiration.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Time delta for token expiration

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({
        "exp": expire,
        "iat": datetime.utcnow()
    })
    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Dictionary of token claims

    Raises:
        TokenExpiredError: If token has expired
        InvalidTokenError: If token is invalid
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )
        return payload
    except ExpiredSignatureError:
        raise TokenExpiredError()
    except JWTError:
        raise InvalidTokenError()


def get_correlation_id() -> str:
    """
    Generate a unique correlation ID for request tracing.

    Returns:
        UUID string for correlation
    """
    return str(uuid.uuid4())


def verify_csrf_token(token: str, session_token: str) -> bool:
    """
    Verify CSRF token against session token.

    Args:
        token: CSRF token to verify
        session_token: Session token to verify against

    Returns:
        True if tokens match, False otherwise
    """
    # Simple equality check for now
    # In production, use more sophisticated CSRF protection
    return token == session_token
