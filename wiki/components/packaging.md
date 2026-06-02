---
type: component
path:
  - "src/hotel_guardrails/Dockerfile"
  - "src/hotel_guardrails/requirements.txt"
  - "railway.toml"
  - "Procfile"
status: active
parent_module: hotel_guardrails
tags: [component, packaging, docker, railway, deploy, python-312]
date_ingested: 2026-04-20
---

# packaging — Docker, Requirements, Railway Deploy

## Purpose

Captures everything needed to ship the hotel assistant to production as a single container on [[Railway]] (and by extension any Docker host).

## Dockerfile (`src/hotel_guardrails/Dockerfile`, 41 lines)

- **Base**: `python:3.12-slim` (see [[decisions/python_312_runtime]])
- **Env**: `PYTHONDONTWRITEBYTECODE=1`, `PYTHONUNBUFFERED=1`
- **System deps**: `build-essential`, `curl` (for healthcheck)
- **Layer ordering** (for cache): `requirements.txt` copied and installed **before** source, so source edits don't invalidate the pip layer.
- **Source copied**:
  - `src/common` — LLM wrappers, embeddings, rerankers, vector stores
  - `src/hotel_guardrails` — the service itself
  - `src/retrievers` — RAG microservice code (imported by the knowledge sub-agent)
  - `src/agent/hotel_tools.py` + `hotel_prompt.yaml` — tool and prompt reuse from the original NVIDIA agent
  - `data/hotel/` — the knowledge-base corpus (see [[references/hotel_knowledge_base]])
- **Port**: `EXPOSE 8081`
- **Healthcheck**: `curl -f http://localhost:8081/healthz` every 30s (10s timeout, 60s grace, 3 retries)
- **Start command**: `uvicorn src.hotel_guardrails.server:app --host 0.0.0.0 --port ${PORT:-8081}` — Railway injects `PORT`, falling back to 8081 elsewhere.

## requirements.txt (48 lines)

Pinned dependencies for reproducibility. Key versions after the 2026-04-20 commit:

| Package | Version | Note |
|---|---|---|
| `fastapi` | 0.115.2 | Server framework |
| `langgraph` | 0.2.32 | State machine |
| `langchain` | 0.3.0 | Tool / chain primitives |
| `langgraph-checkpoint-postgres` | `>=2.0.13,<3.0.0` | **Bumped from 2.0.0** — now ships `langgraph.store.postgres.AsyncPostgresStore` required for [[dual_plane_memory]] |
| `psycopg-binary` | 3.2.3 | Async PostgreSQL driver for both planes |
| `psycopg-pool` | 3.2.2 | Separate `AsyncConnectionPool` for checkpointer and store |
| `qdrant-client` | `>=1.7.0` | Vector store (dev) |
| `langchain-qdrant` | `>=0.1.0` | LangChain Qdrant adapter |
| `sentence-transformers` | `>=3.0.0` | Multilingual embeddings (dev) |
| `sse-starlette` | `>=1.8.0` | SSE for `/chat/stream` |
| `bleach` | 6.1.0 | HTML sanitisation in output path |

`psycopg2-binary` is also pinned for compatibility with older sync code paths; the async path uses `psycopg3`.

## railway.toml (14 lines)

```toml
[build]
builder = "dockerfile"
dockerfilePath = "src/hotel_guardrails/Dockerfile"

[deploy]
healthcheckPath = "/healthz"
healthcheckTimeout = 60
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 3
```

- **Dockerfile build** (not Nixpacks) for full control over the image.
- **Health path**: `/healthz` — the fast probe that does not touch PostgreSQL or Qdrant.
- **Restart policy**: only on failure, capped at 3 retries to avoid crash loops consuming Railway budget.

## Procfile (1 line)

```
web: uvicorn src.hotel_guardrails.server:app --host 0.0.0.0 --port ${PORT:-8081}
```

Used by Railway's web-service detection as a fallback if the Dockerfile is ever disabled.

## Port drift

> [!note]
> The project has three documented ports for what is ultimately the same service:
> - `8081` — bare-metal uvicorn and Dockerfile default
> - `8088` — docker-compose mapping (see [[flows/local_run]])
> - Railway-assigned `${PORT}` — production
>
> The CLAUDE.md env table lists `8081`, which matches bare-metal and Docker but not docker-compose. Mention this in the thesis deployment appendix; don't try to unify — all three are intentional.

## Build reproducibility notes

- Version pins are exact for all critical packages; unpinned only where minor-bump compatibility has been confirmed.
- The build context is the repo root (not `src/hotel_guardrails`) so the Dockerfile can pull in `src/common`, `src/agent`, `src/retrievers`, and `data/hotel/` siblings.
- `touch /app/src/__init__.py` ensures the repo-root-rooted package imports resolve after the selective `COPY`.

## Related

- [[decisions/railway_deployment]] — why Railway
- [[decisions/python_312_runtime]] — why 3.12
- [[flows/local_run]] — docker-compose dev stack
- [[entities/Railway]]
- [[entities/FastAPI]]
- [[entities/PostgreSQL]]
- [[entities/Qdrant]]
- [[components/server]] — the entry point the container runs
