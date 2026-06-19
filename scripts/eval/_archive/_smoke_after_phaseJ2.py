"""
Targeted smoke test after Phase J.2 fixes — verifies the specific
defect classes the fixes are supposed to address. Cheap (~15 chats),
no LLM-as-judge calls.

Verdict: pass/fail per probe, then aggregate.
"""
from __future__ import annotations
import json, sys, time, urllib.request, urllib.error, uuid
sys.stdout.reconfigure(encoding="utf-8")

ENDPOINT = "http://localhost:8088/chat"

# (probe_id, expected_to_contain (any), expected_to_NOT_contain (all), session_id_seed)
PROBES = [
    # === Category C — RAG fix verification ===
    ("transport-sedan-with-driver", "How much does it cost to rent a sedan with a driver for 8 hours?",
     ["2,500", "2500"], ["don't see", "don't have"], "smoke-c1"),
    ("transport-parking", "Where can I park my car at The Grand Horizon Hotel?",
     ["B1", "B2", "B3", "Basement"], ["don't see", "don't have"], "smoke-c2"),
    ("transport-taxi-fare", "Can I get a taxi at the hotel? What is the starting fare?",
     ["35"], ["external providers"], "smoke-c3"),
    ("spa-how-to-book", "How can I book a spa treatment?",
     ["303", "reception", "app"], [], "smoke-c4"),

    # === Category B — Prompt rule verification ===
    ("pricing-deluxe-must-call-tool", "How much is a Deluxe Room from June 18, 2027 to June 20, 2027?",
     ["4,500", "Standard"], [], "smoke-b1"),
    ("suite-no-bleed", "How many guests can a Suite accommodate?",
     ["4 adults", "4"], ["Penthouse", "6 adults"], "smoke-b2"),
    # NOTE: KB literally says "Designated outdoor area on ground floor terrace"
    # so those phrases are NOT hallucinations.
    ("smoking-no-fabrication", "What is the smoking policy at The Grand Horizon Hotel?",
     ["100%", "non-smoking"], ["pool deck", "rooftop bar"], "smoke-b3"),

    # === Category A — Golden patch verification (these MUST still work) ===
    ("std-size-28sqm", "What is the size of a Standard Room?",
     ["28 sqm", "28 square"], ["32 sqm"], "smoke-a1"),
    ("spa-last-booking-7-30", "Until what time can I make a booking for the spa?",
     ["7:30 PM", "19:30"], ["8:30 PM"], "smoke-a2"),
    ("fitness-level-2", "What are the operating hours for the fitness center?",
     ["6:00 AM", "10:00 PM", "6 AM", "10 PM"], ["24 hours", "4th Floor"], "smoke-a3"),

    # === Category E1 — TH date extraction ===
    ("th-3-nights-deluxe", "ขอจองห้อง Deluxe วันที่ 15 มิถุนายน 3 คืน ราคาเท่าไหร่ครับ",
     ["13,500", "4,500"], ["3,500"], "smoke-e1"),

    # === Category D — TH long completeness (timeout safety) ===
    ("th-pool-facility-question", "สิ่งอำนวยความสะดวกในห้องพักทุกประเภทมีอะไรบ้างคะ?",
     ["WiFi", "ฟรี", "free"], [], "smoke-d1"),
]


def chat(message: str, sid: str, timeout: float = 200.0) -> str:
    body = json.dumps({
        "message": message,
        "session_id": f"{sid}-{uuid.uuid4().hex[:6]}",
        "user_id": "smoke-runner",
    }).encode("utf-8")
    req = urllib.request.Request(ENDPOINT, data=body,
                                  headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return (json.loads(r.read()).get("response") or "").strip()


def main():
    print(f"=== Phase J.2 smoke test ({len(PROBES)} probes) ===\n")
    results = []
    for pid, q, expect_any, forbid_all, sid in PROBES:
        t0 = time.time()
        try:
            resp = chat(q, sid)
        except Exception as e:
            print(f"  [{pid}] ERROR: {type(e).__name__}: {e}")
            results.append((pid, False, f"error: {e}", 0))
            continue
        dt = time.time() - t0
        low = resp.lower()
        ok_present = (not expect_any) or any(s.lower() in low for s in expect_any)
        ok_absent = all(s.lower() not in low for s in forbid_all)
        passed = ok_present and ok_absent
        mark = "PASS" if passed else "FAIL"
        results.append((pid, passed, resp[:300], dt))
        print(f"  [{mark}] {pid}  ({dt:.1f}s)")
        if not passed:
            print(f"     Q: {q[:100]}")
            print(f"     A: {resp[:280]}")
            print(f"     expected any of: {expect_any}")
            print(f"     forbidden: {forbid_all}")
        print()

    n_pass = sum(1 for _, p, _, _ in results if p)
    print(f"=== {n_pass}/{len(results)} pass ===")
    if n_pass < len(results):
        print("\n⚠ Some probes failed — review before launching final triple.")
        return 1
    print("\n✓ All probes pass. Safe to launch final clean triple.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
