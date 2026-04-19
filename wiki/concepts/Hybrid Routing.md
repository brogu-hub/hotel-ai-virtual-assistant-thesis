---
type: concept
status: developing
related: [NeMo Guardrails, LangGraph, hotel_guardrails]
tags: [concept, safety, routing, guardrails, hybrid]
created: 2026-04-19
updated: 2026-04-19
---

# Hybrid Routing

## Definition

Hybrid routing is the architectural pattern used in `hotel_guardrails` where [[NeMo Guardrails]] handles safety filtering and a [[LangGraph]] state machine handles all business logic routing. The two systems are layered: guardrails run first, and only safe requests reach LangGraph.

## Origin

A custom design choice for this thesis project. See [[ADR Hybrid Architecture]].

## How it works

```
POST /chat
  → HybridRouter (hybrid_router.py)
      [1] Safety check via NeMo Guardrails (blocks harmful/off-topic)
      [2] If safe → LangGraphAdapter → HotelLangGraph
                      primary_assistant → sub-agent routing
  → Response
```

The `hybrid_router.py` acts as a pre-filter. It does not route by intent itself — it gates access. The routing by intent (booking vs. service vs. knowledge vs. chat) is entirely inside [[LangGraph State Machine]].

## Why this approach

- NeMo Guardrails provides declarative, maintainable safety rules (Colang DSL)
- LangGraph provides flexible stateful multi-agent orchestration
- Combining them avoids re-implementing safety logic in LangGraph and avoids reimplementing stateful routing in NeMo Guardrails

## Trade-offs

- Additional latency: two LLM calls per turn minimum (guardrails check + LangGraph)
- Complexity: two frameworks to configure and maintain
- Guardrails prompts (prompts.yml) are separate from LangGraph prompts

## Related

- [[NeMo Guardrails]]
- [[LangGraph State Machine]]
- [[hotel_guardrails]]
- [[ADR Hybrid Architecture]]
