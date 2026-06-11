"""FPR/FNR rubric stability gate for the LLM-as-judge.

Bootstraps a calibration set of 30 known-correct + 30 known-incorrect
(question, response, expected_facts) triples from past raw eval rows
where the judge's verdict was unambiguously confirmed by deterministic
keyword/regex checks, then re-runs the judge on those triples and
reports false-positive rate (FPR = scored "correct" but is incorrect)
and false-negative rate (FNR = scored "incorrect" but is correct).

Gate: FPR < 10% AND FNR < 10% required to claim rubric stability.

The calibration triples come from existing iter3 raw rows, NOT new
chatbot calls — so this is reproducible at any time without depending
on the live chatbot state.

Usage:
    python scripts/eval/judge_stability.py --bootstrap \
        --source eval/results/final-postfix/20260609T205731/raw.jsonl
    python scripts/eval/judge_stability.py --run

Outputs:
    eval/dataset/rubric_calibration.jsonl  (the 60 triples + ground truth)
    eval/results/rubric_stability/<ts>/raw.jsonl       (re-judged rows)
    eval/results/rubric_stability/<ts>/report.md       (FPR/FNR with CIs)
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from eval.backtest_common import (  # noqa: E402
    TOOL_CALL_LEAK_RE,
    append_jsonl,
    call_openrouter,
    extract_content,
    has_language_leak,
    load_jsonl,
    wilson_ci,
)
from eval.backtest_runner import JUDGE_PROMPT  # noqa: E402

DATASET_DIR = ROOT / "eval" / "dataset"
RESULTS_DIR = ROOT / "eval" / "results" / "rubric_stability"
CALIBRATION_PATH = DATASET_DIR / "rubric_calibration.jsonl"

DEFAULT_JUDGE = os.getenv("JUDGE_MODEL", "deepseek/deepseek-chat-v3.1")


def is_clearly_correct(row: Dict[str, Any], case_lookup: Dict[str, Any]) -> bool:
    """Heuristic: judge said correct AND deterministic checks all pass.

    A row is "clearly correct" when:
      - verdict == "correct"
      - response contains at least one must_contain_any token
      - response contains NO must_not_contain token
      - no language leak detected
      - no tool-call leak
    """
    if row.get("verdict") != "correct":
        return False
    case = case_lookup.get(row["id"])
    if not case:
        return False
    response = row.get("response", "")
    must_any = case.get("must_contain_any", [])
    must_not = case.get("must_not_contain", [])
    if must_any and not any(s in response for s in must_any):
        return False
    if any(s in response for s in (must_not or [])):
        return False
    if TOOL_CALL_LEAK_RE.search(response):
        return False
    if has_language_leak(response, case.get("language", "en"), case.get("question", "")):
        return False
    return True


def is_clearly_incorrect(row: Dict[str, Any], case_lookup: Dict[str, Any]) -> bool:
    """Judge said incorrect AND deterministic checks confirm.

    A row is "clearly incorrect" when:
      - verdict == "incorrect"
      - response is non-empty (so not just a chat error)
      - AND at least one of:
        * missing all must_contain_any tokens, OR
        * contains a must_not_contain token, OR
        * has visible tool-call leak, OR
        * has language leak
    """
    if row.get("verdict") != "incorrect":
        return False
    case = case_lookup.get(row["id"])
    if not case:
        return False
    response = row.get("response", "")
    if not response or "chat error" in (row.get("reason") or "").lower():
        return False
    must_any = case.get("must_contain_any", [])
    must_not = case.get("must_not_contain", [])
    deterministic_fail = (
        (must_any and not any(s in response for s in must_any))
        or any(s in response for s in (must_not or []))
        or bool(TOOL_CALL_LEAK_RE.search(response))
        or has_language_leak(response, case.get("language", "en"), case.get("question", ""))
    )
    return deterministic_fail


def bootstrap_calibration(source_jsonl: Path, per_class: int = 30, seed: int = 7) -> int:
    """Build the calibration set from a past backtest's raw rows.

    Returns: total number of triples written.
    """
    # Load all source cases (the eval dataset definitions) so we can
    # cross-reference must_contain_any / must_not_contain / language.
    case_lookup: Dict[str, Any] = {}
    for fname in (
        "golden_en.jsonl", "golden_th.jsonl", "golden_cn.jsonl",
        "canaries.jsonl", "hard_negatives.jsonl", "adversarial.jsonl",
    ):
        path = DATASET_DIR / fname
        if path.exists():
            for c in load_jsonl(path):
                case_lookup[c["id"]] = c

    rows = list(load_jsonl(source_jsonl))
    clearly_correct = [r for r in rows if is_clearly_correct(r, case_lookup)]
    clearly_incorrect = [r for r in rows if is_clearly_incorrect(r, case_lookup)]

    rng = random.Random(seed)
    rng.shuffle(clearly_correct)
    rng.shuffle(clearly_incorrect)

    correct_sample = clearly_correct[:per_class]
    incorrect_sample = clearly_incorrect[:per_class]

    if len(correct_sample) < per_class or len(incorrect_sample) < per_class:
        print(
            f"WARN: only {len(correct_sample)} clearly-correct + "
            f"{len(incorrect_sample)} clearly-incorrect available from "
            f"{len(rows)} source rows (wanted {per_class} of each)",
            file=sys.stderr,
        )

    CALIBRATION_PATH.parent.mkdir(parents=True, exist_ok=True)
    if CALIBRATION_PATH.exists():
        CALIBRATION_PATH.unlink()

    written = 0
    for r, gt in [(rows_r, "correct") for rows_r in correct_sample] + \
                 [(rows_r, "incorrect") for rows_r in incorrect_sample]:
        case = case_lookup.get(r["id"], {})
        triple = {
            "id": r["id"],
            "ground_truth": gt,                  # the deterministic label
            "language": case.get("language", "en"),
            "rubric_type": case.get("rubric_type", "semantic_match"),
            "question": case.get("question", r.get("question", "")),
            "expected_facts": case.get("expected_facts", []),
            "must_contain_any": case.get("must_contain_any", []),
            "must_not_contain": case.get("must_not_contain", []),
            "expected_tool_calls": case.get("expected_tool_calls", []),
            "response": r.get("response", ""),
            "actual_tool_calls": r.get("actual_tool_calls", []),
            "source_run": str(source_jsonl).replace("\\", "/"),
            "original_verdict": r.get("verdict"),
            "original_reason": r.get("reason"),
        }
        append_jsonl(CALIBRATION_PATH, triple)
        written += 1

    print(f"Wrote {written} calibration triples to {CALIBRATION_PATH.relative_to(ROOT).as_posix()}")
    return written


def judge_triple(judge_model: str, triple: Dict[str, Any]) -> Dict[str, Any]:
    """Re-run the same JUDGE_PROMPT against the triple. Returns the parsed verdict dict."""
    prompt = JUDGE_PROMPT.format(
        rubric_type=triple.get("rubric_type", "semantic_match"),
        language=triple.get("language", "en"),
        question=triple.get("question", ""),
        expected_facts=json.dumps(triple.get("expected_facts", []), ensure_ascii=False),
        must_contain_any=json.dumps(triple.get("must_contain_any", []), ensure_ascii=False),
        must_not_contain=json.dumps(triple.get("must_not_contain", []), ensure_ascii=False),
        expected_tool_calls=json.dumps(triple.get("expected_tool_calls", []), ensure_ascii=False),
        response=(triple.get("response") or "")[:4000],
        actual_tool_calls=json.dumps(triple.get("actual_tool_calls", []), ensure_ascii=False)[:1500],
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
            data = json.loads(extract_content(env))
            if "verdict" in data:
                return data
        except Exception as exc:
            print(f"    [judge attempt {attempt+1}] {type(exc).__name__}: {exc}", file=sys.stderr)
            time.sleep(1.5 * (attempt + 1))
    return {"verdict": "incorrect", "reason": "judge_error", "defects": ["empty_response"]}


def run_stability_gate(judge_model: str) -> int:
    if not CALIBRATION_PATH.exists():
        print(f"ERROR: {CALIBRATION_PATH} not found. Run --bootstrap first.", file=sys.stderr)
        return 2
    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not set", file=sys.stderr)
        return 2

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    triples = list(load_jsonl(CALIBRATION_PATH))
    if not triples:
        print("ERROR: calibration set empty", file=sys.stderr)
        return 2

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    run_dir = RESULTS_DIR / ts
    run_dir.mkdir(parents=True, exist_ok=True)
    raw_path = run_dir / "raw.jsonl"

    print(f"\n=== Rubric stability gate ===")
    print(f"  judge       : {judge_model}")
    print(f"  triples     : {len(triples)}")
    print(f"  out dir     : {run_dir.relative_to(ROOT).as_posix()}")
    print()

    tp = fp = tn = fn = 0  # binary classification on the "correct" label
    for idx, t in enumerate(triples, start=1):
        verdict_obj = judge_triple(judge_model, t)
        judged = verdict_obj.get("verdict")
        gt = t["ground_truth"]
        gt_correct = (gt == "correct")
        judged_correct = (judged == "correct")
        if gt_correct and judged_correct:
            tp += 1
        elif gt_correct and not judged_correct:
            fn += 1
        elif (not gt_correct) and judged_correct:
            fp += 1
        else:
            tn += 1

        row = {
            "id": t["id"],
            "ground_truth": gt,
            "judged_verdict": judged,
            "judge_reason": verdict_obj.get("reason", "")[:200],
            "defects": verdict_obj.get("defects", []),
            "agree": judged == gt,
        }
        append_jsonl(raw_path, row)
        mark = "[OK ]" if row["agree"] else "[X  ]"
        print(f"  {mark} {idx:>3}/{len(triples)}  {t['id']:<48}  gt={gt} judged={judged}")

    n_correct = tp + fn
    n_incorrect = fp + tn
    fpr = fp / n_incorrect if n_incorrect else 0
    fnr = fn / n_correct if n_correct else 0
    accuracy = (tp + tn) / len(triples)
    fpr_ci = wilson_ci(fp, n_incorrect)
    fnr_ci = wilson_ci(fn, n_correct)
    fpr_pass = fpr < 0.10
    fnr_pass = fnr < 0.10

    report_lines = [
        f"# Rubric stability report — {ts}",
        "",
        f"- **Judge model**: `{judge_model}`",
        f"- **Calibration set**: {len(triples)} triples ({n_correct} known-correct + {n_incorrect} known-incorrect)",
        "",
        f"## Confusion matrix",
        "",
        f"|                  | judged correct | judged incorrect |",
        f"|------------------|---:|---:|",
        f"| ground=correct   | {tp} (TP) | {fn} (FN) |",
        f"| ground=incorrect | {fp} (FP) | {tn} (TN) |",
        "",
        f"## Headline metrics",
        "",
        f"- **FPR** (judge says correct when actually incorrect): **{fpr:.1%}** [95% CI {fpr_ci[0]:.1%}-{fpr_ci[1]:.1%}]   gate: < 10%  → {'PASS' if fpr_pass else '**FAIL**'}",
        f"- **FNR** (judge says incorrect when actually correct): **{fnr:.1%}** [95% CI {fnr_ci[0]:.1%}-{fnr_ci[1]:.1%}]   gate: < 10%  → {'PASS' if fnr_pass else '**FAIL**'}",
        f"- Accuracy: **{accuracy:.1%}**",
        "",
        f"## Gate verdict",
        "",
        f"**{'RUBRIC STABLE' if fpr_pass and fnr_pass else 'RUBRIC UNSTABLE — REVISIT JUDGE PROMPT'}**",
        "",
    ]
    (run_dir / "report.md").write_text("\n".join(report_lines), encoding="utf-8")
    (run_dir / "metrics.json").write_text(json.dumps({
        "judge_model": judge_model,
        "n_triples": len(triples),
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "fpr": fpr, "fpr_ci": fpr_ci,
        "fnr": fnr, "fnr_ci": fnr_ci,
        "accuracy": accuracy,
        "fpr_gate_pass": fpr_pass,
        "fnr_gate_pass": fnr_pass,
    }, indent=2), encoding="utf-8")

    print()
    print(f"=== verdict ===")
    print(f"  FPR: {fpr:.1%}  (gate: <10%, {'PASS' if fpr_pass else 'FAIL'})")
    print(f"  FNR: {fnr:.1%}  (gate: <10%, {'PASS' if fnr_pass else 'FAIL'})")
    print(f"  report: {(run_dir / 'report.md').relative_to(ROOT).as_posix()}")
    return 0 if (fpr_pass and fnr_pass) else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--bootstrap", action="store_true",
                   help="Build calibration set from a past backtest's raw rows")
    p.add_argument("--source", default=None,
                   help="(for --bootstrap) raw.jsonl path")
    p.add_argument("--per-class", type=int, default=30)
    p.add_argument("--run", action="store_true",
                   help="Re-judge the calibration set and report FPR/FNR")
    p.add_argument("--judge-model", default=DEFAULT_JUDGE)
    args = p.parse_args()

    if not (args.bootstrap or args.run):
        p.print_help()
        return 2

    if args.bootstrap:
        if not args.source:
            print("--bootstrap requires --source <raw.jsonl>", file=sys.stderr)
            return 2
        bootstrap_calibration(Path(args.source), per_class=args.per_class)

    if args.run:
        return run_stability_gate(args.judge_model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
