---
type: entity
category: product
url: "https://developers.amadeus.com"
tags: [entity, product, hotel-systems, booking, PMS, external-api]
created: 2026-04-19
updated: 2026-04-19
---

# Amadeus Self-Service API

## What it is

Amadeus is a global travel technology company. Its Self-Service API provides real-time hotel inventory, rates, and booking functions — a standard integration point for hotel AI assistants needing live availability data.

## Role in this project

Amadeus is cited as the recommended starting point for real-time hotel data integration ("generous free tier, clear documentation for searching and booking"). It represents the type of external booking system the hotel chatbot would connect to via MCP in a production deployment.

## Key facts

- Provides: hotel availability search, rate plans, booking confirmation
- Free tier available for development use
- Part of the "CRS" (Central Reservation System) layer in hotel tech stacks
- Works alongside Sabre as an alternative hotel data provider
- Would be a natural MCP-compliant endpoint in a full-stack hotel assistant

## Relationship to current project

The current `hotel_guardrails` codebase uses an internal PostgreSQL hotel database (`src/hotel_guardrails/database.py`) rather than Amadeus. Amadeus integration would be the path to live multi-property inventory in a production deployment.

## Related

- [[model_context_protocol]]
- [[langgraph_state_machine_architecture]]
- [[PostgreSQL]]
