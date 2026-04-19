---
type: decision
status: active
date: 2026-04-19
owner: "Mangakorian"
context: "Vector store selection for the hotel assistant — two environments with different hardware constraints"
supersedes: []
superseded_by: []
tags: [decision]
created: 2026-04-19
updated: 2026-04-19
---

# ADR: Qdrant (Dev / Railway) vs. Milvus (Production Blueprint) Split

*Retroactive ADR written 2026-04-19; decision was made when adapting the NVIDIA Blueprint stack for the hotel service.*

## Context

The NVIDIA Blueprint uses Milvus as its vector store, deployed as `milvus-standalone` with MinIO + etcd backing. Milvus is GPU-optimized and designed for large-scale embeddings at production throughput. The hotel knowledge base is 10 structured Markdown documents — far below Milvus's target scale. Milvus's production container stack (Milvus + MinIO + etcd) is heavy for a single-developer dev loop and incompatible with Railway's free-tier container model.

The hotel_guardrails service needed a vector store for knowledge RAG that would run on Railway, in Docker Compose dev, and without GPU hardware.

## Options considered

- **Option A — Qdrant everywhere**
  - Pros: Single vector store to operate; Qdrant Cloud has a free tier; REST/gRPC API; Rust binary is lightweight; Railway-hosted Qdrant works out of the box; `src/common/vectorstore_qdrant.py` adapter already written
  - Cons: Diverges from the NVIDIA Blueprint default; Milvus-based production claims in the thesis are weaker

- **Option B — Milvus everywhere**
  - Pros: Full alignment with NVIDIA Blueprint; GPU-accelerated at scale; well-documented with NeMo Retriever NIMs
  - Cons: Cannot run on Railway (no persistent volume large enough, no GPU); heavy local dev setup (docker-compose pulls ~3 GB of images); overkill for 10 hotel documents

- **Option C — Qdrant for dev/Railway, Milvus for production blueprint**
  - Pros: Each store is used where it fits; `APP_VECTORSTORE_NAME` toggles between them; production baseline matches NVIDIA Blueprint exactly
  - Cons: Two code paths to maintain; embeddings must be compatible across both; team (of one) must understand both systems

## Decision

Use the split (Option C): `APP_VECTORSTORE_NAME=qdrant` for development and Railway; `APP_VECTORSTORE_NAME=milvus` for the production NVIDIA blueprint stack. The switch is a single environment variable. The hotel_guardrails service uses Qdrant exclusively; the original blueprint's `src/retrievers/unstructured_data/` keeps Milvus.

## Consequences

- Positive: Development and Railway deployment work without any GPU or heavyweight container overhead. Qdrant Cloud's free tier covers the hotel knowledge base indefinitely. Embedding-based retrieval with Qdrant achieves 100% per-category accuracy on the knowledge test cases (see [[model-eval-local-vs-cloud-2026-04-06]]).
- Negative / trade-offs: The production NVIDIA NIM + Milvus path is not actively tested in this thesis cycle — it exists as configuration but is not empirically exercised. If scaling beyond the 10-document knowledge base, Qdrant's single-node Railway deployment may need rethinking. Two vector store clients increase package dependencies.
- Revisit if: The hotel knowledge base grows to hundreds of documents and Qdrant single-node becomes a bottleneck; or if the thesis requires an end-to-end Milvus + NIM production run.

## Related

- [[Qdrant]] — dev/Railway vector store
- [[Milvus]] — production blueprint vector store
- [[hotel_guardrails]] — service using Qdrant
- [[retrievers]] — original blueprint retrievers using Milvus
- [[common]] — `vectorstore_qdrant.py` adapter
- [[Railway]] — deployment target where Qdrant is hosted
- [[reranker_disabled]] — related RAG pipeline decision
