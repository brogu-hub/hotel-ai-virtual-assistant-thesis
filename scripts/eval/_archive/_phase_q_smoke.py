"""Phase Q 6-case smoke covering all levers.

Hits POST /chat with fresh session_id per case, prints PASS/FAIL.
"""
import json
import sys
import time
import urllib.request
import urllib.error
import uuid

# Force UTF-8 stdout for Thai output
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ENDPOINT = "http://localhost:8088"
TIMEOUT = 300.0


def post_chat(message, session_id, user_id="phaseQ_smoke"):
    body = json.dumps({
        "message": message,
        "session_id": session_id,
        "user_id": user_id,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{ENDPOINT}/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_response(env):
    for k in ("response", "answer", "text", "message"):
        v = env.get(k)
        if isinstance(v, str) and v.strip():
            return v
    # fallback
    return json.dumps(env)[:500]


def extract_tool_calls(env):
    tcs = env.get("tool_calls") or env.get("tools") or []
    if isinstance(tcs, list):
        names = []
        for t in tcs:
            if isinstance(t, dict):
                names.append(t.get("name") or t.get("tool") or "")
            elif isinstance(t, str):
                names.append(t)
        return names
    return []


def extract_meta(env):
    meta = {}
    for k in ("escalation", "escalation_metadata", "metadata", "escalated", "escalation_reason"):
        if k in env:
            meta[k] = env[k]
    # also peek into common nested locations
    if "diagnostics" in env:
        diag = env.get("diagnostics") or {}
        if isinstance(diag, dict):
            for k in ("escalation", "escalated", "escalation_reason"):
                if k in diag:
                    meta[f"diagnostics.{k}"] = diag[k]
    return meta


CASES = [
    {
        "id": "mt_en_booking_context_retention (turn 2)",
        "turns": [
            "I want to book a Deluxe Room from June 25 to June 27, 2026.",
            "How much will it cost?",
        ],
        "expected_tools": ["calculate_dynamic_price"],
        "must_any": ["4,500", "9,000"],
        "lang": "en",
    },
    {
        "id": "mt_th_change_dates (2 turns TH)",
        "turns": [
            "ขอจอง Standard วันที่ 25 มิถุนายน 2 คืน",
            "ขอเปลี่ยนเป็น 28-30 มิถุนายน ได้ไหมคะ",
        ],
        "expected_tools": ["calculate_dynamic_price"],
        "must_any": ["2,500", "5,000", "Standard"],
        "lang": "th",
    },
    {
        "id": "mi_wifi_and_breakfast_en",
        "turns": ["Could you tell me the WiFi password and when breakfast starts?"],
        "expected_tools": ["search_hotel_knowledge", "ToHotelKnowledge"],
        "must_any_a": ["welcome card", "reception", "per-stay", "HOTEL2024GUEST"],
        "must_any_b": ["6:30", "06:30"],
        "lang": "en",
    },
    {
        "id": "mi_th_wifi_and_breakfast",
        "turns": ["ขอ WiFi รหัสและเวลาอาหารเช้าหน่อยค่ะ"],
        "expected_tools": ["search_hotel_knowledge", "ToHotelKnowledge"],
        "must_any_a": ["เช็คอิน", "เมื่อเช็คอิน", "หลังจากเช็คอิน", "การ์ดต้อนรับ", "ต้อนรับ"],
        "must_any_b": ["06:30", "6:30"],
        "lang": "th",
    },
    {
        "id": "policies_lost_and_found_th_2",
        "turns": ["ถ้าฉันทำของหายที่โรงแรม ฉันควรทำอย่างไรคะ?"],
        "expected_tools": [],
        "must_any": ["lostandfound@grandparadise.com"],
        "lang": "th",
    },
    {
        "id": "pricing_standard_last_minute_en",
        "turns": ["How much is a Standard Room from June 19, 2026 to June 21, 2026?"],
        "expected_tools": ["calculate_dynamic_price"],
        "must_any": ["3,000", "6,000"],
        # tier check: "Last-Minute" tier
        "tier_check": ["Last-Minute", "last-minute", "Last Minute", "last minute"],
        "lang": "en",
    },
]


def run():
    results = []
    for idx, case in enumerate(CASES, 1):
        session_id = f"phaseQ_smoke_{idx}_{uuid.uuid4().hex[:8]}"
        print(f"\n{'='*80}")
        print(f"CASE ({chr(96+idx)}) {case['id']} | session={session_id}")
        print(f"{'='*80}")

        final_env = None
        all_tool_calls = []
        all_responses = []
        error = None

        for t_idx, turn in enumerate(case["turns"], 1):
            print(f"  turn {t_idx}: {turn[:120]}")
            try:
                env = post_chat(turn, session_id)
            except urllib.error.HTTPError as e:
                error = f"HTTP {e.code}: {e.read()[:200]}"
                break
            except urllib.error.URLError as e:
                error = f"URLError: {e}"
                break
            except Exception as e:
                error = f"Exception: {e}"
                break

            resp_text = extract_response(env)
            tcs = extract_tool_calls(env)
            all_tool_calls.extend(tcs)
            all_responses.append(resp_text)
            final_env = env
            print(f"    -> tools: {tcs}")
            print(f"    -> resp[:200]: {resp_text[:200]}")

        if error:
            print(f"  ERROR: {error}")
            results.append({"id": case["id"], "pass": False, "reason": error, "tools": [], "resp": "", "meta": {}})
            continue

        final_resp = all_responses[-1] if all_responses else ""
        meta = extract_meta(final_env or {})

        # Decide pass/fail
        reasons = []
        ok = True

        # Tool check
        expected_tools = case.get("expected_tools", [])
        if expected_tools:
            tool_hit = any(t in all_tool_calls for t in expected_tools)
            if not tool_hit:
                ok = False
                reasons.append(f"missing expected tool {expected_tools} (got {all_tool_calls})")

        # Content checks
        if "must_any" in case:
            if not any(s in final_resp for s in case["must_any"]):
                ok = False
                reasons.append(f"missing must_any {case['must_any']}")

        if "must_any_a" in case:
            if not any(s in final_resp for s in case["must_any_a"]):
                ok = False
                reasons.append(f"missing must_any_a {case['must_any_a']}")
        if "must_any_b" in case:
            if not any(s in final_resp for s in case["must_any_b"]):
                ok = False
                reasons.append(f"missing must_any_b {case['must_any_b']}")

        if "tier_check" in case:
            if not any(s in final_resp for s in case["tier_check"]):
                ok = False
                reasons.append(f"missing tier {case['tier_check']}")

        verdict = "PASS" if ok else "FAIL"
        print(f"  VERDICT: {verdict}")
        if reasons:
            print(f"  reasons: {'; '.join(reasons)}")
        print(f"  escalation/meta: {meta}")

        results.append({
            "id": case["id"],
            "pass": ok,
            "tools": all_tool_calls,
            "resp200": final_resp[:200],
            "meta": meta,
            "reasons": reasons,
        })

    print(f"\n{'#'*80}\nSUMMARY\n{'#'*80}")
    n_pass = sum(1 for r in results if r["pass"])
    for r in results:
        tag = "PASS" if r["pass"] else "FAIL"
        print(f"  [{tag}] {r['id']}")
        print(f"        tools={r.get('tools')}")
        print(f"        resp[:200]={r.get('resp200','')}")
        print(f"        meta={r.get('meta',{})}")
        if r.get("reasons"):
            print(f"        reasons={r['reasons']}")

    print(f"\nPASS COUNT: {n_pass}/{len(results)}")
    if n_pass >= 4:
        print(f"READY for replay ({n_pass}/6)")
    else:
        print(f"BLOCK ({n_pass}/6)")


if __name__ == "__main__":
    run()
