---
type: concept
status: implemented
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/hotel_langgraph.py
  - docs/plans/postgres_store_and_saver_memory.md
tags: [concept, memory, rule-based, extraction, write-back, no-llm]
---

# Rule-Based Memory Write-Back

## Definition

Rule-based memory write-back is the mechanism by which the hotel assistant populates its long-term [[concepts/dual_plane_memory|guest memory store]] without invoking any additional LLM call. Every fact stored in `PostgresStore` is derived either from keyword pattern matching against the user's free text or from the structured arguments of already-executed tool calls.

> [!note]
> **Design decision (locked):** The plan document explicitly chose rule-based extraction over an LLM summariser for v1. The motivation is three-fold: zero added per-turn latency, zero additional API cost, and deterministic behaviour — the same user input always produces the same stored facts.

## Two Write Paths

### Path 1 — Free-Text Preference Extraction (`_extract_prefs_from_text`)

Called at the start of every sub-agent handler and at the primary router level, before the LLM is invoked. It scans the last `HumanMessage` text against two static keyword tables.

**English patterns (`_PREF_KEYWORDS_EN`):**

| Keyword | Stored key | Stored value |
|---|---|---|
| `high floor` | `preferences.floor` | `"high"` |
| `low floor` | `preferences.floor` | `"low"` |
| `quiet room` | `preferences.quiet` | `True` |
| `no peanuts` | `preferences.allergy` | `"peanuts"` |
| `peanut allergy` | `preferences.allergy` | `"peanuts"` |
| `vegetarian` | `preferences.diet` | `"vegetarian"` |
| `vegan` | `preferences.diet` | `"vegan"` |
| `halal` | `preferences.diet` | `"halal"` |
| `king bed` | `preferences.bed` | `"king"` |
| `twin bed` | `preferences.bed` | `"twin"` |
| `extra pillows` | `preferences.pillows` | `"extra"` |

**Thai patterns (`_PREF_KEYWORDS_TH`):**

| Keyword | Stored key | Stored value |
|---|---|---|
| `ชั้นสูง` | `preferences.floor` | `"high"` |
| `ชั้นต่ำ` | `preferences.floor` | `"low"` |
| `ห้องเงียบ` | `preferences.quiet` | `True` |
| `แพ้ถั่ว` | `preferences.allergy` | `"peanuts"` |
| `มังสวิรัติ` | `preferences.diet` | `"vegetarian"` |
| `ฮาลาล` | `preferences.diet` | `"halal"` |
| `เตียงคิง` | `preferences.bed` | `"king"` |
| `หมอนเพิ่ม` | `preferences.pillows` | `"extra"` |

The function **merges** into the existing preferences dict (read-then-update), so adding `king bed` to a guest who already has `peanut allergy` stored does not overwrite the allergy.

**Coverage note:** All 4 sub-agent handlers (`handle_booking`, `handle_service`, `handle_knowledge`, `handle_other_talk`) **and** the `HotelAssistant` primary router call `_extract_prefs_from_text`. This ensures preferences are captured even when the local 9B model answers directly at the router level instead of dispatching to a sub-agent.

### Path 2 — Tool-Call Write-Back (`_extract_facts_from_tool_calls`)

Called after the sub-agent's LLM invocation returns an `AIMessage`, before the function returns. It inspects the `tool_calls` attribute of the `AIMessage` and upserts structured facts.

**`create_reservation` args extracted:**

| Arg | Stored key | Notes |
|---|---|---|
| `guest_email` | `profile.email` | Only if provided |
| `guest_name` | `profile.name` | Only if provided |
| `room_type` + `check_in_date` + `check_out_date` + `num_guests` | `recent_bookings_summary` | Appended as dict; last 10 kept |

**`create_service_request` args extracted:**

| Arg | Stored key | Notes |
|---|---|---|
| `service_type` or `request_type` | `service_history_summary` | Appended as string; last 10, deduplicated |

**`get_reservation_details` / `get_guest_reservations` args extracted:**

| Arg | Stored key | Notes |
|---|---|---|
| `guest_email` | `profile.email` | Only if no email already stored |

## Why Rule-Based Over LLM Summarisation

The plan document evaluated three alternatives for v1:

1. **LLM summariser** — one LLM call per turn to extract facts from the full conversation. Cost: ~$0.001–0.01 per turn on OpenRouter, additive latency of 1–3 s for cloud, longer for local 9B. Also non-deterministic.
2. **Vector-embedding memory** (e.g. [[entities/Mem0]]) — encodes memories as embeddings and retrieves by semantic similarity. High expressiveness, high complexity, external dependency.
3. **Rule-based extraction (selected)** — zero extra calls, deterministic, auditable, easily extended by adding entries to the keyword tables.

The locked decision is to remain rule-based in v1 and revisit LLM summarisation in a future version once the baseline is validated.

## Limitations

- Only pre-defined preference categories are captured. Free-form facts like "prefers the east wing" are not stored.
- No negation handling: "I do NOT want a king bed" currently stores `bed=king` if the string `king bed` appears. A future version should add negation detection.
- Tool-call write-back only fires when the sub-agent actually invokes the tool; the local 9B sometimes confirms in free text without executing the tool, in which case no write-back occurs.

## Related

- [[concepts/bilingual_memory_extraction]] — language-specific keyword sets
- [[concepts/dual_plane_memory]] — where the extracted facts are stored
- [[components/memory_preamble_injector]] — how stored facts are re-injected
- [[flows/cross_session_memory]] — full end-to-end flow
