---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, langgraph, statemachine, routing, agents]
created: 2026-04-19
updated: 2026-04-19
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

- `build_hotel_graph(checkpointer)` — compiles and returns the `StateGraph`
- `get_hotel_graph(checkpointer)` — singleton accessor
- `invoke_hotel_agent(message, session_id, ...)` — async entry point with retry loop
- `has_tool_leak(text)` — quality guard regex check
- `init_checkpointer()` / `close_checkpointer()` — lifecycle management

## Related

- [[components/primary_assistant]] — the router node
- [[components/booking_subagent]], [[components/service_subagent]], [[components/knowledge_subagent]], [[components/other_talk_subagent]]
- [[components/langgraph_adapter]] — calls `invoke_hotel_agent()`
- [[concepts/langgraph_state_machine_architecture]]
- [[concepts/sub_agent_routing]]
