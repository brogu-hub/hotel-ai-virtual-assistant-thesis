---
type: flow
entry_point: "POST /documents (retrievers server)"
endpoints: ["/documents"]
involves: [unstructured_retriever, hotel_knowledge_retriever, common, Milvus, Qdrant]
status: active
created: 2026-04-19
updated: 2026-04-19
tags: [flow, rag, ingest, chunking, embeddings, vectorstore]
---

# rag_ingest_pipeline

End-to-end document ingest flow shared by [[unstructured_retriever]] and [[hotel_knowledge_retriever]]. Covers the path from file upload to indexed, searchable chunks in the vector store.

## Trigger

`POST /documents` on the retrievers FastAPI server, or direct `ingest_docs()` call from `notebooks/ingest_data.ipynb`.

## Flow

```text
Client
  └─ POST /documents (multipart file)
       └─ server.py: save to /tmp-data/uploaded_files/
            └─ example.ingest_docs(filepath, filename)
                 │
                 ├─ [unstructured_data path]
                 │    ├─ UnstructuredFileLoader.load()        → raw Document list
                 │    ├─ get_text_splitter().split_documents() → chunks
                 │    └─ vectorstore.add_documents(chunks)    → Milvus / Qdrant
                 │
                 └─ [hotel_knowledge path]
                      ├─ direct read (md/txt) or UnstructuredFileLoader (pdf)
                      ├─ RecursiveCharacterTextSplitter.split_documents()
                      │    separators: \n## > \n### > \n\n > \n > ". " > "。" > " " > ""
                      ├─ annotate chunk.metadata["source"] = filename
                      └─ qdrant_vectorstore.add_documents(chunks)
```

## Chunking strategy

| Sub-service | Splitter | Chunk size | Overlap |
| --- | --- | --- | --- |
| `unstructured_data` | From `APP_TEXTSPLITTER_MODELNAME` (config) | Config-driven | Config-driven |
| `hotel_knowledge` | `RecursiveCharacterTextSplitter` (markdown-aware) | Auto from embedding token limit × 0.8 × 4 chars/token | 20% of chunk size |

The hotel knowledge splitter's auto-sizing ensures chunks stay within the embedding model's context window. Env vars `CHUNK_SIZE` and `CHUNK_OVERLAP` override the auto values.

## Embedding

Both paths call into [[common]] utilities (`get_embedding_model()` or `get_openrouter_embeddings()`) which resolve to:

- **Production:** NVIDIA NIM embedding endpoint
- **Development:** OpenRouter embeddings (hotel_knowledge) or sentence-transformers (unstructured)

## Vector stores

| Sub-service | Prod | Dev |
| --- | --- | --- |
| `unstructured_data` | [[Milvus]] | [[Qdrant]] |
| `hotel_knowledge` | [[Qdrant]] | [[Qdrant]] |
| `structured_data` | N/A — SQL, not vector | N/A |

## Supported file types

`.txt`, `.pdf`, `.md`. Any other extension raises `ValueError` before loading.

## Batch ingest

`notebooks/ingest_data.ipynb` calls `ingest_docs()` directly for bulk loading of the `data/hotel/` knowledge base at environment setup time.

## Related

- [[unstructured_retriever]], [[hotel_knowledge_retriever]]
- [[retriever_unstructured_ingest_pipeline]] — component detail for unstructured path
- [[RAG]], [[hybrid_rag_with_reranking]]
- [[Milvus]], [[Qdrant]]
