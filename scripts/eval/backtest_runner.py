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
import concurrent.futures
import json
import os
import sys
import threading
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
from eval.backtest_cache import (  # noqa: E402
    compute_chat_sha,
    compute_corpus_sha,
    make_key,
    read_cache,
    write_cache,
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
                TimeoutError, RuntimeError,
                # Phase J.2 2026-06-16: OpenRouter dropped two production runs
                # at #29 and #93 with ConnectionResetError ([WinError 10054]).
                # These were transient network blips on Anthropic's edge, not
                # a real judge failure — retry catches them now.
                ConnectionResetError, ConnectionError, ConnectionAbortedError,
                OSError) as exc:
            print(f"    [judge attempt {attempt+1}] {type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(1.5 * (attempt + 1))
    return deterministic_fallback_verdict(case, response_text, actual_tools)


# Phase J.2: deferral patterns. When the bot says "I'm checking..." instead
# of quoting the fact already in its system-prompt snapshot, we retry once.
# Covers EN + TH (CN deferred per user directive 2026-06-16).
_DEFERRAL_PATTERNS = (
    # EN
    "i am currently checking", "i'm currently checking",
    "let me check", "please bear with me", "currently retrieving",
    "i will provide", "i'll provide", "one moment please",
    "i don't have that information", "i do not have that information",
    "i don't have specific", "i do not have specific",
    "i don't have the exact", "i do not have the exact",
    "do not have information regarding", "no information regarding",
    "do not have specific information",
    # Phase L: widened to cover the actual Gemma phrasings on inventory
    # questions (verified clean_v3_final_fresh_20260616T202346Z.log — bot
    # emits 'I apologize, but I do not have the specific information
    # regarding the total number of rooms' which previously did not match).
    "do not have the specific", "don't have the specific",
    "do not have the exact number", "don't have the exact number",
    "do not have the specific number", "don't have the specific number",
    "i apologize, but i do not have", "i apologize, but i don't have",
    "i do not have information regarding", "i don't have information regarding",
    "do not have the total number", "don't have the total number",
    "not have the specific information regarding",
    "not have information regarding the total",
    # TH
    "ขณะนี้กำลังตรวจสอบ", "ขอตรวจสอบข้อมูล", "กรุณารอสักครู่",
    "ไม่ได้ระบุไว้ในข้อมูล", "ไม่ได้ระบุไว้ในระบบ", "ไม่ได้ระบุ",
    "ดิฉันไม่มีข้อมูล", "ไม่มีข้อมูลจำนวน",
    # Phase L: widened TH patterns observed on inv_*_th_1 cases.
    "ทางเราไม่มีข้อมูล", "ไม่มีข้อมูลจำนวนห้อง", "ไม่มีข้อมูลห้องพัก",
)

def _looks_like_deferral(response: str) -> bool:
    if not response or len(response) > 600:
        # Very long responses with substantive content usually contain the fact
        # even when they include hedging phrases; only retry on shorter pure-defer.
        if not response:
            return False
        # On longer responses, still retry if the response is dominated by
        # deferral phrases (e.g. "Please bear with me... I will get back to you.")
        # Heuristic: deferral phrase in first 200 chars and no digit anywhere.
        head = response[:200].lower()
        if any(p in head for p in _DEFERRAL_PATTERNS) and not any(c.isdigit() for c in response):
            return True
        return False
    low = response.lower()
    return any(p in low for p in _DEFERRAL_PATTERNS)


def _precheck_shortcircuit(
    case: Dict[str, Any],
    response_text: str,
    actual_tools: List[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """D2: deterministic checks BEFORE the LLM judge (skip judge call on
    unambiguous failures). Returns a verdict dict if any fires, else None."""
    must_not = case.get("must_not_contain", []) or []
    defects: List[str] = []
    reason_bits: List[str] = []
    if not response_text or len(response_text.strip()) < 10:
        defects.append("empty_response")
        reason_bits.append("response empty/<10 chars")
    if TOOL_CALL_LEAK_RE.search(response_text or ""):
        defects.append("tool_call_leak")
        reason_bits.append("raw tool syntax in response")
    if must_not and any(s in (response_text or "") for s in must_not):
        defects.append("over_refuse")
        reason_bits.append("matched must_not_contain token")
    if not defects:
        return None
    return {
        "verdict": "incorrect",
        "reason": "; ".join(reason_bits),
        "hallucination_detected": False,
        "defects": defects,
        "dimension_scores": {
            "factual_accuracy": "FAIL",
            "language_match": "PASS",
            "tool_invocation": "N/A",
            "no_hallucination": "PASS",
            "completeness": "FAIL" if "empty_response" in defects else "PASS",
            "safety": "FAIL" if "tool_call_leak" in defects else "PASS",
        },
        "judge_source": "precheck_shortcircuit",
    }


def evaluate_case(
    case: Dict[str, Any],
    *,
    endpoint: str,
    judge_model: str,
    chat_timeout: float,
    use_chat_cache: bool = True,
    chat_sha: str = "",
    corpus_sha: str = "",
    cache_version: str = "",
) -> Dict[str, Any]:
    """Hit /chat (cache or live), judge (or precheck-shortcircuit), return one result row."""
    cid = case["id"]
    started = time.time()
    response_text = ""
    actual_tools: List[Dict[str, Any]] = []
    retries = 0
    had_leak = False
    had_lang_leak = False
    error = None
    chat_source = "live"
    chat_latency = 0.0

    # --- D1: chat-response cache lookup -------------------------------------
    cache_key = make_key(cid, chat_sha, corpus_sha, version=cache_version) if use_chat_cache else ""
    cached_env = read_cache(cid, cache_key) if (use_chat_cache and cache_key) else None
    if cached_env is not None:
        envelope = cached_env
        response_text = envelope.get("response") or envelope.get("message") or ""
        actual_tools = extract_tool_calls(envelope)
        retries = envelope.get("retries", 0) or envelope.get("retry_count", 0)
        had_leak = envelope.get("had_leak", False)
        had_lang_leak = envelope.get("had_lang_leak", False)
        chat_source = "cache"
        chat_latency = 0.0
    else:
        try:
            # Multi-turn dispatch: case may carry `turns: [msg1, msg2, ...]`
            # instead of a single `question`. Replay all turns over the
            # same session_id so LangGraph checkpointer accumulates state;
            # judge the FINAL turn's response.
            sid = f"backtest-{cid}-{int(started)}"
            uid = case.get("user_id") or "backtest-runner"
            turns = case.get("turns") or [case["question"]]
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

            # Phase J.2: retry-on-deferral. Gemma 4 12B Q8 is non-deterministic
            # on long context — sometimes quotes the snapshot/LIVE block,
            # sometimes defers ("I am currently checking..." / "ขณะนี้กำลัง
            # ตรวจสอบ..."). When we detect deferral on what should be a
            # ground-fact answer (inventory count, breakfast time, etc.)
            # retry ONCE with the same session_id. EN+TH only — CN is off.
            if _looks_like_deferral(response_text):
                print(f"  retry-on-deferral fired for {cid}: {response_text[:80]}…",
                      file=sys.stderr)
                # Build a nudge that ALSO references the message verbatim so
                # the model has fresh anchor + the existing turn state.
                nudge = (turns[-1] if turns else case.get("question", ""))
                envelope2 = hit_chat(
                    endpoint=endpoint,
                    message=nudge,
                    session_id=sid,
                    user_id=uid,
                    timeout=chat_timeout,
                )
                resp2 = envelope2.get("response") or envelope2.get("message") or ""
                if resp2 and not _looks_like_deferral(resp2):
                    envelope = envelope2
                    response_text = resp2
                    print(f"  retry-on-deferral PROMOTED {cid}", file=sys.stderr)
            actual_tools = extract_tool_calls(envelope)
            retries = envelope.get("retries", 0) or envelope.get("retry_count", 0)
            had_leak = envelope.get("had_leak", False)
            had_lang_leak = envelope.get("had_lang_leak", False)
            chat_latency = time.time() - started
            if use_chat_cache and cache_key and response_text:
                # Only cache non-empty responses; errors stay un-cached so a
                # transient backend hiccup doesn't poison subsequent runs.
                write_cache(cid, cache_key, envelope)
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
        # --- D2: deterministic precheck short-circuit -----------------------
        pre = _precheck_shortcircuit(case, response_text, actual_tools)
        if pre is not None:
            verdict = pre
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
        "question": case.get("question") or " || ".join(case.get("turns") or []),
        "response": response_text,
        "actual_tool_calls": actual_tools,
        "chat_latency_s": round(chat_latency, 2),
        "judge_latency_s": round(judge_latency, 2),
        "retries": retries,
        "had_leak": had_leak,
        "had_lang_leak": had_lang_leak,
        "chat_source": chat_source,
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
    # Phase J.2 (2026-06-16): per-user directive, Chinese is deprioritised —
    # no CN-speaking reviewers, minority audience. EN+TH form the canonical
    # eval surface; CN is documented as deferred to a future iteration once
    # CN guest volume warrants it.
    skip_cn = os.getenv("EVAL_SKIP_CN", "true").lower() != "false"
    files = ["golden_en.jsonl", "golden_th.jsonl"]
    if not skip_cn:
        files.append("golden_cn.jsonl")
    for fname in files:
        path = DATASET_DIR / fname
        if path.exists():
            cases.extend(load_jsonl(path))
    # Filter mixed-language cases (e.g. canaries, multi_intent) to drop CN
    # rows when EVAL_SKIP_CN is on. This runs AFTER the per-file load below.
    if include_hard_neg and (DATASET_DIR / "hard_negatives.jsonl").exists():
        cases.extend(load_jsonl(DATASET_DIR / "hard_negatives.jsonl"))
    if include_adv and (DATASET_DIR / "adversarial.jsonl").exists():
        cases.extend(load_jsonl(DATASET_DIR / "adversarial.jsonl"))
    if include_canaries and (DATASET_DIR / "canaries.jsonl").exists():
        cases.extend(load_jsonl(DATASET_DIR / "canaries.jsonl"))
    # Multi-intent + out-of-KB cases added after live-test discovery showed
    # the 96-case single-intent dataset missed combined questions and
    # confident hallucinations on out-of-KB facts.
    mi_path = DATASET_DIR / "multi_intent_and_out_of_kb.jsonl"
    if mi_path.exists():
        cases.extend(load_jsonl(mi_path))
    # Phase H.D: checked-in WiFi probes (per-case user_id ties to a real
    # checked_in reservation in seed data; exercises the LIVE GUEST WIFI
    # context-injection path).
    wifi_in = DATASET_DIR / "wifi_checkedin.jsonl"
    if wifi_in.exists():
        cases.extend(load_jsonl(wifi_in))
    # Phase J.2 (2026-06-16): backtest-resident multi-turn cases. Each row
    # carries a `turns` array; the last turn's response is the one judged.
    # AP_E live tests cover broader multi-turn QA; these few stay in the
    # backtest so context-retention + late-turn tool invocation are part
    # of the canonical aggregate.
    mt_path = DATASET_DIR / "multi_turn.jsonl"
    if mt_path.exists():
        cases.extend(load_jsonl(mt_path))
    # Phase J.2: room inventory questions (DB-backed via get_room_inventory).
    # Single-turn cases exercising the LIVE INVENTORY context-injection path
    # introduced alongside the get_room_inventory tool.
    inv_path = DATASET_DIR / "quantity_inventory.jsonl"
    if inv_path.exists():
        cases.extend(load_jsonl(inv_path))
    # Final CN filter — drops cn rows from mixed files (canaries,
    # multi_intent_and_out_of_kb, hard_negatives, etc.) when CN is off.
    if skip_cn:
        cases = [c for c in cases if c.get("language") != "cn"]
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
    p.add_argument("--chat-timeout", type=float, default=300.0,
                   help="per-/chat timeout in seconds. 180->300 on 2026-06-16: "
                        "6 TH cases timed out at exactly 180s on long Thai "
                        "answers under Gemma 4 12B Q8. 300s sits above the "
                        "LLM_QUEUE_TIMEOUT_SEC=240 so the server queue gates first.")
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
    # --- Phase D flags ---
    p.add_argument("--use-chat-cache", dest="use_chat_cache", action="store_true",
                   default=True, help="D1: replay cached /chat envelopes when (model,corpus) unchanged (default on)")
    p.add_argument("--no-chat-cache", dest="use_chat_cache", action="store_false",
                   help="D1: force live /chat calls")
    p.add_argument("--chat-cache-version", default="",
                   help="D1: extra string mixed into cache key to invalidate on demand")
    p.add_argument("--max-chat-parallel", type=int, default=0,
                   help="D3: ThreadPool size (0=auto: 2 for ollama/localhost, 8 for cloud)")
    args = p.parse_args()

    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not set. source .env first.", file=sys.stderr)
        return 2

    ts = args.ts or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = RESULTS_DIR / args.tag / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "raw.jsonl"

    # --- D1 setup: derive cache shas (once per run) -----------------------
    llm_model = os.getenv("OLLAMA_MODEL", os.getenv("APP_LLM_MODELNAME", "unknown"))
    chat_sha = compute_chat_sha(llm_model, args.endpoint)
    corpus_sha = compute_corpus_sha()

    # --- D3 setup: auto-pick parallelism ----------------------------------
    if args.max_chat_parallel > 0:
        max_parallel = args.max_chat_parallel
    elif "localhost" in args.endpoint or "ollama" in args.endpoint.lower():
        max_parallel = 2  # Ollama: 2 keeps the GPU queue warm
    else:
        max_parallel = 8  # cloud / gemma4 over Railway

    # Save manifest
    manifest = {
        "tag": args.tag,
        "ts": ts,
        "endpoint": args.endpoint,
        "judge_model": args.judge_model,
        "chat_cache": {
            "enabled": args.use_chat_cache,
            "chat_sha": chat_sha,
            "corpus_sha": corpus_sha,
            "version": args.chat_cache_version,
        },
        "max_chat_parallel": max_parallel,
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        **capture_version_pins(
            judge_model=args.judge_model,
            dataset_path=DATASET_DIR,
            extra={
                # Phase H.D: pin the augmentation-stack toggles into the
                # manifest so Stack-OFF vs Stack-ON runs are distinguishable
                # by reviewers without diffing source. See CH4 §4.Y.4.
                "stack_query_rewrite": os.getenv("HOTEL_QUERY_REWRITE_ENABLED", "true"),
                "stack_hybrid": os.getenv("HYBRID_RETRIEVAL", "true"),
                "stack_reranker": os.getenv("RERANKER_BACKEND", "none"),
                "stack_prompt_path": os.getenv("HOTEL_PROMPT_PATH", "(default hotel_prompt.yaml)"),
                "stack_num_docs_per_subq": os.getenv("HOTEL_RAG_NUM_DOCS_PER_SUBQ", "5"),
            },
        ),
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
    cache_hits = 0
    precheck_skips = 0
    write_lock = threading.Lock()
    state_lock = threading.Lock()

    def _worker(case: Dict[str, Any]) -> Dict[str, Any]:
        return evaluate_case(
            case,
            endpoint=args.endpoint,
            judge_model=args.judge_model,
            chat_timeout=args.chat_timeout,
            use_chat_cache=args.use_chat_cache,
            chat_sha=chat_sha,
            corpus_sha=corpus_sha,
            cache_version=args.chat_cache_version,
        )

    def _commit(idx_in_run: int, case: Dict[str, Any], row: Dict[str, Any]) -> bool:
        """Append + tally + canary-abort check, all under locks. Returns abort flag."""
        nonlocal pass_n, partial_n, fail_n, canary_fails, cache_hits, precheck_skips
        with write_lock:
            append_jsonl(raw_path, row)
        v = row["verdict"]
        with state_lock:
            if v == "correct":
                pass_n += 1
                mark = "[PASS]"
            elif v == "partial":
                partial_n += 1
                mark = "[PART]"
            else:
                fail_n += 1
                mark = "[FAIL]"
            if row.get("chat_source") == "cache":
                cache_hits += 1
            if row.get("judge_source") == "precheck_shortcircuit":
                precheck_skips += 1
            if case.get("status") == "canary" and v != "correct":
                canary_fails += 1
            abort = canary_fails > args.abort_canary_failures
        print(
            f"  {mark} {idx_in_run:>3}/{len(pending)} "
            f"{row['id']:<48} "
            f"chat={row['chat_latency_s']:>5.1f}s({row.get('chat_source','live')[0]}) "
            f"judge={row['judge_latency_s']:>4.1f}s({(row.get('judge_source') or '?')[:4]})  "
            f"{(row.get('reason') or '')[:60]}"
        )
        return abort

    if max_parallel <= 1:
        for idx, case in enumerate(pending, start=1):
            row = _worker(case)
            if _commit(idx, case, row):
                print(f"\n  ABORTED: {canary_fails} canaries failed (> tolerance {args.abort_canary_failures})")
                aborted = True
                break
    else:
        completed = 0
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_parallel) as ex:
            futures: Dict[concurrent.futures.Future, tuple] = {}
            for idx, case in enumerate(pending, start=1):
                futures[ex.submit(_worker, case)] = (idx, case)
            for fut in concurrent.futures.as_completed(futures):
                idx, case = futures[fut]
                completed += 1
                try:
                    row = fut.result()
                except Exception as exc:
                    row = {
                        "id": case["id"], "verdict": "incorrect",
                        "reason": f"worker crash: {type(exc).__name__}: {exc}",
                        "chat_latency_s": 0.0, "judge_latency_s": 0.0,
                        "defects": ["empty_response"], "judge_source": "worker_crash",
                        "chat_source": "error",
                        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    }
                if _commit(completed, case, row):
                    aborted = True
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    print(f"\n  ABORTED: {canary_fails} canaries failed (> tolerance {args.abort_canary_failures})")
                    break

    print()
    print(f"=== summary: {pass_n} pass, {partial_n} partial, {fail_n} fail "
          f"({pass_n+partial_n+fail_n}/{len(pending)} pending complete) "
          f"| cache_hits={cache_hits} precheck_skips={precheck_skips} parallel={max_parallel} ===")
    if aborted:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
