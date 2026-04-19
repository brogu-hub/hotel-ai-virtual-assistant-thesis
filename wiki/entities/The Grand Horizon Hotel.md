---
type: entity
category: org
url: ""
tags: [entity, fictional, hotel, domain]
created: 2026-04-19
updated: 2026-04-19
---

# The Grand Horizon Hotel

## What it is

The Grand Horizon Hotel is the **fictional hotel brand** used throughout this thesis project as the customer-facing persona for the AI virtual assistant.

## Role in this project

All hotel-domain data, prompts, and conversational personas are written for The Grand Horizon Hotel. It replaces the original NVIDIA blueprint's retail/gear-store use case.

## Key facts

- Hotel knowledge base: `data/hotel/*.md` (dining, facilities, room types, policies, etc.)
- Database schema contains: rooms, bookings, guests tables
- Sub-agents serve: bookings, services/amenities, knowledge Q&A, general conversation
- Name appears in system prompts in `src/hotel_guardrails/config/prompts.yml`

## Related

- [[hotel_guardrails]]
- [[ADR Fork NVIDIA Blueprint]]
- [[Chat Request Flow]]
