---
type: entity
category: model
status: active
tags: [entity, model, qwen, ollama, local, development]
created: 2026-04-19
updated: 2026-04-19
url: https://ollama.com/fredrezones55/qwen3.5-opus
---

# Qwen3.5 Opus 9B

A 9-billion-parameter dense model from the Qwen3.5 family, served locally via [[Ollama]] under the community image `fredrezones55/qwen3.5-opus:9b`. Used as the **development / local** LLM backend for [[hotel_guardrails]].

## Key Facts

| Property | Value |
|----------|-------|
| Model ID (Ollama) | `fredrezones55/qwen3.5-opus:9b` |
| Parameters | 9B (dense) |
| Cost | Free (local GPU) |
| Thinking | Built-in (on by default) |
| Default temperature | 0.3 |
| Default max tokens | 2048 |

## Performance (hotel assistant benchmark, 2026-04-06)

- **Overall accuracy:** 23/25 (92%) on 25-case hotel eval
- **Keyword accuracy:** 80%
- **Language accuracy:** 100% (EN + TH)
- **Avg latency:** 9,905 ms
- **p50 latency:** 9,049 ms
- **p95 latency:** 18,360 ms
- **Notable outlier:** K01 (breakfast query) took 34,624 ms

See [[model-eval-local-vs-cloud-2026-04-06]] and [[model-tuning-and-test-results-2026-04-03]] for full results.

## Notes

- Achieves 94% on the 34-case functional suite *after tuning* (pre-tuning: lower due to RAG context bug and multi-turn context loss)
- Recommended for development; switch to [[Qwen3-max]] for production
- Tool calling required prompt engineering to be reliable (see [[model-tuning-and-test-results-2026-04-03]], Fix 1)
