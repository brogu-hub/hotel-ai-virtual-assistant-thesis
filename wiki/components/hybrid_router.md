---
type: component
path: "src/hotel_guardrails/hybrid_router.py"
status: active
parent_module: hotel_guardrails
tags: [component, safety, routing, guardrails]
created: 2026-04-19
updated: 2026-04-19
---

# HybridRouter — Safety Pre-filter

## Purpose

First gate on every `/chat` request. Runs before any LLM call. Blocks requests matching harmful regex patterns, then routes all valid requests to the LangGraph agent. Despite the "Hybrid" name, this is now a simplified single-path router — LangGraph handles everything that isn't blocked.

## Class: `HybridRouter`

**Module:** `src/hotel_guardrails/hybrid_router.py`

**Constructor args:**

- `feedback_store` — optional async callable `(session_id) -> Optional[float]` that returns a historical quality score; used only for logging metrics, does not affect routing.
- `**kwargs` — silently accepted to absorb legacy parameters from older call sites.

**Key method:** `async route(query, session_id) -> RoutingDecision`

Returns a `RoutingDecision` with:

- `path: RoutingPath` — either `LANGGRAPH_AGENT` or `BLOCKED`
- `complexity: ComplexityLevel` — `SIMPLE` / `MODERATE` / `COMPLEX` (for metrics only, does not affect routing)
- `confidence: float` — 0.0–1.0
- `reason: str` — human-readable explanation

## Routing Logic

1. Check query against `BLOCKED_PATTERNS` (compiled regex). If matched → `RoutingPath.BLOCKED`.
2. Classify complexity against `SIMPLE_PATTERNS` / `COMPLEX_PATTERNS` for logging only.
3. All non-blocked requests → `RoutingPath.LANGGRAPH_AGENT`.

### Blocked patterns (examples)

- Injection / security: `hack`, `exploit`, `bypass`, `sql injection`
- Illegal content: `illegal`, `weapon`, `drug`, `steal`, `fraud`
- Jailbreak attempts: `ignore previous`, `forget instructions`, `jailbreak`
- Credential attacks: `password hack`, `credential dump`

### Complexity patterns (metrics only)

- Simple: greetings, thanks, Thai greetings (`สวัสดี`), quick factual queries
- Complex: booking/reservation keywords, cancellation, multi-step connectors

## Design Note

The class was originally a true hybrid router that could dispatch simple queries to a fast path (direct LLM) and complex ones to LangGraph. That dual-path design was removed in favour of LangGraph-for-all. The `ComplexityLevel` enum and classification logic were retained for metrics and future use. The name "HybridRouter" is therefore a historical artifact.

## Dependencies

- No external LLM calls — pure Python regex
- `pydantic` for `RoutingDecision` schema
- Instantiated by `server.py:lifespan()` and passed `feedback_collector.get_average_score` as `feedback_store`

## Related

- [[components/langgraph_adapter]] — called after `HybridRouter` approves a request
- [[concepts/safety_pre_filter]]
- [[flows/hotel_chat_pipeline]]
