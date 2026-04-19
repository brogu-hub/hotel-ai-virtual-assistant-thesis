---
type: component
parent_module: agent
path: src/agent/main.py
status: legacy
tags: [component, agent, order-status, langgraph-node, tool-loop]
created: 2026-04-19
updated: 2026-04-19
---

# agent_order_status

The `order_status` sub-agent in the [[agent]] StateGraph. Handles all queries about a user's purchase history: order IDs, delivery status, quantities, and order amounts.

## Purpose

Retrieves structured order data from PostgreSQL (via the structured retriever microservice) and answers purchase-history questions in context.

## Tool set

| Tool | Category | Purpose |
| --- | --- | --- |
| `structured_rag` | safe | Query structured retriever for order data |
| `ProductValidation` | routing | Trigger product disambiguation if product is unclear |

## Execution flow

1. `primary_assistant` calls `ToOrderStatusAssistant` → `enter_order_status` (entry node injects context message).
2. `order_validation` node runs `validate_product_info` to resolve `current_product`.
3. If `needs_clarification` → `ask_clarification` → `END`.
4. Otherwise → `order_status` `Assistant` loop.
5. `route_order_status` conditional edge:
   - Tool call to `structured_rag` → `order_status_safe_tools` → back to `order_status`.
   - Tool call to `ProductValidation` → `order_validation`.
   - No tool call → `END`.

## Streaming

When the last message is a `ToolMessage` from `structured_rag`, the node streams the LLM response via `should_stream` tag.

## Prompt

Uses `order_status_template` from `prompt.yaml`. Receives `{user_id}`, `{current_product}`, and `{user_purchase_history}` in state.

## Graph position

```
enter_order_status → order_status <--[safe_tools loop]
order_status --[route_order_status]--> order_status_safe_tools
                                    → order_validation
                                    → END
```

## Comparison to hotel_guardrails

The [[booking_subagent]] in [[hotel_guardrails]] plays the analogous "structured data retrieval" role, but operates on hotel reservation records (PostgreSQL `reservations` table) rather than retail order history. The tool loop pattern is the same.

## Related

- [[agent_validate_product_info]]
- [[agent_tools]]
- [[agent_return_processing]]
- [[booking_subagent]]
