---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, langgraph, subagent, knowledge, rag]
created: 2026-04-19
updated: 2026-04-19
---

# hotel_knowledge Sub-agent

## Purpose

Answers informational questions about the hotel using Retrieval-Augmented Generation (RAG). Covers facilities, dining hours, policies, WiFi, pool, spa, meeting rooms, directions — anything that can be answered from the hotel knowledge base documents. Does not loop with a tool node; it calls the RAG search inline and generates a final response directly.

## Graph Position

```
enter_knowledge → hotel_knowledge → END
```

No tool loop. The sub-agent is responsible for its own RAG call and returns a complete response.

## Handler Function: `handle_knowledge()`

**Location:** `hotel_langgraph.py`

**Algorithm:**

1. Extract the last `HumanMessage` from state.
2. Call `search_hotel_knowledge.invoke(last_user_message)` directly (synchronous call; results trimmed to 2000 chars to prevent context overflow).
3. Build a three-part prompt: system prompt → human message → knowledge context block.
4. Invoke LLM without tools (no tool loop possible — knowledge sub-agent has no bound tools).
5. Set `current_intent = "knowledge"`.

**Temperature:** 0.3
**Max tokens:** 1024

## RAG Details

- `search_hotel_knowledge` is imported from `src/agent/hotel_tools.py`
- Source documents: `data/hotel/*.md` (dining, facilities, room types, policies, etc.)
- Vector store: Qdrant (dev) / Milvus (prod)
- Reranker applied before results are returned (NVIDIA NV-RerankQA or local Qwen reranker)
- If RAG fails, falls back to `"No information found."` (error is logged, not surfaced to guest)

## Language Handling

The prompt instructs the LLM to "answer in the same language the guest used" — supports Thai and English. The knowledge base documents are in English; the LLM translates the content into Thai when responding to Thai-language queries.

## Key Difference from Service Sub-agent

- `hotel_knowledge` → informational ("What time is the pool open?", "Do you have a gym?")
- `hotel_service` → transactional ("I need extra towels", "Book me a spa slot")

## Related

- [[components/primary_assistant]] — routes here via `ToHotelKnowledge`
- [[components/hotel_langgraph]] — parent graph
- [[concepts/sub_agent_routing]]
