"""Watch clean_stackoff Run #1; when it hits 502 cases, kill the triple
driver tree and stop hotel-ollama to free GPU for gaming.

Polls every 30s. Logs to stdout (the nohup-redirected log).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN_DIR_GLOB = ROOT / "eval" / "results" / "clean_stackoff"
LOG_DIR = ROOT / "eval" / "results" / "_dual_backtest_logs"
TARGET = 502
POLL_S = 30


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def latest_raw() -> Path | None:
    dirs = sorted([d for d in RUN_DIR_GLOB.glob("20260614*") if d.is_dir()])
    if not dirs:
        return None
    raw = dirs[-1] / "raw.jsonl"
    return raw if raw.exists() else None


def case_count(raw: Path) -> int:
    return sum(1 for line in raw.open(encoding="utf-8") if line.strip())


def kill_triple_chain() -> None:
    log("looking up triple driver process tree…")
    # Find all python processes in the run_triple / run_micro_probe / backtest_runner chain
    out = subprocess.run(
        ["wmic.exe", "process", "where", "name='python.exe'", "get", "processid,commandline"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    ).stdout
    pids_to_kill = []
    for line in out.splitlines():
        if any(needle in line for needle in (
            "run_triple_clean", "run_micro_probe", "backtest_runner",
        )):
            tokens = line.strip().split()
            for tok in reversed(tokens):
                if tok.isdigit():
                    pids_to_kill.append(tok)
                    break
    log(f"killing PIDs: {pids_to_kill}")
    for pid in pids_to_kill:
        subprocess.run(
            ["taskkill.exe", "/PID", pid, "/T", "/F"],
            capture_output=True, text=True,
        )
    log("triple chain killed")


def free_gpu() -> None:
    log("stopping hotel-ollama container to free GPU…")
    p = subprocess.run(
        ["docker", "stop", "hotel-ollama"],
        capture_output=True, text=True, timeout=60,
    )
    log(f"docker stop hotel-ollama: rc={p.returncode} stdout={p.stdout.strip()[:80]}")
    # Also stop hotel-api so it doesn't keep trying to reach Ollama
    p2 = subprocess.run(
        ["docker", "stop", "hotel-api"],
        capture_output=True, text=True, timeout=60,
    )
    log(f"docker stop hotel-api: rc={p2.returncode} stdout={p2.stdout.strip()[:80]}")


def restore_env() -> None:
    """Strip the RUN_DUAL_BACKTEST managed block from .env in case driver
    didn't clean up before being killed."""
    helper = ROOT / "scripts" / "eval" / "run_dual_backtest.py"
    subprocess.run(
        [sys.executable, str(helper), "--restore-env"],
        capture_output=True, text=True, timeout=30,
    )
    log(".env restored (managed block stripped if present)")


def main() -> int:
    log(f"watcher started, target={TARGET}, poll every {POLL_S}s")
    while True:
        raw = latest_raw()
        if raw is None:
            log("no raw.jsonl yet, waiting…")
            time.sleep(POLL_S)
            continue
        n = case_count(raw)
        if n >= TARGET:
            log(f"✓ clean_stackoff hit {n}/{TARGET} — pausing")
            time.sleep(15)  # let the runner finish writing report.md / manifest
            kill_triple_chain()
            restore_env()
            free_gpu()
            log("=== PAUSED. GPU freed. clean_stackon and clean_stackon_light NOT started. ===")
            log("    To resume: start Ollama + hotel-api + run clean_stackon + clean_stackon_light.")
            log(f"    Run #1 artifact: {raw.parent}")
            return 0
        log(f"  {n}/{TARGET} ({n/TARGET*100:.1f}%) — still going")
        time.sleep(POLL_S)


if __name__ == "__main__":
    sys.exit(main())
