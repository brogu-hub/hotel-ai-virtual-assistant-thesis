---
type: entity
category: product
url: https://openrouter.ai
tags: [entity, product, llm, openrouter, dev-backend]
created: 2026-04-19
updated: 2026-04-19
---

# OpenRouter

## What it is

OpenRouter is an LLM routing API that provides unified access to many model providers (Alibaba, Meta, Mistral, etc.) via a single OpenAI-compatible endpoint.

## Role in this project

OpenRouter is the **development LLM backend** for `hotel_guardrails`. It replaces NVIDIA NIM when running locally or on Railway, allowing development without enterprise GPU hardware. The `OPENROUTER_API_KEY` environment variable gates all calls.

## Key facts

- Default dev model: `qwen/qwen3-max` (Alibaba [[Qwen3-max]])
- Wrapper: `src/hotel_guardrails/openrouter_llm.py` and `src/common/llm_openrouter.py`
- Controlled via `APP_LLM_MODELENGINE=openrouter`
- Also used for: embeddings (`src/common/embeddings_openrouter.py`), reranker (`src/common/reranker_qwen.py`)
- Railway deployment uses OpenRouter exclusively (no NVIDIA NIM)

## Related

- [[Qwen3-max]]
- [[hotel_guardrails]]
- [[common]]
- [[ADR OpenRouter Dev Backend]]
- [[LLM Fallback Chain]]
