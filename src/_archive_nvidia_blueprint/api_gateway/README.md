# Archived: `src/api_gateway/` (NVIDIA blueprint)

This directory contains code from the original [NVIDIA AI Blueprint for AI Virtual Assistant](https://github.com/NVIDIA-AI-Blueprints/ai-virtual-assistant) that the Hotel AI Virtual Assistant thesis project forked from but does **NOT** actively use.

(The original upstream README is preserved as `README_upstream.md` in this directory.)

## Why preserved

1. **Attribution to upstream** — the API gateway is a microservice in the NVIDIA reference architecture.
2. **Reproducibility** — preserved so anyone replaying the full NVIDIA stack can do so from this repo.
3. **Thesis defense clarity** — documents that the hotel deployment removed the gateway layer (Railway exposes the FastAPI server directly).

## What is still active (NOT archived)

Nothing. In the hotel deployment, `src/hotel_guardrails/server.py` is exposed directly via Railway with no separate gateway.

## Contents

| File | Original purpose |
|---|---|
| `Dockerfile` | Gateway container build |
| `README_upstream.md` | Original NVIDIA gateway README (swagger / openapi pointer) |
| `main.py` | HTTP proxy that routes `/chat` requests to the agent server on port 9000 |
| `requirements.txt` | Gateway pip deps |
