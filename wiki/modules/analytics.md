---
type: module
path: src/analytics/
status: active
language: python
purpose: "Sentiment analysis and conversation summarization microservice"
maintainer: Mangakorian
last_updated: 2026-04-19
depends_on: [common]
used_by: []
linked_issues: []
tags: [module, analytics]
created: 2026-04-19
updated: 2026-04-19
---

# analytics

## Purpose

Standalone microservice providing sentiment analysis and conversation summarization for the hotel assistant. Part of the data flywheel: operational teams use summaries and sentiment scores to monitor quality.

## Entry points

- FastAPI server on port 8082

## Key capabilities

- Real-time sentiment analysis on customer messages (scores: +1, 0, −1)
- Conversation summarization for post-session review
- Feedback storage for data flywheel / continuous improvement

## Internal structure

- `prompt.yaml` — Prompt templates for summarization and sentiment chains

## Dependencies

- External: [[FastAPI]], [[NVIDIA]] NIM or [[OpenRouter]] (LLM)
- Internal: [[common]]

## Notes & gotchas

- Feedback convention: +1 positive, 0 neutral, −1 negative
- `feedback` URL paths are explicitly for data flywheel collection

## Related

- [[hotel_guardrails]]
- [[Data Flywheel]]
