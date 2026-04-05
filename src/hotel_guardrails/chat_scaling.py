# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Scaling primitives for the chatbot path (many concurrent users).

Provides:
  - LLMConcurrencyLimiter  : async semaphore + queue timeout to cap
                             concurrent LLM calls (Ollama is single-process)
  - SessionLockManager     : per-session asyncio.Lock so a single user
                             cannot corrupt LangGraph state by spamming
                             messages into the same session concurrently
  - ChatRateLimiter        : per-session sliding window to prevent abuse
  - StreamConnectionLimiter: cap on simultaneously-held SSE connections
  - KnowledgeCache         : TTL+LRU cache for RAG queries (hot questions
                             like "what time is breakfast?" hit the cache
                             instead of Qdrant + reranker)
  - ChatMetrics            : unified counter registry exposed via
                             /admin/metrics/chat

All components are thread-safe (locks) and asyncio-friendly (use asyncio
primitives where possible). In-memory by design — for horizontal scaling
across workers, swap to Redis-backed equivalents.
"""
from __future__ import annotations

import os
import time
import asyncio
import logging
import threading
from collections import OrderedDict, defaultdict, deque
from typing import Any, Deque, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# =============================================================================
# Configuration from environment
# =============================================================================

MAX_CONCURRENT_LLM_CALLS = int(os.getenv("MAX_CONCURRENT_LLM_CALLS", "5"))
LLM_QUEUE_TIMEOUT_SEC = float(os.getenv("LLM_QUEUE_TIMEOUT_SEC", "30"))
MAX_CONCURRENT_STREAMS = int(os.getenv("MAX_CONCURRENT_STREAMS", "20"))
CHAT_RATE_LIMIT_PER_SESSION = int(os.getenv("CHAT_RATE_LIMIT_PER_SESSION", "30"))  # per minute
CHAT_RATE_WINDOW_SEC = 60
KNOWLEDGE_CACHE_SIZE = int(os.getenv("KNOWLEDGE_CACHE_SIZE", "500"))
KNOWLEDGE_CACHE_TTL_SEC = int(os.getenv("KNOWLEDGE_CACHE_TTL_SEC", "300"))  # 5 min
SESSION_LOCK_MAX_ENTRIES = int(os.getenv("SESSION_LOCK_MAX_ENTRIES", "10000"))


# =============================================================================
# LLM Concurrency Limiter
# =============================================================================


class LLMConcurrencyLimiter:
    """
    asyncio.Semaphore wrapper with queue-timeout and metrics.

    Rationale:
    - Ollama is a single inference process. N concurrent LangGraph calls
      still serialize inside Ollama, so piling 50 requests on it just
      makes every request slow and burns memory on LangGraph state.
    - Cap in-flight LLM calls at N (e.g., 5). The (N+1)-th request WAITS
      up to LLM_QUEUE_TIMEOUT_SEC, then 503s with Retry-After.
    - This gives us predictable tail latency and fast-fail backpressure.
    """

    def __init__(self, max_concurrent: int, queue_timeout: float) -> None:
        self.max_concurrent = max_concurrent
        self.queue_timeout = queue_timeout
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._in_flight = 0
        self._waiting = 0
        self._total_acquired = 0
        self._total_rejected = 0
        self._total_timed_out = 0
        self._lock = threading.Lock()  # for counter updates

    async def acquire(self) -> None:
        """
        Acquire a slot. Raises `LLMQueueTimeout` if the queue is saturated
        for longer than `queue_timeout` seconds.
        """
        with self._lock:
            self._waiting += 1
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.queue_timeout,
            )
        except asyncio.TimeoutError:
            with self._lock:
                self._waiting -= 1
                self._total_timed_out += 1
                self._total_rejected += 1
            raise LLMQueueTimeout(
                f"LLM queue saturated — could not acquire slot in "
                f"{self.queue_timeout}s (max_concurrent={self.max_concurrent})"
            )

        with self._lock:
            self._waiting -= 1
            self._in_flight += 1
            self._total_acquired += 1

    def release(self) -> None:
        """Release a slot back to the semaphore."""
        self._semaphore.release()
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)

    async def __aenter__(self) -> "LLMConcurrencyLimiter":
        await self.acquire()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        self.release()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "max_concurrent": self.max_concurrent,
                "in_flight": self._in_flight,
                "waiting": self._waiting,
                "queue_timeout_sec": self.queue_timeout,
                "total_acquired": self._total_acquired,
                "total_rejected": self._total_rejected,
                "total_timed_out": self._total_timed_out,
            }


class LLMQueueTimeout(Exception):
    """Raised when a request waits too long for an LLM slot."""


# =============================================================================
# Per-session lock manager
# =============================================================================


class SessionLockManager:
    """
    Per-session asyncio.Lock with bounded LRU eviction.

    Rationale:
    - If a user sends message A, then message B to the same session_id
      before A finishes, LangGraph's checkpointer sees overlapping writes
      and the conversation state can get corrupted or interleave.
    - A per-session lock serializes requests for the same session without
      affecting requests to OTHER sessions.
    - Lock objects are cheap but unbounded memory is not: evict LRU
      entries above SESSION_LOCK_MAX_ENTRIES.
    """

    def __init__(self, max_entries: int) -> None:
        self.max_entries = max_entries
        self._locks: "OrderedDict[str, asyncio.Lock]" = OrderedDict()
        self._lock = threading.Lock()  # protects the OrderedDict itself

    def get(self, session_id: str) -> asyncio.Lock:
        """Get (or create) the asyncio.Lock for a session_id."""
        with self._lock:
            lock = self._locks.get(session_id)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[session_id] = lock
            else:
                self._locks.move_to_end(session_id)

            # Evict LRU entries when over budget
            while len(self._locks) > self.max_entries:
                # Only evict if the oldest lock isn't currently held
                oldest_sid, oldest_lock = next(iter(self._locks.items()))
                if oldest_lock.locked():
                    break
                self._locks.popitem(last=False)
            return lock

    def size(self) -> int:
        with self._lock:
            return len(self._locks)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            locked_count = sum(1 for lock in self._locks.values() if lock.locked())
            return {
                "tracked_sessions": len(self._locks),
                "currently_locked": locked_count,
                "max_entries": self.max_entries,
            }


# =============================================================================
# Per-session chat rate limiter (sliding window)
# =============================================================================


class ChatRateLimiter:
    """
    Sliding-window rate limiter per session_id.

    Prevents a single user from spamming the chatbot (which is expensive
    due to LLM inference). A reasonable limit is 30 messages/minute.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self.limit = limit
        self.window = window_seconds
        self._attempts: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._rejected_count = 0

    def check(self, session_id: str) -> Tuple[bool, int]:
        """
        Record a chat attempt and check if it's allowed.

        Returns (allowed, retry_after_seconds).
        """
        now = time.time()
        cutoff = now - self.window
        with self._lock:
            q = self._attempts[session_id]
            while q and q[0] < cutoff:
                q.popleft()

            if len(q) >= self.limit:
                retry_after = int(q[0] + self.window - now) + 1
                self._rejected_count += 1
                return False, max(retry_after, 1)

            q.append(now)
            return True, 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            active = sum(1 for q in self._attempts.values() if q)
            return {
                "limit_per_window": self.limit,
                "window_seconds": self.window,
                "tracked_sessions": len(self._attempts),
                "active_sessions": active,
                "total_rejected": self._rejected_count,
            }


# =============================================================================
# Concurrent SSE stream limiter
# =============================================================================


class StreamConnectionLimiter:
    """
    Counter-based cap on simultaneously-open SSE streaming responses.

    Each `/chat/stream` holds a connection open for the duration of the
    LLM response. Many open streams = many held resources. Cap the total,
    reject further streams with 503 until one completes.
    """

    def __init__(self, max_concurrent: int) -> None:
        self.max_concurrent = max_concurrent
        self._active = 0
        self._total_rejected = 0
        self._total_accepted = 0
        self._lock = threading.Lock()

    def try_acquire(self) -> bool:
        """Return True if we can accept a new stream, False if saturated."""
        with self._lock:
            if self._active >= self.max_concurrent:
                self._total_rejected += 1
                return False
            self._active += 1
            self._total_accepted += 1
            return True

    def release(self) -> None:
        """Called when a stream completes (success or error)."""
        with self._lock:
            self._active = max(0, self._active - 1)

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "max_concurrent": self.max_concurrent,
                "active": self._active,
                "total_accepted": self._total_accepted,
                "total_rejected": self._total_rejected,
            }


# =============================================================================
# Knowledge (RAG) cache — TTL + LRU
# =============================================================================


class KnowledgeCache:
    """
    TTL + LRU cache for RAG knowledge-base responses.

    Rationale:
    - Common questions hit repeatedly: "what time is breakfast?", "where
      is the gym?", "pool hours", "WiFi password". Every one of these
      currently does: Qdrant vector search -> reranker -> format.
    - Cache normalizes query (lowercase, collapse whitespace) and memoizes
      the (content, sources, retrieval_context) tuple for TTL_SEC.
    - Huge win for common queries; zero cost for rare ones.
    - TTL is short enough (5 min default) that updates to the knowledge
      base propagate quickly without admin intervention.
    """

    def __init__(self, max_size: int, ttl_seconds: int) -> None:
        self.max_size = max_size
        self.ttl = ttl_seconds
        self._cache: "OrderedDict[str, Tuple[float, Any]]" = OrderedDict()
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _key(query: str) -> str:
        """Normalize query for cache lookup: lowercase + collapse whitespace."""
        return " ".join(query.lower().split())

    def get(self, query: str) -> Optional[Any]:
        """Return cached value if present and fresh, else None."""
        k = self._key(query)
        now = time.time()
        with self._lock:
            entry = self._cache.get(k)
            if entry is None:
                self._misses += 1
                return None
            ts, value = entry
            if now - ts > self.ttl:
                self._cache.pop(k, None)
                self._misses += 1
                return None
            # Move to end (recently used)
            self._cache.move_to_end(k)
            self._hits += 1
            return value

    def set(self, query: str, value: Any) -> None:
        """Store a value in the cache, evicting LRU if over budget."""
        k = self._key(query)
        with self._lock:
            self._cache[k] = (time.time(), value)
            self._cache.move_to_end(k)
            while len(self._cache) > self.max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            hit_rate = (self._hits / total) if total else 0.0
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "ttl_seconds": self.ttl,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(hit_rate, 3),
            }


# =============================================================================
# Module-level singleton instances
# =============================================================================

llm_limiter = LLMConcurrencyLimiter(
    max_concurrent=MAX_CONCURRENT_LLM_CALLS,
    queue_timeout=LLM_QUEUE_TIMEOUT_SEC,
)
session_locks = SessionLockManager(max_entries=SESSION_LOCK_MAX_ENTRIES)
chat_rate_limiter = ChatRateLimiter(
    limit=CHAT_RATE_LIMIT_PER_SESSION,
    window_seconds=CHAT_RATE_WINDOW_SEC,
)
stream_limiter = StreamConnectionLimiter(max_concurrent=MAX_CONCURRENT_STREAMS)
knowledge_cache = KnowledgeCache(
    max_size=KNOWLEDGE_CACHE_SIZE,
    ttl_seconds=KNOWLEDGE_CACHE_TTL_SEC,
)


def get_chat_metrics() -> Dict[str, Any]:
    """Collect all chat scaling stats for the /admin/metrics/chat endpoint."""
    return {
        "llm_limiter": llm_limiter.stats(),
        "session_locks": session_locks.stats(),
        "chat_rate_limiter": chat_rate_limiter.stats(),
        "stream_limiter": stream_limiter.stats(),
        "knowledge_cache": knowledge_cache.stats(),
        "config": {
            "max_concurrent_llm_calls": MAX_CONCURRENT_LLM_CALLS,
            "llm_queue_timeout_sec": LLM_QUEUE_TIMEOUT_SEC,
            "max_concurrent_streams": MAX_CONCURRENT_STREAMS,
            "chat_rate_limit_per_session": CHAT_RATE_LIMIT_PER_SESSION,
            "knowledge_cache_size": KNOWLEDGE_CACHE_SIZE,
            "knowledge_cache_ttl_sec": KNOWLEDGE_CACHE_TTL_SEC,
        },
    }
