---
type: decision
status: active
date: 2026-04-19
owner: "Mangakorian"
context: "The NVIDIA Blueprint assumes NVIDIA NIM endpoints for LLM inference; the thesis dev environment has no GPU hardware"
supersedes: []
superseded_by: []
tags: [decision]
created: 2026-04-19
updated: 2026-04-19
---

# ADR: OpenRouter / Qwen3-max as Development LLM Backend

*Retroactive ADR written 2026-04-19; decision was made during initial adaptation of the NVIDIA Blueprint to the hotel domain.*

## Context

The NVIDIA Blueprint's original LLM backend is Llama 3.3 70B via NVIDIA NIM hosted at `api.nvidia.com`, requiring either an NVIDIA API key with NIM credits or self-hosted hardware (minimum 8×H100 / 8×A100). Neither is available for day-to-day development. The thesis needed a cost-effective LLM backend that:

1. Is OpenAI-API-compatible (minimal code changes to the LangChain wrappers)
2. Has strong multilingual capability (English + Thai)
3. Has per-call pricing suitable for a development/demo workload
4. Can be swapped back to NVIDIA NIM for a "production-equivalent" baseline

## Options considered

- **Option A — OpenRouter with Qwen3-max as default**
  - Pros: Single API key, many models selectable at runtime; Qwen3-max scores 100% on the 25-case hotel eval; OpenAI-compatible endpoint; `$0.78/$3.90` per 1M tokens is affordable for thesis volume; runtime model switching via `PATCH /settings/llm`
  - Cons: Adds an external dependency (openrouter.ai); Qwen3-max thinking mode can produce very long latencies for complex booking (p95: 13.9 s); not NVIDIA NIM — can't claim exact blueprint compliance

- **Option B — Ollama local (Qwen3.5-Opus-9B) only**
  - Pros: Zero marginal cost; fully offline; faster for most simple queries
  - Cons: 9B model scores 92% vs 100% for cloud model; 34-second outlier latency on some RAG queries; requires local GPU or slow CPU inference; not suitable for Railway deployment

- **Option C — Keep NVIDIA NIM, gate behind feature flag**
  - Pros: Preserves full blueprint fidelity
  - Cons: Blocks all daily development — no NIM hardware available; adds no thesis value

## Decision

Use OpenRouter as the primary LLM gateway for `hotel_guardrails`, defaulting to `qwen/qwen3-max`. Retain NVIDIA NIM wiring (`APP_LLM_MODELENGINE=nvidia-ai-endpoints`) as a configuration option for production equivalence. Add Ollama as a second local option for zero-cost offline development. All three paths are toggled via `APP_LLM_MODELENGINE` and `APP_LLM_MODELNAME`.

## Consequences

- Positive: Development runs immediately on any machine with an OpenRouter API key. Railway deployment works without GPU hardware. Runtime model switching enables live A/B comparisons (Qwen3-max vs Qwen3.5-Opus-9B vs MiniMax-M2.7). Evaluation data shows Qwen3-max reaches 100% on the hotel test suite.
- Negative / trade-offs: The production NVIDIA NIM path is untested in the thesis environment — functional equivalence is assumed but not empirically validated end-to-end. OpenRouter adds a network hop and a third-party availability dependency. `openrouter_llm.py` still contains `siam-serenity-hotel.com` as the HTTP referer header — a minor brand inconsistency from an earlier name of the hotel.
- Revisit if: NVIDIA NIM access becomes available for a real production trial; or OpenRouter pricing changes make it uneconomical at scale.

## Related

- [[OpenRouter]] — the gateway entity
- [[Qwen3-max]] — default cloud model
- [[Qwen3.5-Opus-9B]] — local Ollama alternative
- [[hotel_guardrails]] — the service this decision affects
- [[model-eval-local-vs-cloud-2026-04-06]] — empirical validation of Qwen3-max vs 9B local
- [[fork_nvidia_blueprint]] — parent decision that created the gap this fills
- [[NVIDIA]] — original NIM backend
