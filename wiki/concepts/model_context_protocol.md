---
type: concept
status: developing
related:
  - concepts/langgraph_state_machine_architecture
  - concepts/hybrid_rag_with_reranking
tags: [concept, integration, hotel-systems, MCP, connectivity, interoperability]
created: 2026-04-19
updated: 2026-04-19
---

# Model Context Protocol (MCP)

## Definition

MCP is a standardized communication protocol that allows AI agents to query multiple hotel backend systems (PMS, CRS, CRM) through a single structured interface, rather than requiring custom API wrappers for each system.

## Origin

Emerged from the practical fragmentation of hotel technology stacks. Cited in industry implementations by companies **Mirai** and **Cybage** as of 2025–2026. MCP provides the agent with a "navigable" structured view of the hotel's source-of-truth data rather than scraping website content.

## The hotel fragmentation problem

Hotel systems are fragmented across:
- **PMS** (Property Management System) — room status
- **CRS** (Central Reservation System) — pricing and availability
- **CRM** — guest history and preferences
- **OTA channels** (Expedia, Booking.com) — may book rooms seconds before the chatbot confirms

Without MCP, the bot may promise a room that was sold on Expedia 30 seconds earlier ("data lag").

## Variants & related concepts

- [[concepts/human_in_the_loop]] — MCP + HITL together prevent over-commitment on availability
- [[concepts/agentic_upselling]] — MCP enables real-time inventory checks for upsell offers

## How it shows up in this project

MCP is referenced as a best-practice component the project aspires to. The current implementation uses direct tool functions (`check_availability`, `create_reservation`) in `src/hotel_guardrails/actions.py` that call the PostgreSQL hotel database. A full MCP layer (multi-system routing) is not yet implemented.

> [!gap] The current codebase uses a single PostgreSQL store rather than a full MCP-compliant multi-system integration. This is a known limitation to note in the thesis.

## Industry citations

- Mirai and Cybage: MCP-compliant hotel booking agents (2025–2026)
- Amadeus Self-Service API: cited as a "generous free tier" starting point for real-time hotel data

## Key references

- Source: `LLM_CHATBOT_CRITIRION.md` (Gemini architecture conversation, 2026)
- [[entities/amadeus_api]]

## Open questions

- Does the thesis discuss MCP as a future work item?
- Is there an Amadeus API integration planned or implemented anywhere in the codebase?
