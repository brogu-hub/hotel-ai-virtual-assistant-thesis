"""Phase F variance baseline harness.

Runs the iter3-equivalent backtest config N times (default 5) with a pinned
stratified-sample seed so the SAME 96 cases are evaluated every time. The
chatbot is stochastic (temperature 0.3, top_p 0.8); the judge is deterministic
(temperature 0.0). Therefore run-to-run delta in pass rate quantifies *chatbot*
variance — exactly what we need to decide whether the ~5pp gaps observed
between iter1b / iter1c / tier1c and iter3 are real effects or sampling noise.

Outputs:
  eval/results/<tag>/variance_report.md   headline + per-run + per-defect tables
  eval/results/<tag>-run-{i}/<ts>/raw.jsonl   one per child run (via backtest_runner)

Resume: if eval/results/<tag>-run-{i}/<ts>/raw.jsonl already has 96 rows, that
run is reused as-is and no /chat or judge calls are made for it.

Usage:
    python scripts/eval/backtest_variance.py --tag variance --runs 5

Designed for overnight unattended execution (~2h wallclock for 5 runs).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean, pstdev, stdev
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from eval import backtest_runner  # noqa: E402
from eval.backtest_common import load_jsonl  # noqa: E402

RESULTS_DIR = ROOT / "eval" / "results"
EXPECTED_ROWS = 96  # iter3 / gemma4 sample size at --sample-iteration 100 stratified

# t critical values (two-tailed, alpha=0.05) for small df. df = N - 1.
# For df >= 30 we fall back to z=1.96.
_T_CRIT_95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571,
    6: 2.447, 7: 2.365, 8: 2.306, 9: 2.262, 10: 2.228,
    11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060,
    26: 2.056, 27: 2.052, 28: 2.048, 29: 2.045,
}


def _t_critical_95(df: int) -> float:
    if df <= 0:
        return float("nan")
    if df >= 30:
        return 1.96
    return _T_CRIT_95.get(df, 1.96)


def _find_complete_run(tag: str) -> Optional[Path]:
    """Return the newest ts-dir under eval/results/<tag> whose raw.jsonl has
    >= EXPECTED_ROWS rows. None if no such dir.
    """
    base = RESULTS_DIR / tag
    if not base.exists():
        return None
    candidates = sorted(
        [p for p in base.iterdir() if p.is_dir()],
        key=lambda p: p.name,
        reverse=True,
    )
    for ts_dir in candidates:
        raw = ts_dir / "raw.jsonl"
        if not raw.exists():
            continue
        try:
            n = sum(1 for _ in raw.open("r", encoding="utf-8"))
        except OSError:
            continue
        if n >= EXPECTED_ROWS:
            return ts_dir
    return None


def _invoke_runner(
    *,
    child_tag: str,
    judge_model: str,
    chat_timeout: float,
    sample_iteration: int,
    sample_seed: int,
    endpoint: str,
) -> int:
    """Call backtest_runner.main() in-process by rewriting sys.argv.

    Returns the runner's exit code. We do NOT pass --max-chat-parallel because
    the current backtest_runner is single-threaded; the harness arg is reserved
    for future runner versions and logged into the manifest only.
    """
    saved = sys.argv[:]
    try:
        sys.argv = [
            "backtest_runner.py",
            "--tag", child_tag,
            "--judge-model", judge_model,
            "--chat-timeout", str(chat_timeout),
            "--sample-iteration", str(sample_iteration),
            "--sample-seed", str(sample_seed),
            "--endpoint", endpoint,
        ]
        return int(backtest_runner.main() or 0)
    finally:
        sys.argv = saved


def _load_run_rows(ts_dir: Path) -> List[Dict[str, Any]]:
    return list(load_jsonl(ts_dir / "raw.jsonl"))


def _strict_pass_rate(rows: List[Dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    correct = sum(1 for r in rows if r.get("verdict") == "correct")
    return correct / len(rows)


def _weighted_pass_rate(rows: List[Dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    score = 0.0
    for r in rows:
        v = r.get("verdict")
        if v == "correct":
            score += 1.0
        elif v == "partial":
            score += 0.5
    return score / len(rows)


def _defect_counts(rows: List[Dict[str, Any]]) -> Counter:
    c: Counter = Counter()
    for r in rows:
        for d in (r.get("defects") or []):
            c[d] += 1
    return c


def _summarise(values: List[float]) -> Dict[str, float]:
    """Mean, sample stddev (n-1), 95% CI half-width of the mean.

    Uses t-distribution critical value for small N; falls back to z=1.96 for
    N>=30. Returns NaN-safe values when N<2.
    """
    n = len(values)
    if n == 0:
        return {"n": 0, "mean": 0.0, "stddev": 0.0, "ci95_halfwidth": 0.0,
                "ci95_low": 0.0, "ci95_high": 0.0}
    m = mean(values)
    if n < 2:
        return {"n": n, "mean": m, "stddev": 0.0, "ci95_halfwidth": 0.0,
                "ci95_low": m, "ci95_high": m}
    s = stdev(values)
    tc = _t_critical_95(n - 1)
    half = tc * s / math.sqrt(n)
    return {
        "n": n,
        "mean": m,
        "stddev": s,
        "ci95_halfwidth": half,
        "ci95_low": max(0.0, m - half),
        "ci95_high": min(1.0, m + half),
    }


def _fmt_pct(x: float) -> str:
    return f"{x * 100:.2f}%"


def _fmt_pp(x: float) -> str:
    return f"{x * 100:.2f} pp"


def _write_report(
    *,
    report_path: Path,
    args: argparse.Namespace,
    per_run: List[Dict[str, Any]],
    strict_summary: Dict[str, float],
    weighted_summary: Dict[str, float],
    defect_summary: Dict[str, Dict[str, float]],
) -> None:
    lines: List[str] = []
    lines.append(f"# Phase F variance baseline — `{args.tag}`")
    lines.append("")
    lines.append(f"_Generated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"- Runs            : **{args.runs}**")
    lines.append(f"- Sample size     : `--sample-iteration {args.sample_iteration}` (pinned seed `{args.sample_seed}`)")
    lines.append(f"- Judge model     : `{args.judge_model}`")
    lines.append(f"- Chat timeout    : {args.chat_timeout}s")
    lines.append(f"- Max chat parallel: {args.max_chat_parallel} (recorded only; backtest_runner is single-threaded)")
    lines.append(f"- Endpoint        : `{args.endpoint}`")
    lines.append("")
    lines.append("Same stratified sample is replayed for every run; the only source of")
    lines.append("variance is chatbot stochasticity (temperature 0.3, top_p 0.8). The judge")
    lines.append("is held at temperature 0.0.")
    lines.append("")
    lines.append("## Headline")
    lines.append("")
    lines.append("| Metric | Mean | StdDev | 95% CI |")
    lines.append("|---|---|---|---|")
    lines.append(
        f"| Strict pass rate | {_fmt_pct(strict_summary['mean'])} "
        f"| {_fmt_pp(strict_summary['stddev'])} "
        f"| [{_fmt_pct(strict_summary['ci95_low'])}, {_fmt_pct(strict_summary['ci95_high'])}] |"
    )
    lines.append(
        f"| Weighted pass rate (partial=0.5) | {_fmt_pct(weighted_summary['mean'])} "
        f"| {_fmt_pp(weighted_summary['stddev'])} "
        f"| [{_fmt_pct(weighted_summary['ci95_low'])}, {_fmt_pct(weighted_summary['ci95_high'])}] |"
    )
    lines.append("")
    sd_pp = strict_summary["stddev"] * 100
    lines.append("### Interpretation")
    lines.append("")
    lines.append(f"- Observed strict-pass stddev across {strict_summary['n']} runs: **{sd_pp:.2f} pp**.")
    lines.append("- Rule of thumb: an observed delta between two configs must exceed")
    lines.append("  ~2 sigma (~{:.1f} pp) before it is unlikely to be noise.".format(2 * sd_pp))
    lines.append("- The ~5 pp gap between iter1b / iter1c / tier1c and iter3 should be")
    lines.append("  compared against this baseline before any causal claim is made.")
    lines.append("")
    lines.append("## Per-run results")
    lines.append("")
    lines.append("| Run | Source | Rows | Strict pass | Weighted pass |")
    lines.append("|---|---|---|---|---|")
    for r in per_run:
        lines.append(
            f"| {r['run_index']} | `{r['source']}` | {r['n_rows']} "
            f"| {_fmt_pct(r['strict_pass'])} | {_fmt_pct(r['weighted_pass'])} |"
        )
    lines.append("")
    lines.append("## Per-defect category — mean and stddev (counts per run)")
    lines.append("")
    lines.append("| Defect | Mean / run | StdDev | Min | Max |")
    lines.append("|---|---|---|---|---|")
    for label in sorted(defect_summary.keys()):
        s = defect_summary[label]
        lines.append(
            f"| {label} | {s['mean']:.2f} | {s['stddev']:.2f} | {int(s['min'])} | {int(s['max'])} |"
        )
    if not defect_summary:
        lines.append("| (no defects observed in any run) | - | - | - | - |")
    lines.append("")
    lines.append("## Source runs")
    lines.append("")
    for r in per_run:
        lines.append(f"- run {r['run_index']}: `{r['source']}` ({r['n_rows']} rows)")
    lines.append("")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--tag", default="variance",
                   help="label for the aggregate report dir (default: variance)")
    p.add_argument("--runs", type=int, default=5,
                   help="number of repeated runs (default: 5)")
    p.add_argument("--sample-iteration", type=int, default=100,
                   help="stratified sample size per run; pinned seed makes all runs use the same cases (default: 100)")
    p.add_argument("--sample-seed", type=int, default=42,
                   help="stratified sample RNG seed; identical across runs (default: 42)")
    p.add_argument("--judge-model", default=os.getenv("JUDGE_MODEL", "deepseek/deepseek-chat-v3.1"))
    p.add_argument("--chat-timeout", type=float, default=180.0)
    p.add_argument("--max-chat-parallel", type=int, default=1,
                   help="reserved; current backtest_runner is single-threaded")
    p.add_argument("--endpoint", default="http://localhost:8088")
    args = p.parse_args()

    if not os.getenv("OPENROUTER_API_KEY"):
        print("ERROR: OPENROUTER_API_KEY not set. source .env first.", file=sys.stderr)
        return 2

    if args.runs < 1:
        print("ERROR: --runs must be >= 1", file=sys.stderr)
        return 2

    print(f"\n=== Phase F variance baseline ===")
    print(f"  aggregate tag : {args.tag}")
    print(f"  runs          : {args.runs}")
    print(f"  sample        : {args.sample_iteration} cases, seed={args.sample_seed} (pinned)")
    print(f"  judge         : {args.judge_model}")
    print(f"  chat timeout  : {args.chat_timeout}s")
    print(f"  endpoint      : {args.endpoint}")
    print()

    per_run: List[Dict[str, Any]] = []
    defect_per_run: List[Counter] = []

    for i in range(1, args.runs + 1):
        child_tag = f"{args.tag}-run-{i}"
        existing = _find_complete_run(child_tag)
        if existing is not None:
            print(f"  [skip] run {i}: reusing existing complete run at {existing.relative_to(ROOT).as_posix()}")
            source = existing
        else:
            print(f"  [run ] run {i}/{args.runs}: invoking backtest_runner (tag={child_tag})")
            rc = _invoke_runner(
                child_tag=child_tag,
                judge_model=args.judge_model,
                chat_timeout=args.chat_timeout,
                sample_iteration=args.sample_iteration,
                sample_seed=args.sample_seed,
                endpoint=args.endpoint,
            )
            if rc != 0:
                print(f"    ! run {i} returned non-zero exit code {rc}; continuing", file=sys.stderr)
            source = _find_complete_run(child_tag)
            if source is None:
                # accept whatever the runner wrote even if short of EXPECTED_ROWS
                base = RESULTS_DIR / child_tag
                if base.exists():
                    ts_dirs = sorted([p for p in base.iterdir() if p.is_dir()], reverse=True)
                    source = ts_dirs[0] if ts_dirs else None
            if source is None:
                print(f"    ! no raw.jsonl produced for run {i}; skipping aggregation", file=sys.stderr)
                continue

        rows = _load_run_rows(source)
        strict = _strict_pass_rate(rows)
        weighted = _weighted_pass_rate(rows)
        defects = _defect_counts(rows)
        per_run.append({
            "run_index": i,
            "source": source.relative_to(ROOT).as_posix(),
            "n_rows": len(rows),
            "strict_pass": strict,
            "weighted_pass": weighted,
            "defects": dict(defects),
        })
        defect_per_run.append(defects)
        print(f"    -> n={len(rows)} strict={_fmt_pct(strict)} weighted={_fmt_pct(weighted)}")

    if not per_run:
        print("ERROR: no runs produced usable raw.jsonl files", file=sys.stderr)
        return 2

    strict_vals = [r["strict_pass"] for r in per_run]
    weighted_vals = [r["weighted_pass"] for r in per_run]
    strict_summary = _summarise(strict_vals)
    weighted_summary = _summarise(weighted_vals)

    # Per-defect aggregation across runs
    defect_labels = set()
    for d in defect_per_run:
        defect_labels.update(d.keys())
    defect_summary: Dict[str, Dict[str, float]] = {}
    for label in defect_labels:
        counts = [float(d.get(label, 0)) for d in defect_per_run]
        n = len(counts)
        m = mean(counts) if counts else 0.0
        sd = stdev(counts) if n >= 2 else 0.0
        defect_summary[label] = {
            "mean": m,
            "stddev": sd,
            "min": min(counts) if counts else 0.0,
            "max": max(counts) if counts else 0.0,
        }

    out_dir = RESULTS_DIR / args.tag
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "variance_report.md"

    # Persist the raw aggregate JSON alongside the markdown so the thesis
    # can cite exact numbers without re-parsing the report.
    aggregate = {
        "tag": args.tag,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "config": {
            "runs": args.runs,
            "sample_iteration": args.sample_iteration,
            "sample_seed": args.sample_seed,
            "judge_model": args.judge_model,
            "chat_timeout": args.chat_timeout,
            "max_chat_parallel": args.max_chat_parallel,
            "endpoint": args.endpoint,
        },
        "per_run": per_run,
        "strict_pass_rate": strict_summary,
        "weighted_pass_rate": weighted_summary,
        "per_defect": defect_summary,
    }
    (out_dir / "variance_aggregate.json").write_text(
        json.dumps(aggregate, indent=2, ensure_ascii=False), encoding="utf-8",
    )

    _write_report(
        report_path=report_path,
        args=args,
        per_run=per_run,
        strict_summary=strict_summary,
        weighted_summary=weighted_summary,
        defect_summary=defect_summary,
    )

    print()
    print(f"=== variance summary ===")
    print(f"  strict pass mean    : {_fmt_pct(strict_summary['mean'])}")
    print(f"  strict pass stddev  : {_fmt_pp(strict_summary['stddev'])}")
    print(f"  strict pass 95% CI  : [{_fmt_pct(strict_summary['ci95_low'])}, {_fmt_pct(strict_summary['ci95_high'])}]")
    print(f"  weighted pass mean  : {_fmt_pct(weighted_summary['mean'])}")
    print(f"  weighted pass stddev: {_fmt_pp(weighted_summary['stddev'])}")
    print(f"  report              : {report_path.relative_to(ROOT).as_posix()}")
    print(f"  aggregate JSON      : {(out_dir / 'variance_aggregate.json').relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
