"""Dual confound-isolated backtest driver: Gemma Q8 + Stack-OFF, then Stack-ON.

Designed for the AP_D per-case Q&A comparison in the thesis. Holds the model
constant at gemma4:12b-it-q8_0 and flips ONLY the augmentation stack between
runs so the delta is cleanly attributable to Phase G/H/H.A/H.B/H.C.

Stack-OFF env (Backtest #1):
    HYBRID_RETRIEVAL=false             # Phase H.B disabled
    RERANKER_BACKEND=none              # Phase H.C disabled
    HOTEL_QUERY_REWRITE_ENABLED=false  # Phase G/H.A disabled
    HOTEL_PROMPT_PATH=...stackoff.yaml # Phase G model_overrides disabled
    HOTEL_RAG_NUM_DOCS_PER_SUBQ=3      # pre-Phase-G default

Stack-ON env (Backtest #2):
    HYBRID_RETRIEVAL=true
    RERANKER_BACKEND=qwen
    HOTEL_QUERY_REWRITE_ENABLED=true
    HOTEL_PROMPT_PATH=  (default search list -> hotel_prompt.yaml)
    HOTEL_RAG_NUM_DOCS_PER_SUBQ=5

For each backtest the driver:
  1. Mutates the .env file in-place with the stack-specific block (line-bounded,
     not the whole file).
  2. Recreates hotel-api via `docker compose up -d --force-recreate` so the
     import-time env vars (HYBRID_RETRIEVAL, RERANKER_BACKEND) take effect.
  3. Polls /healthz until 200.
  4. PUTs /settings/llm to set gemma4:12b-it-q8_0 + thinking=True (runtime
     state resets on recreate).
  5. Warms Gemma into VRAM via `ollama run ... "hi"` (evicts whatever was loaded).
  6. Runs backtest_canaries.py — abort run if more than 1 canary fails.
  7. Runs the OpenRouter balance check; abort if < $0.50.
  8. Runs backtest_runner.py on the full 514-case set with the appropriate --tag.
  9. Runs backtest_report.py to render per-stratum tables.

After both runs complete:
  - Runs build_apd_table.py with both run dirs to populate AP_D.
  - Restores the original .env (so the host returns to whatever was set before).
  - Prints final summary with both tags + balance delta.

Wall-clock estimate: ~5-6 hours per backtest at gemma4:12b-it-q8_0 / Ollama
NUM_PARALLEL=1, so ~11-12 hours total. Run in background.

Resume: backtest_runner.py already skips cases already in raw.jsonl. If this
driver is interrupted mid-run, re-invoking it picks up where it left off
(per-stack); --force-fresh on the CLI overrides.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = ROOT / ".env"
COMPOSE_PATH = ROOT / "deploy" / "compose" / "docker-compose.hotel.yaml"

STACK_OFF_ENV = {
    "HYBRID_RETRIEVAL": "false",
    "RERANKER_BACKEND": "none",
    "HOTEL_QUERY_REWRITE_ENABLED": "false",
    "HOTEL_PROMPT_PATH": "/app/src/agent/hotel_prompt_stackoff.yaml",
    "HOTEL_RAG_NUM_DOCS_PER_SUBQ": "3",
    "OLLAMA_MODEL": "gemma4:12b-it-q8_0",
}

STACK_ON_ENV = {
    "HYBRID_RETRIEVAL": "true",
    "RERANKER_BACKEND": "qwen",
    "HOTEL_QUERY_REWRITE_ENABLED": "true",
    "HOTEL_PROMPT_PATH": "",
    "HOTEL_RAG_NUM_DOCS_PER_SUBQ": "5",
    "OLLAMA_MODEL": "gemma4:12b-it-q8_0",
}

STACK_MARKER_START = "# >>> RUN_DUAL_BACKTEST stack overrides BEGIN >>>"
STACK_MARKER_END = "# <<< RUN_DUAL_BACKTEST stack overrides END <<<"


def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] {msg}", flush=True)


def patch_env_file(stack_overrides: dict[str, str]) -> None:
    """Replace the stack-override block in .env with the given values."""
    if not ENV_PATH.exists():
        raise RuntimeError(f".env not found at {ENV_PATH}")
    body = ENV_PATH.read_text(encoding="utf-8")
    # Strip any prior managed block.
    pattern = re.compile(
        re.escape(STACK_MARKER_START) + r".*?" + re.escape(STACK_MARKER_END) + r"\n?",
        re.DOTALL,
    )
    body = pattern.sub("", body)
    if not body.endswith("\n"):
        body += "\n"
    body += f"\n{STACK_MARKER_START}\n"
    for k, v in stack_overrides.items():
        body += f"{k}={v}\n"
    body += f"{STACK_MARKER_END}\n"
    ENV_PATH.write_text(body, encoding="utf-8")


def restore_env_file() -> None:
    """Remove the managed block so .env returns to the pre-driver state."""
    if not ENV_PATH.exists():
        return
    body = ENV_PATH.read_text(encoding="utf-8")
    pattern = re.compile(
        r"\n?" + re.escape(STACK_MARKER_START) + r".*?" + re.escape(STACK_MARKER_END) + r"\n?",
        re.DOTALL,
    )
    body = pattern.sub("", body)
    ENV_PATH.write_text(body, encoding="utf-8")


def load_dotenv_vars() -> dict[str, str]:
    """Parse the repo-root .env into a dict.

    docker compose's variable interpolation precedence puts the shell env
    ABOVE the .env file. When we pass env= to subprocess.run, the subprocess
    inherits ONLY what we put in env — .env is no longer auto-read because
    cwd-based .env discovery is masked by the explicit env dict.

    So we must hydrate the subprocess env with .env contents OURSELVES,
    then layer stack overrides on top. Otherwise crucial vars like
    OPENROUTER_API_KEY fall through to the YAML default (`sk-dummy-not-used`)
    and embeddings 401 silently, returning empty RAG results and turning
    every chat into an over-refusal regardless of stack state.

    Strips the RUN_DUAL_BACKTEST managed block so leftover toggles from
    a prior aborted run don't leak in.
    """
    out: dict[str, str] = {}
    if not ENV_PATH.exists():
        return out
    body = ENV_PATH.read_text(encoding="utf-8")
    body = re.sub(
        re.escape(STACK_MARKER_START) + r".*?" + re.escape(STACK_MARKER_END) + r"\n?",
        "",
        body,
        flags=re.DOTALL,
    )
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip("\"'")
    return out


def docker_compose(
    *args: str,
    check: bool = True,
    capture: bool = False,
    env_overrides: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    cmd = ["docker", "compose", "-f", str(COMPOSE_PATH), *args]
    log(f"$ {' '.join(cmd)}")
    env = os.environ.copy()
    # Hydrate from .env first (so OPENROUTER_API_KEY etc. reach the
    # container's docker-compose interpolation pass).
    env.update(load_dotenv_vars())
    if env_overrides:
        env.update(env_overrides)
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        check=check,
        text=True,
        capture_output=capture,
        env=env,
    )


def recreate_hotel_api(stack_env: dict[str, str]) -> None:
    """Force-recreate hotel-api with the given stack overrides actually applied.

    docker compose interpolates ${VAR:-default} from (a) the calling
    process's environment, (b) the .env file in cwd, (c) the YAML default.
    Earlier driver versions only mutated .env, but the .env file was being
    masked by the YAML default substitution in some cases (both stacks
    ended up with the YAML default values). Injecting via the subprocess
    environment is the most direct path and guarantees the stack toggles
    reach the container.
    """
    docker_compose(
        "up", "-d", "--force-recreate", "--no-deps", "hotel-api",
        env_overrides=stack_env,
    )


def verify_container_env(expected: dict[str, str]) -> None:
    """Read the actual container env and fail loudly if it doesn't match.

    Catches the failure mode where the stack overrides didn't propagate.
    """
    log("  verifying container env actually got stack overrides…")
    out = subprocess.run(
        ["docker", "exec", "hotel-api", "env"],
        capture_output=True, text=True, timeout=15,
    ).stdout
    actual = {}
    for line in out.splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            actual[k] = v
    mismatches = []
    for k, want in expected.items():
        got = actual.get(k, "<unset>")
        if got != want:
            mismatches.append(f"    {k}: want={want!r} got={got!r}")
        else:
            log(f"    OK  {k}={got!r}")
    if mismatches:
        log("  CONTAINER ENV MISMATCH:")
        for m in mismatches:
            log(m)
        raise RuntimeError(
            "container env did not match expected stack — aborting before "
            "polluting eval results with the wrong config"
        )
    # Also verify OPENROUTER_API_KEY is real (not the docker-compose dummy
    # fallback). If embeddings 401, every RAG retrieval returns empty and
    # every /chat refuses with "information system unavailable" regardless
    # of stack state — making the dual backtest useless. Catch this before
    # burning hours of GPU time.
    ork = actual.get("OPENROUTER_API_KEY", "")
    if not ork or ork.startswith("sk-dummy"):
        log(f"  OPENROUTER_API_KEY in container: {ork!r}")
        raise RuntimeError(
            "container is missing a real OPENROUTER_API_KEY (got dummy "
            "fallback). The .env file's value did not propagate via the "
            "subprocess env. Aborting before embeddings 401 corrupts the run."
        )
    log(f"    OK  OPENROUTER_API_KEY is real ({ork[:14]}…)")


def wait_for_healthz(timeout_s: int = 180) -> None:
    # Give the container a few seconds before the first probe — recreate
    # returns as soon as the process is spawned, but uvicorn + FastAPI +
    # the in-process LangGraph init can take 3-8s before /healthz answers.
    time.sleep(3)
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen("http://localhost:8088/healthz", timeout=5) as r:
                if r.status == 200:
                    log("  /healthz OK")
                    return
        except Exception:
            # Swallow every flavor of pre-ready error: URLError, HTTPError,
            # ConnectionRefusedError (Windows shows up here on a fresh
            # container), BrokenPipeError, OSError, TimeoutError, etc.
            pass
        time.sleep(3)
    raise RuntimeError(f"hotel-api did not become healthy within {timeout_s}s")


def admin_token() -> str:
    body = json.dumps({"username": "admin", "password": "admin123"}).encode("utf-8")
    req = urllib.request.Request(
        "http://localhost:8088/auth/login",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def put_llm_settings(model: str = "gemma4:12b-it-q8_0") -> None:
    """Set the runtime LLM via PUT /settings/llm. Non-fatal on auth failure.

    The container's OLLAMA_MODEL env already pins the default to Gemma Q8 at
    boot, so this call is a belt-and-braces re-assertion. After a DB re-seed
    the admin user may not exist yet (the seed-on-startup hook re-creates
    it but auth state can be racy), so a 401 here should not abort the
    whole dual backtest — fall through and trust the env default.
    """
    try:
        token = admin_token()
    except Exception as e:
        log(f"  /settings/llm SKIP — admin_token failed ({type(e).__name__}: {e}); "
            f"trusting OLLAMA_MODEL env default")
        return
    try:
        body = json.dumps({"backend": "ollama", "model": model}).encode("utf-8")
        req = urllib.request.Request(
            "http://localhost:8088/settings/llm",
            data=body,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            method="PUT",
        )
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.loads(r.read())
        log(f"  /settings/llm -> {d.get('model')} thinking={d.get('thinking')}")
    except Exception as e:
        log(f"  /settings/llm SKIP — PUT failed ({type(e).__name__}: {e}); "
            f"trusting OLLAMA_MODEL env default")


def warm_ollama_model(model: str = "gemma4:12b-it-q8_0") -> None:
    log(f"  warming {model} into VRAM…")
    subprocess.run(
        ["docker", "exec", "hotel-ollama", "ollama", "run", model, "hi"],
        check=False,
        capture_output=True,
        timeout=600,
    )


def check_openrouter_balance(min_balance: float = 0.50) -> float:
    helper = ROOT / "scripts" / "eval" / "check_openrouter_balance.py"
    out = subprocess.run(
        [sys.executable, str(helper)],
        capture_output=True,
        text=True,
        timeout=30,
    )
    log(f"  balance: {out.stdout.strip()}")
    # parse "$X.XXXX available"
    m = re.search(r"\$([0-9.]+)\s+available", out.stdout)
    bal = float(m.group(1)) if m else -1.0
    if bal < min_balance:
        raise RuntimeError(f"OpenRouter balance ${bal:.4f} below minimum ${min_balance:.2f}")
    return bal


def run_canaries(endpoint: str = "http://localhost:8088", max_failures: int = 1) -> int:
    log("  canary gate (15 sentinels)…")
    # The canary script prints Thai/Chinese probe text — Windows' default cp1252
    # codec chokes on those bytes when subprocess captures stdout. Pass
    # encoding='utf-8' + errors='replace' so the driver never dies on a code
    # point. Also pipe through a hydrated env so OPENROUTER_API_KEY reaches
    # the canary script (it might call the judge for rubric).
    env = os.environ.copy()
    env.update(load_dotenv_vars())
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval" / "backtest_canaries.py"),
            "--endpoint",
            endpoint,
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=1800,
        env=env,
    )
    # Best-effort echo of canary output to the driver log; never let this
    # crash the run (third crash today was a parent-stdout cp1252 encode
    # failure on the canary script's Thai/Chinese probe text).
    def _safe_write(stream, payload: str) -> None:
        if not payload:
            return
        try:
            stream.write(payload)
        except Exception as exc:
            try:
                stream.write(
                    payload.encode("utf-8", errors="replace")
                           .decode("ascii", errors="replace")
                )
            except Exception:
                stream.write(f"[unprintable subprocess output: {type(exc).__name__}]\n")
    _safe_write(sys.stdout, p.stdout)
    _safe_write(sys.stderr, p.stderr)
    # backtest_canaries.py exit code: 0 OK, 1 too many failed
    if p.returncode > max_failures:
        raise RuntimeError(f"canary gate failed (exit={p.returncode})")
    return p.returncode


def run_full_backtest(tag: str, endpoint: str = "http://localhost:8088") -> Path:
    log(f"  full backtest (tag={tag})…")
    env = os.environ.copy()
    env.update(load_dotenv_vars())
    env["PYTHONIOENCODING"] = "utf-8"
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval" / "backtest_runner.py"),
            "--tag",
            tag,
            "--endpoint",
            endpoint,
            "--no-canaries",  # already gated above
            "--abort-canary-failures",
            "16",
            # CRITICAL for confound isolation: the chat-cache key does NOT
            # include the stack toggles (HYBRID_RETRIEVAL, RERANKER_BACKEND,
            # HOTEL_QUERY_REWRITE_ENABLED, HOTEL_PROMPT_PATH), so a cached
            # response from one stack would be replayed for the other —
            # making the two runs look identical regardless of the actual
            # stack configuration. The 2026-06-12 cached run proved this:
            # Stack-OFF and Stack-ON both scored 2.6% / 2.2% from a stale
            # cache. Always force fresh chats for the dual backtest.
            "--no-chat-cache",
            # CRITICAL: match GPU concurrency. OLLAMA_NUM_PARALLEL=1 (Q8 needs
            # serial inference) and MAX_CONCURRENT_LLM_CALLS=1 in the
            # container; runner default of 2 causes the 2nd concurrent /chat
            # to queue for 45s and 503 with empty_response. The 2026-06-12
            # dual backtest had 6.8% / 10% of cases failing this way,
            # silently contaminating the EN/TH regression analysis.
            "--max-chat-parallel", "1",
        ],
        cwd=str(ROOT),
        # Don't capture — we want streaming progress in the parent log.
        check=False,
        timeout=24 * 3600,  # 24h hard ceiling
        env=env,
    )
    if p.returncode != 0:
        log(f"  WARN: backtest_runner.py exit={p.returncode} (raw.jsonl preserved for resume)")

    # find the run dir (latest under eval/results/<tag>/)
    tag_dir = ROOT / "eval" / "results" / tag
    candidates = sorted([d for d in tag_dir.glob("*") if d.is_dir()], reverse=True)
    if not candidates:
        raise RuntimeError(f"no run dir found under {tag_dir}")
    return candidates[0]


def run_report(run_dir: Path) -> None:
    log(f"  rendering report for {run_dir}…")
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval" / "backtest_report.py"),
            "--run-dir",
            str(run_dir),
        ],
        cwd=str(ROOT),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=600,
    )
    if p.stdout:
        sys.stdout.write(p.stdout)
    if p.returncode != 0:
        log(f"  WARN: backtest_report.py exit={p.returncode}")


def run_stack(tag: str, stack_env: dict[str, str]) -> Path:
    log(f"=== STACK '{tag}' begin ===")
    log("  patching .env with stack overrides (for documentation / paper trail)")
    patch_env_file(stack_env)
    log("  recreating hotel-api container with stack env injected via subprocess")
    recreate_hotel_api(stack_env)
    wait_for_healthz()
    # Verify the container actually picked up the stack env before doing any
    # eval work. Strip OLLAMA_MODEL because it's confirmed via /settings/llm.
    expected = {k: v for k, v in stack_env.items() if k != "OLLAMA_MODEL"}
    verify_container_env(expected)
    log("  setting LLM to gemma4:12b-it-q8_0 via /settings/llm")
    put_llm_settings("gemma4:12b-it-q8_0")
    warm_ollama_model("gemma4:12b-it-q8_0")
    check_openrouter_balance(min_balance=0.50)
    run_canaries()
    run_dir = run_full_backtest(tag)
    run_report(run_dir)
    bal = check_openrouter_balance(min_balance=0.0)
    log(f"=== STACK '{tag}' done. run_dir={run_dir} balance=${bal:.4f} ===")
    return run_dir


def build_apd_table(stackoff_dir: Path, stackon_dir: Path, qwen_dir: Path) -> None:
    log("=== building AP_D per-case Q&A table ===")
    out = ROOT / "thesis" / "AP_D_Per_Case_QA.md"
    p = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "eval" / "build_apd_table.py"),
            "--run-a", str(qwen_dir),
            "--run-b", str(stackoff_dir),
            "--run-c", str(stackon_dir),
            "--out", str(out),
        ],
        cwd=str(ROOT),
        check=False,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=300,
    )
    def _safe_write2(stream, payload: str) -> None:
        if not payload:
            return
        try:
            stream.write(payload)
        except Exception:
            try:
                stream.write(payload.encode("utf-8", errors="replace").decode("ascii", errors="replace"))
            except Exception:
                pass
    _safe_write2(sys.stdout, p.stdout)
    if p.returncode != 0:
        _safe_write2(sys.stderr, p.stderr)
        log(f"  WARN: build_apd_table.py exit={p.returncode}")


def _force_utf8_stdout() -> None:
    """Reconfigure parent stdout/stderr to UTF-8 with errors='replace'.

    Without this, any subprocess output containing Thai/Chinese bytes (the
    canary probe transcripts) raises UnicodeEncodeError when we write it
    back to a redirected stdout — Windows' default cp1252 codec can't
    encode CJK. Already cost the driver 2 crashes today.
    """
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception as e:
                log(f"  WARN: could not reconfigure sys.{stream_name}: {e}")


def main() -> int:
    _force_utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--stackoff-tag", default="gemma_q8_stackoff")
    ap.add_argument("--stackon-tag", default="gemma_q8_stackon")
    ap.add_argument(
        "--qwen-baseline",
        default="eval/results/final-postfix/20260609T205731",
        help="Qwen 9B baseline dir for AP_D column A",
    )
    ap.add_argument("--skip-stackoff", action="store_true", help="resume — skip Backtest #1")
    ap.add_argument("--skip-stackon", action="store_true", help="resume — skip Backtest #2")
    ap.add_argument(
        "--restore-env",
        action="store_true",
        help="Just strip the managed .env block and exit (cleanup after crash)",
    )
    args = ap.parse_args()

    if args.restore_env:
        restore_env_file()
        log("restored .env (stripped managed block)")
        return 0

    # Sanity: docker compose + balance helper reachable
    try:
        subprocess.run(["docker", "--version"], check=True, capture_output=True, timeout=10)
    except (subprocess.CalledProcessError, FileNotFoundError, TimeoutError) as e:
        log(f"FATAL: docker unavailable: {e}")
        return 2

    check_openrouter_balance(min_balance=1.00)

    stackoff_dir = stackon_dir = None
    try:
        if not args.skip_stackoff:
            stackoff_dir = run_stack(args.stackoff_tag, STACK_OFF_ENV)
        else:
            # Find the most recent stackoff run for AP_D.
            cands = sorted(
                (ROOT / "eval" / "results" / args.stackoff_tag).glob("*"),
                reverse=True,
            )
            stackoff_dir = cands[0] if cands else None

        if not args.skip_stackon:
            stackon_dir = run_stack(args.stackon_tag, STACK_ON_ENV)
        else:
            cands = sorted(
                (ROOT / "eval" / "results" / args.stackon_tag).glob("*"),
                reverse=True,
            )
            stackon_dir = cands[0] if cands else None

        if stackoff_dir and stackon_dir:
            qwen_dir = (ROOT / args.qwen_baseline).resolve()
            build_apd_table(stackoff_dir, stackon_dir, qwen_dir)
    finally:
        restore_env_file()
        log("restored .env (stripped managed block)")

    log("=== dual backtest complete ===")
    log(f"  Backtest #1 (Stack-OFF): {stackoff_dir}")
    log(f"  Backtest #2 (Stack-ON):  {stackon_dir}")
    bal = check_openrouter_balance(min_balance=0.0)
    log(f"  OpenRouter balance after: ${bal:.4f}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("interrupted; .env will be restored on next --restore-env invocation")
        sys.exit(130)
