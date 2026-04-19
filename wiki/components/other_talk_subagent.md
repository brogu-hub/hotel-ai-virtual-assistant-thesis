---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, langgraph, subagent, conversation]
created: 2026-04-19
updated: 2026-04-19
---

# other_talk Sub-agent

## Purpose

Handles pure conversational turns — greetings, farewells, and thanks — that contain no hotel-specific question or request. Provides a warm, on-brand response and offers to help. No tools are used.

## Graph Position

```
enter_other → other_talk → END
```

No tool loop. Generates a direct conversational response.

## Handler Function: `handle_other_talk()`

**Location:** `hotel_langgraph.py`

Loads `main_prompt` and optional `greeting_templates` from `hotel_prompt.yaml`. Appends instructions to:

- Be friendly and welcoming
- Offer to help with hotel services
- Use polite Thai particles (`ครับ`/`ค่ะ`) for Thai speakers
- Be professional and warm for English speakers

Sets `current_intent = "other"`.

**Temperature:** 0.3
**Max tokens:** 512 (lowest of all sub-agents — responses are short by design)

## Routing Boundary

`HandleOtherTalk` is reached only for pure greetings/farewells with no question attached. The primary assistant's prompt explicitly states: `HandleOtherTalk ONLY for greetings without questions (Hello, Hi, Thanks, Bye)`. Any greeting that includes a question (e.g., "Hi! What time is breakfast?") routes to `hotel_knowledge` instead.

## Related

- [[components/primary_assistant]] — routes here via `HandleOtherTalk`
- [[components/hotel_langgraph]] — parent graph
