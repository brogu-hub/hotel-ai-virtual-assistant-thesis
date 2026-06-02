---
type: component
status: active
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/auth.py
related:
  - flows/auth_and_access_control
  - components/audit
  - decisions/dual_identity_model
  - modules/hotel_guardrails
tags: [component, auth, jwt, security, rate-limiting, bcrypt]
---

# Component: auth.py

## Purpose

`auth.py` implements the full authentication layer for the [[hotel_guardrails]] FastAPI server. It provides password hashing with bcrypt, JWT token issuance and validation, a token blocklist for logout, per-IP and per-username login rate limiting, account lockout, and a user-lookup TTL cache. The module also supplies three FastAPI dependency functions that endpoint handlers inject to gate access by role.

## Role model

Two roles are defined in code:

| Role | Who | Access |
|---|---|---|
| `user` | Registered guests | Own data, `/chat`, `/bookings`, `/guests` |
| `admin` | Hotel staff | Everything above plus `/admin/*`, `/dashboard/*`, `PUT /settings/llm` |

The [[dual_identity_model]] decision document explains why `guests` (hotel profile, email-only) and `users` (login credentials with role) are separate tables. Chat endpoints do not require any token — a guest can chat using email only. JWT is only required for account-management and admin routes.

> [!note] Design decision — unauthenticated chat
> The `/chat` endpoint accepts requests with no `Authorization` header. `get_optional_user` is used there (returns `None` rather than raising 401). This is intentional: frictionless chat is a hotel UX requirement. The auth layer protects write-mutations and admin surfaces, not the bot itself.

## JWT scheme

- **Algorithm:** HS256 via `PyJWT`
- **Secret:** Read from `JWT_SECRET` env var. Falls back to a hardcoded insecure default and logs a `WARNING` at import time if the default or any secret shorter than 32 characters is detected. See `is_jwt_secret_insecure()`.
- **Lifetime:** `JWT_EXPIRE_HOURS` env var (default 24 hours)
- **Claims:** standard `sub` (username), `iat`, `exp`, plus a unique `jti` (JWT ID) generated as `uuid4().hex`

### Token lifecycle

```
POST /auth/login
  → create_access_token({sub: username, role: role, user_id: id})
      → adds iat, exp, jti
      → jwt.encode() with JWT_SECRET / HS256

GET /auth/me or any protected route
  → decode_access_token()
      → PyJWT decode; returns None on expiry or signature error
  → check jti not in TokenBlocklist
  → check username exists and is_active
  → check iat >= password_changed_at (password-change invalidation)

POST /auth/logout
  → add jti to TokenBlocklist until token's natural exp
```

The `iat`-vs-`password_changed_at` check uses integer-second truncation on both sides to handle PyJWT's second-level precision. A token with `iat` strictly less than the DB-stored `password_changed_at` is rejected with HTTP 401. Because `password_changed_at` lives in PostgreSQL, this invalidation survives server restarts — unlike the in-memory JTI blocklist.

> [!key-insight] Password-change invalidation is durable; logout revocation is not
> After a server restart, any token that was revoked via `/auth/logout` (jti blocklist) becomes valid again. Only password-change-based invalidation (DB-backed) survives restart. For a single-container demo deployment this is acceptable; for production with stateful sessions or admin accounts, the blocklist must be migrated to Redis.

## In-memory components

### `TokenBlocklist`

Dict keyed by `jti → expiry_timestamp`. Thread-safe via `threading.Lock`. Self-purges expired entries every 300 seconds (lazy purge on access). In a multi-worker or multi-container setup this must be replaced with a Redis `SET jti "" EX ttl`.

### `LoginRateLimiter`

Sliding-window rate limiter for login attempts. Two instances are created:

| Instance | Env var | Default | Scope |
|---|---|---|---|
| `login_rate_limiter_ip` | `LOGIN_RATE_LIMIT_PER_IP` | 10/min | Per client IP |
| `login_rate_limiter_user` | `LOGIN_RATE_LIMIT_PER_USER` | 5/min | Per username |

`check_and_record(key)` returns `(allowed, retry_after_seconds)`. On rejection the endpoint returns HTTP 429 with a `Retry-After` header. The flow doc [[auth_and_access_control]] documents a historical default of 100/min per IP — the code value is 10/min. See the discrepancy note in that page.

### `UserCache`

TTL-based in-process cache for user lookups keyed on username (normalized lowercase). Default TTL is 30 seconds (`USER_CACHE_TTL_SECONDS` env var). Capacity is bounded at 5000 entries; when full, the oldest 10% are evicted. Provides a `stats()` method exposing hit rate for observability.

The cache is invalidated explicitly on password change and account disable. Without explicit invalidation, role/active-flag changes take up to 30 seconds to propagate to authenticated requests — the docstring acknowledges this as the intended tradeoff.

### Account lockout

`check_account_lockout(user)` reads `users.locked_until` from the user record and returns remaining seconds if the account is locked. Lockout is triggered after `LOCKOUT_THRESHOLD` (default 5) consecutive failed login attempts for `LOCKOUT_MINUTES` (default 15). The lockout state persists in the DB.

## FastAPI dependencies

Three dependency functions for use with `Depends()`:

| Dependency | Behavior |
|---|---|
| `get_current_user` | Requires valid Bearer token; raises 401/403 on any failure; returns full user dict with `_jwt_payload` attached |
| `require_admin` | Chains `get_current_user`; additionally checks `role == "admin"`; raises 403 if not |
| `get_optional_user` | Returns user dict if token valid and active, `None` otherwise; never raises |

`get_current_user` injects `_jwt_payload` into the returned dict as a shallow copy — the JWT claims are available to handlers without re-decoding, but the raw payload is never stored in the `UserCache` (documented comment in code).

## Helper utilities

- **`hash_password(password)`** — bcrypt with 12 rounds
- **`verify_password(password, hash)`** — bcrypt checkpw; catches `ValueError`/`TypeError`
- **`serialize_user(user)`** — strips `password_hash` and `_jwt_payload`; safe for API responses
- **`get_client_ip(request)`** — reads `X-Forwarded-For` first (proxy-aware); used by rate limiter and audit log
- **`is_jwt_secret_insecure()`** — checks for default/short secrets; called at module import

## Security-sensitive patterns

> [!key-insight] Insecure default secret with runtime warning only
> If `JWT_SECRET` is not set, tokens are signed with a hardcoded 66-character string beginning with `"change-me-insecure-default-"`. The module logs a warning but does not refuse to start. A misconfigured production deploy will silently accept forged tokens signed with the known default.

> [!gap] Thai-language error messages in HTTP responses
> Several 401/403 error strings include Thai-language translations inline (e.g., `"Not authenticated / ไม่ได้เข้าสู่ระบบ"`). This is an intentional bilingual UX choice for a Thai-market hotel, but the pattern is inconsistently applied — not all error paths have Thai text.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `JWT_SECRET` | `change-me-insecure-default-...` | HS256 signing secret |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRE_HOURS` | `24` | Token lifetime |
| `LOGIN_RATE_LIMIT_PER_IP` | `10` | Login attempts per IP per minute |
| `LOGIN_RATE_LIMIT_PER_USER` | `5` | Login attempts per username per minute |
| `LOCKOUT_THRESHOLD` | `5` | Failed login attempts before lockout |
| `LOCKOUT_MINUTES` | `15` | Lockout duration |
| `USER_CACHE_TTL_SECONDS` | `30` | User lookup cache TTL |

## Related

- [[flows/auth_and_access_control]] — end-to-end sequence diagrams for login, logout, password change
- [[components/audit]] — audit events emitted by the login/logout/register flows
- [[decisions/dual_identity_model]] — why guests and users are separate tables
- [[modules/hotel_guardrails]] — module overview listing all files
