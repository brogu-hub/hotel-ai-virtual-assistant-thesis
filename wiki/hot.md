---
type: meta
title: "Hot Cache"
updated: 2026-04-20T17:30:00
---

# Recent Context

## Last Updated

2026-04-20 17:30. Three-language policy (EN/TH/CN) shipped + Chinese-leak guards verified end-to-end (0/46 turns leaked after fix, was 7.9% before). Plus: code-walk landed, naming drift resolved, thesis chapter complete.

## Key Recent Facts

- **Latest commit `2cd8362` (Apr 20, 02:00)**: +952 lines implementing dual-plane memory — [[dual_plane_memory|PostgresSaver + PostgresStore]] with separate connection pools, rule-based bilingual write-back (zero extra LLM calls), tool-call leak post-processor for local-9B output, and a 30-day TTL sweeper for anonymous namespaces. All wired uniformly into primary router + 4 sub-agents.
- **Memory validation**: [[memory-test-suite-2026-04-20]] — 27/27 cases pass on local [[Qwen3.5-Opus-9B]] via [[Ollama]]. Covers short-term (5), long-term by store key (11), Thai free-text (6), accumulation (2), edge/negative (3 incl. isolation + no-hallucination + anon).
- **Thesis deliverables (complete)**: [[thesis/memory_system_design]] (Chapter 2 §2.3.4 drop-in text, references, Fig. 2.4 caption) and [[thesis/hotel_ai_chatbot_chapter]] (§4 System Design & Implementation, ~5,400 words, full Mermaid diagrams, every wikilink now resolves).
- **Project**: Hotel AI Virtual Assistant (canonically "The Grand Horizon Hotel" per CLAUDE.md; drift flagged — see below), forked from NVIDIA AI Blueprint. Hybrid [[LangGraph]] + [[NeMo Guardrails]]; OpenRouter/[[Qwen3-max]] for cloud (100% eval), [[Qwen3.5-Opus-9B]] via [[Ollama]] for local (92% eval, 27/27 memory).
- **Primary service**: [[hotel_guardrails]] — FastAPI on 8081 (bare-metal/docker) / 8088 (docker-compose) / Railway-assigned `${PORT}`. Four sub-agents routed through [[hybrid_router]] → [[langgraph_adapter]] → [[hotel_langgraph]].

## Recent Changes (2026-04-20)

- **Agent-authored (rate-limited batch, ~02:08)**: 12 large pages — [[thesis/memory_system_design]], 4 memory concepts (dual-plane, rule-based-write-back, bilingual-extraction + chapter text), 6 component pages (server, pydantic_models, auth, audit, pii_redactor, escalation), 2 data-layer components (actions, database), plus 7 back-filled ADRs.
- **Main-thread fill-in (06:15)**: [[tool_call_codeblock_leak]], [[anon_namespace_ttl]] (concepts) · [[cross_session_memory]] (flow) · [[memory-test-suite-2026-04-20]] (experiment) · memory section on [[components/hotel_langgraph]] · **[[thesis/hotel_ai_chatbot_chapter]]** (main deliverable, ~5400 words).
- **Main-thread gap-fill (06:35)**: [[references/hotel_guardrails_api]], [[references/hotel_knowledge_base]] (new references/ folder), [[components/chat_scaling]], [[components/config]], [[components/packaging]], and the 4 memory subcomponent pages ([[guest_memory_store]], [[memory_preamble_injector]], [[tool_call_post_processor]], [[anon_memory_sweeper]]).
- **Meta**: [[index]], [[log]], [[hot]], `.raw/.manifest.json` updated.

## Active Threads

- **Three-language policy (EN/TH/CN) — SHIPPED 2026-04-20 17:30, EXTENDED 18:10**: trilingual prompt + `has_language_leak` / `strip_language_leak` post-processor in `hotel_langgraph.py`, wired into `invoke_hotel_agent` retry loop alongside `has_tool_leak`. User-provided CJK whitelist preserves proper-name echoes. Validated by [[chinese-leak-test-2026-04-20]] across 3 runs: combined post-fix **0/70 turns leaked** across 18 scenarios. Architecture: [[language_leak_and_three_language_policy]].
- **Trilingual admin-override message (2026-04-20 18:10)**: `_admin_override_message()` selects EN/TH/CN by detected input language so a Chinese guest in an escalated session doesn't get a Thai response. `_ADMIN_OVERRIDE_MESSAGES` dict in `server.py`. Both `/chat` and `/chat/stream` updated.
- **`server.py:1035` NameError fix**: `request_id` → `current_request_id` in the admin-override branch (triggered when escalation_monitor flags a session). Discovered during the Chinese-leak test, fixed in the same patch.
- **Open gap**: chain-of-thought adversarial prompts ("step by step", "show your reasoning") can exhaust the 120s request timeout on the local 9B (3/4 Q-scenario turns timed out). Needs a max_tokens cap or upstream timeout bump. Not a language-leak issue.
- **Hotel naming drift — RESOLVED 2026-04-20 06:50**: canonical name is "The Grand Horizon Hotel" / "โรงแรม เดอะ แกรนด์ ฮอไรซัน". Fixed across 10 files (`server.py`, `openrouter_llm.py`, `__init__.py`, eval scripts, `generate_hotel_knowledge.py`, `data/hotel/*`, OpenAPI yaml+json). See [[log]] 2026-04-20 06:50 entry.
- **Port drift** (still true, now documented): 8081 / 8088 / `${PORT}` — all intentional. Captured in [[thesis/hotel_ai_chatbot_chapter]] §4.8 and [[components/packaging]].
- **Duplicate concept still unmerged**: [[LangGraph State Machine]] (title-case) vs [[langgraph_state_machine_architecture]] (snake-case). `/wiki-lint` should merge.
- **Decision back-fill complete**: 9 ADRs filed (fork_nvidia_blueprint, hybrid_langgraph_nemo, four_subagent_split, openrouter_dev_backend, qdrant_dev_milvus_prod, railway_deployment, python_312_runtime, dual_identity_model, reranker_disabled).
- **Next ingest candidates**: `src/agent/` (original NVIDIA tree), `src/retrievers/*`, `docs/AUTH_TEST_RESULTS.md`, `docs/FRONTEND_AUTH_INTEGRATION.md`, NeMo Guardrails paper, LangGraph paper, Qwen3 technical report. Cloud re-run of the 27-case memory suite on [[Qwen3-max]] would close the eval symmetry.
- **Thesis v8 docx**: still deferred per user instruction.
