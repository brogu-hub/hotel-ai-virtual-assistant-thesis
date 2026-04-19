---
type: module
path: src/ingest_service/
status: active
language: python
purpose: "Document ingestion to vector store and CSV-to-SQL import"
maintainer: Mangakorian
last_updated: 2026-04-19
depends_on: [common]
used_by: []
linked_issues: []
tags: [module, ingest_service, rag, data]
created: 2026-04-19
updated: 2026-04-19
---

# ingest_service

## Purpose

Handles one-time and on-demand ingestion of documents into the vector store ([[Milvus]] or [[Qdrant]]) and CSV data into [[PostgreSQL]]. Supporting the data pipeline for RAG.

## Key operations

- Unstructured data (PDFs, hotel knowledge `.md` files) → chunk → embed → store in vector DB
- Structured data (CSV: `data/gear-store.csv`, `data/orders.csv`) → parse → insert into PostgreSQL
- Triggered via `notebooks/ingest_data.ipynb` (JupyterLab on port 8889)

## Dependencies

- External: [[Milvus]], [[Qdrant]], [[PostgreSQL]], NVIDIA NIM embeddings (prod) / sentence-transformers (dev)
- Internal: [[common]]

## Related

- [[retrievers]]
- [[RAG]]
- [[Milvus]]
- [[Qdrant]]
