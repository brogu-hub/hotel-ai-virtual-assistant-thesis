---
type: meta
title: "Decisions Index"
updated: 2026-04-19
---

# Decisions

Architectural Decision Records (ADRs) and methodology decisions for the thesis. One page per decision. Use [[_templates/decision]].

## Known decisions to back-fill

- Fork NVIDIA AI Blueprint instead of building from scratch
- OpenRouter/Qwen3-max as dev LLM backend (alternative to NVIDIA NIM)
- Hybrid LangGraph + NeMo Guardrails architecture (vs. pure LangGraph or pure rails)
- Qdrant (dev) vs. Milvus (prod) vector store split
- Railway deployment target for hotel_guardrails
- 4 sub-agent routing split (booking / service / knowledge / other_talk)
- Python 3.12 as target runtime (post-rebuild, Apr 19 2026)
- Thesis methodology chapter structure
- Evaluation framework: DeepEval + custom harness

## Filed pages

- [[reranker_disabled]] — CrossEncoder removed from the hot path; event-loop blocking was pushing p95 latency past SLA.
- [[dual_identity_model]] — Separate `GUESTS` and `USERS` tables; why the schema is not unified.

> Most of the "Known decisions to back-fill" list above is still unfiled. Surface these as ADRs on the next pass.
