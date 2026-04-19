---
type: entity
category: library
url: https://langchain-ai.github.io/langgraph/
tags: [entity, library, langgraph, langchain, orchestration]
created: 2026-04-19
updated: 2026-04-19
---

# LangGraph

## What it is

LangGraph is an open-source orchestration library by LangChain for building stateful, multi-actor LLM workflows as directed graphs (StateGraphs).

## Role in this project

LangGraph is the **core orchestration engine** for both agent systems:
- `src/hotel_guardrails/hotel_langgraph.py` — primary state machine with 4 sub-agents
- `src/agent/main.py` — original blueprint StateGraph (validate → router → ProductQA/OrderStatus/ReturnProcessing)

## Key facts

- State machine pattern: nodes = functions/agents, edges = conditional routing
- `hotel_langgraph.py` sub-agents: `hotel_booking`, `hotel_service`, `hotel_knowledge`, `other_talk`
- Original blueprint sub-agents: `ProductQA`, `OrderStatus`, `ReturnProcessing` (+ `validate_product_info` guard)
- Adapter: `src/hotel_guardrails/langgraph_adapter.py` bridges FastAPI ↔ LangGraph

## Related

- [[LangGraph State Machine]]
- [[langgraph_state_machine_architecture]] — concept page with checkpointers, time-travel, Break state details
- [[hotel_guardrails]]
- [[agent]]
- [[Hybrid Routing]]
- [[ADR 4 Sub-agent Split]]
- [[human_in_the_loop]]
- [[persistent_memory_chatbot]]
