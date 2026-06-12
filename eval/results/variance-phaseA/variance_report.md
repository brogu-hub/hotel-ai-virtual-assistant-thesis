# Phase F variance baseline — `variance-phaseA`

_Generated: 2026-06-11T13:12:29+00:00_

## Configuration

- Runs            : **5**
- Sample size     : `--sample-iteration 100` (pinned seed `42`)
- Judge model     : `deepseek/deepseek-chat-v3.1`
- Chat timeout    : 180.0s
- Max chat parallel: 2 (recorded only; backtest_runner is single-threaded)
- Endpoint        : `http://localhost:8088`

Same stratified sample is replayed for every run; the only source of
variance is chatbot stochasticity (temperature 0.3, top_p 0.8). The judge
is held at temperature 0.0.

## Headline

| Metric | Mean | StdDev | 95% CI |
|---|---|---|---|
| Strict pass rate | 80.83% | 1.58 pp | [78.87%, 82.79%] |
| Weighted pass rate (partial=0.5) | 83.23% | 1.45 pp | [81.43%, 85.02%] |

### Interpretation

- Observed strict-pass stddev across 5 runs: **1.58 pp**.
- Rule of thumb: an observed delta between two configs must exceed
  ~2 sigma (~3.2 pp) before it is unlikely to be noise.
- The ~5 pp gap between iter1b / iter1c / tier1c and iter3 should be
  compared against this baseline before any causal claim is made.

## Per-run results

| Run | Source | Rows | Strict pass | Weighted pass |
|---|---|---|---|---|
| 1 | `eval/results/variance-phaseA-run-1/20260611T120335` | 96 | 79.17% | 81.77% |
| 2 | `eval/results/variance-phaseA-run-2/20260611T124339` | 96 | 82.29% | 84.90% |
| 3 | `eval/results/variance-phaseA-run-3/20260611T125159` | 96 | 82.29% | 84.38% |
| 4 | `eval/results/variance-phaseA-run-4/20260611T125902` | 96 | 79.17% | 81.77% |
| 5 | `eval/results/variance-phaseA-run-5/20260611T130537` | 96 | 81.25% | 83.33% |

## Per-defect category — mean and stddev (counts per run)

| Defect | Mean / run | StdDev | Min | Max |
|---|---|---|---|---|
| empty_response | 1.60 | 0.89 | 1 | 3 |
| hallucination | 10.20 | 1.79 | 9 | 13 |
| incomplete | 9.20 | 0.84 | 8 | 10 |
| over_refuse | 3.20 | 0.45 | 3 | 4 |
| rag_drift | 0.20 | 0.45 | 0 | 1 |
| rag_miss | 2.40 | 0.55 | 2 | 3 |
| spec_wrong | 6.40 | 1.14 | 5 | 8 |
| tool_not_called | 1.00 | 0.00 | 1 | 1 |
| wrong_routing | 0.20 | 0.45 | 0 | 1 |

## Source runs

- run 1: `eval/results/variance-phaseA-run-1/20260611T120335` (96 rows)
- run 2: `eval/results/variance-phaseA-run-2/20260611T124339` (96 rows)
- run 3: `eval/results/variance-phaseA-run-3/20260611T125159` (96 rows)
- run 4: `eval/results/variance-phaseA-run-4/20260611T125902` (96 rows)
- run 5: `eval/results/variance-phaseA-run-5/20260611T130537` (96 rows)
