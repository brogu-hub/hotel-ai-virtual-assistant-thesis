---
type: module
path: src/common/
status: active
language: python
purpose: "Shared utilities: LLM wrappers, embeddings, rerankers, vector store adapters, configuration"
maintainer: Mangakorian
last_updated: 2026-04-19
depends_on: []
used_by: [hotel_guardrails, agent, retrievers, analytics, ingest_service]
linked_issues: []
tags: [module, common, shared-utils]
created: 2026-04-19
updated: 2026-04-19
---

# common

## Purpose

Shared utility library consumed by all other services. Provides abstracted LLM, embedding, reranker, and vector store interfaces that can swap between NVIDIA NIM (prod) and OpenRouter/sentence-transformers (dev).

## Key components

| File | Role |
|---|---|
| `llm_openrouter.py` | OpenRouter LLM client |
| `llm_fallback.py` | `FallbackLLM` — chains multiple providers with failover |
| `embeddings_openrouter.py` | OpenRouter embeddings client |
| `reranker_qwen.py` | Qwen3-0.6B reranker (dev) |
| `reranker_nvidia.py` | NVIDIA NIM reranker (prod) |
| `vectorstore_qdrant.py` | Qdrant vector store adapter |
| `configuration.py` | Base configuration reading |
| `configuration_wizard.py` | `ConfigWizard` base class with `@configclass` / `configfield` decorators; reads env vars with `APP_{SECTION}_{FIELD}` prefix |

## Configuration system

`ConfigWizard` pattern: subclass `ConfigWizard`, decorate sections with `@configclass`, individual fields with `configfield`. Environment variable pattern: `APP_LLM_MODELNAME`, `APP_VECTORSTORE_NAME`, etc.

## LLM Fallback Chain

`FallbackLLM` chains providers in order: primary → secondary → ... → fallback. If the primary fails, the next is tried transparently.

## Dependencies

- External: [[OpenRouter]], [[Qdrant]], [[NVIDIA]] NIM, `sentence-transformers`

## Used by

- [[hotel_guardrails]], [[agent]], [[retrievers]], [[analytics]], [[ingest_service]]

## Related

- [[Configuration Wizard Pattern]]
- [[LLM Fallback Chain]]
- [[ADR OpenRouter Dev Backend]]
