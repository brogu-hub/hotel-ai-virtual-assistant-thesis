# SPDX-License-Identifier: Apache-2.0
"""
Comprehensive authentication test suite for Hotel AI API.

Tests (27 total):
  A. Default admin seed + login
  B. User registration (success + duplicate + validation)
  C. User login (success + wrong password + nonexistent)
  D. /auth/me (with/without/bad token)
  E. Admin-only endpoints: unauth → 401, user → 403, admin → 200
  F. Dashboard endpoints protection (5 endpoints)
  G. Admin-only admin creation
  H. Admin user listing
  I. Guest endpoints remain public (no token required)
  J. Token structure validation

Usage:
    python scripts/test_auth.py
"""
import sys
import json
import time
import uuid
from typing import Optional

import requests

# Windows UTF-8 for Thai output
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_URL = "http://localhost:8088"

# Default admin from .env seed
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Generate unique test user to avoid collisions on repeated runs
_suffix = uuid.uuid4().hex[:8]
TEST_USER = {
    "username": f"testuser_{_suffix}",
    "email": f"test_{_suffix}@example.com",
    "password": "TestPass123!",
    "full_name": "Test User",
}
TEST_ADMIN2 = {
    "username": f"admin2_{_suffix}",
    "email": f"admin2_{_suffix}@example.com",
    "password": "AdminPass456!",
    "full_name": "Second Admin",
}

# Color output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

results: list[tuple[str, bool, str]] = []


def log_test(name: str, passed: bool, detail: str = "") -> None:
    mark = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  [{mark}] {name}" + (f" — {detail}" if detail else ""))
    results.append((name, passed, detail))


def section(title: str) -> None:
    print(f"\n{BOLD}{CYAN}=== {title} ==={RESET}")


def assert_status(resp: requests.Response, expected: int, name: str) -> bool:
    passed = resp.status_code == expected
    detail = f"got {resp.status_code}"
    if not passed:
        try:
            detail += f" body={resp.json()}"
        except Exception:
            detail += f" body={resp.text[:200]}"
    log_test(name, passed, detail)
    return passed


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# =============================================================================
# Part A: Default admin login
# =============================================================================
section("A. Default admin login")

r = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    timeout=10,
)
assert_status(r, 200, "A1. Default admin login succeeds")

admin_token: Optional[str] = None
if r.status_code == 200:
    body = r.json()
    admin_token = body.get("access_token")
    log_test("A2. Response has access_token", bool(admin_token))
    log_test("A3. Response has token_type=bearer", body.get("token_type") == "bearer")
    log_test("A4. Response has expires_in > 0", body.get("expires_in", 0) > 0)
    user = body.get("user", {})
    log_test(
        "A5. User role is 'admin'",
        user.get("role") == "admin",
        f"role={user.get('role')}",
    )
    log_test("A6. User username is 'admin'", user.get("username") == ADMIN_USERNAME)
else:
    print(f"{RED}FATAL: cannot login as default admin. Subsequent tests will fail.{RESET}")
    sys.exit(1)

# =============================================================================
# Part B: User registration
# =============================================================================
section("B. User registration")

r = requests.post(f"{BASE_URL}/auth/register", json=TEST_USER, timeout=10)
assert_status(r, 200, "B1. New user registers successfully")

user_token: Optional[str] = None
if r.status_code == 200:
    body = r.json()
    user_token = body.get("access_token")
    log_test("B2. Registered user gets JWT", bool(user_token))
    log_test(
        "B3. Registered user role is 'user' (not admin)",
        body.get("user", {}).get("role") == "user",
    )

# Duplicate username
r = requests.post(f"{BASE_URL}/auth/register", json=TEST_USER, timeout=10)
assert_status(r, 400, "B4. Duplicate username rejected (400)")

# Short password
r = requests.post(
    f"{BASE_URL}/auth/register",
    json={
        "username": f"short_{_suffix}",
        "email": f"short_{_suffix}@example.com",
        "password": "short",
    },
    timeout=10,
)
assert_status(r, 422, "B5. Short password rejected (422)")

# Invalid username (special chars)
r = requests.post(
    f"{BASE_URL}/auth/register",
    json={
        "username": "bad user!",
        "email": f"bad_{_suffix}@example.com",
        "password": "GoodPass123",
    },
    timeout=10,
)
assert_status(r, 422, "B6. Invalid username pattern rejected (422)")

# =============================================================================
# Part C: User login
# =============================================================================
section("C. User login")

# Correct credentials
r = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": TEST_USER["username"], "password": TEST_USER["password"]},
    timeout=10,
)
assert_status(r, 200, "C1. Login with correct credentials")
if r.status_code == 200:
    # Refresh the user token with the login response
    user_token = r.json().get("access_token")
    log_test("C2. Login returns same username", r.json().get("user", {}).get("username") == TEST_USER["username"])

# Login with email instead of username
r = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": TEST_USER["email"], "password": TEST_USER["password"]},
    timeout=10,
)
assert_status(r, 200, "C3. Login with email (instead of username) works")

# Wrong password
r = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": TEST_USER["username"], "password": "WrongPassword"},
    timeout=10,
)
assert_status(r, 401, "C4. Wrong password rejected (401)")

# Nonexistent user
r = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": "nonexistent_user_xyz", "password": "whatever"},
    timeout=10,
)
assert_status(r, 401, "C5. Nonexistent user rejected (401)")

# =============================================================================
# Part D: /auth/me
# =============================================================================
section("D. /auth/me endpoint")

# Without token
r = requests.get(f"{BASE_URL}/auth/me", timeout=10)
assert_status(r, 401, "D1. /auth/me without token → 401")

# With valid user token
r = requests.get(f"{BASE_URL}/auth/me", headers=auth_header(user_token), timeout=10)
assert_status(r, 200, "D2. /auth/me with valid user token → 200")
if r.status_code == 200:
    log_test(
        "D3. /auth/me returns correct username",
        r.json().get("username") == TEST_USER["username"],
    )
    log_test(
        "D4. /auth/me does NOT expose password_hash",
        "password_hash" not in r.json(),
    )

# With admin token
r = requests.get(f"{BASE_URL}/auth/me", headers=auth_header(admin_token), timeout=10)
assert_status(r, 200, "D5. /auth/me with admin token → 200")
if r.status_code == 200:
    log_test("D6. Admin /auth/me returns role='admin'", r.json().get("role") == "admin")

# Invalid token
r = requests.get(
    f"{BASE_URL}/auth/me",
    headers={"Authorization": "Bearer not.a.valid.jwt.token"},
    timeout=10,
)
assert_status(r, 401, "D7. Invalid JWT → 401")

# Malformed header (no 'Bearer ')
r = requests.get(
    f"{BASE_URL}/auth/me",
    headers={"Authorization": "just-a-token"},
    timeout=10,
)
assert_status(r, 401, "D8. Malformed auth header → 401")

# =============================================================================
# Part E: Admin-only endpoints (access control)
# =============================================================================
section("E. Admin endpoint access control")

admin_endpoints = [
    ("GET", "/admin/sessions", None),
    ("GET", "/admin/escalations", None),
]

for method, path, payload in admin_endpoints:
    # No auth
    r = requests.request(method, f"{BASE_URL}{path}", json=payload, timeout=10)
    assert_status(r, 401, f"E. {method} {path} without token → 401")

    # User token (should be forbidden)
    r = requests.request(
        method, f"{BASE_URL}{path}",
        headers=auth_header(user_token),
        json=payload, timeout=10,
    )
    assert_status(r, 403, f"E. {method} {path} with user token → 403")

    # Admin token (should succeed)
    r = requests.request(
        method, f"{BASE_URL}{path}",
        headers=auth_header(admin_token),
        json=payload, timeout=10,
    )
    assert_status(r, 200, f"E. {method} {path} with admin token → 200")

# =============================================================================
# Part F: Dashboard endpoint protection
# =============================================================================
section("F. Dashboard endpoint protection")

dashboard_endpoints = [
    "/dashboard/stats",
    "/dashboard/sessions",
    "/dashboard/rooms",
    "/dashboard/revenue",
    "/dashboard/bookings/recent",
]

for path in dashboard_endpoints:
    # No auth → 401
    r = requests.get(f"{BASE_URL}{path}", timeout=10)
    assert_status(r, 401, f"F. GET {path} without token → 401")

    # User token → 403
    r = requests.get(
        f"{BASE_URL}{path}",
        headers=auth_header(user_token),
        timeout=10,
    )
    assert_status(r, 403, f"F. GET {path} with user token → 403")

    # Admin token → 200
    r = requests.get(
        f"{BASE_URL}{path}",
        headers=auth_header(admin_token),
        timeout=10,
    )
    assert_status(r, 200, f"F. GET {path} with admin token → 200")

# =============================================================================
# Part G: Admin-only admin creation
# =============================================================================
section("G. Admin-only admin creation")

# User cannot create admin
r = requests.post(
    f"{BASE_URL}/auth/admin/register",
    headers=auth_header(user_token),
    json=TEST_ADMIN2,
    timeout=10,
)
assert_status(r, 403, "G1. User cannot create admin (403)")

# No token cannot create admin
r = requests.post(f"{BASE_URL}/auth/admin/register", json=TEST_ADMIN2, timeout=10)
assert_status(r, 401, "G2. Unauthenticated cannot create admin (401)")

# Admin can create admin
r = requests.post(
    f"{BASE_URL}/auth/admin/register",
    headers=auth_header(admin_token),
    json=TEST_ADMIN2,
    timeout=10,
)
assert_status(r, 200, "G3. Admin can create new admin")
if r.status_code == 200:
    log_test("G4. New admin has role='admin'", r.json().get("role") == "admin")

# The new admin can login
r = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": TEST_ADMIN2["username"], "password": TEST_ADMIN2["password"]},
    timeout=10,
)
assert_status(r, 200, "G5. Newly created admin can login")
if r.status_code == 200:
    log_test(
        "G6. New admin has admin role in token",
        r.json().get("user", {}).get("role") == "admin",
    )

# =============================================================================
# Part H: User listing
# =============================================================================
section("H. User listing (admin only)")

r = requests.get(
    f"{BASE_URL}/auth/users",
    headers=auth_header(admin_token),
    timeout=10,
)
assert_status(r, 200, "H1. Admin can list users")
if r.status_code == 200:
    body = r.json()
    log_test("H2. Response has 'users' list", "users" in body)
    log_test("H3. At least 3 users exist", body.get("count", 0) >= 3)
    # Check password_hash not leaked
    users = body.get("users", [])
    no_hash_leaked = all("password_hash" not in u for u in users)
    log_test("H4. Password hashes NOT exposed in list", no_hash_leaked)

# Filter by role
r = requests.get(
    f"{BASE_URL}/auth/users?role=admin",
    headers=auth_header(admin_token),
    timeout=10,
)
assert_status(r, 200, "H5. Filter users by role=admin")
if r.status_code == 200:
    all_admin = all(u.get("role") == "admin" for u in r.json().get("users", []))
    log_test("H6. All returned users are admin", all_admin)

# User cannot list users
r = requests.get(
    f"{BASE_URL}/auth/users",
    headers=auth_header(user_token),
    timeout=10,
)
assert_status(r, 403, "H7. User cannot list users (403)")

# =============================================================================
# Part I: Public endpoints remain open
# =============================================================================
section("I. Guest endpoints still public (no auth required)")

# /chat should NOT require auth (guest flow). We don't care about LLM latency
# — we only care that the endpoint doesn't reject with 401/403. Use a short
# timeout and treat a timeout as "reachable without auth" (since auth errors
# return immediately).
try:
    r = requests.post(
        f"{BASE_URL}/chat",
        json={"message": "hi", "session_id": f"test-{_suffix}"},
        timeout=5,  # short — only care about fast-fail auth rejections
    )
    log_test(
        f"I1. POST /chat without auth → {r.status_code}",
        r.status_code not in (401, 403),
        "guest chat should not require auth",
    )
except requests.exceptions.ReadTimeout:
    # Timeout means the server accepted the request and is running the LLM.
    # Auth rejection would return instantly (<100ms).
    log_test(
        "I1. POST /chat without auth → reachable (LLM processing)",
        True,
        "no 401/403 — request was accepted without token",
    )

# /rooms is open for browsing
r = requests.get(f"{BASE_URL}/rooms", timeout=10)
assert_status(r, 200, "I2. GET /rooms (room catalog) public")

# /health is open
r = requests.get(f"{BASE_URL}/health", timeout=10)
assert_status(r, 200, "I3. GET /health public")

# /settings/llm GET is open (read-only)
r = requests.get(f"{BASE_URL}/settings/llm", timeout=10)
assert_status(r, 200, "I4. GET /settings/llm public (read-only)")

# /settings/llm PUT requires admin
r = requests.put(
    f"{BASE_URL}/settings/llm",
    headers=auth_header(user_token),
    json={"temperature": 0.5},
    timeout=10,
)
assert_status(r, 403, "I5. PUT /settings/llm with user token → 403")

r = requests.put(
    f"{BASE_URL}/settings/llm",
    json={"temperature": 0.5},
    timeout=10,
)
assert_status(r, 401, "I6. PUT /settings/llm without token → 401")

# =============================================================================
# Part J: JWT payload validation
# =============================================================================
section("J. JWT payload validation")

# Decode JWT payload manually (no verification — just check structure)
import base64

def decode_jwt_payload(token: str) -> dict:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    payload = parts[1]
    # Add padding
    payload += "=" * (-len(payload) % 4)
    decoded = base64.urlsafe_b64decode(payload)
    return json.loads(decoded)

try:
    payload = decode_jwt_payload(admin_token)
    log_test("J1. JWT has 'sub' claim", "sub" in payload)
    log_test("J2. JWT has 'role' claim", "role" in payload)
    log_test("J3. JWT has 'exp' claim", "exp" in payload)
    log_test("J4. JWT has 'iat' claim", "iat" in payload)
    log_test("J5. JWT 'sub' == admin username", payload.get("sub") == ADMIN_USERNAME)
    log_test("J6. JWT 'role' == 'admin'", payload.get("role") == "admin")
    log_test(
        "J7. JWT expiry is in the future (~24h)",
        payload.get("exp", 0) > time.time() + 3600,  # at least 1h future
    )
except Exception as e:
    log_test("J. JWT decode error", False, str(e))

# =============================================================================
# Summary
# =============================================================================
print(f"\n{BOLD}{'=' * 60}{RESET}")
total = len(results)
passed = sum(1 for _, p, _ in results if p)
failed = total - passed
color = GREEN if failed == 0 else (YELLOW if failed < 3 else RED)
print(f"{BOLD}Auth Test Summary: {color}{passed}/{total} passed{RESET}")

if failed > 0:
    print(f"\n{RED}Failed tests:{RESET}")
    for name, p, detail in results:
        if not p:
            print(f"  - {name}: {detail}")

sys.exit(0 if failed == 0 else 1)
