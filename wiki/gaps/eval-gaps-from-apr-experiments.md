---
type: gap
priority: medium
blocking: [thesis Chapter 5, model selection decision]
tags: [gap, eval, model-comparison, minimax]
created: 2026-04-19
updated: 2026-04-19
---

# Gaps: Open Questions from April 2026 Evaluation Experiments

Gaps surfaced by [[model-eval-local-vs-cloud-2026-04-06]] and [[model-tuning-and-test-results-2026-04-03]].

## GAP-1: MiniMax M2.7 Multi-Turn Context Not Validated

**Question:** Does [[MiniMax-M2.7]] maintain context across 5+ turns in a Thai booking conversation?

**Why it matters:** Multi-turn context retention is critical for production hotel assistant quality. [[Qwen3-max]] and [[Qwen3.5-Opus-9B]] were both validated on a 5-turn Thai booking flow. MiniMax was only tested on single-turn queries.

**Resolution path:** Run the same 5-turn Thai booking test against `minimax/minimax-m2.7` via the `PUT /settings/llm` runtime switch.

---

## GAP-2: Cohen's κ = 0.000 — Ensemble Potential Unexplored

**Question:** If the two models fail on *different* cases (κ = 0.000), would a local–cloud ensemble (e.g., majority vote or cascade) achieve >100% single-model accuracy? What is the theoretical maximum?

**Why it matters:** Could justify a hybrid routing strategy for cost-sensitive deployments.

**Resolution path:** Manual review of the 2 disagreements (G03, E03). Analyze whether a rule-based cascade (try local, escalate to cloud on low confidence) can close the gap.

---

## GAP-3: Two Remaining Test Failures (C22, E28) Unresolved

**Question:** Why did the agent fail to call the cancel tool in C22, and why did it route E28 to `hotel_knowledge` instead of `get_hotel_services`?

**Why it matters:** These failures indicate routing or tool-selection gaps that would affect production users.

- **C22 (cancel):** Agent checked DB, found nothing, but didn't call cancel tool. Possibly a routing prompt issue or a missing confirmation step.
- **E28 (services list):** "What services does the hotel offer?" routes to RAG knowledge rather than the structured `get_hotel_services` tool — likely an intent classification boundary problem.

**Resolution path:** Add explicit routing examples for these intents in the LangGraph routing prompt; re-run tests.

---

## GAP-4: Keyword-Match Eval Does Not Capture Factual Accuracy

**Question:** The eval passes cases where keywords appear but does not verify the *correctness* of surrounding content. Are there cases where correct keywords appear in an otherwise wrong or hallucinated response?

**Why it matters:** Thesis Chapter 5 needs to claim valid evaluation methodology. If DeepEval or human review reveals hallucinated content that passed keyword checks, the accuracy figures overstate quality.

**Resolution path:** Cross-validate a sample of PASS cases with the DeepEval harness (`scripts/eval/run_deepeval.py`). Document results.

---

## GAP-5: Infrastructure Tests Not Linked to Commit Hash

**Question:** The 193/193 infrastructure test run (2026-04-06 16:24) is not pinned to a specific commit or deployment version.

**Why it matters:** Reproducibility for thesis appendix.

**Resolution path:** Re-run with `git rev-parse HEAD` recorded in test output.
