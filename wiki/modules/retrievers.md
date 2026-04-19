---
type: module
path: src/retrievers/
status: active
language: python
purpose: "RAG retriever microservices — unstructured (Milvus), structured (Vanna/SQL), hotel knowledge"
maintainer: Mangakorian
last_updated: 2026-04-19
depends_on: [common]
used_by: [hotel_guardrails, agent]
linked_issues: []
tags: [module, retrievers, rag]
created: 2026-04-19
updated: 2026-04-19
---

# retrievers

## Purpose

Three retriever microservices that serve document and data retrieval to the agent systems. Each is a standalone FastAPI service that can be called independently.

## Sub-modules

| Sub-module | Port | Storage | Purpose |
|---|---|---|---|
| `unstructured_data/` | 8086 | [[Milvus]] | PDF/document embedding + similarity search |
| `structured_data/` | 8087 | [[PostgreSQL]] + [[Vanna.AI]] | NL-to-SQL for structured data |
| `hotel_knowledge/` | — | [[Qdrant]] | Hotel-specific document RAG |

## Dependencies

- External: [[Milvus]], [[Qdrant]], [[Vanna.AI]], [[PostgreSQL]], [[FastAPI]], [[NVIDIA]] NIM (embeddings/reranker in prod)
- Internal: [[common]]

## Notes & gotchas

- `unstructured_data/` uses NVIDIA NIM embeddings in prod; sentence-transformers in dev
- Each retriever has its own `prompt.yaml` for retrieval chain prompts
- Data ingestion via `notebooks/ingest_data.ipynb`

## Related

- [[RAG]]
- [[Milvus]]
- [[Qdrant]]
- [[hotel_guardrails]]
- [[agent]]
