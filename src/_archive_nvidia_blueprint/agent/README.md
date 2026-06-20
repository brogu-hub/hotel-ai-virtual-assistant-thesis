# Archived: `src/agent/` (NVIDIA blueprint portion)

This directory contains code from the original [NVIDIA AI Blueprint for AI Virtual Assistant](https://github.com/NVIDIA-AI-Blueprints/ai-virtual-assistant) that the Hotel AI Virtual Assistant thesis project forked from but does **NOT** actively use.

## Why preserved

1. **Attribution to upstream** — keeps the NVIDIA reference implementation visible alongside the hotel fork.
2. **Reproducibility** — `main.py` is the StateGraph the hotel architecture was modelled after; auditors can diff hotel changes against the original.
3. **Thesis defense clarity** — these are the customer-service agent (ProductQA / OrderStatus / ReturnProcessing) workflows the thesis explicitly replaced.

## What is still active (NOT archived)

The hotel-specific files remain at the original path `src/agent/`:

- `src/agent/__init__.py`
- `src/agent/hotel_tools.py`
- `src/agent/hotel_prompt.yaml`
- `src/agent/hotel_prompt_stackoff.yaml`
- `src/agent/hotel_prompt_gemma4_31b_cloud.yaml`

The active hotel codebase lives in `src/hotel_guardrails/`, with hotel tool implementations imported from `src/agent/hotel_tools.py` and knowledge retrieval from `src/retrievers/hotel_knowledge/`.

## Contents of this archive

| File | Original purpose |
|---|---|
| `Dockerfile` | Container build for the NVIDIA agent server |
| `main.py` | Original `StateGraph` with `validate_product_info → router → ProductQA/OrderStatus/ReturnProcessing` |
| `prompt.yaml` | Customer-service agent prompts (gear-store / returns flow) |
| `server.py` | FastAPI server using `Datastore` + `SessionManager` |
| `tools.py` | `structured_rag`, `canonical_rag`, purchase history, returns tools |
| `utils.py` | `get_product_name`, checkpointer helpers, tool-node fallbacks |
| `requirements.txt` | NVIDIA-stack pip deps (langchain-nvidia-ai-endpoints, etc.) |
| `cache/` | LocalCache + Redis-backed session storage |
| `datastore/` | Postgres-backed conversation datastore |
