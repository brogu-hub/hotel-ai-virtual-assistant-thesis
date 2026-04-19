---
type: decision
status: active
date: 2026-04-19
owner: "Mangakorian"
context: "Safety and orchestration architecture for hotel_guardrails — how to combine conversation control with LLM safety"
supersedes: []
superseded_by: []
tags: [decision]
created: 2026-04-19
updated: 2026-04-19
---

# ADR: Hybrid LangGraph + NeMo Guardrails Architecture

*Retroactive ADR written 2026-04-19; decision was made during the initial architecture design of `hotel_guardrails`.*

## Context

The hotel assistant needs two distinct capabilities: (1) stateful multi-turn conversation orchestration with specialized routing (booking, RAG, service, general chat), and (2) safety filtering to block harmful inputs before they reach the LLM. Two libraries address these concerns: LangGraph handles orchestration; NeMo Guardrails handles safety rails via its Colang DSL.

Each library can in principle do both jobs. LangGraph can add safety checks as graph nodes; NeMo Guardrails can run LLM-backed conversation rails that also call tools. The question was whether to use one or both.

## Options considered

- **Option A — Pure LangGraph (no NeMo Guardrails)**
  - Pros: Single framework; simpler dependency graph; safety as just another graph node
  - Cons: Safety logic mixed into business logic; no Colang DSL for declarative rail specification; harder to audit safety rules separately

- **Option B — Pure NeMo Guardrails**
  - Pros: Declarative Colang DSL for rail definitions; NVIDIA-supported safety framework; designed specifically for safe LLM conversations
  - Cons: NeMo Guardrails is not well-suited for complex stateful workflows with multi-step tool calling; the booking and RAG sub-agents have deep state requirements that fit LangGraph's StateGraph better; NeMo imposes additional LLM calls per turn for rail checks, increasing latency

- **Option C — Hybrid: NeMo Guardrails as safety pre-filter, LangGraph for orchestration**
  - Pros: Each library does what it does best; safety layer is architecturally separate from business logic; can independently update rail definitions without touching orchestration code
  - Cons: Two frameworks to maintain; integration point (`HybridRouter`) is bespoke; potential for duplicate LLM calls (rails check + routing LLM call)

## Decision

Use the hybrid architecture (Option C). `HybridRouter` runs NeMo Guardrails safety checks first; if the request passes, it is handed to `LangGraphAdapter` → `HotelLangGraph`. The two concerns are kept structurally separate.

> [!contradiction]
> In practice, the NeMo Guardrails `config/` directory (`config.yml`, `prompts.yml`, `rails.co`) does not exist in the current codebase. The `HybridRouter` performs safety checks via regex pattern matching, not via the NeMo Guardrails runtime. The "hybrid" label is architecturally correct in intent but NeMo Guardrails is not active. See [[nemo_guardrails_config]] gap note and the `hotel_guardrails` module page contradiction callout.

## Consequences

- Positive: The architectural boundary is clean — safety pre-filter can be replaced or upgraded independently of the LangGraph state machine. The `HybridRouter` abstraction is in place for a future real NeMo Guardrails wiring.
- Negative / trade-offs: NeMo Guardrails is not running; the "hybrid" claim in the service name and thesis is currently backed only by regex safety checks. This is a meaningful gap for a thesis contribution centered on safety. The `LANGGRAPH_MODE` env var adds further complexity (embedded vs HTTP-server LangGraph).
- Revisit if: Actual NeMo Guardrails Colang configuration is added (completing the hybrid intent); or if LangGraph's `interrupt_before` / human-in-the-loop pattern proves sufficient for safety without NeMo.

## Related

- [[NeMo Guardrails]] — safety layer entity
- [[LangGraph]] — orchestration layer entity
- [[hotel_guardrails]] — module this decision defines
- [[components/hybrid_router]] — the integration point
- [[components/hotel_langgraph]] — the orchestration side
- [[concepts/safety_pre_filter]] — concept page
- [[concepts/langgraph_state_machine_architecture]] — concept page
