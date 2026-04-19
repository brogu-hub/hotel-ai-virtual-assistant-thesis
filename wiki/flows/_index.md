---
type: meta
title: "Flows Index"
updated: 2026-04-19
---

# Flows

Request paths, data flows, and control flows. One page per named flow.

## Filed pages

- [[guest_chat]] — `POST /chat` end-to-end: rate limit → PII scrub → HybridRouter → LangGraph → sub-agent → response
- [[reservation_lifecycle]] — booking status machine: pending → confirmed → checked_in → checked_out, dynamic pricing, mock payment
- [[auth_and_access_control]] — JWT registration/login, dual identity model, login hardening, password-change invalidation
- [[admin_monitoring]] — session takeover, auto-escalation, time-travel/checkpoint replay, audit log, runtime LLM switching
- [[chat_scaling]] — concurrency semaphore, session locks, rate limiters, knowledge cache, Ollama parallelism alignment
- [[local_run]] — Docker Compose hotel stack, data population commands, bare-metal uvicorn, Jupyter ingest

## Expected pages (not yet filed)

- Guardrails safety flow (NeMo input/output rails → refusal paths) — see [[hybrid_router]]
- Knowledge RAG ingest flow (document → chunk → embed → Qdrant)
- Evaluation flow (DeepEval / custom eval harness)
- CI/CD pipeline flow
