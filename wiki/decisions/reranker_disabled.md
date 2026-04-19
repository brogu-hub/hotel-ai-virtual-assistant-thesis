---
type: decision
status: active
date: 2026-04-19
context: "RAG pipeline performance — CrossEncoder reranker in hot path"
created: 2026-04-19
updated: 2026-04-19
tags: [decision, rag, reranker, performance]
---

# Decision: Reranker Disabled by Default (RERANKER_BACKEND=none)

## Status

Active.

## Context

The `hotel_guardrails` RAG pipeline originally included a CrossEncoder reranker (`RERANKER_BACKEND=qwen` using Qwen3-0.6B) after Qdrant vector search to re-score retrieved chunks.

## Problem

- Added ~1–2 seconds of CPU-bound work **per RAG query**.
- Being synchronous inside an async FastAPI endpoint, it **blocked the entire event loop** for that duration.
- This stalled all other concurrent requests while any single knowledge query was processing.

## Decision

Set `RERANKER_BACKEND=none` as the new default. Remove the reranker from the hot path.

## Rationale

Qdrant embedding-based vector search is accurate enough for the hotel knowledge base:
- 10 well-structured markdown documents.
- Queries are narrow hotel-domain questions with low ambiguity.
- Embedding similarity alone achieves acceptable retrieval quality.

## Consequences

- ~1–2 s saved per RAG query.
- Event loop no longer blocked by CPU-bound reranking.
- `RERANKER_BACKEND=qwen` and `RERANKER_BACKEND=nvidia` remain available for environments with low-quality embeddings.

## Related

- [[chat_scaling]] — event loop protection rationale
- [[guest_chat]] — flow that benefits from the removal
