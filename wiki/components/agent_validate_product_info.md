---
type: component
parent_module: agent
path: src/agent/main.py
status: legacy
tags: [component, agent, validation, langgraph-node]
created: 2026-04-19
updated: 2026-04-19
---

# agent_validate_product_info

Pre-routing validator node in the [[agent]] StateGraph. Resolves which product the user is referring to before passing control to the [[agent_order_status]] or [[agent_return_processing]] sub-agents.

## Purpose

Sits between the `primary_assistant` router and the order/return sub-agents. Prevents those sub-agents from acting on an ambiguous product reference.

## Inputs (from State)

- `state["user_id"]` — used to fetch purchase history
- `state["messages"]` — conversation so far

## Outputs (State patches)

| Field | Value |
|---|---|
| `user_purchase_history` | latest rows from `get_purchase_history(user_id)` |
| `needs_clarification` | `True` if 0 or 2+ matching products |
| `clarification_type` | `"no_product"` or `"multiple_products"` |
| `reason` | product name(s) found in query, for follow-up prompt |
| `current_product` | resolved product name if exactly one match |

## Logic

1. Fetch purchase history for `user_id`.
2. Extract unique `product_name` values.
3. Call `get_product_name(messages, product_list)` (in `utils.py`) — LLM call that matches the user's query against owned products.
4. If 0 products found → `needs_clarification=True, clarification_type="no_product"`.
5. If 2+ products found → `needs_clarification=True, clarification_type="multiple_products"`.
6. If exactly 1 → `current_product` is set.

## Downstream edges

- `is_order_product_valid` / `is_return_product_valid` → `ask_clarification` or the sub-agent node

## Notes

- Two separate graph nodes (`order_validation`, `return_validation`) both call this same function — one guards the order path, the other the return path.
- No hotel-domain equivalent exists in [[hotel_guardrails]]; the hotel system resolves identity via guest email rather than product name.

## Related

- [[agent_router]]
- [[agent_order_status]]
- [[agent_return_processing]]
