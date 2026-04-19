---
type: entity
category: library
url: "https://github.com/microsoft/autogen"
tags: [entity, library, orchestration, multiagent, microsoft, alternative]
created: 2026-04-19
updated: 2026-04-19
---

# AutoGen (AG2)

## What it is

AutoGen (rebranded as AG2) is a Microsoft Research framework for multi-agent AI systems based on "Group Chat" dynamics where agents communicate, critique each other, and write/execute code to solve problems collaboratively.

## Role in this project

AutoGen is evaluated as an architectural alternative to LangGraph in the hotel chatbot context. It is not used in the production codebase. Its emergent, low-control communication style makes it unsuitable for deterministic hotel booking transactions.

## Key facts

- Originally called AutoGen; community rebranding to AG2 occurred circa 2025
- Built on conversational exchange between agents ("Group Chat")
- Low pre-defined control — behavior emerges from agent dialogue
- Supports autonomous code writing and execution
- Memory via conversational history or Mem0 integration
- Best suited for: research assistants, coding bots, open-ended problem solving

## Related

- [[autogen_conversation_driven_orchestration]]
- [[langgraph_state_machine_architecture]]
- [[crewai_role_based_orchestration]]
- [[Mem0]]
