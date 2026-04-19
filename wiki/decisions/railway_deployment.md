---
type: decision
status: active
date: 2026-04-19
owner: "Mangakorian"
context: "Where to host the hotel_guardrails service for live demo and thesis evaluation"
supersedes: []
superseded_by: []
tags: [decision]
created: 2026-04-19
updated: 2026-04-19
---

# ADR: Railway as Deployment Target for hotel_guardrails

*Retroactive ADR written 2026-04-19; decision was made when setting up the live demo environment.*

## Context

The thesis requires a publicly accessible, live demo of the hotel assistant for evaluation and presentation. The deployment needs to host: the `hotel_guardrails` FastAPI server, a PostgreSQL database (bookings, guests, auth), a Redis cache (rate limiting, session state), and a Qdrant vector store (hotel RAG). The constraint: no GPU hardware, a limited thesis budget, and a need for git-push-to-deploy simplicity.

## Options considered

- **Option A — Railway**
  - Pros: Free-tier credits available at time of decision; managed PostgreSQL, Redis, and Qdrant all available as Railway services; git-based deploy via `railway.toml` and `Procfile`; no GPU required (uses OpenRouter); health check endpoint `/healthz` integrates natively with Railway's health check system
  - Cons: Free tier has usage limits; multi-worker Railway deployments will have split LangGraph checkpointer state (in-memory `MemorySaver` per worker) unless PostgreSQL checkpointer is configured; Railway is not a standard academic deployment target

- **Option B — Self-hosted VPS (DigitalOcean / Linode)**
  - Pros: Full control; predictable cost; no platform dependency
  - Cons: Manual setup of all supporting services (PostgreSQL, Redis, Qdrant); ongoing sysadmin overhead; no budget allocated

- **Option C — Docker Compose on local machine (no public deployment)**
  - Pros: Zero cost; full control; matches dev environment exactly
  - Cons: Not publicly accessible for evaluation or advisor demonstrations; not a meaningful "deployment" for the thesis claim

- **Option D — Kubernetes / Helm (NVIDIA Blueprint production target)**
  - Pros: Matches the blueprint's intended production architecture; Helm charts exist in `deploy/helm/`
  - Cons: Requires a Kubernetes cluster with GPUs; far exceeds thesis budget and complexity requirements

## Decision

Deploy to Railway. The configuration is minimal: `railway.toml` declares the service, `Procfile` defines the start command, and Railway-hosted managed services supply PostgreSQL, Redis, and Qdrant. The OpenRouter dependency means no GPU is needed.

## Consequences

- Positive: Live public URL available for demos and evaluation. All managed services (PostgreSQL, Redis, Qdrant) operate without self-hosted maintenance. Git push deploys automatically. The deployment accurately represents the hotel_guardrails architecture as a real running service.
- Negative / trade-offs: Railway is a thesis-scale convenience choice, not a production-hardening decision. The in-memory token blocklist means logout tokens re-validate after server restarts (a known limitation noted in the `hotel_guardrails` module page). Multi-worker deployments on Railway would need the PostgreSQL checkpointer configured for LangGraph, or session state will diverge across workers. Railway usage costs may accumulate if the demo receives sustained traffic.
- Revisit if: Free-tier credits are exhausted and continued deployment is needed; or if the thesis requires evaluating the full NVIDIA NIM + GPU stack in production.

## Related

- [[Railway]] — the deployment platform entity
- [[hotel_guardrails]] — the service deployed
- [[Qdrant]] — Railway-hosted vector store
- [[openrouter_dev_backend]] — no-GPU LLM backend that makes Railway viable
- [[qdrant_dev_milvus_prod]] — vector store decision that feeds into this deployment
