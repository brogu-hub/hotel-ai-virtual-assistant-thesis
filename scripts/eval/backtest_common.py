"""Shared utilities for the hotel chatbot backtest pipeline.

This module is the home of every cross-script helper used by the backtest
suite (generator, canary runner, main runner, bucket, report). Each helper
is deliberately kept small and dependency-light so the same code can run
from inside the hotel-api container (eval against localhost:8088 via the
docker network) and from the host (eval against the deployed Railway URL).

Public surface:
    Statistical helpers:
        wilson_ci(correct, total)        -> (low, high) 95% CI
        stratified_sample(cases, n, ...) -> list[case]
    Language detection:
        detect_lang(text)                -> 'en' | 'th' | 'cn' | '?'
        has_language_leak(text, expected, user_input)
                                         -> bool
    Tool / leak detection:
        TOOL_CALL_LEAK_RE                regex for raw tool syntax in prose
        extract_tool_calls(response_envelope)
                                         -> list[{'name': str, 'args': dict}]
    Version pins for reproducibility:
        capture_version_pins(judge_model)
                                         -> dict (the 6 required pins)
    JSONL streaming:
        load_jsonl(path)                 -> Iterator[dict]
        append_jsonl(path, row)          -> None
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime, timezone
from math import sqrt
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

# =============================================================================
# Statistical helpers
# =============================================================================


def wilson_ci(correct: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Standard for reporting pass-rates at small n; outperforms naive
    p +/- z*sqrt(p*(1-p)/n) when p is near 0 or 1 or n is small.

    Returns (low, high) as proportions in [0, 1], rounded to 3dp.
    """
    if total <= 0:
        return (0.0, 0.0)
    p = correct / total
    denom = 1 + z ** 2 / total
    centre = (p + z ** 2 / (2 * total)) / denom
    margin = (z * sqrt(p * (1 - p) / total + z ** 2 / (4 * total ** 2))) / denom
    low = max(0.0, centre - margin)
    high = min(1.0, centre + margin)
    return (round(low, 3), round(high, 3))


def stratified_sample(
    cases: Sequence[Dict[str, Any]],
    n: int,
    strata_keys: Sequence[str] = ("domain", "language"),
    rng_seed: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Sample roughly equally across (domain x language) cells.

    Uniform random sampling would let high-cardinality strata (e.g.
    `rooms`) dominate the sample and mask failures in low-cardinality
    strata (e.g. `attractions`). Stratification fixes that.

    rng_seed: pass an int for reproducible sampling (golden-set CI runs).
    """
    if n <= 0 or not cases:
        return []
    rng = random.Random(rng_seed) if rng_seed is not None else random
    buckets: Dict[Tuple[Any, ...], List[Dict[str, Any]]] = defaultdict(list)
    for c in cases:
        key = tuple(c.get(k, "unknown") for k in strata_keys)
        buckets[key].append(c)
    per_bucket = max(1, n // len(buckets))
    sampled: List[Dict[str, Any]] = []
    for bucket in buckets.values():
        sampled.extend(rng.sample(bucket, min(per_bucket, len(bucket))))
    rng.shuffle(sampled)
    return sampled[:n]


# =============================================================================
# Language detection
# =============================================================================

CJK_RE = re.compile(r"[㐀-鿿]")
THAI_RE = re.compile(r"[฀-๿]")


def detect_lang(text: str) -> str:
    """Heuristic script-dominance detection over EN / TH / CN.

    Returns 'en', 'th', 'cn', or '?' (when text is too short to decide).
    Uses 20% threshold (matching the chatbot's own detect_input_language).
    """
    if not text:
        return "?"
    cjk = len(CJK_RE.findall(text))
    thai = len(THAI_RE.findall(text))
    latin = sum(1 for c in text if c.isascii() and c.isalpha())
    total = cjk + thai + latin
    if total < 5:
        return "?"
    if cjk >= max(thai, latin) and cjk / total >= 0.20:
        return "cn"
    if thai >= max(cjk, latin) and thai / total >= 0.20:
        return "th"
    return "en"


def has_language_leak(
    response: str,
    expected_lang: str,
    user_input: str = "",
) -> bool:
    """True if the response script disagrees with expected_lang.

    User-provided proper names (e.g. a Chinese guest's name echoed back
    in an English reply) are excluded — characters that appear in
    user_input are whitelisted.
    """
    if not response or expected_lang == "?":
        return False
    user_cjk = set(CJK_RE.findall(user_input))
    user_thai = set(THAI_RE.findall(user_input))

    foreign_cjk = [c for c in CJK_RE.findall(response) if c not in user_cjk]
    foreign_thai = [c for c in THAI_RE.findall(response) if c not in user_thai]

    if expected_lang == "en":
        return len(foreign_cjk) >= 1 or len(foreign_thai) >= 3
    if expected_lang == "th":
        return len(foreign_cjk) >= 1
    if expected_lang == "cn":
        return len(foreign_thai) >= 5
    return False


# =============================================================================
# Tool / leak detection
# =============================================================================

# Tool names that the hotel agent can legitimately invoke; if any of these
# appear as a function-call literal in the user-facing response text,
# something leaked through the §5.14.2 quality gate.
HOTEL_TOOL_NAMES = (
    "search_hotel_knowledge",
    "check_room_availability",
    "create_reservation",
    "cancel_reservation",
    "get_guest_reservations",
    "calculate_dynamic_price",
    "create_service_request",
    "get_service_requests",
    "generate_payment_link",
)
TOOL_CALL_LEAK_RE = re.compile(
    r"\b(?:" + "|".join(HOTEL_TOOL_NAMES) + r")\s*\(",
    re.IGNORECASE,
)


def extract_tool_calls(response_envelope: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pull the structured tool-call list from a chatbot /chat envelope.

    The hotel server returns `tool_calls` (list of dicts) in its
    `/chat` response. This helper normalises it across schema versions
    so eval code can treat it uniformly.
    """
    raw = response_envelope.get("tool_calls") or response_envelope.get("toolCalls") or []
    out: List[Dict[str, Any]] = []
    for call in raw:
        if not isinstance(call, dict):
            continue
        name = call.get("name") or call.get("tool") or call.get("function", {}).get("name")
        args = call.get("args") or call.get("arguments") or call.get("function", {}).get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                pass
        if name:
            out.append({"name": name, "args": args or {}})
    return out


# =============================================================================
# Version pins (6 required) — per §2.2.2 of the eval strategy
# =============================================================================


def _git_sha(short: bool = True) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short" if short else "HEAD", "HEAD"],
            cwd=Path(__file__).resolve().parent.parent.parent,
            stderr=subprocess.DEVNULL,
            text=True,
        ).strip()
        return out or "unknown"
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _qdrant_corpus_signature(api_base: str = "http://localhost:8088") -> str:
    """Stable signature of the Qdrant hotel_knowledge collection."""
    try:
        import urllib.request
        req = urllib.request.Request(f"{api_base}/healthz")
        with urllib.request.urlopen(req, timeout=3) as resp:
            urllib.request.urlopen(req, timeout=3).read()
    except Exception:
        pass
    # Fall back to a timestamp signature if we can't query Qdrant directly
    return f"qdrant_hotel_knowledge_unknown_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"


def capture_version_pins(
    judge_model: str = "deepseek/deepseek-chat-v3.1",
    dataset_path: Optional[Path] = None,
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """Build the 6-field version-pin block for this backtest run.

    Per the strategy: workflow_sha + corpus_version + embedding_model +
    llm_model + judge_model + dataset_version. Without all six, results
    can't be reproduced or cross-compared.
    """
    pins = {
        "workflow_sha": _git_sha(),
        "corpus_version": _qdrant_corpus_signature(),
        "embedding_model": os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b"),
        "llm_model": os.getenv("OLLAMA_MODEL", os.getenv("APP_LLM_MODELNAME", "unknown")),
        "judge_model": judge_model,
        "dataset_version": _dataset_signature(dataset_path) if dataset_path else "unspecified",
    }
    if extra:
        pins.update(extra)
    return pins


def _dataset_signature(path: Path) -> str:
    """SHA256 short-prefix of a JSONL file's bytes — stable across reorderings.

    Useful as the dataset_version pin so two runs against the same golden
    file produce the same signature even if file metadata differs.
    """
    if not path.exists():
        return "missing"
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"sha256_{h.hexdigest()[:12]}"


# =============================================================================
# JSONL streaming
# =============================================================================


def load_jsonl(path: Path) -> Iterator[Dict[str, Any]]:
    """Stream-parse a JSONL file. Skips blank lines and # comments."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                print(f"WARN: skipping malformed JSONL line in {path}: {exc}", file=sys.stderr)


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    """Append one record to a JSONL file, creating parent dir if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# =============================================================================
# OpenRouter chat client (shared by generator + judge runner)
# =============================================================================


def call_openrouter(
    model: str,
    messages: List[Dict[str, str]],
    *,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    response_format_json: bool = False,
    api_key: Optional[str] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """One-shot OpenRouter chat completion. Returns the raw JSON envelope.

    Uses urllib so we don't add a runtime dependency on httpx/requests
    just for the eval harness. Caller is responsible for parsing the
    content field.
    """
    import urllib.request
    api_key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY not set")
    body: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format_json:
        body["response_format"] = {"type": "json_object"}
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/Mangakorian/hote-ai-virtual-assistant-thesis",
            "X-Title": "hotel-ai-eval-backtest",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def extract_content(envelope: Dict[str, Any]) -> str:
    """Pull the assistant message content from an OpenRouter completion envelope."""
    try:
        return envelope["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return ""
