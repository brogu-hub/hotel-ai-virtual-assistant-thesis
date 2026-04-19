---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, langgraph, subagent, service]
created: 2026-04-19
updated: 2026-04-19
---

# hotel_service Sub-agent

## Purpose

Handles in-stay service requests — amenity queries and service order creation. Covers room service, housekeeping, spa bookings, transportation, wake-up calls, and extra item requests. Can loop with its tool node if multiple service calls are needed.

## Graph Position

```
enter_service → hotel_service ⇄ service_tools → END
```

## Handler Function: `handle_service()`

**Location:** `hotel_langgraph.py`

Loads the `service_prompt` and `main_prompt` from `hotel_prompt.yaml`. Binds the two service tools to the LLM. Sets `current_intent = "service"`.

**Temperature:** 0.3
**Max tokens:** 1024

## Tools Available

Both imported from `src/agent/hotel_tools.py`:

| Tool | Purpose |
|---|---|
| `get_hotel_services` | Retrieve the list of available hotel services and their details |
| `create_service_request` | Submit a new service order (e.g., extra towels, room service order) |

## Edge Function: `route_service()`

After each `hotel_service` invocation, checks for additional tool calls. If yes → `"service_tools"`. If no → `END`.

## Scope Boundary

The primary assistant routes "what services do you have?" to `hotel_knowledge` (informational) rather than here. `hotel_service` is reached only when the guest is making a specific service request, not a general enquiry about what's available.

## Related

- [[components/primary_assistant]] — routes here via `ToHotelService`
- [[components/knowledge_subagent]] — handles general facility/amenity queries
- [[components/hotel_langgraph]] — parent graph
