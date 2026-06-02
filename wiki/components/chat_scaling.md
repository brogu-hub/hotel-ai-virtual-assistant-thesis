---
type: component
path: "src/hotel_guardrails/chat_scaling.py"
status: active
parent_module: hotel_guardrails
tags: [component, concurrency, scaling, rate-limiting, backpressure]
date_ingested: 2026-04-20
---

# chat_scaling — Concurrency & Backpressure

## Purpose

Protect the hotel assistant from traffic spikes that could starve the LLM backend's connection budget or the LangGraph checkpoint path. All controls are process-local and in-memory — no external dependency (no Redis) in the default configuration.

## Classes

| Class | Purpose |
|---|---|
| `LLMConcurrencyLimiter` (line 56) | `asyncio.Semaphore` capping simultaneous LLM calls. Callers `await` the limiter before invoking `get_llm()`. Raises `LLMQueueTimeout` if wait exceeds the configured cap. |
| `LLMQueueTimeout` (line 133) | Custom exception for bounded-wait failures. Caught at the server edge and mapped to a 503 with a retryable message. |
| `SessionLockManager` (line 142) | Per-session `asyncio.Lock`. Ensures a single session cannot interleave two `/chat` calls that would corrupt the shared `HotelState`. Locks are auto-evicted after idle timeout. |
| `ChatRateLimiter` (line 199) | Token-bucket per client identifier (user_id or request IP). Returns a `Retry-After` hint on 429. |
| `StreamConnectionLimiter` (line 252) | Caps concurrent SSE connections on `/chat/stream` so a burst of browser tabs cannot exhaust worker slots. |
| `KnowledgeCache` (line 298) | LRU cache keyed on normalised query string for the RAG sub-agent — avoids hitting Qdrant for repeated questions within a short window. |

## Functions

- `get_chat_metrics()` (line 394) — snapshot of limiter states: queue depths, lock counts, rate-limit refusals, cache hit rates. Used by `/health` and by the [[components/audit]] structured log emitter.

## Design choices

- **In-memory, not Redis.** Keeps the deployment simple and sub-millisecond. If horizontal scaling becomes necessary, the limiters can be swapped for Redis-backed equivalents without changing the `await` surface.
- **asyncio-first.** Every primitive is an `asyncio.Lock`/`Semaphore` so blocking never leaves the event loop.
- **Bounded waits, not unbounded.** Every `await` has a timeout; timeouts surface to the client as retryable 503s.
- **Session locks auto-evict.** Idle locks release their memory so a burst of unique session IDs can't leak heap.

## Integration points

- `server.py` — instantiates limiters at startup and wraps `/chat`/`/chat/stream` handlers with `acquire()`/`release()` patterns.
- `hotel_langgraph.py` — LLM factory awaits `LLMConcurrencyLimiter` before creating a `ChatOpenAI` client.
- `components/knowledge_subagent` — reads `KnowledgeCache` before calling the retriever.

## Env controls

Configuration is read from [[components/config]]'s `ServerSettings`. Typical knobs: `APP_SERVER_LLM_MAX_CONCURRENT`, `APP_SERVER_CHAT_RATE_LIMIT_PER_MIN`, `APP_SERVER_STREAM_MAX_CONNS`, `APP_SERVER_KNOWLEDGE_CACHE_SIZE`. See config.py for the authoritative list.

## Observability

`get_chat_metrics()` output is surfaced in `/health` and logged at INFO every few minutes. Surges in `queue_depth` or `rate_limited_refusals` indicate capacity pressure before it becomes a user-visible outage.

## Related

- [[flows/chat_scaling]] — sequence view of request queuing
- [[components/server]] — instantiation and wiring
- [[components/hotel_langgraph]] — consumer of the LLM concurrency limit
- [[entities/Redis]] — potential future backing store for horizontal scaling
