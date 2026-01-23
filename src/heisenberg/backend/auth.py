"""Authentication utilities for Heisenberg backend."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import TYPE_CHECKING

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

if TYPE_CHECKING:
    pass

# API key header
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage using SHA-256.

    Args:
        api_key: Plain text API key.

    Returns:
        Hashed API key (hex string).
    """
    return hashlib.sha256(api_key.encode()).hexdigest()


def verify_api_key(plain_key: str, hashed_key: str) -> bool:
    """
    Verify an API key against its hash using constant-time comparison.

    Args:
        plain_key: Plain text API key to verify.
        hashed_key: Stored hash to verify against.

    Returns:
        True if the key matches, False otherwise.
    """
    computed_hash = hash_api_key(plain_key)
    return hmac.compare_digest(computed_hash, hashed_key)


def generate_api_key(prefix: str = "hb") -> str:
    """
    Generate a new API key.

    Args:
        prefix: Prefix for the key (default: "hb" for Heisenberg).

    Returns:
        New API key in format: prefix_randomstring
    """
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"


async def get_api_key(
    api_key: str | None = Security(_api_key_header),
) -> str:
    """
    FastAPI dependency to extract and validate API key from header.

    Args:
        api_key: API key from X-API-Key header.

    Returns:
        The API key if valid.

    Raises:
        HTTPException: If API key is missing or invalid.
    """
    if api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
