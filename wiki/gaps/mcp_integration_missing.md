---
type: gap
priority: medium
blocking: [thesis/evaluation_methodology]
tags: [gap, MCP, hotel-systems, integration, future-work]
created: 2026-04-19
updated: 2026-04-19
---

# Gap: MCP Integration Not Implemented

## Description

The industry best practice for hotel AI chatbots is a **Model Context Protocol (MCP)** layer that provides a unified interface to PMS, CRS, and CRM systems. The current `hotel_guardrails` codebase uses a single PostgreSQL database (`src/hotel_guardrails/database.py`) instead of multi-system integration.

## Why it matters

Without MCP, the system cannot integrate live inventory from OTA channels (Expedia, Booking.com), meaning a room confirmed by the bot could have been sold elsewhere seconds earlier ("data lag").

## Recommended action

- Thesis: Document as a **known limitation** in Chapter 5 and **future work** in Chapter 6
- Codebase: Prototype an MCP-compliant tool layer or Amadeus API integration as an extension

## Related

- [[concepts/model_context_protocol]]
- [[entities/Amadeus API]]
- [[thesis/evaluation_methodology]]
