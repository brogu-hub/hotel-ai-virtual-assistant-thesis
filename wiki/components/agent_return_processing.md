---
type: component
parent_module: agent
path: src/agent/main.py
status: legacy
tags: [component, agent, returns, human-in-the-loop, langgraph-node]
created: 2026-04-19
updated: 2026-04-19
---

# agent_return_processing

The `return_processing` sub-agent in the [[agent]] StateGraph. Manages product return requests: validates return eligibility and writes return status to the database, with a human-in-the-loop confirmation step before the write.

## Purpose

Determines whether an order is within the return window, confirms the action with the user, and calls `update_return` to set `return_status = 'Requested'` in PostgreSQL.

## Tool set

| Tool | Category | Purpose |
| --- | --- | --- |
| `get_recent_return_details` | safe | Fetch user's return history |
| `return_window_validation` | safe | Check if order date is within return window |
| `update_return` | **sensitive** | Write `return_status = 'Requested'` to DB |
| `ProductValidation` | routing | Trigger product disambiguation |

## Human-in-the-loop interrupt

The graph is compiled with `interrupt_before=["return_processing_sensitive_tools"]`. Before `update_return` executes, the server pauses and asks the user: *"Do you approve of the process the return? Type 'y' to continue; otherwise, explain your requested changes."*

If the user replies "yes/y/Y" → graph resumes and `update_return` fires. If the user objects → the server injects a `ToolMessage` denial into state so the LLM can adjust.

## Conditional routing

```
return_processing --[route_return_processing]--> return_processing_safe_tools
                                              → return_processing_sensitive_tools  (interrupt here)
                                              → return_validation
                                              → END
```

## Prompt

Uses `return_processing_template` from `prompt.yaml`. Receives `{user_id}`, `{current_product}`, `{user_purchase_history}`. The template instructs the agent to only call `update_return` when order status is "delivered" AND within the return window.

## Comparison to hotel_guardrails

[[hotel_guardrails]] has no direct equivalent to a sensitive-tool interrupt. The cancel-reservation flow in [[booking_subagent]] is destructive but does not pause for user confirmation. This is a notable design difference — `agent` demonstrates the [[human_in_the_loop]] pattern more explicitly.

## Related

- [[agent_validate_product_info]]
- [[agent_tools]]
- [[human_in_the_loop]]
- [[agent_order_status]]
