---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, langgraph, statemachine, routing, agents, memory]
created: 2026-04-19
updated: 2026-04-20
---

# hotel_langgraph — LangGraph State Machine

## Purpose

Defines and compiles the `StateGraph` that is the brain of the hotel assistant. Every valid chat message enters the graph, is routed by `primary_assistant` to exactly one of four sub-agents, and exits with a response. The graph supports multi-turn conversation via a checkpointer that persists `HotelState` across requests.

## State: `HotelState`

TypedDict with LangGraph `add_messages` annotation:

| Field | Type | Purpose |
|---|---|---|
| `messages` | `List[AnyMessage]` | Full conversation thread (managed by checkpointer) |
| `session_id` | `str` | Conversation/thread identifier |
| `user_id` | `str` | Guest identifier |
| `language` | `str` | `'th'`, `'en'`, or `'auto'` |
| `current_intent` | `str` | Set by sub-agents: `booking`, `service`, `knowledge`, `other` |
| `tool_calls_made` | `List[Dict]` | Accumulator of tool invocations this turn |

## Graph Topology

```
START
  └─► primary_assistant
        ├─► enter_booking ─► hotel_booking ⇄ booking_tools
        ├─► enter_service ─► hotel_service ⇄ service_tools
        ├─► enter_knowledge ─► hotel_knowledge ─► END
        └─► enter_other    ─► other_talk     ─► END
```

**Entry nodes** (`enter_*`) are synthetic `ToolMessage` injection nodes that convert the primary assistant's routing tool-call into a valid message before handing off to the sub-agent. This is required because LangGraph expects every `tool_call` to be followed by a `ToolMessage` before the next `AIMessage`.

**Tool loops:** `hotel_booking` and `hotel_service` can call tools and loop back to themselves until they decide to END. `hotel_knowledge` and `other_talk` go directly to END (no tool loop).

## Routing Tools (Pydantic models used as LangGraph tools)

| Tool | Routes to |
|---|---|
| `ToHotelBooking` | `enter_booking` |
| `ToHotelService` | `enter_service` |
| `ToHotelKnowledge` | `enter_knowledge` |
| `HandleOtherTalk` | `enter_other` |

The primary assistant is instructed to **always route** — never answer directly. This is enforced in the system prompt with explicit Thai-language examples because the 9B model needs concrete examples to get edge cases right (e.g., "ยกเลิกการจอง" → booking, not other_talk).

## LLM Factory: `get_llm()`

Reads `RuntimeLLMConfig` singleton to dispatch to either:

- **Ollama:** `ChatOpenAI` pointing at `ollama_base_url` with a dummy API key
- **OpenRouter:** `ChatOpenAI` pointing at OpenRouter with HTTP headers (`HTTP-Referer`, `X-Title`) and optional `reasoning` body param for thinking models

Per-call overrides for temperature and max_tokens come from `config.configurable.llm_settings`.

## Checkpointer

Initialised by `init_checkpointer()` at server startup:

- `APP_CHECKPOINTER_NAME=postgres` (default) → `AsyncPostgresSaver` with `AsyncConnectionPool` (min 2, max 10)
- Fallback or `APP_CHECKPOINTER_NAME=memory` → `MemorySaver`

The checkpointer is passed into `build_hotel_graph()` at compile time and maps `thread_id` → `session_id`.

## Quality Retry Loop

`invoke_hotel_agent()` wraps graph invocation with a retry loop:

1. Invoke graph.
2. Extract last `AIMessage` content.
3. Run `has_tool_leak(text)` — regex check for leaked tool-call syntax.
4. If empty or leaked and retries remain → retry (re-invokes with same session, checkpointer provides history).
5. Retry budget: 2 for Ollama 9B models, 1 for cloud OpenRouter models.

The `had_leak` and `retries` counters are returned in the result dict for observability.

## Prompts

Loaded at runtime from `src/agent/hotel_prompt.yaml` (tries three paths for Railway compatibility). Falls back to an inline default. Bangkok timezone (GMT+7) date/time is injected as `{current_date}`, `{current_time}`, `{current_month}` at load time.

## Key Functions

- `build_hotel_graph(checkpointer, store=None)` — compiles and returns the `StateGraph`, now accepts a `store` for long-term memory
- `get_hotel_graph(checkpointer, store=None)` — singleton accessor, store-aware
- `invoke_hotel_agent(message, session_id, user_id='guest', ...)` — async entry point with retry loop
- `has_tool_leak(text)` — quality guard regex check
- `strip_tool_call_codeblocks(text)` — post-processor that removes three observed local-9B tool-call leak shapes (fenced code blocks, `<call_TOOL(...)>`, dangling truncations). See [[tool_call_codeblock_leak]].
- `init_checkpointer()` / `close_checkpointer()` — short-term plane lifecycle
- `init_store()` / `close_store()` — **new** long-term plane lifecycle, uses a separate `AsyncConnectionPool` so store contention cannot starve checkpoint writes
- `prune_anon_memory(max_age_days=30)` — TTL sweeper for `("anon", session_id)` namespaces. See [[anon_namespace_ttl]].
- `load_guest_memory(state)` — reads the four memory keys (`profile`, `preferences`, `recent_bookings_summary`, `service_history_summary`) from the appropriate namespace
- `upsert_guest_memory(state, key, value)` — write-through helper
- `_render_memory_preamble(memory)` — renders the compact "Known about this guest: …" block injected into every sub-agent prompt
- `_extract_prefs_from_text(state, text)` — rule-based EN+TH keyword extraction from free text (zero LLM calls)
- `_extract_facts_from_tool_calls(state, result)` — extracts structured facts from `create_reservation` and `create_service_request` tool-call args
- `_memory_namespace(state)` — returns `("guest", user_id)` when authenticated, else `("anon", session_id)`

## Memory: Dual-Plane Architecture (added 2026-04-20)

> [!key-insight]
> The 2026-04-20 commit adds a **long-term memory plane** on top of the existing short-term checkpointer. The two planes share PostgreSQL but use separate connection pools, separate tables, and separate lifecycle hooks. This is the thesis novel contribution — see [[thesis/memory_system_design]].

### Plane 1 — Short-Term (pre-existing)

`AsyncPostgresSaver` + `AsyncConnectionPool(min=2, max=10)`. Keyed by `thread_id = session_id`. Writes full `HotelState` snapshots to `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` after every node transition. Fallback: `MemorySaver`.

### Plane 2 — Long-Term (new)

`AsyncPostgresStore` + `AsyncConnectionPool(min=1, max=5)`. Namespaced by `("guest", user_id)` or `("anon", session_id)`. Writes four small keys (`profile`, `preferences`, `recent_bookings_summary`, `service_history_summary`) to `store`. Fallback: `InMemoryStore` when `langgraph-checkpoint-postgres < 2.0.13` (store module absent).

### Memory read → preamble injection

Every sub-agent (`handle_booking`, `handle_service`, `handle_knowledge`, `handle_other_talk`) and the primary router call `load_guest_memory(state)` on entry, then inject `_render_memory_preamble(memory)` as a system-level context block into their prompt template. A returning guest with `user_id=alice-123` starting a fresh `session_id` recovers name, preferences, allergies, recent-booking summary, and service history on the very first turn.

### Memory write-back — rule-based, zero extra LLM calls

Two paths populate Plane 2:

1. **Free-text path** — `_extract_prefs_from_text()` scans each `HumanMessage` against English and Thai keyword tables. Hits upsert the `preferences` key. See [[bilingual_memory_extraction]].
2. **Tool-call path** — `_extract_facts_from_tool_calls()` inspects `AIMessage.tool_calls` for `create_reservation` / `create_service_request` and extracts structured facts (room type, dates, service type, etc.) from the args. No LLM summariser in v1. See [[rule_based_memory_write_back]].

### Anonymous namespace TTL

`prune_anon_memory(max_age_days=30)` issues a parameterised `DELETE FROM store WHERE prefix LIKE 'anon.%%' AND updated_at < NOW() - (%s * INTERVAL '1 day')`. Scheduled by the FastAPI lifespan at `server.py` (24h interval). See [[anon_namespace_ttl]].

### Env controls

| Variable | Default | Options | Effect |
|---|---|---|---|
| `APP_CHECKPOINTER_NAME` | `postgres` | `postgres` / `memory` | Short-term backend |
| `APP_STORE_NAME` | `postgres` | `postgres` / `memory` / `off` | Long-term backend |
| `DATABASE_URL` | — | PostgreSQL URI | Shared by both planes |

### Validation

27/27 cases passed in the new `memory` test suite on local Qwen3.5-Opus-9B. See [[memory-test-suite-2026-04-20]].

## Related

- [[components/primary_assistant]] — the router node (now memory-aware)
- [[components/booking_subagent]], [[components/service_subagent]], [[components/knowledge_subagent]], [[components/other_talk_subagent]] — all four now load memory on entry and write back
- [[components/langgraph_adapter]] — forwards `store` argument into `get_hotel_graph()`
- [[components/server]] — lifespan wires `init_store`/`close_store` + schedules the 24h anon sweeper
- [[concepts/langgraph_state_machine_architecture]]
- [[concepts/dual_plane_memory]] — the two-plane model explained
- [[concepts/rule_based_memory_write_back]] — zero-LLM extraction
- [[concepts/bilingual_memory_extraction]] — Thai + English keyword tables
- [[concepts/tool_call_codeblock_leak]] — the three leak shapes and the post-processor
- [[concepts/anon_namespace_ttl]] — GDPR-motivated anonymous TTL
- [[flows/cross_session_memory]] — end-to-end sequence diagram
- [[thesis/memory_system_design]] — thesis-grade write-up
