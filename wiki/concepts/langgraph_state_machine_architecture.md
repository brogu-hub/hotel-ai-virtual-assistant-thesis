---
type: concept
status: mature
related:
  - concepts/persistent_memory_chatbot
  - concepts/human_in_the_loop
  - entities/langgraph
tags: [concept, architecture, orchestration, langgraph, statemachine]
created: 2026-04-19
updated: 2026-04-19
---

# LangGraph State Machine Architecture

## Definition

LangGraph treats a chatbot as a **Directed Acyclic Graph (DAG)** — or a cyclic graph where each node is a function or sub-agent and edges define transition logic. It is the primary orchestration pattern used in this project's `hotel_guardrails` service.

## Origin

Developed by the LangChain team as part of the LangChain ecosystem. Gained industry adoption circa 2024–2026 as the standard for production-grade agentic systems requiring reliability and Human-in-the-Loop capabilities.

## Variants & related concepts

- [[concepts/crewai_role_based_orchestration]] — role-based alternative, lower control
- [[concepts/autogen_conversation_driven_orchestration]] — conversation/emergent alternative
- [[concepts/human_in_the_loop]] — enabled by LangGraph's "Break" state checkpointing
- [[concepts/persistent_memory_chatbot]] — implemented via LangGraph Checkpointers

## Core capabilities

- **Checkpointers:** Save full graph state (not just chat history) to PostgreSQL, Redis, or MongoDB after every step.
- **Time Travel / Debugging:** If an agent fails at Step 3, state can be rewound to Step 2 and resumed.
- **Deterministic Cycles:** Allows the bot to loop — e.g., if booking fails because a room was snatched, the graph can loop back to the Search node automatically.
- **"Break" State:** Pauses execution pending a human confirmation before committing a transaction.

## How it shows up in this project

The `hotel_guardrails` service uses LangGraph as its state machine backbone (`src/hotel_guardrails/hotel_langgraph.py`). The graph routes from `primary_assistant` to sub-agents: `hotel_booking`, `hotel_service`, `hotel_knowledge`, and `other_talk`. See [[flows/_index]] for the full request path.

## Why chosen for hotels

Hotels have non-linear conversations. A user may check prices, ask about the pool (RAG), then return to change the date. A state machine can track this across turns while guaranteeing transactional integrity. Simpler frameworks (CrewAI, Botpress) struggle to maintain state across live multi-turn transactions.

## Key references

- Source: `LLM_CHATBOT_CRITIRION.md` (Gemini architecture conversation, 2026)
- [[entities/langgraph]]
- [[concepts/persistent_memory_chatbot]]

## Open questions

- Does the thesis formalize the specific graph topology (nodes, edges) as a diagram?
- Does "time travel" debugging get exercised in any of the experiment runs?
