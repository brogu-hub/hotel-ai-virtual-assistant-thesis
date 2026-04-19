---
type: meta
title: "Operations Log"
updated: 2026-04-19
---

# Operations Log

Append-only. **New entries at the TOP.** Every ingest, scaffold, lint, autoresearch, or significant save gets a line.

Format: `- YYYY-MM-DD HH:MM — [op] short description [[page1]] [[page2]]`

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
