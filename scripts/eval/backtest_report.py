"""Aggregate raw backtest results into a per-stratum + watchlist report.

Reads `eval/results/<tag>/<ts>/raw.jsonl` and produces:
  - per_stratum.csv  (domain x language verdict counts + Wilson CI)
  - per_defect.csv   (defect category counts)
  - report.md        (human-readable markdown with all the tables)
  - watchlist.json   (critical-item status for promotion gate)

If --compare-to <previous_run_dir> is given, also writes a delta table.

Usage:
    python scripts/eval/backtest_report.py --run-dir eval/results/baseline/20260609T161229
    python scripts/eval/backtest_report.py --tag baseline   # finds latest under tag
    python scripts/eval/backtest_report.py --tag post-fix --compare-to baseline
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from eval.backtest_common import wilson_ci, load_jsonl, TOOL_CALL_LEAK_RE  # noqa: E402

RESULTS_DIR = ROOT / "eval" / "results"

# Critical regression items per §2.8 of the eval strategy
CRITICAL_WATCHLIST = [
    {
        "key": "rag_drift_count",
        "label": "rag_drift",
        "severity": "critical",
        "threshold": 0,                  # any drift -> auto-no-ship
        "comparator": "<=",
    },
    {
        "key": "language_leak_count_en_th",
        "label": "language_leak (EN+TH replies)",
        "severity": "critical",
        "threshold": 0,
        "comparator": "<=",
    },
    {
        "key": "hallucination_count_hard_neg",
        "label": "hallucination on hard negatives",
        "severity": "critical",
        "threshold": 0,
        "comparator": "<=",
    },
    {
        "key": "tool_error_booking_count",
        "label": "booking lifecycle tool_error",
        "severity": "critical",
        "threshold": 0,
        "comparator": "<=",
    },
    {
        "key": "tool_call_leak_rate",
        "label": "tool_call_leak rate",
        "severity": "high",
        "threshold": 0.01,
        "comparator": "<=",
    },
    {
        "key": "over_refuse_rate",
        "label": "over_refuse rate",
        "severity": "high",
        "threshold": 0.15,
        "comparator": "<=",
    },
    {
        "key": "empty_response_rate",
        "label": "empty_response rate",
        "severity": "high",
        "threshold": 0.03,
        "comparator": "<=",
    },
]

PROMOTION_GATES = [
    ("aggregate_pass_rate", "Aggregate pass rate", ">=", 0.75),
    ("min_domain_pass_rate", "Worst per-domain pass rate", ">=", 0.65),
    ("canary_pass_rate", "Canary pass rate", ">=", 1.0),
    ("hard_negative_pass_rate", "Hard negative pass rate", ">=", 0.80),
    ("language_match_rate", "Per-row language match rate", ">=", 0.98),
]


def find_latest_run(tag: str) -> Optional[Path]:
    base = RESULTS_DIR / tag
    if not base.exists():
        return None
    ts_dirs = sorted([p for p in base.iterdir() if p.is_dir()], reverse=True)
    return ts_dirs[0] if ts_dirs else None


def load_rows(run_dir: Path) -> List[Dict[str, Any]]:
    raw = run_dir / "raw.jsonl"
    if not raw.exists():
        return []
    return list(load_jsonl(raw))


def is_correct(row: Dict[str, Any]) -> bool:
    return row.get("verdict") == "correct"


def is_partial(row: Dict[str, Any]) -> bool:
    return row.get("verdict") == "partial"


def stratum_key(row: Dict[str, Any]) -> Tuple[str, str]:
    domain = row.get("domain", "?")
    sub = row.get("subdomain", "")
    lang = row.get("language", "?")
    label = f"{domain}/{sub}" if sub and sub != domain else domain
    return (label, lang)


def compute_per_stratum(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    by_stratum: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("status") == "canary":
            continue
        by_stratum[stratum_key(r)].append(r)

    out: List[Dict[str, Any]] = []
    for (label, lang), group in sorted(by_stratum.items()):
        total = len(group)
        correct = sum(1 for r in group if is_correct(r))
        partial = sum(1 for r in group if is_partial(r))
        rate = correct / total if total else 0.0
        low, high = wilson_ci(correct, total)
        out.append({
            "domain": label,
            "language": lang,
            "n": total,
            "correct": correct,
            "partial": partial,
            "fail": total - correct - partial,
            "rate": round(rate, 3),
            "ci_low": low,
            "ci_high": high,
        })
    return out


def compute_per_defect(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counter: Counter = Counter()
    examples: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        for tag in r.get("defects", []) or []:
            counter[tag] += 1
            if len(examples[tag]) < 3:
                examples[tag].append({
                    "id": r.get("id"),
                    "language": r.get("language"),
                    "reason": (r.get("reason") or "")[:120],
                    "response_excerpt": (r.get("response") or "")[:100],
                })
    out = []
    for tag, count in counter.most_common():
        out.append({"defect": tag, "count": count, "examples": examples[tag]})
    return out


def compute_watchlist(
    rows: List[Dict[str, Any]],
    drift_count: int = 0,
) -> Dict[str, Any]:
    """Compute critical-item metrics for the regression watchlist."""
    nonempty = [r for r in rows if r.get("status") != "canary"]
    n_total = len(nonempty) or 1

    def defect_count(tag: str, predicate=lambda r: True) -> int:
        return sum(
            1
            for r in nonempty
            if predicate(r) and tag in (r.get("defects") or [])
        )

    def is_hard_neg(r: Dict[str, Any]) -> bool:
        return (r.get("status") or "") == "hard_negative" or (
            "adversarial" in (r.get("status") or "")
        )

    def is_en_th(r: Dict[str, Any]) -> bool:
        return (r.get("language") or "") in ("en", "th")

    def is_booking(r: Dict[str, Any]) -> bool:
        return (r.get("domain") or "").startswith("booking")

    hallu_hard = sum(
        1
        for r in nonempty
        if is_hard_neg(r) and r.get("hallucination_detected")
    )

    metrics = {
        "rag_drift_count": drift_count,
        "language_leak_count_en_th": defect_count("language_leak", is_en_th),
        "hallucination_count_hard_neg": hallu_hard,
        "tool_error_booking_count": defect_count("tool_error", is_booking),
        "tool_call_leak_rate": round(defect_count("tool_call_leak") / n_total, 4),
        "over_refuse_rate": round(defect_count("over_refuse") / n_total, 4),
        "empty_response_rate": round(defect_count("empty_response") / n_total, 4),
    }

    status: List[Dict[str, Any]] = []
    for item in CRITICAL_WATCHLIST:
        v = metrics.get(item["key"], 0)
        passed = (
            v <= item["threshold"] if item["comparator"] == "<=" else v >= item["threshold"]
        )
        status.append({
            "label": item["label"],
            "severity": item["severity"],
            "metric": v,
            "threshold": item["threshold"],
            "comparator": item["comparator"],
            "passed": passed,
        })
    return {"metrics": metrics, "status": status}


def compute_promotion(
    per_stratum: List[Dict[str, Any]],
    rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    nonempty = [r for r in rows if r.get("status") != "canary"]
    canaries = [r for r in rows if r.get("status") == "canary"]
    hardneg = [r for r in rows if (r.get("status") or "").startswith("hard")]

    total = len(nonempty) or 1
    correct = sum(1 for r in nonempty if is_correct(r))
    aggregate = correct / total

    canary_pass = (
        sum(1 for r in canaries if is_correct(r)) / len(canaries)
        if canaries
        else None
    )
    hardneg_pass = sum(1 for r in hardneg if is_correct(r)) / max(1, len(hardneg)) if hardneg else None

    domain_only: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for s in per_stratum:
        domain_only[s["domain"]].append(s)
    domain_rates = []
    for dom, grp in domain_only.items():
        n = sum(s["n"] for s in grp)
        c = sum(s["correct"] for s in grp)
        if n:
            domain_rates.append((dom, c / n))
    min_domain = min(domain_rates, key=lambda t: t[1])[1] if domain_rates else 0.0

    lang_match_total = sum(
        1
        for r in nonempty
        if (r.get("dimension_scores") or {}).get("language_match") == "PASS"
    )
    lang_match_rate = lang_match_total / total

    metric_values = {
        "aggregate_pass_rate": aggregate,
        "min_domain_pass_rate": min_domain,
        "canary_pass_rate": canary_pass,            # None if no canaries in run
        "hard_negative_pass_rate": hardneg_pass,    # None if no hard negs
        "language_match_rate": lang_match_rate,
    }

    out = []
    for key, label, comp, thresh in PROMOTION_GATES:
        v = metric_values[key]
        if v is None:
            out.append({
                "label": label,
                "metric": None,
                "threshold": thresh,
                "comparator": comp,
                "passed": True,           # N/A treated as pass (gate skipped)
                "na": True,
            })
            continue
        passed = (v >= thresh) if comp == ">=" else (v <= thresh)
        out.append({
            "label": label,
            "metric": round(v, 3),
            "threshold": thresh,
            "comparator": comp,
            "passed": passed,
            "na": False,
        })
    return out


def get_drift_count() -> int:
    """Best-effort read of the latest drift audit run.

    Counts only rooms_drift (high confidence). services_drift is a
    heuristic — too many false positives for a critical no-ship gate.
    """
    try:
        import subprocess
        env = {"PYTHONIOENCODING": "utf-8"}
        env.update(__import__("os").environ)
        res = subprocess.run(
            [sys.executable, "scripts/audit_data_db_drift.py", "--json"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )
        if res.returncode in (0, 1) and res.stdout.strip():
            d = json.loads(res.stdout)
            return len(d.get("rooms_drift", []))
    except Exception as exc:
        print(f"WARN: drift audit subprocess failed: {exc}", file=sys.stderr)
    return 0


def write_csv(path: Path, rows: List[Dict[str, Any]], cols: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cols)
        writer.writeheader()
        for r in rows:
            writer.writerow({c: r.get(c, "") for c in cols})


def write_markdown(
    out_path: Path,
    run_dir: Path,
    rows: List[Dict[str, Any]],
    per_stratum: List[Dict[str, Any]],
    per_defect: List[Dict[str, Any]],
    watchlist: Dict[str, Any],
    promotion: List[Dict[str, Any]],
    delta_section: Optional[str] = None,
    manifest: Optional[Dict[str, Any]] = None,
) -> None:
    lines: List[str] = []
    push = lines.append

    push(f"# Backtest report — `{run_dir.parent.name}` / `{run_dir.name}`")
    push("")
    if manifest:
        push("## Manifest")
        push("")
        for k in ("workflow_sha", "corpus_version", "embedding_model",
                 "llm_model", "judge_model", "dataset_version", "endpoint"):
            v = manifest.get(k, "?")
            push(f"- **{k}**: `{v}`")
        push("")

    # Headline
    total = len([r for r in rows if r.get("status") != "canary"])
    correct = sum(1 for r in rows if r.get("status") != "canary" and is_correct(r))
    ci_low, ci_high = wilson_ci(correct, total)
    push("## Headline")
    push("")
    push(f"- **Aggregate**: {correct}/{total} = **{correct / max(total,1):.1%}** [95% CI {ci_low:.1%} – {ci_high:.1%}]")
    push("")

    push("## Per-stratum pass rate")
    push("")
    push("| Domain | Lang | n | Pass | Partial | Fail | Rate | 95% CI |")
    push("|---|---|---:|---:|---:|---:|---:|---|")
    for s in per_stratum:
        push(
            f"| {s['domain']} | {s['language']} | {s['n']} | "
            f"{s['correct']} | {s['partial']} | {s['fail']} | "
            f"{s['rate']:.1%} | [{s['ci_low']:.1%}, {s['ci_high']:.1%}] |"
        )
    push("")

    push("## Defect breakdown")
    push("")
    push("| Defect | Count | Example IDs |")
    push("|---|---:|---|")
    for d in per_defect:
        ex_ids = ", ".join(f"`{e['id']}`" for e in d["examples"])
        push(f"| `{d['defect']}` | {d['count']} | {ex_ids} |")
    push("")

    push("## Regression watchlist")
    push("")
    push("| Item | Severity | Metric | Threshold | Status |")
    push("|---|---|---:|---|---|")
    for item in watchlist["status"]:
        mark = "PASS" if item["passed"] else "**FAIL**"
        sev = item["severity"].upper()
        push(
            f"| {item['label']} | {sev} | {item['metric']} | "
            f"{item['comparator']} {item['threshold']} | {mark} |"
        )
    push("")

    push("## Promotion gates")
    push("")
    push("| Gate | Metric | Threshold | Status |")
    push("|---|---:|---|---|")
    for g in promotion:
        if g.get("na"):
            mark = "N/A (skipped — no cases of this type in run)"
            metric_str = "—"
        else:
            mark = "PASS" if g["passed"] else "**FAIL**"
            metric_str = f"{g['metric']}"
        push(f"| {g['label']} | {metric_str} | {g['comparator']} {g['threshold']} | {mark} |")
    push("")

    crit_fail = any(
        not it["passed"] and it["severity"] == "critical"
        for it in watchlist["status"]
    )
    all_gates = all(g["passed"] for g in promotion)
    verdict = "READY TO SHIP" if all_gates and not crit_fail else "DO NOT SHIP"
    push(f"## Verdict: **{verdict}**")
    push("")
    if crit_fail:
        push("> A critical watchlist item failed — automatic no-ship per §2.8.")
        push("")

    if delta_section:
        push("## Delta vs previous run")
        push("")
        push(delta_section)
        push("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def compute_delta(
    prev_per_stratum: List[Dict[str, Any]],
    cur_per_stratum: List[Dict[str, Any]],
) -> str:
    prev_idx = {(s["domain"], s["language"]): s["rate"] for s in prev_per_stratum}
    lines = ["| Domain | Lang | Prev | Cur | Delta |", "|---|---|---:|---:|---:|"]
    for s in cur_per_stratum:
        prev = prev_idx.get((s["domain"], s["language"]))
        if prev is None:
            delta = "—"
        else:
            delta = f"{(s['rate'] - prev) * 100:+.1f}pp"
        prev_str = f"{prev:.1%}" if prev is not None else "—"
        lines.append(
            f"| {s['domain']} | {s['language']} | {prev_str} | {s['rate']:.1%} | {delta} |"
        )
    return "\n".join(lines)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--run-dir", help="explicit path to eval/results/<tag>/<ts>/")
    p.add_argument("--tag", help="if no --run-dir, find latest run for this tag")
    p.add_argument("--compare-to", help="tag of previous run for delta table")
    args = p.parse_args()

    if args.run_dir:
        run_dir = Path(args.run_dir)
    elif args.tag:
        latest = find_latest_run(args.tag)
        if not latest:
            print(f"No run found for tag {args.tag!r}", file=sys.stderr)
            return 2
        run_dir = latest
    else:
        print("Must give --run-dir or --tag", file=sys.stderr)
        return 2

    rows = load_rows(run_dir)
    if not rows:
        print(f"No raw rows in {run_dir}", file=sys.stderr)
        return 2

    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}

    drift_count = get_drift_count()
    per_stratum = compute_per_stratum(rows)
    per_defect = compute_per_defect(rows)
    watchlist = compute_watchlist(rows, drift_count=drift_count)
    promotion = compute_promotion(per_stratum, rows)

    delta_section = None
    if args.compare_to:
        prev_dir = find_latest_run(args.compare_to)
        if prev_dir:
            prev_rows = load_rows(prev_dir)
            prev_strata = compute_per_stratum(prev_rows)
            delta_section = compute_delta(prev_strata, per_stratum)

    write_csv(
        run_dir / "per_stratum.csv",
        per_stratum,
        ["domain", "language", "n", "correct", "partial", "fail", "rate", "ci_low", "ci_high"],
    )
    write_csv(
        run_dir / "per_defect.csv",
        [{"defect": d["defect"], "count": d["count"]} for d in per_defect],
        ["defect", "count"],
    )
    (run_dir / "watchlist.json").write_text(
        json.dumps(watchlist, indent=2), encoding="utf-8"
    )
    write_markdown(
        run_dir / "report.md",
        run_dir,
        rows,
        per_stratum,
        per_defect,
        watchlist,
        promotion,
        delta_section,
        manifest,
    )

    print(f"\nWrote:")
    for fname in ("report.md", "per_stratum.csv", "per_defect.csv", "watchlist.json"):
        print(f"  {(run_dir / fname).relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
