---
type: module
path: "src/retrievers/unstructured_data/chains.py"
status: active
language: python
purpose: "Document embedding retriever — chunks, embeds, and vector-searches unstructured text/PDF/Markdown files"
maintainer: Mangakorian
created: 2026-04-19
updated: 2026-04-19
port: 8086
depends_on: [common, retrievers]
used_by: [agent]
tags: [module, retriever, rag, embeddings, milvus, qdrant]
---

# unstructured_retriever

Sub-service of [[retrievers]]. Provides full-text RAG over uploaded documents (`.txt`, `.pdf`, `.md`). Runs on **port 8086**.

## Responsibility

- Accept document uploads and chunk them into fixed-size overlapping segments.
- Embed each chunk using the configured embedding model and store in the vector store.
- On search, embed the query, retrieve top-K candidates from the vector store, and optionally rerank before returning.

## Key class

`UnstructuredRetriever` in `src/retrievers/unstructured_data/chains.py` — implements [[retriever_base_example]].

## Ingest pipeline

```python
UnstructuredFileLoader(filepath).load()
  → get_text_splitter()           # env: APP_TEXTSPLITTER_MODELNAME
  → text_splitter.split_documents()
  → vectorstore.add_documents()   # Milvus (prod) / Qdrant (dev)
```

Supported formats: `.txt`, `.pdf`, `.md`. Other extensions raise `ValueError`.

The text splitter model is expected to share the same tokenizer dimension as the embedding model to avoid truncation artefacts.

## Search pipeline

```python
query (+ conv_history?) → query_rewriting (optional LLM step)
  → vectorstore.as_retriever(k=VECTOR_DB_TOPK)
  → [reranker.compress_documents() if ranker else raw docs]
  → List[{source, content, score}]
```

**Query rewriting** is triggered when `conv_history` is non-empty. The LLM is called with a structured-output schema (`Question`) to produce a decontextualized standalone question before the vector search. The prompt is loaded from `prompt.yaml` under the `query_rewriting` key.

**Reranker** is optional. `VECTOR_DB_TOPK` (default 40) is used for the initial over-fetch; the reranker then narrows to `num_docs`. When no reranker is configured the raw top-K results are returned directly.

Decision context: see [[reranker_disabled]] for why the reranker is off by default in the hotel knowledge path.

## Environment variables

| Variable | Default | Effect |
| --- | --- | --- |
| `VECTOR_DB_TOPK` | `40` | Initial fetch size before reranking |
| `APP_TEXTSPLITTER_MODELNAME` | (from config) | Tokenizer for chunk sizing |
| `APP_VECTORSTORE_NAME` | `qdrant` / `milvus` | Vector store backend |
| `APP_VECTORSTORE_URL` | — | Vector store connection URL |

## Prompt template

`src/retrievers/unstructured_data/prompt.yaml`:

```yaml
query_rewriting: |
  "Given a chat history and the latest user question … formulate a standalone
  question … Do NOT answer the question, just reformulate it …"
```

## Storage backends

| Environment | Backend | Notes |
| --- | --- | --- |
| Production | [[Milvus]] | NVIDIA NIM embeddings |
| Development | [[Qdrant]] | sentence-transformers or OpenRouter embeddings |

## Related

- [[retrievers]] — parent module
- [[retriever_base_example]] — interface contract
- [[retriever_unstructured_ingest_pipeline]] — component detail
- [[rag_ingest_pipeline]] — end-to-end ingest flow
- [[RAG]], [[hybrid_rag_with_reranking]]
- [[Milvus]], [[Qdrant]]
