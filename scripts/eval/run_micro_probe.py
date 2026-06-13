"""Single-stack micro-probe: pick env, recreate container, run a small backtest.

Used to confirm causal attribution from the regression dig: each probe is a
Stack-ON-minus-one-component variant. Reuses the same hardened plumbing as
run_dual_backtest.py (env injection, container env verification, encoding-
safe subprocess captures) but only runs ONE stack and supports --sample-N
so each probe finishes in ~30 min instead of 5h.

Usage:
    python scripts/eval/run_micro_probe.py \\
        --tag probe_no_reranker \\
        --env RERANKER_BACKEND=none \\
        [--env ANOTHER=value …] \\
        [--sample-iteration 80] \\
        [--base-stack on|off]

Starts from STACK_ON_ENV (or STACK_OFF_ENV with --base-stack off), applies
the --env overrides on top, runs the canary gate, then the (sampled)
backtest, then a report. Restores .env on exit. Output: eval/results/{tag}/{ts}/.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "eval"))

# Reuse the dual-backtest plumbing.
from run_dual_backtest import (  # noqa: E402
    STACK_OFF_ENV, STACK_ON_ENV,
    log, patch_env_file, restore_env_file,
    recreate_hotel_api, wait_for_healthz, verify_container_env,
    put_llm_settings, warm_ollama_model,
    check_openrouter_balance, run_canaries, run_report,
    _force_utf8_stdout,
)
import os
import subprocess
import re
from datetime import datetime, timezone


def run_sampled_backtest(tag: str, sample_n: int | None, endpoint: str = "http://localhost:8088") -> Path:
    from run_dual_backtest import load_dotenv_vars
    env = os.environ.copy()
    env.update(load_dotenv_vars())
    env["PYTHONIOENCODING"] = "utf-8"
    args = [
        sys.executable,
        str(ROOT / "scripts" / "eval" / "backtest_runner.py"),
        "--tag", tag,
        "--endpoint", endpoint,
        "--no-canaries",
        "--abort-canary-failures", "16",
        "--no-chat-cache",
        # CRITICAL: backtest_runner defaults max_parallel=2 for localhost, but
        # the container has OLLAMA_NUM_PARALLEL=1 (Q8 needs serial inference)
        # AND MAX_CONCURRENT_LLM_CALLS=1 (FastAPI semaphore). Sending 2
        # concurrent /chat requests queues the second one for 45s, hitting
        # LLM_QUEUE_TIMEOUT_SEC and returning HTTP 503 -> empty_response.
        # Original dual backtest 2026-06-12 had 6.8% / 10% of cases failing
        # this way. Forcing parallel=1 eliminates the artifact.
        "--max-chat-parallel", "1",
    ]
    if sample_n:
        args += ["--sample-iteration", str(sample_n), "--sample-seed", "42"]
    log(f"  full backtest (tag={tag}, sample_n={sample_n or 'all'})…")
    p = subprocess.run(args, cwd=str(ROOT), check=False, timeout=8 * 3600, env=env)
    if p.returncode != 0:
        log(f"  WARN: backtest_runner.py exit={p.returncode}")
    tag_dir = ROOT / "eval" / "results" / tag
    candidates = sorted([d for d in tag_dir.glob("*") if d.is_dir()], reverse=True)
    if not candidates:
        raise RuntimeError(f"no run dir found under {tag_dir}")
    return candidates[0]


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--tag", required=True)
    ap.add_argument("--env", action="append", default=[],
                    help="VAR=value override, repeatable")
    ap.add_argument("--sample-iteration", type=int, default=80,
                    help="0 or omit for full 502-case run")
    ap.add_argument("--base-stack", choices=["on", "off"], default="on")
    ap.add_argument("--skip-canary", action="store_true")
    ap.add_argument("--endpoint", default="http://localhost:8088")
    args = ap.parse_args()

    base = STACK_ON_ENV if args.base_stack == "on" else STACK_OFF_ENV
    stack_env = dict(base)
    for raw in args.env:
        if "=" not in raw:
            print(f"bad --env (must be VAR=value): {raw!r}", file=sys.stderr)
            return 2
        k, v = raw.split("=", 1)
        stack_env[k.strip()] = v.strip()

    log(f"=== MICRO PROBE '{args.tag}' begin ===")
    log("  effective stack env:")
    for k, v in stack_env.items():
        log(f"    {k}={v}")

    check_openrouter_balance(min_balance=1.00)

    try:
        patch_env_file(stack_env)
        recreate_hotel_api(stack_env)
        wait_for_healthz()
        expected = {k: v for k, v in stack_env.items() if k != "OLLAMA_MODEL"}
        verify_container_env(expected)
        put_llm_settings("gemma4:12b-it-q8_0")
        warm_ollama_model("gemma4:12b-it-q8_0")
        check_openrouter_balance(min_balance=0.50)
        if not args.skip_canary:
            run_canaries(endpoint=args.endpoint, max_failures=2)
        run_dir = run_sampled_backtest(args.tag, args.sample_iteration, endpoint=args.endpoint)
        run_report(run_dir)
        bal = check_openrouter_balance(min_balance=0.0)
        log(f"=== MICRO PROBE '{args.tag}' done. run_dir={run_dir} balance=${bal:.4f} ===")
    finally:
        restore_env_file()
        log("restored .env (stripped managed block)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("interrupted")
        sys.exit(130)
