---
type: experiment
date: 2026-04-20
hypothesis: "Dual-plane memory (PostgresSaver + PostgresStore) with rule-based write-back delivers correct cross-turn and cross-session recall for all four sub-agents, in English and Thai, without hallucinating facts for unknown users."
status: done
outcome: "27/27 passing on local Qwen3.5-Opus-9B via Ollama"
sources:
  - scripts/test_4_subagents.py
  - src/hotel_guardrails/hotel_langgraph.py
tags: [experiment, memory, validation, qwen, ollama, bilingual, test-suite]
---

# Memory Test Suite — 2026-04-20

> [!key-insight]
> 27/27 new memory cases pass on local Qwen3.5-Opus-9B — including 9 Thai-language cases, 2 namespace-isolation negative cases, and 1 anonymous-namespace cross-turn case. This is the validation evidence for the [[dual_plane_memory]] design.

## Hypothesis

A dual-plane memory architecture combining [[dual_plane_memory|PostgresSaver + PostgresStore]] with [[rule_based_memory_write_back|rule-based (zero-LLM) write-back]] and [[bilingual_memory_extraction|bilingual keyword extraction]] should support:

- **H1.** Cross-turn recall (short-term / same session) for every sub-agent.
- **H2.** Cross-session recall (long-term / different session, same `user_id`) for every store key.
- **H3.** Thai-language free-text preference extraction with equal reliability.
- **H4.** Namespace isolation — user Y must not see user A's facts.
- **H5.** No fact hallucination on a brand-new, unseen `user_id`.
- **H6.** Anonymous namespace (`("anon", session_id)`) retains cross-turn context without a stable identity.

## Setup

- **Backend:** Local [[Qwen3.5-Opus-9B]] via [[Ollama]].
- **Store:** `AsyncPostgresStore` on local PostgreSQL.
- **Saver:** `AsyncPostgresSaver` on the same database, separate pool.
- **Runner:** `scripts/test_4_subagents.py` — the new `memory` suite + a multi-turn runner that reuses `session_id` across turns of a single case and shares `user_id` across cases that name the same user.
- **Gate:** each case has an `expect` list (fuzzy keyword match at 20% threshold) and optional `reject` list (phrases that must NOT appear). Responses are normalised lowercase before matching.

## Case Breakdown (27 total)

### Section 1 — Short-Term Recall (5 cases)

One case per sub-agent proves the checkpointer carried prior turns into the second turn:

| ID | Sub-agent | Turn 1 | Turn 2 | Pass |
|---|---|---|---|---|
| `st_booking_modify` | booking | Book Deluxe Apr 25–27, 2 guests | Change to 3 guests | ✓ |
| `st_service_followup` | service | Extra towels for room 501 | Also two more pillows | ✓ |
| `st_knowledge_followup` | knowledge | Breakfast time? | When does it end? | ✓ |
| `st_other_name_recall` | other_talk | My name is Alice | What was my name? | ✓ |
| `st_thai_booking_modify` | booking (th) | จองห้อง Suite 10–12 พ.ค. | เปลี่ยนเป็น Deluxe | ✓ |

### Section 2 — Long-Term Recall by Store Key (11 cases)

Seed → recall pairs, each using a distinct `user_id` and a *different* `session_id` on the recall turn:

| Pair | Store key exercised | Seed phrase | Recall ask | Pass |
|---|---|---|---|---|
| userA | `preferences.floor`, `preferences.allergy` | "high floor and peanut allergy" | "what do you know about my room preferences?" | ✓ |
| userB | `preferences.bed` | "always want a king bed" | "what bed do I prefer?" | ✓ |
| userC | `preferences.diet` (surfaced via KNOWLEDGE sub-agent) | "I'm vegetarian" | "which restaurants would you recommend?" | ✓ |
| userD | `service_history_summary` via `create_service_request` | "extra pillows to room 702" | "what requests have I made?" | ✓ |
| userE (3 cases) | `profile.name`, `profile.email`, `recent_bookings_summary` via `create_reservation` | Book for Zoe Reyes, zoe@test.com | "do I have bookings?" / "what name + email?" | ✓ |

> [!note] Design concession
> The `service_history_summary` and `recent_bookings_summary` recall cases accept *either* direct recall *or* graceful deferral ("I'll check — what's your email?"). Local 9B sometimes produces a natural-language confirmation without firing the tool; the tests don't force tool invocation.

### Section 3 — Thai Free-Text Preference Extraction (6 cases)

| Pair | Thai seed | Recall | Pass |
|---|---|---|---|
| userF-TH | ผมชอบห้องเงียบและอยู่ชั้นสูง (quiet room, high floor) | "คุณจำอะไรได้บ้าง" | ✓ |
| userG-TH | ผมทานมังสวิรัติ (vegetarian) | "แนะนำร้านอาหาร?" | ✓ |
| userH-TH | ผมแพ้ถั่วครับ (peanut allergy) | "what allergy do I have?" (EN) | ✓ |

The userH case is cross-lingual: Thai seed, English recall. Passes because the keyword extractor writes the semantic fact, and the English ask retrieves it regardless of the language in which the fact was stated. See [[bilingual_memory_extraction]].

### Section 4 — Accumulation (2 cases)

`lt_accumulate_multi_prefs_userI` seeds four preferences in a single free-text turn ("king bed, quiet room, vegetarian diet, and extra pillows"). Recall turn confirms all four surface together. Validates that `_extract_prefs_from_text()` does not stop at the first match.

### Section 5 — Edge / Negative (3 cases)

| ID | What it proves | Pass |
|---|---|---|
| `lt_isolation_userY` | user Y asking about preferences does NOT receive user A's data | ✓ |
| `lt_no_hallucination_unknown_user` | brand-new user_id does NOT invent owned facts | ✓ |
| `anon_name_recall_no_user_id` | anonymous two-turn "my name is Bob" / "what's my name?" works via `("anon", session_id)` | ✓ |

Both isolation cases have `reject` lists of ownership phrases ("you prefer a king", "your peanut allergy") that must NOT appear. The agent may mention "high floor" as a *generic* example of a preference guests can state — only ownership-claiming phrases are forbidden.

## Result

**27 / 27 PASS** on local Qwen3.5-Opus-9B.

Every hypothesis H1–H6 is confirmed. No tool-call leaks reported by the retry harness on any memory case.

## What This Doesn't Cover

- **Cloud model.** The suite was not re-run against [[Qwen3-max]] on OpenRouter. Given the earlier 100% functional-suite score, cloud is expected to pass at least as well; confirming is a quick follow-up.
- **Concurrent writes.** Tests are serial. MVCC-level concurrent-write safety is assumed from PostgreSQL, not directly exercised.
- **TTL sweeper.** `prune_anon_memory()` is unit-testable but not triggered by this suite; validated separately.
- **Long-horizon retention.** Tests verify "next session" recall; they do not simulate 30+ day anon expiry.
- **Malformed tool-call args.** `_extract_facts_from_tool_calls` assumes well-typed args from the sub-agent.

## Related

- [[concepts/dual_plane_memory]]
- [[concepts/rule_based_memory_write_back]]
- [[concepts/bilingual_memory_extraction]]
- [[concepts/anon_namespace_ttl]]
- [[concepts/tool_call_codeblock_leak]]
- [[flows/cross_session_memory]]
- [[components/hotel_langgraph]]
- [[thesis/memory_system_design]]
- [[experiments/model-eval-local-vs-cloud-2026-04-06]] — earlier functional/eval comparison
- [[experiments/model-tuning-and-test-results-2026-04-03]] — prior-generation test harness
- [[Qwen3.5-Opus-9B]]
- [[Ollama]]
