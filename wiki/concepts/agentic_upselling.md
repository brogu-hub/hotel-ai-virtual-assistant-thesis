---
type: concept
status: stub
related:
  - concepts/langgraph_state_machine_architecture
  - concepts/human_in_the_loop
  - concepts/model_context_protocol
tags: [concept, revenue, upselling, hotel-domain, agentic, business-logic]
created: 2026-04-19
updated: 2026-04-19
---

# Agentic Upselling

## Definition

Agentic upselling is a revenue-driven logic pattern where the chatbot proactively identifies upsell opportunities (spa slots, breakfast add-ons, room upgrades) and presents time-sensitive offers during booking conversations, rather than only answering questions reactively.

## Origin

Concept derived from traditional hospitality revenue management ("Revenue Per Available Room" — RevPAR). Applied to AI chatbots by STR and Revfine industry research (2025), reporting **10–15% growth in RevPAR** from AI-driven pricing and upselling agents.

## Implementation pattern

In LangGraph, a **"Nudge Node"** is added to the graph:

```
user asks about amenities (e.g., spa)
  → Nudge Node checks real-time spa availability via MCP/booking tool
  → If slots open today → generate offer: "10% discount if booked in the next 10 minutes"
  → Inject into response
```

The nudge node is triggered when users ask about amenities during the room selection phase.

## Industry data

> "Hotels using 'Agentic Upselling' see a 10–30% increase in direct revenue compared to static booking engines." — Revfine / STR (2025–2026)

## Variants & related concepts

- [[concepts/model_context_protocol]] — MCP enables real-time inventory checks that power valid upsell offers
- [[concepts/human_in_the_loop]] — high-value upsells may pause for HITL confirmation
- [[concepts/langgraph_state_machine_architecture]] — provides the Nudge Node architecture

## How it shows up in this project

Not yet implemented in the current codebase. The `hotel_service` sub-agent handles amenities queries but does not include a proactive upsell nudge node. This is a candidate feature for thesis evaluation.

> [!gap] Agentic upselling (Nudge Node) is referenced as a best practice but not implemented. If the thesis evaluates revenue impact, this is a gap.

## Key references

- Source: `LLM_CHATBOT_CRITIRION.md` (Gemini architecture conversation, 2026)
- [[papers/str_revfine_upselling]]

## Open questions

- Is agentic upselling in scope for the thesis, or is it a future work item?
- Can it be retrofitted to the `hotel_service` sub-agent without major restructuring?
