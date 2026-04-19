---
type: concept
status: stub
related:
  - concepts/langgraph_state_machine_architecture
  - concepts/crewai_role_based_orchestration
  - entities/autogen
tags: [concept, architecture, orchestration, multiagent, research]
created: 2026-04-19
updated: 2026-04-19
---

# AutoGen / AG2 Conversation-Driven Orchestration

## Definition

AutoGen (rebranded as AG2) is a multi-agent framework centered on **Group Chats** where agents speak to each other, critique work, and write and execute code autonomously to solve tasks. Control is emergent rather than pre-defined.

## Origin

Developed by Microsoft Research. Originally called AutoGen; community fork/rebranding to AG2 occurred circa 2025. Suited to research, coding assistants, and open-ended problem solving.

## Variants & related concepts

- [[concepts/langgraph_state_machine_architecture]] — deterministic, chosen for this project
- [[concepts/crewai_role_based_orchestration]] — role-based alternative
- [[concepts/persistent_memory_chatbot]] — AutoGen integrates with Mem0 for persistence

## Core capabilities

- Agents "talk it out" or brainstorm to solve problems.
- Supports autonomous code writing and execution.
- Memory via conversational history or integration with **Mem0** / specialized vector stores.

## Why NOT chosen for this hotel project

AutoGen offers low control (dynamic/emergent). Hotel booking workflows require predictable, step-by-step transaction management. A hallucination or lost-state mid-booking has direct business consequences. AutoGen is best suited for research or open-ended coding bots, not customer-facing transactional systems.

## How it shows up in this project

Evaluated as an architectural alternative in the thesis. Not used in production. Referenced in the architecture comparison table.

## Key references

- Source: `LLM_CHATBOT_CRITIRION.md` (Gemini architecture conversation, 2026)
- [[entities/autogen]]

## Open questions

- Does the thesis cite any AutoGen academic publications?
