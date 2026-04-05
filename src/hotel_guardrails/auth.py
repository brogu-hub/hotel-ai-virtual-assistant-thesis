# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Authentication module for Hotel AI API.

Provides:
- bcrypt password hashing
- JWT token encode/decode
- FastAPI dependencies: get_current_user, require_admin, get_optional_user

Roles:
- 'user'  : registered guests (can access their own data, chat, bookings)
- 'admin' : hotel staff (full access to /admin/*, /dashboard/*, /settings/llm)
"""
import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from . import database as db

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

JWT_SECRET = os.getenv(
    "JWT_SECRET",
    "change-me-insecure-default-" + "x" * 40,
)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

if JWT_SECRET.startswith("change-me-insecure-default-"):
    logger.warning(
        "JWT_SECRET is using an insecure default. "
        "Set JWT_SECRET env var to a long random string in production."
    )

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Bearer JWT token from /auth/login",
)

# =============================================================================
# Password hashing
# =============================================================================


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt."""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            password.encode("utf-8"),
            password_hash.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


# =============================================================================
# JWT token operations
# =============================================================================


def create_access_token(data: Dict[str, Any], expires_hours: Optional[int] = None) -> str:
    """Create a signed JWT access token."""
    to_encode = data.copy()
    hours = expires_hours if expires_hours is not None else JWT_EXPIRE_HOURS
    now = datetime.now(timezone.utc)
    to_encode.update({
        "iat": now,
        "exp": now + timedelta(hours=hours),
    })
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT access token. Returns None if invalid/expired."""
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        logger.debug("JWT token expired")
        return None
    except jwt.PyJWTError as e:
        logger.debug(f"JWT decode error: {e}")
        return None


# =============================================================================
# FastAPI dependencies
# =============================================================================


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    """
    FastAPI dependency: require a valid Bearer token and return the user dict.

    Raises 401 if missing, invalid, expired, or user no longer exists/active.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated / ไม่ได้เข้าสู่ระบบ",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_access_token(credentials.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token / โทเค็นไม่ถูกต้องหรือหมดอายุ",
            headers={"WWW-Authenticate": "Bearer"},
        )

    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await db.get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found / ไม่พบผู้ใช้",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled / บัญชีถูกปิดการใช้งาน",
        )

    return user


async def require_admin(
    user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """FastAPI dependency: require an authenticated admin user."""
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required / ต้องมีสิทธิ์ผู้ดูแลระบบ",
        )
    return user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[Dict[str, Any]]:
    """FastAPI dependency: return user if authenticated, None otherwise. Never raises."""
    if credentials is None:
        return None

    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None

    username = payload.get("sub")
    if not username:
        return None

    try:
        user = await db.get_user_by_username(username)
    except Exception:
        return None

    if not user or not user.get("is_active", True):
        return None
    return user


# =============================================================================
# Helpers
# =============================================================================


def serialize_user(user: Dict[str, Any]) -> Dict[str, Any]:
    """Convert DB user row to API-safe dict (no password_hash)."""
    return {
        "user_id": user["user_id"],
        "username": user["username"],
        "email": user["email"],
        "role": user["role"],
        "full_name": user.get("full_name"),
        "is_active": bool(user.get("is_active", True)),
        "guest_id": user.get("guest_id"),
        "last_login": user["last_login"].isoformat() if user.get("last_login") else None,
        "created_at": user["created_at"].isoformat() if user.get("created_at") else "",
    }
