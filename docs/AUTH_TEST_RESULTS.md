# Authentication Test Results

**Date:** 2026-04-05
**Test scripts:** `scripts/test_auth.py` + `scripts/test_auth_hardening.py`
**Result:** **110 / 110 tests passed** (72 baseline auth + 38 hardening)

## Environment
- Backend: `hotel-api` container (Docker)
- Database: `hotel-db` (PostgreSQL 16)
- Auth: JWT (HS256) + bcrypt (12 rounds)
- Libraries: `PyJWT 2.12.1`, `bcrypt 5.0.0`
- Hardening: jti blocklist, rate limiting, account lockout, password-change invalidation

## Test Coverage

### Baseline Auth (`test_auth.py`) — 72/72

| Part | Area | Tests |
|---|---|---|
| A | Default admin login + JWT response structure | 6/6 |
| B | User registration (success + duplicate + password/username validation) | 6/6 |
| C | User login (username + email + wrong password + nonexistent) | 5/5 |
| D | `/auth/me` (unauthenticated / valid / invalid / malformed token + password_hash leak check) | 8/8 |
| E | Admin endpoint access control (2 endpoints × {no-auth / user / admin}) | 6/6 |
| F | Dashboard endpoint protection (5 endpoints × 3 scenarios) | 15/15 |
| G | Admin-only admin creation (user→403, no-auth→401, admin→200, new admin can login) | 6/6 |
| H | User listing (list + filter by role + no password_hash leak + user→403) | 7/7 |
| I | Public endpoint accessibility + `PUT /settings/llm` protected | 6/6 |
| J | JWT payload validation (sub / role / exp / iat claims + expiry window) | 7/7 |

### Hardening (`test_auth_hardening.py`) — 38/38

| Part | Area | Tests |
|---|---|---|
| K | Token blocklist / `/auth/logout` (9 scenarios inc. double logout, post-logout login, old-token-stays-blocked) | 9/9 |
| L | Login rate limiting — per-username 5/min triggers 429 with Retry-After header | 4/4 |
| M | Account lockout — 5 failed attempts → 423/429 even with correct password, visible in admin listing | 4/4 |
| N | `PATCH /auth/me/password` — wrong current (401), same password (400), short (422), success invalidates old token, new login works, old rejected | 9/9 |
| O | Server operational despite insecure JWT_SECRET warning | 1/1 |
| P | JWT `jti` claim — present, hex string ≥16 chars, unique per token | 3/3 |
| Q | Edge cases — user token rejected from admin even after hardening, password change preserves role, tampered JWT → 401, blocklist persistence across multiple requests | 8/8 |

## Key Verifications

### Access control matrix (per endpoint)

| Scenario | `/auth/me` | `/admin/*` | `/dashboard/*` | `PUT /settings/llm` | `/chat`, `/rooms`, `/health` |
|---|---|---|---|---|---|
| No token | 401 | 401 | 401 | 401 | 200 |
| Valid user token | 200 | 403 | 403 | 403 | 200 |
| Valid admin token | 200 | 200 | 200 | 200 | 200 |
| Invalid/expired JWT | 401 | 401 | 401 | 401 | 200 |
| Logged-out (blocklisted) | 401 | 401 | 401 | 401 | 200 |
| Token pre-dating password change | 401 | 401 | 401 | 401 | 200 |

### Security properties verified

- **bcrypt 12 rounds** — all hashes in DB confirmed starting with `$2b$12$`
- **No password_hash leak** — `/auth/me`, `/auth/users`, login, and password change responses never include `password_hash`
- **JWT contains role claim** — downstream `require_admin` dependency checks `role == "admin"`
- **JWT expiry** — 24h lifetime, `exp` field validated in the future
- **JWT jti claim** — unique UUID per token for blocklist keying
- **Username = email fallback** — login accepts either as the identifier
- **Guest flow untouched** — `/chat`, `/rooms`, `/health`, `GET /settings/llm` remain public
- **Admin-only admin creation** — users cannot self-promote; `/auth/admin/register` requires existing admin JWT
- **last_login timestamp** — updated on every successful login
- **Account lockout** — 5 failed attempts trigger 15-minute lockout, visible in DB `locked_until` column
- **Rate limiting** — per-IP (100/min) + per-username (5/min) sliding window with `Retry-After` header
- **Token revocation on logout** — in-memory jti blocklist persists across multiple requests until token natural expiry
- **Password change invalidates all prior tokens** — via `password_changed_at` timestamp check in `get_current_user` (persistent across server restarts, unlike in-memory blocklist)

### Database state (after tests)

Sample rows demonstrating hardening features in action:

```
user_id | username                  | role  | failed_login_attempts | locked_until              | password_is_default
--------+---------------------------+-------+-----------------------+---------------------------+---------------------
1       | admin                     | admin | 0                     | —                         | f
9       | ratelimit_be69551a_624c6d | user  | 5                     | 2026-04-05 13:15:59       | f
16      | lockout_2e78d58f_187c9f   | user  | 5                     | 2026-04-05 13:28:25       | f
17      | pwchange_2e78d58f_c8ccc1  | user  | 1                     | —                         | f
```

## New Endpoints (7 total)

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | Public | Register as `user` role |
| POST | `/auth/login` | Public | Login (username OR email), rate-limited, lockout-protected |
| GET | `/auth/me` | Bearer | Current user profile |
| POST | `/auth/logout` | Bearer | Revoke current token (blocklist jti) |
| PATCH | `/auth/me/password` | Bearer | Change password, invalidates all prior tokens |
| POST | `/auth/admin/register` | Admin | Create new admin account |
| GET | `/auth/users` | Admin | List all users (filter by role) |

## Protected Endpoints (require admin JWT)

**Admin (11):** `PUT /admin/rooms/{id}/status`, `PUT /admin/bookings/{id}/status`, `POST /admin/chat/override`, `POST /admin/sessions/{id}/takeover`, `POST /admin/sessions/{id}/release`, `GET /admin/sessions`, `GET /admin/sessions/{id}/messages`, `GET /admin/escalations`, `GET /admin/sessions/{id}/states`, `POST /admin/sessions/{id}/rollback`, `POST /admin/sessions/{id}/replay`

**Dashboard (5):** `GET /dashboard/stats`, `GET /dashboard/bookings/recent`, `GET /dashboard/sessions`, `GET /dashboard/rooms`, `GET /dashboard/revenue`

**Settings (1):** `PUT /settings/llm`

## Configuration (env vars)

| Variable | Default | Description |
|---|---|---|
| `JWT_SECRET` | `dev-only-...` | JWT signing secret — **MUST** rotate in production |
| `JWT_ALGORITHM` | `HS256` | JWT algorithm |
| `JWT_EXPIRE_HOURS` | `24` | Token lifetime |
| `LOGIN_RATE_LIMIT_PER_IP` | `100` | Max login attempts per IP per minute |
| `LOGIN_RATE_LIMIT_PER_USER` | `5` | Max login attempts per username per minute |
| `LOCKOUT_THRESHOLD` | `5` | Failed attempts before lockout |
| `LOCKOUT_MINUTES` | `15` | Lockout duration |
| `DEFAULT_ADMIN_USERNAME` | `admin` | Seeded on first startup |
| `DEFAULT_ADMIN_EMAIL` | `admin@grandhorizon.hotel` | Seeded on first startup |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | **MUST** rotate in production |

## Startup Warnings

On server startup, the following warnings are emitted when insecure defaults are detected:

```
======================================================================
PRODUCTION SECURITY WARNINGS:
  [!] JWT_SECRET is insecure (default or <32 chars). Tokens can be forged.
      Set a long random JWT_SECRET env var.
  [!] At least one admin still uses the default seed password.
      Log in and call PATCH /auth/me/password to rotate it.
======================================================================
```

## Production Hardening — COMPLETED

- [x] **Rate limiting** on `/auth/login` — per-IP + per-username sliding window
- [x] **Account lockout** after 5 failed attempts (15-minute lockout)
- [x] **`/auth/logout` + token blocklist** — jti-based in-memory revocation
- [x] **`PATCH /auth/me/password`** — with current-password verification, persistent token invalidation via `password_changed_at`
- [x] **Startup warnings** for insecure `JWT_SECRET` / unchanged `DEFAULT_ADMIN_PASSWORD`
- [x] **JWT `jti` claim** for per-token identity
- [x] **Password change preserves role** (verified)
- [x] **Tampered JWT signature rejected** (verified)

## Still Recommended (not yet done)

- [ ] Redis-backed token blocklist for multi-worker/multi-container deployments (in-memory works for single-container demo)
- [ ] Refresh token flow for shorter access token lifetimes without re-login
- [ ] Password strength meter on frontend (min 8 chars enforced on backend only)
- [ ] Audit log for admin actions (who locked whom, who created admins)
- [ ] 2FA/TOTP for admin accounts
- [ ] HTTPS enforcement (HSTS header) — deployment-level concern
