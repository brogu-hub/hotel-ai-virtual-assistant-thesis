---
type: module
path: src/agent/
status: legacy
language: python
purpose: "Original NVIDIA blueprint agent — retail customer service reference implementation"
maintainer: Mangakorian
last_updated: 2026-04-19
depends_on: [common, retrievers]
used_by: []
linked_issues: []
tags: [module, agent, nvidia-blueprint, legacy, langgraph]
created: 2026-04-19
updated: 2026-04-19
---

# agent

## Purpose

The original [[NVIDIA]] AI Blueprint customer-service agent, retained as-is for comparison and reference. Targets the gear-store / retail use-case: product Q&A, order status, and return processing. Uses [[LangGraph]] with NVIDIA NIM endpoints and a PostgreSQL datastore. Runs on the same port (8081) as [[hotel_guardrails]] — only one runs at a time.

The fork added `hotel_tools.py` and `hotel_prompt.yaml` as hotel-domain overlays without modifying the original graph logic.

> [!note] Development status
> `hotel_guardrails` is the actively-developed service. The `agent` module is not being extended; it serves as the baseline comparison system in the thesis.

## Entry points

- `server.py:app` — FastAPI app, port 8081
- `main.py:graph` — compiled `StateGraph`, imported by server at startup via `EXAMPLE_PATH` env var dynamic load

## Public API / Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Liveness probe |
| GET | `/metrics` | Prometheus metrics |
| GET | `/create_session` | Allocate session UUID (Redis + PostgreSQL) |
| GET | `/end_session` | Flush session to permanent store |
| DELETE | `/delete_session` | Destroy session and checkpointer state |
| POST | `/generate` | Main inference endpoint — streaming SSE |
| POST | `/feedback/response` | Store user thumbs-up/-down feedback |

The `/generate` endpoint accepts a `Prompt` payload (`messages[]`, `user_id`, `session_id`) and returns `text/event-stream` (SSE). Input is HTML-sanitized via `bleach` and non-ASCII characters are stripped.

## Internal structure

| File | Role |
|---|---|
| `main.py` | `StateGraph` definition — nodes, conditional edges, graph compilation with PostgreSQL checkpointer |
| `server.py` | FastAPI server, session management, streaming response generator |
| `tools.py` | LangChain `@tool` functions + Pydantic routing classes |
| `hotel_tools.py` | Hotel CRUD tools + dynamic pricing + RAG search (fork addition) |
| `utils.py` | `get_product_name`, `canonical_rag`, `create_tool_node_with_fallback`, `get_checkpointer` |
| `prompt.yaml` | System prompt templates for all agents (NVIDIA Gear Store context) |
| `hotel_prompt.yaml` | Hotel-specific prompt overrides (bilingual Thai/English, Grand Horizon Hotel) |
| `datastore/datastore.py` | PostgreSQL conversation persistence |
| `datastore/postgres_client.py` | Low-level psycopg2 client |
| `cache/session_manager.py` | Redis-backed session cache |
| `cache/redis_client.py` | Redis client wrapper |
| `cache/local_cache.py` | In-memory fallback cache |

## Graph state

```
State: TypedDict {
  messages: list[AnyMessage]   # add_messages reducer
  user_id: str
  user_purchase_history: Dict
  current_product: str
  needs_clarification: bool
  clarification_type: str      # "no_product" | "multiple_products"
  reason: str
}
```

## Sub-agents / nodes

- [[agent_validate_product_info]] — pre-routing validator, resolves product from purchase history
- [[agent_router]] — `primary_assistant` node, routes to specialized sub-agents
- [[agent_product_qa]] — ProductQA via `canonical_rag`
- [[agent_order_status]] — order lookup via `structured_rag`
- [[agent_return_processing]] — returns workflow with human-in-the-loop interrupt

## Tools

- [[agent_tools]] — `structured_rag`, `get_purchase_history`, `return_window_validation`, `update_return`, routing Pydantic classes
- [[agent_hotel_tools]] — hotel CRUD tools and `search_hotel_knowledge` (fork addition, cross-references [[hotel_guardrails]])

## Prompt files

- `prompt.yaml` — five templates: `primary_assistant_template`, `other_talk_template`, `return_processing_template`, `order_status_template`, `rag_template`. Tuned for [[Llama 3.3 70B]] / NVIDIA NIM.
- `hotel_prompt.yaml` — single `main_prompt` with Thai/English language rules, Thai politeness-particle enforcement, and tool-call instructions for hotel domain.

## Dependencies

- External: [[FastAPI]], [[LangGraph]], [[NVIDIA]] NIM, [[Milvus]], [[Vanna.AI]], `bleach`, `prometheus_client`, `psycopg2`, `nest_asyncio`
- Internal: [[common]] (`get_llm`, `get_prompts`, `get_config`), [[retrievers]] (structured + unstructured)

## Notes & gotchas

- `nest_asyncio.apply()` is called at module import time — required because the graph builds a Postgres checkpointer asynchronously at startup
- Return processing uses `interrupt_before=["return_processing_sensitive_tools"]` — human-in-the-loop confirmation before `update_return` writes to DB
- `graph.get_graph(xray=True).draw_mermaid_png()` is called on startup; failure is silently swallowed
- `GRAPH_RECURSION_LIMIT` (default 6) and `GRAPH_TIMEOUT_IN_SEC` are env-configurable
- `hotel_tools.py` imports from `src.hotel_guardrails.chat_scaling` at runtime — creates a hard dependency on the other service if used
- `structured_rag` and several other tools use `@lru_cache` — identical queries within a process lifetime hit memory, not the retriever

## Related

- [[agent_chat_pipeline]] — end-to-end flow diagram
- [[hotel_guardrails]] — the parallel, actively-developed service
- [[guest_chat]] — hotel_guardrails equivalent flow
