---
type: component
parent_module: agent
path: src/agent/hotel_tools.py
status: active
tags: [component, agent, hotel-tools, crud, dynamic-pricing, rag, bilingual]
created: 2026-04-19
updated: 2026-04-19
---

# agent_hotel_tools

Hotel-specific tool extensions added to the [[agent]] module during the fork (`src/agent/hotel_tools.py`). Provides full CRUD over the hotel database plus dynamic pricing, upselling, RAG knowledge search, and a mock payment link generator.

> [!note] Unlike the rest of `src/agent/`, this file is actively maintained — it overlaps in purpose with tools inside [[hotel_guardrails]] and cross-imports from that service at runtime.

## Tool inventory

### Read operations

| Tool | Purpose |
| --- | --- |
| `check_room_availability` | Query available rooms for date range; optional room-type filter |
| `get_reservation_details` | Fetch full reservation by ID or confirmation number |
| `get_guest_reservations` | List all reservations for a guest email |
| `get_hotel_services` | List active hotel services from `hotel_services` table |

### Create / confirm operations

| Tool | Purpose |
| --- | --- |
| `create_reservation` | Book a room; auto-registers guest by email if unknown; applies dynamic pricing |
| `confirm_reservation` | Transition `pending` → `confirmed` |
| `create_service_request` | Log a service request against a reservation |

### Update operations

| Tool | Purpose |
| --- | --- |
| `update_reservation` | Modify dates, room, guest count, or special requests; recalculates total |
| `check_in_guest` | Transition `confirmed` → `checked_in`; sets room `occupied` |
| `check_out_guest` | Transition `checked_in` → `checked_out`; marks payment `paid`, room `cleaning` |

### Cancel

| Tool | Purpose |
| --- | --- |
| `cancel_reservation` | Cancel `pending` or `confirmed` reservation with reason |

### Knowledge & pricing

| Tool | Purpose |
| --- | --- |
| `search_hotel_knowledge` | RAG search via [[hotel_guardrails]] `HotelKnowledgeRetriever`; checks `chat_scaling` cache first |
| `calculate_dynamic_price` | Show pricing breakdown with early-bird/last-minute multipliers |
| `check_upsell_opportunity` | Suggest next room tier upgrade with price delta |
| `generate_payment_link` | Demo payment link (writes to `payment_links` table, 30 min TTL) |

## Dynamic pricing model

`_calculate_dynamic_multiplier(check_in_date)` applies tiered multipliers based on days-until-check-in:

| Days ahead | Multiplier | Label |
| --- | --- | --- |
| ≥ 30 | 0.85 | Early Bird 15% off |
| 14–29 | 0.90 | Advance Booking 10% off |
| 7–13 | 1.00 | Standard Rate |
| 1–6 | 1.20 | Last-Minute +20% |
| 0 | 1.30 | Same-Day +30% |

This logic is duplicated in [[hotel_guardrails]] `actions.py` — see contradiction callout below.

## Routing classes

`ToHotelBookingAssistant` and `ToHotelServiceAssistant` — Pydantic routing classes following the same pattern as the original `tools.py`, intended for wiring into a hotel-adapted `primary_assistant`.

## Cross-service dependency

`search_hotel_knowledge` imports from `src.hotel_guardrails.chat_scaling` (knowledge cache) and `src.retrievers.hotel_knowledge.chains` at call time. If those services are unavailable the tool falls back gracefully, directing the guest to Front Desk extension 0.

## Bilingual output

All tool responses are bilingual Thai/English inline (e.g., `"ห้องว่างสำหรับ ... / Available rooms for ..."`). The hotel prompt (`hotel_prompt.yaml`) instructs the LLM to pick one language based on the guest's input.

> [!contradiction]
> Dynamic pricing logic (`_calculate_dynamic_multiplier`) appears in both this file and `src/hotel_guardrails/actions.py`. If the tiers diverge between the two files, guests booking via the two different endpoints would receive different prices. Needs a shared utility.

## Related

- [[agent_tools]] — original retail tools in the same module
- [[hotel_guardrails]] — the primary hotel service; this file cross-imports from it
- [[booking_subagent]] — hotel_guardrails equivalent for booking operations
- [[agentic_upselling]] — concept behind `check_upsell_opportunity`
