---
type: entity
category: model
url: https://openrouter.ai/models/qwen/qwen3-max
tags: [entity, model, alibaba, qwen, llm]
created: 2026-04-19
updated: 2026-04-19
---

# Qwen3-max

## What it is

Qwen3-max is Alibaba's flagship chat/reasoning model from the Qwen3 family, accessed in this project via [[OpenRouter]] (`qwen/qwen3-max`).

## Role in this project

Default development LLM for the [[hotel_guardrails]] service. Handles all primary assistant reasoning, sub-agent routing, and tool-call generation during local and Railway-deployed runs.

## Key facts

- Model ID on OpenRouter: `qwen/qwen3-max`
- Environment variable: `APP_LLM_MODELNAME=qwen/qwen3-max`
- Reranker counterpart: `Qwen3-0.6B` (`src/common/reranker_qwen.py`)
- Org: Alibaba Cloud
- Prompts tuned for Llama 3.1/3.3 in the upstream blueprint; may need prompt adjustment for Qwen3

## Related

- [[OpenRouter]]
- [[Llama 3.3 70B]]
- [[hotel_guardrails]]
- [[ADR OpenRouter Dev Backend]]
