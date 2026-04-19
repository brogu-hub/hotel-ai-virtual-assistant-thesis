---
type: experiment
status: done
date: 2026-04-06
hypothesis: "Qwen3-max (cloud) will outperform Qwen3.5 Opus 9B (local Ollama) on hotel assistant tasks, but local model will achieve acceptable accuracy with lower cost."
metric: "Overall accuracy (pass/fail per test case), keyword accuracy, language accuracy, per-category accuracy, latency (avg / p50 / p95)"
outcome: "Cloud model scored 100% vs local 92%. Both achieved 100% language accuracy. Cloud was faster (p50: 6703ms vs 9049ms). Cohen's κ = 0.000 indicates poor inter-model agreement on which specific cases pass/fail."
tags: [experiment, eval, model-comparison, qwen, ollama, openrouter]
created: 2026-04-19
updated: 2026-04-19
---

# Experiment: Local vs Cloud Model Evaluation (2026-04-06)

## Hypothesis

[[Qwen3-max]] (via OpenRouter cloud) will score higher than [[Qwen3.5-Opus-9B]] (via Ollama local) on a structured 25-case hotel assistant benchmark, but the local model will remain viable for development given its zero marginal cost. Both should achieve 100% language detection accuracy.

## Setup

- **Code path:** `scripts/eval/run_evaluation.py` (inferred; report dated 2026-04-06 16:22)
- **Local model:** `fredrezones55/qwen3.5-opus:9b` via Ollama
- **Cloud model:** `qwen/qwen3-max` via OpenRouter
- **Test cases:** 25 total across 5 categories
- **Evaluation criteria:** keyword matching, language detection, response completeness, latency
- **System under test:** [[hotel_guardrails]] — LangGraph agent with 4 sub-agents (booking, service, knowledge, other_talk)
- **Routing observed:** `langgraph` (primary), `langchain_fallback` (secondary)

## Test Categories

| Category | Cases | Description |
|----------|-------|-------------|
| Knowledge (K) | 8 | RAG-retrieved hotel info, EN + TH |
| Booking (B) | 6 | Room availability, reservation CRUD |
| Greeting (G) | 4 | Conversation handling, out-of-scope queries |
| Language (L) | 3 | Language-match enforcement (EN/TH) |
| Edge (E) | 4 | Multi-room, empty input, special dates |

## Results

### Overall Summary

| Metric | Qwen3.5 Opus 9B (Local) | Qwen3-max (Cloud) |
|--------|-------------------------|-------------------|
| Overall accuracy | 23/25 (92%) | 25/25 (100%) |
| Keyword accuracy | 80% | 88% |
| Language accuracy | 100% | 100% |
| Avg latency | 9,905 ms | 8,852 ms |
| p50 latency | 9,049 ms | 6,703 ms |
| p95 latency | 18,360 ms | 13,933 ms |
| Errors / timeouts | 1 | 1 |

**Cohen's Kappa (inter-model agreement): κ = 0.000** — poor agreement, meaning each model fails on different cases.

### Per-Category Accuracy — Local

| Category | Passed | Total | Accuracy |
|----------|--------|-------|----------|
| Booking | 6 | 6 | 100% |
| Edge | 3 | 4 | 75% |
| Greeting | 3 | 4 | 75% |
| Knowledge | 8 | 8 | 100% |
| Language | 3 | 3 | 100% |

### Per-Category Accuracy — Cloud

| Category | Passed | Total | Accuracy |
|----------|--------|-------|----------|
| Booking | 6 | 6 | 100% |
| Edge | 4 | 4 | 100% |
| Greeting | 4 | 4 | 100% |
| Knowledge | 8 | 8 | 100% |
| Language | 3 | 3 | 100% |

### Disagreements (Cases Where Models Differ)

| ID | Category | Local | Cloud | Notes |
|----|----------|-------|-------|-------|
| G03 | Greeting | FAIL | PASS | "Thank you for your help!" — local scored 1/4 keywords |
| E03 | Edge | FAIL | PASS | Group booking (3 rooms, 10 people) — local responded in Thai |

### Notable Per-Case Latencies

| Case | Local (ms) | Cloud (ms) | Note |
|------|-----------|-----------|------|
| K01 breakfast | 34,624 | 6,457 | Outlier — local 5x slower |
| B05 create booking | 18,360 | 37,955 | Cloud outlier — longest cloud response |
| E04 empty input | 6 | 5 | Validation fast path on both |

### Infrastructure Test Results (Same Session)

Infrastructure tests run separately (date: 2026-04-06 16:24), **193/193 (100%)** pass rate:

| Suite | Tests | Passed | Time |
|-------|-------|--------|------|
| Auth Baseline | 72 | 72 | 4s |
| Auth Hardening | 38 | 38 | 10s |
| Audit + DB Scaling | 46 | 46 | 8s |
| Chat Scaling | 37 | 37 | 8s |

## Conclusion

The cloud model ([[Qwen3-max]]) achieves perfect accuracy and lower median latency, confirming its role as the production default. The local model ([[Qwen3.5-Opus-9B]]) is viable for development at 92% accuracy. The κ = 0.000 result is notable: it indicates the two models fail on *different* cases, suggesting they are complementary rather than substitutable — a local–cloud ensemble could theoretically reach higher combined accuracy.

Language accuracy was 100% for both, validating the bilingual (EN/TH) routing in [[hotel_guardrails]].

The 34-second K01 latency for the local model is an outlier that inflates the local average significantly.

## Links

- [[hotel_guardrails]] — system under test
- [[Qwen3-max]] — cloud model
- [[Qwen3.5-Opus-9B]] — local model
- [[keyword-match-eval]] — evaluation methodology used
- Source: `docs/MODEL_EVAL_REPORT.md`
- Informs: thesis Chapter 5 (evaluation), Chapter 4 (architecture)
