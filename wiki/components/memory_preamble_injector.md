---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, memory, prompt, personalisation, novel-contribution]
date_ingested: 2026-04-20
---

# memory_preamble_injector — Guest Memory → Prompt Prefix

> [!note]
> Function-level view of how long-term memory becomes personalised behaviour. For the architecture see [[concepts/dual_plane_memory]]; for the flow see [[flows/cross_session_memory]].

## Scope

`_render_memory_preamble(memory)` at `src/hotel_guardrails/hotel_langgraph.py:623` plus its five call sites — one in `primary_assistant` and one in each of the four sub-agent handlers.

## Contract

**Input**: a dict with zero or more of the four memory keys (`profile`, `preferences`, `recent_bookings_summary`, `service_history_summary`).

**Output**: a compact multi-line string, either empty (no memory) or formatted as:

```
Known about this guest:
- Name: Alice (alice@example.com)
- Preferences: high floor, quiet room, vegetarian, king bed
- Recent booking: Deluxe Apr 25–27, 2 guests
- Recent services: extra pillows, wake-up call
```

The exact format is a compact English list so it takes minimal context budget but is LLM-parseable in both Thai and English conversations.

## Injection points

All five are structurally identical — fetch memory, render preamble, prepend to the sub-agent's system-level prompt. The five call sites correspond to:

| Handler | Line | Role |
|---|---|---|
| `route_primary_assistant` | 525 | Router — uses memory to bias routing (e.g., a vegetarian guest asking about "restaurants" weights toward knowledge sub-agent) |
| `handle_booking` | 278 | Booking — pre-fills likely preferences (bed type, floor) |
| `handle_service` | 340 | Service — surfaces prior service requests ("you had extra pillows last time — want the same?") |
| `handle_knowledge` | 379 | Knowledge — personalises recommendations (vegetarian-friendly restaurants) |
| `handle_other_talk` | 458 | Other — allows greeting by name |

## Why a preamble, not a retrieval?

An obvious alternative is to treat long-term memory as another vector-search target and let the LLM retrieve only what it thinks it needs. The thesis rejects this:

- **Determinism**. Known keys render the same every time — no retrieval ranking variance.
- **Cost**. Zero extra embedding calls, zero extra vector searches per turn.
- **Coverage**. The memory is small (~4 keys, ~200 tokens rendered). Retrieving is strictly more complex than always-include.

The trade-off is a slight context-budget cost on every turn; acceptable given the tiny size.

## Empty state

If `load_guest_memory()` returns `{}`, the preamble is a single-line "No prior information about this guest yet." This is still rendered so the sub-agent prompt is structurally uniform — no branching in the prompt template.

## Language

Preambles are always rendered in **English**, regardless of `state.language`. The sub-agent LLM is expected to translate/paraphrase in its reply. This keeps the extractor simple (one rendering path) and lets the LLM handle the bilingual presentation layer.

## Related

- [[concepts/dual_plane_memory]]
- [[concepts/bilingual_memory_extraction]]
- [[components/guest_memory_store]] — produces the dict
- [[components/hotel_langgraph]] — hosts the five call sites
- [[components/primary_assistant]], [[components/booking_subagent]], [[components/service_subagent]], [[components/knowledge_subagent]], [[components/other_talk_subagent]] — the five consumers
- [[flows/cross_session_memory]]
