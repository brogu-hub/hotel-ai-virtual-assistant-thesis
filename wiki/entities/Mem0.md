---
type: entity
category: product
url: "https://mem0.ai"
tags: [entity, product, memory, personalization, vector-store]
created: 2026-04-19
updated: 2026-04-19
---

# Mem0

## What it is

Mem0 is a "Memory-as-a-Service" platform that extracts structured facts from conversations (e.g., "User prefers king-sized beds") and stores them in a vector database for retrieval in future sessions. It enables long-term personalization across chatbot sessions.

## Role in this project

Mem0 is referenced as a best-practice component for long-term guest personalization in the hotel chatbot context. The current project implements long-term memory via PostgreSQL + pgvector rather than Mem0 directly, but the architectural pattern Mem0 represents is directly applicable.

## Key facts

- Extracts facts from conversation and stores in vector DB
- Enables retrieval of past preferences weeks/months later
- Integrates with AutoGen/AG2 as a memory layer
- Positioned as the leading "Memory-as-a-Service" as of 2025–2026
- Alternative to custom hybrid retrieval (vector DB + knowledge graph)

## Related

- [[persistent_memory_chatbot]]
- [[autogen_conversation_driven_orchestration]]
- [[Qdrant]]
- [[PostgreSQL]]
