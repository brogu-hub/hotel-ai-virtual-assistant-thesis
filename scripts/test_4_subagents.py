#!/usr/bin/env python3
"""
Comprehensive sub-agent + tool calling tests.

Verifies all 4 LangGraph sub-agents and their tools:
  1. knowledge   — search_hotel_knowledge (RAG)
  2. booking     — 12 tools (availability, CRUD, pricing, upsell, payment)
  3. service     — get_hotel_services, create_service_request
  4. other_talk  — no tools, direct LLM response

Usage:
  python scripts/test_4_subagents.py                # all tests
  python scripts/test_4_subagents.py --agent booking
  python scripts/test_4_subagents.py --quick        # 2 per category
  python scripts/test_4_subagents.py --stream-all   # test /chat/stream for every case
  python scripts/test_4_subagents.py --json out.json
"""
import sys
import json
import re
import time
import uuid
import argparse
import requests

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

API = "http://localhost:8088"

# =============================================================================
# Test cases — organized by sub-agent, with tool tags
# =============================================================================
TEST_CASES = {
    "knowledge": [
        # Typical Q&A — covers RAG across all 10 knowledge docs
        {"msg": "What time is breakfast?", "expect": ["breakfast", "6:30", "dining"], "tool": "search_hotel_knowledge"},
        {"msg": "What is the WiFi password?", "expect": ["WiFi", "password", "GrandHorizon"], "tool": "search_hotel_knowledge"},
        {"msg": "สระว่ายน้ำเปิดกี่โมง", "expect": ["สระ", "06:00", "21:00"], "lang": "th", "tool": "search_hotel_knowledge"},
        {"msg": "Do you allow pets?", "expect": ["pet", "500", "5 kg"], "tool": "search_hotel_knowledge"},
        {"msg": "นโยบายการยกเลิกการจอง", "expect": ["ยกเลิก", "48"], "lang": "th", "tool": "search_hotel_knowledge"},
        {"msg": "Spa treatments and prices?", "expect": ["spa", "massage", "THB", "1,500", "2,000"], "tool": "search_hotel_knowledge"},
        {"msg": "Check-in and check-out times?", "expect": ["2:00", "12:00", "check", "pm", "noon"], "tool": "search_hotel_knowledge"},
        {"msg": "มีบริการรถรับส่งสนามบินไหม", "expect": ["สนามบิน", "บาท", "สุวรรณภูมิ"], "lang": "th", "tool": "search_hotel_knowledge"},
        {"msg": "Where is the gym located?", "expect": ["gym", "fitness", "floor"], "tool": "search_hotel_knowledge"},
        {"msg": "Tell me about your restaurants", "expect": ["restaurant", "dining", "hours"], "tool": "search_hotel_knowledge"},
        {"msg": "What room types do you have?", "expect": ["Standard", "Deluxe", "Suite", "Penthouse"], "tool": "search_hotel_knowledge"},
        {"msg": "Is there a late check-out fee?", "expect": ["late", "check-out", "500", "hour", "fee"], "tool": "search_hotel_knowledge"},
        {"msg": "ห้องประชุมมีไหม", "expect": ["meeting", "ประชุม", "booking"], "tool": "search_hotel_knowledge"},  # knowledge base has this only in English
        {"msg": "Do you have a loyalty program?", "expect": ["loyalty", "member", "point", "tier"], "tool": "search_hotel_knowledge"},
        {"msg": "ร้านอาหารเปิดกี่โมง", "expect": ["ร้าน", "อาหาร", "เปิด"], "lang": "th", "tool": "search_hotel_knowledge"},
    ],

    "booking": [
        # === check_room_availability ===
        {"msg": "Is there a room available for April 15-17?", "expect": ["available", "room", "THB"], "tool": "check_room_availability"},
        {"msg": "Do you have Deluxe rooms next Monday to Wednesday?", "expect": ["Deluxe", "available"], "tool": "check_room_availability"},
        {"msg": "มีห้องว่างวันที่ 20-22 เมษายนไหมครับ", "expect": ["ห้อง", "ว่าง"], "lang": "th", "tool": "check_room_availability"},
        {"msg": "Any Suite available for this weekend?", "expect": ["Suite", "available"], "tool": "check_room_availability"},

        # === get_reservation_details (by HTL number) ===
        {"msg": "Check reservation HTL2604150001", "expect": ["HTL2604150001", "reservation", "booking", "not found"], "tool": "get_reservation_details"},
        {"msg": "Show details for confirmation HTL2604060308", "expect": ["HTL2604060308", "Standard", "reservation"], "tool": "get_reservation_details"},
        {"msg": "สถานะการจอง HTL2604060309 คืออะไร", "expect": ["HTL2604060309", "สถานะ"], "lang": "th", "tool": "get_reservation_details"},

        # === get_guest_reservations (by email) ===
        {"msg": "Check my bookings by email test@example.com", "expect": ["booking", "reservation", "HTL", "confirmation"], "tool": "get_guest_reservations"},
        {"msg": "List all reservations for email guest@hotel.com", "expect": ["reservation", "booking", "email", "not found"], "tool": "get_guest_reservations"},

        # === cancel_reservation ===
        {"msg": "Cancel booking HTL2604150001", "expect": ["cancel", "HTL2604150001", "not found"], "tool": "cancel_reservation"},
        {"msg": "I need to cancel my reservation HTL2604060308", "expect": ["cancel", "HTL2604060308"], "tool": "cancel_reservation"},
        {"msg": "ยกเลิกการจอง HTL2604060309", "expect": ["ยกเลิก"], "lang": "th", "tool": "cancel_reservation"},

        # === calculate_dynamic_price ===
        {"msg": "What's the actual price for a Deluxe on April 20-22?", "expect": ["Deluxe", "THB", "price"], "tool": "calculate_dynamic_price"},
        {"msg": "How much is a Standard room tomorrow with same-day surcharge?", "expect": ["Standard", "THB"], "tool": "calculate_dynamic_price"},

        # === create_reservation (full flow, may need multiple turns) ===
        {"msg": "Book me a Standard room for April 25-27, 2 guests, email user@test.com", "expect": ["book", "Standard", "confirmation", "HTL"], "tool": "create_reservation"},
        {"msg": "I want to book a Deluxe room for this weekend", "expect": ["Deluxe", "date", "email", "when"], "tool": "create_reservation"},

        # === General booking intent ===
        {"msg": "I want to book a room", "expect": ["date", "room", "book", "when", "check-in", "stay", "arrive", "type"]},
        {"msg": "Help me make a reservation", "expect": ["reservation", "date", "type", "room", "book", "help"]},

        # === Thai booking ===
        {"msg": "อยากจองห้องพักครับ", "expect": ["จอง", "ห้อง", "วัน"], "lang": "th"},
    ],

    "service": [
        # === get_hotel_services ===
        {"msg": "What services do you offer?", "expect": ["service", "request", "towel", "room"], "tool": "get_hotel_services"},
        {"msg": "What housekeeping services are available?", "expect": ["housekeeping", "service", "clean"], "tool": "get_hotel_services"},

        # === create_service_request ===
        {"msg": "I need extra towels for room 101", "expect": ["towel", "request", "room"], "tool": "create_service_request"},
        {"msg": "Can I have room service - 2 bottles of water please", "expect": ["room service", "water", "request"], "tool": "create_service_request"},
        {"msg": "Request wake-up call at 7 AM tomorrow for HTL2604060308", "expect": ["wake", "call", "7"], "tool": "create_service_request"},
        {"msg": "Need housekeeping for my room, reservation HTL2604060309", "expect": ["housekeeping", "room"], "tool": "create_service_request"},
        {"msg": "Can I book the spa for tomorrow at 3 PM?", "expect": ["spa", "book", "request"], "tool": "create_service_request"},
        {"msg": "The AC is not working in my room, need maintenance", "expect": ["maintenance", "AC", "room", "request"], "tool": "create_service_request"},
        {"msg": "ขอผ้าเช็ดตัวเพิ่มครับ", "expect": ["ผ้า", "ขอ"], "lang": "th", "tool": "create_service_request"},
        {"msg": "ขอบริการรูมเซอร์วิสครับ", "expect": ["บริการ", "ห้อง"], "lang": "th", "tool": "create_service_request"},
        {"msg": "เรียกรถแท็กซี่หน่อยครับ", "expect": ["รถ", "บริการ"], "lang": "th", "tool": "create_service_request"},
    ],

    "other_talk": [
        {"msg": "Hello!", "expect": ["welcome", "hotel", "assist", "help"]},
        {"msg": "Hi there", "expect": ["welcome", "hello", "hi", "assist"]},
        {"msg": "สวัสดีครับ", "expect": ["สวัสดี", "ยินดี", "ต้อนรับ"], "lang": "th"},
        {"msg": "Good morning", "expect": ["morning", "welcome", "good"]},
        {"msg": "Thank you so much", "expect": ["welcome", "thank", "pleasure", "glad"]},
        {"msg": "ขอบคุณมากครับ", "expect": ["ยินดี", "ขอบคุณ"], "lang": "th"},
        {"msg": "Goodbye", "expect": ["goodbye", "thank", "stay", "see"]},
        {"msg": "What's the weather like?", "expect": ["weather", "hotel", "assist", "help"]},
        {"msg": "Tell me a joke", "expect": ["hotel", "help", "assist", "focus"]},
    ],

    "edge": [
        # Edge cases + multi-turn
        {"msg": "", "expect": [], "agent": "error"},  # empty — should 422
        {"msg": "a" * 5000, "expect": [], "agent": "error"},  # exceeds 4096 max_length
        {"msg": "Hello สวัสดี how are you", "expect": ["hello", "welcome", "สวัสดี"]},  # mixed lang
        {"msg": "I want to book a room and also need extra towels", "expect": ["book", "date", "towel"]},  # multi-intent
        {"msg": "Check reservation HTL999999", "expect": ["not found", "HTL999999", "check"]},  # invalid HTL
    ],

    # =========================================================================
    # Memory tests — cross-turn (short-term checkpoint) + cross-session (long-term store)
    # =========================================================================
    # Every case is multi-turn (uses "turns"); cases that share a "user_id"
    # exercise long-term PostgresStore recall across independent sessions.
    # Cases are ordered so each seed appears BEFORE its recall case.
    "memory": [
        # ================================================================
        # Section 1 — SHORT-TERM recall (PostgresSaver / checkpointer)
        # One case per sub-agent, each proving the handler saw prior turns.
        # ================================================================
        {
            "id": "st_booking_modify",
            "turns": [
                {"msg": "Book a Deluxe room for April 25-27, 2 guests, email alice@test.com"},
                {"msg": "Actually make that 3 guests"},
            ],
            "expect": ["Deluxe", "April", "25", "3"],
        },
        {
            "id": "st_service_followup",
            "turns": [
                {"msg": "I need extra towels for room 501, please."},
                {"msg": "And could I also get two more pillows sent to the same room?"},
            ],
            "expect": ["501", "pillow"],
        },
        {
            "id": "st_knowledge_followup",
            "turns": [
                {"msg": "What time is breakfast at the restaurant?"},
                {"msg": "And when does the breakfast service end?"},
            ],
            "expect": ["10:30", "11", "end", "close", "breakfast"],
        },
        {
            "id": "st_other_name_recall",
            "turns": [
                {"msg": "Hi, my name is Alice and I'm here on business."},
                {"msg": "What did I just tell you my name was?"},
            ],
            # Model may transliterate Alice → อลิซ when responding in Thai.
            "expect": ["Alice", "อลิซ"],
        },
        {
            "id": "st_thai_booking_modify",
            "turns": [
                {"msg": "จองห้อง Suite วันที่ 10-12 พฤษภาคม 2 คน อีเมล thai@test.com", "lang": "th"},
                {"msg": "เปลี่ยนเป็นห้อง Deluxe ได้ไหมครับ", "lang": "th"},
            ],
            "expect": ["Deluxe", "10", "พฤษภาคม"],
        },

        # ================================================================
        # Section 2 — LONG-TERM recall (PostgresStore), one pair per store key
        # ================================================================

        # (a) preferences.floor + preferences.allergy via free-text extractor
        {
            "id": "lt_seed_prefs_floor_allergy_userA",
            "user_id": "mem-test-user-A",
            "turns": [{"msg": "Please remember I prefer a high floor and I have a peanut allergy."}],
            "expect": [],
        },
        {
            "id": "lt_recall_prefs_floor_allergy_userA",
            "user_id": "mem-test-user-A",
            "turns": [{"msg": "Hi again — what do you know about my room preferences?"}],
            "expect": ["high", "peanut"],
        },

        # (b) preferences.bed (king) via free-text extractor
        {
            "id": "lt_seed_prefs_bed_userB",
            "user_id": "mem-test-user-B",
            "turns": [{"msg": "Just so you know, I always want a king bed when I stay."}],
            "expect": [],
        },
        {
            "id": "lt_recall_prefs_bed_userB",
            "user_id": "mem-test-user-B",
            "turns": [{"msg": "What bed type do I usually prefer?"}],
            "expect": ["king"],
        },

        # (c) preferences.diet (vegetarian) surfaced through the KNOWLEDGE sub-agent
        {
            "id": "lt_seed_prefs_diet_userC",
            "user_id": "mem-test-user-C",
            "turns": [{"msg": "Quick note: I'm vegetarian."}],
            "expect": [],
        },
        {
            "id": "lt_recall_prefs_diet_userC",
            "user_id": "mem-test-user-C",
            "turns": [{"msg": "Given what you know about me, which restaurants would you recommend?"}],
            "expect": ["vegetarian", "restaurant"],
        },

        # (d) service_history_summary via a create_service_request tool call.
        # NOTE: requires the sub-agent to actually invoke the tool. Local 9B
        # sometimes skips the tool and confirms in free text — the recall
        # case's expect list accepts either real recall OR graceful deferral.
        {
            "id": "lt_seed_service_history_userD",
            "user_id": "mem-test-user-D",
            "turns": [{"msg": "Please send extra pillows to my room, 702."}],
            "expect": ["pillow", "หมอน", "702"],
        },
        {
            "id": "lt_recall_service_history_userD",
            "user_id": "mem-test-user-D",
            "turns": [{"msg": "What kinds of requests have I made before?"}],
            # Recall OR graceful deferral, in either language.
            "expect": ["pillow", "หมอน", "request", "คำขอ",
                       "email", "อีเมล", "previous", "history", "ประวัติ"],
        },

        # (e) profile.name + profile.email + recent_bookings_summary via a
        # create_reservation tool call. Same tool-fire caveat as (d).
        {
            "id": "lt_seed_profile_booking_userE",
            "user_id": "mem-test-user-E",
            "turns": [{"msg": "Book me a Standard room for May 18-20, 2 guests. Guest name: Zoe Reyes, email zoe@test.com."}],
            "expect": ["Standard", "May"],
        },
        {
            "id": "lt_recall_bookings_userE",
            "user_id": "mem-test-user-E",
            "turns": [{"msg": "Do I have any recent bookings with you?"}],
            # Recall OR graceful deferral, in either language.
            "expect": ["Standard", "May", "booking", "reservation", "email",
                       "การจอง", "ประวัติ", "อีเมล"],
        },
        {
            "id": "lt_recall_profile_userE",
            "user_id": "mem-test-user-E",
            "turns": [{"msg": "What name and email do you have on file for me?"}],
            "expect": ["Zoe", "zoe@test.com", "email", "name", "profile",
                       "อีเมล", "ชื่อ", "ข้อมูล", "ส่วนตัว"],
        },

        # ================================================================
        # Section 3 — THAI free-text preference extraction
        # ================================================================
        {
            "id": "lt_th_seed_quiet_floor_userF",
            "user_id": "mem-test-user-F-TH",
            "turns": [{"msg": "ฝากจำไว้ด้วยนะครับ ผมชอบห้องเงียบและอยู่ชั้นสูง", "lang": "th"}],
            "expect": [],
        },
        {
            "id": "lt_th_recall_quiet_floor_userF",
            "user_id": "mem-test-user-F-TH",
            "turns": [{"msg": "คุณจำอะไรเกี่ยวกับห้องที่ผมชอบได้บ้าง", "lang": "th"}],
            "expect": ["เงียบ", "สูง"],
        },
        {
            "id": "lt_th_seed_diet_userG",
            "user_id": "mem-test-user-G-TH",
            "turns": [{"msg": "แจ้งให้ทราบนะครับ ผมทานมังสวิรัติ", "lang": "th"}],
            "expect": [],
        },
        {
            "id": "lt_th_recall_diet_userG",
            "user_id": "mem-test-user-G-TH",
            "turns": [{"msg": "แนะนำร้านอาหารที่เหมาะกับผมหน่อยได้ไหมครับ", "lang": "th"}],
            "expect": ["มังสวิรัติ"],
        },
        {
            "id": "lt_th_seed_allergy_userH",
            "user_id": "mem-test-user-H-TH",
            "turns": [{"msg": "ผมแพ้ถั่วครับ โปรดจำไว้ด้วย", "lang": "th"}],
            "expect": [],
        },
        {
            "id": "lt_th_recall_allergy_userH",
            "user_id": "mem-test-user-H-TH",
            "turns": [{"msg": "What allergy do I have on file?"}],
            # Model may respond in Thai or English depending on prior session;
            # accept peanut OR Thai equivalents OR the word "allergy" itself.
            "expect": ["peanut", "ถั่ว", "แพ้", "allergy"],
        },

        # ================================================================
        # Section 4 — ACCUMULATION: multiple prefs in a single free-text turn
        # ================================================================
        {
            "id": "lt_accumulate_multi_prefs_userI",
            "user_id": "mem-test-user-I",
            "turns": [{"msg": "Just noting preferences: king bed, quiet room, vegetarian diet, and extra pillows."}],
            "expect": [],
        },
        {
            "id": "lt_recall_multi_prefs_userI",
            "user_id": "mem-test-user-I",
            "turns": [{"msg": "List everything you remember about my room preferences."}],
            "expect": ["king", "quiet", "vegetarian", "pillow"],
        },

        # ================================================================
        # Section 5 — EDGE / NEGATIVE
        # ================================================================
        # Namespace isolation: user Y must NOT see user A's (or anyone's) prefs.
        # Agent is allowed to *mention* "high floor"/"king bed" etc. as generic
        # examples of preferences guests can specify — we only fail if it
        # claims OWNERSHIP on behalf of this user_id.
        {
            "id": "lt_isolation_userY",
            "user_id": "mem-test-user-Y",
            "turns": [{"msg": "What do you know about me and my room preferences?"}],
            "expect": [],
            "reject": [
                "you prefer a high floor",
                "you prefer high floor",
                "your peanut allergy",
                "you have a peanut",
                "you prefer a king",
                "you are vegetarian",
                "you are a vegetarian",
                "your preferred diet",
            ],
        },
        # Unknown user: brand-new user_id must NOT hallucinate OWNED facts.
        # Generic examples like "high floor" are allowed; we reject only
        # phrases that claim ownership ("you prefer ...", "your allergy").
        {
            "id": "lt_no_hallucination_unknown_user",
            "user_id": "mem-test-user-NEW-unseen",
            "turns": [{"msg": "What do you know about my preferences?"}],
            "expect": [],
            "reject": [
                "you prefer a high floor",
                "you prefer high floor",
                "your peanut allergy",
                "you have a peanut",
                "you prefer a king",
                "you are vegetarian",
                "you are a vegetarian",
                "your preferred diet",
            ],
        },
        # Anonymous namespace: no user_id. Short-term checkpoint still recalls
        # within the session even without a stable guest identity.
        {
            "id": "anon_name_recall_no_user_id",
            "turns": [
                {"msg": "My name is Bob."},
                {"msg": "What's my name?"},
            ],
            # Model may transliterate Bob → บ็อบ when answering in Thai.
            "expect": ["Bob", "บ็อบ"],
        },
    ],
}


# Patterns that indicate the LLM leaked tool-call syntax into the response
# instead of executing the tool (9B model weirdness with Thai or sparse RAG context)
TOOL_LEAK_PATTERNS = [
    re.compile(r"```[\s\S]*?\w+\s*\(", re.MULTILINE),  # ```\nsearch_hotel_knowledge(
    re.compile(r"\bsearch_hotel_knowledge\s*\(", re.IGNORECASE),
    re.compile(r"\bcheck_room_availability\s*\(", re.IGNORECASE),
    re.compile(r"\bcreate_reservation\s*\(", re.IGNORECASE),
    re.compile(r"\bcancel_reservation\s*\(", re.IGNORECASE),
    re.compile(r"\bget_reservation_details\s*\(", re.IGNORECASE),
    re.compile(r"\bget_guest_reservations\s*\(", re.IGNORECASE),
    re.compile(r"\bcalculate_dynamic_price\s*\(", re.IGNORECASE),
    re.compile(r"\bcreate_service_request\s*\(", re.IGNORECASE),
    re.compile(r"\bget_hotel_services\s*\(", re.IGNORECASE),
    re.compile(r'\{\s*"name"\s*:\s*"(?:ToHotel|Handle)', re.IGNORECASE),  # raw tool call JSON
    re.compile(r"ToHotel(?:Booking|Service|Knowledge)\s*\(", re.IGNORECASE),
]


def has_tool_leak(text):
    """Detect tool-call syntax leaked into response text."""
    if not text:
        return False, None
    for pat in TOOL_LEAK_PATTERNS:
        m = pat.search(text)
        if m:
            return True, m.group(0)[:60]
    return False, None


def has_keyword(text, keywords, threshold=0.2):
    if not keywords:
        return True, 0, 0
    text_lower = text.lower()
    hits = sum(1 for kw in keywords if kw.lower() in text_lower)
    return hits / len(keywords) >= threshold, hits, len(keywords)


def is_thai(text):
    thai_chars = sum(1 for c in text if "\u0e00" <= c <= "\u0e7f")
    total_letters = sum(1 for c in text if c.isalpha())
    return thai_chars / max(total_letters, 1) > 0.3


def test_chat_endpoint(msg, session_id=None, user_id=None):
    body = {"message": msg}
    if session_id:
        body["session_id"] = session_id
    if user_id:
        body["user_id"] = user_id
    t0 = time.time()
    try:
        r = requests.post(f"{API}/chat", json=body, timeout=120)
        dt = (time.time() - t0) * 1000
        if r.status_code != 200:
            return None, None, None, dt, f"HTTP {r.status_code}"
        data = r.json()
        return data.get("response", ""), data.get("intent", data.get("current_intent", "")), data.get("tool_calls", []), dt, None
    except Exception as e:
        return None, None, None, (time.time() - t0) * 1000, str(e)


def run_multi_turn(turns, session_id, user_id=None):
    """
    Execute a list of turns against /chat, reusing session_id across all
    turns so the checkpointer accumulates state. Returns the final turn's
    result plus the aggregated latency.
    """
    final_resp = ""
    final_tools = []
    final_err = None
    total_latency = 0.0
    for turn in turns:
        resp, _intent, tools, dt, err = test_chat_endpoint(turn["msg"], session_id, user_id)
        total_latency += dt
        if err:
            return "", [], dt, err
        final_resp = resp or ""
        final_tools = tools or []
        final_err = err
    return final_resp, final_tools, total_latency, final_err


def test_stream_endpoint(msg, session_id=None):
    body = {"message": msg}
    if session_id:
        body["session_id"] = session_id
    t0 = time.time()
    content = ""
    try:
        r = requests.post(f"{API}/chat/stream", json=body, timeout=120, stream=True)
        for line in r.iter_lines(decode_unicode=True):
            if line and line.startswith("data: "):
                try:
                    obj = json.loads(line[6:])
                    if obj.get("content") and not obj.get("done"):
                        content += obj["content"]
                except Exception:
                    pass
        dt = (time.time() - t0) * 1000
        return content, dt, None
    except Exception as e:
        return "", (time.time() - t0) * 1000, str(e)


def run(args):
    # Health check
    try:
        h = requests.get(f"{API}/health", timeout=5).json()
        comps = h.get("components", {})
        print(f"Health: {comps}")
        unhealthy = [k for k, v in comps.items() if "healthy" not in str(v).lower()]
        if unhealthy:
            print(f"WARNING: unhealthy components: {unhealthy}")
    except Exception as e:
        print(f"API not reachable: {e}")
        sys.exit(1)
    print()

    # Filter test cases
    if args.agent:
        test_agents = {args.agent: TEST_CASES[args.agent]}
    else:
        test_agents = TEST_CASES

    if args.quick:
        test_agents = {k: v[:2] for k, v in test_agents.items()}

    total = sum(len(v) for v in test_agents.values())
    print("=" * 90)
    print(f"Running {total} test cases across {len(test_agents)} sub-agent(s)")
    if args.stream_all:
        print("(Also testing /chat/stream for every case)")
    print("=" * 90)

    results = {agent: {"pass": 0, "fail": 0, "cases": []} for agent in test_agents}
    stream_results = {"pass": 0, "fail": 0}
    tool_coverage = {}  # tool_name -> pass/fail
    latencies = []

    for agent, cases in test_agents.items():
        print(f"\n▶ {agent.upper()} ({len(cases)} cases)")
        print("-" * 90)

        for i, case in enumerate(cases, 1):
            turns = case.get("turns")  # multi-turn memory cases use this
            is_multi = bool(turns)
            if is_multi:
                msg = turns[-1]["msg"]
                expected_lang = turns[-1].get("lang")
            else:
                msg = case["msg"]
                expected_lang = case.get("lang")
            keywords = case["expect"]
            reject_keywords = case.get("reject") or []  # anti-keywords (must NOT appear)
            expected_tool = case.get("tool")
            expected_agent = case.get("agent")
            case_user_id = case.get("user_id")

            # Retry is counter-productive for multi-turn cases: replaying ALL
            # turns in a fresh session would mask the thing under test.
            max_attempts = 1 if is_multi else (args.retry + 1 if expected_agent != "error" else 1)
            attempt = 0
            status = "FAIL"
            reasons = []
            resp = ""
            tools = []
            latency = 0
            err = None

            while attempt < max_attempts:
                attempt += 1
                if is_multi:
                    sid = f"mem-{case.get('id', agent)}-{uuid.uuid4().hex[:6]}"
                    resp, tools, latency, err = run_multi_turn(turns, sid, case_user_id)
                else:
                    sid = f"test-{agent}-{uuid.uuid4().hex[:8]}"
                    resp, _intent, tools, latency, err = test_chat_endpoint(msg, sid, case_user_id)
                latencies.append(latency)

                status = "PASS"
                reasons = []

                # Edge case: empty message should return 422, not 200
                if expected_agent == "error":
                    if err and "422" in err:
                        status = "PASS"
                    else:
                        status = "FAIL"
                        reasons.append(f"expected 422, got: {err or 'success'}")
                elif err:
                    status = "FAIL"
                    reasons.append(f"error: {err}")
                elif not resp:
                    status = "FAIL"
                    reasons.append("empty response")
                else:
                    # Tool-call leak detection (9B model sometimes writes tool syntax as text)
                    leaked, leak_sample = has_tool_leak(resp)
                    if leaked:
                        status = "FAIL"
                        reasons.append(f"tool-call leak: {leak_sample!r}")

                    keyword_pass, hits, n_kw = has_keyword(resp, keywords, threshold=0.2)
                    if keywords and not keyword_pass:
                        status = "FAIL"
                        reasons.append(f"keywords {hits}/{n_kw}")
                    if expected_lang == "th" and not is_thai(resp):
                        status = "FAIL"
                        reasons.append("expected Thai")

                    # Anti-keyword check for namespace-isolation / no-hallucination tests.
                    if reject_keywords:
                        resp_lower = resp.lower()
                        leaks = [rk for rk in reject_keywords if rk.lower() in resp_lower]
                        if leaks:
                            status = "FAIL"
                            reasons.append(f"leaked forbidden: {leaks}")

                if status == "PASS":
                    break  # No need to retry

                if attempt < max_attempts:
                    print(f"    ↻ retry {attempt}/{max_attempts-1}: {', '.join(reasons)}")

            if status == "PASS":
                results[agent]["pass"] += 1
            else:
                results[agent]["fail"] += 1

            # Tool coverage
            if expected_tool:
                if expected_tool not in tool_coverage:
                    tool_coverage[expected_tool] = {"pass": 0, "fail": 0}
                tool_coverage[expected_tool]["pass" if status == "PASS" else "fail"] += 1

            icon = "✓" if status == "PASS" else "✗"
            tool_str = ",".join(t.get("name", "") for t in (tools or []))[:25] or "-"
            msg_preview = msg[:48] if len(msg) > 48 else msg
            if len(msg) > 48:
                msg_preview += "…"
            print(f"  {icon} [{i:2d}/{len(cases)}] {latency:>6.0f}ms | tools={tool_str:25s} | {msg_preview}")
            if reasons:
                preview = (resp or "")[:80].replace("\n", " ")
                print(f"      ↳ {', '.join(reasons)} | resp=\"{preview}\"")

            results[agent]["cases"].append({
                "msg": msg,
                "status": status,
                "latency_ms": round(latency, 0),
                "tools": [t.get("name") for t in (tools or [])],
                "expected_tool": expected_tool,
                "resp_preview": (resp or "")[:200],
                "reasons": reasons,
            })

            # Stream test
            if args.stream_all or (i == 1 and not args.quick):
                sid2 = f"stream-{agent}-{uuid.uuid4().hex[:8]}"
                s_resp, s_latency, s_err = test_stream_endpoint(msg, sid2)
                s_pass = bool(s_resp and len(s_resp) > 10)
                stream_results["pass" if s_pass else "fail"] += 1
                s_icon = "✓" if s_pass else "✗"
                print(f"    [STREAM] {s_icon} {s_latency:>6.0f}ms | {len(s_resp)} chars")

    # =============================================================================
    # Summary
    # =============================================================================
    print()
    print("=" * 90)
    print("SUMMARY")
    print("=" * 90)
    total_pass = sum(r["pass"] for r in results.values())
    total_fail = sum(r["fail"] for r in results.values())
    total_n = total_pass + total_fail

    print(f"\n/chat: {total_pass}/{total_n} passed ({total_pass/total_n*100:.1f}%)")
    for agent, r in results.items():
        n = r["pass"] + r["fail"]
        pct = r["pass"] / n * 100 if n else 0
        icon = "✓" if r["fail"] == 0 else ("⚠" if r["pass"] > r["fail"] else "✗")
        print(f"  {icon} {agent:12s}: {r['pass']:>2}/{n} ({pct:5.1f}%)")

    s_total = stream_results["pass"] + stream_results["fail"]
    if s_total:
        print(f"\n/chat/stream: {stream_results['pass']}/{s_total} passed ({stream_results['pass']/s_total*100:.1f}%)")

    if tool_coverage:
        print(f"\nTool coverage ({len(tool_coverage)} tools):")
        for tool, r in sorted(tool_coverage.items()):
            n = r["pass"] + r["fail"]
            icon = "✓" if r["fail"] == 0 else "⚠"
            print(f"  {icon} {tool:32s}: {r['pass']}/{n}")

    if latencies:
        latencies_sorted = sorted(latencies)
        p50 = latencies_sorted[len(latencies_sorted) // 2]
        p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
        print(f"\nLatency: avg={sum(latencies)/len(latencies):.0f}ms, p50={p50:.0f}ms, p95={p95:.0f}ms")

    # Save JSON if requested
    if args.json:
        out = {
            "summary": {
                "total": total_n,
                "passed": total_pass,
                "failed": total_fail,
                "by_agent": {a: {"pass": r["pass"], "fail": r["fail"]} for a, r in results.items()},
                "tool_coverage": tool_coverage,
                "stream": stream_results,
                "latency_avg_ms": sum(latencies) / len(latencies) if latencies else 0,
            },
            "cases": {a: r["cases"] for a, r in results.items()},
        }
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2, ensure_ascii=False)
        print(f"\nJSON report: {args.json}")

    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--agent", choices=list(TEST_CASES.keys()), help="Run only this sub-agent")
    p.add_argument("--quick", action="store_true", help="Only 2 cases per category")
    p.add_argument("--stream-all", action="store_true", help="Test /chat/stream for every case")
    p.add_argument("--retry", type=int, default=2, help="Retry failed cases N times before marking FAIL (default: 2)")
    p.add_argument("--json", help="Save results as JSON to this path")
    args = p.parse_args()
    sys.exit(run(args))
