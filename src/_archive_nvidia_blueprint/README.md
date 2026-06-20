# `_archive_nvidia_blueprint/`

This directory contains code from the original [NVIDIA AI Blueprint for AI Virtual Assistant](https://github.com/NVIDIA-AI-Blueprints/ai-virtual-assistant) that the Hotel AI Virtual Assistant thesis project forked from but does **NOT** actively use.

## Why preserved

1. **Attribution to upstream** — the NVIDIA blueprint is the parent of this thesis project (Apache-2.0); keeping these files in-tree makes the fork relationship auditable.
2. **Reproducibility** — anyone who wants to compare the hotel-specific changes against the original NVIDIA reference implementation can do so without cloning two repos.
3. **Thesis defense clarity** — "this is the original blueprint, this is the hotel-specific work" is the single most repeated question in viva; archived files let the answer be pointed at concretely.

## What is still active (NOT archived)

The live hotel codebase lives in:

- `src/hotel_guardrails/` — primary FastAPI + LangGraph hotel assistant (deployed to Railway)
- `src/agent/hotel_tools.py` + `src/agent/hotel_prompt*.yaml` — hotel tool implementations and prompt variants
- `src/retrievers/hotel_knowledge/` + `src/retrievers/base.py` — hotel knowledge RAG retriever
- `src/common/` — shared LLM, embedding, reranker, vector-store wrappers (used by the active stack)

## What is archived here

| Sub-path | Original purpose | Why dropped from hotel stack |
|---|---|---|
| `agent/` (Dockerfile, main.py, prompt.yaml, server.py, tools.py, utils.py, cache/, datastore/, requirements.txt) | Original NVIDIA customer-service agent (ProductQA / OrderStatus / ReturnProcessing) | Replaced wholesale by `src/hotel_guardrails/` |
| `analytics/` | Sentiment + summarization microservice (NVIDIA NIM) | Not used by hotel assistant; out of scope for thesis evaluation |
| `api_gateway/` | HTTP proxy to the agent server | Hotel server is exposed directly via Railway; gateway unused |
| `ingest_service/` | CSV-to-SQL + document ingestion service | Hotel ingestion is done via `scripts/ingest_hotel_knowledge.py` directly |
| `retrievers/structured_data/` (incl. `vaanaai/`) | Vanna.AI NL-to-SQL retriever | Hotel uses direct SQL + structured tools, not Vanna |
| `retrievers/unstructured_data/` | Milvus + NVIDIA-embedding retriever | Hotel uses Qdrant + sentence-transformers via `hotel_knowledge/` |
| `retrievers/Dockerfile`, `retrievers/server.py` | Generic retriever microservice entrypoint | Hotel retriever is invoked in-process, no separate service |

## License

Files retained from the upstream blueprint remain under their original Apache-2.0 license (see `data/LICENSE` and per-file SPDX headers).
