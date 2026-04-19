---
type: component
path: "src/retrievers/unstructured_data/chains.py"
parent_module: unstructured_retriever
status: active
language: python
purpose: "Chunking, embedding, and vector-store write pipeline for unstructured documents"
created: 2026-04-19
updated: 2026-04-19
tags: [component, retriever, ingest, chunking, embeddings, vectorstore]
---

# retriever_unstructured_ingest_pipeline

The ingest half of [[unstructured_retriever]]. Called when `POST /documents` receives a file upload.

## Steps

```text
1. Validate extension (.txt / .pdf / .md only)
2. UnstructuredFileLoader(filepath).load()   → List[Document]
3. get_text_splitter()                        → splitter (lazy-init, cached)
4. splitter.split_documents(raw_documents)   → List[Document] (chunks)
5. get_vectorstore(vectorstore, embedder)    → live VS handle
6. vs.add_documents(chunks)                  → persist to Milvus / Qdrant
```

## Text splitter

Selected via `APP_TEXTSPLITTER_MODELNAME`. The splitter's tokenizer dimension must match the embedding model's to avoid silent truncation. Instance is created once on first call and cached in a module-level `text_splitter` variable.

## Embedding model

Module-level singleton: `document_embedder = get_embedding_model()`. In production this resolves to NVIDIA NIM embeddings; in development to sentence-transformers or OpenRouter embeddings (via [[common]] utilities).

## Error handling

Any exception during load, split, or store raises `ValueError("Failed to upload document…")`, which the server returns as HTTP 500.

## Related

- [[unstructured_retriever]] — parent module
- [[rag_ingest_pipeline]] — flow page covering end-to-end ingest
- [[Milvus]], [[Qdrant]]
