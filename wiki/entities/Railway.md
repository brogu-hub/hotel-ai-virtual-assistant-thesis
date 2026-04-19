---
type: entity
category: product
url: https://railway.app
tags: [entity, product, deployment, cloud]
created: 2026-04-19
updated: 2026-04-19
---

# Railway

## What it is

Railway is a cloud platform-as-a-service for deploying containerized applications, with built-in managed databases and simple git-based deploys.

## Role in this project

Railway is the **primary deployment target** for `hotel_guardrails`. The service, PostgreSQL database, Redis cache, and Qdrant vector store are all Railway-hosted for the active dev/demo environment.

## Key facts

- Deploy config: `railway.toml` and `Procfile` at repo root
- Health check endpoint: `GET /healthz`
- `docker-compose.dev.yaml` points `DATABASE_URL` and `APP_VECTORSTORE_URL` to Railway-hosted services
- No GPU required (uses OpenRouter, not NVIDIA NIM)
- Production-equivalent NVIDIA stack uses Docker Compose or Helm on GPU hardware

## Related

- [[hotel_guardrails]]
- [[OpenRouter]]
- [[Qdrant]]
- [[PostgreSQL]]
- [[Redis]]
- [[ADR Railway Deploy]]
