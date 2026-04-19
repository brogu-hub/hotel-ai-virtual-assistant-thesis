---
type: paper
status: stub
year: 2025
authors: [Unknown — MDPI Tourism journal]
venue: "MDPI Tourism AI Research (journal article)"
url: "https://www.mdpi.com"
key_claim: "Travelers have high uncertainty regarding non-refundable booking policies — RAG must prioritize accurate policy retrieval."
methodology: "Academic survey/study on traveler AI interaction patterns and booking uncertainty"
contradicts: []
supports:
  - concepts/hybrid_rag_with_reranking
tags: [paper, academic, tourism, RAG, policy-retrieval, MDPI]
created: 2026-04-19
updated: 2026-04-19
---

# MDPI Tourism AI Research (2025)

> **Authors**: Not directly identified — attributed as "MDPI Tourism AI Research" 
> **Venue / Year**: MDPI journal, circa 2025
> **Link**: MDPI open-access platform (specific URL not provided in source)

## Key claim

Travelers have **high uncertainty** regarding non-refundable bookings and cancellation policies. This motivates the use of Hybrid RAG with re-ranking to ensure policy documents are accurately surfaced by hotel chatbots.

## Methodology

Academic study examining traveler decision-making patterns and information uncertainty in AI-assisted hotel booking contexts.

## Results

- Travelers express high uncertainty around non-refundable booking terms
- Standard vector-only RAG risks surfacing adjacent (e.g., spa cancellation) instead of standard cancellation policy
- Re-ranking models (Cohere, BGE) resolve this by scoring document relevance before LLM ingestion

## Relevance to thesis

Supports the design choice of Hybrid RAG + re-ranking in the hotel knowledge retrieval stack. The `hotel_knowledge` sub-agent and `src/common/reranker_qwen.py` are directly motivated by this finding.

## Quotes worth keeping

> Recent studies highlight that travelers have "high uncertainty" regarding non-refundable bookings. — MDPI Tourism AI Research

## Related

- [[concepts/hybrid_rag_with_reranking]]
- [[thesis/evaluation_methodology]]

## Open questions

- Full citation needed — author names, volume/issue number, DOI.
- Is this paper cited in the thesis bibliography?
