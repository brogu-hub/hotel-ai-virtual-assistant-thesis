---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, memory, postgres-store, lifecycle, novel-contribution]
date_ingested: 2026-04-20
---

# guest_memory_store — Long-Term Memory Store Lifecycle

> [!note]
> This is a function-level view of the long-term memory plane. For the architecture-level story see [[concepts/dual_plane_memory]] and [[thesis/memory_system_design]]; for the integration with sub-agents see [[components/hotel_langgraph]].

## Scope

Four functions in `src/hotel_guardrails/hotel_langgraph.py` that own the lifecycle and access of the `AsyncPostgresStore`:

| Function | Line | Purpose |
|---|---|---|
| `init_store()` | 1024 | Create the `AsyncConnectionPool` and `AsyncPostgresStore`, open the pool, run the store's migrations. Sets process-level `_store` and `_store_pool`. |
| `close_store()` | 1085 | Close the store, close the pool. Idempotent; lifespan-safe. |
| `load_guest_memory(state)` | 599 | Read the four memory keys for the namespace selected by `_memory_namespace(state)`. |
| `upsert_guest_memory(state, key, value)` | 612 | Write a key under the same namespace. Used by both extractors. |
| `_memory_namespace(state)` | 591 | Select `("guest", user_id)` or `("anon", session_id)` per the identity rules in [[anon_namespace_ttl]]. |

## Pool isolation

The store uses its **own** `AsyncConnectionPool` (`min=1, max=5`), distinct from the checkpointer pool (`min=2, max=10`). The two pools share the same `DATABASE_URL` but not the same connection slots. This is deliberate: a slow store operation cannot starve checkpoint writes, which must respond quickly on every node transition.

## Fallback ladder

`init_store()` tries backends in order:

1. `AsyncPostgresStore` (imports from `langgraph.store.postgres`) — production default.
2. `InMemoryStore` — fallback when `langgraph-checkpoint-postgres < 2.0.13` (store module absent) or `APP_STORE_NAME=memory`.
3. `None` — `APP_STORE_NAME=off`; `load_guest_memory` becomes a no-op returning `{}`.

Each fallback is logged at startup so operators know which backend is active.

## Memory key schema

Read and written by `load_guest_memory` / `upsert_guest_memory`:

| Key | Type | Written by |
|---|---|---|
| `profile` | `dict` — `{name, email, loyalty_tier, language}` | Tool-call extractor |
| `preferences` | `dict` — `{floor, allergy, diet, bed, quiet, pillows, …}` | Free-text extractor |
| `recent_bookings_summary` | `list[dict]` (last 10) | Tool-call extractor |
| `service_history_summary` | `list[str]` (last 10, deduplicated) | Tool-call extractor |

Deduplication and trimming happen inside `upsert_guest_memory` for list-valued keys.

## Concurrency guarantees

PostgreSQL's MVCC ([[PostgreSQL]]) means concurrent upserts from two parallel sub-agents on the same `(guest, user_id)` namespace are safe. The write path uses single-row UPSERT (`INSERT ... ON CONFLICT ... DO UPDATE`); no explicit advisory locks are held.

## Failure handling

- `load_guest_memory` catches exceptions, logs at WARNING, returns `{}` so the sub-agent proceeds with empty context rather than failing the turn.
- `upsert_guest_memory` catches exceptions, logs at WARNING, swallows — write failures never user-visible.

## Integration

- `server.py` lifespan calls `init_store()` after `init_checkpointer()` and schedules `prune_anon_memory` at 24h intervals.
- `langgraph_adapter.py` forwards the `store` handle returned by `init_store()` into `get_hotel_graph(checkpointer, store)`.
- Every sub-agent calls `load_guest_memory(state)` on entry before rendering its prompt.

## Related

- [[concepts/dual_plane_memory]] — architecture
- [[components/hotel_langgraph]] — the parent component
- [[components/memory_preamble_injector]] — how the loaded memory enters sub-agent prompts
- [[components/anon_memory_sweeper]] — the TTL counterpart
- [[flows/cross_session_memory]]
- [[entities/PostgreSQL]]
- [[entities/LangGraph]]
