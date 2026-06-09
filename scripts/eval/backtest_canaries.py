"""Run the 15-case stability canary sweep.

Canaries are deterministic sentinels. Each case has a `must_contain_any`
list and a `must_not_contain` list; we hit /chat (or /healthz for the
infra row), apply both checks, and report pass/fail.

If >1 canary fails, the caller should abort any larger eval run — the
environment broke (model swap, chunk corruption, API change, container
restart with cold cache, etc).

Usage:
    python scripts/eval/backtest_canaries.py
    python scripts/eval/backtest_canaries.py --endpoint http://localhost:8088
    python scripts/eval/backtest_canaries.py --timeout 240   # cold-start budget

Exit codes:
    0  all canaries passed (or exactly 1 failed — within tolerance)
    1  2+ canaries failed (abort downstream eval)
    2  internal error
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from eval.backtest_common import (  # noqa: E402
    detect_lang,
    has_language_leak,
    load_jsonl,
)


def hit_chat(endpoint: str, message: str, session_id: str, timeout: float) -> Dict[str, Any]:
    """POST /chat and return the parsed envelope."""
    body = json.dumps({
        "message": message,
        "session_id": session_id,
        "user_id": "canary-runner",
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{endpoint}/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def hit_healthz(endpoint: str, timeout: float = 5.0) -> Tuple[bool, str]:
    """GET /healthz; returns (ok, body_excerpt)."""
    try:
        with urllib.request.urlopen(f"{endpoint}/healthz", timeout=timeout) as resp:
            body = resp.read().decode("utf-8")
            try:
                d = json.loads(body)
                ok = d.get("status") == "ok" or d.get("ok") is True
            except json.JSONDecodeError:
                ok = "ok" in body.lower() or resp.status == 200
            return ok, body[:200]
    except Exception as exc:
        return False, str(exc)[:200]


def evaluate_canary(
    case: Dict[str, Any],
    endpoint: str,
    timeout: float,
) -> Dict[str, Any]:
    """Run one canary; return a row with verdict + metadata."""
    cid = case["id"]
    question = case["question"]
    must_any = case.get("must_contain_any", [])
    must_not = case.get("must_not_contain", [])
    expected_lang = case.get("language", "en")
    started = time.time()
    response_text = ""
    error = None

    if question == "__INFRA_HEALTHZ__":
        ok, body = hit_healthz(endpoint, timeout=10.0)
        response_text = body
        verdict = "pass" if ok else "fail"
        failure_reason = "" if ok else "healthz did not return ok"
        return {
            "id": cid,
            "verdict": verdict,
            "latency_s": round(time.time() - started, 2),
            "response_preview": body[:200],
            "failure_reason": failure_reason,
            "language_match": True,
            "leak_detected": False,
        }

    try:
        envelope = hit_chat(
            endpoint=endpoint,
            message=question,
            session_id=f"canary-{cid}-{int(started)}",
            timeout=timeout,
        )
        response_text = envelope.get("response") or envelope.get("message") or ""
    except Exception as exc:
        error = f"http error: {exc}"

    if error:
        return {
            "id": cid,
            "verdict": "fail",
            "latency_s": round(time.time() - started, 2),
            "response_preview": "",
            "failure_reason": error,
            "language_match": False,
            "leak_detected": False,
        }

    must_any_hit = any(s in response_text for s in must_any) if must_any else True
    must_not_hit = next((s for s in must_not if s in response_text), None)
    lang_leak = has_language_leak(response_text, expected_lang, question)
    lang_match = detect_lang(response_text) == expected_lang or expected_lang == "?"

    if not must_any_hit:
        verdict = "fail"
        failure_reason = f"missing required token from must_contain_any={must_any!r}"
    elif must_not_hit:
        verdict = "fail"
        failure_reason = f"contains forbidden token: {must_not_hit!r}"
    elif lang_leak:
        verdict = "fail"
        failure_reason = f"language leak (expected {expected_lang}, got {detect_lang(response_text)})"
    else:
        verdict = "pass"
        failure_reason = ""

    return {
        "id": cid,
        "verdict": verdict,
        "latency_s": round(time.time() - started, 2),
        "response_preview": response_text[:200].replace("\n", " "),
        "failure_reason": failure_reason,
        "language_match": lang_match,
        "leak_detected": lang_leak,
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument(
        "--endpoint",
        default="http://localhost:8088",
        help="chatbot base URL (default: http://localhost:8088)",
    )
    p.add_argument(
        "--canary-file",
        default=str(ROOT / "eval" / "dataset" / "canaries.jsonl"),
        help="canary JSONL file",
    )
    p.add_argument("--timeout", type=float, default=180.0, help="per-canary timeout in seconds")
    p.add_argument("--tolerance", type=int, default=1,
                   help="how many canary failures tolerated before exit 1 (default: 1)")
    p.add_argument("--out", default=None, help="optional output file for per-row results JSONL")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    canary_path = Path(args.canary_file)
    if not canary_path.exists():
        print(f"ERROR: canary file not found: {canary_path}", file=sys.stderr)
        return 2

    cases = list(load_jsonl(canary_path))
    if not cases:
        print(f"ERROR: no canaries in {canary_path}", file=sys.stderr)
        return 2

    if not args.quiet:
        print(f"\n=== canary run ({len(cases)} cases) ===")
        print(f"endpoint: {args.endpoint}")
        print(f"timeout : {args.timeout}s per case")
        print(f"started : {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
        print()

    out_path = Path(args.out) if args.out else None
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if out_path.exists():
            out_path.unlink()

    rows = []
    pass_n = 0
    for idx, case in enumerate(cases, start=1):
        row = evaluate_canary(case, args.endpoint, args.timeout)
        rows.append(row)
        if row["verdict"] == "pass":
            pass_n += 1
        if not args.quiet:
            verdict_mark = "[PASS]" if row["verdict"] == "pass" else "[FAIL]"
            print(
                f"  {verdict_mark} {row['id']:<32} "
                f"{row['latency_s']:>6.1f}s  "
                + (row['failure_reason'] or row['response_preview'][:70])
            )
        if out_path:
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")

    fail_n = len(rows) - pass_n
    if not args.quiet:
        print()
        print(f"=== result: {pass_n}/{len(rows)} pass, {fail_n} fail ===")
        if fail_n > args.tolerance:
            print(f"ABORT downstream eval: {fail_n} canary failures exceed tolerance={args.tolerance}")
        else:
            print("OK — within tolerance")

    return 1 if fail_n > args.tolerance else 0


if __name__ == "__main__":
    raise SystemExit(main())
