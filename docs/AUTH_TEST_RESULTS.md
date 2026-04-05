# Authentication Test Results

**Date:** 2026-04-05
**Test script:** `scripts/test_auth.py`
**Result:** **72 / 72 tests passed**

## Environment
- Backend: `hotel-api` container (Docker)
- Database: `hotel-db` (PostgreSQL 16)
- Auth: JWT (HS256) + bcrypt (12 rounds)
- Libraries: `PyJWT 2.12.1`, `bcrypt 5.0.0`

## Test Coverage (72 assertions)

| Part | Area | Tests | Result |
|---|---|---|---|
| A | Default admin login + JWT response structure | 6 | 6/6 |
| B | User registration (success + duplicate + password/username validation) | 6 | 6/6 |
| C | User login (username + email + wrong password + nonexistent) | 5 | 5/5 |
| D | `/auth/me` (unauthenticated / valid / invalid / malformed token + password_hash leak check) | 8 | 8/8 |
| E | Admin endpoint access control (2 endpoints × {no-auth / user / admin}) | 6 | 6/6 |
| F | Dashboard endpoint protection (5 endpoints × 3 scenarios) | 15 | 15/15 |
| G | Admin-only admin creation (user→403, no-auth→401, admin→200, new admin can login) | 6 | 6/6 |
| H | User listing (list + filter by role + no password_hash leak + user→403) | 7 | 7/7 |
| I | Public endpoint accessibility (`/chat`, `/rooms`, `/health`, read-only settings) + `PUT /settings/llm` protected | 6 | 6/6 |
| J | JWT payload validation (sub / role / exp / iat claims + expiry window) | 7 | 7/7 |

## Key Verifications

### Access control matrix (per endpoint)

| Scenario | `/auth/me` | `/admin/*` | `/dashboard/*` | `PUT /settings/llm` | `/chat`, `/rooms`, `/health` |
|---|---|---|---|---|---|
| No token | 401 | 401 | 401 | 401 | 200 |
| Valid user token | 200 | 403 | 403 | 403 | 200 |
| Valid admin token | 200 | 200 | 200 | 200 | 200 |
| Invalid/expired JWT | 401 | 401 | 401 | 401 | 200 |

### Security properties verified

- **bcrypt 12 rounds** — all hashes in DB confirmed starting with `$2b$12$`
- **No password_hash leak** — `/auth/me`, `/auth/users`, and login responses never include `password_hash`
- **JWT contains role claim** — downstream `require_admin` dependency checks `role == "admin"`
- **JWT expiry** — 24h lifetime, `exp` field validated in the future
- **Username = email fallback** — login accepts either as the identifier
- **Guest flow untouched** — `/chat`, `/rooms`, `/health`, `GET /settings/llm` remain public
- **Admin-only admin creation** — users cannot self-promote; `/auth/admin/register` requires existing admin JWT
- **last_login timestamp** — updated on every successful login (confirmed in DB)

### Database state (after tests)

```
 user_id |   username   |      role      | is_active | hash_prefix | last_login
---------+--------------+----------------+-----------+-------------+---------------------
       1 | admin        | admin          | t         | $2b$12$     | 2026-04-05 12:37:26
       2 | testuser_*   | user           | t         | $2b$12$     | 2026-04-05 12:37:27
       3 | admin2_*     | admin          | t         | $2b$12$     | 2026-04-05 12:37:28
```

## New Endpoints Added

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | public | Register as `user` role |
| POST | `/auth/login` | public | Login (username OR email), returns JWT |
| GET | `/auth/me` | bearer | Current user profile |
| POST | `/auth/admin/register` | admin | Create new admin account |
| GET | `/auth/users` | admin | List all users (filter by role) |

## Protected Endpoints (require admin JWT)

**Admin (11):** `PUT /admin/rooms/{id}/status`, `PUT /admin/bookings/{id}/status`, `POST /admin/chat/override`, `POST /admin/sessions/{id}/takeover`, `POST /admin/sessions/{id}/release`, `GET /admin/sessions`, `GET /admin/sessions/{id}/messages`, `GET /admin/escalations`, `GET /admin/sessions/{id}/states`, `POST /admin/sessions/{id}/rollback`, `POST /admin/sessions/{id}/replay`

**Dashboard (5):** `GET /dashboard/stats`, `GET /dashboard/bookings/recent`, `GET /dashboard/sessions`, `GET /dashboard/rooms`, `GET /dashboard/revenue`

**Settings (1):** `PUT /settings/llm` (runtime model switching)

## Production Hardening Checklist

- [ ] Change `JWT_SECRET` to a long random value (not the dev default)
- [ ] Change `DEFAULT_ADMIN_PASSWORD` before first deployment
- [ ] Add rate limiting to `/auth/login` (currently unlimited — brute-force risk)
- [ ] Consider adding `/auth/logout` with token blocklist or short-lived access + refresh tokens
- [ ] Add password change endpoint (`PATCH /auth/me/password`)
- [ ] Add account lockout after N failed login attempts
- [ ] Require HTTPS in production (JWTs over HTTP can be stolen)
