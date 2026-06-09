"""Run the strategic backtest: hit /chat for each golden case + judge with DeepSeek.

Pipeline (per case):
    1. POST /chat with the case's question
    2. Capture: response text, tool_calls, latency, retries, had_leak flags
    3. Send (case + response + tool_calls) to DeepSeek Chat v3.1 via OpenRouter
       with the rubric judge prompt; force JSON output
    4. Validate the judge's JSON; if invalid, retry once then fall back to
       deterministic rule-based verdict
    5. Append the row to eval/results/{tag}/{ts}/raw.jsonl (resumable)

Resume: re-running with the same --tag/--ts skips ids already present in
raw.jsonl. Use --force to re-run everything.

Sampling: --sample-iteration N picks N cases via stratified sampling on
(domain, language); --canaries-only runs only the 15 sentinels;
--no-canaries skips them (use after baseline canary check).

Usage:
    # full strategic backtest
    python scripts/eval/backtest_runner.py --tag baseline

    # iterative fast feedback (60-160 cases)
    python scripts/eval/backtest_runner.py --tag iter1 --sample-iteration 80

    # canaries only — environmental sanity check
    python scripts/eval/backtest_runner.py --tag canary-only --canaries-only

Exit codes:
    0  run completed; report generation is the caller's concern
    1  abort (e.g. canaries failed > tolerance)
    2  internal error
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from eval.backtest_common import (  # noqa: E402
    HOTEL_TOOL_NAMES,
    TOOL_CALL_LEAK_RE,
    append_jsonl,
    call_openrouter,
    capture_version_pins,
    detect_lang,
    extract_content,
    extract_tool_calls,
    has_language_leak,
    load_jsonl,
    stratified_sample,
)

# Default judge — per the eval plan's approved model choice
DEFAULT_JUDGE_MODEL = os.getenv("JUDGE_MODEL", "deepseek/deepseek-chat-v3.1")

DATASET_DIR = ROOT / "eval" / "dataset"
RESULTS_DIR = ROOT / "eval" / "results"

JUDGE_PROMPT = """You are a grading assistant evaluating a trilingual (EN/TH/CN) hotel chatbot.

Rubric type: {rubric_type}
Question (lang={language}): {question}
Expected facts: {expected_facts}
Must contain any of: {must_contain_any}
Must NOT contain: {must_not_contain}
Expected tool calls: {expected_tool_calls}

Chatbot response:
{response}

Actual tool calls made: {actual_tool_calls}

Scoring rules:
1. exact_match_with_unit: numeric value AND unit must both be correct.
   Accept: THB / บาท / 泰铢 if value matches. Reject if value differs.
2. semantic_match: correct if all key facts in expected_facts appear.
   Extra correct info is not penalised.
3. set_match: all expected items must be present. Order does not matter.
   Partial credit: verdict=partial if >=50% items present.
4. refusal_correct: correct ONLY if the bot declined AND the question is
   genuinely out-of-scope. Confirm it didn't hallucinate a fake answer.
5. tool_invocation_match: correct ONLY if expected_tool_calls were invoked.
6. language_match: response must be in the same script as the question.
   User-provided proper names (e.g. "Wang Xiaoming" in CJK echoed in an EN
   response) do NOT count as leaks.

HALLUCINATION OVERRIDE: if the answer contains any factual claim NOT supported
by either the retrieved context OR the expected_facts, set verdict=incorrect.
Set hallucination_detected=true.

DEFECT TAGGING: from this fixed taxonomy, list every applicable tag:
  rag_miss | rag_drift | room_conflation | spec_wrong | incomplete |
  tool_not_called | tool_error | hallucination | language_leak |
  tool_call_leak | particle_mismatch | wrong_routing | empty_response |
  format_error | over_refuse

Return ONLY valid JSON, no other text:
{{
  "verdict": "correct" | "partial" | "incorrect",
  "reason": "one-sentence explanation",
  "hallucination_detected": true | false,
  "defects": ["tag1", "tag2"],
  "dimension_scores": {{
    "factual_accuracy": "PASS" | "FAIL",
    "language_match": "PASS" | "FAIL",
    "tool_invocation": "PASS" | "FAIL" | "N/A",
    "no_hallucination": "PASS" | "FAIL",
    "completeness": "PASS" | "FAIL",
    "safety": "PASS" | "FAIL"
  }}
}}
"""


def hit_chat(
    endpoint: str,
    message: str,
    session_id: str,
    user_id: str,
    timeout: float,
) -> Dict[str, Any]:
    body = json.dumps({
        "message": message,
        "session_id": session_id,
        "user_id": user_id,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{endpoint}/chat",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def deterministic_fallback_verdict(
    case: Dict[str, Any],
    response_text: str,
    actual_tools: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """When the judge fails to return valid JSON, derive a verdict from rules.

    Less rich than the LLM judge but always non-null. We assign defect
    tags from the easily-detectable categories (language_leak, tool_call_leak,
    empty_response) and leave others empty.
    """
    must_any = case.get("must_contain_any", [])
    must_not = case.get("must_not_contain", [])
    expected_tools = case.get("expected_tool_calls", []) or []
    expected_lang = case.get("language", "en")
    question = case.get("question", "")

    defects: List[str] = []
    reason_bits: List[str] = []

    if not response_text or len(response_text.strip()) < 10:
        defects.append("empty_response")
        reason_bits.append("response empty/<10 chars")

    if TOOL_CALL_LEAK_RE.search(response_text):
        defects.append("tool_call_leak")
        reason_bits.append("raw tool syntax in response")

    if has_language_leak(response_text, expected_lang, question):
        defects.append("language_leak")
        reason_bits.append(f"language leak (expected {expected_lang})")

    if must_any and not any(s in response_text for s in must_any):
        defects.append("rag_miss")
        reason_bits.append("missing must_contain_any token(s)")

    if must_not and any(s in response_text for s in must_not):
        defects.append("over_refuse")
        reason_bits.append("matched must_not_contain token")

    actual_tool_names = {t.get("name", "") for t in actual_tools}
    missing_tools = [t for t in expected_tools if t not in actual_tool_names]
    if missing_tools:
        defects.append("tool_not_called")
        reason_bits.append(f"missing expected tools: {missing_tools}")

    if defects:
        verdict = "incorrect"
    else:
        verdict = "correct"

    return {
        "verdict": verdict,
        "reason": "; ".join(reason_bits) or "ok (deterministic fallback)",
        "hallucination_detected": False,
        "defects": defects,
        "dimension_scores": {
            "factual_accuracy": "PASS" if "rag_miss" not in defects else "FAIL",
            "language_match": "PASS" if "language_leak" not in defects else "FAIL",
            "tool_invocation": "PASS" if "tool_not_called" not in defects else "FAIL",
            "no_hallucination": "PASS",
            "completeness": "PASS",
            "safety": "PASS" if "tool_call_leak" not in defects else "FAIL",
        },
        "judge_source": "deterministic_fallback",
    }


def judge_response(
    judge_model: str,
    case: Dict[str, Any],
    response_text: str,
    actual_tools: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Ask the LLM judge; fall back to deterministic verdict on failure."""
    prompt = JUDGE_PROMPT.format(
        rubric_type=case.get("rubric_type", "semantic_match"),
        language=case.get("language", "en"),
        question=case.get("question", ""),
        expected_facts=json.dumps(case.get("expected_facts", []), ensure_ascii=False),
        must_contain_any=json.dumps(case.get("must_contain_any", []), ensure_ascii=False),
        must_not_contain=json.dumps(case.get("must_not_contain", []), ensure_ascii=False),
        expected_tool_calls=json.dumps(case.get("expected_tool_calls", []), ensure_ascii=False),
        response=response_text[:4000],
        actual_tool_calls=json.dumps(actual_tools, ensure_ascii=False)[:1500],
    )

    for attempt in range(2):
        try:
            env = call_openrouter(
                model=judge_model,
                messages=[
                    {"role": "system", "content": "You return strict JSON judgments. No prose."},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.0,
                max_tokens=600,
                response_format_json=True,
                timeout=90.0,
            )
            raw = extract_content(env)
            data = json.loads(raw)
            # minimal schema check
            if not isinstance(data, dict) or "verdict" not in data:
                raise ValueError("missing verdict")
            data.setdefault("defects", [])
            data.setdefault("hallucination_detected", False)
            data.setdefault("reason", "")
            data.setdefault("dimension_scores", {})
            data["judge_source"] = judge_model
            return data
        except (json.JSONDecodeError, ValueError, urllib.error.URLError,
                TimeoutError, RuntimeError) as exc:
            print(f"    [judge attempt {attempt+1}] {type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(1.5 * (attempt + 1))
    return deterministic_fallback_verdict(case, response_text, actual_tools)


def evaluate_case(
    case: Dict[str, Any],
    *,
    endpoint: str,
    judge_model: str,
    chat_timeout: float,
) -> Dict[str, Any]:
    """Hit /chat, judge, return one result row."""
    cid = case["id"]
    started = time.time()
    response_text = ""
    actual_tools: List[Dict[str, Any]] = []
    retries = 0
    had_leak = False
    had_lang_leak = False
    error = None

    try:
        envelope = hit_chat(
            endpoint=endpoint,
            message=case["question"],
            session_id=f"backtest-{cid}-{int(started)}",
            user_id="backtest-runner",
            timeout=chat_timeout,
        )
        response_text = envelope.get("response") or envelope.get("message") or ""
        actual_tools = extract_tool_calls(envelope)
        retries = envelope.get("retries", 0) or envelope.get("retry_count", 0)
        had_leak = envelope.get("had_leak", False)
        had_lang_leak = envelope.get("had_lang_leak", False)
    except Exception as exc:
        error = f"chat error: {type(exc).__name__}: {exc}"
        response_text = ""

    chat_latency = time.time() - started

    judge_start = time.time()
    if error:
        verdict = {
            "verdict": "incorrect",
            "reason": error,
            "defects": ["empty_response"],
            "hallucination_detected": False,
            "dimension_scores": {},
            "judge_source": "chat_error",
        }
    else:
        verdict = judge_response(judge_model, case, response_text, actual_tools)
    judge_latency = time.time() - judge_start

    return {
        "id": cid,
        "domain": case.get("domain", "?"),
        "subdomain": case.get("subdomain", "?"),
        "language": case.get("language", "?"),
        "complexity": case.get("complexity", "?"),
        "status": case.get("status", "?"),
        "question": case["question"],
        "response": response_text,
        "actual_tool_calls": actual_tools,
        "chat_latency_s": round(chat_latency, 2),
        "judge_latency_s": round(judge_latency, 2),
        "retries": retries,
        "had_leak": had_leak,
        "had_lang_leak": had_lang_leak,
        "verdict": verdict.get("verdict"),
        "reason": verdict.get("reason"),
        "defects": verdict.get("defects", []),
        "hallucination_detected": verdict.get("hallucination_detected", False),
        "dimension_scores": verdict.get("dimension_scores", {}),
        "judge_source": verdict.get("judge_source"),
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def load_all_cases(include_canaries: bool, include_hard_neg: bool, include_adv: bool) -> List[Dict[str, Any]]:
    cases: List[Dict[str, Any]] = []
    for fname in ("golden_en.jsonl", "golden_th.jsonl", "golden_cn.jsonl"):
        path = DATASET_DIR / fname
        if path.exists():
            cases.extend(load_jsonl(path))
    if include_hard_neg and (DATASET_DIR / "hard_negatives.jsonl").exists():
        cases.extend(load_jsonl(DATASET_DIR / "hard_negatives.jsonl"))
    if include_adv and (DATASET_DIR / "adversarial.jsonl").exists():
        cases.extend(load_jsonl(DATASET_DIR / "adversarial.jsonl"))
    if include_canaries and (DATASET_DIR / "canaries.jsonl").exists():
        cases.extend(load_jsonl(DATASET_DIR / "canaries.jsonl"))
    return cases


def load_existing_ids(raw_path: Path) -> set:
    if not raw_path.exists():
        return set()
    seen = set()
    for row in load_jsonl(raw_path):
        seen.add(row.get("id"))
    return seen


def main() -> int:
    # Force UTF-8 on stdout/stderr so Thai/CJK chars in judge reasons don't
    # crash the runner under Windows cp1252 default.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--tag", required=True, help="label for this run (baseline, iter1, post-fix, ...)")
    p.add_argument("--ts", default=None, help="explicit timestamp dir (default: now)")
    p.add_argument("--endpoint", default="http://localhost:8088", help="chatbot URL")
    p.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    p.add_argument("--chat-timeout", type=float, default=180.0,
                   help="per-/chat timeout in seconds (allows model cold-load)")
    p.add_argument("--sample-iteration", type=int, default=0,
                   help="if >0, take a stratified sample of this many cases")
    p.add_argument("--sample-seed", type=int, default=42)
    p.add_argument("--canaries-only", action="store_true")
    p.add_argument("--no-canaries", action="store_true")
    p.add_argument("--no-hard-negatives", action="store_true")
    p.add_argument("--no-adversarial", action="store_true")
    p.add_argument("--force", action="store_true", help="ignore checkpoint, re-run every case")
    p.add_argument("--limit", type=int, default=0, help="cap N cases (debugging)")
    p.add_argument("--abort-canary-failures", type=int, default=2,
                   help="if more than this many canaries fail, abort the rest")
    args = p.parse_args()

    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not set. source .env first.", file=sys.stderr)
        return 2

    ts = args.ts or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = RESULTS_DIR / args.tag / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "raw.jsonl"

    # Save manifest
    manifest = {
        "tag": args.tag,
        "ts": ts,
        "endpoint": args.endpoint,
        "judge_model": args.judge_model,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **capture_version_pins(judge_model=args.judge_model),
    }
    (run_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Load case set
    if args.canaries_only:
        cases = list(load_jsonl(DATASET_DIR / "canaries.jsonl"))
    else:
        cases = load_all_cases(
            include_canaries=not args.no_canaries,
            include_hard_neg=not args.no_hard_negatives,
            include_adv=not args.no_adversarial,
        )

    if args.sample_iteration > 0:
        cases = stratified_sample(
            cases,
            n=args.sample_iteration,
            strata_keys=("domain", "language"),
            rng_seed=args.sample_seed,
        )

    if args.limit > 0:
        cases = cases[: args.limit]

    if not cases:
        print("No cases to run.", file=sys.stderr)
        return 2

    # Resume support
    if args.force and raw_path.exists():
        raw_path.unlink()
    done = load_existing_ids(raw_path)
    pending = [c for c in cases if c["id"] not in done]

    print(f"\n=== backtest run [{args.tag}/{ts}] ===")
    print(f"  endpoint   : {args.endpoint}")
    print(f"  judge      : {args.judge_model}")
    print(f"  cases total: {len(cases)} (already done: {len(done)}, pending: {len(pending)})")
    print(f"  out dir    : {run_dir.relative_to(ROOT).as_posix()}")
    print()

    pass_n = 0
    fail_n = 0
    partial_n = 0
    canary_fails = 0
    aborted = False

    for idx, case in enumerate(pending, start=1):
        row = evaluate_case(
            case,
            endpoint=args.endpoint,
            judge_model=args.judge_model,
            chat_timeout=args.chat_timeout,
        )
        append_jsonl(raw_path, row)
        v = row["verdict"]
        if v == "correct":
            pass_n += 1
            mark = "[PASS]"
        elif v == "partial":
            partial_n += 1
            mark = "[PART]"
        else:
            fail_n += 1
            mark = "[FAIL]"

        if case.get("status") == "canary" and v != "correct":
            canary_fails += 1

        print(
            f"  {mark} {idx:>3}/{len(pending)} "
            f"{row['id']:<48} "
            f"chat={row['chat_latency_s']:>5.1f}s "
            f"judge={row['judge_latency_s']:>4.1f}s  "
            f"{row['reason'][:60]}"
        )

        if canary_fails > args.abort_canary_failures:
            print(f"\n  ABORTED: {canary_fails} canaries failed (> tolerance {args.abort_canary_failures})")
            aborted = True
            break

    print()
    print(f"=== summary: {pass_n} pass, {partial_n} partial, {fail_n} fail "
          f"({pass_n+partial_n+fail_n}/{len(pending)} pending complete) ===")
    if aborted:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
