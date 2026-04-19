---
type: module
path: "src/retrievers/hotel_knowledge/chains.py"
status: active
language: python
purpose: "Hotel-specific bilingual (Thai/English) RAG retriever backed by Qdrant and OpenRouter embeddings"
maintainer: Mangakorian
created: 2026-04-19
updated: 2026-04-19
port: null
depends_on: [common, retrievers, Qdrant]
used_by: [hotel_guardrails]
tags: [module, retriever, rag, qdrant, openrouter, bilingual, hotel]
---

# hotel_knowledge_retriever

Sub-service of [[retrievers]]. Provides hotel-specific RAG over the knowledge base documents in `data/hotel/`. Unlike the generic [[unstructured_retriever]], this service is purpose-built for [[The Grand Horizon Hotel]] and supports bilingual Thai/English queries. No assigned port — called directly by [[hotel_guardrails]] via the `knowledge_subagent`.

## Key class

`HotelKnowledgeRetriever` in `src/retrievers/hotel_knowledge/chains.py` — implements [[retriever_base_example]].

## Ingest pipeline

```text
filepath (.md/.txt/.pdf)
  → direct file read (md/txt) or UnstructuredFileLoader (pdf)
  → RecursiveCharacterTextSplitter (markdown-aware separators)
  → add source metadata to each chunk
  → Qdrant vectorstore.add_documents()
```

Chunk size is **auto-calculated** from the embedding model's token limit:

```python
chunk_size  = int(token_limit * safety_margin * chars_per_token)  # ~80% of limit × 4 chars/token
chunk_overlap = int(chunk_size * overlap_ratio)                   # default 20%
```

Overridable via `CHUNK_SIZE` and `CHUNK_OVERLAP` env vars for backward compatibility.

Text splitter separator priority: `\n## ` → `\n### ` → `\n\n` → `\n` → `. ` → `。` → ` ` → `""`. The Thai sentence separator `。` is included explicitly for bilingual documents.

## Search pipeline

```text
query (Thai or English)
  → Qdrant retriever (k=TOP_K_RETRIEVAL, default 30)
  → [reranker.compress_documents() if RERANKER_BACKEND != "none"]
  → trim to num_docs
  → List[{source, content, score}]
  → audit_logger.log_rag_pipeline() (if available)
```

No query rewriting step (unlike [[unstructured_retriever]]). The embedding model is expected to handle bilingual queries natively.

## Reranker configuration

Controlled by `RERANKER_BACKEND` env var:

| Value | Behaviour |
| --- | --- |
| `none` (default) | Skip reranking — return top-N vector results directly |
| `qwen` | Local CPU CrossEncoder via `src/common/reranker_qwen.py` |
| `nvidia` | NVIDIA NIM reranker API via `src/common/reranker_nvidia.py` |

Reranking is **off by default**. The rationale (documented in code): reranking added 1–2 seconds of CPU-bound work that blocked the FastAPI async event loop, hurting concurrent throughput. The embedding search alone provides sufficient recall for hotel knowledge. See also [[reranker_disabled]].

## Embedding model

`src/common/embeddings_openrouter.py` — `get_openrouter_embeddings()`. The default model is `DEFAULT_EMBEDDING_MODEL` from that module (expected to be an OpenRouter-hosted embedding model, likely `qwen-3-embedding-8b` or similar based on project naming). Token limits are queried from `get_model_token_limit()` to auto-size chunks.

> [!note] Model entity gap
> The specific OpenRouter embedding model name (`DEFAULT_EMBEDDING_MODEL`) is defined in `src/common/embeddings_openrouter.py` — not confirmed here. No entity page exists for it yet. Check `embeddings_openrouter.py` to create one if needed.

## Audit logging

`document_search` calls `audit_logger.log_retrieval()` and `audit_logger.log_rag_pipeline()` if `src/common/audit_logger` is importable. This captures per-query latency broken down into retrieval and reranking phases.

## Additional methods

Beyond the base interface:

- `ingest_text(text, source)` — ingest raw string directly (no file path needed).
- `clear_collection()` — wipe and recreate the Qdrant collection.

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `RERANKER_BACKEND` | `none` | `none` / `qwen` / `nvidia` |
| `NVIDIA_API_KEY` | — | Required only when `RERANKER_BACKEND=nvidia` |
| `EMBEDDING_MODEL` | `DEFAULT_EMBEDDING_MODEL` | Override embedding model name |
| `CHUNK_SIZE` | auto-calculated | Characters per chunk |
| `CHUNK_OVERLAP` | auto-calculated | Overlap characters between chunks |
| `TOP_K_RETRIEVAL` | `30` | Initial vector search fetch size |
| `TOP_K_RERANK` | `5` | Results returned after reranking (or direct) |

## Knowledge base documents

Source files live in `data/hotel/` (`.md` format): dining, facilities, room types, policies, etc. Ingestion is triggered via `notebooks/ingest_data.ipynb`.

## Related

- [[retrievers]] — parent module
- [[retriever_base_example]] — interface contract
- [[hotel_guardrails]] — primary caller (via [[knowledge_subagent]])
- [[rag_ingest_pipeline]] — end-to-end ingest flow
- [[RAG]], [[hybrid_rag_with_reranking]]
- [[Qdrant]], [[The Grand Horizon Hotel]]
- [[reranker_disabled]] — decision on why reranking is off
