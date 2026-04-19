---
type: entity
category: org
url: https://www.nvidia.com
tags: [entity, org, nvidia, nim, blueprint]
created: 2026-04-19
updated: 2026-04-19
---

# NVIDIA

## What it is

NVIDIA Corporation — GPU hardware company and AI platform provider whose NIM microservices and AI Blueprints form the upstream origin of this project.

## Role in this project

The hotel AI assistant is a fork of the **NVIDIA AI Blueprint: AI Virtual Assistant for Customer Service**. The production backend uses NVIDIA NIM endpoints for LLM inference, embeddings, and reranking. The original agent in `src/agent/` is the unmodified blueprint agent.

## Key facts

- Blueprint license: Apache 2.0
- Primary LLM: [[Llama 3.3 70B]] via NVIDIA NIM hosted at `api.nvidia.com`
- Embedding NIM: `nvidia/llama-3.2-nv-embedqa-1b-v2`
- Reranker NIM: `nvidia/llama-3.2-nv-rerankqa-1b-v2`
- Self-hosted NIM minimum hardware: 8×H100 or 8×A100
- NGC (NVIDIA GPU Cloud) used for container registry and API key management
- NeMo Retriever powers the embedding and reranking NIMs
- Synthetic data generation uses Nemotron-4 340B NIM

## Related

- [[Llama 3.3 70B]]
- [[NeMo Guardrails]]
- [[Milvus]]
- [[agent]]
- [[hotel_guardrails]]
- [[ADR Fork NVIDIA Blueprint]]
