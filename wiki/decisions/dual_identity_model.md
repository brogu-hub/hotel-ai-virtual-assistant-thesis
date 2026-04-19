---
type: decision
status: active
date: 2026-04-19
context: "Hotel guest identity — do guests need accounts to chat or book?"
created: 2026-04-19
updated: 2026-04-19
tags: [decision, auth, identity, ux]
---

# Decision: Dual Identity Model (GUESTS vs USERS)

## Status

Active.

## Context

The system needs to handle two personas:

1. **Walk-in guests** — hotel customers who chat via the website. They may never create an account.
2. **Registered users** — guests who want persistent login, booking history across devices, or admin access.

## Decision

Maintain two separate tables:

- `GUESTS` — hotel profile (email, name, loyalty tier, preferences). Created automatically when a new email is used for a booking. No password.
- `USERS` — login credentials (username, password_hash, role). Optional link to a guest profile via `guest_id` FK.

Guest chat flow uses email-only identity. No login, no token, no friction.

## Rationale

- Frictionless booking is a hotel-industry UX requirement — requiring account creation would drive users away.
- Staff and registered users need access control (JWT) for `/admin/*` and `/dashboard/*`.
- Linking `users.guest_id → guests.guest_id` allows a registered user to see their full booking history once they choose to create an account.

## Consequences

- `GUESTS` table grows with every new booking email.
- Two auth paths must be maintained and tested separately.
- `/chat`, `/rooms`, `/bookings`, `/guests` are fully public — no token required.

## Related

- [[auth_and_access_control]] — implementation detail
- [[reservation_lifecycle]] — auto-register guest on first booking
