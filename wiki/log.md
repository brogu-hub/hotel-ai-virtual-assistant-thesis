---
type: meta
title: "Operations Log"
updated: 2026-04-20
---

# Operations Log

Append-only. **New entries at the TOP.** Every ingest, scaffold, lint, autoresearch, or significant save gets a line.

Format: `- YYYY-MM-DD HH:MM — [op] short description [[page1]] [[page2]]`

---

## 2026-04-20

### 2026-04-20 18:10 — [test+fix] Extended Chinese-leak edge cases + trilingual admin-override

After the basic 13-scenario suite passed, ran a 5-scenario edge-case sweep covering: (N) per-sub-agent CN coverage, (O) romanised Chinese names without CJK input, (P) 10-turn sustained Chinese, (Q) chain-of-thought adversarial prompts, (R) CN cross-session memory recall.

- Findings: N/O/R clean (4/3/3). P initially 6/10 leaked because the auto-escalation hardcoded admin-override message was bilingual TH+EN only — when escalated, Chinese guests received Thai. Q showed 3/4 timeouts on "step by step" prompts (separate runaway-CoT issue, not a language leak).
- **Trilingual admin-override fix**: added `_admin_override_message(lang)` + `_ADMIN_OVERRIDE_MESSAGES` dict in `server.py`. Both `/chat` and `/chat/stream` admin-override branches now select EN/TH/CN by `detect_input_language(request.message)`. Chinese variant: `酒店工作人员正在为您服务，请稍候。`
- **Re-run P after fix**: 0/10 leaked. Combined post-fix tally: **0/70 turns leaked across 18 scenarios**.
- Side-issue filed: explicit chain-of-thought prompts can blow the 120s request timeout on the local 9B. Needs a max_tokens cap or upstream timeout bump — separate gap, not a language-leak issue.
- Wiki: [[experiments/chinese-leak-test-2026-04-20]] extended with Run 3 + Side-issue sections.

### 2026-04-20 17:30 — [feat+fix] Three-language policy (EN/TH/CN) + Chinese-leak guards

User raised concern about Chinese ideographs leaking into Thai/English replies on hard questions. Tested, confirmed, fixed, validated.

- **Empirical validation** — built [scripts/test_chinese_leak.py](../scripts/test_chinese_leak.py): 13 multi-turn scenarios, 46 turns total against live local Qwen3.5-Opus-9B. Run 1 (pre-fix): 3/38 leaked (7.9%) — including a 3-CJK-chars leak in a 760-char Thai response (`การตรวจสอบราคาและ可用性`). Run 2 (post-fix): **0/46 leaked**, including 5 turns of pure Chinese conversation and a CN→TH→EN three-language switch.
- **Fix in code** — added `detect_input_language` / `has_language_leak` / `strip_language_leak` in `src/hotel_guardrails/hotel_langgraph.py`, mirroring the existing `has_tool_leak` / `strip_tool_call_codeblocks` pattern. Wired into the retry loop in `invoke_hotel_agent` so language drift triggers a retry just like tool-call drift.
- **Policy** — `src/agent/hotel_prompt.yaml` `main_prompt` declares trilingual EN/TH/CN with a Chinese tone block (use 您, default Simplified). `server.py:~1107` LangChain fallback prompt mirrors it. `models.py` `ChatRequest.language` regex bumped to accept `cn`. Greeting + farewell templates added in Chinese.
- **User-provided CJK whitelist** — characters in the user's own input are exempt from leak detection so name echoes (王小明) survive without false-positive stripping.
- **Bonus fix surfaced by the test** — `server.py:1035` `request_id=request_id` (NameError, undefined) → `request_id=current_request_id`. Triggered when a previous response auto-escalated the session and the next turn hit the admin-override branch.
- **Wiki** — [[concepts/language_leak_and_three_language_policy]] (architecture + thesis framing), [[experiments/chinese-leak-test-2026-04-20]] (validation evidence), [[index]] entries.

### 2026-04-20 06:50 — [fix] Hotel naming drift unified → "The Grand Horizon Hotel"

User designated "The Grand Horizon Hotel" (EN) / "โรงแรม เดอะ แกรนด์ ฮอไรซัน" (TH) as the canonical name. Previously the codebase carried three conflicting names across source, data, scripts, and OpenAPI specs. All resolved.

- **Source code**: `src/hotel_guardrails/server.py:1114` Thai greeting (สยามเซอเรนิตี้ → เดอะแกรนด์ฮอไรซัน); `openrouter_llm.py:68` referer default; `__init__.py:29` docstring.
- **Scripts**: `scripts/eval/config.py:67`, `scripts/eval/metrics.py:46` (referer URLs → `grand-horizon-hotel.com`); `scripts/generate_hotel_knowledge.py:61-62` (EN+TH address).
- **Knowledge base**: `data/hotel/room_types.md:6`, `data/hotel/hotel_faq.md:35` (Thai "พาราไดส์" → "ฮอไรซัน").
- **OpenAPI spec**: `docs/api_references/hotel_guardrails_server.yaml:3` and `.json` title ("Siam Serenity Hotel Concierge API" → "The Grand Horizon Hotel Concierge API").
- **Wiki cleanup**: removed drift callouts / notes from [[references/hotel_knowledge_base]], [[references/hotel_guardrails_api]], [[components/server]], [[components/openrouter_llm_wrapper]], [[modules/hotel_guardrails]], [[decisions/openrouter_dev_backend]].
- No code behaviour changed — all edits were string replacements. No new dependencies, no schema changes. Memory tests and other functional suites remain unaffected.

### 2026-04-20 06:35 — [gap-fill] Remaining code-walk pages filled on main thread

Filled all 9 pending pages flagged after the rate-limited agent batch.

- **References folder created**: [[references/hotel_knowledge_base]] (10-file KB catalog, flags "Siam Serenity" vs "Grand Horizon" vs "Grand Paradise" naming drift), [[references/hotel_guardrails_api]] (20 endpoints across 6 tag groups from OpenAPI 3.1).
- **Component gap-fill**: [[components/chat_scaling]] (6 classes — LLMConcurrencyLimiter, SessionLockManager, ChatRateLimiter, StreamConnectionLimiter, KnowledgeCache, LLMQueueTimeout), [[components/config]] (4 Settings classes + RuntimeLLMConfig + model presets), [[components/packaging]] (Dockerfile, railway.toml, Procfile, requirements.txt — notes the langgraph-checkpoint-postgres ≥2.0.13 bump).
- **Memory subcomponents**: [[components/guest_memory_store]] (init/close/load/upsert lifecycle), [[components/memory_preamble_injector]] (5 injection points), [[components/tool_call_post_processor]] (3-pass regex strategy), [[components/anon_memory_sweeper]] (scheduled task + DELETE query).
- **Contradictions flagged**: hotel naming drift across CLAUDE.md ("Grand Horizon"), OpenAPI spec ("Siam Serenity"), and `room_types.md` ("Grand Paradise"). Logged in [[references/hotel_knowledge_base]].
- All pending wikilinks from [[thesis/hotel_ai_chatbot_chapter]] now resolve.

### 2026-04-20 06:15 — [synthesis] Thesis support chapter assembled on main thread

After the four parallel ingest agents rate-limited mid-run, the main thread filled the remaining gaps and wrote the chapter synthesis.

- **Source**: latest commit `2cd8362` (+952 lines, dual-plane memory) plus full `src/hotel_guardrails/` code-walk.
- **Primary deliverable**: [[thesis/hotel_ai_chatbot_chapter]] — §4 System Design & Implementation, ~5,400 words, Mermaid architecture + sequence diagrams, cross-refs to every component/concept/flow/experiment/decision page.
- **Memory system pages created** (main thread): [[tool_call_codeblock_leak]], [[anon_namespace_ttl]] (concepts) · [[cross_session_memory]] (flow) · [[memory-test-suite-2026-04-20]] (experiment).
- **Updated**: [[components/hotel_langgraph]] with a full "Memory: Dual-Plane Architecture" section documenting `init_store`/`close_store`, `load_guest_memory`, `_render_memory_preamble`, `_extract_prefs_from_text`, `_extract_facts_from_tool_calls`, `strip_tool_call_codeblocks`, `prune_anon_memory`, and env controls.
- **Key insight**: memory system is the thesis novel contribution — deserves its own Chapter 2 §2.3.4 (drafted in [[thesis/memory_system_design]]) and §4.6 (in the chapter). 27/27 memory cases pass on local Qwen3.5-Opus-9B.

### 2026-04-20 02:08 — [ingest] Hotel AI code-walk — 4 parallel agents (A: memory, B: server/API, C: cross-cutting, D: data/tools)

Agents dispatched in parallel, all rate-limited mid-run (reset 4am Asia/Bangkok). Still landed 12 substantive pages before stopping:

- **Agent A (memory system)**: [[thesis/memory_system_design]], [[dual_plane_memory]], [[rule_based_memory_write_back]], [[bilingual_memory_extraction]]. Did NOT finish: tool_call_codeblock_leak, anon_namespace_ttl, cross_session_memory flow, memory-test-suite experiment, hotel_langgraph update — completed on main thread (next entry).
- **Agent B (server & API)**: [[components/server]], [[components/pydantic_models]]. Did NOT finish: references/hotel_guardrails_api.
- **Agent C (cross-cutting)**: [[components/auth]], [[components/audit]], [[components/pii_redactor]], [[components/escalation]]. Did NOT finish: chat_scaling, config components.
- **Agent D (data/tools/packaging)**: [[components/actions]], [[components/database]]. Did NOT finish: references/hotel_knowledge_base, components/packaging.
- **Back-filled decisions** (some agents created these): [[fork_nvidia_blueprint]], [[hybrid_langgraph_nemo]], [[four_subagent_split]], [[openrouter_dev_backend]], [[qdrant_dev_milvus_prod]], [[railway_deployment]], [[python_312_runtime]].

---

## 2026-04-19

### 2026-04-19 22:30 — [merge] Tier 1 bootstrap merge pass

Consolidated parallel-ingest outputs into master indexes. Updated [[index]], [[hot]], [[overview]], [[decisions/_index]], and topped up `.raw/.manifest.json` with 3 missing source entries.

### 2026-04-19 22:25 — [ingest] `src/hotel_guardrails/` (module tree walk)

- Source: `src/hotel_guardrails/` directory
- Module page: [[hotel_guardrails]]
- Component pages created: [[hybrid_router]], [[langgraph_adapter]], [[hotel_langgraph]], [[primary_assistant]], [[booking_subagent]], [[service_subagent]], [[knowledge_subagent]], [[other_talk_subagent]], [[openrouter_llm_wrapper]], [[feedback_collector]]
- Agent paused before writing concept pages unique to this ingest; `[[Hybrid Routing]]` and `[[LangGraph State Machine]]` (from other agents) cover most of the conceptual ground.
- Key insight: hybrid architecture keeps NeMo rails as a thin pre-filter while LangGraph owns real routing — the two systems don't overlap.

### 2026-04-19 22:20 — [ingest] `docs/WORKFLOW.md`

- Source: `docs/WORKFLOW.md`
- Pages created: [[guest_chat]], [[reservation_lifecycle]], [[auth_and_access_control]], [[admin_monitoring]], [[chat_scaling]], [[local_run]], [[Ollama]], [[reranker_disabled]], [[dual_identity_model]]
- Key insight: WORKFLOW.md uses port 8088 (Docker stack) while CLAUDE.md lists 8081 (bare-metal uvicorn). Not a contradiction — different deploy modes.

### 2026-04-19 22:15 — [ingest] `docs/MODEL_EVAL_REPORT.md` + `docs/TEST_RESULTS.md`

- Sources: `docs/MODEL_EVAL_REPORT.md`, `docs/TEST_RESULTS.md`
- Pages created: [[model-eval-local-vs-cloud-2026-04-06]], [[model-tuning-and-test-results-2026-04-03]], [[Qwen3.5-Opus-9B]], [[MiniMax-M2.7]], [[keyword-match-eval]], [[eval-gaps-from-apr-experiments]]
- Pages updated: [[Qwen3-max]] (eval results), experiments/entities/concepts/gaps indexes
- Key insight: Cloud (Qwen3-max) 100% vs Local (Qwen3.5-Opus-9B) 92% on 25-case hotel benchmark; Cohen's κ = 0.000 → models fail on disjoint cases, ensemble candidate.

### 2026-04-19 22:10 — [ingest] `LLM_CHATBOT_CRITIRION.md`

- Source: `LLM_CHATBOT_CRITIRION.md`
- Pages created: [[bcg_2026_traveler_ai]], [[eu_ai_act_2026]], [[mdpi_tourism_ai_research]], [[str_revfine_upselling]], [[agentic_upselling]], [[autogen_conversation_driven_orchestration]], [[crewai_role_based_orchestration]], [[human_in_the_loop]], [[hybrid_rag_with_reranking]], [[langgraph_state_machine_architecture]], [[model_context_protocol]], [[persistent_memory_chatbot]], [[pii_redaction_and_compliance]], [[AutoGen]], [[CrewAI]], [[Mem0]], [[Microsoft Presidio]], [[Amadeus API]], [[evaluation_methodology]], [[mcp_integration_missing]]
- Agent paused mid-concept-pass; concept set may be incomplete.
- Key insight: criteria doc is partly literature review, partly eval checklist — split accordingly across papers/, concepts/, and thesis/evaluation_methodology.

### 2026-04-19 22:05 — [ingest] `CLAUDE.md` + `README.md`

- Sources: `CLAUDE.md`, `README.md`
- Module stubs created: [[hotel_guardrails]], [[agent]], [[retrievers]], [[analytics]], [[api_gateway]], [[ingest_service]], [[common]], [[frontend]]
- Entity pages: [[NVIDIA]], [[OpenRouter]], [[The Grand Horizon Hotel]], [[Railway]], [[FastAPI]], [[LangGraph]], [[NeMo Guardrails]], [[Milvus]], [[Qdrant]], [[PostgreSQL]], [[Redis]], [[Llama 3.3 70B]], [[Vanna.AI]]
- Concept pages: [[RAG]], [[Hybrid Routing]], [[LangGraph State Machine]]
- Agent paused before writing gap pages it had identified.
- Key insight: fork-from-blueprint approach lets the hotel assistant stay in the same conceptual shape as NVIDIA's reference stack while swapping backends.

### 2026-04-19 21:57 — [scaffold] Initialized hybrid Mode B + E vault

Created folder structure, `_templates/`, visual CSS, and `wiki/CLAUDE.md`. Owner: Mangakorian. Purpose: codebase map + thesis + experiment logs + documentation.
