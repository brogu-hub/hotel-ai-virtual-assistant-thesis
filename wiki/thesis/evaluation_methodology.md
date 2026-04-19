---
type: thesis-chapter
chapter_num: 5
status: draft
word_count: 0
key_claims:
  - "LangGraph state machine is the optimal orchestration architecture for hotel booking chatbots due to deterministic cycle handling and checkpointing."
  - "Hybrid RAG with semantic re-ranking outperforms pure vector search for hotel policy retrieval."
  - "HITL checkpoints are required for high-value transactions and regulatory compliance."
  - "PII redaction is a hard requirement under GDPR / EU AI Act 2026 for hospitality AI systems."
cites:
  - papers/bcg_2026_traveler_ai
  - papers/str_revfine_upselling
  - papers/mdpi_tourism_ai_research
  - papers/eu_ai_act_2026
tags: [thesis, evaluation, architecture, methodology, chapter-5]
created: 2026-04-19
updated: 2026-04-19
---

# Evaluation Methodology — Hotel AI Chatbot Design Criteria

## Purpose of this chapter

Chapter 5 documents how the hotel AI chatbot (Grand Horizon Hotel) was evaluated against industry and academic design criteria. It bridges the architectural decisions made in Chapter 3 (System Design) with the experimental results that validate or challenge those decisions.

## Design criteria from literature and industry

The following criteria define what a "hotel-grade" AI chatbot must satisfy, derived from `LLM_CHATBOT_CRITIRION.md` (Gemini architecture consultation, 2026):

| Criterion | Rationale | Technical Implementation |
|---|---|---|
| **Stateful orchestration** | Non-linear hotel conversations require deterministic cycle recovery | [[langgraph_state_machine_architecture]] — LangGraph StateGraph |
| **Hybrid RAG + re-ranking** | Policy retrieval failures cause booking errors and compliance risk | [[hybrid_rag_with_reranking]] — dense + BM25 + reranker |
| **Persistent memory** | Booking drafts and guest preferences must survive disconnects | [[persistent_memory_chatbot]] — PostgreSQL + Redis checkpointers |
| **MCP integration** | Multi-system hotel data (PMS/CRS/CRM) must be unified | [[model_context_protocol]] — single structured agent interface |
| **HITL checkpoints** | High-value transactions and complex challenges need human confirmation | [[human_in_the_loop]] — LangGraph Break states + escalate tool |
| **PII redaction** | GDPR / PCI-DSS / EU AI Act compliance is mandatory | [[pii_redaction_and_compliance]] — Presidio or regex layer |
| **Agentic upselling** | Revenue generation differentiates bot from cost center | [[agentic_upselling]] — Nudge Node in LangGraph |

## Architecture comparison assessed

Three orchestration architectures were evaluated:

- **LangGraph** (State Machine) — chosen: highest control, checkpointing, time-travel debugging
- **[[crewai_role_based_orchestration]]** — rejected: insufficient live transaction state management
- **[[autogen_conversation_driven_orchestration]]** — rejected: emergent/low-control, unsuitable for booking transactions

## Industry evidence supporting criteria

- BCG (2026): 37% traveler AI adoption, human touch still key → justifies HITL ([[papers/bcg_2026_traveler_ai]])
- STR/Revfine (2025): 10–30% RevPAR growth from AI upselling → justifies Nudge Node ([[papers/str_revfine_upselling]])
- MDPI Tourism (2025): high traveler uncertainty on cancellation policy → justifies re-ranking ([[papers/mdpi_tourism_ai_research]])
- EU AI Act (2026): essential service risk tier → justifies PII redaction + AI inventory ([[papers/eu_ai_act_2026]])

## Implementation gaps vs. best practice

The following criteria are defined but not fully implemented in the current codebase:

1. **MCP layer** — project uses single PostgreSQL DB instead of PMS/CRS/CRM multi-system integration
2. **Agentic upselling (Nudge Node)** — not implemented in `hotel_service` sub-agent
3. **PII redaction** — NeMo Guardrails rails exist but dedicated Presidio layer not confirmed
4. **Amadeus API integration** — internal DB used instead of live CRS

These gaps should be addressed in the Discussion (Chapter 6) as limitations and future work.

## Outline

- Section 5.1 — Evaluation framework overview
- Section 5.2 — Orchestration architecture evaluation (LangGraph vs. alternatives)
- Section 5.3 — RAG quality evaluation (hybrid search + reranking)
- Section 5.4 — Safety and compliance evaluation (guardrails, PII)
- Section 5.5 — End-to-end booking task success rate
- Section 5.6 — Performance metrics (latency, throughput)

## Sources cited

- [[papers/bcg_2026_traveler_ai]]
- [[papers/str_revfine_upselling]]
- [[papers/mdpi_tourism_ai_research]]
- [[papers/eu_ai_act_2026]]

## Links back to codebase

- [[LangGraph]] — `src/hotel_guardrails/hotel_langgraph.py`
- [[NeMo Guardrails]] — `src/hotel_guardrails/config/`
- `src/common/reranker_qwen.py`, `src/common/reranker_nvidia.py`
- `src/hotel_guardrails/database.py`

## Open issues

- Full citation details needed for MDPI Tourism paper (author, DOI)
- Confirm whether Presidio or equivalent PII scrubbing is implemented
- Confirm whether BM25 hybrid search is active or only dense vector search
- Determine if agentic upselling is in scope for Chapter 5 or deferred to Chapter 6 (future work)
