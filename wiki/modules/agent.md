---
type: module
path: src/agent/
status: legacy
language: python
purpose: "Original NVIDIA blueprint agent — retained as reference implementation"
maintainer: Mangakorian
last_updated: 2026-04-19
depends_on: [common, retrievers]
used_by: []
linked_issues: []
tags: [module, agent, nvidia-blueprint, legacy]
created: 2026-04-19
updated: 2026-04-19
---

# agent

## Purpose

The original [[NVIDIA]] AI Blueprint customer service agent, retained as-is for comparison and fallback. Uses [[LangGraph]] with NVIDIA NIM endpoints and targets the original retail use-case data (gear store, orders, returns).

## Entry points

- `server.py` — FastAPI app on port 8081
- `main.py` — StateGraph definition

## Internal structure

| File | Role |
|---|---|
| `main.py` | StateGraph: validate_product_info → router → sub-agents |
| `server.py` | FastAPI app |
| `tools.py` | Agent tools: structured_rag, canonical_rag, purchase history, returns |
| `hotel_tools.py` | Hotel-specific tool extensions (added in fork) |
| `prompt.yaml` | Original customer service prompts |
| `hotel_prompt.yaml` | Hotel-specific prompt overrides |

## Sub-agents

- `ProductQA` — product questions via unstructured RAG
- `OrderStatus` — order lookup via structured RAG
- `ReturnProcessing` — returns workflow

## Dependencies

- External: [[FastAPI]], [[LangGraph]], [[NVIDIA]] NIM, [[Milvus]], [[Vanna.AI]]
- Internal: [[common]], [[retrievers]]

## Notes & gotchas

- Not actively developed; `hotel_guardrails` is the primary service
- Same port (8081) as hotel_guardrails — only one runs at a time
- Prompts tuned for [[Llama 3.3 70B]]

## Related

- [[ADR Fork NVIDIA Blueprint]]
- [[hotel_guardrails]]
