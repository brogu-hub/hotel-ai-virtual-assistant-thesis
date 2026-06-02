---
type: concept
status: implemented
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/hotel_langgraph.py
  - docs/plans/postgres_store_and_saver_memory.md
  - scripts/test_4_subagents.py
tags: [concept, memory, thai, bilingual, extraction, localisation]
---

# Bilingual Memory Extraction (Thai + English)

## Overview

The hotel assistant serves guests communicating in both Thai and English. A memory extraction system that only recognised English preference keywords would miss the majority of statements made by Thai-language guests. The implementation therefore maintains **two parallel keyword tables** — `_PREF_KEYWORDS_EN` and `_PREF_KEYWORDS_TH` — and scans both on every user message regardless of detected language.

> [!note]
> **Why this matters for a Thai-market hotel:** The Grand Horizon Hotel is set in Thailand. Guests stating dietary restrictions, floor preferences, or allergy information in Thai are as likely to be returning guests who want personalised service as guests stating the same in English. Ignoring Thai-language preferences would create a systematically worse experience for the primary market.

## Implementation Detail

The `_extract_prefs_from_text()` function in `hotel_langgraph.py` performs **two independent scans**:

1. English: lowercased substring match — `kw in lower` — so `high floor` matches "I prefer a high floor please".
2. Thai: direct substring match on the original text (not lowercased, as Thai has no case) — `kw in text` — so `ชั้นสูง` matches "ฝากจำไว้ด้วยนะครับ ผมชอบห้องเงียบและอยู่ชั้นสูง".

Both scans run on every message regardless of which language is dominant; a mixed-language message like "I want a king bed, ไม่มีถั่วนะครับ" will correctly extract both `bed=king` (English path) and `allergy=peanuts` (Thai path for `แพ้ถั่ว` — though in this mixed example the Thai phrase for peanut allergy would need to be present, not merely implied).

## Thai Keyword Coverage

| Thai keyword | English equivalent | Memory field |
|---|---|---|
| `ชั้นสูง` | high floor | `preferences.floor = "high"` |
| `ชั้นต่ำ` | low floor | `preferences.floor = "low"` |
| `ห้องเงียบ` | quiet room | `preferences.quiet = True` |
| `แพ้ถั่ว` | peanut allergy | `preferences.allergy = "peanuts"` |
| `มังสวิรัติ` | vegetarian | `preferences.diet = "vegetarian"` |
| `ฮาลาล` | halal | `preferences.diet = "halal"` |
| `เตียงคิง` | king bed | `preferences.bed = "king"` |
| `หมอนเพิ่ม` | extra pillows | `preferences.pillows = "extra"` |

The Thai coverage is slightly smaller than the English table (no `vegan`, no `twin bed` equivalent) — this is a current gap identified during implementation.

## Test Coverage for Thai Extraction

The memory test suite in `scripts/test_4_subagents.py` (Section 3 of the memory category) specifically validates Thai extraction across three users:

- `mem-test-user-F-TH` — seeds `ห้องเงียบ` (quiet) + `ชั้นสูง` (high floor) in Thai; recalls in a new session asserting `เงียบ` and `สูง` appear.
- `mem-test-user-G-TH` — seeds `มังสวิรัติ` (vegetarian) in Thai; recalls as restaurant recommendation tailored to vegetarian preferences.
- `mem-test-user-H-TH` — seeds `แพ้ถั่ว` (peanut allergy) in Thai; recalls via an English question ("What allergy do I have on file?"), accepting `peanut`, `ถั่ว`, `แพ้`, or `allergy` in response.

The last case (cross-language recall: seeded in Thai, recalled in English) is a non-trivial test: the memory preamble is inserted in English ("Known about this guest: prefers allergy=peanuts") and the LLM must bridge the representation to the guest's question language.

> [!note]
> The test for `mem-test-user-H-TH` uses a broad accept list (`["peanut", "ถั่ว", "แพ้", "allergy"]`) because the model may respond in either language depending on its language-detection heuristic for short English questions asked after a Thai-language seeding session.

## Gaps and Future Work

1. **Thai `vegan`:** No keyword for `วีแกน` or similar Thai spellings of vegan. Currently a guest stating "ผมทานวีแกน" would not be stored as vegan (only `มังสวิรัติ` / vegetarian is covered).
2. **Thai `twin bed`:** No keyword for `เตียงคู่` or `เตียงทวิน`.
3. **Negation:** Neither the English nor Thai extractor handles negation. "ไม่ชอบชั้นสูง" (don't like high floors) would currently not be stored at all (the keyword `ชั้นสูง` is absent), but "ไม่ต้องการเตียงคิง" would incorrectly store `bed=king` if `เตียงคิง` appeared even in a negated context.
4. **Fuzzy / inflected Thai:** Thai does not use spaces between all words, so compound forms or slightly different phrasing might miss the exact substring match.

## Related

- [[concepts/rule_based_memory_write_back]] — the broader extraction mechanism
- [[concepts/dual_plane_memory]] — where extracted facts are stored
- [[experiments/memory-test-suite-2026-04-20]] — the 27-case test suite including Thai coverage
