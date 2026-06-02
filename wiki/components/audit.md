---
type: component
status: active
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/audit.py
related:
  - flows/admin_monitoring
  - components/auth
  - modules/hotel_guardrails
tags: [component, audit, logging, compliance, privacy, admin]
---

# Component: audit.py

## Purpose

`audit.py` provides a structured audit trail for the [[hotel_guardrails]] service. It defines a flat taxonomy of action-name constants (`AuditActions`) and a single async function `audit()` that writes a record to the `audit_log` PostgreSQL table via `database.log_audit()`. Every admin endpoint that mutates state or reads guest PII is expected to call this function.

The design philosophy is deliberately best-effort: any database failure inside `audit()` is caught, logged to the Python logger, and swallowed. Audit must never break the business flow it is observing.

## `AuditActions` taxonomy

Action names follow a `{domain}.{object}.{verb}` convention. Full list:

| Domain | Constant | Action string |
|---|---|---|
| Auth | `LOGIN_SUCCESS` | `auth.login.success` |
| Auth | `LOGIN_FAILED` | `auth.login.failed` |
| Auth | `LOGIN_LOCKED` | `auth.login.locked` |
| Auth | `LOGIN_RATE_LIMITED` | `auth.login.rate_limited` |
| Auth | `LOGOUT` | `auth.logout` |
| Auth | `REGISTER` | `auth.register` |
| Auth | `PASSWORD_CHANGED` | `auth.password.changed` |
| Auth | `PASSWORD_CHANGE_FAILED` | `auth.password.change_failed` |
| User management | `ADMIN_CREATED` | `user.admin.created` |
| User management | `USERS_LISTED` | `user.list` |
| Room/booking | `ROOM_STATUS_CHANGED` | `admin.room.status_changed` |
| Room/booking | `BOOKING_STATUS_CHANGED` | `admin.booking.status_changed` |
| Chat/session | `CHAT_OVERRIDE` | `admin.chat.override` |
| Chat/session | `SESSION_TAKEOVER` | `admin.session.takeover` |
| Chat/session | `SESSION_RELEASE` | `admin.session.release` |
| Chat/session | `SESSION_VIEWED` | `admin.session.viewed` |
| Chat/session | `SESSIONS_LISTED` | `admin.session.listed` |
| Chat/session | `SESSION_ROLLBACK` | `admin.session.rollback` |
| Chat/session | `SESSION_REPLAY` | `admin.session.replay` |
| Chat/session | `ESCALATIONS_VIEWED` | `admin.escalations.viewed` |
| System | `LLM_CONFIG_CHANGED` | `settings.llm.changed` |
| System | `AUDIT_VIEWED` | `admin.audit.viewed` |

> [!note] Meta-audit
> Reading the audit log itself (`GET /admin/audit`) writes an `admin.audit.viewed` entry. This means the audit trail is self-referencing — any admin that inspects audit history is themselves audited.

## `audit()` function signature

```python
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
) -> None
```

Callers pass either `actor` (a full user dict from `get_current_user`, which extracts `user_id`, `username`, and `role`) or `actor_username` (a bare string for unauthenticated events like failed login attempts). The `details` dict is stored as JSONB and can carry arbitrary context (e.g., `{"new_status": "maintenance", "notes": "plumbing"}` for a room status change).

## Log schema (PostgreSQL)

The `audit_log` table, as defined in `init-hotel.sql`:

```sql
audit_log (
    audit_id       BIGSERIAL PRIMARY KEY
    actor_user_id  INTEGER REFERENCES users(user_id)
    actor_username VARCHAR(64)
    actor_role     VARCHAR(20)       -- 'user' | 'admin'
    action         VARCHAR(100)      -- AuditActions constant value
    resource_type  VARCHAR(50)       -- e.g. 'session', 'booking', 'room'
    resource_id    VARCHAR(100)
    details        JSONB
    ip_address     VARCHAR(45)       -- IPv4 or IPv6; respects X-Forwarded-For
    user_agent     VARCHAR(500)
    success        BOOLEAN
    created_at     TIMESTAMP DEFAULT now()
)
```

The IP is extracted via `_get_client_ip(request)`, which reads `X-Forwarded-For` (honoring Railway/proxy deployments) before falling back to `request.client.host`. The user-agent string is stored verbatim from the `User-Agent` header.

## Retention and querying

The `audit_log` table has no TTL or automated pruning configured in the current codebase. `GET /admin/audit` supports `LIMIT`/`OFFSET` pagination with `action_prefix` and `actor_username` query filters. `GET /admin/audit/stats` returns aggregated counts.

> [!gap] No retention policy
> There is no automated log rotation, partition, or deletion policy in `audit.py` or `init-hotel.sql`. For a production system handling EU guest data under GDPR, a retention window (e.g., 90 days) should be enforced. This is a compliance gap.

## Privacy implications

`SESSION_VIEWED` is the most sensitive action: it records which admin account read which guest's full conversation history, including date/time and IP. This is the minimal audit trail required for GDPR Article 30 (Records of Processing Activities). However, the `details` JSONB field is unconstrained — callers could inadvertently write PII into audit records (e.g., pasting a booking reference that contains a guest name). No PII scrubbing is applied to the `details` payload before it reaches the DB.

> [!key-insight] Audit details are not PII-scrubbed
> The `details` dict passed to `audit()` is written directly to PostgreSQL JSONB with no PII filtering. If a caller passes a guest name, email, or booking detail in `details`, it enters the audit log in plaintext. This is a potential compliance gap for GDPR/PDPA (Thailand's Personal Data Protection Act).

## Sink

Single sink: PostgreSQL `audit_log` table via `db.log_audit()`. There is no file-based or stdout audit sink, no SIEM forwarding, and no webhook. Failures at the DB level are caught and logged to the Python standard logger (`logger.error`) but do not propagate.

## Related

- [[flows/admin_monitoring]] — full list of audited admin endpoints and query flow diagrams
- [[components/auth]] — auth events that call `audit()`
- [[concepts/pii_redaction_and_compliance]] — compliance context
- [[modules/hotel_guardrails]] — module overview
