---
type: reference
status: active
date_ingested: 2026-04-20
sources:
  - docs/api_references/hotel_guardrails_server.yaml
tags: [reference, api, openapi, rest, hotel-guardrails]
---

# Hotel Guardrails API Reference

> [!note]
> Reference derived from the OpenAPI 3.1 spec at `docs/api_references/hotel_guardrails_server.yaml`. For request/response schemas see [[components/pydantic_models]]; for routing / lifecycle see [[components/server]].

## Identity & versioning

- **OpenAPI version**: 3.1.0
- **API title (per spec)**: "The Grand Horizon Hotel Concierge API" _(previously "Siam Serenity Hotel Concierge API" — naming drift resolved 2026-04-20)_
- **API version**: 1.0.0
- **Base URL**: `http://localhost:8081` (bare-metal) / `:8088` (docker-compose) / Railway-assigned URL (prod)
- **Request tracking**: optional `X-Request-ID` header; auto-generated if absent and echoed in responses

## Endpoint Catalog (20 endpoints, 6 tag groups)

### Health

| Method | Path | Purpose |
|---|---|---|
| GET | `/` | Root — service identity |
| GET | `/healthz` | Simple load-balancer probe (used by Railway, K8s) |
| GET | `/health` | Detailed health — guardrails, Qdrant, OpenRouter subsystem status |

### Chat

| Method | Path | Purpose |
|---|---|---|
| POST | `/chat` | Main entry — routes via [[hybrid_router]] → [[langgraph_adapter]] → [[hotel_langgraph]] |
| POST | `/chat/stream` | Server-Sent Events variant of `/chat` for token-by-token streaming |

Request body: `ChatRequest` — `{message, session_id?, user_id?, language?}`. See [[components/pydantic_models]].

### Rooms

| Method | Path | Purpose |
|---|---|---|
| GET | `/rooms` | List all room types with photos, amenities, base price |
| GET | `/rooms/{room_id}` | Single room lookup |
| GET | `/rooms/availability` | Date-range availability check |

### Bookings

| Method | Path | Purpose |
|---|---|---|
| GET | `/bookings` | List bookings (scoped by guest email) |
| GET | `/bookings/{reservation_id}` | Single booking |
| PATCH | `/bookings/{reservation_id}` | Update booking (dates, room type, etc.) |
| POST | `/tools/book` | Direct booking tool endpoint (bypasses chat) |

### Sessions

| Method | Path | Purpose |
|---|---|---|
| POST | `/sessions` | Create session (returns session_id) |
| GET | `/sessions/{session_id}` | Session metadata |
| DELETE | `/sessions/{session_id}` | End session |
| GET | `/sessions/{session_id}/messages` | Full message history from checkpointer |

Backed by [[dual_plane_memory|Plane 1 PostgresSaver]]; `thread_id = session_id`.

### Settings

| Method | Path | Purpose |
|---|---|---|
| GET | `/settings/llm` | Current LLM backend, model, temperature, runtime overrides |
| GET | `/settings/models` | Available model presets (see [[components/config]]) |

### Feedback

| Method | Path | Purpose |
|---|---|---|
| POST | `/feedback` | Submit response-quality rating (thumbs up/down + comment) |
| GET | `/feedback/stats` | Aggregate feedback counts; consumed by [[components/feedback_collector]] |

## Cross-cutting response headers

- `X-Request-ID` — echoes the client header or returns a UUID
- `Content-Type: application/json` (non-stream) / `text/event-stream` (for `/chat/stream`)

## Error conventions

- `422` — Pydantic validation failure (returns `HTTPValidationError`)
- `500` — Unhandled server error (structured JSON with request ID for correlation via [[components/audit]])
- `503` — Health check failures when a dependency (PostgreSQL, Qdrant, OpenRouter) is unreachable

## Auth posture

Currently **open** for guest `/chat` and `/chat/stream`. Admin surfaces (`/settings/*`, certain `/bookings/*` mutations) require auth per [[components/auth]] and the [[dual_identity_model]] decision. A full auth matrix per endpoint is a follow-up task.

## Streaming details (`/chat/stream`)

Server-Sent Events format. Example:

```bash
curl -X POST http://localhost:8081/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about the spa"}' \
  --no-buffer
```

Each event is a JSON object with `{text, done?}`. Graph invocation runs fully before streaming begins; tokens are then replayed from the final response. See [[components/server]] for the implementation.

## Related

- [[components/server]] — handler bindings
- [[components/pydantic_models]] — request/response shapes
- [[components/auth]] — which endpoints require which identity
- [[flows/guest_chat]] — `/chat` end-to-end flow
- [[flows/cross_session_memory]] — how `user_id` flows through `/chat`
- [[thesis/hotel_ai_chatbot_chapter]] §4.3 — request flow walkthrough
