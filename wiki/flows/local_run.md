---
type: flow
status: active
entry_point: "docker compose up"
endpoints:
  - "http://localhost:8088"
  - "http://localhost:8088/docs"
  - "http://localhost:11435"
  - "http://localhost:5433"
  - "http://localhost:6380"
  - "http://localhost:6334"
involves:
  - hotel_guardrails
  - Ollama
  - PostgreSQL
  - Redis
  - Qdrant
created: 2026-04-19
updated: 2026-04-19
tags: [flow, local, docker, dev, ops]
---

# Flow: Local Run (Docker Stack)

The `hotel` Docker Compose stack brings up all five containers needed for local development and demo. Uses the Ollama-backed LLM (free, local GPU).

## Docker containers

| Container | Port | Service |
|---|---|---|
| `hotel-ollama` | 11435 | Local LLM — `qwen3.5-opus:9b` |
| `hotel-db` | 5433 | PostgreSQL (hotel database) |
| `hotel-redis` | 6380 | Redis (session cache) |
| `hotel-qdrant` | 6334 | Qdrant (knowledge vectors) |
| `hotel-api` | 8088 | FastAPI server (hotel_guardrails) |

Note: ports are offset from the NVIDIA blueprint defaults to allow parallel stacks.

## Start the stack

```bash
# Start all containers
docker compose -p hoteai -f deploy/compose/docker-compose.hotel.yaml --env-file .env up -d

# Verify health
curl http://localhost:8088/healthz
curl http://localhost:8088/health
```

## Populate hotel data

```bash
# Generate demo rooms, bookings, guests
docker compose -p hoteai -f deploy/compose/docker-compose.hotel.yaml --env-file .env \
  exec hotel-api python scripts/generate_hotel_dataset.py

# Ingest hotel knowledge base into Qdrant
docker compose -p hoteai -f deploy/compose/docker-compose.hotel.yaml --env-file .env \
  exec hotel-api python scripts/ingest_hotel_knowledge.py
```

## Run tests

```bash
python scripts/test_hotel_workflow.py
```

Test suite breakdown (94% pass rate):

| Part | Tests | Description |
|---|---|---|
| A | 7/7 | Infrastructure, model switching, rooms |
| B | 6/6 | Knowledge/RAG (breakfast, WiFi, spa, pets, transport) |
| C | 9/10 | Full booking lifecycle (create, confirm, update, cancel) |
| D | 4/4 | Advanced scenarios (multi-room, natural dates, Thai) |
| E | 3/4 | Service requests (towels, spa, airport) |
| F | 3/3 | Edge cases (past dates, max guests, off-topic) |

## Swagger UI

`http://localhost:8088/docs` — full OpenAPI spec with 52 endpoints. Source: `docs/api_references/openapi.json`.

## LLM backend switching

Switch model at runtime without restart:

```bash
# Switch to Ollama (local, free)
curl -X PUT http://localhost:8088/settings/llm \
  -H "Authorization: Bearer <admin-JWT>" \
  -H "Content-Type: application/json" \
  -d '{"backend": "ollama", "model": "qwen3.5-opus:9b"}'

# Switch to OpenRouter (cloud)
curl -X PUT http://localhost:8088/settings/llm \
  -H "Authorization: Bearer <admin-JWT>" \
  -H "Content-Type: application/json" \
  -d '{"backend": "openrouter", "model": "qwen/qwen3-max"}'
```

Per-model presets are applied automatically (temperature, max_tokens, thinking mode, rate limiter).

## LLM backends

```
  Ollama (local)                     OpenRouter (cloud)
  qwen3.5-opus:9b                    qwen/qwen3-max
  port 11435                         minimax-m2.7
  FREE                               any model
       │                                  │
       └────── PUT /settings/llm ─────────┘
               switchable at runtime
               no restart needed
```

Cloud backend: 20 req/min rate limiter applied automatically.

## Environment variables (key)

| Variable | Purpose |
|---|---|
| `DEFAULT_ADMIN_USERNAME` | Seeded admin username (default: `admin`) |
| `DEFAULT_ADMIN_PASSWORD` | Seeded admin password (default: `admin123` — **change in prod**) |
| `JWT_SECRET` | JWT signing secret (**change in prod**) |
| `OPENROUTER_API_KEY` | Required if using OpenRouter backend |
| `DATABASE_URL` | PostgreSQL connection (default: `hotel-db:5432`) |
| `MAX_CONCURRENT_LLM_CALLS` | LLM semaphore slots (default: 4) |
| `OLLAMA_NUM_PARALLEL` | Ollama parallel request slots (set in docker-compose, default: 4) |
| `RERANKER_BACKEND` | `none` (default), `qwen`, `nvidia` |

## Original NVIDIA blueprint (parallel stack)

```bash
# Full NVIDIA NIM stack
docker compose -f deploy/compose/docker-compose.yaml up -d

# Dev stack with OpenRouter + Railway-hosted Qdrant/PostgreSQL
docker compose -f deploy/compose/docker-compose.dev.yaml up -d
```

## Uvicorn (bare metal, no Docker)

```bash
# hotel_guardrails service
python -m uvicorn src.hotel_guardrails.server:app --host 0.0.0.0 --port 8081 --reload

# Original NVIDIA agent
python -m uvicorn src.agent.server:app --host 0.0.0.0 --port 8081 --reload
```

## Data ingestion (Jupyter)

```bash
jupyter lab --allow-root --ip=0.0.0.0 --port=8889
# Then run notebooks/ingest_data.ipynb
```

## Related

- [[guest_chat]] — what the running stack serves
- [[chat_scaling]] — concurrency config for the API server
- [[Ollama]] — local LLM entity
- [[Qdrant]] — vector store entity
- [[decisions/ollama_migration]] — why Ollama replaced NVIDIA NIM for local dev
