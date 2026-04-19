---
type: component
path: "src/hotel_guardrails/feedback_collector.py"
status: active
parent_module: hotel_guardrails
tags: [component, feedback, evaluation, quality]
created: 2026-04-19
updated: 2026-04-19
---

# FeedbackCollector — Response Quality Feedback

## Purpose

Captures quality signals for every chat response and exposes aggregated scores to the routing layer. Acts as the observability backbone for the hotel assistant's continuous improvement loop.

## Class: `FeedbackCollector`

**Module:** `src/hotel_guardrails/feedback_collector.py`

## Feedback Types

| Type | Enum | Source |
|---|---|---|
| Explicit | `FeedbackType.EXPLICIT` | User thumbs up (1.0) or thumbs down (0.0) via `POST /feedback` |
| Implicit | `FeedbackType.IMPLICIT` | Inferred from behaviour: follow-up questions, retries |
| Automated | `FeedbackType.AUTOMATED` | DeepEval pipeline scores injected programmatically |

## Data Model: `FeedbackRecord`

Each record (Pydantic `BaseModel`) captures:

- `request_id`, `session_id`, `timestamp`
- `query`, `response`
- `routing_path` — always `"langgraph"` currently
- `complexity` — `"simple"`, `"moderate"`, or `"complex"` (from `HybridRouter`)
- `latency_ms`
- `feedback_type`, `score` (0.0–1.0)
- `feedback_details` — free-form dict for additional metadata

## Key Methods

- `async record_response(...)` — called after every chat response is generated; stores a record with `FeedbackType.AUTOMATED` and no initial score
- `async record_explicit_feedback(request_id, score)` — updates an existing record with user-provided score
- `async get_average_score(session_id) -> Optional[float]` — returns average quality score for a session; passed as `feedback_store` to `HybridRouter` for routing metrics

## Storage

Records are written to a local JSON file (path configured at construction time). This is intentionally simple — no database dependency. The trade-off is loss of feedback data on container redeploy unless the path is on a mounted volume.

## Integration in Server

`server.py:lifespan()` constructs `FeedbackCollector()` and passes `feedback_collector.get_average_score` to `HybridRouter`. After each `/chat` response, the endpoint calls `record_response()`. The `/feedback` endpoint calls `record_explicit_feedback()`.

## Related

- [[components/hybrid_router]] — consumes `get_average_score`
- [[modules/hotel_guardrails]]
