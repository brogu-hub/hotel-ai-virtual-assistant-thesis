---
type: entity
category: model
url: https://build.nvidia.com/meta/llama-3_3-70b-instruct
tags: [entity, model, meta, llama, llm, production]
created: 2026-04-19
updated: 2026-04-19
---

# Llama 3.3 70B

## What it is

Meta's Llama 3.3 70B Instruct — the production LLM for this project, served via NVIDIA NIM at `api.nvidia.com`.

## Role in this project

Production inference backend for both `src/agent/` (original blueprint) and optionally `src/hotel_guardrails/` when `APP_LLM_MODELENGINE=nvidia-ai-endpoints`. The upstream NVIDIA blueprint prompts are tuned specifically for this model.

## Key facts

- Model ID (NIM): `meta/llama-3.3-70b-instruct`
- Environment variable: `APP_LLM_MODELNAME=meta/llama-3.3-70b-instruct`
- Self-hosted minimum: 8×H100 or 8×A100
- Original blueprint also references Llama 3.1 70B for self-hosted; cloud-hosted upgrades to 3.3
- Prompts in `src/agent/prompt.yaml` and `src/agent/hotel_prompt.yaml` tuned for this model family

## Related

- [[NVIDIA]]
- [[Qwen3-max]]
- [[agent]]
- [[hotel_guardrails]]
