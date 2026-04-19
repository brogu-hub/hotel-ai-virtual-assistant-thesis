---
type: concept
status: stub
related:
  - concepts/langgraph_state_machine_architecture
  - concepts/autogen_conversation_driven_orchestration
  - entities/crewai
tags: [concept, architecture, orchestration, multiagent]
created: 2026-04-19
updated: 2026-04-19
---

# CrewAI Role-Based Orchestration

## Definition

CrewAI is a multi-agent orchestration framework where agents are defined with specific **Roles, Goals, and Backstories**. The orchestrator manages task passing sequentially or hierarchically among a "crew" of specialized agents.

## Origin

Emerged circa 2024 as a high-speed-development alternative to LangGraph for multi-agent pipelines. YAML-like configuration enables standing up a multi-agent system in a few dozen lines of code.

## Variants & related concepts

- [[concepts/langgraph_state_machine_architecture]] — higher control, chosen for this project
- [[concepts/autogen_conversation_driven_orchestration]] — conversation-emergent alternative
- [[entities/crewai]]

## Core capabilities

- **Built-in Memory Layer:**
  - **Short-term:** Recent context from the current "crew" mission.
  - **Long-term:** Persistent data via local SQLite database or RAG.
  - **Entity memory:** Knowledge about specific subjects learned over time.
- **Sequential or hierarchical task routing** between agents.

## Why NOT chosen for this hotel project

CrewAI makes it harder to manage the "state" of a live transaction across multiple conversational turns. Hotel bookings require deterministic cycle handling (retry on failure, mid-session state recovery) that LangGraph's checkpointers provide and CrewAI does not guarantee.

## How it shows up in this project

CrewAI is evaluated as an architectural alternative in the thesis comparison. It is **not** used in the production codebase. The decision to use LangGraph instead is documented in [[decisions/_index]].

## Key references

- Source: `LLM_CHATBOT_CRITIRION.md` (Gemini architecture conversation, 2026)
- [[entities/crewai]]

## Open questions

- Is CrewAI explicitly mentioned in the thesis architecture decision record?
