---
type: decision
status: active
date: 2026-04-19
owner: "Mangakorian"
context: "How to decompose hotel assistant intents into LangGraph sub-agents"
supersedes: []
superseded_by: []
tags: [decision]
created: 2026-04-19
updated: 2026-04-19
---

# ADR: 4-Sub-Agent Routing Split (booking / service / knowledge / other_talk)

*Retroactive ADR written 2026-04-19; decision was made during the initial hotel_langgraph design.*

## Context

The hotel assistant receives heterogeneous user intents: transactional booking queries (check availability, create/cancel reservations), hotel service questions (amenities, facilities), knowledge retrieval (dining hours, pool hours, policies — answered from RAG over `data/hotel/*.md`), and general conversational turns (greetings, out-of-scope chat). The original NVIDIA Blueprint used 3 sub-agents aligned to its e-commerce domain (`ProductQA`, `OrderStatus`, `ReturnProcessing`).

The LangGraph state machine needs to route each turn to the appropriate handler. The question was how finely to split intents.

## Options considered

- **Option A — 2 sub-agents (transactional / informational)**
  - Pros: Simple routing; fewer routing errors
  - Cons: "Informational" becomes a catch-all; tool selection within it would be ambiguous; service-type vs. RAG-knowledge queries require different tool sets

- **Option B — 4 sub-agents (booking / service / knowledge / other_talk)**
  - Pros: Each sub-agent has a coherent, narrow tool set; booking gets reservation CRUD tools; service gets amenities/facilities tools; knowledge triggers RAG via `search_hotel_knowledge`; other_talk handles greetings and deflections cleanly; maps naturally to hotel staff specializations
  - Cons: Routing LLM call must classify into 4 intents — misrouting between service and knowledge is possible (see failure case E28 in [[model-tuning-and-test-results-2026-04-03]]);  4-way classification adds one LLM round-trip per turn

- **Option C — No routing, single agent with all tools**
  - Pros: No routing overhead; agent picks tools by itself
  - Cons: Tool selection ambiguity increases with 10+ tools; harder to apply per-intent safety rules; harder to debug which path the agent took

- **Option D — 6+ sub-agents (separate check-availability, create-booking, cancel-booking, etc.)**
  - Pros: Maximum specificity
  - Cons: Overfits to known intents; maintenance burden; LLM routing accuracy decreases with more classes

## Decision

Use the 4-sub-agent split: `hotel_booking`, `hotel_service`, `hotel_knowledge`, `other_talk`. The `primary_assistant` node in `hotel_langgraph.py` classifies the intent, then routes via conditional edges. Each sub-agent has its own tool node.

## Consequences

- Positive: Evaluation results show the 4-split achieves 100% booking accuracy, 100% knowledge accuracy, and handles language routing correctly. Per-category test structure (Parts A–F in [[model-tuning-and-test-results-2026-04-03]]) maps cleanly to sub-agents, making targeted debugging straightforward.
- Negative / trade-offs: One confirmed routing failure (E28): hotel services list query was routed to `hotel_knowledge` instead of the `get_hotel_services` tool — the boundary between `hotel_service` and `hotel_knowledge` is ambiguous for certain queries. The routing LLM call adds latency on every turn (~1–3 s overhead). The split mirrors the NVIDIA Blueprint's 3-agent pattern philosophically, so this is an evolution rather than a novel architecture.
- Revisit if: A broader range of hotel intents is added (e.g., concierge, transportation, spa booking) that requires a 5th or 6th sub-agent; or if routing accuracy degrades with additional models.

## Related

- [[LangGraph]] — orchestration library
- [[hotel_guardrails]] — module this decision defines
- [[components/hotel_langgraph]] — the state machine implementation
- [[concepts/sub_agent_routing]] — concept page
- [[model-tuning-and-test-results-2026-04-03]] — confirms routing accuracy post-tuning
- [[model-eval-local-vs-cloud-2026-04-06]] — per-category accuracy across the 4-split
- [[agent]] — original 3-sub-agent NVIDIA Blueprint (reference architecture)
