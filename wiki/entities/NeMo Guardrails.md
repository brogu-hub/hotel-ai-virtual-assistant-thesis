---
type: entity
category: library
url: https://github.com/NVIDIA/NeMo-Guardrails
tags: [entity, library, nvidia, guardrails, safety]
created: 2026-04-19
updated: 2026-04-19
---

# NeMo Guardrails

## What it is

NVIDIA NeMo Guardrails is an open-source toolkit for adding programmable safety rails to LLM conversations, using a domain-specific language called Colang.

## Role in this project

NeMo Guardrails provides the **safety layer** in `hotel_guardrails`. The config lives in `src/hotel_guardrails/config/` (config.yml, prompts.yml, rails.co). The hybrid architecture layers NeMo Guardrails atop [[LangGraph]] rather than replacing it.

## Key facts

- Config directory: `src/hotel_guardrails/config/`
- Rail definitions: `rails.co` (Colang DSL)
- Prompts for rails: `prompts.yml`
- The `hybrid_router.py` runs safety checks via NeMo Guardrails before passing to LangGraph
- Part of the [[ADR Hybrid Architecture]] decision

## Related

- [[Hybrid Routing]]
- [[hotel_guardrails]]
- [[NVIDIA]]
- [[ADR Hybrid Architecture]]
- [[LangGraph]]
