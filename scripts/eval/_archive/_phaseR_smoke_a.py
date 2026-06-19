"""Phase R smoke (a) re-run with UTF-8-safe printing."""
import io
import json
import sys
import urllib.request
import uuid

# Force UTF-8 on stdout to handle Thai characters in tool args
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

ENDPOINT = "http://localhost:8088"
TIMEOUT = 240.0


def chat(message, session_id, user_id="smoke_phase_r_a"):
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


def names(tool_calls):
    return [t.get("name", "") for t in (tool_calls or [])]


sid = f"smoke_a_{uuid.uuid4().hex[:8]}"
t1 = chat("ขอจอง Standard วันที่ 12 กรกฎาคม 2 คืน", sid)
print(f"[a] turn1 tools={names(t1.get('tool_calls'))}")
print(f"[a] turn1 response[:200]: {(t1.get('response','') or '')[:200]}")

t2 = chat("ขอเปลี่ยนเป็น 18-20 กรกฎาคม ได้ไหมคะ", sid)
tools = names(t2.get("tool_calls"))
text = t2.get("response", "") or ""
escal = t2.get("escalation", {})
has_price_tool = "calculate_dynamic_price" in tools
has_price_text = any(s in text for s in ("2,500", "5,000", "2500", "5000"))
verdict = "PASS" if has_price_tool else "FAIL"

print(f"\n== (a) mt_th_change_dates turn2: {verdict} ==")
print(f"  tool_calls: {tools}")
print(f"  response[:200]: {text[:200]}")
print(f"  escalation: {escal}")
print(f"  price_tool={has_price_tool} price_text={has_price_text}")
