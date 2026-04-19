---
type: decision
status: active
date: 2026-04-19
owner: "Mangakorian"
context: "Starting point for the hotel AI assistant — build from scratch vs. extend an existing blueprint"
supersedes: []
superseded_by: []
tags: [decision]
created: 2026-04-19
updated: 2026-04-19
---

# ADR: Fork NVIDIA AI Blueprint Instead of Building from Scratch

*Retroactive ADR written 2026-04-19; decision was made at project inception during initial setup.*

## Context

The thesis goal is to demonstrate a production-quality hotel AI virtual assistant with RAG, booking workflows, safety guardrails, and bilingual (EN/TH) support. Two practical starting points existed: (a) implement the full microservices stack from scratch, or (b) fork the publicly available NVIDIA AI Blueprint for AI Virtual Assistant for Customer Service (Apache 2.0).

The blueprint ships with a pre-wired multi-microservice architecture: agent server (LangGraph), structured and unstructured retrievers (Milvus + Vanna.AI), analytics (sentiment/summarization), API gateway, ingest service, and a React frontend. It targets Llama 3.3 70B via NVIDIA NIM endpoints with NVIDIA embeddings and reranker NIMs.

Constraints: The project is thesis-scoped with a single developer, limited calendar time, and no access to 8×H100 for production NIM hosting. A thesis contribution requires customization on top of an existing foundation, not necessarily end-to-end implementation.

## Options considered

- **Option A — Fork NVIDIA Blueprint**
  - Pros: Entire microservices scaffolding available immediately; architecture decisions already vetted by NVIDIA; Apache 2.0 license; thesis work focuses on the hotel customization layer and evaluation
  - Cons: Large codebase surface to understand; original stack assumes NVIDIA hardware; many services are unused placeholders in the hotel adaptation

- **Option B — Build from scratch with FastAPI + LangGraph**
  - Pros: Minimal dependencies; full architectural ownership; no legacy code to carry
  - Cons: Weeks of scaffolding before any hotel-specific logic; no pre-built retriever pipeline; reinvents solved problems (auth, rate limiting, vector search integration)

- **Option C — Fork an open LangChain starter template**
  - Pros: Lighter than the full blueprint
  - Cons: No domain similarity; would require building all retriever and guardrails wiring anyway

## Decision

Fork the NVIDIA AI Blueprint. The actively-developed service (`src/hotel_guardrails/`) is a heavily modified descendant. The original blueprint agent is preserved in `src/agent/` as a reference baseline. Supporting services (analytics, API gateway, ingest, frontend, Helm charts) are retained but minimally adapted.

## Consequences

- Positive: Significant scaffolding cost avoided. The thesis development cycle focuses on hotel-domain customization: the LangGraph sub-agent split, OpenRouter adapter, RAG knowledge base, booking/guest database, auth hardening, and bilingual support.
- Negative / trade-offs: The codebase carries `src/agent/`, `src/retrievers/unstructured_data/`, and `src/analytics/` at original blueprint state — these are dead weight for the active hotel service but are kept as the thesis comparison baseline. The original blueprint's NVIDIA NIM dependency is a mismatch for the dev environment, requiring the OpenRouter adapter (see [[openrouter_dev_backend]]).
- Revisit if: The thesis scope expands to require a full from-scratch implementation to prove architectural independence; or if the blueprint license changes unfavorably.

## Related

- [[NVIDIA]] — upstream blueprint origin
- [[agent]] — original blueprint agent (preserved as reference)
- [[hotel_guardrails]] — the forked and adapted service
- [[openrouter_dev_backend]] — consequence of replacing NVIDIA NIM
- [[Llama 3.3 70B]] — original blueprint LLM
