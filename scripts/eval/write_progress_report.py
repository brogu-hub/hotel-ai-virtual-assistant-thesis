"""Snapshot dual-backtest progress into eval/results/_dual_backtest_logs/PROGRESS.md.

Designed to run on every 30-min monitoring tick. Writes a fresh PROGRESS.md
(overwrites) and appends a one-line snapshot to HISTORY.md so the user can
diff the trajectory.

Pulls from:
  - the live driver log (newest run_*.log)
  - eval/results/{stackoff,stackon}/<ts>/raw.jsonl (case-by-case progress)
  - OpenRouter balance via check_openrouter_balance.py
  - docker exec on hotel-api / hotel-ollama for live container state
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = ROOT / "eval" / "results" / "_dual_backtest_logs"
PROGRESS_MD = LOG_DIR / "PROGRESS.md"
HISTORY_MD = LOG_DIR / "HISTORY.md"

STACK_OFF_TAG = "gemma_q8_stackoff"
STACK_ON_TAG = "gemma_q8_stackon"
# Phase I triple — the new canonical runs after the queue-artifact fix
CLEAN_OFF_TAG = "clean_stackoff"
CLEAN_ON_TAG = "clean_stackon"
CLEAN_LIGHT_TAG = "clean_stackon_light"
TRIPLE_TAGS = (CLEAN_OFF_TAG, CLEAN_ON_TAG, CLEAN_LIGHT_TAG)


def sh(cmd: list[str], timeout: int = 15) -> str:
    try:
        p = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
        return (p.stdout or "") + (p.stderr or "")
    except Exception as e:
        return f"(error: {e})"


def latest_log() -> Path | None:
    cands = sorted(list(LOG_DIR.glob("run_*.log")) + list(LOG_DIR.glob("triple_*.log")) + list(LOG_DIR.glob("probe*.log")))
    return cands[-1] if cands else None


def driver_alive() -> tuple[bool, str | None]:
    """Check if the driver PID is still running.

    Git-Bash mangles `/FI` arg into a path, so we use the raw `tasklist`
    output without filtering and grep ourselves. Also fall back to a log
    freshness check (mtime in last 5 min) — if the log is being actively
    written, the driver is alive even if tasklist is being weird.
    """
    pid_file = LOG_DIR / ".current_pid"
    if not pid_file.exists():
        return False, None
    pid = pid_file.read_text(encoding="utf-8").strip()
    if not pid:
        return False, None
    out = sh(["tasklist.exe", "/NH"], timeout=12)
    # rows look like:  python.exe   12345 Console   1   123,456 K
    alive_by_tasklist = False
    for line in out.splitlines():
        if "python" in line.lower():
            parts = line.split()
            if len(parts) >= 2 and parts[1] == pid:
                alive_by_tasklist = True
                break
    if alive_by_tasklist:
        return True, pid
    log = latest_log()
    if log and log.exists():
        import time
        age = time.time() - log.stat().st_mtime
        if age < 300:
            return True, pid + " (by-log-mtime)"
    return False, pid


def latest_run_dir(tag: str) -> Path | None:
    tag_dir = ROOT / "eval" / "results" / tag
    if not tag_dir.exists():
        return None
    runs = sorted([p for p in tag_dir.iterdir() if p.is_dir()], reverse=True)
    return runs[0] if runs else None


def case_progress(run_dir: Path | None) -> dict:
    """Return counts and verdict distribution from raw.jsonl."""
    if not run_dir:
        return {"started": False}
    raw = run_dir / "raw.jsonl"
    if not raw.exists():
        return {"started": True, "raw_exists": False, "run_dir": str(run_dir)}
    n = 0
    verdicts: dict[str, int] = {}
    langs: dict[str, dict[str, int]] = {}
    last_id = None
    last_ts = None
    for line in raw.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        n += 1
        v = row.get("verdict", "unknown")
        verdicts[v] = verdicts.get(v, 0) + 1
        lang = row.get("language", "?")
        langs.setdefault(lang, {})
        langs[lang][v] = langs[lang].get(v, 0) + 1
        last_id = row.get("id", last_id)
        last_ts = row.get("timestamp", last_ts)
    return {
        "started": True,
        "raw_exists": True,
        "run_dir": str(run_dir),
        "n_complete": n,
        "verdicts": verdicts,
        "by_lang": langs,
        "last_id": last_id,
        "last_ts": last_ts,
    }


def balance() -> tuple[float, str]:
    out = sh([sys.executable, str(ROOT / "scripts" / "eval" / "check_openrouter_balance.py")])
    m = re.search(r"\$([0-9.]+)\s+available", out)
    bal = float(m.group(1)) if m else -1.0
    status = "OK"
    if bal < 0:
        status = "ERR"
    elif bal < 0.50:
        status = "CRIT"
    elif bal < 1.00:
        status = "LOW"
    return bal, status


def container_state() -> dict:
    env_out = sh(["docker", "exec", "hotel-api", "env"], timeout=10)
    env_map = {}
    for line in env_out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            env_map[k.strip()] = v.strip()
    keys = (
        "OLLAMA_MODEL",
        "HYBRID_RETRIEVAL",
        "RERANKER_BACKEND",
        "HOTEL_QUERY_REWRITE_ENABLED",
        "HOTEL_PROMPT_PATH",
        "HOTEL_RAG_NUM_DOCS_PER_SUBQ",
    )
    visible = {k: env_map.get(k, "<unset>") for k in keys}
    ps = sh(["docker", "exec", "hotel-ollama", "ollama", "ps"], timeout=10)
    return {"env": visible, "ollama_ps": ps.strip()}


def derive_phase(log_text: str) -> str:
    """Best-effort phase derivation from the latest driver log lines."""
    if not log_text:
        return "unknown (no log)"
    tail = log_text.splitlines()[-200:]
    joined = "\n".join(tail).lower()
    # Triple driver (Phase I — current canonical) — check this first
    if "=== triple clean backtest done" in joined:
        return "DONE"
    if "=== triple: building ap_d ===" in joined:
        return "AP_D generation"
    for label, tag in (
        ("Backtest #3 (Stack-ON-light)", "clean_stackon_light"),
        ("Backtest #2 (Stack-ON heavy)", "clean_stackon"),
        ("Backtest #1 (Stack-OFF clean)", "clean_stackoff"),
    ):
        begin = f"micro probe '{tag}' begin"
        done = f"micro probe '{tag}' done"
        if begin in joined and done not in joined:
            after_begin = joined.split(begin)[-1]
            if "full backtest" in after_begin:
                return f"{label} — backtest running"
            if "canary gate" in after_begin:
                return f"{label} — canary gate"
            return f"{label} — setup"
    # Fall through to legacy dual-backtest phase detection
    if "=== dual backtest complete ===" in joined:
        return "DONE (legacy dual)"
    if "building ap_d" in joined:
        return "AP_D generation"
    if "stack 'gemma_q8_stackon' begin" in joined and "stack 'gemma_q8_stackon' done" not in joined:
        if "canary gate" in joined.split("stack 'gemma_q8_stackon' begin")[-1]:
            return "Stack-ON canary gate"
        if "full backtest" in joined.split("stack 'gemma_q8_stackon' begin")[-1]:
            return "Stack-ON backtest running"
        return "Stack-ON setup"
    if "stack 'gemma_q8_stackoff' done" in joined:
        return "Between Stack-OFF and Stack-ON"
    if "stack 'gemma_q8_stackoff' begin" in joined:
        if "full backtest" in joined.split("stack 'gemma_q8_stackoff' begin")[-1]:
            return "Stack-OFF backtest running"
        if "canary gate" in joined.split("stack 'gemma_q8_stackoff' begin")[-1]:
            return "Stack-OFF canary gate"
        return "Stack-OFF setup"
    if "balance:" in joined:
        return "Driver starting"
    return "unknown"


def fmt_verdicts(v: dict) -> str:
    if not v:
        return "(none yet)"
    order = ["correct", "partial", "incorrect", "unknown"]
    parts = []
    for k in order:
        if k in v:
            parts.append(f"{k}={v[k]}")
    for k in v:
        if k not in order:
            parts.append(f"{k}={v[k]}")
    return " ".join(parts)


def main() -> int:
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    log_path = latest_log()
    log_text = log_path.read_text(encoding="utf-8", errors="replace") if log_path and log_path.exists() else ""
    alive, pid = driver_alive()
    phase = derive_phase(log_text)
    bal, bal_status = balance()
    cstate = container_state()
    # Triple (Phase I) is the current canonical; legacy dual remains for reference
    triple = {tag: case_progress(latest_run_dir(tag)) for tag in TRIPLE_TAGS}
    off = case_progress(latest_run_dir(STACK_OFF_TAG))
    on = case_progress(latest_run_dir(STACK_ON_TAG))

    last_log_lines = log_text.splitlines()[-12:] if log_text else []
    last_log_tail = "\n".join(last_log_lines)

    md = f"""# Dual Backtest — Live Progress

**Snapshot:** `{now_iso}` (UTC)

## Driver

| | |
|---|---|
| PID | `{pid or '(none)'}` |
| Alive | {'✅ running' if alive else '🔴 not running'} |
| Phase | **{phase}** |
| Log | `{log_path.relative_to(ROOT) if log_path else '(none)'}` |

## OpenRouter budget

- Balance: **${bal:.4f}** — status: **{bal_status}**
- Alerts: warn ≤ $1.00 · block ≤ $0.50 · hard-stop at $0

## Container state

| Var | Value |
|---|---|
""" + "\n".join(f"| `{k}` | `{v}` |" for k, v in cstate["env"].items()) + f"""

**Ollama loaded models:**

```
{cstate['ollama_ps'][:500]}
```

## Phase I clean triple (current canonical)

"""
    for label, tag in (
        ("Run #1 — clean Stack-OFF (baseline, no Phase G/H)", CLEAN_OFF_TAG),
        ("Run #2 — clean Stack-ON (Phase G+H WITH overrides)", CLEAN_ON_TAG),
        ("Run #3 — clean Stack-ON-light (Phase G+H minus overrides) — PRODUCTION CANDIDATE", CLEAN_LIGHT_TAG),
    ):
        md += f"### {label} (`{tag}`)\n\n"
        d = triple.get(tag, {})
        if not d.get("started"):
            md += "_Not started yet._\n\n"
            continue
        if not d.get("raw_exists"):
            md += f"_Run dir created (`{d.get('run_dir')}`), raw.jsonl not yet populated._\n\n"
            continue
        md += (
            f"- Run dir: `{Path(d['run_dir']).relative_to(ROOT)}`\n"
            f"- Cases complete: **{d['n_complete']}** / 502\n"
            f"- Verdicts: {fmt_verdicts(d['verdicts'])}\n"
            f"- Last id: `{d['last_id']}` @ `{d['last_ts']}`\n"
        )
        for lang, vd in sorted(d.get("by_lang", {}).items()):
            md += f"  - **{lang}**: {fmt_verdicts(vd)}\n"
        md += "\n"

    md += f"## Legacy 2026-06-12 dual (queue-contaminated, not used in thesis)\n\n"
    md += f"### Backtest #1 — Stack-OFF (`{STACK_OFF_TAG}`)\n\n"
    if not off.get("started"):
        md += "_Not started yet._\n"
    elif not off.get("raw_exists"):
        md += f"_Run dir created (`{off.get('run_dir')}`), raw.jsonl not yet populated._\n"
    else:
        md += (
            f"- Run dir: `{Path(off['run_dir']).relative_to(ROOT)}`\n"
            f"- Cases complete: **{off['n_complete']}** / 517 (golden 477 + canaries 15 + adv 6 + hard_neg 6 + multi-intent 10 + wifi_checkedin 3)\n"
            f"- Verdicts: {fmt_verdicts(off['verdicts'])}\n"
            f"- Last id: `{off['last_id']}` @ `{off['last_ts']}`\n"
        )
        for lang, vd in sorted(off.get("by_lang", {}).items()):
            md += f"  - **{lang}**: {fmt_verdicts(vd)}\n"

    md += f"\n### Backtest #2 — Stack-ON (`{STACK_ON_TAG}`)\n\n"
    if not on.get("started"):
        md += "_Not started yet._\n"
    elif not on.get("raw_exists"):
        md += f"_Run dir created (`{on.get('run_dir')}`), raw.jsonl not yet populated._\n"
    else:
        md += (
            f"- Run dir: `{Path(on['run_dir']).relative_to(ROOT)}`\n"
            f"- Cases complete: **{on['n_complete']}** / 517\n"
            f"- Verdicts: {fmt_verdicts(on['verdicts'])}\n"
            f"- Last id: `{on['last_id']}` @ `{on['last_ts']}`\n"
        )
        for lang, vd in sorted(on.get("by_lang", {}).items()):
            md += f"  - **{lang}**: {fmt_verdicts(vd)}\n"

    md += f"""
## Last driver log lines

```
{last_log_tail}
```

## How to read this

- Updated automatically at 30-min checkpoints.
- See `HISTORY.md` for the timeline of one-line snapshots across all ticks.
- Driver script: `scripts/eval/run_dual_backtest.py`. Logs stream to the path above.
- To inspect a specific run: `cat <run_dir>/manifest.json` and the streaming `raw.jsonl`.

_(Auto-generated by `scripts/eval/write_progress_report.py`)_
"""
    PROGRESS_MD.write_text(md, encoding="utf-8")

    # one-line history line
    n_off = off.get("n_complete", 0)
    n_on = on.get("n_complete", 0)
    n_clean_off = triple.get(CLEAN_OFF_TAG, {}).get("n_complete", 0)
    n_clean_on = triple.get(CLEAN_ON_TAG, {}).get("n_complete", 0)
    n_clean_light = triple.get(CLEAN_LIGHT_TAG, {}).get("n_complete", 0)
    history_line = (
        f"- `{now_iso}` — phase=`{phase}` "
        f"alive=`{alive}` "
        f"bal=`${bal:.4f}` "
        f"triple=`{n_clean_off}/{n_clean_on}/{n_clean_light}` "
        f"legacy=`{n_off}/{n_on}`\n"
    )
    if HISTORY_MD.exists():
        HISTORY_MD.write_text(HISTORY_MD.read_text(encoding="utf-8") + history_line, encoding="utf-8")
    else:
        HISTORY_MD.write_text(
            "# Dual Backtest — Progress History\n\n"
            "Append-only one-liner per checkpoint.\n\n"
            + history_line,
            encoding="utf-8",
        )
    print(f"wrote {PROGRESS_MD.relative_to(ROOT)} (phase={phase}, alive={alive}, triple={n_clean_off}/{n_clean_on}/{n_clean_light}, legacy={n_off}/{n_on})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
