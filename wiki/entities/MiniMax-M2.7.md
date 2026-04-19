---
type: entity
category: model
status: evaluated
tags: [entity, model, minimax, openrouter, budget-production]
created: 2026-04-19
updated: 2026-04-19
url: https://openrouter.ai/minimax/minimax-m2.7
---

# MiniMax M2.7

A Mixture-of-Experts (MoE) agentic model from MiniMax, accessed via [[OpenRouter]] at model ID `minimax/minimax-m2.7`. Evaluated as a **budget production** alternative to [[Qwen3-max]] for [[hotel_guardrails]].

## Key Facts

| Property | Value |
|----------|-------|
| Provider | MiniMax |
| Access | OpenRouter (`minimax/minimax-m2.7`) |
| Architecture | MoE (agentic) |
| Cost | $0.30 / $1.20 per 1M tokens (in/out) |
| Thinking | On (recommended) |
| Default temperature | 0.3 |
| Default max tokens | 2048 |

## Performance (hotel assistant benchmark, 2026-04-03)

| Task | Result | Time |
|------|--------|------|
| Thai breakfast query | PASS | ~39s |
| Thai spa query | PASS | ~32s |
| English booking (one-shot) | PASS | ~33s |
| Multi-turn Thai booking (5 turns) | Not tested | — |

## Assessment

- Passed all tested single-turn cases
- Significantly slower than [[Qwen3-max]] (30–40s vs 12–32s)
- Cost is 38% lower than Qwen3-max for input tokens
- Multi-turn context retention **not validated** — flagged as gap in [[gap-minimax-multiturn]]
- Produces bilingual (EN+TH) responses by default even for EN-only queries

## Role in Project

Identified as budget production option. Not currently deployed. See [[model-tuning-and-test-results-2026-04-03]] for comparison verdict.
