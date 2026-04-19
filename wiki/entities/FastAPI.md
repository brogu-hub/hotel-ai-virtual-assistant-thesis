---
type: entity
category: library
url: https://fastapi.tiangolo.com
tags: [entity, library, webframework, python]
created: 2026-04-19
updated: 2026-04-19
---

# FastAPI

## What it is

FastAPI is a modern Python web framework for building APIs, based on Starlette and Pydantic, with automatic OpenAPI documentation.

## Role in this project

FastAPI is the HTTP server framework used by every service that exposes a REST endpoint:
- `src/hotel_guardrails/server.py` — primary entry point (port 8081)
- `src/agent/server.py` — original blueprint agent server (port 8081)
- `src/analytics/` — analytics server (port 8082)
- `src/api_gateway/` — HTTP proxy (port 9000)
- `src/retrievers/*/` — retriever microservices (ports 8086, 8087)

## Key facts

- Served via uvicorn: `python -m uvicorn src.hotel_guardrails.server:app --host 0.0.0.0 --port 8081 --reload`
- Health check: `GET /healthz` (hotel_guardrails)
- Chat endpoint: `POST /chat`

## Related

- [[hotel_guardrails]]
- [[agent]]
- [[analytics]]
- [[api_gateway]]
