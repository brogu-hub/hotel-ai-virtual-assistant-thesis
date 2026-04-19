---
type: entity
category: product
status: active
url: "https://ollama.com"
created: 2026-04-19
updated: 2026-04-19
tags: [entity, llm, local, inference]
---

# Ollama

Local LLM inference server. Runs models on the host GPU, exposing an OpenAI-compatible HTTP API.

## Role in this project

Primary LLM backend for local development. Replaces NVIDIA NIM endpoints so dev work is free and offline-capable.

- **Port**: 11435 (inside Docker stack `hotel-ollama`)
- **Default model**: `qwen3.5-opus:9b`
- **Parallelism**: `OLLAMA_NUM_PARALLEL=4` (set in `docker-compose.hotel.yaml`)

## Runtime switching

The admin `PUT /settings/llm` endpoint can switch between Ollama and OpenRouter at runtime without a server restart. See [[admin_monitoring]].

## Parallelism note

Ollama serialises requests by default (`OLLAMA_NUM_PARALLEL=1`). The project sets `OLLAMA_NUM_PARALLEL=4` to match `MAX_CONCURRENT_LLM_CALLS=4` in the app semaphore. See [[chat_scaling]].

## Models used

- [[Qwen3.5-Opus-9B]] — primary dev model, 92% eval pass rate

## Related

- [[chat_scaling]] — how the app semaphore aligns with Ollama slots
- [[local_run]] — Docker stack setup
- [[decisions/ollama_migration]] — migration from NVIDIA NIM to Ollama for local dev
