---
type: meta
title: "Wiki Index"
updated: 2026-04-19
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
- [[hotel_langgraph]] — 4-sub-agent state machine
- [[primary_assistant]] — router node
- [[booking_subagent]], [[service_subagent]], [[knowledge_subagent]], [[other_talk_subagent]]
- [[openrouter_llm_wrapper]]
- [[feedback_collector]]

### Flows — [[flows/_index]]
- [[guest_chat]] — `POST /chat` end-to-end
- [[reservation_lifecycle]] — booking state machine
- [[auth_and_access_control]] — JWT, dual-identity
- [[admin_monitoring]] — takeover, checkpoint replay, audit
- [[chat_scaling]] — concurrency, rate limits, caching
- [[local_run]] — Docker Compose, uvicorn, Jupyter ingest

### Decisions — [[decisions/_index]]
- [[reranker_disabled]]
- [[dual_identity_model]]

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

### Entities — [[entities/_index]]
**Orgs & platforms:** [[NVIDIA]], [[OpenRouter]], [[Railway]], [[The Grand Horizon Hotel]]
**Models:** [[Qwen3-max]], [[Qwen3.5-Opus-9B]], [[MiniMax-M2.7]], [[Llama 3.3 70B]]
**Frameworks:** [[LangGraph]], [[NeMo Guardrails]], [[FastAPI]], [[AutoGen]], [[CrewAI]]
**Data / infra:** [[Milvus]], [[Qdrant]], [[PostgreSQL]], [[Redis]], [[Ollama]], [[Vanna.AI]]
**Compliance / integrations:** [[Microsoft Presidio]], [[Mem0]], [[Amadeus API]]

---

## Thesis — [[thesis/_index]]

- [[evaluation_methodology]]

---

## Experiments — [[experiments/_index]]

- [[model-eval-local-vs-cloud-2026-04-06]]
- [[model-tuning-and-test-results-2026-04-03]]

---

## Open threads — [[gaps/_index]]

- [[eval-gaps-from-apr-experiments]]
- [[mcp_integration_missing]]

---

## Meta

- [[CLAUDE]] — vault conventions
- `_templates/` — note scaffolds (not linked, used by ingest ops)
