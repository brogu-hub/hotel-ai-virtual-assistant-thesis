---
type: component
parent_module: agent
path: src/agent/main.py
status: legacy
tags: [component, agent, rag, product-qa, langgraph-node]
created: 2026-04-19
updated: 2026-04-19
---

# agent_product_qa

The `enter_product_qa` / `handle_product_qa` node in the [[agent]] StateGraph. Answers generic product questions using unstructured RAG over the NVIDIA Gear Store knowledge base.

## Purpose

Handles product specification questions, usage instructions, warranty queries, store policy, and general catalogue questions. It does not use tools after the initial RAG call — it generates a final answer and exits to `END`.

## Inputs (from State)

- `state["messages"]` — full conversation; last user message used as RAG query
- `state["user_purchase_history"]` — available in state but not used directly by this node

## Execution flow

1. Extract previous conversation, filtering out `ToolMessage` entries.
2. Serialize to `[{role, content}]` list.
3. Call `canonical_rag(query=last_message, conv_history=...)` from `utils.py` — calls the unstructured retriever microservice.
4. Format a `rag_template` prompt with retrieved context injected.
5. Invoke the LLM (streaming via `should_stream` tag).
6. Return `{"messages": [response]}` and proceed to `END`.

## Prompt

Uses `rag_template` from `prompt.yaml`. Template expects `{chat_history}` and `{context}` placeholders.

## Graph position

```
primary_assistant --[ToProductQAAssistant]--> enter_product_qa --> END
```

No tool loop — unlike `order_status` and `return_processing`, ProductQA does not call additional tools after the RAG response.

## Comparison to hotel_guardrails

Functionally mirrors [[knowledge_subagent]] in [[hotel_guardrails]], which also does RAG-and-respond without a tool loop. Key difference: `agent_product_qa` calls the unstructured retriever microservice (`canonical_rag`), while `knowledge_subagent` calls the `hotel_knowledge` retriever chain directly.

## Related

- [[agent_router]]
- [[agent_tools]]
- [[knowledge_subagent]]
