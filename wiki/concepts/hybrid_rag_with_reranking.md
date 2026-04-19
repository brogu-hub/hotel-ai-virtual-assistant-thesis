---
type: concept
status: mature
related:
  - concepts/model_context_protocol
  - concepts/persistent_memory_chatbot
tags: [concept, RAG, reranking, retrieval, hybrid-search, hotel-domain]
created: 2026-04-19
updated: 2026-04-19
---

# Hybrid RAG with Semantic Re-Ranking

## Definition

Hybrid RAG combines **dense vector search** (semantic "vibes") with **BM25 keyword search** (precise term matching), followed by a **re-ranking step** where a cross-encoder model scores retrieved documents by relevance before they are fed to the LLM. This prevents standard vector search from burying the most critical policy snippet under loosely related content.

## Origin

The pattern solidified circa 2023–2024 as hotel and enterprise RAG implementations revealed that pure vector search fails on domain-specific policy documents (e.g., "Spa Cancellation" policy retrieves instead of "Standard Cancellation" policy when user asks about cancellation).

MDPI Tourism AI Research studies (referenced 2025) specifically highlighted high traveler uncertainty around non-refundable bookings as the motivating problem.

## Components

| Component | Role |
|---|---|
| **Vector search** (Qdrant/Milvus + embeddings) | Semantic similarity — "vibe" questions like "is it cozy?" |
| **BM25 keyword search** | Exact term matching — "late check-out fee", policy names |
| **Metadata filtering** | Tag chunks with `category: policy`, `date_valid: 2026-Q1` to scope retrieval |
| **Re-ranker** (Cohere, BGE, Qwen3-0.6B) | Score retrieved docs; ensures most relevant snippet reaches the LLM |

## Variants & related concepts

- Standard RAG (without hybrid or reranking) — known to fail on domain-specific hotel policies
- [[concepts/persistent_memory_chatbot]] — complements memory-based personalization

## How it shows up in this project

The project implements retrieval in `src/retrievers/`:
- `unstructured_data/` — Milvus/Qdrant for document embeddings
- `hotel_knowledge/` — hotel-specific RAG
- `src/common/reranker_qwen.py` and `reranker_nvidia.py` — reranking implementations
- Metadata filtering on hotel knowledge base in `data/hotel/*.md`

The Qwen3-0.6B model (`src/common/reranker_qwen.py`) serves as the dev-stack reranker. NVIDIA reranker is used in production.

## Hotel-specific challenge: policy volatility

Hotel policies change seasonally (e.g., breakfast hours differ on Sundays). Static chunking without metadata date-validity tags means the bot may retrieve a stale policy. Mitigation: tag chunks with `date_valid` metadata and filter at query time.

## Key references

- Source: `LLM_CHATBOT_CRITIRION.md` (Gemini architecture conversation, 2026)
- [[papers/mdpi_tourism_ai_research]]

## Open questions

- Is BM25 hybrid search actually implemented, or only dense vector search?
- Are `date_valid` metadata tags applied to the `data/hotel/*.md` knowledge base chunks?
