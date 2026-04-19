---
type: flow
status: active
entry_point: "hotel_booking sub-agent"
endpoints:
  - "POST /chat"
  - "POST /tools/book"
  - "GET /bookings"
  - "GET /bookings/{id}"
  - "PATCH /bookings/{id}"
  - "GET /rooms"
  - "GET /rooms/availability"
  - "GET /rooms/{id}"
involves:
  - hotel_booking
  - hotel_langgraph
  - database
  - PostgreSQL
created: 2026-04-19
updated: 2026-04-19
tags: [flow, booking, reservation, postgresql]
---

# Flow: Reservation Lifecycle

Covers the full lifecycle of a hotel booking from guest chat through to check-out, plus the admin override path.

## Status machine

```
create_reservation()        confirm_reservation()
       |                           |
       v                           v
   +--------+              +-----------+
   | pending | ----------> | confirmed |
   +--------+              +-----------+
       |                        |    |
       |   cancel_reservation() |    |  check_in_guest()
       |         |              |    |
       v         v              v    v
 +-----------+              +------------+
 | cancelled |              | checked_in |
 +-----------+              +------------+
                                   |
                                   |  check_out_guest()
                                   v
                            +--------------+
                            | checked_out  |
                            +--------------+
```

Rules:
- No hard deletes — all state changes via SQL `UPDATE`.
- `payment_status` stays `pending` throughout (demo; no real payment processing).
- Soft-cancel is safe to call at any pre-checkin status.

## New booking (multi-turn chat)

```mermaid
sequenceDiagram
    participant G as Guest
    participant B as hotel_booking sub-agent
    participant DB as PostgreSQL

    G->>B: "I want to book a room"
    B-->>G: "What dates and room type?"
    G->>B: "Deluxe, Apr 15-17, 2 guests"
    B->>DB: check_room_availability(room_type, dates)
    DB-->>B: 10 Deluxe rooms available
    B-->>G: "4,500 THB/night. Total 9,000 THB. Email?"
    G->>B: "my.email@gmail.com"
    B->>DB: auto-register guest (if new email)
    B->>DB: create_reservation() → status=pending
    DB-->>B: HTL2604150001
    B-->>G: "Booked! Confirm now?"
    G->>B: "Yes"
    B->>DB: confirm_reservation() → status=confirmed
    DB-->>B: OK
    B-->>G: "Confirmed! Email sent."
```

## Dynamic pricing

Applied automatically inside `create_reservation()`. The `calculate_dynamic_price` tool shows the guest the actual price before they commit.

| Days before check-in | Multiplier | Label |
|---|---|---|
| 30+ | 0.85× | Early Bird 15% off |
| 14-29 | 0.90× | Advance 10% off |
| 7-13 | 1.00× | Standard Rate |
| 1-6 | 1.20× | Last-Minute +20% |
| Same day | 1.30× | Same-Day +30% |

## Manage existing booking

```mermaid
sequenceDiagram
    participant G as Guest
    participant B as hotel_booking sub-agent
    participant DB as PostgreSQL

    G->>B: "Check booking HTL2604150001"
    B->>DB: get_reservation_details(confirmation_number)
    DB-->>B: Room 404, Apr 15-17, confirmed, 9,000 THB
    B-->>G: booking summary
    G->>B: "Cancel — plans changed"
    B->>DB: cancel_reservation() → status=cancelled
    B-->>G: "Cancelled. Cancellation email sent."
```

## Hotel arrival (front-desk check-in)

This is an in-person flow — not chatbot. Staff verifies in the system:

1. Guest presents email or confirmation number.
2. Staff queries reservation: `status == confirmed`, room assignment matches.
3. Staff processes check-in: `check_in_guest()` → `status = checked_in`.
4. Guest pays at front desk (demo: no real transaction).
5. Guest receives room key.

Admin API: `PUT /admin/bookings/{id}/status` can force any status override (e.g., no-show).

## Mock payment flow

```mermaid
sequenceDiagram
    participant G as Guest
    participant B as Bot
    participant S as Server
    participant DB as PostgreSQL

    G->>B: "Confirm booking"
    B->>S: generate_payment_link()
    S->>DB: INSERT payment token (expires 30min)
    S-->>B: pay.grandhorizon.hotel/checkout/{token}
    B-->>G: "Pay here: {url}"
    G->>S: GET /payment/{token}
    S->>DB: fetch booking details
    S-->>G: {amount, room, dates}
    G->>S: POST /payment/{token}/complete
    S->>DB: UPDATE status=paid
    S-->>G: "Payment successful"
```

## Tools in `actions.py`

| Tool | Purpose |
|---|---|
| `check_room_availability(room_type, check_in, check_out)` | Returns count of available rooms and base price |
| `calculate_dynamic_price(room_type, check_in)` | Returns final price with multiplier |
| `create_reservation(email, room_type, check_in, check_out, guests)` | Creates `pending` reservation, auto-registers guest |
| `confirm_reservation(confirmation_number)` | Moves `pending → confirmed` |
| `update_reservation(confirmation_number, ...)` | Modifies dates / room type |
| `cancel_reservation(confirmation_number)` | Soft-cancel → `cancelled` |
| `check_in_guest(confirmation_number)` | `confirmed → checked_in` |
| `check_out_guest(confirmation_number)` | `checked_in → checked_out` |
| `get_reservation_details(confirmation_number \| email)` | Lookup booking |

## Failure modes

| Failure | Behaviour |
|---|---|
| Room not available | Bot reports "sold out", offers alternatives |
| Invalid confirmation number | Tool returns not-found error |
| Payment token expired | `GET /payment/{token}` returns 404 |
| DB constraint violation | Exception propagated, booking not created |

## Related

- [[guest_chat]] — parent flow
- [[hotel_guardrails]] — module containing these tools
- [[database]] — PostgreSQL schema
- [[decisions/no_hard_deletes]] — why cancellation is a status update
- [[decisions/dynamic_pricing]] — pricing multiplier rationale
