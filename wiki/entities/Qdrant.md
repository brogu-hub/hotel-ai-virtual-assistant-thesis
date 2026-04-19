---
type: entity
category: product
url: https://qdrant.tech
tags: [entity, product, vectorstore, dev]
created: 2026-04-19
updated: 2026-04-19
---

# Qdrant

## What it is

Qdrant is an open-source vector database written in Rust, offering a REST/gRPC API and cloud-hosted managed service.

## Role in this project

Qdrant is the **development vector store** and is also Railway-hosted for the deployed `hotel_guardrails` service. Set via `APP_VECTORSTORE_NAME=qdrant` and `APP_VECTORSTORE_URL`.

## Key facts

- Adapter: `src/common/vectorstore_qdrant.py`
- Used in `docker-compose.dev.yaml` (dev stack) and Railway deployment
- Cloud (Railway-hosted) Qdrant replaces self-hosted Milvus for the hotel_guardrails service
- Lighter-weight than Milvus — no GPU required
- Port: default 6333 (REST)

## Related

- [[Milvus]]
- [[retrievers]]
- [[hotel_guardrails]]
- [[common]]
- [[ADR Qdrant Milvus Split]]
- [[Railway]]
