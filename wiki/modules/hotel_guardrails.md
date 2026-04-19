---
type: module
path: src/hotel_guardrails/
status: active
language: python
purpose: "Primary hotel AI assistant — hybrid NeMo Guardrails + LangGraph service"
maintainer: Mangakorian
last_updated: 2026-04-19
depends_on: [common, retrievers]
used_by: []
linked_issues: []
tags: [module, hotel_guardrails, active]
created: 2026-04-19
updated: 2026-04-19
---

# hotel_guardrails

## Purpose

The actively-developed hotel AI virtual assistant service for [[The Grand Horizon Hotel]]. Implements a hybrid architecture combining [[NeMo Guardrails]] safety filtering with a [[LangGraph]] state machine for multi-turn hotel customer service.

## Entry points

- `server.py` — FastAPI app, `POST /chat`, `GET /healthz`. Main deployment artifact.
- `hybrid_router.py` — Safety check → route to LangGraph
- `hotel_langgraph.py` — LangGraph StateGraph definition

## Public API

- `POST /chat` — accepts user message + session ID, returns assistant response
- `GET /healthz` — health check (used by Railway)

## Internal structure

| File | Role |
|---|---|
| `server.py` | FastAPI app, uvicorn entry point |
| `hotel_langgraph.py` | StateGraph: primary_assistant → 4 sub-agents |
| `hybrid_router.py` | Safety filter → LangGraph dispatch |
| `langgraph_adapter.py` | Bridges server ↔ LangGraph |
| `actions.py` | Tool functions: availability, reservations, RAG search, safety |
| `database.py` | PostgreSQL CRUD for rooms, bookings, guests |
| `openrouter_llm.py` | OpenRouter LLM wrapper (dev mode) |
| `feedback_collector.py` | Response quality feedback collection |
| `config/config.yml` | NeMo Guardrails main config |
| `config/prompts.yml` | Guardrails prompt templates |
| `config/rails.co` | Colang rail definitions |

## Dependencies

- External: [[FastAPI]], [[LangGraph]], [[NeMo Guardrails]], [[OpenRouter]], [[PostgreSQL]], [[Redis]]
- Internal: [[common]]

## Used by

- Deployed to [[Railway]] as the primary service

## Notes & gotchas

- Prompts in upstream blueprint were tuned for Llama 3.1/3.3; may need adjustment when using [[Qwen3-max]]
- `hybrid_router.py` runs safety checks first; unsafe requests never reach LangGraph

## Related

- [[Chat Request Flow]]
- [[ADR Hybrid Architecture]]
- [[ADR OpenRouter Dev Backend]]
- [[ADR 4 Sub-agent Split]]
