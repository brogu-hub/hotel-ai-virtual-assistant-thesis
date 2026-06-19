"""
Smoke-test the 8 multi-turn cases against their goldens directly,
plus the new inventory cases. No LLM-as-judge — uses the same
substring/forbid checks as the smoke probe.
"""
from __future__ import annotations
import json, sys, time, urllib.request, uuid
sys.stdout.reconfigure(encoding="utf-8")
ROOT_FILE = "z:/Dev_Drive/hote-ai-virtual-assistant-thesis"

ENDPOINT = "http://localhost:8088/chat"

def chat(message: str, sid: str, uid: str = "smoke-mt") -> str:
    body = json.dumps({"message": message, "session_id": sid, "user_id": uid}).encode("utf-8")
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return (json.loads(r.read()).get("response") or "").strip()


def grade(case: dict, response: str) -> tuple[bool, str]:
    """Returns (ok, reason). Heuristic — same as the smoke probe rules."""
    if not response:
        return False, "empty response"
    low = response.lower()
    expect_any = case.get("must_contain_any") or case.get("expected_facts") or []
    forbid = case.get("must_not_contain") or []
    ok_present = (not expect_any) or any(s.lower() in low for s in expect_any)
    # forbid: skip substring matches that fall inside expected matches (e.g. "3,500" inside "13,500")
    really_forbidden = []
    for f in forbid:
        if f.lower() not in low:
            continue
        skip = False
        for e in expect_any:
            if e.lower() in low and f.lower() in e.lower():
                skip = True
                break
        if not skip:
            really_forbidden.append(f)
    if not ok_present:
        return False, f"missing required: {expect_any}"
    if really_forbidden:
        return False, f"contains forbidden: {really_forbidden}"
    return True, "ok"


def main():
    files = ["eval/dataset/multi_turn.jsonl", "eval/dataset/quantity_inventory.jsonl"]
    cases = []
    for fname in files:
        with open(f"{ROOT_FILE}/{fname}", encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    cases.append(json.loads(line))

    print(f"=== Smoke: {len(cases)} cases (multi-turn + inventory) ===\n")
    results = []
    for case in cases:
        cid = case["id"]
        turns = case.get("turns") or [case.get("question", "")]
        sid = f"mt-smoke-{uuid.uuid4().hex[:8]}"
        t0 = time.time()
        try:
            resp = ""
            for t in turns:
                resp = chat(t, sid)
        except Exception as e:
            print(f"  [ERROR] {cid}: {type(e).__name__}: {e}")
            results.append((cid, False, "error"))
            continue
        dt = time.time() - t0
        ok, why = grade(case, resp)
        mark = "PASS" if ok else "FAIL"
        results.append((cid, ok, why))
        print(f"  [{mark}] {cid}  ({dt:.1f}s) — {why}")
        if not ok:
            print(f"     turns: {turns}")
            print(f"     resp:  {resp[:280]}")
        print()

    n_pass = sum(1 for _, ok, _ in results if ok)
    print(f"=== {n_pass}/{len(results)} pass ===")
    return 0 if n_pass == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
