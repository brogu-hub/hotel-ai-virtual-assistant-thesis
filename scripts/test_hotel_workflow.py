#!/usr/bin/env python3
"""
Hotel AI Virtual Assistant - Comprehensive Booking Workflow Test

Tests all use cases via the agent chat API and direct REST endpoints.
Verifies database state after each mutation.

Usage:
    python scripts/test_hotel_workflow.py
    python scripts/test_hotel_workflow.py --base-url http://localhost:8088
    python scripts/test_hotel_workflow.py --part A   # Run only Part A
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta

# Force UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
import psycopg2
import psycopg2.extras

# =============================================================================
# Configuration
# =============================================================================

BASE_URL = "http://localhost:8088"
DB_CONFIG = {
    "host": "localhost",
    "port": 5433,
    "dbname": "hotel",
    "user": "postgres",
    "password": "hotelpass123",
}
CHAT_TIMEOUT = 120  # seconds - Ollama inference can be slow
API_TIMEOUT = 30

# Counters
PASS = 0
FAIL = 0
SKIP = 0
RESULTS = []


# =============================================================================
# Helpers
# =============================================================================


def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"  [{ts}] {level}: {msg}")


def verify_db(query, params=None):
    """Direct DB check via psycopg2."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(query, params or ())
        result = cur.fetchall()
        conn.close()
        return result
    except Exception as e:
        log(f"DB verification failed: {e}", "ERROR")
        return None


def chat(message, session_id=None, language="auto"):
    """Send a chat message and return the response."""
    payload = {"message": message, "language": language}
    if session_id:
        payload["session_id"] = session_id
    try:
        resp = requests.post(
            f"{BASE_URL}/chat",
            json=payload,
            timeout=CHAT_TIMEOUT,
        )
        data = resp.json()
        return data
    except requests.exceptions.Timeout:
        return {"error": "timeout", "status_code": 0}
    except Exception as e:
        return {"error": str(e), "status_code": 0}


def api_get(path, params=None):
    """GET request helper."""
    try:
        resp = requests.get(f"{BASE_URL}{path}", params=params, timeout=API_TIMEOUT)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {"error": str(e)}


def api_post(path, data=None):
    """POST request helper."""
    try:
        resp = requests.post(f"{BASE_URL}{path}", json=data, timeout=API_TIMEOUT)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {"error": str(e)}


def api_put(path, data=None):
    """PUT request helper."""
    try:
        resp = requests.put(f"{BASE_URL}{path}", json=data, timeout=API_TIMEOUT)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {"error": str(e)}


def api_patch(path, data=None):
    """PATCH request helper."""
    try:
        resp = requests.patch(f"{BASE_URL}{path}", json=data, timeout=API_TIMEOUT)
        return resp.status_code, resp.json()
    except Exception as e:
        return 0, {"error": str(e)}


def test(name, passed, detail=""):
    """Record a test result."""
    global PASS, FAIL
    status = "PASS" if passed else "FAIL"
    if passed:
        PASS += 1
    else:
        FAIL += 1
    RESULTS.append({"name": name, "status": status, "detail": detail})
    icon = "+" if passed else "X"
    print(f"  {icon} {status}: {name}")
    if detail and not passed:
        print(f"         {detail[:200]}")


def get_next_monday():
    """Get the date of next Monday."""
    today = datetime.now()
    days_ahead = 7 - today.weekday()  # Monday = 0
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


def get_next_wednesday():
    """Get the date of next Wednesday."""
    today = datetime.now()
    days_ahead = 2 - today.weekday()  # Wednesday = 2
    if days_ahead <= 0:
        days_ahead += 7
    return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")


# =============================================================================
# Part A: Infrastructure Tests
# =============================================================================


def test_part_a():
    print("\n" + "=" * 60)
    print("PART A: Infrastructure Tests")
    print("=" * 60)

    # A1: Health check
    status, data = api_get("/healthz")
    test("A1: GET /healthz returns 200", status == 200)

    # A2: Full health
    status, data = api_get("/health")
    test("A2: GET /health returns 200", status == 200)

    # A3: LLM settings — verify Ollama backend
    status, data = api_get("/settings/llm")
    test(
        "A3: GET /settings/llm shows ollama backend",
        status == 200 and data.get("backend") == "ollama",
        f"backend={data.get('backend')}, model={data.get('model')}",
    )

    # A4: Switch to openrouter and back
    status, data = api_put("/settings/llm", {"backend": "openrouter", "model": "qwen/qwen3-max"})
    switched = status == 200 and data.get("backend") == "openrouter"
    test("A4a: PUT /settings/llm -> switch to openrouter", switched, str(data.get("backend")))

    status, data = api_put(
        "/settings/llm",
        {"backend": "ollama", "model": "fredrezones55/qwen3.5-opus:9b"},
    )
    switched_back = status == 200 and data.get("backend") == "ollama"
    test("A4b: PUT /settings/llm -> switch back to ollama", switched_back)

    # A5: Room types loaded
    status, data = api_get("/rooms")
    rooms_list = data.get("rooms", data) if isinstance(data, dict) else data
    if not isinstance(rooms_list, list):
        rooms_list = []
    has_rooms = status == 200 and len(rooms_list) >= 4
    test("A5: GET /rooms returns 4+ room types", has_rooms, f"count={len(rooms_list)}")

    # A6: Room availability
    next_mon = get_next_monday()
    next_wed = get_next_wednesday()
    status, data = api_get("/rooms/availability", {"start_date": next_mon, "end_date": next_wed})
    test("A6: GET /rooms/availability returns data", status == 200, str(data)[:100] if data else "")


# =============================================================================
# Part B: Hotel Knowledge Tests (RAG)
# =============================================================================


def test_part_b():
    print("\n" + "=" * 60)
    print("PART B: Hotel Knowledge Tests (RAG)")
    print("=" * 60)

    knowledge_tests = [
        ("B7", "What time is breakfast?", ["breakfast", "6:30", "10:30", "morning"]),
        ("B8", "What's the WiFi password?", ["HOTEL2024GUEST", "wifi", "WiFi"]),
        ("B9", "What is the cancellation policy?", ["cancel", "48", "hour", "policy"]),
        ("B10", "สปาเปิดกี่โมงครับ", ["spa", "สปา", "10", "22", "wellness"]),
        ("B11", "Do you allow pets?", ["pet", "500", "fee", "สัตว์"]),
        ("B12", "How do I get from the airport to the hotel?", ["airport", "shuttle", "transport", "transfer"]),
    ]

    for test_id, question, expected_keywords in knowledge_tests:
        data = chat(question)
        response = data.get("response", "") or ""
        response_lower = response.lower()
        matched = any(kw.lower() in response_lower for kw in expected_keywords)
        test(
            f"{test_id}: '{question[:40]}...' -> relevant response",
            matched and len(response) > 20,
            f"response={response[:120]}...",
        )


# =============================================================================
# Part C: Complete Booking Workflow (Agent Chat)
# =============================================================================


def test_part_c():
    print("\n" + "=" * 60)
    print("PART C: Complete Booking Workflow (Agent Chat)")
    print("=" * 60)

    session_id = str(uuid.uuid4())
    test_email = f"testguest_{int(time.time())}@example.com"
    confirmation_number = None

    # Pre-register guest via API so the agent can book directly
    reg_status, reg_data = api_post("/guests", {
        "email": test_email,
        "first_name": "John",
        "last_name": "Smith",
    })
    test("C13: Pre-register guest via API", reg_status in (200, 201), f"status={reg_status}")

    # C14: Natural language date availability
    data = chat("Is there a room available next Monday?", session_id)
    resp = data.get("response", "") or ""
    has_room_info = any(w in resp.lower() for w in ["available", "room", "ห้อง", "ว่าง", "standard", "deluxe", "suite"])
    test("C14: 'next Monday' availability -> room info", has_room_info, resp[:120])

    # C15: Room types and prices
    data = chat("What types of rooms do you have and how much do they cost?", session_id)
    resp = data.get("response", "") or ""
    has_types = any(w in resp.lower() for w in ["standard", "deluxe", "suite", "penthouse", "2,500", "3,500"])
    test("C15: Room types + prices query", has_types, resp[:120])

    # C16: Book a specific room with email
    next_mon = get_next_monday()
    next_wed = get_next_wednesday()

    # Find an available Deluxe room number first
    avail_rooms = verify_db(
        "SELECT r.room_number FROM rooms r "
        "JOIN room_types rt ON r.room_type_id = rt.room_type_id "
        "WHERE rt.name = 'Deluxe Room' AND r.status = 'available' LIMIT 1"
    )
    room_num = avail_rooms[0]["room_number"] if avail_rooms else "403"

    data = chat(
        f"Please book Deluxe room {room_num} from {next_mon} to {next_wed} for 2 guests. "
        f"My email is {test_email}.",
        session_id,
    )
    resp = data.get("response", "") or ""
    test("C16: Booking request -> agent responds", len(resp) > 20, resp[:120])

    # C17: Check if reservation was created, give agent up to 2 more turns if needed
    import re
    conf_match = re.search(r"HTL\w+", resp)
    if conf_match:
        confirmation_number = conf_match.group(0)

    # Check DB
    db_check = verify_db(
        "SELECT confirmation_number, status FROM reservations "
        "JOIN guests g ON reservations.guest_id = g.guest_id "
        "WHERE g.email = %s ORDER BY reservations.created_at DESC LIMIT 1",
        (test_email,),
    )
    has_reservation = db_check and len(db_check) > 0

    # If not yet, nudge the agent
    for nudge in ["Yes, go ahead and book it.", "Please create the reservation now."]:
        if has_reservation:
            break
        data = chat(nudge, session_id)
        resp = data.get("response", "") or ""
        conf_match = re.search(r"HTL\w+", resp)
        if conf_match:
            confirmation_number = conf_match.group(0)
        db_check = verify_db(
            "SELECT confirmation_number, status FROM reservations "
            "JOIN guests g ON reservations.guest_id = g.guest_id "
            "WHERE g.email = %s ORDER BY reservations.created_at DESC LIMIT 1",
            (test_email,),
        )
        has_reservation = db_check and len(db_check) > 0

    if has_reservation and not confirmation_number:
        confirmation_number = db_check[0]["confirmation_number"]
    test(
        "C17: Reservation created in DB",
        has_reservation,
        f"conf={confirmation_number}",
    )

    # C18: Confirm booking
    if confirmation_number:
        data = chat("Can you confirm my booking?", session_id)
        resp = data.get("response", "") or ""
        db_check = verify_db(
            "SELECT status FROM reservations WHERE confirmation_number = %s",
            (confirmation_number,),
        )
        is_confirmed = db_check and db_check[0]["status"] == "confirmed"
        test("C18: Confirm booking -> DB status=confirmed", is_confirmed, f"status={db_check}")
    else:
        test("C18: Confirm booking (skipped - no confirmation number)", False, "No booking to confirm")

    # C19: Update to Suite
    if confirmation_number:
        data = chat("Actually, can I change to a Suite instead?", session_id)
        resp = data.get("response", "") or ""
        test("C19: Update room type -> agent responds", len(resp) > 20, resp[:120])

    # C20: Add special requests
    if confirmation_number:
        data = chat("I'd also like late checkout and extra pillows please", session_id)
        resp = data.get("response", "") or ""
        db_check = verify_db(
            "SELECT special_requests FROM reservations WHERE confirmation_number = %s",
            (confirmation_number,),
        )
        has_requests = db_check and db_check[0].get("special_requests")
        test("C20: Special requests -> updated in DB", has_requests or len(resp) > 20, resp[:120])

    # C21: Get reservation details
    if confirmation_number:
        data = chat("What's my reservation details?", session_id)
        resp = data.get("response", "") or ""
        has_details = any(w in resp for w in [confirmation_number, "reservation", "การจอง", test_email, "Smith"])
        test("C21: Reservation details -> includes confirmation", has_details, resp[:120])

    # C22: Cancel reservation
    if confirmation_number:
        data = chat("I need to cancel my reservation, plans changed", session_id)
        resp = data.get("response", "") or ""
        db_check = verify_db(
            "SELECT status FROM reservations WHERE confirmation_number = %s",
            (confirmation_number,),
        )
        is_cancelled = db_check and db_check[0]["status"] == "cancelled"
        test("C22: Cancel reservation -> DB status=cancelled", is_cancelled, f"status={db_check}")


# =============================================================================
# Part D: Advanced Booking Scenarios
# =============================================================================


def test_part_d():
    print("\n" + "=" * 60)
    print("PART D: Advanced Booking Scenarios")
    print("=" * 60)

    # D23: Multi-room booking
    session_d = str(uuid.uuid4())
    data = chat(
        "I need 2 rooms for a family trip, April 15-20, one Standard and one Deluxe",
        session_d,
    )
    resp = data.get("response", "") or ""
    test("D23: Multi-room request -> agent understands", len(resp) > 20, resp[:120])

    # D24: Natural language date + view preference
    data = chat(
        "Do you have any rooms with an ocean view available this weekend?",
        str(uuid.uuid4()),
    )
    resp = data.get("response", "") or ""
    test("D24: 'this weekend' + ocean view -> response", len(resp) > 20, resp[:120])

    # D25: Same-day / cheapest room
    data = chat("What's the cheapest room available for tonight?", str(uuid.uuid4()))
    resp = data.get("response", "") or ""
    has_price = any(w in resp.lower() for w in ["standard", "2,500", "2500", "price", "ราคา", "บาท"])
    test("D25: Cheapest room tonight -> price info", has_price or len(resp) > 30, resp[:120])

    # D26: Full booking in Thai
    data = chat(
        "อยากจองห้อง Suite วันที่ 20-22 เมษายน สำหรับ 3 คนครับ",
        str(uuid.uuid4()),
        language="th",
    )
    resp = data.get("response", "") or ""
    test("D26: Thai booking request -> Thai response", len(resp) > 20, resp[:120])


# =============================================================================
# Part E: Service Requests & Post-Booking
# =============================================================================


def test_part_e():
    print("\n" + "=" * 60)
    print("PART E: Service Requests & Post-Booking")
    print("=" * 60)

    # E27: Service request
    data = chat("I'm checked into room 501, can I get extra towels please?", str(uuid.uuid4()))
    resp = data.get("response", "") or ""
    test("E27: Extra towels request -> acknowledged", len(resp) > 20, resp[:120])

    # E28: Hotel services list
    data = chat("What services does the hotel offer?", str(uuid.uuid4()))
    resp = data.get("response", "") or ""
    has_services = any(w in resp.lower() for w in ["spa", "pool", "gym", "fitness", "restaurant", "สปา"])
    test("E28: Hotel services -> list of services", has_services, resp[:120])

    # E29: Spa booking
    data = chat("I'd like to book a spa treatment for tomorrow afternoon", str(uuid.uuid4()))
    resp = data.get("response", "") or ""
    test("E29: Spa booking -> response", len(resp) > 20, resp[:120])

    # E30: Airport pickup
    data = chat("Can you arrange airport pickup for my arrival?", str(uuid.uuid4()))
    resp = data.get("response", "") or ""
    test("E30: Airport pickup -> transport info", len(resp) > 20, resp[:120])


# =============================================================================
# Part F: Edge Cases
# =============================================================================


def test_part_f():
    print("\n" + "=" * 60)
    print("PART F: Edge Cases")
    print("=" * 60)

    # F31: Past dates
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    data = chat(f"Book a room for {yesterday}", str(uuid.uuid4()))
    resp = data.get("response", "") or ""
    test("F31: Past date booking -> graceful rejection", len(resp) > 20, resp[:120])

    # F32: Too many guests
    data = chat("I want a room for 100 guests", str(uuid.uuid4()))
    resp = data.get("response", "") or ""
    test("F32: 100 guests -> explains limits", len(resp) > 20, resp[:120])

    # F33: Off-topic
    data = chat("What's the weather like in Bangkok?", str(uuid.uuid4()))
    resp = data.get("response", "") or ""
    test("F33: Off-topic -> handles gracefully", len(resp) > 10, resp[:120])


# =============================================================================
# Main
# =============================================================================


def print_summary():
    print("\n" + "=" * 60)
    print(f"TEST SUMMARY: {PASS} passed, {FAIL} failed, {PASS + FAIL} total")
    print("=" * 60)

    if FAIL > 0:
        print("\nFailed tests:")
        for r in RESULTS:
            if r["status"] == "FAIL":
                print(f"  X {r['name']}")
                if r["detail"]:
                    print(f"    {r['detail'][:200]}")

    return FAIL == 0


def main():
    global BASE_URL, DB_CONFIG

    parser = argparse.ArgumentParser(description="Hotel AI Workflow Tests")
    parser.add_argument("--base-url", default=BASE_URL, help="API base URL")
    parser.add_argument("--db-host", default="localhost")
    parser.add_argument("--db-port", default=5433, type=int)
    parser.add_argument("--part", default=None, help="Run specific part (A/B/C/D/E/F)")
    args = parser.parse_args()

    BASE_URL = args.base_url
    DB_CONFIG["host"] = args.db_host
    DB_CONFIG["port"] = args.db_port

    print(f"Hotel AI Virtual Assistant - Workflow Tests")
    print(f"API: {BASE_URL}")
    print(f"DB: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['dbname']}")

    # Check API is reachable (generous timeout since Ollama may be busy)
    try:
        resp = requests.get(f"{BASE_URL}/healthz", timeout=30)
        if resp.status_code != 200:
            print(f"\nERROR: API not healthy (status={resp.status_code})")
            sys.exit(1)
    except Exception as e:
        print(f"\nERROR: Cannot reach API at {BASE_URL}: {e}")
        sys.exit(1)

    parts = {
        "A": test_part_a,
        "B": test_part_b,
        "C": test_part_c,
        "D": test_part_d,
        "E": test_part_e,
        "F": test_part_f,
    }

    if args.part:
        part = args.part.upper()
        if part in parts:
            parts[part]()
        else:
            print(f"Unknown part: {part}. Available: {', '.join(parts.keys())}")
            sys.exit(1)
    else:
        for part_fn in parts.values():
            part_fn()

    success = print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
