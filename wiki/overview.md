---
type: meta
title: "Overview"
updated: 2026-04-19
---

# Wiki Overview

Executive summary of what this wiki covers. High-altitude. Link to the first layer of detail; don't restate it.

## Scope

Three intertwined workstreams:

1. **Codebase map** — the Hotel AI Virtual Assistant microservices: `hotel_guardrails`, `agent`, `retrievers/*`, `analytics`, `api_gateway`, `ingest_service`, `common`.
2. **Thesis research & chapters** — the academic write-up: literature review, methodology, system design, evaluation, discussion.
3. **Experiment logs & documentation** — DeepEval runs, 4-subagent routing tests, LLM backend comparisons, Python environment rebuilds, deployment notes.

## Project context

Hotel AI Virtual Assistant for **The Grand Horizon Hotel**. Forked from the NVIDIA AI Blueprint, adapted to use OpenRouter (Qwen3-max) as an alternative to NVIDIA NIM. Hybrid architecture combining LangGraph (state machine + sub-agent routing) with NeMo Guardrails (safety + intent filtering). Deployed on Railway.app.

## Navigation

- Start with [[hot]] for what's current.
- Use [[index]] for the full catalog.
- Each section has its own `_index.md`:
  - [[modules/_index]], [[components/_index]], [[flows/_index]], [[decisions/_index]]
  - [[papers/_index]], [[concepts/_index]], [[entities/_index]]
  - [[thesis/_index]], [[experiments/_index]], [[gaps/_index]]

## What gets filed here vs. elsewhere

- **Files here**: synthesized knowledge — summaries, cross-references, decisions, comparisons, open questions.
- **Lives in `.raw/`**: source documents (papers, transcripts, raw data dumps, exports).
- **Lives in `src/` and `data/`**: production code and runtime data (not the wiki's job).
- **Lives in `docs/`**: end-user and developer-facing documentation (reference, link from wiki but don't duplicate).
- **Lives in claude-mem**: ephemeral session-level context (auto-captured, different from wiki's curated synthesis).
