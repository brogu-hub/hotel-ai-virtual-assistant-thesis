---
type: meta
title: "Hot Cache"
updated: 2026-04-19T22:30:00
---

# Recent Context

## Last Updated
2026-04-19. Tier 1 bootstrap ingest complete — 5 sources processed in parallel, vault now holds 75+ pages across all typed folders.

## Key Recent Facts

- **Project**: Hotel AI Virtual Assistant (The Grand Horizon Hotel), forked from NVIDIA AI Blueprint. Hybrid LangGraph + NeMo Guardrails; OpenRouter/[[Qwen3-max]] for prod cloud, [[Qwen3.5-Opus-9B]] via [[Ollama]] for local dev.
- **Primary service**: [[hotel_guardrails]] — FastAPI server with 4 sub-agents ([[booking_subagent]], [[service_subagent]], [[knowledge_subagent]], [[other_talk_subagent]]), routed through [[hybrid_router]] → [[langgraph_adapter]] → [[hotel_langgraph]].
- **April 2026 eval results**: Cloud Qwen3-max 100% (25/25), Local Qwen3.5-Opus-9B 92% (23/25) on hotel benchmark. Cohen's κ = 0.000 — models fail on disjoint cases. Functional suite 94% after 7 targeted fixes. Infra tests 193/193. See [[model-eval-local-vs-cloud-2026-04-06]] and [[model-tuning-and-test-results-2026-04-03]].
- **Port drift noticed**: Docker Compose stack binds hotel_guardrails to 8088 ([[local_run]]); bare-metal uvicorn in project CLAUDE.md uses 8081. Both are valid; worth noting in thesis deployment section.
- **Architecture concepts surfacing from literature ingest**: [[agentic_upselling]], [[hybrid_rag_with_reranking]], [[human_in_the_loop]], [[persistent_memory_chatbot]], [[model_context_protocol]], plus orchestration alternatives [[autogen_conversation_driven_orchestration]] and [[crewai_role_based_orchestration]].

## Recent Changes

- Created: 75+ pages across modules, components, flows, concepts, entities, papers, experiments, decisions, gaps, thesis.
- Updated: [[index]], [[log]], [[hot]], [[overview]], [[decisions/_index]]; `.raw/.manifest.json` topped up with 3 missing source entries.
- Flagged dup: [[LangGraph State Machine]] (title-case) and [[langgraph_state_machine_architecture]] (snake-case) cover the same concept — `/wiki-lint` should merge.
- Incomplete ingests: agent #1 (CLAUDE.md+README.md) paused before gap pages; agent #2 (LLM_CHATBOT_CRITIRION) paused mid-concept-pass; agent #5 (hotel_guardrails) paused before hotel-specific concept pages. Components and modules for #5 are complete.

## Active Threads

- **Naming convention**: entities/concepts have mixed Title Case vs snake_case filenames. Pick one (Title Case recommended) and lint.
- **Decision back-fill**: `decisions/_index.md` lists 9 back-fill candidates; only 2 filed (reranker_disabled, dual_identity_model). Need ADRs for: NVIDIA blueprint fork, OpenRouter backend, hybrid architecture, Qdrant/Milvus split, Railway deploy, 4-subagent split, Python 3.12 rebuild, thesis methodology structure, eval framework choice.
- **Next ingest candidates**: thesis v8 docx (currently skipped per user), `src/agent/` module tree, `src/retrievers/*`, `docs/AUTH_TEST_RESULTS.md`, `docs/FRONTEND_AUTH_INTEGRATION.md`, `docs/api_references/*`, NeMo Guardrails paper, LangGraph paper, Qwen3 technical report.
- **Open question**: should concept pages on AutoGen/CrewAI (not used in this project) stay in `concepts/` or move to `research/alternatives/`?
