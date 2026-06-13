"""Triple full-dataset backtest with the queue artifact fix applied.

Three runs in sequence so the AP_D / CH6 §6.5 narrative has confound-
isolated, queue-artifact-free numbers:

  1. clean_stackoff       — STACK_OFF_ENV unchanged (baseline)
  2. clean_stackon        — STACK_ON_ENV unchanged (Phase G+H stack with overrides)
  3. clean_stackon_light  — STACK_ON minus model_overrides (production candidate)

Each run uses the full 502-case dataset (no --sample-iteration), forces
--no-chat-cache, and inherits the run_micro_probe defaults
(--max-chat-parallel=1 which is the fix that produced this rerun).

Wall-clock estimate: 502 × ~50s/case = ~7h per run, ~21h total. Cost
estimate: ~$0.35 judge per run × 3 = ~$1.05 OpenRouter spend.

Logs stream to eval/results/_dual_backtest_logs/triple_<ts>.log. After
all three finish, build_apd_table.py is invoked to refresh
thesis/AP_D_Per_Case_QA.md with the clean three-column comparison
(Col A = Qwen 9B baseline, Col B = clean_stackoff, Col C = clean_stackon_light).
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "eval"))

from run_dual_backtest import _force_utf8_stdout, log  # noqa: E402

PROBE_PY = ROOT / "scripts" / "eval" / "run_micro_probe.py"
LOG_DIR = ROOT / "eval" / "results" / "_dual_backtest_logs"

CONFIGS = [
    {
        "tag": "clean_stackoff",
        "base_stack": "off",
        "env_overrides": [],
        "rationale": "baseline (no Phase G/H), parallel=1 (no queue artifact)",
    },
    {
        "tag": "clean_stackon",
        "base_stack": "on",
        "env_overrides": [],
        "rationale": "full Phase G+H stack including gemma model_overrides, parallel=1",
    },
    {
        "tag": "clean_stackon_light",
        "base_stack": "on",
        "env_overrides": [
            "HOTEL_PROMPT_PATH=/app/src/agent/hotel_prompt_stackoff.yaml",
        ],
        "rationale": "Phase G+H stack MINUS gemma model_overrides (production candidate)",
    },
]


def run_one(cfg: dict) -> Path | None:
    log(f"=== TRIPLE: starting '{cfg['tag']}' ({cfg['rationale']}) ===")
    cmd = [
        sys.executable, "-u", str(PROBE_PY),
        "--tag", cfg["tag"],
        "--base-stack", cfg["base_stack"],
        "--sample-iteration", "0",  # full dataset
    ]
    for ov in cfg["env_overrides"]:
        cmd += ["--env", ov]

    # Critical for Windows + Git Bash: defeat MSYS path-conversion so
    # --env HOTEL_PROMPT_PATH=/app/... doesn't become C:/Program Files/Git/app/...
    env = os.environ.copy()
    env["MSYS2_ARG_CONV_EXCL"] = "*"
    env["PYTHONIOENCODING"] = "utf-8"

    started = time.time()
    p = subprocess.run(cmd, cwd=str(ROOT), env=env, check=False)
    dur = time.time() - started
    log(f"=== TRIPLE: '{cfg['tag']}' done (exit={p.returncode}, dur={dur/60:.1f} min) ===")
    if p.returncode != 0:
        log(f"  WARN: non-zero exit; raw.jsonl is still preserved at run dir")

    tag_dir = ROOT / "eval" / "results" / cfg["tag"]
    if not tag_dir.exists():
        return None
    runs = sorted([d for d in tag_dir.iterdir() if d.is_dir()], reverse=True)
    return runs[0] if runs else None


def build_apd(off_dir: Path, light_dir: Path) -> None:
    qwen_baseline = ROOT / "eval" / "results" / "final-postfix" / "20260609T205731"
    out = ROOT / "thesis" / "AP_D_Per_Case_QA.md"
    cmd = [
        sys.executable, str(ROOT / "scripts" / "eval" / "build_apd_table.py"),
        "--run-a", str(qwen_baseline),
        "--run-b", str(off_dir),
        "--run-c", str(light_dir),
        "--out", str(out),
    ]
    log(f"=== TRIPLE: building AP_D ===")
    log(f"  $ {' '.join(cmd)}")
    p = subprocess.run(
        cmd, cwd=str(ROOT), check=False,
        encoding="utf-8", errors="replace",
    )
    log(f"=== TRIPLE: AP_D done (exit={p.returncode}) ===")


def main() -> int:
    _force_utf8_stdout()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    start = datetime.now(timezone.utc)
    log(f"=== TRIPLE CLEAN BACKTEST START {start.isoformat(timespec='seconds')} ===")
    log(f"  est wall: ~21 hours, est cost: ~$1.05 OpenRouter")

    run_dirs: dict[str, Path | None] = {}
    for cfg in CONFIGS:
        run_dirs[cfg["tag"]] = run_one(cfg)

    log(f"=== TRIPLE: summary ===")
    for tag, rd in run_dirs.items():
        log(f"  {tag}: {rd}")

    if run_dirs.get("clean_stackoff") and run_dirs.get("clean_stackon_light"):
        build_apd(run_dirs["clean_stackoff"], run_dirs["clean_stackon_light"])

    end = datetime.now(timezone.utc)
    dur = (end - start).total_seconds() / 3600
    log(f"=== TRIPLE CLEAN BACKTEST DONE  {end.isoformat(timespec='seconds')}  total_dur={dur:.1f}h ===")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("triple backtest interrupted")
        sys.exit(130)
