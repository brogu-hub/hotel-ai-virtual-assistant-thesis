# Archived: `src/analytics/` (NVIDIA blueprint)

This directory contains code from the original [NVIDIA AI Blueprint for AI Virtual Assistant](https://github.com/NVIDIA-AI-Blueprints/ai-virtual-assistant) that the Hotel AI Virtual Assistant thesis project forked from but does **NOT** actively use.

(The original upstream README is preserved as `README_upstream.md` in this directory.)

## Why preserved

1. **Attribution to upstream** — the analytics microservice (sentiment + conversation summarization) is part of the NVIDIA reference architecture diagram.
2. **Reproducibility** — preserved so anyone benchmarking the full NVIDIA blueprint can rebuild it from this repo.
3. **Thesis defense clarity** — clarifies that the hotel thesis intentionally scoped analytics out (sentiment/summarization were not evaluated).

## What is still active (NOT archived)

Nothing from this directory is referenced by the active hotel stack. The hotel assistant lives in `src/hotel_guardrails/`, with no sentiment or summarization microservice.

## Contents

| File | Original purpose |
|---|---|
| `Dockerfile` | Analytics service container build |
| `README_upstream.md` | Original NVIDIA analytics README (data-persistence configuration) |
| `main.py` | Sentiment + summarization entrypoint (NVIDIA NIM) |
| `prompt.yaml` | Sentiment / summarization prompts |
| `server.py` | FastAPI server on port 8082 |
| `requirements.txt` | NVIDIA-stack pip deps |
| `datastore/` | Postgres + Redis session storage for analytics |
