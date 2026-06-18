"""Phase M — Cloud escalation side experiment.

Replays the 11 still-failing case IDs from
    eval/results/clean_v3_final/20260616T203134/raw.jsonl
against the *cloud* OpenRouter Qwen3-max backend, judges them with
DeepSeek (same judge as canonical) and writes the results to a SEPARATE
file:
    eval/results/clean_v3_final/20260616T203134/phase_m_cloud_qwen3max.jsonl

The canonical raw.jsonl is NEVER mutated. This script does NOT touch the
report.md / manifest.json / per_*.csv either — it is a side experiment
whose purpose is to classify the remaining 11 defects as either
"model-floor" (cloud passes) or "other-defect, KB/rubric/prompt"
(cloud also fails).

Decision logic on aggregate cloud pass-rate over 11 cases:
    >=6 passes -> strong model-floor evidence -> thesis can claim
        cloud-fallback strategy as a valid production option.
    3-5 passes -> mixed: some model-floor, some KB/rubric.
    0-2 passes -> NOT a model-floor issue: defects are KB-retrieval /
        prompt / rubric and would need targeted fixes regardless of model.

Hot-swap protocol:
    1. POST /auth/login with admin credentials -> Bearer token
    2. GET  /settings/llm     -> snapshot baseline (ollama, gemma4:12b-it-q8_0)
    3. PUT  /settings/llm     -> {"backend":"openrouter","model":"qwen/qwen3-max"}
    4. GET  /settings/llm     -> verify swap took effect
    5. For each of the 11 case_ids: hit /chat (cloud is now live), judge
       with DeepSeek, append a row to phase_m_cloud_qwen3max.jsonl.
    6. PUT  /settings/llm     -> restore baseline (ollama gemma4:12b-it-q8_0)
    7. GET  /settings/llm     -> verify restore. If restore fails: abort
       with explicit error so the operator can manually fix the live bot.

Cost guard:
    ~$0.40 per 354-case full run on cloud Qwen3-max ~= ~$0.0011/case.
    11 cases ~= ~$0.012. We still check OpenRouter balance >=$1.00 before
    starting (warn-at threshold) and abort early if below.

Usage (do NOT run yet; the orchestrator will trigger this manually):
    python scripts/eval/_phase_m_cloud_experiment.py \
        --tag clean_v3_final --ts 20260616T203134

    Optional:
        --endpoint http://localhost:8088    (default; matches canonical)
        --admin-user admin                   (default; matches .env seed)
        --admin-pass admin123                (default; matches .env seed)
        --judge-model deepseek/deepseek-chat-v3.1   (default; canonical judge)
        --cloud-model qwen/qwen3-max         (default; cloud escalation target)
        --restore-backend ollama             (default; baseline to restore)
        --restore-model gemma4:12b-it-q8_0   (default; baseline to restore)
        --dry-run                            (skip hot-swap + chat; just print plan)

Exit codes:
    0  experiment ran to completion and baseline restored.
    1  hot-swap failed -- baseline preserved, no chat calls made.
    2  chat / judge run had an error AND restore failed; OPERATOR MUST
       MANUALLY RESTORE the bot. The error message identifies which case
       was running when it broke.
    3  pre-flight failed (auth, balance below floor, missing dataset case,
       missing raw.jsonl).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

# stdout utf-8 for THAI/CN text in question/response fields
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

# Reuse the canonical chat+judge plumbing so verdicts are directly
# comparable to the canonical raw.jsonl rows (same prompt, same
# precheck rules, same deferral-retry behaviour, same tool-call
# extraction).
from eval.backtest_runner import (  # noqa: E402
    hit_chat,
    judge_response,
    extract_tool_calls,
    _precheck_shortcircuit,
    _looks_like_deferral,
    DEFAULT_JUDGE_MODEL,
)


# -------- constants --------
DEFAULT_ENDPOINT = "http://localhost:8088"
DEFAULT_ADMIN_USER = "admin"
DEFAULT_ADMIN_PASS = "admin123"
DEFAULT_CLOUD_MODEL = "qwen/qwen3-max"
DEFAULT_RESTORE_BACKEND = "ollama"
DEFAULT_RESTORE_MODEL = "gemma4:12b-it-q8_0"
DEFAULT_OUTPUT_NAME = "phase_m_cloud_qwen3max.jsonl"

OPENROUTER_BALANCE_FLOOR_USD = 1.0
EXPECTED_FAIL_IDS = [
    "pricing_standard_last_minute_en",
    "rooms_penthouse_suite_th_2",
    "policies_lost_and_found_th_2",
    "hardneg_book_without_email_en",
    "adv_other_guest_pii_en",
    "adv_force_chinese_en",
    "mi_wifi_and_breakfast_en",
    "mi_th_wifi_and_breakfast",
    "mt_en_booking_context_retention",
    "mt_th_booking_3nights",
    "mt_th_change_dates",
]

DATASET_DIR = ROOT / "eval" / "dataset"


# -------- small HTTP helpers --------
def _http(method: str, url: str, body: Optional[dict] = None,
          headers: Optional[dict] = None, timeout: float = 30.0) -> Dict[str, Any]:
    data = None
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return {"status": resp.status, "body": json.loads(raw) if raw else {}}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = {"raw": raw}
        return {"status": e.code, "body": parsed, "error": True}
    except Exception as e:
        return {"status": -1, "body": {"exception": f"{type(e).__name__}: {e}"}, "error": True}


def login_admin(endpoint: str, user: str, password: str) -> str:
    """Returns the Bearer token or raises SystemExit(3)."""
    res = _http("POST", f"{endpoint}/auth/login",
                body={"username": user, "password": password}, timeout=15)
    if res["status"] != 200:
        sys.exit(f"[pre-flight] admin login failed: status={res['status']} body={res['body']}")
    tok = (res["body"] or {}).get("access_token")
    if not tok:
        sys.exit(f"[pre-flight] admin login returned no access_token: {res['body']}")
    return tok


def get_llm_settings(endpoint: str) -> Dict[str, Any]:
    res = _http("GET", f"{endpoint}/settings/llm", timeout=10)
    if res["status"] != 200:
        sys.exit(f"[pre-flight] GET /settings/llm failed: {res}")
    return res["body"]


def put_llm_settings(endpoint: str, token: str, backend: str, model: str) -> Dict[str, Any]:
    res = _http("PUT", f"{endpoint}/settings/llm",
                body={"backend": backend, "model": model},
                headers={"Authorization": f"Bearer {token}"},
                timeout=30)
    if res["status"] != 200:
        raise RuntimeError(f"PUT /settings/llm failed: status={res['status']} body={res['body']}")
    return res["body"]


def check_openrouter_balance(min_usd: float) -> Optional[float]:
    """Best-effort balance check; logs but does not abort if API unreachable.

    OpenRouter /api/v1/credits returns {data:{total_credits, total_usage}};
    available = total_credits - total_usage.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        print("[pre-flight] OPENROUTER_API_KEY unset; skipping balance check")
        return None
    res = _http(
        "GET",
        "https://openrouter.ai/api/v1/credits",
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=15,
    )
    if res.get("error"):
        print(f"[pre-flight] balance check error (continuing): {res}")
        return None
    data = (res["body"] or {}).get("data", {}) or {}
    try:
        avail = float(data.get("total_credits", 0)) - float(data.get("total_usage", 0))
    except Exception:
        print(f"[pre-flight] unexpected balance shape (continuing): {data}")
        return None
    print(f"[pre-flight] OpenRouter balance: ${avail:.4f}")
    if avail < min_usd:
        sys.exit(f"[pre-flight] balance ${avail:.4f} < floor ${min_usd:.2f}; abort")
    return avail


# -------- dataset loader --------
def load_all_cases_by_id() -> Dict[str, Dict[str, Any]]:
    """Merge every eval/dataset/*.jsonl into a {id: case} map.

    Mirrors _replay_63_fails.load_all_cases_by_id so we use identical
    dataset semantics (skips calibration / stability files).
    """
    out: Dict[str, Dict[str, Any]] = {}
    for fp in DATASET_DIR.glob("*.jsonl"):
        if "calibration" in fp.name or "stability" in fp.name:
            continue
        for line in fp.open(encoding="utf-8"):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:
                continue
            if "id" in rec:
                out[rec["id"]] = rec
    return out


# -------- canonical-raw reader --------
def load_canonical_fails(raw_path: Path) -> List[Dict[str, Any]]:
    """Return the rows from raw.jsonl whose verdict != 'correct'."""
    rows: List[Dict[str, Any]] = []
    for line in raw_path.open(encoding="utf-8"):
        line = line.strip()
        if not line:
            continue
        rec = json.loads(line)
        if rec.get("verdict") != "correct":
            rows.append(rec)
    return rows


# -------- main flow --------
def run_one_case(endpoint: str, case: Dict[str, Any], judge_model: str) -> Dict[str, Any]:
    """Mirror _replay_63_fails.main's per-case flow exactly so verdicts
    are directly comparable to canonical raw.jsonl rows. Returns the row
    to append to phase_m_cloud_qwen3max.jsonl."""
    cid = case["id"]
    sid = f"phasem-cloud-{cid}-{int(time.time())}"
    uid = case.get("user_id") or "phase-m-cloud"
    turns = case.get("turns") or [case.get("question", "")]

    envelope: Dict[str, Any] = {}
    started = time.time()
    response_text = ""
    actual_tools: List[Dict[str, Any]] = []
    chat_error: Optional[str] = None
    try:
        for t in turns:
            envelope = hit_chat(
                endpoint=endpoint, message=t,
                session_id=sid, user_id=uid, timeout=300,
            )
        response_text = envelope.get("response") or envelope.get("message") or ""
        actual_tools = extract_tool_calls(envelope)
        if _looks_like_deferral(response_text):
            envelope = hit_chat(
                endpoint=endpoint, message=turns[-1],
                session_id=sid, user_id=uid, timeout=300,
            )
            resp2 = envelope.get("response") or envelope.get("message") or ""
            if resp2 and not _looks_like_deferral(resp2):
                response_text = resp2
                actual_tools = extract_tool_calls(envelope)
    except Exception as e:
        chat_error = f"{type(e).__name__}: {e}"
    chat_latency = time.time() - started

    judge_start = time.time()
    if not response_text:
        verdict = {
            "verdict": "incorrect",
            "reason": f"empty response (cloud) {chat_error or ''}".strip(),
            "defects": ["empty_response"],
            "hallucination_detected": False,
            "dimension_scores": {},
            "judge_source": "chat_error",
        }
    else:
        pre = _precheck_shortcircuit(case, response_text, actual_tools)
        verdict = pre if pre is not None else judge_response(
            judge_model, case, response_text, actual_tools,
        )
    judge_latency = time.time() - judge_start

    return {
        "id": cid,
        "domain": case.get("domain"),
        "subdomain": case.get("subdomain"),
        "language": case.get("language"),
        "complexity": case.get("complexity"),
        "status": case.get("status"),
        "question": case.get("question") or " || ".join(case.get("turns") or []),
        "response": response_text,
        "actual_tool_calls": actual_tools,
        "chat_latency_s": round(chat_latency, 2),
        "judge_latency_s": round(judge_latency, 2),
        "chat_source": "phase-m-cloud-qwen3max",
        "verdict": verdict.get("verdict"),
        "reason": verdict.get("reason"),
        "defects": verdict.get("defects"),
        "hallucination_detected": verdict.get("hallucination_detected"),
        "dimension_scores": verdict.get("dimension_scores"),
        "judge_source": verdict.get("judge_source"),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "phase_m_meta": {
            "experiment": "phase_m_cloud_escalation",
            "cloud_model": DEFAULT_CLOUD_MODEL,
            "chat_error": chat_error,
        },
    }


def classify_outcome(n_pass: int, n_total: int) -> str:
    if n_total == 0:
        return "indeterminate"
    if n_pass >= 6:
        return ("strong_model_floor_evidence — cloud Qwen3-max recovers "
                f"{n_pass}/{n_total} canonical fails; thesis can claim "
                "cloud-fallback as a valid production option.")
    if n_pass >= 3:
        return ("mixed — some defects are model floor, others are "
                f"KB/rubric/prompt ({n_pass}/{n_total} cloud passes).")
    return ("not_model_floor — cloud Qwen3-max also fails "
            f"({n_pass}/{n_total}); defects are KB-retrieval / prompt / "
            "rubric and need targeted fixes regardless of model.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", default="clean_v3_final")
    ap.add_argument("--ts", default="20260616T203134")
    ap.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    ap.add_argument("--admin-user", default=DEFAULT_ADMIN_USER)
    ap.add_argument("--admin-pass", default=DEFAULT_ADMIN_PASS)
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE_MODEL)
    ap.add_argument("--cloud-model", default=DEFAULT_CLOUD_MODEL)
    ap.add_argument("--restore-backend", default=DEFAULT_RESTORE_BACKEND)
    ap.add_argument("--restore-model", default=DEFAULT_RESTORE_MODEL)
    ap.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    run_dir = ROOT / "eval" / "results" / args.tag / args.ts
    raw = run_dir / "raw.jsonl"
    out_path = run_dir / args.output_name
    if not raw.exists():
        print(f"[pre-flight] canonical raw not found: {raw}")
        return 3

    fails = load_canonical_fails(raw)
    print(f"[pre-flight] canonical fails in raw.jsonl: {len(fails)}")
    fail_ids = [r["id"] for r in fails]
    missing = [c for c in EXPECTED_FAIL_IDS if c not in fail_ids]
    extra = [c for c in fail_ids if c not in EXPECTED_FAIL_IDS]
    if missing or extra:
        print(f"[pre-flight] WARNING fail-id drift  missing={missing}  extra={extra}")

    cases_by_id = load_all_cases_by_id()
    not_in_dataset = [cid for cid in fail_ids if cid not in cases_by_id]
    if not_in_dataset:
        print(f"[pre-flight] cases missing from dataset/*.jsonl: {not_in_dataset}")
        return 3

    if args.dry_run:
        print("[dry-run] plan:")
        print(f"  endpoint        : {args.endpoint}")
        print(f"  cloud_model     : {args.cloud_model}")
        print(f"  restore         : {args.restore_backend}/{args.restore_model}")
        print(f"  judge_model     : {args.judge_model}")
        print(f"  output          : {out_path}")
        print(f"  cases to replay : {len(fail_ids)}")
        for c in fail_ids:
            print(f"    - {c}")
        return 0

    # -------- pre-flight checks --------
    check_openrouter_balance(OPENROUTER_BALANCE_FLOOR_USD)
    token = login_admin(args.endpoint, args.admin_user, args.admin_pass)
    baseline = get_llm_settings(args.endpoint)
    print(f"[pre-flight] baseline backend={baseline.get('backend')} "
          f"model={baseline.get('model')}")

    # -------- hot-swap to cloud --------
    try:
        swapped = put_llm_settings(args.endpoint, token,
                                   backend="openrouter", model=args.cloud_model)
    except Exception as e:
        print(f"[hot-swap] FAILED to switch to cloud: {e}")
        return 1
    verify = get_llm_settings(args.endpoint)
    if verify.get("backend") != "openrouter" or verify.get("model") != args.cloud_model:
        print(f"[hot-swap] verification mismatch after PUT: {verify}")
        # try to restore and bail
        try:
            put_llm_settings(args.endpoint, token,
                             backend=args.restore_backend, model=args.restore_model)
        except Exception as e2:
            print(f"[hot-swap] AND restore failed: {e2}")
            return 2
        return 1
    print(f"[hot-swap] live bot now backend={verify.get('backend')} "
          f"model={verify.get('model')}")

    # -------- run 11 cases against cloud --------
    out_rows: List[Dict[str, Any]] = []
    n_pass = n_part = n_fail = 0
    chat_run_failed_at: Optional[str] = None
    try:
        for i, cid in enumerate(fail_ids, 1):
            case = cases_by_id[cid]
            row = run_one_case(args.endpoint, case, args.judge_model)
            out_rows.append(row)
            v = row.get("verdict")
            if v == "correct":
                n_pass += 1
            elif v == "partial":
                n_part += 1
            else:
                n_fail += 1
            print(f"  [{i}/{len(fail_ids)}] {v:9s} {cid:48s} "
                  f"chat={row['chat_latency_s']:6.1f}s")
    except Exception as e:
        chat_run_failed_at = f"{type(e).__name__}: {e}"
        print(f"[chat-run] aborted mid-loop: {chat_run_failed_at}")

    # -------- write output BEFORE restore so partial data is preserved --------
    if out_rows:
        with out_path.open("w", encoding="utf-8", newline="\n") as f:
            for r in out_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"[output] wrote {len(out_rows)} rows -> {out_path}")
    else:
        print(f"[output] nothing to write to {out_path}")

    # -------- restore baseline --------
    try:
        restored = put_llm_settings(args.endpoint, token,
                                    backend=args.restore_backend,
                                    model=args.restore_model)
    except Exception as e:
        print(f"[restore] FAILED to restore baseline: {e}")
        print("[restore] OPERATOR MUST MANUALLY RESTORE the bot:")
        print(f"  PUT {args.endpoint}/settings/llm "
              f'{{"backend":"{args.restore_backend}","model":"{args.restore_model}"}}')
        return 2
    final = get_llm_settings(args.endpoint)
    if final.get("backend") != args.restore_backend or final.get("model") != args.restore_model:
        print(f"[restore] verification mismatch: {final}")
        return 2
    print(f"[restore] live bot back to backend={final.get('backend')} "
          f"model={final.get('model')}")

    if chat_run_failed_at:
        # chat ran but errored partway; output partial; baseline restored.
        print(f"[summary] chat loop errored: {chat_run_failed_at}")
        return 0

    # -------- summary + classification --------
    total = n_pass + n_part + n_fail
    print(f"\n[summary] cloud Qwen3-max on 11 canonical fails: "
          f"{n_pass} pass / {n_part} partial / {n_fail} fail (of {total})")
    print(f"[summary] decision: {classify_outcome(n_pass, total)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
