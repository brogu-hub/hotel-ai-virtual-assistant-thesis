---
type: experiment
status: done
date: 2026-04-03
hypothesis: "Six identified bugs (passive booking prompt, RAG context ordering, multi-turn history duplication, missing guest auto-register, schema mismatch, Thai encoding) are the root causes of test failures; fixing them will bring the agent to ≥90% pass rate on a 34-case functional test suite."
metric: "Pass rate across 34 test cases (Parts A–F); per-part pass counts; multi-turn context retention (5-turn Thai booking)"
outcome: "32/34 (94%) pass rate achieved after all fixes. Part B (RAG/Knowledge) went from 3/6 to 6/6 after restructuring knowledge context injection. Multi-turn 5-turn Thai booking now works end-to-end."
tags: [experiment, tuning, debugging, model-comparison, qwen, ollama, openrouter, minimax]
created: 2026-04-19
updated: 2026-04-19
---

# Experiment: Agent Tuning & Functional Test Suite (2026-04-03)

## Hypothesis

Six specific bugs in [[hotel_guardrails]] and [[hotel_langgraph]] were causing failures in the initial test run. Resolving each bug sequentially will raise the functional pass rate to ≥90% on a 34-case suite covering infrastructure, RAG, booking, advanced scenarios, service requests, and edge cases.

## Setup

- **Code path:** `src/hotel_guardrails/hotel_langgraph.py`, `src/agent/hotel_tools.py`, `src/agent/hotel_prompt.yaml`, `src/hotel_guardrails/database.py`, `src/hotel_guardrails/config.py`
- **Primary test model:** `fredrezones55/qwen3.5-opus:9b` via Ollama (local)
- **Comparison models:** `qwen/qwen3-max` (OpenRouter), `minimax/minimax-m2.7` (OpenRouter)
- **Test runner:** direct Python `requests` calls (curl replaced due to Windows UTF-8 issue)
- **Test scope:** 34 cases across 6 parts (A: infra, B: RAG, C: booking, D: advanced, E: service, F: edge)
- **Parameters after tuning:** temperature=0.3, max_tokens=2048, thinking=on for all main models

## Models Compared

| Model | Backend | Cost (in/out per 1M tokens) |
|-------|---------|---------------------------|
| qwen3.5-opus:9b | Ollama (local) | Free |
| qwen/qwen3-max | OpenRouter | $0.78 / $3.90 |
| minimax/minimax-m2.7 | OpenRouter | $0.30 / $1.20 |

## Procedure

1. Run initial test suite — identify failure cases.
2. Diagnose root cause for each failure cluster.
3. Apply targeted code fix.
4. Re-run affected tests to confirm pass.
5. Run full suite for final score.

## Results

### Final Pass Rate: 32/34 (94%)

| Part | Description | Passed | Total | Pass Rate |
|------|-------------|--------|-------|-----------|
| A | Infrastructure | 7 | 7 | 100% |
| B | Knowledge / RAG | 6 | 6 | 100% |
| C | Booking workflow | 9 | 10 | 90% |
| D | Advanced scenarios | 4 | 4 | 100% |
| E | Service requests | 3 | 4 | 75% |
| F | Edge cases | 3 | 3 | 100% |

### Failures

| Test | Description | Root cause |
|------|-------------|------------|
| C22 | Cancel reservation | Agent didn't call cancel tool in that turn |
| E28 | Hotel services list | Routed to `hotel_knowledge` instead of `get_hotel_services` tool |

### Head-to-Head Model Comparison

#### Thai Breakfast Query

| Model | Result | Time | Notes |
|-------|--------|------|-------|
| qwen3.5-opus:9b (Ollama) | PASS | ~15s | Correct hours, location, menu details |
| qwen/qwen3-max | PASS | 32s | Correct hours, 50+ menu items, dietary options |
| minimax/minimax-m2.7 | PASS | 39s | Correct hours, polite Thai response |

#### English Booking (one-shot with all info)

| Model | Result | Time | Notes |
|-------|--------|------|-------|
| qwen3.5-opus:9b (Ollama) | PASS | ~20s | Created reservation, HTL number returned |
| qwen/qwen3-max | PASS | 16s | One-shot booking, clean format |
| minimax/minimax-m2.7 | PASS | 33s | Created reservation, bilingual response |

#### Multi-Turn Thai Booking (5 turns)

| Model | Result | Turns | Total Time |
|-------|--------|-------|-----------|
| qwen/qwen3-max | PASS | 5/5 | ~72s |
| qwen3.5-opus:9b (Ollama) | PASS (after tuning) | 5/5 | ~90s |
| minimax/minimax-m2.7 | Not tested | — | — |

### Model Selection Verdict

| Metric | qwen3.5-opus:9b | qwen/qwen3-max | minimax-m2.7 |
|--------|-----------------|----------------|--------------|
| Speed | ~15–20s | ~12–32s | ~30–40s |
| Cost | Free (local GPU) | $0.78/$3.90/1M | $0.30/$1.20/1M |
| Thai quality | Good | Excellent | Good |
| Tool calling | Reliable (post-tuning) | Very reliable | Reliable |
| Multi-turn context | Works | Works | Not tested |
| Recommended use | Development | Production (default) | Budget production |

## Tuning Changes Applied

### Fix 1 — Passive Booking Prompt
- **File:** `src/agent/hotel_prompt.yaml` (`booking_flow` prompt)
- **Change:** Rewrote to be action-oriented: "Pick the FIRST available room automatically", "Don't ask for room numbers"
- **Effect:** Agent books on first try when all info is provided

### Fix 2 — RAG Context Ordering (B: 3/6 → 6/6)
- **File:** `src/hotel_guardrails/hotel_langgraph.py` (`handle_knowledge()`)
- **Change:** Moved knowledge context from `system(prompt + knowledge)` to a trailing system message after user messages; trimmed context to max 2,000 chars
- **Effect:** 9B model can now locate user question and answer it from context

### Fix 3 — Multi-Turn History Duplication
- **File:** `src/hotel_guardrails/hotel_langgraph.py` (`invoke_hotel_agent()`)
- **Change:** Changed to send only the new message; MemorySaver checkpointer handles full history
- **Effect:** 5-turn Thai booking conversation maintains context across all turns

### Fix 4 — Guest Auto-Registration
- **File:** `src/agent/hotel_tools.py` (`create_reservation()`)
- **Change:** Added auto-insert of guest row when email is new
- **Effect:** New guests can book with just an email — no prior registration required

### Fix 5 — Schema Mismatch (POST /guests 400 error)
- **File:** `src/hotel_guardrails/database.py` (`create_guest()`)
- **Change:** Removed non-existent columns (`id_type`, `date_of_birth`, `address`) from INSERT
- **Effect:** Guest registration API returns 200

### Fix 6 — Thai Encoding on Windows
- **Files:** test scripts
- **Change:** Added `sys.stdout.reconfigure(encoding='utf-8')`, replaced Unicode symbols with ASCII, switched from `curl` to Python `requests`
- **Effect:** All Thai-language tests pass correctly

### Fix 7 — Hardcoded Hotel Knowledge in Prompt
- **File:** `src/agent/hotel_prompt.yaml`
- **Change:** Removed 50-line hardcoded facility details block; replaced with instruction to use `search_hotel_knowledge` tool
- **Effect:** Hotel info now fully RAG-driven — update `data/hotel/*.md` and re-ingest to change facts

## Per-Model Optimization Presets

Auto-applied when switching via `PUT /settings/llm`:

| Model | Temperature | Max Tokens | Thinking |
|-------|-------------|------------|----------|
| qwen3.5-opus:9b | 0.3 | 2048 | On |
| qwen/qwen3-max | 0.3 | 2048 | On |
| qwen/qwen3.5-397b-a17b | 0.3 | 2048 | On |
| qwen/qwen3.5-flash | 0.3 | 1024 | Off |
| minimax/minimax-m2.7 | 0.3 | 2048 | On |

Pattern-based auto-detection for unknown models (implemented in `src/hotel_guardrails/config.py` → `get_model_presets()`).

## Conclusion

All six bugs were confirmed as root causes of observed failures. After fixes, the suite reached 94% (32/34). The two remaining failures (C22 cancel tool not called, E28 wrong routing to knowledge) are tool-selection issues that likely require further prompt engineering or routing rule updates — they are documented as open gaps.

The RAG context ordering fix (Fix 2) had the largest single impact: +3 cases in Part B. The multi-turn history fix (Fix 3) is critical for production quality but was hard to detect from single-turn tests.

[[MiniMax-M2.7]] is identified as a viable budget production option but lacks multi-turn test coverage — flagged as a gap.

## Links

- [[hotel_guardrails]] — primary system under test
- [[hotel_langgraph]] — core fixes applied here
- [[Qwen3-max]] — cloud production model
- [[Qwen3.5-Opus-9B]] — local dev model
- [[MiniMax-M2.7]] — third model evaluated
- [[keyword-match-eval]] — methodology
- Source: `docs/TEST_RESULTS.md`
- Informs: thesis Chapter 5 (evaluation), Chapter 3 (implementation)
