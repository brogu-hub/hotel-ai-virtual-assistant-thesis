---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, langgraph, routing, primary_assistant]
created: 2026-04-19
updated: 2026-04-19
---

# primary_assistant — Router Node

## Purpose

The entry node of the LangGraph graph. Its sole job is to examine every incoming user message and dispatch it to exactly one of the four specialised sub-agents by emitting a routing tool-call. It never generates a user-facing response directly.

## Implementation

Implemented as an instance of the `HotelAssistant` class with the primary routing prompt and four routing tools bound to the LLM. On each turn, it runs:

```
primary_prompt → LLM.bind_tools([ToHotelBooking, ToHotelService, ToHotelKnowledge, HandleOtherTalk]) → AIMessage with tool_call
```

The output is always expected to contain exactly one tool call selecting the destination sub-agent.

## Routing Tools

| Tool | Destination node | Use when |
|---|---|---|
| `ToHotelBooking` | `enter_booking` | Reservations, availability, check-in/out, modify/cancel, payment |
| `ToHotelService` | `enter_service` | Room service, housekeeping, transportation, specific amenity requests |
| `ToHotelKnowledge` | `enter_knowledge` | Hotel info, facilities, dining, WiFi, policies, hours — anything informational |
| `HandleOtherTalk` | `enter_other` | Pure greetings or farewells with no attached question |

## Routing Rules (Prompt-enforced)

Key disambiguation rules baked into the system prompt:

- "cancel my booking" → `ToHotelBooking` (not `HandleOtherTalk`)
- "what services do you have?" → `ToHotelKnowledge` (general info, not `ToHotelService`)
- "I need a spa booking" → `ToHotelService` (specific service request)
- Thai questions ending with `มีไหม`, `กี่โมง`, `ที่ไหน`, `อย่างไร` → `ToHotelKnowledge`
- When ambiguous between Knowledge and Service → prefer `ToHotelKnowledge`
- `HandleOtherTalk` only for pure greeting/farewell with no question attached

## Edge Function: `route_primary_assistant()`

After the primary assistant emits its message, the conditional edge function inspects `state.messages[-1].tool_calls[0].name` and maps to:

- `ToHotelBooking.__name__` → `"enter_booking"`
- `ToHotelService.__name__` → `"enter_service"`
- `ToHotelKnowledge.__name__` → `"enter_knowledge"`
- `HandleOtherTalk.__name__` → `"enter_other"`
- No tool call → `END`

## LLM Settings

Temperature and max_tokens are passed via `config.configurable.llm_settings`. Defaults: temperature=0.3, max_tokens=1024 (overridden by model presets).

## Gotcha — 9B Model Specificity

The primary prompt includes concrete Thai-language routing examples because the local Qwen3.5 9B model misroutes edge cases without them. The cloud models (Qwen3-max) are more robust but the examples are kept for safety.

## Related

- [[components/hotel_langgraph]] — graph that hosts this node
- [[components/booking_subagent]], [[components/service_subagent]], [[components/knowledge_subagent]], [[components/other_talk_subagent]]
- [[concepts/sub_agent_routing]]
