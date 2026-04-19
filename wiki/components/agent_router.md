---
type: component
parent_module: agent
path: src/agent/main.py
status: legacy
tags: [component, agent, router, langgraph-node, primary-assistant]
created: 2026-04-19
updated: 2026-04-19
---

# agent_router

The `primary_assistant` node in the [[agent]] StateGraph. Acts as the top-level dispatcher — the first LLM node a user message reaches after purchase history is fetched.

## Purpose

Receives the user message and, using tool-calling on [[Llama 3.3 70B]] (via NVIDIA NIM), selects one of four routing targets. The LLM does not answer directly; it exclusively calls routing tools.

## Routing tools available

| Tool class | Destination node |
|---|---|
| `ToProductQAAssistant` | `enter_product_qa` |
| `ToOrderStatusAssistant` | `enter_order_status` → `order_validation` |
| `ToReturnProcessing` | `enter_return_processing` → `return_validation` |
| `HandleOtherTalk` | `other_talk` |

## Prompt context

Uses `primary_assistant_template` from `prompt.yaml`. The template instructs the LLM to never expose sub-agent names to the user and to delegate silently via function calls.

## Graph edges

```
fetch_purchase_history → primary_assistant
primary_assistant --[route_primary_assistant]--> enter_product_qa
                                              → enter_order_status
                                              → enter_return_processing
                                              → other_talk
                                              → END
```

## Comparison to hotel_guardrails

The [[primary_assistant]] component in [[hotel_guardrails]] is structurally identical — an LLM node that calls routing tools — but routes to four hotel sub-agents ([[booking_subagent]], [[service_subagent]], [[knowledge_subagent]], [[other_talk_subagent]]). The key difference: `agent_router` has a pre-flight `fetch_purchase_history` step; the hotel router has no equivalent pre-fetch.

## Notes

- The `Assistant` class (in `main.py`) wraps the LLM call. It loops until the model produces a non-empty, non-empty-list response; this loop is bounded by `GRAPH_RECURSION_LIMIT`.
- If `tool_calls` is empty and `result.content` is empty, the node appends `"Respond with a real output."` to state messages and retries.

## Related

- [[agent_validate_product_info]]
- [[agent_product_qa]]
- [[agent_order_status]]
- [[agent_return_processing]]
- [[agent_chat_pipeline]]
