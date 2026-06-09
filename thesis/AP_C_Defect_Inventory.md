# Appendix C — Defect Inventory & Applied Fixes

> Living catalogue of every defect class surfaced by the eval pipeline
> (Chapter 6) plus the fix applied and the verification evidence. One
> section per defect category from the taxonomy in §3.x.3.
>
> Status legend:
> - **OPEN**     — observed in baseline, no fix yet
> - **PATCHED**  — fix landed; awaiting post-fix backtest confirmation
> - **RESOLVED** — fix landed AND post-fix backtest confirms no recurrence

This appendix is the audit trail behind §6.x.5 (Fixes Applied) — the
fix→verification chain in this document is the evidence that the
post-fix metrics in §6.x.4 were earned by the patches, not by chance.

---

## C.1 RAG drift — stale knowledge-base prices vs live database

**Defect category:** `rag_drift`
**First observed:** 2026-06-09, baseline canary + manual trilingual probe
**Severity:** Critical (revenue-affecting — guest is quoted X by RAG and charged Y by booking system)
**Status:** PATCHED → pending post-fix re-test

### Example failure (baseline)

| Question | Bot response (RAG-grounded) | Live DB price | Drift |
|---|---|---:|---|
| "How much is a Deluxe Room?" | 3,500 THB/night | **4,500 THB** | −22% |
| "How much is a Suite?" | 5,500 THB/night | **8,500 THB** | −35% |
| "How much is a Penthouse?" | 15,000 THB/night | **25,000 THB** | −40% |

### Root cause

`data/hotel/room_types.md` hardcoded each room's price as `**Price:** 3,500 THB per night`.  When the DB `room_types.base_price` column was updated in production, no one resynced the Markdown KB. RAG returns the markdown text verbatim; the LLM relays the stale number. Booking writes the correct number from the DB column. Two sources of truth → silent divergence → quoted X, charged Y.

### Detection — pre-fix

```
$ DATABASE_URL=postgresql://hotel_app:...@localhost:5433/hotel \
    python scripts/audit_data_db_drift.py

ROOM PRICE DRIFT (6 mismatches):
  Item                      DB        MD     Delta  Source
  Deluxe Room            4,500     3,500    -22.2%  data/hotel/room_types.md:36
  Suite                  8,500     5,500    -35.3%  data/hotel/room_types.md:53
  Penthouse             25,000    15,000    -40.0%  data/hotel/room_types.md:70
  Deluxe Room            4,500     3,500    -22.2%  data/hotel/room_types.md:91
  Suite                  8,500     5,500    -35.3%  data/hotel/room_types.md:92
  Penthouse             25,000    15,000    -40.0%  data/hotel/room_types.md:93
```

### Fix applied (commit `<sha>`)

1. Stripped every `**Price:** ... THB` line from `data/hotel/room_types.md`. Replaced with directive: `**Price:** Quote via calculate_dynamic_price tool / ขอราคาจากเครื่องมือจองห้อง`.
2. Dropped the Price column from the room comparison table.
3. Added top-of-file pricing note instructing the LLM (via RAG context) to defer pricing answers to the `calculate_dynamic_price` tool.
4. Re-ingested the Qdrant `hotel_knowledge` collection (`python scripts/ingest_hotel_knowledge.py`). Points went from 10 (whole-doc chunks) → ~50 (per-section chunks).

### Verification — post-fix

- [ ] `python scripts/audit_data_db_drift.py` → exit 0
- [ ] Live `/chat` "How much is a Deluxe Room from July 15 to July 17?" → 4,500 THB base mentioned, with Early Bird 15% off applied; no `3,500` anywhere in the response
- [ ] Eval pricing-template rows (12 EN + 12 TH + 12 CN) all `verdict=correct`
- [ ] Backtest post-fix run shows `rag_drift` count = 0

---

## C.2 RAG retrieval miss — WiFi password buried inside whole-doc chunk

**Defect category:** `rag_miss`
**First observed:** 2026-06-09, canary EN/TH/CN "What is the WiFi password?"
**Severity:** High (degrades guest experience, easily reproducible)
**Status:** PATCHED → pending post-fix re-test

### Example failure (baseline)

| Question | Bot response | Expected |
|---|---|---|
| "What is the WiFi password?" (EN) | "I don't have access to that info — contact the front desk." | `HOTEL2024GUEST` |
| "รหัส WiFi คืออะไรครับ" (TH) | "ไม่มีข้อมูล กรุณาติดต่อแผนกต้อนรับ" | `HOTEL2024GUEST` |
| "WiFi 密码是什么？" (CN) | "请联系前台获取 WiFi 密码" | `HOTEL2024GUEST` |
| "What is the hotel address?" (EN) | "I don't have that information." | 123 Sukhumvit Road, Khlong Toei |

### Root cause

`RecursiveCharacterTextSplitter` configured with `chunk_size ≈ 26,212 chars` made each `data/hotel/*.md` file a single whole-document chunk. `data/hotel/facilities_amenities.md` is ~4 KB → whole file = 1 chunk including pool / gym / business-centre / WiFi / concierge / parking sections. The WiFi password sits at line 89, ~80 lines into the chunk. Top-3 retrieval (`num_docs=3` at `src/agent/hotel_tools.py:882`) + no reranker (`RERANKER_BACKEND=none`) means even when the right `.md` chunk is retrieved, the LLM's attention drops off well before the WiFi line. The Q "What time is breakfast?" works because the time pattern (`6:30 AM - 10:30 AM`) is high-saliency and near the H2 header; the Q "What is the WiFi password?" gets a different, lower-saliency token buried in mid-chunk.

### Fix applied (commit `<sha>`)

1. `src/retrievers/hotel_knowledge/chains.py:109-131`: replaced the token-derived `chunk_size = token_limit * 0.8 * 4` (= 26,212) with env-overridable `chunk_size = int(os.getenv("CHUNK_SIZE_CHARS", "2000"))` and `chunk_overlap = int(os.getenv("CHUNK_OVERLAP_CHARS", "200"))`.
2. `src/agent/hotel_tools.py:882`: `num_docs=3 → 5`.
3. Re-ingest: `python scripts/ingest_hotel_knowledge.py`. Collection grows from 10 → ~50 points; each H2 section becomes its own searchable chunk.

### Verification — post-fix

- [ ] Canary run: 15/15 pass (was 11/15)
- [ ] `eval/dataset/canaries.jsonl` rows `canary_wifi_password_{en,th,cn}` and `canary_hotel_address_en` all return `verdict=correct`
- [ ] Backtest post-fix shows `rag_miss` defect count drops substantially (>50%) vs baseline

---

## C.3 Tool not called — dynamic pricing path unreached on routing

**Defect category:** `tool_not_called`
**First observed:** 2026-06-08, manual trilingual pricing test
**Severity:** Medium (correctness affected only for date-specific pricing queries)
**Status:** PATCHED → pending post-fix re-test

### Example failure (baseline)

```
User: "How much is a Standard Room from July 15 to July 17, 2026?"
Bot:  "Standard Room is 2,500 THB per night × 2 nights = 5,000 THB."

Expected (today = 2026-06-09, check-in 36 days out → Early Bird 0.85x):
  2,125 THB/night × 2 nights = 4,250 THB
Actual tool_calls field in /chat envelope: []   (calculate_dynamic_price not invoked)
```

### Root cause

The primary router classifies *"How much is X room from date Y to date Z?"* as a **knowledge** query (matches `"how much"` / `"ราคา"` / `"价格"` lexical patterns in the routing system prompt). It dispatches to `hotel_knowledge` sub-agent, which has `search_hotel_knowledge` but NOT `calculate_dynamic_price` in its tool list. RAG returns the (now stale) rate-card text, and the LLM relays the base price without the date-aware discount.

### Fix applied (commit `<sha>`)

Added `_maybe_compute_pricing_context()` helper in `src/hotel_guardrails/hotel_langgraph.py` that pre-computes the dynamic price (using the live DB + `_calculate_dynamic_multiplier`) when the user's message contains both a room type and a parseable date, and injects it into `handle_knowledge`'s prompt as a `LIVE PRICING` block. Helper supports EN/TH/CN date formats and English / Thai / Chinese room-type aliases.

(Note: helper works correctly when invoked directly inside the container. Whether the routing actually reaches `handle_knowledge` for all pricing variants will be verified by the post-fix backtest — if `tool_not_called` rate stays high, a follow-up fix is to add the same helper to the booking sub-agent's prompt assembly.)

### Verification — post-fix

- [ ] 12 EN + 12 TH + 12 CN pricing cases (`pricing_*_{en,th,cn}`) all return verdicts containing the correct Early Bird / Last-Minute total
- [ ] No regression on facility/dining domains (chunk-size change side-effect check)

---

## C.4 (template — populate from baseline) — Other defects

Add a section for each category surfaced in the baseline run that we haven't explicitly addressed:

- `room_conflation`
- `spec_wrong`
- `incomplete`
- `tool_error`
- `language_leak` (regression of §5.14.7?)
- `tool_call_leak` (regression of §5.14.2?)
- `particle_mismatch`
- `wrong_routing`
- `empty_response`
- `format_error`
- `over_refuse` (separate from rag_miss when the bot refuses even with the info present)

Each follows the same template:

```
**Defect category:** <tag>
**First observed:** YYYY-MM-DD, run id <run_dir>, case id <case_id>
**Severity:** Critical | High | Medium | Low
**Status:** OPEN | PATCHED | RESOLVED

### Example failure
[case id, question, response, expected]

### Root cause
[one paragraph]

### Fix applied (commit <sha>)
[bulleted change-list]

### Verification — post-fix
[checklist of evidence: audit exit code, eval row verdict, sample pass-rate delta]
```

---

## C.X Closing summary table

To be populated after Phase 6 strategic backtest:

| Defect | Baseline count | Post-fix count | Δ | Status |
|---|---:|---:|---:|---|
| `rag_drift` | ? | ? | ? | ? |
| `rag_miss` | ? | ? | ? | ? |
| `tool_not_called` | ? | ? | ? | ? |
| ... | | | | |

This table is the single sentence the reader takes away from Chapter 6: how many defects we found, how many remain, and which fixes mattered most.
