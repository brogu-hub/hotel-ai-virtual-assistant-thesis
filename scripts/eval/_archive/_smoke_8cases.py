"""Smoke test 8 cases against hotel-api after restart."""
import json
import urllib.request
import urllib.error
import uuid
import sys
import io

# Force UTF-8 stdout on Windows so Thai chars don't crash print().
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

URL = "http://localhost:8088/chat"
TIMEOUT = 300

CASES = [
    {
        "id": "a",
        "label": "PRICING-FAR-FUTURE (EN)",
        "msg": "How much is a Deluxe Room from July 15, 2027 to July 17, 2027?",
        "must_any": ["4,500", "4500"],
        "should_avoid": [],
        "note_check": "ideally calculate_dynamic_price",
    },
    {
        "id": "b",
        "label": "Room-service fee",
        "msg": "Is there a fee for ordering room service?",
        "must_any": ["100 THB", "100 thb", "service charge", "100THB", "service-charge", "100 baht"],
        "should_avoid_alone": ["complimentary"],
        "note_check": "NOT complimentary alone",
    },
    {
        "id": "c",
        "label": "Pool Bar hours",
        "msg": "What are the hours for the Pool Bar?",
        "must_any": ["10:00 AM", "10:00", "10 AM", "10am", "10 am"],
        "should_avoid": ["7:00 AM", "7 AM", "7am", "7 am"],
        "note_check": "NOT 7AM (swimming pool)",
    },
    {
        "id": "d",
        "label": "Parking location",
        "msg": "Where can I park my car?",
        "must_all": ["B1", "B2", "B3"],
        "note_check": "B1/B2/B3 levels",
    },
    {
        "id": "e",
        "label": "Valet parking cost",
        "msg": "How much does valet parking cost?",
        "must_any": ["500 THB", "500THB", "500 baht", "500"],
        "note_check": "500 THB",
    },
    {
        "id": "f",
        "label": "Guest WiFi SSID",
        "msg": "What is the SSID of your guest WiFi network?",
        "must_any": ["HotelGuest", "Hotel Guest", "HotelGUEST"],
        "note_check": "HotelGuest SSID",
    },
    {
        "id": "g",
        "label": "Deluxe room count",
        "msg": "How many Deluxe Rooms do you have?",
        "must_any": ["45"],
        "note_check": "45 rooms",
    },
    {
        "id": "h",
        "label": "TH pricing (2 nights)",
        "msg": "ขอจอง Deluxe วันที่ 15 กรกฎาคม 2027 2 คืน ราคาเท่าไหร่ครับ",
        "must_all": [["4,500", "4500"], ["9,000", "9000"]],
        "note_check": "4,500 per night + 9,000 total",
    },
]


def call(msg):
    sid = str(uuid.uuid4())
    payload = {
        "message": msg,
        "session_id": sid,
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        URL, data=data, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return body, None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.read().decode('utf-8', errors='replace')[:200]}"
    except Exception as e:
        return None, f"ERR {type(e).__name__}: {e}"


def extract_text(body):
    """Try to extract response text. /chat may stream SSE-style or return JSON."""
    if not body:
        return ""
    # Try JSON first
    try:
        j = json.loads(body)
        if isinstance(j, dict):
            for k in ("response", "answer", "content", "message", "text"):
                if k in j and isinstance(j[k], str):
                    return j[k]
            return json.dumps(j)
        return str(j)
    except Exception:
        pass
    # SSE/stream chunks: collect data: pieces
    chunks = []
    for line in body.splitlines():
        s = line.strip()
        if s.startswith("data:"):
            payload = s[5:].strip()
            if payload in ("[DONE]", ""):
                continue
            try:
                obj = json.loads(payload)
                # OpenAI-style
                if isinstance(obj, dict):
                    choices = obj.get("choices")
                    if choices and isinstance(choices, list):
                        for c in choices:
                            delta = c.get("delta") or {}
                            msg = c.get("message") or {}
                            content = delta.get("content") or msg.get("content")
                            if content:
                                chunks.append(content)
                            continue
                    for k in ("content", "text", "response", "answer", "message"):
                        v = obj.get(k)
                        if isinstance(v, str):
                            chunks.append(v)
                else:
                    chunks.append(str(obj))
            except Exception:
                chunks.append(payload)
    if chunks:
        return "".join(chunks)
    return body


def check_case(case, text):
    text_l = text.lower()
    # must_any: at least one substring present (case-insensitive)
    if "must_any" in case:
        hits = [m for m in case["must_any"] if m.lower() in text_l]
        if not hits:
            return False, f"none of {case['must_any']} found"
    # must_all: every entry present; if entry is a list, treat as OR
    if "must_all" in case:
        for entry in case["must_all"]:
            if isinstance(entry, list):
                if not any(e.lower() in text_l for e in entry):
                    return False, f"missing any of {entry}"
            else:
                if entry.lower() not in text_l:
                    return False, f"missing {entry}"
    # should_avoid: hard fail if present
    if "should_avoid" in case:
        bad = [a for a in case["should_avoid"] if a.lower() in text_l]
        if bad:
            return False, f"contains forbidden token(s) {bad}"
    # should_avoid_alone: only fail if avoidant token present AND no must_any token present
    if "should_avoid_alone" in case:
        bad = [a for a in case["should_avoid_alone"] if a.lower() in text_l]
        any_good = False
        if "must_any" in case:
            any_good = any(m.lower() in text_l for m in case["must_any"])
        if bad and not any_good:
            return False, f"only has forbidden alone-token {bad}"
    return True, "ok"


def main():
    results = []
    passed = 0
    fails = []
    for case in CASES:
        print(f"\n=== ({case['id']}) {case['label']} ===")
        print(f"  Q: {case['msg'][:120]}")
        body, err = call(case["msg"])
        if err:
            print(f"  [FAIL] transport error: {err}")
            results.append((case["id"], False, err))
            fails.append(case["id"])
            continue
        text = extract_text(body) or ""
        snippet = text[:250].replace("\n", " ")
        ok, reason = check_case(case, text)
        verdict = "[PASS]" if ok else "[FAIL]"
        print(f"  {verdict} reason: {reason}")
        print(f"  snippet: {snippet!r}")
        results.append((case["id"], ok, reason))
        if ok:
            passed += 1
        else:
            fails.append(case["id"])

    total = len(CASES)
    print(f"\n========== TALLY: {passed}/{total} ==========")
    for cid, ok, reason in results:
        print(f"  ({cid}) {'PASS' if ok else 'FAIL'} - {reason}")

    if passed == total:
        print(f"\nVERDICT: READY ({passed}/{total} pass) - proceed to full re-run")
    else:
        fail_list = ",".join(fails)
        print(f"\nVERDICT: NOT READY ({passed}/{total} pass) - fix {fail_list} first")

    return 0


if __name__ == "__main__":
    sys.exit(main())
