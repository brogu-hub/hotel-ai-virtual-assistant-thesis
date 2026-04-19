---
type: concept
status: developing
related: [LangGraph, hotel_guardrails, agent]
tags: [concept, langgraph, state-machine, orchestration]
created: 2026-04-19
updated: 2026-04-19
---

# LangGraph State Machine

## Definition

A LangGraph StateGraph is a directed graph where nodes are Python functions (agent steps or tool calls) and edges are conditional routing rules based on the current state. State is a typed dict passed through each node, accumulating conversation history and tool results.

## Origin

LangGraph was developed by LangChain Inc. as an extension of LangChain for complex, cyclical agent workflows.

## How it shows up in this project

### hotel_guardrails (`hotel_langgraph.py`)

```
primary_assistant
  → hotel_booking   (booking_tools: check availability, create/cancel reservation)
  → hotel_service   (service_tools: amenities, facilities)
  → hotel_knowledge (RAG search against hotel knowledge base)
  → other_talk      (general conversation)
```

State: typed dict with messages (conversation history), session metadata, tool results.

Adapter: `langgraph_adapter.py` bridges the FastAPI server to the graph's `invoke()` / `astream()`.

### agent (`main.py`)

```
validate_product_info
  → router
    → ProductQA
    → OrderStatus
    → ReturnProcessing
```

## Key concepts

- **Nodes**: async functions receiving and returning state
- **Edges**: `add_conditional_edges()` — function returns a string key selecting the next node
- **Tools**: `ToolNode` wraps function calls; results flow back into state
- **Checkpointing**: state can be persisted across invocations (multi-turn memory)

## Open questions

- Does the `hotel_langgraph` use a persistent checkpointer (PostgreSQL saver)?

## Related

- [[LangGraph]]
- [[hotel_guardrails]]
- [[agent]]
- [[Hybrid Routing]]
- [[ADR 4 Sub-agent Split]]
