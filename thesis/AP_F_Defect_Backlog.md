# Appendix F — Defect Backlog (case-by-case fix tracker)

> Generated 2026-06-13 from the `clean_stackoff` Run #1 incorrects-triage
> workflow (`w3rdscaqk`, 19 agents) after the queue-artifact fix (§C.5)
> closed the eval contamination loop. The 17 cases below are the genuine
> defects + eval artifacts surfaced by the Stack-OFF baseline rerun (full
> 502 cases were planned but Run #1 was killed at 102/502 to apply
> rank-1/rank-2 patches before continuing).
>
> This file is the live backlog: rows track from `OPEN` → `PATCHED` →
> `VERIFIED` as the post-patch rerun re-evaluates them. Each row links
> back to the source eval case so a reviewer can replay against the
> patched dataset/KB.

## F.1 Headline

| Metric | Value |
|---|---:|
| Cases inspected | 17 (incorrects on Stack-OFF baseline, 102-case prefix) |
| Eval-artifact share | 6 (35 %) — rubric bugs, not bot bugs |
| KB-internal contradictions | 2 (12 %) — `room_guide.md` vs `room_types.md` size mismatch |
| **KB ↔ PMS DB drifts** | **1 — Deluxe `max_occupancy`** (open, needs operational decision) |
| Dense-retrieval misses (Phase G/H will fix) | 5 (29 %) |
| Gemma behavioural defects | 4 (24 %) |
| Router misclassification | 1 (6 %) |
| **True floor defect rate (after rank-1/2)** | **~8/94 = 8.5 %** (down from apparent 18 %) |

## F.2 Systemic drifts

Same defect class as the original Phase 5 price drift — multiple sources of
truth disagree about the same field. Each one is documented here so that
re-fixing requires a single grep instead of re-doing the dig.

### F.2.1 Size drift — KB-internal (CLOSED)

| Room | `room_guide.md` (pre-fix) | `room_types.md` (canonical) | Action |
|---|---:|---:|---|
| Standard | 32 sqm | 28 sqm | aligned to 28 |
| Deluxe | 45 sqm | 35 sqm | aligned to 35 |
| Suite | 72 sqm | 55 sqm | aligned to 55 |
| Penthouse | 150 sqm | 120 sqm | aligned to 120 |

Source-of-truth pick: `room_types.md` (matches the goldens and is referenced
by Phase 5's price-strip directive). `room_guide.md` was uniformly ~25 %
inflated — appears to have been drafted from a different spec sheet and
never reconciled. Fixed 2026-06-13 (commit pending). Re-ingested Qdrant.

### F.2.2 Max-occupancy drift — KB ↔ PMS DB (CLOSED, Option B applied)

| Room | `room_guide.md` | `room_types.md` | **PMS DB** | Action |
|---|---|---|---:|---|
| Standard | 2 adults | 2 | 2 | ✓ |
| **Deluxe** | 2 adults + 1 child (was) | 3 (was) | **2** | KB → 2 adults, table → 2, golden → "2" |
| Suite | 4 adults | 4 | 4 | ✓ |
| Penthouse | 6 adults | 6 | 6 | ✓ |

Mechanism: `create_reservation()` in `src/agent/hotel_tools.py:340` rejects
`num_guests > room['max_occupancy']` against the PMS DB row. The bot,
reading the pre-fix KB, would tell a guest "yes 3 fits in a Deluxe" but
the booking flow then rejected the actual `create_reservation` call with
"max occupancy is 2". Same defect class as Phase 5 price drift.

**Resolution chosen:** Option B (KB follows DB). The owner-driving
principle is "DB is operational truth; KB updates are ETL output, not
ETL input." Rationale: in a production hotel the DB is mutated by ops
staff dozens of times per day (status, pricing, blocked rooms); KB
markdown is rebuilt periodically by a content pipeline. Letting the
content side drift away from operations is the failure mode we want to
catch, not entrench. Phase 5 took the same stance for room prices.

Patches applied 2026-06-13:
- `data/hotel/room_guide.md`: Deluxe **Max Guests** "2 adults + 1 child" → "2 adults" (EN + TH).
- `data/hotel/room_types.md`: Deluxe section header "Max Guests: 2 adults + 1 child" → "2 adults"; comparison table row Deluxe "3" → "2".
- `eval/dataset/golden_en.jsonl rooms_room_comparison_en_2`: `expected_facts` / `must_contain_any` → ["2", "2 adults", "2 guests"]; undid the rank-1 over-accept of "2 adults and 1 child".
- `eval/dataset/golden_th.jsonl rooms_room_comparison_th_2`: → ["2", "2 ท่าน"].

Verified via fresh-session probe 2026-06-13: bot answers "A Deluxe Room
can accommodate a maximum of 2 adults" on `"How many people fit in a
Deluxe Room maximum?"` (18.1 s) and "The maximum occupancy for our
Deluxe Room is 2 adults" on `"What is the max occupancy of Deluxe Room?"`
(24.3 s) — both match DB without invoking "+1 child".

### F.2.3 Facility-location and hours drift — KB ↔ PMS DB (CLOSED)

A broader ETL-style sweep of every row in `hotel_services` against the
KB markdown found four additional facility-level drifts. All fixed in
the same direction (KB → DB).

| Service | KB (pre-fix) | **PMS DB** | KB (post-fix) |
|---|---|---|---|
| Fitness Center location | 4th Floor | **Level 2** | Level 2 |
| Fitness Center hours | 24 hours (keycard) | **6:00 AM – 10:00 PM** | 6:00 AM – 10:00 PM |
| Swimming Pool hours (start) | 6:00 AM | **7:00 AM** | 7:00 AM |
| Business Center location | 2nd Floor | **Lobby Level** | Lobby Level |
| Business Center hours | 8:00 AM – 8:00 PM | **24 Hours** | 24 Hours |
| Spa & Wellness hours | 10:00 AM – 10:00 PM | **9:00 AM – 9:00 PM** | 9:00 AM – 9:00 PM |
| Last spa booking | 8:30 PM | (derived: 7:30 PM) | 7:30 PM |

All located in `data/hotel/facilities_amenities.md` (Fitness, Pool,
Business Center) and `data/hotel/spa_wellness.md` (Spa). Thai mirror
blocks updated alongside the EN. Verified post-patch via a 5-case smoke:

| Smoke case | Bot response (post-fix) | Verdict |
|---|---|---|
| `Where is the gym?` | "Our Fitness Center is located on Level 2 and is open daily from 6:00 AM to 10:00 PM. Access is complimentary…" | ✓ |
| `What time does the pool open?` | "Our swimming pool, located on the 5th Floor Rooftop, is open daily from 7:00 AM to 9:00 PM." | ✓ |
| `What are the Business Center hours?` | "The Business Center is located on the Lobby Level and is open 24 hours daily." | ✓ |
| `What are the spa operating hours?` | "The Serenity Spa & Wellness Center is open daily from 9:00 AM to 9:00 PM. Last booking 7:30 PM. 3rd floor." | ✓ |

Affected goldens patched at the same time (token-level):

| Golden | Old token | New token |
|---|---|---|
| `canaries.jsonl / canary_gym_location_en` | "4th Floor" | "Level 2" / "2nd Floor" / "ชั้น 2" |
| `golden_en.jsonl / spa_operating_hours_en_1` | "10:00 AM – 10:00 PM" / "10:00 AM" / "10:00 PM" | "9:00 AM – 9:00 PM" / "9:00 AM" / "9:00 PM" |
| `golden_en.jsonl / facilities_swimming_pool_en_1` | "6:00 AM" | "7:00 AM" |
| `golden_en.jsonl / facilities_business_center_en_1` | "8:00 AM – 8:00 PM" | "24 Hours" / "Lobby Level" |
| `golden_th.jsonl / spa_operating_hours_th_1` | "10:00 – 22:00 น." | "09:00 – 21:00 น." |
| `golden_th.jsonl / facilities_swimming_pool_th_1` | "06:00" | "07:00" |
| `golden_cn.jsonl / spa_operating_hours_cn_1` | "10:00 AM – 10:00 PM" | "9:00 AM – 9:00 PM" |
| `multi_intent_and_out_of_kb.jsonl / mi_pool_hours_and_gym_floor_en` | "4th Floor" / "06:00" | "Level 2" / "2nd Floor" / "07:00" |

False positives (matched the audit grep but were on unrelated topics
and left untouched): `attractions_transportation_en_1`/`th_1` (BTS/MRT
operating hours, separately authored from facility services) and
`emergency_medical_services_en_1` (in-house clinic hours).

### F.2.4 ETL pipeline implication (Phase K backlog item)

The 5 drifts above (Deluxe occupancy + 4 facility location/hour
disagreements) were detected only because the regression dig (§C.5)
forced a full KB ↔ DB cross-reference. Without that audit they would
have survived as silent guest-facing inaccuracies — the bot would
politely repeat the wrong floor / hours / occupancy. A production
hotel would not catch this until a real guest got the wrong answer.

The proper architectural fix is a one-way ETL: the DB owns operational
truth; a nightly content pipeline regenerates the relevant sections
of `data/hotel/*.md` from the latest DB rows, and the resulting
markdown bundle is re-ingested into Qdrant. Section-level templates
(name, location, hours, price) become DB-bound; descriptive prose
(amenities flavour, view descriptions) stays human-authored.

This is documented as **Phase K — KB↔DB ETL pipeline (BACKLOG)** in
AP_C §C.Z and not implemented in this thesis (out of scope). The
manual sweep performed today is the one-time bridge to ship the
post-dig clean triple; future iterations should pick up the ETL.

## F.3 Per-case backlog (Stack-OFF Run #1, 102-case prefix, 17 incorrects)

Status legend: `OPEN` (no fix planned) · `PATCHED` (fix applied, awaits
re-judge verification) · `VERIFIED` (re-judged, now `correct`/`partial`).

### F.3.1 Rooms domain (9 cases)

| ID | Question (truncated) | Bot response (truncated) | Why incorrect | Category | Effort | Status | Fix applied |
|---|---|---|---|---|---|---|---|
| `rooms_standard_room_en_1` | What is the size of a Standard Room? | "listed as 28 sqm in our general info … 32 sqm in the detailed section" | KB contradiction — bot reported BOTH chunks faithfully | KB-internal drift (F.2.1) | trivial | **PATCHED** | room_guide.md 32 → 28 sqm |
| `rooms_deluxe_room_en_1` | What is the size of the Deluxe Room? | "listed as 35 sqm in our comparison table and 45 sqm in our directory" | Same as above for Deluxe | KB-internal drift (F.2.1) | trivial | **PATCHED** | room_guide.md 45 → 35 sqm |
| `rooms_suite_en_1` | What is the size of the Suite room? | "I am currently retrieving the exact dimensions … one moment, please" | Gemma deferral phrase — no facts emitted despite chunk being retrieved | gemma_default_behavioral | small | **OPEN — rank-3** | model_override anti-deferral, deferred (entanglement risk) |
| `rooms_room_comparison_en_1` | What is the size of a Standard room? | "Please allow me a moment to confirm" | Same Gemma deferral pattern | gemma_default_behavioral | small | **OPEN — rank-3** | (same as above) |
| `rooms_room_comparison_en_2` | How many guests can a Deluxe room accommodate? | "2 adults and 1 child" (correct per KB, =3) | Rubric demanded literal "3"; bot's KB-canonical phrasing semantically equivalent | eval_artifact (rubric too literal) | trivial | **PATCHED** | golden_en.jsonl `must_contain_any` accepts "2 adults and 1 child" |
| `rooms_special_requests_en_1` | How much does an extra bed cost per night? | "800 THB per night … contact the front desk" | `must_not_contain` blocked "contact the front desk" even though same answer included it as an action channel, not a refusal | eval_artifact (rubric conflict) | trivial | **PATCHED** | golden_en.jsonl removed "contact the front desk" from `must_not_contain` |
| `rooms_room_types_en_1` | What is the size of a Standard Room? | "listed as 2" (truncated) | Scalar substitution — bot grabbed Max Guests (=2) instead of Size (=28 sqm) from the multi-field chunk | gemma_default_behavioral | small | **OPEN — rank-3** | model_override mandates unit-qualified extraction `"Size: {N} sqm"` |
| `rooms_housekeeping_en_2` | How can I request daily cleaning service? | Listed 3 channels but missed "Make Up Room sign" tag | KB has the Make Up Room sign info but dense retrieval missed it under Stack-OFF | dense_retrieval_miss | (Phase H.C fixes it) | **DEFERRED** | Phase H.C BM25 expected to retrieve under `clean_stackon_light` |
| `rooms_extra_beds_en_1` | How much does an extra bed cost per night? | "800 THB per night … contact the front desk" | Same as `rooms_special_requests_en_1` | eval_artifact (rubric conflict) | trivial | **PATCHED** | golden_en.jsonl removed "contact the front desk" from `must_not_contain` |

### F.3.2 Facilities / FAQ / Spa / Policies domain (8 cases)

| ID | Question (truncated) | Bot response (truncated) | Why incorrect | Category | Effort | Status | Fix applied |
|---|---|---|---|---|---|---|---|
| `spa_reservations_en_1` | How can I book a spa treatment? | Generic spa info, asked for reservation ID instead of listing 303/reception/app channels | Dense retrieval missed the "How to Book" sub-section; bot fell back to a transactional flow on an informational question | dense_retrieval_miss + gemma_account_flow_on_info | (Phase H.C fixes retrieval; rank-3 for account-flow) | **DEFERRED** | Phase H.C + Gemma override |
| `facilities_fitness_center_en_3` | How much does a personal training session cost and how do I book one? | "Fitness Center is complimentary … we do not have the specific pricing" | Bot retrieved the gym chunk but missed the PT chunk (1,000 THB / dial 404) — dense miss + over_refuse | dense_retrieval_miss + over_refuse | (Phase H.C fixes it) | **DEFERRED** | Phase H.C BM25 expected to retrieve `1,000 THB`/`dial 404` |
| `facilities_wifi_en_1` | (WiFi-related, full Q in dataset) | Bot mentioned "contact the front desk" appropriately | `must_not_contain` blocked legitimate action channel | eval_artifact (rubric conflict) | trivial | **PATCHED** | golden_en.jsonl removed "contact the front desk" |
| `facilities_wifi_en_3` | (WiFi-related, full Q in dataset) | Bot mentioned "contact front desk to upgrade" as the literal expected fact | `must_not_contain` conflicted with `expected_facts` — golden itself REQUIRED the phrase | eval_artifact (golden self-contradictory) | trivial | **PATCHED** | golden_en.jsonl removed "contact the front desk" |
| `faq_check_in_check_out_en_2` | (FAQ check-in/out, full Q in dataset) | Bot asked for confirmation number on a general policy question | Gemma router fell into account-lookup branch when KB+RAG would have answered | gemma_account_flow_on_info | small | **OPEN — rank-3** | model_override forbids confirmation-number requests on general FAQ intents |
| `policies_pet_policy_en_1` | What is the pet policy? | Bot returned generic refusal, missed the 5 kg limit chunk | Dense retrieval miss — high-signal token "5 kg" exists verbatim in KB but wasn't surfaced | dense_retrieval_miss | (Phase H.C fixes it) | **DEFERRED** | Phase H.C BM25 expected |
| `policies_smoking_en_1` | What is the smoking policy? | Returned generic policy info, missed "100 % non-smoking" / fine amount | Same dense miss pattern | dense_retrieval_miss | (Phase H.C fixes it) | **DEFERRED** | Phase H.C BM25 expected |
| `policies_cancellation_en_3` | How can I cancel my reservation? | Bot started transactional cancel_reservation flow instead of returning policy info | Router misclassified informational phrasing (no confirmation number in turn) as transactional intent | router_misclassification | small | **OPEN — rank-5** | tighten booking router to route bare informational cancel to RAG first |

## F.4 Fix-effort summary

| Rank | Action | Cases addressed | Effort | Status |
|---|---|---:|---|---|
| 1 | Golden-label patches (5 cases) | 5 | trivial | **DONE 2026-06-13** |
| 2 | Align `room_guide.md` sizes to `room_types.md` + re-ingest | 2 | trivial | **DONE 2026-06-13** |
| 3 | Gemma model_override (anti-deferral + unit-qualified extraction + anti-account-flow-on-FAQ) | 4 | small | **OPEN** — deferred to next iteration (entanglement risk vs `clean_stackon` baseline) |
| 4 | Header-promoted chunking on `policies_rules.md` / `facilities_amenities.md` | 5 | small | **DEFERRED — redundant** with Phase H.C (BM25+reranker) |
| 5 | Tighten cancel-router (informational cancel → RAG before tool) | 1 | small | **OPEN** — backlog |
| F.2.2 | **PMS DB ↔ KB Deluxe max_occupancy drift** | ~3 | trivial | **OPEN — owner decision required** (Option A: DB → 3; Option B: KB+golden → 2) |

## F.5 Projected pass-rate impact (102-case sample)

| Patch level | Pass rate | Δ |
|---|---:|---:|
| Baseline (no patches) | 83.3 % (85/102) | — |
| **After rank-1 + rank-2 (current state)** | **~90.2 % (92/102)** | **+6.9 pp** |
| After rank-3 (Gemma override, deferred) | ~92.2 % (94/102) | +1.9 pp |
| After rank-4/5 (chunking + router) — but Phase H.C will own these | ~97.1 % (99/102) | +4.9 pp |

Phase G/H (BM25 + reranker + multi-intent) is expected to recover the 5
`DEFERRED` dense-retrieval-miss cases when `clean_stackon_light` runs, so the
post-stack-on aggregate is projected at 95 %+. The remaining floor defects
(Gemma deferral + router misclassification + max_occupancy drift) survive
across all three stack configurations and form the **Phase J backlog**.

## F.6 Reproduction

```bash
# 1. Re-run the affected 17 cases against the patched dataset + KB:
python scripts/eval/backtest_runner.py \
    --tag clean_stackoff_v2 \
    --endpoint http://localhost:8088 \
    --no-canaries --no-chat-cache --max-chat-parallel 1

# 2. Compare verdicts on the 17 IDs:
python scripts/eval/_compare_two_runs.py \
    --before eval/results/clean_stackoff/20260613T113341/raw.jsonl \
    --after  eval/results/clean_stackoff_v2/<ts>/raw.jsonl \
    --ids rooms_standard_room_en_1,rooms_deluxe_room_en_1,\
rooms_room_comparison_en_2,rooms_special_requests_en_1,\
rooms_extra_beds_en_1,facilities_wifi_en_1,facilities_wifi_en_3
```

Expected on re-judge after rank-1 + rank-2: 7 of 17 flip to `correct`
(5 from rubric patches + 2 from KB size alignment).
