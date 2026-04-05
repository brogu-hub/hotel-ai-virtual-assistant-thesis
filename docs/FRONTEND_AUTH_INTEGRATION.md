# Frontend Auth Integration Guide

Backend now has JWT-based authentication separating **registered users** (website accounts) from **hotel admins** (staff dashboard). Guest chat flow is unchanged — no login required.

## TL;DR

- **7 auth endpoints:** `/auth/register`, `/auth/login`, `/auth/me`, `/auth/logout`, `/auth/me/password`, `/auth/admin/register`, `/auth/users`
- **Default admin:** `admin` / `admin123` (change in prod via `DEFAULT_ADMIN_PASSWORD` env var)
- **All `/admin/*`, `/dashboard/*`, and `PUT /settings/llm` require an admin JWT** — 401 without token, 403 with user token
- **Guest endpoints stay open:** `/chat`, `/chat/stream`, `/rooms`, `/bookings`, `/guests`, `/health`, `GET /settings/llm`
- **Hardening built in:** rate limiting, account lockout, token blocklist, password-change invalidation
- OpenAPI spec: [docs/api_references/openapi.json](api_references/openapi.json) — 49 endpoints, `HTTPBearer` security scheme

## Auth endpoints

### `POST /auth/register` (public)
Register a new website user (role always `user`, never `admin`).

```jsonc
// request
{
  "username": "john_doe",        // 3-64 chars, [a-zA-Z0-9_.-]
  "email": "john@example.com",
  "password": "MinEightChars",   // ≥ 8 chars
  "full_name": "John Doe"        // optional
}

// 200 response
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 86400,
  "user": {
    "user_id": 7,
    "username": "john_doe",
    "email": "john@example.com",
    "role": "user",
    "full_name": "John Doe",
    "is_active": true,
    "guest_id": null,
    "last_login": null,
    "created_at": "2026-04-05T12:30:48"
  }
}
```

### `POST /auth/login` (public)
Login with **username OR email** + password. Works for both `user` and `admin` roles.

```jsonc
// request
{ "username": "admin", "password": "admin123" }
// or
{ "username": "admin@grandhorizon.hotel", "password": "admin123" }

// 200 response — same shape as /auth/register
// 401 on wrong password or unknown user
```

### `GET /auth/me` (requires bearer token)
Returns the current authenticated user. Use this for rehydrating session on page load.

```http
GET /auth/me
Authorization: Bearer eyJhbGciOiJIUzI1NiIs...
```

```jsonc
// 200 — UserResponse (no password_hash)
// 401 if token missing / invalid / expired
// 403 if account disabled
```

### `POST /auth/logout` (requires bearer token)
Revokes the current JWT by adding its `jti` to an in-memory blocklist. Subsequent requests with the same token return 401.

```http
POST /auth/logout
Authorization: Bearer <token>
```

```jsonc
// 200
{ "success": true, "message": "Logged out successfully / ออกจากระบบสำเร็จ" }
// 401 if token already revoked or invalid
```

**Gotcha:** The blocklist is **in-memory** (reset on server restart). For a "force logout everywhere" effect that persists across restarts, use `PATCH /auth/me/password` instead — the `password_changed_at` check invalidates all tokens persistently.

### `PATCH /auth/me/password` (requires bearer token)
Change the current user's password. Requires current password for verification. On success, **all previously-issued tokens for this user become invalid** — the user must log in again.

```jsonc
// request
{ "current_password": "OldPass123", "new_password": "NewPass456" }

// 200
{ "success": true, "message": "Password changed successfully. Please log in again." }
// 400 if new == current
// 401 if current_password is wrong
// 422 if new_password < 8 chars
```

**Frontend action on success:**
1. Show success toast
2. Clear stored token (localStorage / cookie)
3. Redirect to `/login`

### `POST /auth/admin/register` (admin only)
Used inside the admin dashboard to provision additional staff accounts. Non-admin tokens → 403.

### `GET /auth/users?role=admin&limit=100` (admin only)
List users for the admin UI. Filter by role.

## Rate limiting and lockout handling

Login is protected by three layers. Your UI must handle each:

| Status | Meaning | What to show | Action |
|---|---|---|---|
| **429** | Per-IP or per-username rate limit (too many attempts in 60s) | "Too many login attempts. Please wait N seconds." | Disable submit button for `Retry-After` seconds |
| **423** | Account locked after 5 failed attempts (15 min) | "Account temporarily locked. Try again in N minutes." | Disable submit, show countdown |
| **401** | Wrong username/password | "Invalid credentials" | Allow retry |

All three responses include a `Retry-After` header (integer seconds):

```typescript
async function handleLogin(username: string, password: string) {
  const res = await fetch('/api/hotel/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });

  if (res.status === 429 || res.status === 423) {
    const retryAfter = parseInt(res.headers.get('Retry-After') ?? '60');
    const isLocked = res.status === 423;
    const message = isLocked
      ? `Account locked. Try again in ${retryAfter}s.`
      : `Too many attempts. Try again in ${retryAfter}s.`;
    showToast(message, 'error');
    disableLoginFormFor(retryAfter);
    return;
  }

  if (res.status === 401) {
    showToast('Invalid username or password', 'error');
    return;
  }

  if (res.ok) {
    const { access_token, user } = await res.json();
    localStorage.setItem('auth_token', access_token);
    router.push(user.role === 'admin' ? '/dashboard' : '/account');
  }
}
```

## How to integrate

### 1. On login success

Store the JWT. **Recommended: httpOnly cookie** set by your Next.js backend proxy (server-to-server call to `/auth/login`, then set the cookie). Alternatives:

| Storage | XSS risk | CSRF risk | Notes |
|---|---|---|---|
| httpOnly cookie | ✅ safe | ⚠️ use SameSite=Strict | best for Next.js proxy |
| localStorage | ❌ exposed | ✅ safe | simplest; ok for demo |
| in-memory | ✅ safe | ✅ safe | lost on refresh; pair with refresh flow |

For this project (demo/thesis), **localStorage is fine**. In production swap to httpOnly cookies.

### 2. Attach the token to every admin/dashboard request

```typescript
// lib/api.ts
const token = localStorage.getItem('auth_token');
const headers: HeadersInit = token
  ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }
  : { 'Content-Type': 'application/json' };

const res = await fetch('/api/hotel/dashboard/stats', { headers });
if (res.status === 401) {
  // token expired — redirect to login
  localStorage.removeItem('auth_token');
  router.push('/login');
}
if (res.status === 403) {
  // logged in but not an admin — show "access denied"
}
```

### 3. Role-based UI rendering

Decode the JWT client-side to get `role` for rendering, but **never trust it for access control** — the backend is the source of truth.

```typescript
import { jwtDecode } from 'jwt-decode';

type JwtPayload = { sub: string; role: 'user' | 'admin'; user_id: number; exp: number };

const payload = jwtDecode<JwtPayload>(token);
const isAdmin = payload.role === 'admin';

// hide admin nav items from regular users
{isAdmin && <Link href="/dashboard">Admin Dashboard</Link>}
```

### 4. Guest chat — no changes

`/chat` and `/chat/stream` still work without any token. Keep the existing guest chat flow as-is. The login UI is only needed for (a) registered users who want booking history, and (b) hotel staff accessing the admin dashboard.

### 5. Login page

```
/login
  |
  +-- Tab 1: "Guest Login" -> POST /auth/login
  |     -> on success, redirect to /account (booking history)
  |
  +-- Tab 2: "Staff Login"  -> POST /auth/login
        -> on success, check role === 'admin'
        -> redirect to /dashboard
```

Same endpoint, same request — the returned `user.role` tells you where to redirect.

### 6. Registration page

- Public signup only creates `user` accounts (by backend design — you cannot pass `role: admin`)
- Admin provisioning happens inside the dashboard via `POST /auth/admin/register`

## Error handling reference

| Status | Meaning | UX |
|---|---|---|
| 400 | Duplicate username/email | "Username already taken" |
| 401 | Missing / invalid / expired JWT | Redirect to /login |
| 403 | Token valid but insufficient role | "Access denied — admin only" |
| 422 | Validation (short password, bad username chars) | Inline field error |

## OpenAPI / Swagger

Swagger UI is at `http://localhost:8088/docs`. The "Authorize" button now accepts a Bearer token — paste your JWT and all protected endpoints become callable from the UI.

Security scheme in the spec:
```json
{
  "securitySchemes": {
    "HTTPBearer": { "type": "http", "scheme": "bearer" }
  }
}
```

If you auto-generate a TypeScript client from the spec (e.g. with `openapi-typescript-codegen`), the bearer auth will be wired in automatically.

## Testing credentials (local dev)

```
Admin:  username=admin         password=admin123
User:   (create via /auth/register)
```

Rotate the admin password before any deployment:
```bash
# in .env
DEFAULT_ADMIN_PASSWORD=<strong-random-password>
JWT_SECRET=<64-char-random-string>
```

## Questions?

- Full test suite: [scripts/test_auth.py](../scripts/test_auth.py) (72/72 passing)
- Backend implementation: [src/hotel_guardrails/auth.py](../src/hotel_guardrails/auth.py)
- Test results: [docs/AUTH_TEST_RESULTS.md](AUTH_TEST_RESULTS.md)
