# Archived: `src/retrievers/` (NVIDIA blueprint portion)

This directory contains code from the original [NVIDIA AI Blueprint for AI Virtual Assistant](https://github.com/NVIDIA-AI-Blueprints/ai-virtual-assistant) that the Hotel AI Virtual Assistant thesis project forked from but does **NOT** actively use.

## Why preserved

1. **Attribution to upstream** — the Milvus + Vanna.AI retriever stack is a defining feature of the NVIDIA reference architecture.
2. **Reproducibility** — preserved so anyone benchmarking against the NVIDIA stack can run the original retrievers verbatim.
3. **Thesis defense clarity** — documents the swap: NVIDIA used Milvus + NVIDIA embeddings + Vanna NL-to-SQL; the hotel thesis uses Qdrant + sentence-transformers + direct SQL.

## What is still active (NOT archived)

The hotel-specific retriever stack remains at the original path `src/retrievers/`:

- `src/retrievers/base.py` — shared `BaseExample` interface (used by `hotel_knowledge/`)
- `src/retrievers/hotel_knowledge/` — the hotel RAG retriever (Qdrant + sentence-transformers + Qwen3 reranker)

## Contents of this archive

| Sub-path | Original purpose |
|---|---|
| `Dockerfile` | Retriever microservice container build |
| `server.py` | FastAPI retriever endpoint (port 8086 / 8087) |
| `structured_data/` (`chains.py`, `prompt.yaml`, `__init__.py`, `requirements.txt`) | Vanna.AI NL-to-SQL retriever chain |
| `structured_data/vaanaai/` (`utils.py`, `vaana_base.py`, `vaana_llm.py`) | Vanna wrapper with NVIDIA embeddings + NVIDIA LLM |
| `unstructured_data/` (`chains.py`, `prompt.yaml`, `requirements.txt`) | Milvus document-RAG retriever chain |
