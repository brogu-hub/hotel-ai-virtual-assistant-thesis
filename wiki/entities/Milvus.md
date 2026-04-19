---
type: entity
category: product
url: https://milvus.io
tags: [entity, product, vectorstore, production]
created: 2026-04-19
updated: 2026-04-19
---

# Milvus

## What it is

Milvus is an open-source, GPU-optimized vector database designed for high-performance similarity search at scale.

## Role in this project

Milvus is the **production vector store** for unstructured data retrieval. Used by `src/retrievers/unstructured_data/` to store document embeddings. Set via `APP_VECTORSTORE_NAME=milvus`.

## Key facts

- Deployed as `milvus-standalone` container in Docker Compose (production stack)
- Requires a GPU (L40 or similar recommended) for optimal performance
- Storage backed by MinIO (object store) + etcd (metadata)
- Port: 19530 (gRPC), 9091 (HTTP)
- Not used in dev; [[Qdrant]] is used instead
- Data ingestion via `notebooks/ingest_data.ipynb`

## Related

- [[Qdrant]]
- [[retrievers]]
- [[ADR Qdrant Milvus Split]]
- [[RAG]]
