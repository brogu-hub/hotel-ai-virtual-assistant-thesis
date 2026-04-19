---
type: component
path: "src/hotel_guardrails/hotel_langgraph.py"
status: active
parent_module: hotel_guardrails
tags: [component, langgraph, subagent, booking]
created: 2026-04-19
updated: 2026-04-19
---

# hotel_booking Sub-agent

## Purpose

Handles all reservation lifecycle operations — checking availability, creating/confirming/updating/cancelling bookings, guest check-in and check-out, and payment link generation. Can loop with its tool node to complete multi-step operations within a single turn.

## Graph Position

```
enter_booking → hotel_booking ⇄ booking_tools → END
```

The `hotel_booking` node and `booking_tools` tool node form a loop: the sub-agent calls tools, gets results back, and may call more tools before ending.

## Handler Function: `handle_booking()`

**Location:** `hotel_langgraph.py`

Loads the `booking_flow` and `main_prompt` from `hotel_prompt.yaml`, binds all booking tools to the LLM, and invokes. Sets `current_intent = "booking"` in the returned state.

**Temperature:** 0.3 (configurable via `llm_settings`)
**Max tokens:** 2048 (higher than other sub-agents due to complex multi-step responses)

## Tools Available

All imported from `src/agent/hotel_tools.py`:

| Tool | Purpose |
|---|---|
| `check_room_availability` | Query available rooms for date range and type |
| `calculate_dynamic_price` | Compute price with seasonal/demand adjustments |
| `create_reservation` | Create a new booking record |
| `confirm_reservation` | Confirm a pending reservation |
| `update_reservation` | Modify dates, room type, or guest count |
| `cancel_reservation` | Cancel an existing booking |
| `check_in_guest` | Mark guest as checked in |
| `check_out_guest` | Mark guest as checked out |
| `get_reservation_details` | Retrieve single booking by ID |
| `get_guest_reservations` | List all reservations for a guest |
| `check_upsell_opportunity` | Suggest upgrades or add-ons |
| `generate_payment_link` | Create a payment URL for a booking |

## Edge Function: `route_booking()`

After each `hotel_booking` invocation, checks if the LLM made further tool calls. If yes → `"booking_tools"`. If no → `END`.

## Related

- [[components/primary_assistant]] — routes here via `ToHotelBooking`
- [[components/hotel_langgraph]] — parent graph
- [[modules/hotel_guardrails]]
