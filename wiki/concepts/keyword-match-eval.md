---
type: concept
status: developing
tags: [concept, evaluation, methodology, hotel-ai]
created: 2026-04-19
updated: 2026-04-19
related: [LLM-as-judge-evaluation, hotel_guardrails]
---

# Keyword-Match Evaluation (Hotel Assistant Eval Methodology)

The evaluation methodology used in [[model-eval-local-vs-cloud-2026-04-06]] and [[model-tuning-and-test-results-2026-04-03]] for the Grand Horizon Hotel assistant. A lightweight, deterministic alternative to LLM-as-judge scoring.

## How It Works

Each test case specifies:
- **Input:** the user message (EN or TH)
- **Expected:** a plain-text description of the required response content
- **Keywords:** a list of required terms/phrases that must appear in the response
- **Language:** the required response language (EN or TH)

Scoring per case:
- `keyword_score = matched_keywords / total_keywords`
- `lang_ok = True/False` (language detection against expected language)
- `pass = (keyword_score >= threshold) AND lang_ok AND no_timeout`

## Metrics Produced

| Metric | Definition |
|--------|------------|
| Overall accuracy | Cases where pass=True / total cases |
| Keyword accuracy | Average keyword_score across cases |
| Language accuracy | Cases where lang_ok=True / total |
| Avg latency | Mean response time (ms) |
| p50 / p95 latency | Percentile latencies |
| Cohen's κ | Inter-model agreement beyond chance |

## Strengths

- Deterministic and reproducible — same run produces same scores
- No LLM dependency in the evaluation loop
- Language check is a strong proxy for bilingual routing correctness
- Fast to run (no extra API calls)

## Limitations

- Keyword matching does not capture semantic correctness or politeness
- Does not evaluate factual accuracy of non-keyword content
- κ = 0.000 in the Apr-06 run reveals models fail on *different* cases — a single threshold may mask complementary strengths
- Does not penalize verbose or hallucinated content that happens to include the keywords
- No multi-turn context evaluation — each case is a single turn

## Relation to Other Eval Approaches

The project also has a DeepEval harness (`scripts/eval/run_deepeval.py`) which likely provides semantic/LLM-as-judge scoring. The keyword-match method is complementary: cheap for regression testing, DeepEval for deeper quality assessment.

## Implementation

- Harness: `scripts/eval/run_evaluation.py` (inferred)
- Infrastructure suite: `pytest` (193 cases, 100% pass, auth + DB + scaling)
- Test data: hardcoded in eval script or a companion YAML/JSON file (not yet ingested)

## Links

- [[model-eval-local-vs-cloud-2026-04-06]]
- [[model-tuning-and-test-results-2026-04-03]]
- [[hotel_guardrails]] — system under test
