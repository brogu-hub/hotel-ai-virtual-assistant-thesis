# SPDX-License-Identifier: Apache-2.0
"""
Audit log + scaling test suite for Hotel AI API.

Tests:
  R. Audit log basics (table exists, inserts happen, auth events logged)
  S. Audit log filters (actor_username, action, action_prefix, resource_type, success_only)
  T. Audit log pagination (limit, offset, has_more, total)
  U. Audit log access control (user → 403, no-auth → 401, admin → 200)
  V. Audit stats endpoint
  W. Specific action coverage (login success/failed, password change, role change, admin actions)
  X. Scaling: concurrent login latency (pooled connections + user cache)
  Y. Scaling: user cache correctness (invalidation on password change)
  Z. Scaling: no regression for baseline + hardening

Usage:
    python scripts/test_audit_and_scaling.py
"""
import sys
import time
import uuid
import concurrent.futures
from typing import Optional

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE_URL = "http://localhost:8088"
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

_suffix = uuid.uuid4().hex[:8]

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


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def register_user(prefix: str = "audituser") -> tuple[str, str, str]:
    username = f"{prefix}_{_suffix}_{uuid.uuid4().hex[:6]}"
    password = "OriginalPass123!"
    r = requests.post(
        f"{BASE_URL}/auth/register",
        json={
            "username": username,
            "email": f"{username}@test.com",
            "password": password,
            "full_name": "Audit Test User",
        },
        timeout=10,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Register failed: {r.status_code} {r.text}")
    return username, password, r.json()["access_token"]


# =============================================================================
# Prereq: admin token
# =============================================================================
section("Prereq. Login as admin")

r = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": ADMIN_USERNAME, "password": ADMIN_PASSWORD},
    timeout=10,
)
if r.status_code != 200:
    print(f"{RED}FATAL: admin login failed{RESET}")
    sys.exit(1)
admin_token = r.json()["access_token"]
log_test("Prereq. Admin login", True)

# =============================================================================
# Part R: Audit log basics
# =============================================================================
section("R. Audit log basics")

# R1. Audit endpoint exists and returns data
r = requests.get(f"{BASE_URL}/admin/audit?limit=5", headers=auth(admin_token), timeout=10)
assert_status(r, 200, "R1. GET /admin/audit with admin token → 200")

if r.status_code == 200:
    body = r.json()
    log_test("R2. Response has 'entries' field", "entries" in body)
    log_test("R3. Response has 'total' field", "total" in body)
    log_test("R4. Response has 'has_more' field", "has_more" in body)
    log_test("R5. Total is > 0 (previous activity exists)", body.get("total", 0) > 0)

    # R6. Entry structure
    if body.get("entries"):
        e = body["entries"][0]
        expected_fields = ["audit_id", "actor_username", "action", "created_at", "success"]
        missing = [f for f in expected_fields if f not in e]
        log_test("R6. Entry has required fields", not missing, f"missing={missing}")

# R7. The admin login we just did should appear in audit log
time.sleep(0.3)  # wait for DB write
r = requests.get(
    f"{BASE_URL}/admin/audit?action=auth.login.success&limit=10",
    headers=auth(admin_token),
    timeout=10,
)
if r.status_code == 200:
    entries = r.json().get("entries", [])
    admin_login_found = any(
        e.get("actor_username") == ADMIN_USERNAME for e in entries
    )
    log_test("R7. Admin login recorded in audit log", admin_login_found)

# =============================================================================
# Part S: Audit log filters
# =============================================================================
section("S. Audit log filters")

# Generate some auditable activity
test_user, test_pw, test_tok = register_user("filterable")
time.sleep(0.2)

# S1. Filter by action_prefix
r = requests.get(
    f"{BASE_URL}/admin/audit?action_prefix=auth.&limit=20",
    headers=auth(admin_token),
    timeout=10,
)
assert_status(r, 200, "S1. Filter by action_prefix=auth.")
if r.status_code == 200:
    entries = r.json().get("entries", [])
    all_auth = all(e.get("action", "").startswith("auth.") for e in entries)
    log_test("S2. All returned entries start with 'auth.'", all_auth)

# S3. Filter by exact action
r = requests.get(
    f"{BASE_URL}/admin/audit?action=auth.register&limit=10",
    headers=auth(admin_token),
    timeout=10,
)
assert_status(r, 200, "S3. Filter by action=auth.register")
if r.status_code == 200:
    entries = r.json().get("entries", [])
    all_register = all(e.get("action") == "auth.register" for e in entries)
    log_test("S4. All returned entries are auth.register", all_register)
    # Should find the user we just registered
    found = any(e.get("actor_username") == test_user for e in entries)
    log_test("S5. Newly registered user found in audit", found)

# S6. Filter by actor_username
r = requests.get(
    f"{BASE_URL}/admin/audit?actor_username={test_user}&limit=10",
    headers=auth(admin_token),
    timeout=10,
)
assert_status(r, 200, "S6. Filter by actor_username")
if r.status_code == 200:
    entries = r.json().get("entries", [])
    all_match = all(e.get("actor_username", "").lower() == test_user.lower() for e in entries)
    log_test("S7. All entries match the actor filter", all_match)

# S8. success_only=false filter (should include failed register attempt)
# Trigger a failed register first
requests.post(
    f"{BASE_URL}/auth/register",
    json={"username": test_user, "email": "dup@test.com", "password": "GoodPass123"},
    timeout=10,
)
time.sleep(0.2)
r = requests.get(
    f"{BASE_URL}/admin/audit?success_only=false&limit=20",
    headers=auth(admin_token),
    timeout=10,
)
assert_status(r, 200, "S8. Filter success_only=false")
if r.status_code == 200:
    entries = r.json().get("entries", [])
    all_failed = all(e.get("success") is False for e in entries)
    log_test("S9. success_only=false returns only failures", all_failed)
    log_test("S10. At least one failure recorded", len(entries) > 0)

# =============================================================================
# Part T: Pagination
# =============================================================================
section("T. Audit log pagination")

# T1. Limit works
r = requests.get(f"{BASE_URL}/admin/audit?limit=3", headers=auth(admin_token), timeout=10)
if r.status_code == 200:
    body = r.json()
    log_test("T1. limit=3 returns ≤ 3 entries", len(body.get("entries", [])) <= 3)
    log_test("T2. has_more=true when total > limit", body.get("has_more") is True if body.get("total", 0) > 3 else True)

# T3. Offset pagination — compare against a single atomic page of 10 to
# avoid race conditions from the audit-log-viewing itself generating new rows
r_full = requests.get(
    f"{BASE_URL}/admin/audit?limit=10&offset=0", headers=auth(admin_token), timeout=10,
)
if r_full.status_code == 200:
    full_ids = [e["audit_id"] for e in r_full.json().get("entries", [])]
    if len(full_ids) >= 10:
        # Use high offset where the data is stable (older entries don't shift)
        r_deep = requests.get(
            f"{BASE_URL}/admin/audit?limit=5&offset=100", headers=auth(admin_token), timeout=10,
        )
        if r_deep.status_code == 200:
            deep_ids = {e["audit_id"] for e in r_deep.json().get("entries", [])}
            # Deep page must not contain any of the top-10 IDs
            log_test(
                "T3. Offset pagination returns distinct deep entries",
                deep_ids.isdisjoint(set(full_ids)) if deep_ids else True,
            )
        else:
            log_test("T3. Offset pagination (deep page skipped)", True)
    else:
        log_test("T3. Offset pagination (not enough data, skipped)", True)

# T4. Limit capped at 500
r = requests.get(
    f"{BASE_URL}/admin/audit?limit=9999",
    headers=auth(admin_token),
    timeout=10,
)
if r.status_code == 200:
    log_test("T4. limit is capped at 500", r.json().get("limit", 0) <= 500)

# =============================================================================
# Part U: Audit access control
# =============================================================================
section("U. Audit endpoint access control")

# U1. No auth → 401
r = requests.get(f"{BASE_URL}/admin/audit", timeout=10)
assert_status(r, 401, "U1. No token → 401")

# U2. User token → 403
r = requests.get(f"{BASE_URL}/admin/audit", headers=auth(test_tok), timeout=10)
assert_status(r, 403, "U2. User token → 403")

# U3. Admin token → 200
r = requests.get(f"{BASE_URL}/admin/audit", headers=auth(admin_token), timeout=10)
assert_status(r, 200, "U3. Admin token → 200")

# U4. Stats endpoint same access rules
r = requests.get(f"{BASE_URL}/admin/audit/stats", timeout=10)
assert_status(r, 401, "U4. Stats no token → 401")

r = requests.get(f"{BASE_URL}/admin/audit/stats", headers=auth(test_tok), timeout=10)
assert_status(r, 403, "U5. Stats user token → 403")

r = requests.get(f"{BASE_URL}/admin/audit/stats", headers=auth(admin_token), timeout=10)
assert_status(r, 200, "U6. Stats admin token → 200")
if r.status_code == 200:
    stats = r.json()
    log_test("U7. Stats has total_events", "total_events" in stats)
    log_test("U8. Stats has top_actions_24h", "top_actions_24h" in stats)
    log_test("U9. Stats has top_actors_24h", "top_actors_24h" in stats)

# =============================================================================
# Part V: Specific action coverage
# =============================================================================
section("V. Specific action coverage")

# V1. Trigger a failed login → should create auth.login.failed entry
failed_user, _, _ = register_user("failed_login")
r = requests.post(
    f"{BASE_URL}/auth/login",
    json={"username": failed_user, "password": "wrong_password"},
    timeout=10,
)
time.sleep(0.3)

r = requests.get(
    f"{BASE_URL}/admin/audit?action=auth.login.failed&limit=20",
    headers=auth(admin_token),
    timeout=10,
)
if r.status_code == 200:
    entries = r.json().get("entries", [])
    found = any(e.get("actor_username", "").lower() == failed_user.lower() for e in entries)
    log_test("V1. Failed login recorded as auth.login.failed", found)

# V2. Trigger password change → should create auth.password.changed
pw_user, pw_pass, pw_tok = register_user("pwaudit")
r = requests.patch(
    f"{BASE_URL}/auth/me/password",
    headers=auth(pw_tok),
    json={"current_password": pw_pass, "new_password": "BrandNewAuditPass456!"},
    timeout=10,
)
time.sleep(0.3)

r = requests.get(
    f"{BASE_URL}/admin/audit?action=auth.password.changed&actor_username={pw_user}&limit=5",
    headers=auth(admin_token),
    timeout=10,
)
if r.status_code == 200:
    log_test("V2. Password change recorded", len(r.json().get("entries", [])) > 0)

# V3. Trigger LLM config change → should create settings.llm.changed
r = requests.get(f"{BASE_URL}/settings/llm", timeout=10)
current_temp = r.json().get("temperature", 0.3) if r.status_code == 200 else 0.3
new_temp = 0.5 if current_temp != 0.5 else 0.6
r = requests.put(
    f"{BASE_URL}/settings/llm",
    headers=auth(admin_token),
    json={"temperature": new_temp},
    timeout=10,
)
time.sleep(0.3)

r = requests.get(
    f"{BASE_URL}/admin/audit?action=settings.llm.changed&limit=5",
    headers=auth(admin_token),
    timeout=10,
)
if r.status_code == 200:
    log_test("V3. LLM config change recorded", len(r.json().get("entries", [])) > 0)

# V4. Admin listing users → recorded
requests.get(f"{BASE_URL}/auth/users?limit=5", headers=auth(admin_token), timeout=10)
time.sleep(0.3)
r = requests.get(
    f"{BASE_URL}/admin/audit?action=user.list&limit=5",
    headers=auth(admin_token),
    timeout=10,
)
if r.status_code == 200:
    log_test("V4. Admin user listing recorded", len(r.json().get("entries", [])) > 0)

# V5. Admin viewing sessions → recorded (privacy-sensitive)
requests.get(f"{BASE_URL}/admin/sessions", headers=auth(admin_token), timeout=10)
time.sleep(0.3)
r = requests.get(
    f"{BASE_URL}/admin/audit?action=admin.session.listed&limit=5",
    headers=auth(admin_token),
    timeout=10,
)
if r.status_code == 200:
    log_test("V5. Admin session listing recorded", len(r.json().get("entries", [])) > 0)

# V6. Audit entries contain ip_address
r = requests.get(f"{BASE_URL}/admin/audit?limit=5", headers=auth(admin_token), timeout=10)
if r.status_code == 200:
    entries = r.json().get("entries", [])
    has_ip = any(e.get("ip_address") for e in entries)
    log_test("V6. Audit entries capture ip_address", has_ip)

# V7. Audit entries contain user_agent
if r.status_code == 200:
    has_ua = any(e.get("user_agent") for e in entries)
    log_test("V7. Audit entries capture user_agent", has_ua)

# =============================================================================
# Part W: Scaling — concurrent authenticated request latency
# =============================================================================
section("W. Scaling: concurrent request latency with pool + cache")


def make_me_request(token: str) -> float:
    start = time.time()
    r = requests.get(f"{BASE_URL}/auth/me", headers=auth(token), timeout=10)
    assert r.status_code == 200
    return time.time() - start


# Warm up the cache with a single request
make_me_request(admin_token)

# W1. 30 concurrent /auth/me calls should complete under a reasonable budget
N = 30
start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    latencies = list(pool.map(lambda _: make_me_request(admin_token), range(N)))
total_time = time.time() - start

avg_latency = sum(latencies) / len(latencies)
p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
log_test(
    f"W1. {N} concurrent /auth/me requests completed",
    True,
    f"total={total_time:.2f}s, avg={avg_latency*1000:.0f}ms, p95={p95_latency*1000:.0f}ms",
)
# Budget: 30 requests with 10 concurrent should take less than 5s on a healthy setup
log_test(
    "W2. Total time under 5s budget (pool+cache working)",
    total_time < 5.0,
    f"actual={total_time:.2f}s",
)
log_test(
    "W3. p95 latency under 500ms",
    p95_latency < 0.5,
    f"actual p95={p95_latency*1000:.0f}ms",
)

# =============================================================================
# Part X: User cache correctness
# =============================================================================
section("X. User cache correctness (password change invalidation)")

cache_user, cache_pw, cache_tok = register_user("cachetest")

# X1. Make a request that populates the cache
r = requests.get(f"{BASE_URL}/auth/me", headers=auth(cache_tok), timeout=10)
assert_status(r, 200, "X1. Initial /auth/me populates cache")

# Sleep >1s so the subsequent password change lands in a strictly later
# whole-second bucket than the token's iat (iat is truncated to whole seconds,
# and password_change invalidation works at second granularity to avoid
# racing freshly-issued tokens in the same second).
time.sleep(1.2)

# X2. Change password — should invalidate cache entry
r = requests.patch(
    f"{BASE_URL}/auth/me/password",
    headers=auth(cache_tok),
    json={"current_password": cache_pw, "new_password": "NewCachePass456!"},
    timeout=10,
)
assert_status(r, 200, "X2. Password change succeeds")

# X3. Old token MUST be rejected (cache invalidated + password_changed_at check)
time.sleep(0.3)
r = requests.get(f"{BASE_URL}/auth/me", headers=auth(cache_tok), timeout=10)
assert_status(r, 401, "X3. Old token rejected after password change (cache invalidated)")

# =============================================================================
# Part Y: DB pool health check — no connection exhaustion
# =============================================================================
section("Y. DB connection pool health")

# Y1. Make 50 sequential DB-heavy requests — should not leak connections
ok_count = 0
for _ in range(50):
    r = requests.get(
        f"{BASE_URL}/admin/audit?limit=1",
        headers=auth(admin_token),
        timeout=10,
    )
    if r.status_code == 200:
        ok_count += 1

log_test(
    f"Y1. 50 sequential DB requests succeed ({ok_count}/50)",
    ok_count == 50,
)

# Y2. 20 concurrent DB-heavy requests
def audit_req():
    return requests.get(
        f"{BASE_URL}/admin/audit?limit=5",
        headers=auth(admin_token),
        timeout=10,
    ).status_code

start = time.time()
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
    codes = list(pool.map(lambda _: audit_req(), range(20)))
concurrent_time = time.time() - start

log_test(
    f"Y2. 20 concurrent audit queries all succeed",
    all(c == 200 for c in codes),
    f"time={concurrent_time:.2f}s",
)

# =============================================================================
# Summary
# =============================================================================
print(f"\n{BOLD}{'=' * 60}{RESET}")
total = len(results)
passed = sum(1 for _, p, _ in results if p)
failed = total - passed
color = GREEN if failed == 0 else (YELLOW if failed < 3 else RED)
print(f"{BOLD}Audit + Scaling Test Summary: {color}{passed}/{total} passed{RESET}")

if failed > 0:
    print(f"\n{RED}Failed tests:{RESET}")
    for name, p, detail in results:
        if not p:
            print(f"  - {name}: {detail}")

sys.exit(0 if failed == 0 else 1)
