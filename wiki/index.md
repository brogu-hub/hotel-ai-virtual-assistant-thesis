---
type: meta
title: "Wiki Index"
updated: 2026-04-20
---

# Wiki Index

Master catalog. Update on every ingest, save, or autoresearch. Group by section; link to sub-indexes first, then individual pages.

## Quick entry points

- [[overview]] — executive summary
- [[hot]] — recent context (~500 words, always fresh)
- [[log]] — chronological operations log

---

## Codebase

### Modules — [[modules/_index]]
- [[hotel_guardrails]] — primary hotel assistant (FastAPI + LangGraph + NeMo Guardrails)
- [[agent]] — original NVIDIA blueprint agent (LangGraph + NIM)
- [[retrievers]] — RAG retriever microservices
- [[analytics]] — sentiment + summarization
- [[api_gateway]] — HTTP proxy
- [[ingest_service]] — vector store + CSV-to-SQL import
- [[common]] — LLM wrappers, embeddings, rerankers, config
- [[frontend]] — UI (port 3001)

### Components & sub-agents — [[components/_index]]
- [[hybrid_router]] — safety pre-filter
- [[langgraph_adapter]] — server-to-graph bridge
- [[hotel_langgraph]] — 4-sub-agent state machine (now memory-aware)
- [[primary_assistant]] — router node
- [[booking_subagent]], [[service_subagent]], [[knowledge_subagent]], [[other_talk_subagent]]
- [[server]] — FastAPI entry, lifespan, endpoints _(new 2026-04-20)_
- [[pydantic_models]] — request/response schemas _(new 2026-04-20)_
- [[actions]] — tool catalog _(new 2026-04-20)_
- [[database]] — PostgreSQL operations _(new 2026-04-20)_
- [[auth]], [[audit]], [[pii_redactor]], [[escalation]] — cross-cutting _(new 2026-04-20)_
- [[chat_scaling]], [[config]], [[packaging]] — scaling, settings, deploy _(gap-fill 2026-04-20)_
- [[guest_memory_store]], [[memory_preamble_injector]], [[tool_call_post_processor]], [[anon_memory_sweeper]] — memory subcomponents _(gap-fill 2026-04-20)_
- [[openrouter_llm_wrapper]]
- [[feedback_collector]]

### Flows — [[flows/_index]]
- [[guest_chat]] — `POST /chat` end-to-end
- [[cross_session_memory]] — dual-plane memory read/write _(new 2026-04-20)_
- [[reservation_lifecycle]] — booking state machine
- [[auth_and_access_control]] — JWT, dual-identity
- [[admin_monitoring]] — takeover, checkpoint replay, audit
- [[chat_scaling]] — concurrency, rate limits, caching
- [[local_run]] — Docker Compose, uvicorn, Jupyter ingest

### Decisions — [[decisions/_index]]
- [[reranker_disabled]]
- [[dual_identity_model]]
- [[fork_nvidia_blueprint]], [[hybrid_langgraph_nemo]], [[four_subagent_split]], [[openrouter_dev_backend]], [[qdrant_dev_milvus_prod]], [[railway_deployment]], [[python_312_runtime]] _(back-filled 2026-04-20)_

---

## Research

### Papers — [[papers/_index]]
- [[bcg_2026_traveler_ai]]
- [[eu_ai_act_2026]]
- [[mdpi_tourism_ai_research]]
- [[str_revfine_upselling]]

### Concepts — [[concepts/_index]]
- [[RAG]]
- [[Hybrid Routing]]
- [[LangGraph State Machine]] _(dup: see [[langgraph_state_machine_architecture]] — lint needed)_
- [[keyword-match-eval]]
- [[agentic_upselling]]
- [[hybrid_rag_with_reranking]]
- [[human_in_the_loop]]
- [[persistent_memory_chatbot]]
- [[pii_redaction_and_compliance]]
- [[model_context_protocol]]
- [[autogen_conversation_driven_orchestration]]
- [[crewai_role_based_orchestration]]
- **Memory system** _(new 2026-04-20)_: [[dual_plane_memory]] · [[rule_based_memory_write_back]] · [[bilingual_memory_extraction]] · [[tool_call_codeblock_leak]] · [[anon_namespace_ttl]]
- **Three-language policy** _(new 2026-04-20)_: [[language_leak_and_three_language_policy]] — EN/TH/CN, detector + retry + strip post-processor

### Entities — [[entities/_index]]
**Orgs & platforms:** [[NVIDIA]], [[OpenRouter]], [[Railway]], [[The Grand Horizon Hotel]]
**Models:** [[Qwen3-max]], [[Qwen3.5-Opus-9B]], [[MiniMax-M2.7]], [[Llama 3.3 70B]]
**Frameworks:** [[LangGraph]], [[NeMo Guardrails]], [[FastAPI]], [[AutoGen]], [[CrewAI]]
**Data / infra:** [[Milvus]], [[Qdrant]], [[PostgreSQL]], [[Redis]], [[Ollama]], [[Vanna.AI]]
**Compliance / integrations:** [[Microsoft Presidio]], [[Mem0]], [[Amadeus API]]

---

## Thesis — [[thesis/_index]]

- [[evaluation_methodology]]
- [[thesis/memory_system_design]] — dual-plane memory novel contribution _(new 2026-04-20)_
- [[thesis/hotel_ai_chatbot_chapter]] — §4 system design & implementation chapter _(new 2026-04-20)_

---

## Experiments — [[experiments/_index]]

- [[model-eval-local-vs-cloud-2026-04-06]]
- [[model-tuning-and-test-results-2026-04-03]]
- [[memory-test-suite-2026-04-20]] — 27/27 memory cases pass on local Qwen3.5-Opus-9B _(new 2026-04-20)_
- [[chinese-leak-test-2026-04-20]] — 13 scenarios / 46 turns: 7.9% leak rate before fix → 0% after; trilingual EN/TH/CN policy validated _(new 2026-04-20)_

---

## Open threads — [[gaps/_index]]

- [[eval-gaps-from-apr-experiments]]
- [[mcp_integration_missing]]

---

## References — `references/`

- [[references/hotel_guardrails_api]] — OpenAPI-derived API reference _(new 2026-04-20)_
- [[references/hotel_knowledge_base]] — catalog of `data/hotel/*.md` RAG corpus _(new 2026-04-20)_

---

## Meta

- [[CLAUDE]] — vault conventions
- `_templates/` — note scaffolds (not linked, used by ingest ops)
