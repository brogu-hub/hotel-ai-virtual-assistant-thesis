---
type: component
parent_module: agent
path: src/agent/tools.py
status: legacy
tags: [component, agent, tools, rag, postgresql]
created: 2026-04-19
updated: 2026-04-19
---

# agent_tools

The tools module for the [[agent]] service (`src/agent/tools.py`). Provides LangChain `@tool`-decorated functions for data retrieval and mutation, plus Pydantic routing classes used as tool schemas by the LLM.

## Tool functions

| Function | Category | Description |
| --- | --- | --- |
| `structured_rag(query, user_id)` | safe | POST to structured retriever microservice; falls back to `get_purchase_history` on error |
| `get_purchase_history(user_id)` | safe | Direct PostgreSQL query on `customer_data` table, last 15 orders |
| `get_recent_return_details(user_id)` | safe | Thin alias over `get_purchase_history` |
| `return_window_validation(order_date)` | safe | Computes return eligibility; configurable via `RETURN_WINDOW_THRESHOLD_DAYS` (default 15) and `RETURN_WINDOW_CURRENT_DATE` |
| `update_return(user_id, current_product, order_id)` | **sensitive** | Sets `return_status = 'Requested'` in `customer_data`; only called after human approval |

All functions are decorated with both `@tool` and `@lru_cache`. The `lru_cache` memoizes results within a single process lifetime — identical arguments return cached responses without hitting the DB or retriever.

## Routing Pydantic classes

These are registered as tools on the LLM but do not execute actions. The LLM calls them to signal intent to the router.

| Class | Routes to |
| --- | --- |
| `ToProductQAAssistant` | [[agent_product_qa]] |
| `ToOrderStatusAssistant` | [[agent_order_status]] |
| `ToReturnProcessing` | [[agent_return_processing]] |
| `HandleOtherTalk` | `other_talk` node |
| `ProductValidation` | `validate_product_info` node |

## External dependencies

- `structured_rag_uri` — env `STRUCTURED_RAG_URI` (default `http://structured-retriever:8081`) — calls `[[retrievers]]` structured microservice
- PostgreSQL — `CUSTOMER_DATA_DB`, `POSTGRES_USER_READONLY`, `POSTGRES_PASSWORD_READONLY` (read), `POSTGRES_USER`/`POSTGRES_PASSWORD` (write)

## Notes

- `lru_cache` on `@tool` functions means test isolation requires clearing the cache between test runs.
- `structured_rag` silently degrades to `get_purchase_history` on any HTTP error, masking retriever failures.
- `RETURN_WINDOW_CURRENT_DATE` env var allows deterministic testing of the return window without mocking `datetime.now()`.

## Related

- [[agent_hotel_tools]]
- [[agent_order_status]]
- [[agent_return_processing]]
- [[retrievers]]
