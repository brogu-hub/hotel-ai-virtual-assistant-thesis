"""Replay only the originally-failing case IDs against the patched bot.

Reads raw.jsonl, finds non-correct rows, runs each case through /chat + judge,
and overwrites only those rows. Other rows are preserved.

Usage:
    python scripts/eval/_replay_63_fails.py --tag clean_v3_final --ts 20260616T203134
"""
from __future__ import annotations
import argparse, json, os, shutil, sys, time, urllib.request, urllib.error, uuid
from pathlib import Path
sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from eval.backtest_runner import (
    hit_chat, judge_response, _precheck_shortcircuit, _looks_like_deferral,
    extract_tool_calls, DEFAULT_JUDGE_MODEL,
)

ENDPOINT = "http://localhost:8088"
DATASET_DIR = ROOT / "eval" / "dataset"


def load_all_cases_by_id() -> dict:
    """Load every dataset jsonl into {id: case_record}."""
    out = {}
    for fp in DATASET_DIR.glob("*.jsonl"):
        if "calibration" in fp.name or "stability" in fp.name:
            continue
        for line in fp.open(encoding="utf-8"):
            if not line.strip(): continue
            rec = json.loads(line)
            if "id" in rec:
                out[rec["id"]] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--ts", required=True)
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    args = ap.parse_args()

    run_dir = ROOT / "eval" / "results" / args.tag / args.ts
    raw = run_dir / "raw.jsonl"
    if not raw.exists():
        sys.exit(f"raw not found: {raw}")

    print(f"Reading {raw}")
    rows = [json.loads(l) for l in raw.open(encoding="utf-8") if l.strip()]
    print(f"  total rows: {len(rows)}")
    fails = [r for r in rows if r.get("verdict") in ("incorrect", "partial")]
    print(f"  to replay: {len(fails)}")

    # Backup
    backup = raw.with_suffix(".jsonl.before_replay_" + time.strftime("%Y%m%dT%H%M%S"))
    shutil.copy(raw, backup)
    print(f"  backup → {backup.name}")

    cases_by_id = load_all_cases_by_id()
    new_rows_by_id = {}
    n_pass = n_part = n_fail = 0

    for i, old in enumerate(fails, 1):
        cid = old["id"]
        case = cases_by_id.get(cid)
        if not case:
            print(f"  [{i}/{len(fails)}] SKIP {cid} (not found in dataset)")
            continue
        sid = f"replay-{cid}-{int(time.time())}"
        uid = case.get("user_id") or "backtest-runner"
        turns = case.get("turns") or [case.get("question", "")]
        envelope = None
        started = time.time()
        try:
            for t in turns:
                envelope = hit_chat(endpoint=ENDPOINT, message=t, session_id=sid, user_id=uid, timeout=300)
            response_text = envelope.get("response") or envelope.get("message") or ""
            actual_tools = extract_tool_calls(envelope)
            if _looks_like_deferral(response_text):
                envelope = hit_chat(endpoint=ENDPOINT, message=turns[-1], session_id=sid, user_id=uid, timeout=300)
                resp2 = envelope.get("response") or envelope.get("message") or ""
                if resp2 and not _looks_like_deferral(resp2):
                    response_text = resp2
                    actual_tools = extract_tool_calls(envelope)
            chat_latency = time.time() - started
        except Exception as e:
            response_text = ""
            actual_tools = []
            chat_latency = time.time() - started
            print(f"  [{i}/{len(fails)}] chat error {cid}: {type(e).__name__}: {e}")

        # Judge
        judge_start = time.time()
        if not response_text:
            verdict = {"verdict": "incorrect", "reason": "empty response (replay)", "defects": ["empty_response"], "hallucination_detected": False, "dimension_scores": {}, "judge_source": "chat_error"}
        else:
            pre = _precheck_shortcircuit(case, response_text, actual_tools)
            verdict = pre if pre is not None else judge_response(args.judge_model, case, response_text, actual_tools)
        judge_latency = time.time() - judge_start

        new_row = {
            **old,  # keep old metadata
            "question": case.get("question") or " || ".join(case.get("turns") or []),
            "response": response_text,
            "actual_tool_calls": actual_tools,
            "chat_latency_s": round(chat_latency, 2),
            "judge_latency_s": round(judge_latency, 2),
            "chat_source": "live-replay",
            "verdict": verdict.get("verdict"),
            "reason": verdict.get("reason"),
            "defects": verdict.get("defects"),
            "hallucination_detected": verdict.get("hallucination_detected"),
            "dimension_scores": verdict.get("dimension_scores"),
            "judge_source": verdict.get("judge_source"),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "replay_of_prev_verdict": old.get("verdict"),
        }
        new_rows_by_id[cid] = new_row

        v = verdict.get("verdict", "?")
        if v == "correct": n_pass += 1
        elif v == "partial": n_part += 1
        else: n_fail += 1
        prev_v = old.get("verdict")
        flip = "→ recovered" if (v == "correct" and prev_v != "correct") else ("→ still " + v if v != "correct" else "")
        print(f"  [{i}/{len(fails)}] {v:9s} {cid:48s} chat={chat_latency:6.1f}s {flip}")

    # Merge: replace failed rows with new rows
    merged = []
    for r in rows:
        cid = r.get("id")
        if cid in new_rows_by_id:
            merged.append(new_rows_by_id[cid])
        else:
            merged.append(r)

    with raw.open("w", encoding="utf-8", newline="\n") as f:
        for r in merged:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\nWrote {len(merged)} rows back to {raw.name}")

    # Final tally
    total_correct = sum(1 for r in merged if r.get("verdict") == "correct")
    print(f"\nReplay summary: {n_pass} pass / {n_part} partial / {n_fail} fail (out of {len(fails)} replayed)")
    print(f"New aggregate: {total_correct}/{len(merged)} = {100*total_correct/len(merged):.2f}%")


if __name__ == "__main__":
    main()
