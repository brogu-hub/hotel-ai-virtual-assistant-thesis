# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Audit logging for admin actions, authentication events, and privacy-sensitive
operations (viewing guest conversations, overriding bookings, etc.).

Usage from endpoint handlers:

    from .audit import audit, AuditActions

    await audit(
        http_request,
        actor=current_admin,
        action=AuditActions.ROOM_STATUS_CHANGED,
        resource_type="room",
        resource_id=str(room_id),
        details={"new_status": status, "notes": notes},
    )

Every admin endpoint that mutates state or reads guest PII should call audit.
"""
import logging
from typing import Optional, Dict, Any

from fastapi import Request

from . import database as db

logger = logging.getLogger(__name__)


class AuditActions:
    """String constants for audit action names.

    Format: {domain}.{object}.{verb}
    """

    # --- Authentication ---
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    LOGIN_LOCKED = "auth.login.locked"
    LOGIN_RATE_LIMITED = "auth.login.rate_limited"
    LOGOUT = "auth.logout"
    REGISTER = "auth.register"
    PASSWORD_CHANGED = "auth.password.changed"
    PASSWORD_CHANGE_FAILED = "auth.password.change_failed"

    # --- User management ---
    ADMIN_CREATED = "user.admin.created"
    USERS_LISTED = "user.list"

    # --- Room / booking overrides ---
    ROOM_STATUS_CHANGED = "admin.room.status_changed"
    BOOKING_STATUS_CHANGED = "admin.booking.status_changed"

    # --- Chat / session intervention (privacy-sensitive) ---
    CHAT_OVERRIDE = "admin.chat.override"
    SESSION_TAKEOVER = "admin.session.takeover"
    SESSION_RELEASE = "admin.session.release"
    SESSION_VIEWED = "admin.session.viewed"  # admin reads guest conversation
    SESSIONS_LISTED = "admin.session.listed"
    SESSION_ROLLBACK = "admin.session.rollback"
    SESSION_REPLAY = "admin.session.replay"
    ESCALATIONS_VIEWED = "admin.escalations.viewed"

    # --- System / settings ---
    LLM_CONFIG_CHANGED = "settings.llm.changed"
    AUDIT_VIEWED = "admin.audit.viewed"


def _get_client_ip(request: Optional[Request]) -> Optional[str]:
    """Extract the client IP, respecting X-Forwarded-For."""
    if request is None:
        return None
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _get_user_agent(request: Optional[Request]) -> Optional[str]:
    if request is None:
        return None
    return request.headers.get("User-Agent")


async def audit(
    request: Optional[Request],
    *,
    action: str,
    actor: Optional[Dict[str, Any]] = None,
    actor_username: Optional[str] = None,
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
) -> None:
    """
    Write an audit log entry.

    Either `actor` (a user dict from get_current_user) or `actor_username`
    (for unauthenticated events like failed logins) should be provided.

    This function is best-effort — any DB error is swallowed and logged
    rather than propagated to the caller. Audit must never break the
    business flow.
    """
    try:
        if actor:
            actor_user_id = actor.get("user_id")
            username = actor.get("username")
            role = actor.get("role")
        else:
            actor_user_id = None
            username = actor_username
            role = None

        await db.log_audit(
            action=action,
            actor_user_id=actor_user_id,
            actor_username=username,
            actor_role=role,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
            success=success,
        )
    except Exception as e:
        # Never propagate audit failures — log and continue
        logger.error(f"audit() failed (action={action}): {e}")
