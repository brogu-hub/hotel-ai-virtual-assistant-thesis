---
type: meta
title: "Experiments Index"
updated: 2026-04-19
---

# Experiments

One page per experiment, benchmark, or eval run. Use [[_templates/experiment]]. Link outcomes back into thesis chapters.

## Recent experiments (from session memory)

- 2026-04-19 — **Comprehensive 4-subagent routing test suite** (`scripts/test_4_subagents.py`) — verifies booking / service / knowledge / other_talk routing under extensive conversation cases. _(stub on ingest)_
- 2026-04-19 — **Python 3.12 environment rebuild** — full rebuild, upgraded `docker/dev/Dockerfile.dev` base image. _(stub on ingest)_
- Ongoing — **CI/CD pipeline integration for LLM-based API tests** — wiring existing test cases into the pipeline. _(stub on ingest)_

## Standing eval harnesses

- `scripts/eval/run_evaluation.py` — custom evaluation harness
- `scripts/eval/run_deepeval.py` — DeepEval framework runs
- `scripts/test_chat.py` — smoke test for the chat endpoint

## Filed pages

- [[model-eval-local-vs-cloud-2026-04-06]] — Local (Qwen3.5 Opus 9B / Ollama) vs Cloud (Qwen3-max / OpenRouter) on 25-case hotel benchmark. Cloud: 100%, Local: 92%. Cohen's κ = 0.000. 193/193 infra tests pass.
- [[model-tuning-and-test-results-2026-04-03]] — 34-case functional suite (Parts A–F), 94% pass (32/34) after 7 targeted fixes. Three-model comparison: Qwen3.5-Opus-9B vs Qwen3-max vs MiniMax M2.7.
