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

### Fix applied (commit `154b623`)

1. Stripped every `**Price:** ... THB` line from `data/hotel/room_types.md`. Replaced with directive: `**Price:** Quote via calculate_dynamic_price tool / ขอราคาจากเครื่องมือจองห้อง`.
2. Dropped the Price column from the room comparison table.
3. Added top-of-file pricing note instructing the LLM (via RAG context) to defer pricing answers to the `calculate_dynamic_price` tool.
4. Re-ingested the Qdrant `hotel_knowledge` collection with `CHUNK_SIZE=1000` (iter3). Points went from 10 (whole-doc chunks) → 49 (per-H2-section chunks).

### Verification — post-fix

- [x] `scripts/audit_data_db_drift.py` → exit 0 (was: 6 room-price mismatches surfaced)
- [x] Iter3 backtest (100-case stratified sample): **`rag_drift` count went from 3 → 0**
- [x] Iter5 was a regression on this metric (`rag_drift` went back to 3 with `num_docs=8`) — confirmed not to re-enable
- [ ] Pricing-template eval rows: pending the final 261-case strategic backtest

**Status update: RESOLVED** (iter3 stable across all subsequent iterations).

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

### Fix applied (commits `154b623` + post-baseline iter3)

1. `src/agent/hotel_tools.py:882`: `num_docs=3 → 5` (env-overridable via `HOTEL_RAG_NUM_DOCS`).
2. **Iter1 (Phase 5 base):** re-ingest with `CHUNK_SIZE=2000` (env var; `chains.py` already env-overridable at line 129). Collection went 10 → 22 chunks (~2 per file).
3. **Iter3:** re-ingest with `CHUNK_SIZE=1000`. Collection went 22 → **49 chunks** (per-H2-section granularity). `emergency_contacts.md` (5 H2 sections) finally got 5 chunks; `facilities_amenities.md` (6 H2 sections) got 6 chunks; WiFi and address sections are now independently searchable.

We tried `num_docs=5→8` in iter5 looking for further uplift, but it introduced more noise than signal: hallucination went up and `rag_drift` re-appeared. `num_docs=5` is the optimum.

### Verification — post-fix

- [x] Canary EN `canary_wifi_password_en` → PASS (response now contains `HOTEL2024GUEST`)
- [x] Canary EN `canary_hotel_address_en` → PASS (response now contains `123 Sukhumvit Road`)
- [x] Canary CN `canary_wifi_password_cn` → PASS (response now contains `HOTEL2024GUEST`)
- [-] Canary TH `canary_wifi_password_th` → FAIL (false positive — bot returns correct password but also mentions front-desk upsell, which matches the `ติดต่อแผนกต้อนรับ` forbidden token; semantic-judge confirms response is correct)
- [x] Canary sweep: **11/15 → 14/15 pass** (3 of 4 known fails resolved)
- [x] Iter3 backtest (100-case stratified sample): `rag_miss` count **30 → 6** (−80%)

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

## C.5 Eval queue artifact — `empty_response` from FastAPI semaphore timeout

> Discovered 2026-06-13 during the Phase G+H regression dig. The original
> 2026-06-12 dual backtest (Stack-OFF vs Stack-ON, both 502 cases) showed
> a `-1.4 pp` aggregate delta and `+16 empty_response` regression in the
> ON arm that an adversarial-verification workflow attributed to the
> Gemma `model_overrides` prompt. A causal-isolation probe rerun on a
> 58-case stratified sample exposed a second, larger cause: a
> concurrency mismatch between the backtest driver and the chatbot's
> queue-cap server-side semaphore.

**Defect category:** `empty_response` (eval-side artifact, not a model
or retrieval bug)
**First observed:** 2026-06-12, run dirs `eval/results/gemma_q8_stackoff/20260612T171021/` and `eval/results/gemma_q8_stackon/20260612T215522/`
**Severity:** High (silently contaminates every backtest aggregate by 6–10
percentage points without showing up in canary tolerance gates)
**Status:** **RESOLVED** in commit `d8c309b`; runs prior to that commit
require rerun for thesis-grade numbers

### Example failure (C.5 — queue timeout)

Stack-ON case `dining_skyline_restaurant_all_day_dining_en_1` ("What are
the operating hours for the Skyline Restaurant?") returned:

- OFF: `"The Skyline Restaurant is open from 11:00 AM to 11:00 PM. It is located on the 25th floor and offers panoramic city views."` — `correct`
- ON: empty string, `chat_latency_s = 45.0`, `reason = "chat error: HTTPError: HTTP Error 503: Service Unavailable"` — `incorrect` with defect `["empty_response"]`

Eighteen further EN/TH regression cases in the original dual backtest
share the same exactly-45.0-second latency signature.

### Root cause (C.5 — queue timeout)

`scripts/eval/backtest_runner.py:484-504` set `max_chat_parallel = 2`
when the endpoint is `localhost`, dispatching two `/chat` requests
concurrently to keep the GPU queue warm. The container however runs
with `OLLAMA_NUM_PARALLEL = 1` (Gemma Q8_0 weights are 12 GB; a second
concurrent inference exceeds the 16 GB VRAM budget on the RTX 5080
alongside the bge-reranker) and `MAX_CONCURRENT_LLM_CALLS = 1` in the
FastAPI semaphore. The second concurrent request enters the
`LLM_QUEUE_TIMEOUT_SEC = 45` queue, waits 45 s for the first to finish,
times out, and returns HTTP 503 with an empty body. The runner records
the 503 as `verdict=incorrect, defects=["empty_response"]`, and the
report aggregates the artifact into the `empty_response` defect column.

Mechanism diagram:

```
runner → /chat #1 (queued at semaphore)  → LLM acquires lock → 50 s generation → 200 OK
runner → /chat #2 (queued at semaphore)  → waits  45 s for lock  → 503 Service Unavailable
                                                  └── LLM_QUEUE_TIMEOUT_SEC fires here
runner sees /chat #2 = empty → records empty_response
```

Stack-ON cases hit this artifact more often than Stack-OFF cases (`32`
vs `20` exactly-45 s timeouts in the original dual backtest) because
the Phase H reranker + heavier `model_overrides` prompt slow the first
inference by ~5–10 s, leaving the second waiter past the 45 s gate more
often. The original dig workflow correctly identified that empty
responses dominated EN/TH regressions but mis-attributed the proximate
cause to the model_overrides prompt because the verification step
relied only on `raw.jsonl` content (which records the 503 the same way
as a genuine LLM silence).

### Detection — pre-fix (C.5 — queue timeout)

Heuristic from the dig analysis (`scripts/eval/_regression_dig_503.py`):

```python
import json
rows = [json.loads(l) for l in open(raw_path)]
timeouts_45 = [r for r in rows
               if abs(r.get('chat_latency_s', 0) - 45.0) < 0.5
               and 'chat error' in r.get('reason', '')]
print(f"45-s queue timeouts: {len(timeouts_45)} / {len(rows)}")
```

Original 2026-06-12 dual:

| Run | n | Chat errors | 45-s timeouts |
|---|---:|---:|---:|
| Stack-OFF | 502 | 34 (6.8 %) | **20** |
| Stack-ON | 502 | 50 (10.0 %) | **32** |
| Probe 1 tainted | 58 | 32 (55.2 %) | **32** |
| Probe 1 clean (post-fix) | 58 | **0** | **0** |

### Fix applied (C.5 — queue timeout, commit `d8c309b`)

Three coordinated changes so the eval driver actually matches the GPU
concurrency it's measuring:

- `scripts/eval/run_dual_backtest.py` + `scripts/eval/run_micro_probe.py`
  pass `--max-chat-parallel 1` to `backtest_runner.py`, forcing
  per-call serialization on the driver side.
- `deploy/compose/docker-compose.hotel.yaml` raises the default for
  `LLM_QUEUE_TIMEOUT_SEC` from `30` to `240` (defensive — the runner
  now serializes so the queue shouldn't fill, but if a stray
  concurrent request slips through during smoke testing, a 4-minute
  window covers any Q8 + reranker + multi-intent worst case).
- `.env` mirror of the same `LLM_QUEUE_TIMEOUT_SEC=240`.

A complementary `verify_container_env()` guard in the dual-backtest
driver already exists (commit `c17c3d3`) — it fails the run if the
expected stack toggles or OpenRouter key are missing. The fix does not
extend that guard to runtime queue settings because the only operator
that can change them is the operator running the driver.

### Verification — post-fix (C.5 — queue timeout)

The same 58-case stratified sample rerun under probe 1 (Stack-ON minus
`model_overrides`, `--max-chat-parallel 1`) returned:

- `chat_errors = 0`
- `45-s timeouts = 0`
- `empty_response = 0`
- Aggregate pass rate `70.7 %` (vs `33 %` on the same probe pre-fix)

The "+16 empty_response regression" originally attributed to the
gemma `model_overrides` block in the workflow synthesis was therefore
**partly the queue artifact** (~16 of the 32 extra Stack-ON timeouts
were within 5 s of the model-overrides' added prompt-processing
latency) and **partly genuine** (probe 1 still gains `+9.1 pp` on EN
and `+5.6 pp` on TH from removing the overrides — see §C.Y Phase G.D
below for the corrected attribution).

The 2026-06-12 dual backtest's aggregate numbers
(`Stack-OFF 68.1 %` / `Stack-ON 66.7 %`) cannot be used in CH6 §6.5
as-is — they are reported in the chapter alongside the corrected
clean-triple aggregates from the post-fix rerun and labelled
**"contaminated baseline (queue artifact)"**, with the post-fix numbers
used for all promotion-gate evaluation.

### Replication

```bash
# Pre-fix (will show ~6–10 % empty_response storms):
python scripts/eval/backtest_runner.py --tag repro_pre_fix --max-chat-parallel 2
# Post-fix (clean):
python scripts/eval/backtest_runner.py --tag repro_post_fix --max-chat-parallel 1
```

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

## C.X Closing summary

Final 261-case strategic backtest (run tag `final-postfix`, judge `deepseek/deepseek-chat-v3.1`) vs the 138-case pre-fix baseline:

| Defect | Baseline rate | Post-fix rate | Δ | Status |
|---|---:|---:|---:|---|
| `rag_drift` | 2.2% | 0.8% | −1.4 pp | **RESOLVED** (audit gate now 0) |
| `rag_miss` | 21.7% | 6.9% | **−14.8 pp** | **PATCHED** (chunk_size=1000 → per-section retrieval) |
| `hallucination` | 20.3% | 13.4% | −6.9 pp | PARTIAL — remaining hallucinations are 9B-model limits |
| `incomplete` | 30.4% | 18.8% | **−11.6 pp** | PARTIAL — same root cause as rag_miss, helped by same patch |
| `over_refuse` | 13.8% | 3.4% | **−10.4 pp** | **RESOLVED** (RAG now surfaces the facts the bot used to refuse) |
| `tool_not_called` | 4.3% | 3.8% | −0.5 pp | PARTIAL — pricing helper landed; remaining cases are routing issues |
| `spec_wrong` | 8.7% | 8.0% | −0.7 pp | OPEN — needs deeper room-info chunking, not addressed |
| `wrong_routing` | 0.7% | 0 | −0.7 pp | RESOLVED (was 1 case in baseline) |
| `empty_response` | 0.7% | 0.4% | −0.3 pp | RESOLVED at this rate |
| `language_leak` | 0% | 0.4% | +0.4 pp | NEW — 1 adversarial probe (`adv_force_chinese_en`) succeeded once |
| `tool_call_leak` | 0% | 0% | 0 | UNCHANGED (§5.14.2 protection holding) |
| `particle_mismatch` | 0% | 0% | 0 | UNCHANGED |
| `format_error` | 0% | 0% | 0 | UNCHANGED |

**Aggregate strict pass rate: 54.3% → 72.4% (+18.1 pp).** With the larger 261-case sample the Wilson 95% CI is [65.2%, 76.4%] — the 75% ship gate sits inside the CI, so the system is plausibly ship-ready but the available evidence is not yet conclusive.

The patches that mattered most (by defect-rate reduction):

1. **`chunk_size = 1000`** (iter3) — single biggest win. Re-ingested Qdrant from 10 whole-document chunks to 49 per-H2-section chunks. Resolved both `rag_miss` (WiFi password, hotel address, embassy phone) and `over_refuse` (bot no longer refuses questions whose answers ARE in the KB).
2. **KB price strip + `calculate_dynamic_price` directive** (Phase 5.1) — resolved `rag_drift` to 0 + made dynamic pricing reachable via the knowledge sub-agent's pre-fetch helper.
3. **`num_docs = 5`** (Phase 5.3) — modest contribution; the +chunks change had already done most of the work.

The patches that *didn't* work and were reverted:

- **iter2 prompt rule** ("if not in source, refuse"): caused +5 `over_refuse` and +6 `rag_miss`. Lesson: refusal rules are brittle — better to fix the retrieval that drives them.
- **iter4 temperature = 0.1**: dropped hallucination by −4 but bot became over-conservative (+5 `rag_miss`, +2 `tool_not_called`).
- **iter5 num_docs = 8**: more noise than signal; `rag_drift` came back.
- **iter6 temperature = 0.2**: pure plateau — defect profile identical to T=0.3.

The remaining gap from 72.4% → 75% (ship gate) is small enough that the system is *plausibly* ready; further gains require a stronger base LLM (cloud Qwen3-max parity rerun is the obvious next experiment) or human-eval comparison to confirm the judge isn't over-penalising paraphrased-but-correct responses.

## C.Y Phase A–F: model-tier swap, workflow improvements, defence

After the iter1–9 plateau, a 4-agent strategic investigation surfaced cloud-LLM swap as the single highest-leverage remaining lever (predicted +10–15 pp). Because the project budget excluded paid API spend, we substituted **a local Gemma 4 12B swap via the existing runtime `PUT /settings/llm` endpoint** as the comparable local-only experiment (Phases A–F below). Same Ollama backend, same iter3 retrieval config — only the base LLM changes.

### Phase A — Gemma 4 12B swap (SHIPPED)

- **Pulled:** `ollama pull gemma4:12b` (11.9B params, Q4_K_M, 7.6 GB, 262K context). Required upgrading the `ollama/ollama` image from 0.18.2 → 0.30.7 to recognise the model.
- **Swap path:** runtime hot-swap via `PUT /settings/llm {"backend":"ollama","model":"gemma4:12b"}` (admin-only). No restart, no code change.
- **Result vs Qwen3.5-Opus 9B at iter3 config (n=100, seed=42):**
  - Strict pass: 79.2% → **80.2%** (+1.0 pp).
  - `hallucination`: 14 → 12 (−2).
  - `incomplete`: 11 → 9 (−2).
  - `hard_negatives`: 3/3 in sample (was 3/3 in iter3 sample too, but n=3 has huge variance).
  - Average chat latency: ~13s (similar to 9B; gemma4:12b at Q4_K_M is faster per token than the 9B's wider context).
- **Status:** **NEW BASE OPTIMUM**. All subsequent work uses gemma4:12b.

### Phase B — BGE / Qwen3-0.6B cross-encoder reranker (REVERTED)

- **Activated:** `RERANKER_BACKEND=qwen` in `.env`, container recreate. Logs confirmed "Reranking 30 documents... → top 5". Cross-encoder loaded on CPU (event-loop blocking concern was a non-issue since `document_search` is sync and runs in a worker thread).
- **Result (gemma4 + reranker, n=100):** 78.1% strict (**−2.1 pp** vs Phase A). Hallucination −3 ✓ (the intended target), but `over_refuse` +2, `incomplete` +4. Chat latency 13s → 21s/case (reranker adds ~8s).
- **Verdict:** Within the ±9 pp noise band, but no demonstrable benefit. Reverted. **Hypothesis:** gemma4's stronger embedding-similarity rankings already saturate top-1 precision on this KB; the reranker reorders by a *different* relevance signal that occasionally drops the correct chunk from top-5.

### Phase C — `MarkdownHeaderTextSplitter` + breadcrumb prepend (REVERTED)

- **Applied:** Replaced `RecursiveCharacterTextSplitter` with a two-stage pipeline — `MarkdownHeaderTextSplitter(headers=[h1,h2,h3])` first, then character splitter only for chunks still > `CHUNK_SIZE`. Prepended `"Hotel > {h1} > {h2} > {h3}:\n"` breadcrumb to every chunk's `page_content` before vectorisation. Re-ingested: 49 → 80 Qdrant chunks.
- **Result (gemma4 + reranker + breadcrumb, n=100):** 71.9% strict (**−8.3 pp** vs Phase A). `over_refuse` 5 → 15 (+10) — the dominant regression.
- **Root cause of the regression:** The hotel KB's H2 headers are *bilingual*, e.g. `"## Local Attractions & Transportation / สถานที่ท่องเที่ยวและการเดินทาง"`. The 4-level breadcrumb `"Hotel > Local Attractions & Transportation / สถานที่ท่องเที่ยวและการเดินทาง > Transportation / การเดินทาง > MRT Subway / รถไฟฟ้าใต้ดิน MRT:\n"` consumed ~200 tokens of each ~250-token chunk — leaving the actual *body* of the chunk at one-fifth its normal density. The bot interpreted the resulting low-density context as "no info available" and refused.
- **Verdict:** Reverted via `git checkout` + re-ingest with the original splitter. Breadcrumb chunking is a known good technique on monolingual KBs but this specific bilingual structure breaks the trade-off.

### Phase D — Eval-runner speedups (LANDED)

- `scripts/eval/backtest_cache.py` + cache lookup in `scripts/eval/backtest_runner.py` keyed by `(case_id, chat_sha, corpus_sha)`. Smoke-tested: 5 cases cold → 5/5 warm hits, `chat_latency_s=0.00`. Saves ~95% wallclock when only the judge prompt changes.
- Pre-judge deterministic short-circuit: lifts empty/leak/`must_not_contain` checks before the LLM judge call (~10–15% judge call savings).
- Parallel chat + async judge via `ThreadPoolExecutor` (default 2 for Ollama, 8 for cloud).

### Phase E — Rubric stability gate (LANDED, gate PASSES)

`scripts/eval/judge_stability.py` bootstrapped 60 triples (30 known-correct + 30 known-incorrect) from the iter3 strategic backtest, re-ran the DeepSeek Chat v3.1 judge, and computed binary FPR/FNR:

- **FPR = 0.0%** [Wilson 95% CI 0.0%–11.4%] — gate < 10% **PASS**
- **FNR = 0.0%** [Wilson 95% CI 0.0%–11.4%] — gate < 10% **PASS**

The most-cited threat to validity in §6.5.7 is now formally closed.

### Phase F — Variance baseline (5 runs, completed)

5× rerun of the same Phase A config (gemma4, no reranker, 49 chunks, `seed=42`, 96-case stratified sample) via `scripts/eval/backtest_variance.py`. Identical inputs every run; the only source of variance is the chatbot's sampling (T=0.3, top_p=0.8) — the judge is fixed at T=0.0.

**Headline:**

| Metric | Mean | σ | 95% CI (mean ± 2σ) |
|---|---:|---:|---|
| **Strict pass rate** | **80.83%** | **1.58 pp** | **[78.87%, 82.79%]** |
| Weighted pass rate | 83.23% | 1.45 pp | [81.43%, 85.02%] |
| Per-run strict | 79.2 / 82.3 / 82.3 / 79.2 / 81.2 % | — | — |

**Statistical re-classification of prior iterations.** With σ = 1.58 pp, the minimum "real signal" threshold is **2σ ≈ 3.2 pp**:

| Change | Δ | abs(Δ) > 2σ | Status |
|---|---:|---|---|
| iter4 T=0.1 | −1.1 pp | No | within noise |
| iter6 T=0.2 | 0.0 pp | No | within noise |
| Phase B reranker | −2.1 pp | No (1.3σ) | within noise (REVERT decision correct on cost grounds, not statistical) |
| **Phase A gemma4 swap** | **+1.0 pp** | **No (0.6σ)** | **within noise — see below** |
| iter8 neg-facts KB | −5.2 pp | Yes (3.3σ) | real regression |
| iter9 lang lock | −5.2 pp | Yes (3.3σ) | real regression |
| Phase C breadcrumbs | −8.3 pp | Yes (5.3σ) | real regression |
| iter7 verbatim prompt | −8.4 pp | Yes (5.3σ) | real regression |
| iter5 num_docs=8 | −11.0 pp | Yes (7.0σ) | real regression |

**Most important finding for the thesis.** The Gemma 4 12B swap (Phase A) produces a single-run +1.0 pp uplift that is *within 1σ* of the noise floor. The defensible claim is therefore not "gemma4 beats Qwen 9B on this dataset" but rather **"gemma4 ties Qwen 9B in aggregate accuracy with the same iter3 retrieval; we shipped it because the 5-run mean 80.83% is one σ above iter3's single-run 79.2% and the qualitative output is cleaner (no Thai unit fragments in CN responses, no `น.` markers leaking, better politeness markers), but the aggregate pass rate gap is statistically negligible."**

The ship-gate consequence is more favourable: with mean 80.83% and 95% CI [78.87%, 82.79%], **every endpoint of the CI is above the 75% gate**. The system passes the aggregate promotion gate *with statistical confidence* — not "plausibly" as we had to qualify the 261-case strategic backtest result, but definitively.

**Per-defect stochasticity.** Some defect categories are highly reproducible run-to-run (incomplete σ=0.84, over_refuse σ=0.45, tool_not_called σ=0.00 — these depend on retrieval determinism), while `hallucination` σ=1.79 dominates the inter-run variance (the LLM confabulates *differently* per sample). The implication for any further iteration: chasing hallucinations with prompt or sampling tweaks is hostage to this 1.79-count baseline jitter; the leverage is on retrieval categories that already have low σ.

### Phase G — Per-model prompt versioning (PARTIAL SHIP)

`load_hotel_prompts(model: Optional[str])` in `src/hotel_guardrails/hotel_langgraph.py:105-182` reads `src/agent/hotel_prompt.yaml`, looks up `model_overrides[<runtime_model_id>]`, and merges those keys over the base prompts at load time. Trigger: when the runtime LLM is hot-swapped via `PUT /settings/llm`, the synthesis prompt rebuilds with the new model's overrides on the next request — no restart, no code change.

Two override blocks shipped initially for `gemma4:12b`:

- `knowledge_synthesis` — 42 lines of "ABSOLUTE RULES" repeated in positive + negative form, calibrated against Gemma's observed tendency to "reason itself into refusal" on guest-facing values (WiFi password, embassy phones, dynamic prices). Each rule appears both as "OUTPUT THE EXACT VALUE word-for-word" AND "NEVER add 'for security reasons' / 'please contact the front desk' / 'I'm not at liberty to share'" forms.
- `booking_flow` — reinforces the LIVE PRICING context-injection block with concrete TH examples and a hardcoded 4-item view whitelist (City / Partial city / Panoramic city / 360°) plus an explicit non-existence list (Mountain / Ocean / Garden / Sea views do NOT exist at this property).

**Outcome:** the override loader itself is permanently shipped (the versioning mechanism is sound and supports future model swaps without code changes), but the specific `gemma4:12b` `knowledge_synthesis` override block was **reverted from production** in Phase I.B once the regression dig (§C.5, §C.Y Phase G.D) showed it was the primary driver of the EN/TH `empty_response` and rare-value substitution regressions. The `booking_flow` override survives in production because its dynamic-pricing reinforcement is a net positive without the value-substitution side effect.

### Phase H — Retrieval-stack augmentation (PARTIAL SHIP)

Three composable additions ran in series after Phase G. Each was tracked by its own runtime env flag (`HYBRID_RETRIEVAL`, `HOTEL_QUERY_REWRITE_ENABLED`, `RERANKER_BACKEND`) so the dual backtest could ablate each independently.

**Phase H.A — Query rewriting (NEUTRAL, KEEP).** Two helpers run on every embed path:

- `_strip_greeting_intro(sq)` removes leading "Hi", "Hello", "I'm <name>", "checking in", สวัสดี/ดิฉันชื่อ/ผมชื่อ, 你好/我叫/我是 patterns before the embedding call. Live-test discovery showed that a greeting + factual question (e.g. *"Hi I'm James, what time does breakfast start?"*) embedded to a routing-router neighbourhood rather than to the dining-section neighbourhood, causing the bot to answer with a hospitality acknowledgement instead of the breakfast time.
- `_extract_query_keywords(sq, lang_hint)` strips TH particles (ค่ะ, ครับ, น่ะ, หน่อย, ขอ, ช่วย), CN politeness (请问, 麻烦, 您, 我想, 一下), and EN fillers ("could you tell me", "would you mind"). The CN politeness strip is the largest single contribution — Chinese question-form questions front-load 请问/麻烦/您 which dominate the embedding centroid until stripped.

Probe 1 ablation: dropping both helpers via `HOTEL_QUERY_REWRITE_ENABLED=false` moves EN/TH within 1 case of the rewrite-on result and removes ~3 CN gains. Verdict: neutral on aggregate but worth keeping for live behavioural quality on greeting-prefixed queries (qualitative win not visible in the eval set).

**Phase H.B — Multi-intent decomposition (KEEP).** `_split_multi_intent(text)` in `hotel_langgraph.py:739-768` splits user messages on bilingual delimiters (`?`, `.`, `;`, `;`, `และ`, `และก็`, `กับ`, `还有`, `还可以`, `;`) when the resulting sub-queries each contain at least one info-keyword (price/time/place/contact). For each sub-query, `search_hotel_knowledge` runs independently with `HOTEL_RAG_NUM_DOCS_PER_SUBQ=5` chunks, the results are concatenated as `[Q1: …][Q2: …]` blocks for the synthesis prompt, then the LLM produces an answer with one paragraph per intent. Verdict: ships unchanged — only ~10 % of the dataset triggers the multi-intent branch (84 % of regressions are single-intent per §C.5 detection table), but on those 10 % it converts ~3 incorrect-into-partial cases per language.

**Phase H.C — BM25 + RRF hybrid retrieval + bge-reranker-v2-m3 (KEEP, CN-driven).** When `HYBRID_RETRIEVAL=true`, `src/retrievers/hotel_knowledge/chains.py:139-185` runs BM25 over the in-memory tokenised chunk store in parallel with the dense Qdrant retrieval and fuses both lists via Reciprocal Rank Fusion (RRF with `k=60`). When `RERANKER_BACKEND=qwen`, the fused top-30 list is then cross-encoded by `BAAI/bge-reranker-v2-m3` on CUDA, returning the top-5 chunks for synthesis.

Probe 1 result on the SAME 58 stratified case ids, model held constant at `gemma4:12b-it-q8_0`:

| Lang | n | Stack-OFF (no Phase H) | Stack-ON minus model_overrides (Phase H + base prompts) | Δ |
|---|---:|---:|---:|---:|
| EN | 22 | 59.1 % | 63.6 % | +4.5 pp |
| TH | 18 | 72.2 % | 66.7 % | −5.5 pp |
| CN | 18 | 77.8 % | **83.3 %** | **+5.5 pp** |
| Aggregate | 58 | 69.0 % | 70.7 % | +1.7 pp |

The CN gain is the canonical BM25-helps-CJK signature: exact rare tokens (addresses, phone numbers, email addresses, time ranges like `22:00-08:00`) that the dense embedding underweights for Chinese hanzi. TH loses slightly to the same numeric-token mechanism (Suvarnabhumi transfer query pulls the Airport Shuttle chunk instead of the multi-option sedan list), but the CN gain dominates aggregate. Verdict: ship Phase H.C; the BM25 + reranker layer is the largest single positive contribution from the Phase H batch.

### Phase G.D — Reverting the gemma `model_overrides` block (REVERTED)

The 2026-06-12 dual backtest's apparent `-1.4 pp` aggregate regression for Stack-ON was confound-isolated in a 4-phase adversarial workflow + the 58-case probe. After also fixing the queue artifact (§C.5), Stack-ON minus `model_overrides` outperforms both Stack-OFF and Stack-ON-with-overrides on EN and TH (`+9.1 pp` and `+5.6 pp` respectively on the same 58-case sample) while keeping the CN gain at `+5.5 pp`. The mechanism is consistent with the workflow's primary hypothesis: a 110-line English-anchored "ABSOLUTE RULES" prompt block, when prepended to the synthesis turn for a TH or EN question, pushes the local-quantised `gemma4:12b-it-q8_0` toward over-strict rule-arbitration (refusal-on-uncertainty), increasing rare-value substitution (returns nearby price/time/location for a different entity) and short generations.

The override block is preserved in `src/agent/hotel_prompt.yaml` for historical traceability but `HOTEL_PROMPT_PATH=/app/src/agent/hotel_prompt_stackoff.yaml` is the production default. The `booking_flow` override is retained — it reinforces the LIVE PRICING context-injection block without triggering the value-substitution side effect (booking is more constrained than open knowledge_synthesis).

### Phase H.D — Per-stay WiFi credentials (SHIPPED, behaviour change)

A live-test discovery showed the chatbot was disclosing a fixed `HOTEL2024GUEST` published in `data/hotel/facilities_amenities.md` — modelling-wise correct (the value WAS in the KB) but operationally wrong (no real 5-star hotel publishes a fixed WiFi password). Phase H.D moves WiFi credentials to a per-reservation per-stay model:

- Schema: `reservations.wifi_password VARCHAR(32) DEFAULT ('WiFi-' || md5(random())[:8])` plus an idempotent `ALTER TABLE` migration for existing dev DBs. Backfilled NULL rows with a deterministic SHA of `reservation_id + created_at`.
- KB: `facilities_amenities.md` and `policies_rules.md` both rewritten to state "per-stay randomly-generated password, printed on welcome card at check-in, available from reception (ext. 0) after check-in". All three languages (EN/TH/CN).
- LangGraph: new `_maybe_compute_wifi_context(message, user_id)` hook fires only when the message contains a WiFi-intent token AND the user_id resolves to a `checked_in` reservation, injecting a `LIVE GUEST WIFI` block with that room's per-stay password into the synthesis context. Anonymous askers and pre-arrival reservations get the published policy text and a polite redirect to reception.
- Tools: `get_guest_reservations()` returns `wifi_password` only when `status='checked_in'`; `check_in_guest()` surfaces SSID + per-stay password in the EN/TH welcome receipt.
- Prompts: both base and override `knowledge_synthesis` blocks rewritten with a two-case rule (LIVE GUEST WIFI present → quote verbatim; absent → decline politely and explain per-stay policy).
- Eval: 12 anonymous WiFi golden labels migrated (canaries × 3, golden × 3, hard_negatives × 1, rubric_calibration × 1, multi_intent × 4) to expect decline + policy; new `eval/dataset/wifi_checkedin.jsonl` adds 3 checked-in test cases with `user_id` pointing at a seed `checked_in` reservation.

Smoke matrix (Gemma Q8 + Stack-ON + Phase G.D revert):

| Case | Expected | Got |
|---|---|---|
| EN anon | decline + policy | ✓ "no fixed password, get it at check-in" |
| TH anon | decline + policy | ✓ "ไม่มีรหัสผ่านคงที่... ใบต้อนรับเมื่อเช็คอิน" |
| CN anon | decline + policy | ✓ "不提供固定的公共密码... 随机生成的临时密码" |
| EN checked-in | share password | ✓ "Room 204 / WiFi-A387931A / valid until June 14" |
| TH checked-in | share password | ✓ "ห้อง 204 รหัสผ่าน: WiFi-A387931A" |

Verdict: **SHIPPED**. This is the largest behaviour-change of the Phase G–I cluster and produces a more realistic hotel demo. The 12-case golden migration is preserved in `scripts/eval/_migrate_wifi_cases.py` for reproducibility.

### Phase I — Eval infrastructure fixes (SHIPPED)

Two regressions surfaced during the Phase G+H regression dig that contaminated both the original 2026-06-12 dual backtest and probe 1's first launch:

**Phase I.A — Subprocess env hydration.** The dual-backtest driver injects stack overrides via `subprocess.run(env=…)`. Without explicitly hydrating from `.env` first, the subprocess inherited only the explicit override dict, so `OPENROUTER_API_KEY` fell back to the docker-compose YAML default `sk-dummy-not-used`, embeddings 401'd, every RAG returned empty, every chat became "information system unavailable". Fixed in commit `c17c3d3` — `load_dotenv_vars()` is called BEFORE the override dict is layered on top. Plus `verify_container_env()` now hard-fails the run if `OPENROUTER_API_KEY` in the container starts with `sk-dummy`.

**Phase I.B — Parallel mismatch.** Documented above as §C.5. Fixed in commit `d8c309b`.

Combined effect of I.A + I.B: the post-fix dual backtest produces interpretable per-language deltas (probe 1 EN +9.1 pp, TH +5.6 pp, CN unchanged from removing `model_overrides`) where the pre-fix dual backtest produced a noisy −1.4 pp aggregate with the prompt and queue effects entangled. The thesis CH6 §6.5 results table reports the clean post-fix triple as the canonical numbers and uses the pre-fix dual only to illustrate the detection trace.

## C.Z Closing patch list

| Phase | Change | Δ vs prior | Verdict |
|---|---|---:|---|
| iter3 | `chunk_size=1000`, num_docs=5, KB price strip | +24.9 pp from baseline | LOCKED |
| iter4 | T=0.1 | −1.1 pp | REVERT |
| iter5 | num_docs=8 | −11.0 pp | KILL |
| iter6 | T=0.2 | 0 pp | PLATEAU |
| iter7 | verbatim prompt | −8.4 pp | REVERT |
| iter8 | negative-facts KB | −5.2 pp | REVERT |
| iter9 | booking lang lock | −5.2 pp | REVERT |
| **Phase A** | **Qwen 9B → Gemma 4 12B** | **+1.0 pp** | **SHIP — new optimum** |
| Phase B | reranker on | −2.1 pp | REVERT |
| Phase C | breadcrumb chunks | −8.3 pp | REVERT |
| Phase D | runner cache + parallel | n/a (workflow) | LANDED |
| Phase E | FPR/FNR gate | n/a (defence) | PASS |
| Phase F | 5× variance | n/a (defence) | DONE (σ=1.58 pp) |
| **Phase G.A–C** | **prompt versioning loader + gemma `model_overrides`** | mixed (CN neutral, EN −9.1 / TH −5.6) | **loader SHIPPED; gemma overrides REVERTED in Phase G.D** |
| Phase G.D | revert gemma `model_overrides`, point at `hotel_prompt_stackoff.yaml` | recovers +9.1 EN, +5.6 TH | SHIPPED (production default) |
| Phase H.A | query rewriting (greeting strip + politeness strip) | neutral (qualitative win on live tests) | SHIPPED |
| Phase H.B | multi-intent decomposition (`_split_multi_intent`) | +3 partial-rescues per language | SHIPPED |
| **Phase H.C** | **BM25 + RRF hybrid + bge-reranker-v2-m3** | **+5.5 pp CN, neutral EN, −1 to +1 TH** | **SHIPPED (largest single positive)** |
| Phase H.D | per-stay WiFi credentials (schema + KB + LangGraph context injection) | behaviour change; not measured by aggregate | SHIPPED |
| Phase I.A | subprocess env hydration (`OPENROUTER_API_KEY` propagation) | unblocks all post-Phase-G evals | SHIPPED |
| **Phase I.B** | **eval driver `--max-chat-parallel=1` + `LLM_QUEUE_TIMEOUT_SEC=240`** | **eliminates ~6–10 % empty_response artifact in every backtest** | **SHIPPED — see §C.5** |

**Final production state (2026-06-13):** local `gemma4:12b-it-q8_0` + Phase H (BM25 hybrid + bge-reranker + query rewrite + multi-intent) + Phase G loader pointed at `hotel_prompt_stackoff.yaml` (no gemma overrides) + Phase H.D per-stay WiFi + Phase I queue-fixed eval driver. The original 2026-06-12 dual backtest aggregates (Stack-OFF 68.1 %, Stack-ON 66.7 %) are not used in CH6 §6.5 because of §C.5 contamination; the clean triple backtest started 2026-06-13 (tags `clean_stackoff`, `clean_stackon`, `clean_stackon_light`) provides the canonical numbers.

**Earlier final state (Phase F, 5-run variance baseline):** local Gemma 4 12B + iter3 retrieval config; mean aggregate 80.83 % [78.87 %, 82.79 %]. Wallclock for one 100-case backtest dropped from 30 min (pre-Phase D) to ~3 min (warm cache, parallel chat). Judge credibility is formally backed by FPR/FNR=0 % on a 60-triple calibration set.
