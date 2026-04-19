---
type: component
path: "src/hotel_guardrails/langgraph_adapter.py"
status: active
parent_module: hotel_guardrails
tags: [component, langgraph, adapter, bridge]
created: 2026-04-19
updated: 2026-04-19
---

# LangGraphAdapter — Server-to-Graph Bridge

## Purpose

Thin adapter that decouples `server.py` from the concrete LangGraph implementation. Translates a plain-dict invocation call into the format `invoke_hotel_agent()` expects, and returns a normalised result dict. Also owns the mode-switch between embedded (default) and legacy HTTP invocation.

## Class: `LangGraphAdapter`

**Module:** `src/hotel_guardrails/langgraph_adapter.py`

**Constructor args:**

| Arg | Default | Purpose |
|---|---|---|
| `mode` | `$LANGGRAPH_MODE` env (default `"embedded"`) | `"embedded"` or `"http"` |
| `endpoint` | `$LANGGRAPH_ENDPOINT` (default `http://localhost:8090`) | External server URL (http mode only) |
| `timeout` | `60.0` | Request timeout seconds |
| `max_retries` | `2` | Retry attempts on failure |
| `checkpointer` | `None` | LangGraph checkpointer passed through to `get_hotel_graph()` |

On `__init__` with `mode="embedded"`, pre-loads the graph by calling `get_hotel_graph(checkpointer)`.

## Key Method: `async invoke(...) -> Dict`

**Inputs:**

- `message: str` — user message
- `session_id: str` — conversation thread ID (maps to LangGraph `thread_id`)
- `user_id: str` — guest identifier
- `conversation_history: Optional[List[Dict]]` — accepted but unused; LangGraph's own checkpointer tracks history
- `llm_settings: Optional[Dict]` — passed through to `invoke_hotel_agent()` as `configurable.llm_settings`

**Output dict keys:**

- `success: bool`
- `response: str` — assistant text
- `path: str` — always `"langgraph"`
- `intent: str` — final sub-agent intent (`booking`, `service`, `knowledge`, `other`)
- `tool_calls: List[Dict]` — tool invocations made during the turn
- `session_id: str`
- `retries: int` — how many quality-check retries were consumed
- `had_leak: bool` — whether a tool-call leak was detected on any attempt
- `error: str` — present only on failure

## Modes

**Embedded (default):** Calls `invoke_hotel_agent()` in-process. No network hop. Checkpointer is shared with the server process.

**HTTP (legacy):** Makes a POST to `{endpoint}/invoke` with the message payload. Used historically when LangGraph ran as a separate service on port 8090. Not used in current Railway deployment.

## Dependencies

- `src/hotel_guardrails/hotel_langgraph.py` — `get_hotel_graph()`, `invoke_hotel_agent()`
- Instantiated in `server.py:lifespan()` after checkpointer is ready

## Related

- [[components/hotel_langgraph]] — what this adapter calls
- [[components/hybrid_router]] — what calls this adapter
- [[flows/hotel_chat_pipeline]]
