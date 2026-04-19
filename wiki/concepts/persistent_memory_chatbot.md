---
type: concept
status: developing
related:
  - concepts/langgraph_state_machine_architecture
  - entities/langgraph
  - entities/mem0
tags: [concept, memory, persistence, stateful, personalization]
created: 2026-04-19
updated: 2026-04-19
---

# Persistent Memory (Chatbot)

## Definition

Persistent memory in a chatbot context means the system retains state — guest preferences, booking drafts, past interactions — across conversation turns and across sessions (days/weeks later). It goes beyond a simple in-session chat history.

## Origin

Necessity emerged as LLM-based chatbots moved from stateless API calls to multi-turn agentic workflows. The pattern was formalized with the rise of LangGraph Checkpointers, Mem0, and hybrid vector+relational storage approaches circa 2024–2026.

## Memory tiers

| Tier | Storage | Scope |
|---|---|---|
| **Short-term** | LangGraph state / in-memory | Current conversation thread |
| **Long-term (session)** | Redis (fast retrieval) | Current booking draft, recent context |
| **Long-term (persistent)** | PostgreSQL with pgvector | Guest preferences across visits |
| **Entity memory** | Vector DB (Qdrant/Milvus) | Facts about specific guests or bookings |

## Variants & related concepts

- [[concepts/langgraph_state_machine_architecture]] — provides Checkpointers for short/medium persistence
- [[entities/mem0]] — "Memory-as-a-Service" that extracts facts and stores in vector DB
- [[concepts/hybrid_rag_with_reranking]] — used alongside memory for knowledge retrieval

## How it shows up in this project

LangGraph Checkpointers are used in `hotel_langgraph.py`. PostgreSQL is the backing store for long-term guest/booking data (`src/hotel_guardrails/database.py`). Redis is used for caching (`APP_CACHE_URL`). The combination enables multi-turn booking sessions to survive user disconnects.

## Implementation pattern

```
Short-term: LangGraph state dict (in-memory, lost on restart)
Medium-term: Redis (APP_CACHE_URL) — current booking draft
Long-term: PostgreSQL — guest preferences, booking history
Semantic: Qdrant / pgvector — preference vectors for personalization
```

## Key references

- Source: `LLM_CHATBOT_CRITIRION.md` (Gemini architecture conversation, 2026)
- [[entities/mem0]]
- [[entities/langgraph]]

## Open questions

- Is long-term personalization (past preferences) actually implemented, or only short-term session state?
- Does the thesis include a memory-tier diagram?
