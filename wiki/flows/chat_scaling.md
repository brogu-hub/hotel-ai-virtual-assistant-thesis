---
type: flow
status: active
entry_point: "POST /chat (concurrency path)"
endpoints:
  - "POST /chat"
  - "POST /chat/stream"
  - "GET /admin/metrics/chat"
involves:
  - hotel_guardrails
  - hotel_langgraph
  - Ollama
  - Qdrant
created: 2026-04-19
updated: 2026-04-19
tags: [flow, scaling, concurrency, rate-limiting, cache]
---

# Flow: Chat Scaling

Five primitives gate the `/chat` path to protect the local LLM and PostgreSQL from overload. All are implemented in `src/hotel_guardrails/chat_scaling.py`.

## Request path (concurrency view)

```
POST /chat (user message)
     │
     ▼
┌─────────────────────────┐  429 + Retry-After
│ Per-session rate limit  │──► "Too many messages for this session"
│ ChatRateLimiter         │
│ CHAT_RATE_LIMIT_PER_    │
│ SESSION = 30/min        │
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Per-session async lock  │  serialises requests for the SAME session_id
│ SessionLockManager      │  prevents LangGraph checkpointer interleaving
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐  cache HIT → skip Qdrant + reranker (~1ms)
│ Routing + PII scrub +   │
│ KnowledgeCache lookup   │
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐  503 + Retry-After
│ LLM concurrency         │──► "Chatbot is busy, try again in a moment"
│ semaphore               │
│ MAX_CONCURRENT_LLM_     │
│ CALLS = 4               │
└─────────────────────────┘
     │
     ▼
┌─────────────────────────┐
│ Ollama (GPU, 4 parallel │  OLLAMA_NUM_PARALLEL=4
│ slots)                  │
└─────────────────────────┘
     │
     ▼
Response + audit log
```

## Scaling primitives

| Component | Class | Env var | Default | Purpose |
|---|---|---|---|---|
| LLM concurrency semaphore | `LLMConcurrencyLimiter` | `MAX_CONCURRENT_LLM_CALLS` | 4 | Async semaphore; extras fast-fail instead of piling up |
| LLM queue timeout | `LLMConcurrencyLimiter` | `LLM_QUEUE_TIMEOUT_SEC` | 30 | Wait >30s for a slot → 503 Retry-After |
| Session lock | `SessionLockManager` | `SESSION_LOCK_MAX_ENTRIES` | 10000 | Per-session `asyncio.Lock`, bounded LRU |
| Chat rate limiter | `ChatRateLimiter` | `CHAT_RATE_LIMIT_PER_SESSION` | 30/min | Sliding window per `session_id` → 429 |
| Stream cap | `StreamConnectionLimiter` | `MAX_CONCURRENT_STREAMS` | 20 | Hard cap on open SSE streams → 503 |
| Knowledge cache | `KnowledgeCache` | `KNOWLEDGE_CACHE_SIZE` | 500 | LRU+TTL cache for RAG queries |
| Cache TTL | `KnowledgeCache` | `KNOWLEDGE_CACHE_TTL_SEC` | 300 | 5 min — quick invalidation on hotel-info changes |

## Ollama parallelism alignment

Ollama serialises requests by default (`OLLAMA_NUM_PARALLEL=1`). `docker-compose.hotel.yaml` sets `OLLAMA_NUM_PARALLEL=4` to match the app-side semaphore.

```
App semaphore (MAX_CONCURRENT_LLM_CALLS=4)
        │
        ▼
Ollama slots (OLLAMA_NUM_PARALLEL=4)   ← must be >= app semaphore
        │
        ▼
Single 9B model on GPU (shared KV-cache)
```

Guideline: keep `MAX_CONCURRENT_LLM_CALLS <= OLLAMA_NUM_PARALLEL`. A single RTX 5080 (16GB) with a quantized 9B model can support 6-8 parallel slots.

## Knowledge cache detail

```
search_hotel_knowledge(query)
  → KnowledgeCache.get(query)
     HIT  → return (content, sources)   [~1ms]
     MISS → Qdrant vector search        [~500ms]
               │
               ▼
          trim to top_k (no reranker)   [~1ms]
               │
               ▼
          KnowledgeCache.set()
               │
               ▼
          return (content, sources)
```

Common questions hit the cache after the first ask: ~1 ms vs ~500 ms.

## Reranker disabled

`RERANKER_BACKEND=none` is the default. The CrossEncoder reranker added 1–2 s of synchronous CPU work inside an async endpoint, blocking the FastAPI event loop for all concurrent requests. Qdrant embedding search is sufficient for the 10-doc hotel knowledge base. Legacy options `qwen` and `nvidia` remain available via env var.

## Measured performance (local Docker, single worker)

| Benchmark | Result |
|---|---|
| 30 concurrent `GET /auth/me` | total 0.06s, p95 20ms |
| 50 sequential `GET /admin/audit` | 50/50 success |
| 20 concurrent `GET /admin/audit` | total 0.16s, all 200 |

## Production horizontal scaling notes

All primitives are in-memory and per-process — they reset on restart and do not coordinate across workers. For multi-worker deployments:

| Primitive | Redis replacement |
|---|---|
| `LLMConcurrencyLimiter` | Redis semaphore (`INCR` + `EXPIRE`) |
| `SessionLockManager` | Redis `SET NX EX` distributed lock |
| `ChatRateLimiter` | Redis `INCR` sliding window |
| `KnowledgeCache` | Redis with TTL |
| JTI blocklist (auth) | Redis `SET jti "" EX ttl` |
| Login rate limiter (auth) | Redis `INCR` sliding window |

`password_changed_at` invalidation (auth) is DB-backed — no Redis needed for that path.

Current setup (single container demo) is fine with in-memory and avoids an extra dependency.

## Observability

`GET /admin/metrics/chat` (admin JWT) returns live values for all primitives. See [[admin_monitoring]] for the full response schema.

Alert thresholds:
- `llm_limiter.total_rejected` growing quickly → add more GPU slots or scale out
- `knowledge_cache.hit_rate` < 0.3 → cache size or TTL too low

## Related

- [[guest_chat]] — the flow this protects
- [[admin_monitoring]] — metrics endpoint
- [[decisions/reranker_disabled]] — CrossEncoder removal decision
- [[Ollama]] — entity page for local LLM
