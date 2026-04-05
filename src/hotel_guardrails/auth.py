# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Authentication module for Hotel AI API.

Provides:
- bcrypt password hashing
- JWT token encode/decode with jti claim
- In-memory token blocklist for /auth/logout
- Per-IP and per-username login rate limiting
- Password-change invalidation (via iat vs password_changed_at check)
- FastAPI dependencies: get_current_user, require_admin, get_optional_user

Roles:
- 'user'  : registered guests (can access their own data, chat, bookings)
- 'admin' : hotel staff (full access to /admin/*, /dashboard/*, /settings/llm)

Production note:
- Token blocklist is in-memory. For multi-worker/multi-container setups use
  Redis. A single-container demo deployment works fine with in-memory.
- Password change invalidates ALL previously-issued tokens via the
  password_changed_at timestamp check — this is persistent across restarts.
"""
import os
import time
import uuid
import logging
import threading
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, Deque, Tuple

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from . import database as db

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

_INSECURE_DEFAULT_SECRET = "change-me-insecure-default-" + "x" * 40
JWT_SECRET = os.getenv("JWT_SECRET", _INSECURE_DEFAULT_SECRET)
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))

# Rate limiting
LOGIN_RATE_LIMIT_PER_IP = int(os.getenv("LOGIN_RATE_LIMIT_PER_IP", "10"))  # per minute
LOGIN_RATE_LIMIT_PER_USER = int(os.getenv("LOGIN_RATE_LIMIT_PER_USER", "5"))  # per minute
LOGIN_RATE_WINDOW_SEC = 60

# Account lockout
LOCKOUT_THRESHOLD = int(os.getenv("LOCKOUT_THRESHOLD", "5"))
LOCKOUT_MINUTES = int(os.getenv("LOCKOUT_MINUTES", "15"))

bearer_scheme = HTTPBearer(
    auto_error=False,
    description="Bearer JWT token from /auth/login",
)


def is_jwt_secret_insecure() -> bool:
    """Return True if JWT_SECRET is the default dev value or suspiciously short."""
    return (
        JWT_SECRET == _INSECURE_DEFAULT_SECRET
        or JWT_SECRET.startswith("change-me")
        or JWT_SECRET.startswith("dev-only")
        or len(JWT_SECRET) < 32
    )


if is_jwt_secret_insecure():
    logger.warning(
        "JWT_SECRET is insecure (default/short). "
        "Set JWT_SECRET to a long random string (>=32 chars) in production."
    )


# =============================================================================
# Password hashing
# =============================================================================


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt (12 rounds)."""
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
    """Create a signed JWT access token with a unique jti (JWT ID) claim."""
    to_encode = data.copy()
    hours = expires_hours if expires_hours is not None else JWT_EXPIRE_HOURS
    now = datetime.now(timezone.utc)
    to_encode.update({
        "iat": now,
        "exp": now + timedelta(hours=hours),
        "jti": uuid.uuid4().hex,
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
# Token blocklist (in-memory — use Redis for multi-worker deployments)
# =============================================================================


class TokenBlocklist:
    """In-memory JWT blocklist keyed by jti → expiry timestamp.

    Automatically purges expired entries to prevent unbounded growth.
    """

    def __init__(self) -> None:
        self._blocked: Dict[str, float] = {}
        self._lock = threading.Lock()
        self._last_purge = time.time()
        self._purge_interval = 300  # purge every 5 min

    def add(self, jti: str, exp_timestamp: float) -> None:
        """Block a token until its natural expiry."""
        with self._lock:
            self._blocked[jti] = exp_timestamp
            self._maybe_purge_locked()

    def contains(self, jti: str) -> bool:
        """Check if a jti is currently blocklisted (and not yet expired)."""
        with self._lock:
            self._maybe_purge_locked()
            exp = self._blocked.get(jti)
            if exp is None:
                return False
            if exp < time.time():
                # Already expired — remove and treat as not blocked
                self._blocked.pop(jti, None)
                return False
            return True

    def _maybe_purge_locked(self) -> None:
        """Remove expired entries. Caller must hold the lock."""
        now = time.time()
        if now - self._last_purge < self._purge_interval:
            return
        expired = [jti for jti, exp in self._blocked.items() if exp < now]
        for jti in expired:
            self._blocked.pop(jti, None)
        self._last_purge = now
        if expired:
            logger.debug(f"Purged {len(expired)} expired blocklist entries")

    def size(self) -> int:
        with self._lock:
            return len(self._blocked)


token_blocklist = TokenBlocklist()


# =============================================================================
# Login rate limiting + account lockout (in-memory sliding window)
# =============================================================================


class LoginRateLimiter:
    """Sliding-window rate limiter for login attempts.

    Tracks attempts per key (IP address or username) in a deque. Keys that
    exceed the threshold within the window are rejected until the oldest
    attempt ages out.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._attempts: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_record(self, key: str) -> Tuple[bool, int]:
        """
        Record an attempt and check whether it's allowed.

        Returns (allowed, retry_after_seconds). If not allowed, retry_after
        tells the client when the oldest attempt will age out of the window.
        """
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            q = self._attempts[key]
            # Drop old attempts outside the window
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= self.limit:
                retry_after = int(q[0] + self.window - now) + 1
                return False, max(retry_after, 1)

            q.append(now)
            return True, 0

    def reset(self, key: str) -> None:
        """Clear all recorded attempts for a key (e.g., after successful login)."""
        with self._lock:
            self._attempts.pop(key, None)


login_rate_limiter_ip = LoginRateLimiter(LOGIN_RATE_LIMIT_PER_IP, LOGIN_RATE_WINDOW_SEC)
login_rate_limiter_user = LoginRateLimiter(LOGIN_RATE_LIMIT_PER_USER, LOGIN_RATE_WINDOW_SEC)


def get_client_ip(request: Request) -> str:
    """Extract the client IP, respecting X-Forwarded-For when behind a proxy."""
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


# =============================================================================
# FastAPI dependencies
# =============================================================================


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    """
    FastAPI dependency: require a valid Bearer token and return the user dict.

    Raises 401 if:
    - Token is missing, invalid, or expired
    - jti is in the blocklist (logged out)
    - Token was issued before the user's last password change
    - User no longer exists or is inactive
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

    jti = payload.get("jti")
    if jti and token_blocklist.contains(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked / โทเค็นถูกยกเลิก",
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

    # Password-change invalidation: reject tokens issued before last password change
    iat = payload.get("iat")
    pwd_changed = user.get("password_changed_at")
    if iat is not None and pwd_changed is not None:
        iat_ts = float(iat)
        pwd_changed_ts = pwd_changed.timestamp() if hasattr(pwd_changed, "timestamp") else 0
        # Allow 1 second grace period for clock skew between insert and token creation
        if iat_ts + 1 < pwd_changed_ts:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalidated by password change / โทเค็นถูกยกเลิกเนื่องจากการเปลี่ยนรหัสผ่าน",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # Attach the raw token payload for endpoints that need jti (e.g., logout)
    user["_jwt_payload"] = payload
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

    jti = payload.get("jti")
    if jti and token_blocklist.contains(jti):
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
    """Convert DB user row to API-safe dict (no password_hash, no JWT payload)."""
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


def check_account_lockout(user: Dict[str, Any]) -> Optional[int]:
    """
    Check if an account is currently locked.

    Returns remaining lockout time in seconds if locked, None otherwise.
    """
    locked_until = user.get("locked_until")
    if locked_until is None:
        return None
    if hasattr(locked_until, "timestamp"):
        remaining = int(locked_until.timestamp() - time.time())
        if remaining > 0:
            return remaining
    return None
