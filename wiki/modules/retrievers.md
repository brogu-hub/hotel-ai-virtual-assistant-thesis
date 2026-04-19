---
type: module
path: "src/retrievers/"
status: active
language: python
purpose: "Three RAG retriever microservices — unstructured document search, structured NL-to-SQL, and hotel-specific knowledge"
maintainer: Mangakorian
created: 2026-04-19
updated: 2026-04-19
depends_on: [common]
used_by: [hotel_guardrails, agent]
tags: [module, retrievers, rag, fastapi]
---

# retrievers

Overview and navigation page for the three RAG retriever microservices under `src/retrievers/`.

## Architecture

All three sub-services share a single FastAPI application defined in `src/retrievers/server.py`. The server discovers its concrete implementation at startup by scanning a path given in the `EXAMPLE_PATH` environment variable, looking for a class that implements the [[retriever_base_example]] interface (`ingest_docs`, `document_search`, `get_documents`, `delete_documents`).

```
POST /documents   — ingest a file (multipart upload)
POST /search      — semantic / NL-to-SQL search
GET  /documents   — list ingested files
DELETE /documents — remove a file by name
GET  /health      — liveness probe
```

The same server binary serves whichever sub-service is mounted at startup. Docker Compose selects the sub-service via `EXAMPLE_PATH`.

## Sub-services

| Sub-service | Page | Port | Storage | Purpose |
|---|---|---|---|---|
| `unstructured_data/` | [[unstructured_retriever]] | 8086 | [[Milvus]] / [[Qdrant]] | Document embedding + similarity search |
| `structured_data/` | [[structured_retriever]] | 8087 | [[PostgreSQL]] + [[Milvus]] | NL-to-SQL via [[Vanna.AI]] |
| `hotel_knowledge/` | [[hotel_knowledge_retriever]] | — | [[Qdrant]] | Hotel-specific bilingual RAG |

## Shared base contract

`src/retrievers/base.py` defines `BaseExample` (abstract base class). Every sub-service chain must implement:

- `document_search(content, num_docs, ...) -> List[Dict]`
- `get_documents() -> List[str]`
- `delete_documents(filenames) -> bool`
- `ingest_docs(filepath, filename) -> None`

## Data flow

```
Caller (hotel_guardrails / agent)
  └─ POST /search {query, top_k, user_id?, conv_history?}
       └─ server.py dispatch
            ├─ UnstructuredRetriever.document_search()  (port 8086)
            ├─ CSVChatbot.document_search()             (port 8087)
            └─ HotelKnowledgeRetriever.document_search() (hotel_knowledge)
```

## Component pages

- [[retriever_base_example]] — shared abstract interface
- [[retriever_unstructured_ingest_pipeline]] — chunking + embedding + vectorstore write path
- [[retriever_vanna_wrapper]] — Vanna.AI NL-to-SQL + SQL safety layer

## Flow pages

- [[rag_ingest_pipeline]] — end-to-end ingest flow (chunk → embed → index)

## Related concepts & entities

- [[RAG]], [[hybrid_rag_with_reranking]]
- [[Milvus]], [[Qdrant]], [[Vanna.AI]], [[PostgreSQL]]
- [[hotel_guardrails]], [[agent]]
