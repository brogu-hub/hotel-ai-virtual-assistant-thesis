---
type: concept
status: developing
related: [retrievers, Milvus, Qdrant, Vanna.AI]
tags: [concept, rag, retrieval, llm]
created: 2026-04-19
updated: 2026-04-19
---

# RAG (Retrieval-Augmented Generation)

## Definition

RAG is a technique where an LLM is augmented with a retrieval step: relevant documents or data records are fetched from an external store based on the query, then injected into the LLM context before generation. This gives the model access to up-to-date and domain-specific knowledge without fine-tuning.

## Origin

Introduced by Lewis et al. (2020) "Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks" (Facebook AI Research).

## Variants in this project

- **Canonical RAG (unstructured):** PDFs and hotel knowledge `.md` files chunked, embedded, stored in [[Milvus]] (prod) or [[Qdrant]] (dev). Queried via semantic similarity search + reranker.
- **Structured RAG (SQL):** [[Vanna.AI]] converts natural language to SQL, queries [[PostgreSQL]]. Used for order history and room/booking data.
- **Hotel Knowledge RAG:** Dedicated `hotel_knowledge/` retriever using hotel-specific documents.

## How it shows up in this project

- `src/retrievers/unstructured_data/` — canonical RAG pipeline
- `src/retrievers/structured_data/` — SQL RAG via Vanna.AI
- `src/retrievers/hotel_knowledge/` — hotel domain RAG
- `src/hotel_guardrails/actions.py` — `search_hotel_knowledge` tool
- Embed → store handled by [[ingest_service]]
- Reranking: NVIDIA NIM reranker (prod) / Qwen3-0.6B (dev)

## Open questions

- Optimal chunking strategy for hotel policy documents?
- How does RAG quality compare between Milvus and Qdrant on hotel queries?

## Related

- [[retrievers]]
- [[Milvus]]
- [[Qdrant]]
- [[Vanna.AI]]
- [[hotel_guardrails]]
