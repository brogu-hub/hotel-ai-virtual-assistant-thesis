---
type: meta
title: "Components Index"
updated: 2026-04-19
---

# Components & Sub-agents

Reusable units finer-grained than a module: sub-agents, tool functions, adapters, router nodes, UI components. Use the [[_templates/module]] template (type: `component`).

## Expected pages

### hotel_guardrails sub-agents
- `hotel_booking` sub-agent
- `hotel_service` sub-agent
- `hotel_knowledge` sub-agent
- `other_talk` sub-agent
- `primary_assistant` router node
- `HybridRouter` (safety layer)
- `LangGraphAdapter`

### Shared
- `OpenRouterLLM` wrapper
- `FallbackLLM` chain
- `ConfigWizard` base class

## agent sub-agents & nodes

- [[agent_router]] — `primary_assistant` node; LLM-based routing via tool-calling
- [[agent_validate_product_info]] — pre-routing product resolver (order/return paths)
- [[agent_product_qa]] — ProductQA: unstructured RAG + LLM, no tool loop
- [[agent_order_status]] — OrderStatus: structured RAG tool loop over purchase history
- [[agent_return_processing]] — ReturnProcessing: return eligibility + human-in-the-loop interrupt
- [[agent_tools]] — `@tool` functions (structured_rag, get_purchase_history, return tools) + routing Pydantic classes
- [[agent_hotel_tools]] — hotel CRUD, dynamic pricing, upselling, payment link (fork addition)

## hotel_guardrails sub-agents

- [[hybrid_router]] — safety pre-filter
- [[langgraph_adapter]] — server-to-graph bridge
- [[hotel_langgraph]] — 4-sub-agent state machine
- [[primary_assistant]] — router node
- [[booking_subagent]], [[service_subagent]], [[knowledge_subagent]], [[other_talk_subagent]]
- [[openrouter_llm_wrapper]]
- [[feedback_collector]]
