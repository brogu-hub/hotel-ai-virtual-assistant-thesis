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

## Eval Results (2026-04-06, 25-case hotel benchmark)

| Metric | Value |
|--------|-------|
| Overall accuracy | 25/25 (100%) |
| Keyword accuracy | 88% |
| Language accuracy (EN+TH) | 100% |
| Avg latency | 8,852 ms |
| p50 latency | 6,703 ms |
| p95 latency | 13,933 ms |
| Cost | $0.78 / $3.90 per 1M tokens (in/out) |

See [[model-eval-local-vs-cloud-2026-04-06]] and [[model-tuning-and-test-results-2026-04-03]].

## Model Preset

Temperature: 0.3, max tokens: 2048, thinking: on (reasoning param).

## Related

- [[OpenRouter]]
- [[Llama 3.3 70B]]
- [[hotel_guardrails]]
- [[ADR OpenRouter Dev Backend]]
- [[Qwen3.5-Opus-9B]] — local dev counterpart
- [[MiniMax-M2.7]] — budget cloud alternative
