---
type: module
path: "src/hotel_guardrails/"
status: active
language: python
purpose: "Primary hotel assistant service — FastAPI server with LangGraph state machine, safety routing, RAG, booking, and guest management"
maintainer: "Mangakorian"
last_updated: 2026-04-19
depends_on:
  - src/agent/hotel_tools.py
  - src/retrievers/hotel_knowledge/
  - langchain
  - langgraph
  - fastapi
  - psycopg2
  - pydantic
used_by:
  - Railway deployment (production)
  - Docker Compose dev stack
linked_issues: []
tags: [module, hotel_guardrails, fastapi, langgraph, guardrails]
created: 2026-04-19
updated: 2026-04-19
---

# hotel_guardrails Module

## Purpose

The actively-developed hotel assistant service for The Grand Horizon Hotel. Exposes a FastAPI HTTP server with chat, booking, room management, guest registration, and admin endpoints. Internally, all chat requests flow through a safety pre-filter (`HybridRouter`) into an embedded LangGraph state machine (`hotel_langgraph`) that routes each message to one of four specialized sub-agents. The module was forked from the NVIDIA AI Blueprint and adapted to use [[OpenRouter]] / [[Qwen3-max]] for development and NVIDIA NIM as fallback for production.

## Entry Points

- `server.py:app` — FastAPI application; start with `uvicorn src.hotel_guardrails.server:app --port 8081`
- `hotel_langgraph.py:invoke_hotel_agent()` — async function to invoke the graph directly (used by tests)

## Public API (Endpoints)

| Group | Methods | Path(s) |
|---|---|---|
| Health | GET | `/health`, `/healthz` |
| Auth | POST | `/auth/register`, `/auth/login`, `/auth/logout` — PATCH `/auth/me/password` |
| Chat | POST | `/chat`, `/chat/stream` (SSE) |
| Rooms | GET | `/rooms`, `/rooms/{id}`, `/rooms/availability` |
| Booking | GET/POST/PATCH/DELETE | `/bookings`, `/bookings/{id}` |
| Tools | POST | `/tools/book` |
| Guests | GET/POST/PATCH | `/guests`, `/guests/{id}` |
| Sessions | GET/POST/DELETE | `/sessions`, `/sessions/{id}` |
| Feedback | POST | `/feedback` |
| Settings | GET/PATCH | `/settings/llm` |
| Admin | GET/POST/PATCH | `/admin/*` (requires admin JWT) |
| Dashboard | GET | `/dashboard/*` (requires admin JWT) |

## Internal Structure

| File | Role |
|---|---|
| `server.py` | FastAPI app wiring, lifespan startup/shutdown, all endpoint handlers |
| `hotel_langgraph.py` | LangGraph graph definition — `HotelState`, 4 sub-agent handler functions, entry nodes, tool nodes, quality retry loop |
| `hybrid_router.py` | Safety pre-filter: blocks harmful patterns, classifies complexity for metrics, routes everything to LangGraph |
| `langgraph_adapter.py` | Server-to-graph bridge; supports embedded (default) or legacy HTTP mode via `LANGGRAPH_MODE` env var |
| `actions.py` | RAG tool wrappers: `search_hotel_knowledge`, `search_hotel_knowledge_with_sources`, and booking shims used by `server.py` directly |
| `database.py` | PostgreSQL ops via psycopg2 `ThreadedConnectionPool` — rooms, bookings, sessions, guests, users, audit log |
| `config.py` | Pydantic Settings (`LLMSettings`, `ServerSettings`, `RerankerSettings`); `RuntimeLLMConfig` singleton; `AVAILABLE_MODELS` catalog |
| `openrouter_llm.py` | `get_openrouter_llm()` factory — dispatches to Ollama or OpenRouter based on `RuntimeLLMConfig` |
| `models.py` | All Pydantic request/response schemas (30+ models covering chat, rooms, bookings, guests, auth, admin) |
| `auth.py` | JWT (HS256) + bcrypt; in-memory token blocklist; per-IP and per-username login rate limiting; account lockout |
| `audit.py` | Structured audit log written to PostgreSQL — every admin mutation and privacy-sensitive read |
| `feedback_collector.py` | Three feedback types (explicit/implicit/automated) stored to JSON; provides historical score to `HybridRouter` |
| `chat_scaling.py` | Concurrency limiter, per-session asyncio lock, sliding-window rate limiter, SSE connection cap, TTL+LRU knowledge cache |
| `pii_redactor.py` | Regex PII scrubber (credit card, Thai national ID, passport, phone, email) applied before sending text to LLM |
| `escalation.py` | Auto-escalation monitor — triggers on frustration keywords (EN+TH), repetition (3+ similar messages), or high-value bookings >50K THB |

### NeMo Guardrails config directory

> [!contradiction]
> CLAUDE.md describes a `config/` subdirectory with `config.yml`, `prompts.yml`, and `rails.co`. **This directory does not exist in the current codebase.** The NeMo Guardrails runtime is not active; safety is handled entirely by regex patterns in `hybrid_router.py`. Prompts are loaded from `src/agent/hotel_prompt.yaml`. See [[nemo_guardrails_config]] gap note.

## Dependencies

### External packages
- `fastapi`, `uvicorn` — HTTP server
- `langchain-openai`, `langgraph` — agent orchestration
- `psycopg2`, `psycopg-pool` — PostgreSQL sync and async pool
- `pydantic`, `pydantic-settings` — config and validation
- `bcrypt`, `PyJWT` — authentication
- `yaml` — prompt file loading

### Internal modules
- `src/agent/hotel_tools.py` — booking + service tool functions imported directly into `hotel_langgraph.py`
- `src/retrievers/hotel_knowledge/` — RAG chain (Qdrant + reranker) called from `actions.py`

## Used By

- [[Railway]] production deployment (via `Procfile` / `railway.toml`)
- Docker Compose dev stack (`deploy/compose/docker-compose.dev.yaml`)
- Test suite (`scripts/test_chat.py`, `scripts/eval/run_evaluation.py`, DeepEval runner)

## Notes & Gotchas

- **No `config/` NeMo directory** — see contradiction callout above.
- **LangGraph mode is `embedded` by default.** The HTTP mode (separate LangGraph server on port 8090) is legacy.
- **Checkpointer fallback:** PostgreSQL (`AsyncPostgresSaver`) when `DATABASE_URL` is set; falls back to in-memory `MemorySaver`. Railway multi-worker deployments need external checkpointer or will have split session state.
- **Tool-call leak detection.** Local 9B Ollama model sometimes prints tool-call JSON as plain text. `has_tool_leak()` detects and retries — up to 2 retries for Ollama, 1 for cloud models.
- **Runtime model switching** via `PATCH /settings/llm` changes `RuntimeLLMConfig` singleton in-process with no restart required.
- **PII scrubbing** happens inside `/chat` before the message reaches LangGraph.
- **Audit trail** is PostgreSQL-backed; token blocklist is in-memory (not Redis), so logout tokens are re-valid after server restart.
- **`openrouter_llm.py` ref note:** The file still contains the old referer `siam-serenity-hotel.com` rather than `grand-horizon-hotel.com` — minor brand inconsistency.

## Related

- [[flows/hotel_chat_pipeline]] — end-to-end `/chat` request flow
- [[components/hotel_langgraph]] — the state machine
- [[components/hybrid_router]] — safety pre-filter
- [[concepts/langgraph_state_machine_architecture]]
- [[concepts/sub_agent_routing]]
- [[concepts/safety_pre_filter]]
