"""Chat-response cache for the strategic backtest.

Key shape: <case_id>__<chat_sha>__<corpus_sha>[__v<cache_version>]
  chat_sha   = sha256(llm_model + endpoint)[:12]
  corpus_sha = sha256(concat(sorted data/hotel/*.md bytes))[:12]

Storage: eval/cache/chat_responses/<case_id>.jsonl, one envelope per line
(JSON-encoded {"key": ..., "envelope": ..., "ts": ...}). Append-only;
last-write-wins on lookup so a fresh run silently supersedes a stale entry
without requiring compaction.

Thread-safety: read_cache is read-only; write_cache opens with mode="a" so
POSIX guarantees atomic single-line appends up to PIPE_BUF. The runner's
append_jsonl lock is NOT required here because each case_id has its own
shard and the runner already serialises per-case work.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE_DIR = ROOT / "eval" / "cache" / "chat_responses"


def _sha12(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:12]


def compute_chat_sha(llm_model: str, endpoint: str) -> str:
    """Identity of the chat backend. Changes when model or URL changes."""
    return _sha12(f"{llm_model}||{endpoint}")


def compute_corpus_sha(hotel_dir: Optional[Path] = None) -> str:
    """Stable hash of the hotel knowledge corpus (data/hotel/*.md).

    Sorted by filename so Windows vs. POSIX dir ordering doesn't drift.
    """
    hotel_dir = hotel_dir or (ROOT / "data" / "hotel")
    if not hotel_dir.exists():
        return "nocorpus"
    h = hashlib.sha256()
    for md in sorted(hotel_dir.glob("*.md")):
        h.update(md.name.encode("utf-8"))
        h.update(b"\0")
        h.update(md.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:12]


def make_key(case_id: str, chat_sha: str, corpus_sha: str, version: str = "") -> str:
    base = f"{case_id}__{chat_sha}__{corpus_sha}"
    return f"{base}__v{version}" if version else base


def _shard_path(case_id: str) -> Path:
    # Sanitize: case_id may contain '/' or ':' in malformed datasets.
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in case_id)
    return CACHE_DIR / f"{safe}.jsonl"


def read_cache(case_id: str, key: str) -> Optional[Dict[str, Any]]:
    """Return the cached envelope for key, or None on miss.

    Reads the shard top-to-bottom and returns the LAST matching entry —
    this gives last-write-wins semantics without requiring rewrite.
    """
    shard = _shard_path(case_id)
    if not shard.exists():
        return None
    hit: Optional[Dict[str, Any]] = None
    try:
        with open(shard, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if row.get("key") == key:
                    hit = row.get("envelope")
    except OSError:
        return None
    return hit


def write_cache(case_id: str, key: str, envelope: Dict[str, Any]) -> None:
    """Append (key, envelope) to the case_id shard. Best-effort; errors swallowed."""
    shard = _shard_path(case_id)
    try:
        shard.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "key": key,
            "envelope": envelope,
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        with open(shard, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as exc:
        # Cache is an optimisation — never crash the runner on a write failure.
        print(f"WARN: chat-cache write failed for {case_id}: {exc}")
