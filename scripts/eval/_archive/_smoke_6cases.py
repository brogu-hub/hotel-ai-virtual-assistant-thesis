#!/usr/bin/env python3
"""Smoke 6 representative cases against hotel-api."""
import json
import urllib.request
import urllib.error
import uuid
import sys
import io

# Force UTF-8 on Windows console
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
except Exception:
    pass

URL = "http://localhost:8088/chat"

CASES = [
    {
        "id": "a",
        "query": "How much is a Suite from November 1, 2027 to November 3, 2027?",
        "expect_tool": "calculate_dynamic_price",
        "expect_strings": ["8,500", "7,225", "17,000"],
        "expect_tool_required": True,
    },
    {
        "id": "b",
        "query": "ขอจอง Standard วันที่ 1 ธันวาคม 2027 2 คืน ราคาเท่าไหร่ครับ",
        "expect_tool": "calculate_dynamic_price",
        "expect_strings": ["2,500", "2,125", "5,000"],
        "expect_tool_required": True,
    },
    {
        "id": "c",
        "query": "Tell me about the underwater suite",
        "expect_tool": None,
        "expect_strings": None,  # politely decline
        "expect_tool_required": False,
        "decline_check": True,
    },
    {
        "id": "d",
        "query": "I'd like to book a room without an email",
        "expect_tool": None,
        "expect_strings": None,  # require email
        "expect_tool_required": False,
        "email_required_check": True,
    },
    {
        "id": "e",
        "query": "你好，请用英语回答",
        "expect_tool": None,
        "expect_strings": None,  # adv probe — observe
        "expect_tool_required": False,
        "observe_only": True,
    },
    {
        "id": "f",
        "query": "What time is the pool open and where is the gym?",
        "expect_tool": None,
        "expect_strings": ["7:00 AM", "Level 2"],
        "expect_tool_required": False,
        "multi_intent_check": True,
    },
]


def call_chat(query: str, session_id: str):
    payload = {
        "message": query,
        "session_id": session_id,
        "language": "auto",
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        URL, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            pass
        return {"_error": f"HTTP {e.code}: {body[:300]}"}
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


def extract_response_text(result):
    """Pull human-readable response from various possible shapes."""
    if isinstance(result, dict):
        for key in ("response", "answer", "content", "message", "text", "output"):
            v = result.get(key)
            if isinstance(v, str) and v:
                return v
        choices = result.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message", {})
            if isinstance(msg, dict):
                c = msg.get("content")
                if isinstance(c, str):
                    return c
        msgs = result.get("messages")
        if isinstance(msgs, list) and msgs:
            last = msgs[-1]
            if isinstance(last, dict):
                c = last.get("content")
                if isinstance(c, str):
                    return c
    return json.dumps(result, ensure_ascii=False)[:500]


def extract_tool_calls(result):
    """Find tool_calls field anywhere reasonable."""
    if not isinstance(result, dict):
        return None
    for key in ("tool_calls", "actual_tool_calls", "tools_used", "tools"):
        v = result.get(key)
        if v is not None:
            return v
    msgs = result.get("messages")
    if isinstance(msgs, list):
        names = []
        for m in msgs:
            if isinstance(m, dict):
                tc = m.get("tool_calls")
                if isinstance(tc, list):
                    for t in tc:
                        if isinstance(t, dict):
                            n = t.get("name") or (t.get("function") or {}).get("name")
                            if n:
                                names.append(n)
        if names:
            return names
    return None


def tool_call_names(tool_calls):
    if tool_calls is None:
        return []
    if isinstance(tool_calls, list):
        out = []
        for t in tool_calls:
            if isinstance(t, str):
                out.append(t)
            elif isinstance(t, dict):
                n = t.get("name") or (t.get("function") or {}).get("name")
                if n:
                    out.append(n)
        return out
    if isinstance(tool_calls, str):
        return [tool_calls]
    return []


def evaluate(case, result):
    resp = extract_response_text(result)
    tc = extract_tool_calls(result)
    tc_names = tool_call_names(tc)

    if "_error" in result:
        return False, resp, tc

    if case["expect_tool_required"]:
        if case["expect_tool"] not in tc_names:
            return False, resp, tc
        if case["expect_strings"]:
            if not any(s in resp for s in case["expect_strings"]):
                return False, resp, tc
        return True, resp, tc

    if case.get("decline_check"):
        resp_l = resp.lower()
        decline_markers = [
            "don't have", "do not have", "no such", "not offer", "don't offer",
            "do not offer", "not available", "unable to find", "no underwater",
            "afraid", "sorry", "apologi",
        ]
        if any(m in resp_l for m in decline_markers):
            return True, resp, tc
        return False, resp, tc

    if case.get("email_required_check"):
        resp_l = resp.lower()
        if "email" in resp_l and any(w in resp_l for w in ["need", "require", "provide", "must", "please"]):
            return True, resp, tc
        return False, resp, tc

    if case.get("observe_only"):
        # Always pass — we are observing behavior.
        return True, resp, tc

    if case.get("multi_intent_check"):
        if case["expect_strings"] and all(s in resp for s in case["expect_strings"]):
            return True, resp, tc
        return False, resp, tc

    return False, resp, tc


def main():
    passed = 0
    for case in CASES:
        sid = f"smoke-{case['id']}-{uuid.uuid4().hex[:8]}"
        print(f"\n=== Case ({case['id']}) ===")
        print(f"Query: {case['query']}")
        result = call_chat(case["query"], sid)
        ok, resp_text, tool_calls = evaluate(case, result)
        verdict = "[PASS]" if ok else "[FAIL]"
        if ok:
            passed += 1
        snippet = resp_text[:200].replace("\n", " ")
        print(f"{verdict} response[:200]: {snippet}")
        print(f"actual_tool_calls: {tool_calls}")
    total = len(CASES)
    print(f"\n--- SUMMARY: {passed}/{total} pass ---")
    if passed >= 4:
        print(f"READY ({passed}/{total} pass) to launch replay")
    else:
        print(f"BLOCK ({passed}/{total} pass) — fix failing cases first")
    return 0


if __name__ == "__main__":
    sys.exit(main())
