"""Phase V fresh-eval driver: replay an explicit case_id list with FRESH sessions.

Reads a JSON file of case_ids (e.g. a held-out slice), looks each one up across
eval/dataset/*.jsonl, hits /chat with a brand-new session_id per case (no
session reuse, no state carryover from any prior run), judges each response
with DeepSeek Chat v3.1 via OpenRouter, and writes the result rows to a
SEPARATE output file (never the canonical raw.jsonl).

Designed for variance-replication runs (run-1, run-2, run-3) and held-out
validation, where contamination from cached sessions or prior verdicts must
be ruled out.

Usage:
    python scripts/eval/_phase_v_freshrun.py \
        --ids-file eval/results/_phase_v_heldout/case_ids.json \
        --output-path eval/results/_phase_v_heldout/run-1/raw.jsonl \
        --run-tag run-1

Resumption:
    --max-cases N caps the number of cases evaluated this invocation.
    Re-running with the same --output-path skips ids already written.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from eval.backtest_runner import (  # noqa: E402
    DEFAULT_JUDGE_MODEL,
    _looks_like_deferral,
    _precheck_shortcircuit,
    extract_tool_calls,
    hit_chat,
    judge_response,
)

DATASET_DIR = ROOT / "eval" / "dataset"
DEFAULT_ENDPOINT = "http://localhost:8088"


def load_all_cases_by_id() -> Dict[str, Dict[str, Any]]:
    """Index every dataset jsonl row by its id field.

    Skips calibration/stability files (those aren't part of the eval surface).
    """
    out: Dict[str, Dict[str, Any]] = {}
    for fp in DATASET_DIR.glob("*.jsonl"):
        if "calibration" in fp.name or "stability" in fp.name:
            continue
        for line in fp.open(encoding="utf-8"):
            if not line.strip():
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if "id" in rec:
                out[rec["id"]] = rec
    return out


def load_ids_file(path: Path) -> List[str]:
    """Accept either ["id1", "id2"] or {"ids": ["id1", "id2"]} JSON shapes."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        ids = data
    elif isinstance(data, dict) and "ids" in data:
        ids = data["ids"]
    else:
        raise ValueError(
            f"--ids-file must be a JSON list or {{'ids': [...]}}; got {type(data).__name__}"
        )
    if not all(isinstance(x, str) for x in ids):
        raise ValueError("--ids-file must contain only string ids")
    return ids


def load_existing_ids(output_path: Path) -> set:
    if not output_path.exists():
        return set()
    seen = set()
    for line in output_path.open(encoding="utf-8"):
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "id" in rec:
            seen.add(rec["id"])
    return seen


def run_one_case(
    case: Dict[str, Any],
    *,
    endpoint: str,
    judge_model: str,
    chat_timeout: float,
    run_tag: str,
) -> Dict[str, Any]:
    """Hit /chat with a FRESH session_id, then judge. No cache, no reuse."""
    cid = case["id"]
    # Fresh session per case — embed run_tag so concurrent runs (run-1 vs
    # run-2) cannot collide on the LangGraph checkpointer.
    sid = f"freshrun-{run_tag}-{cid}-{int(time.time() * 1000)}"
    uid = case.get("user_id") or "phase-v-freshrun"
    turns = case.get("turns") or [case.get("question", "")]

    response_text = ""
    actual_tools: List[Dict[str, Any]] = []
    chat_latency = 0.0
    chat_error = None
    started = time.time()

    try:
        envelope = None
        for turn_msg in turns:
            envelope = hit_chat(
                endpoint=endpoint,
                message=turn_msg,
                session_id=sid,
                user_id=uid,
                timeout=chat_timeout,
            )
        response_text = envelope.get("response") or envelope.get("message") or ""
        actual_tools = extract_tool_calls(envelope)

        # Mirror backtest_runner's retry-on-deferral so a single hedge response
        # doesn't dominate the held-out aggregate.
        if _looks_like_deferral(response_text):
            envelope2 = hit_chat(
                endpoint=endpoint,
                message=turns[-1] if turns else case.get("question", ""),
                session_id=sid,
                user_id=uid,
                timeout=chat_timeout,
            )
            resp2 = envelope2.get("response") or envelope2.get("message") or ""
            if resp2 and not _looks_like_deferral(resp2):
                envelope = envelope2
                response_text = resp2
                actual_tools = extract_tool_calls(envelope)
        chat_latency = time.time() - started
    except Exception as exc:
        chat_error = f"chat error: {type(exc).__name__}: {exc}"
        chat_latency = time.time() - started

    judge_start = time.time()
    if chat_error or not response_text:
        verdict = {
            "verdict": "incorrect",
            "reason": chat_error or "empty response",
            "defects": ["empty_response"],
            "hallucination_detected": False,
            "dimension_scores": {},
            "judge_source": "chat_error",
        }
    else:
        pre = _precheck_shortcircuit(case, response_text, actual_tools)
        verdict = pre if pre is not None else judge_response(
            judge_model, case, response_text, actual_tools
        )
    judge_latency = time.time() - judge_start

    return {
        "id": cid,
        "domain": case.get("domain", "?"),
        "subdomain": case.get("subdomain", "?"),
        "language": case.get("language", "?"),
        "complexity": case.get("complexity", "?"),
        "status": case.get("status", "?"),
        "question": case.get("question") or " || ".join(case.get("turns") or []),
        "response": response_text,
        "actual_tool_calls": actual_tools,
        "chat_latency_s": round(chat_latency, 2),
        "judge_latency_s": round(judge_latency, 2),
        "chat_source": "live-freshrun",
        "session_id": sid,
        "run_tag": run_tag,
        "verdict": verdict.get("verdict"),
        "reason": verdict.get("reason"),
        "defects": verdict.get("defects", []),
        "hallucination_detected": verdict.get("hallucination_detected", False),
        "dimension_scores": verdict.get("dimension_scores", {}),
        "judge_source": verdict.get("judge_source"),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ids-file", required=True,
                    help="JSON file with case_ids: either a list or {'ids':[...]}")
    ap.add_argument("--output-path", required=True,
                    help="separate output jsonl (NOT the canonical raw.jsonl)")
    ap.add_argument("--run-tag", required=True,
                    help="variance-replication tag (run-1, run-2, run-3, ...)")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    ap.add_argument("--chat-timeout", type=float, default=300.0)
    ap.add_argument("--max-cases", type=int, default=0,
                    help="cap N cases this invocation (0 = no cap). Supports "
                         "resumption: ids already in --output-path are skipped.")
    ap.add_argument("--force", action="store_true",
                    help="ignore existing rows in --output-path and re-run all")
    args = ap.parse_args()

    ids_file = Path(args.ids_file)
    if not ids_file.exists():
        print(f"ERROR: --ids-file not found: {ids_file}", file=sys.stderr)
        return 2
    output_path = Path(args.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Guard against accidentally clobbering canonical results.
    if output_path.name == "raw.jsonl" and "_phase_v" not in str(output_path):
        print(
            f"ERROR: refusing to write to a canonical raw.jsonl path: {output_path}\n"
            f"  fresh-eval output must live under a phase-V-prefixed directory.",
            file=sys.stderr,
        )
        return 2

    target_ids = load_ids_file(ids_file)
    cases_by_id = load_all_cases_by_id()

    if args.force and output_path.exists():
        output_path.unlink()
    done = load_existing_ids(output_path)
    pending_ids = [cid for cid in target_ids if cid not in done]

    missing = [cid for cid in pending_ids if cid not in cases_by_id]
    if missing:
        print(f"WARNING: {len(missing)} requested ids not found in dataset:",
              file=sys.stderr)
        for m in missing[:10]:
            print(f"   - {m}", file=sys.stderr)
        if len(missing) > 10:
            print(f"   ... and {len(missing) - 10} more", file=sys.stderr)
    pending_ids = [cid for cid in pending_ids if cid in cases_by_id]

    if args.max_cases > 0:
        pending_ids = pending_ids[: args.max_cases]

    print(f"\n=== phase-V freshrun [{args.run_tag}] ===")
    print(f"  endpoint    : {args.endpoint}")
    print(f"  judge       : {args.judge_model}")
    print(f"  ids file    : {ids_file}")
    print(f"  output path : {output_path}")
    print(f"  ids loaded  : {len(target_ids)} (already done: {len(done)}, "
          f"missing: {len(missing)}, pending this run: {len(pending_ids)})")
    if args.max_cases > 0:
        print(f"  max-cases   : {args.max_cases}")
    print()

    if not pending_ids:
        print("Nothing to run.")
        return 0

    pass_n = part_n = fail_n = 0
    for idx, cid in enumerate(pending_ids, start=1):
        case = cases_by_id[cid]
        row = run_one_case(
            case,
            endpoint=args.endpoint,
            judge_model=args.judge_model,
            chat_timeout=args.chat_timeout,
            run_tag=args.run_tag,
        )
        # Append immediately for crash-safe resumption.
        with output_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

        v = row.get("verdict", "?")
        if v == "correct":
            pass_n += 1
            mark = "[PASS]"
        elif v == "partial":
            part_n += 1
            mark = "[PART]"
        else:
            fail_n += 1
            mark = "[FAIL]"
        print(
            f"  {mark} {idx:>3}/{len(pending_ids)} "
            f"{cid:<48} "
            f"chat={row['chat_latency_s']:>5.1f}s "
            f"judge={row['judge_latency_s']:>4.1f}s  "
            f"{(row.get('reason') or '')[:60]}"
        )

    total = pass_n + part_n + fail_n
    pct = (100.0 * pass_n / total) if total else 0.0
    print()
    print(f"=== freshrun summary [{args.run_tag}]: "
          f"{pass_n} pass / {part_n} partial / {fail_n} fail "
          f"= {pct:.2f}% correct on {total} cases ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
