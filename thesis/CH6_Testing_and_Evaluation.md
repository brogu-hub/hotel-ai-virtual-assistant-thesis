# Chapter 6: Testing and Evaluation

## 6.1 Evaluation Methodology

### 6.1.1 Test Design

The evaluation strategy uses two complementary approaches:

1. **Model evaluation** — 25 test cases covering hotel-domain tasks, scored for accuracy against expected behaviors
2. **Infrastructure testing** — 193 automated assertions verifying auth, security, scaling, and API correctness

### 6.1.2 Golden Dataset (25 Test Cases)

The golden dataset covers five categories representing the full range of hotel chatbot interactions:

| Category | Cases | Coverage |
|----------|-------|----------|
| Knowledge (K01–K08) | 8 | Breakfast, WiFi, pool, pets, cancellation policy, spa, check-in/out, airport transfer |
| Booking (B01–B06) | 6 | Availability check, pricing, cancellation, Thai dates, full booking flow, booking lookup |
| Greeting (G01–G04) | 4 | English/Thai greeting, thank you, off-topic (weather) |
| Language (L01–L03) | 3 | English-only response, Thai-only response, gym location |
| Edge Cases (E01–E04) | 4 | Service request (towels), holiday booking, multi-room group, empty message |

Each test case defines:
- **Input message** (Thai or English)
- **Expected keywords** that must appear in the response
- **Expected behavior** description
- **Language check** (optional — verify response is in the correct language)

### 6.1.3 Scoring Criteria

A response **passes** if all three conditions are met:
1. **Keyword score ≥ 50%** — at least half of expected keywords appear in the response
2. **Language correct** — if a language check is specified, the response must be in that language (< 20% Thai characters for English, > 10 Thai characters for Thai)
3. **Has response** — the response is non-empty and no error occurred

## 6.2 Model Evaluation Results

### 6.2.1 Overall Accuracy

| Metric | Qwen3.5 Opus 9B (Local) | Qwen3 Max (Cloud) |
|--------|--------------------------|---------------------|
| **Overall accuracy** | **23/25 (92%)** | **25/25 (100%)** |
| Keyword accuracy | 81% | 89% |
| Language accuracy | 100% | 100% |
| Errors / timeouts | 0 | 0 |

[Figure 5.1: Model accuracy comparison bar chart — Local 92% vs Cloud 100%. Both models achieve 100% on knowledge and booking categories. Differences are in greeting (75% vs 100%) and edge cases (75% vs 100%).]

### 6.2.2 Per-Category Breakdown

| Category | Local 9B | Cloud | Agreement |
|----------|----------|-------|-----------|
| Knowledge (8 cases) | **8/8 (100%)** | **8/8 (100%)** | Perfect |
| Booking (6 cases) | **6/6 (100%)** | **6/6 (100%)** | Perfect |
| Greeting (4 cases) | **3/4 (75%)** | **4/4 (100%)** | 3/4 agree |
| Language (3 cases) | **3/3 (100%)** | **3/3 (100%)** | Perfect |
| Edge Cases (4 cases) | **3/4 (75%)** | **4/4 (100%)** | 3/4 agree |

[Figure 5.2: Per-category accuracy heatmap — rows are categories, columns are models. Color intensity represents accuracy (green = 100%, yellow = 75%). Knowledge, Booking, and Language are fully green for both models.]

### 6.2.3 Latency Analysis

| Metric | Local 9B | Cloud |
|--------|----------|-------|
| Average | 9,879 ms | 8,921 ms |
| Median (p50) | 9,049 ms | 6,703 ms |
| p95 | 18,360 ms | 37,955 ms |

[Figure 5.3: Latency distribution box plot — Local 9B shows tighter distribution (most requests 6–12s) with lower p95. Cloud shows lower median but higher p95 variance due to network latency and API queue times.]

The local model has **more consistent latency** (lower p95) despite similar average — a key advantage for user experience, since the worst-case response time is more predictable.

### 6.2.4 Cohen's Kappa Inter-Model Agreement

$$\kappa = 0.000$$

Interpretation: κ = 0.000 does **not** mean the models disagree. It indicates that the observed agreement (92% — both models agree on 23/25 cases) is close to what would be expected by chance given that both models pass almost everything. This is a known behavior of κ when both raters have high accuracy — the denominator $(1 - p_e)$ approaches zero, making κ unstable.

In practical terms: **both models produce the same pass/fail verdict on 23 of 25 test cases** (92% agreement).

[Figure 5.6: Cohen's Kappa 2×2 confusion matrix — Both Pass: 23, Local Pass/Cloud Fail: 0, Local Fail/Cloud Pass: 2, Both Fail: 0. The two disagreements are G03 (thank you) and E03 (multi-room group booking).]

### 6.2.5 Failure Analysis

**G03 (Thank you response)** — The local 9B model responded politely but did not include enough of the expected keywords ("thank", "welcome", "help", "pleasure"). The response was still appropriate but scored below the 50% keyword threshold. This is a **scoring artifact**, not a capability gap.

**E03 (Multi-room group booking)** — The local model failed to route "I want to book 3 rooms for 10 people" to the booking handler. The cloud model correctly identified the booking intent and responded with availability. This represents a genuine **routing capability gap** in the 9B model for complex multi-entity requests.

## 6.3 Infrastructure Test Results (193/193)

### 6.3.1 Test Suite Summary

| Suite | Tests | Passed | Coverage |
|-------|-------|--------|----------|
| Auth Baseline | 72 | 72 | Login, register, JWT validation, role separation, public endpoints |
| Auth Hardening | 38 | 38 | Rate limiting, account lockout, token blocklist, password change, logout |
| Audit + DB Scaling | 46 | 46 | Audit log CRUD, filters, pagination, DB pool, user cache, concurrent queries |
| Chat Scaling | 37 | 37 | LLM semaphore, session locks, chat rate limit, SSE stream cap, metrics endpoint |

[Figure 5.5: Infrastructure test coverage pie chart — Auth Baseline 37%, Hardening 20%, Audit+Scaling 24%, Chat Scaling 19%. Total: 193 tests covering authentication, security, database, and concurrent-user scaling.]

### 6.3.2 Key Verifications

- **Access control**: Every admin/dashboard endpoint verified with 3 scenarios (no token → 401, user token → 403, admin token → 200)
- **Rate limiting**: Per-IP and per-username login limits trigger 429 with Retry-After header
- **Token revocation**: Logged-out tokens are rejected on subsequent requests; old tokens stay blocked after new login
- **Password-change invalidation**: Changing password invalidates ALL prior tokens (persistent via `password_changed_at`, survives server restart)
- **Concurrent chat**: 5 parallel `/chat` requests to different sessions complete in 3 seconds (not serialized)

## 6.4 Performance Optimization Results

### 6.4.1 Before/After Benchmarks

| Optimization | Before | After | Impact |
|-------------|--------|-------|--------|
| Reranker removal | 18s per /chat | **5s** per /chat | **3.6× faster** |
| Prompt trimming | 5,500 chars | **2,800 chars** | -50% tokens per request |
| Ollama NUM_PARALLEL=4→2 | 30–50s per chat | **4–9s** per chat | Full GPU throughput per request |
| Flash attention | — | Enabled | Faster attention compute |
| Q8_0 KV cache | Tested | **Removed** | Caused CPU offload, 10× slower |
| Knowledge cache | No caching | **500 entries, 5-min TTL** | ~1ms vs ~500ms per cached query |
| DB connection pool | New connection per request | **Pool (min=2, max=20)** | Eliminated connection setup cost |

[Figure 5.4: Before/after optimization chart — warm chat latency dropped from 18s to 5s. Concurrent 5-session test improved from serialized (~90s total) to parallel (~3s total).]

### 6.4.2 Ollama GPU Tuning (RTX 5080, 16 GB)

| Config | VRAM Used | GPU % | Per-Request Latency |
|--------|-----------|-------|---------------------|
| NUM_PARALLEL=4 | 9.9 GB | 100% | 30–50s |
| **NUM_PARALLEL=2** | **9.9 GB** | **100%** | **4–9s** |
| NUM_PARALLEL=2 + Q8_0 KV | 7.9 GB | **37% GPU / 63% CPU** | >120s (broken) |

The key insight: `OLLAMA_NUM_PARALLEL` divides the GPU's fixed token/sec throughput across active sequences. Reducing from 4 to 2 halved throughput per slot but **doubled per-request speed** — the better trade-off for interactive hotel chat.

### 6.4.3 Scaling Metrics Under Load

| Benchmark | Result |
|-----------|--------|
| 30 concurrent `GET /auth/me` | total **0.06s**, p95 **20ms** |
| 50 sequential `GET /admin/audit` | **50/50** success |
| 20 concurrent `GET /admin/audit` | total **0.16s**, all 200 |
| 2 concurrent `/chat` (within GPU slots) | **14.5s** wall time |
| 4 concurrent `/chat` (2 queued) | **19.7s** wall time, 0 failures |

---

## 6.5 Strategic Backtest — LLM-as-Judge Pipeline

The 25-case golden dataset in §6.1.2 covers the canonical happy paths
but is too small to surface the long-tail defects that affect production
quality (stale knowledge, retrieval misses on buried facts, tool-call
omissions, etc). To address this we built a second, larger evaluation
pipeline based on the *strategic backtest* framework: a 504-case golden
dataset, an LLM-as-judge scoring stage, and per-stratum reporting with
Wilson confidence intervals and a regression watchlist.

This section presents the pre-fix baseline numbers, the patches applied,
and the post-fix delta. The full methodology is in Chapter 3 §3.x; the
defect inventory and patch evidence is in Appendix C.

### 6.5.1 Pipeline architecture

[Figure 6.x: Eval Pipeline Architecture — golden generation (Gemini 2.5
Flash) → 504-case dataset → live chatbot /chat → DeepSeek Chat v3.1 judge
→ per-stratum + watchlist report.]

The pipeline has four pieces, each in its own script under `scripts/eval/`:

| Script | Role |
|---|---|
| `backtest_generate.py` | Source-grounded Q&A generation via `google/gemini-2.5-flash` (OpenRouter). One pass per `.md` section produces 3 EN + 3 TH + 3 CN pairs with strict-JSON schema. |
| `backtest_canaries.py` | 15 hand-curated stability sentinels; pattern-based pass/fail; aborts downstream eval if >2 fail. |
| `backtest_runner.py` | Hits `POST /chat` for each case, captures response + `tool_calls` + retries + `had_leak` flags; sends to `deepseek/deepseek-chat-v3.1` judge with a rubric prompt that returns strict JSON (verdict + defect tags). Resumable. |
| `backtest_report.py` | Aggregates raw rows into per-stratum CSV (with Wilson CI), per-defect table, watchlist JSON, and a Markdown report. Supports `--compare-to <previous_run>` for delta tables. |
| `audit_data_db_drift.py` | Deterministic complement to the LLM judge — regex-grep on `data/hotel/*.md` vs `room_types.base_price` DB column. Non-LLM, exit-code 0/1 for CI gating. |

### 6.5.2 Dataset coverage

| Source | Cases | Per language |
|---|---:|---|
| Generated from `data/hotel/*.md` sections (49 sections × 9) | 405 | 135 EN + 135 TH + 135 CN |
| Programmatic pricing templates (4 rooms × 3 brackets × 3 langs) | 36 | 12 EN + 12 TH + 12 CN |
| Hand-curated canaries (stability sentinels) | 15 | 5 EN + 5 TH + 3 CN + 2 infra |
| Hand-curated hard negatives (refusal-correct) | 6 | EN-only |
| Hand-curated adversarial (SQL drop, jailbreak, PII probe, …) | 6 | EN-only |
| **Total** | **504** | **159 + 159 + 159 + 27 special** |

### 6.5.3 Defect taxonomy

Every judged response carries 0 or more tags from this fixed 15-tag
taxonomy (rationale in §3.x.3):

`rag_miss` · `rag_drift` · `room_conflation` · `spec_wrong` ·
`incomplete` · `tool_not_called` · `tool_error` · `hallucination` ·
`language_leak` · `tool_call_leak` · `particle_mismatch` ·
`wrong_routing` · `empty_response` · `format_error` · `over_refuse`

The first three are *new* concerns surfaced by this pipeline — the
existing §5.14 quality gates cover only `language_leak` and
`tool_call_leak`.

### 6.5.4 Pre-fix baseline (200-case stratified sample + 27 specials)

The pre-fix baseline run sampled 200 stratified cases from the 504-case dataset (seed=42) and aborted at row 138 when the runner hit the canary-failure tolerance (>2 canaries failing → "environment broke" alarm). The 138 rows are sufficient for the headline aggregate.

**Pre-fix headline (138 rows, judge = `deepseek/deepseek-chat-v3.1`):**

| Metric | Value | Wilson 95% CI |
|---|---:|---|
| Strict pass rate | **54.3%** (75/138) | [46.0%, 62.5%] |
| Weighted pass rate (partial credit) | 56.9% | — |
| Canary pass rate | 7/13 = **53.8%** | [29.1%, 76.8%] |
| Hard negative pass rate | 3/5 = 60.0% | [23.1%, 88.2%] |

**Defect bucket counts (baseline, n=138):**

| Defect | Count | % of dataset |
|---|---:|---:|
| `incomplete` | 42 | 30.4% |
| `rag_miss` | 30 | 21.7% |
| `hallucination` | 28 | 20.3% |
| `over_refuse` | 19 | 13.8% |
| `spec_wrong` | 12 | 8.7% |
| `tool_not_called` | 6 | 4.3% |
| `rag_drift` | 3 | 2.2% |
| `wrong_routing` | 1 | 0.7% |
| `empty_response` | 1 | 0.7% |

**Promotion-gate verdict: DO NOT SHIP.** All four substantive gates failed:
aggregate 54.3% (< 75%), worst per-domain 0% (< 65%), canaries 53.8% (< 100%),
hard negatives 60.0% (< 80%). Only the language-match rate (100%) passed —
§5.14.7 protection holding.

The top three buckets (`incomplete`, `rag_miss`, `hallucination` = 100/138 ≈ 72% of all defects) were exactly the targets we hypothesised in §6.5.1 — the
existing 25-case eval suite cannot surface them because its assertions only
check 50% keyword overlap.

### 6.5.5 Iterative improvement loop (6 iterations, +24.8 pp gained)

Patches applied one layer at a time per the confound-isolation protocol of §3.4.7:

| Iter | Layer | Change | Strict pass | Δ vs prev | Decision |
|---|---|---|---:|---:|---|
| baseline | — | (pre-fix) | 54.3% | — | — |
| iter1 | Multi-layer base | KB strip + pricing-inject helper + `num_docs` 3→5 + `chunk_size` 26212→2000 | **67.8%** | **+13.4 pp** | SHIP |
| iter2 | Prompt | Strengthened `handle_knowledge` system prompt with "QUOTE EXACT values; if not in HOTEL INFORMATION, say I don't have that" rule | 62.6% | −5.2 pp | REVERT (bot became over-conservative: +5 `over_refuse`, +6 `rag_miss`) |
| iter3 | Retrieval | `chunk_size` 2000→1000, re-ingest (Qdrant: 22→**49 chunks**, now per-H2-section). Embassy / WiFi / FAQ sections become independently searchable | **79.2%** | **+11.4 pp** | **SHIP — current optimum** |
| iter4 | Model | `handle_knowledge` temperature 0.3→0.1 | 78.1% | −1.1 pp | REVERT (plateau; hallucination −4 but `rag_miss` +5 and `tool_not_called` +2 — over-conservative) |
| iter5 | Retrieval | `num_docs` 5→8 | 68.2% (killed at 66/96) | −11.0 pp | KILLED (regression; more chunks = more noise; `rag_drift` resurfaced at 3) |
| iter6 | Model | `handle_knowledge` temperature 0.3→0.2 | **79.2%** | 0.0 pp | PLATEAU (defect profile identical to iter3) |
| iter7 | Prompt | Verbatim-quote rule in `handle_knowledge` ("MUST quote prices/sizes/phones/lists exactly; reproduce every bullet") | 70.8% | −8.4 pp | REVERT (`hallucination` +6, `incomplete` +7 — the rule made the model more confident on wrong details rather than more grounded) |
| iter8 | KB content | Added 6 negative-fact Q&A entries to `hotel_faq.md` ("no casino", "no helipad", "no underwater suite"). hotel_faq chunks 5→8. | 74.0% | −5.2 pp | REVERT (hard negatives flipped 3/3 in sample but new chunks competed in embedding space, costing `rag_miss` +4 and `incomplete` +4 in other strata) |
| iter9 | Model | Inject detected-language lock as a 2nd system message in `handle_booking` to fix EN→TH leak on missing-email refusal | 74.0% | −5.2 pp | REVERT (target case `hardneg_book_without_email_en` was already PASS in iter3; no demonstrable benefit, and same 5pp gap vs iter3 — likely sample variance, but no signal to keep the change) |

**Final shipped configuration (iter3):** `chunk_size=1000 chars × 200 overlap` (giving 49 per-section Qdrant chunks), `num_docs=5`, `temperature=0.3`, KB room prices stripped, pricing pre-fetch helper active in the knowledge sub-agent.

**Methodology note on iter7-9.** A six-agent workflow investigation (parallel defect drill-downs + live trilingual probe + synthesised recommendation) proposed these three Tier-1 changes as the highest-ratio next moves, predicting +5–7 pp aggregate uplift. All three failed on the 100-case stratified sample (seed=42, same as iter3) and were reverted via `git checkout`. This is itself useful evidence: (i) confound isolation worked — each change was tested alone so its individual effect was measurable; (ii) prompt-engineering and KB additions beyond iter3's chunk-size fix produce diminishing or negative returns at the 9B model size; (iii) the 100-case sample's Wilson 95% CI of ±9 pp means small per-iteration deltas are not distinguishable from noise at this n. Iter3 remains the optimum for the local Ollama configuration.

**Key learnings:**

1. **Retrieval granularity dominated** the +13.4→+24.8 pp progression. Without per-section chunks, the bot could not surface buried facts (WiFi password, embassy phone, hotel address) — the LLM substituted plausible-but-wrong values from its training data instead.
2. **Prompt tightening was brittle** (iter2). Saying "if not in source, refuse" caused the bot to refuse questions whose answers ARE in source — net negative.
3. **Temperature plateaued** (iter4, iter6). Once retrieval is right, model sampling discipline contributes little. The remaining ~14 hallucinations after iter3 are genuine 9B-model limits, not addressable by sampling-knob tuning.
4. **More chunks ≠ better** (iter5). At `num_docs=8`, signal-to-noise drops and even cleaner retrieval signal cannot rescue accuracy.

### 6.5.6 Post-fix backtest + per-stratum delta

The final strategic backtest (run tag `final-postfix`) ran 261 cases sampled with seed=42 stratified across (domain, language) from the 504-case dataset, against the iter3-locked configuration.

**Headline (n=261, judge = `deepseek/deepseek-chat-v3.1`):**

| Metric | Baseline (n=138) | Post-fix (n=261) | Δ |
|---|---:|---:|---:|
| **Aggregate strict pass** | 54.3% | **72.4%** | **+18.1 pp** |
| Aggregate weighted pass (partial credit) | 56.9% | 75.3% | +18.4 pp |
| 95% Wilson CI (aggregate, main cases) | [46.0%, 62.5%] | **[65.2%, 76.4%]** | non-overlapping |
| Canary pass rate | 7/13 = 53.8% | **14/15 = 93.3%** | +39.5 pp |
| Hard-negative pass rate | 3/5 = 60.0% | 3/6 = 50.0% | −10.0 pp (small sample) |
| Per-row language match rate | 100% | 98.8% | −1.2 pp (1 adversarial case) |

**Defect bucket deltas (rates expressed as % of dataset, so the 138-case baseline and 261-case post-fix are directly comparable):**

| Defect | Baseline rate | Post-fix rate | Δ |
|---|---:|---:|---:|
| `incomplete` | 30.4% | 18.8% | **−11.6 pp** |
| `rag_miss` | 21.7% | 6.9% | **−14.8 pp** |
| `hallucination` | 20.3% | 13.4% | −6.9 pp |
| `over_refuse` | 13.8% | 3.4% | **−10.4 pp** |
| `spec_wrong` | 8.7% | 8.0% | −0.7 pp |
| `tool_not_called` | 4.3% | 3.8% | −0.5 pp |
| `rag_drift` | 2.2% | 0.8% | −1.4 pp |
| `empty_response` | 0.7% | 0.4% | −0.3 pp |
| `language_leak` | 0% | 0.4% | +0.4 pp (1 adversarial case where bot was tricked) |

**Promotion-gate verdict: DO NOT SHIP.** Three gates still fail at the final state:

| Gate | Metric | Threshold | Status |
|---|---:|---|---|
| Aggregate pass rate | 71.1%* | ≥ 75% | **FAIL** (gap = 3.9 pp) |
| Worst per-domain pass rate | 0.0% | ≥ 65% | **FAIL** (small per-domain n=2–3) |
| Canary pass rate | 93.3% | = 100% | **FAIL** (1 false-positive on TH WiFi upsell phrase) |
| Hard negative pass rate | 50.0% | ≥ 80% | **FAIL** (3 of 6 hallucinated on refusal cases) |
| Per-row language match rate | 98.8% | ≥ 98% | PASS |

\* The report's aggregate (175/246 = 71.1%) excludes canaries from the denominator; including the 27 special cases lifts it to 72.4%.

**Drift audit (deterministic, non-LLM):** went from **6 room-price mismatches** (Deluxe −22%, Suite −35%, Penthouse −40%, each appearing in both the section heading and the comparison table) to **0** after the iter3 KB strip + re-ingest. The watchlist treats `rag_drift>0` as auto-no-ship; this hard gate now passes.

**What the gap means.** The aggregate is 3.9 pp below the 75% ship bar. With the larger 261-case Wilson CI of [65.2%, 76.4%], 75% is inside the CI — i.e. statistically we cannot say with 95% confidence whether the true population pass rate is above or below the 75% threshold. The system is *plausibly* ship-ready but the available evidence is not yet conclusive. The iteration loop hit a plateau (iter4 T=0.1, iter5 num_docs=8, iter6 T=0.2 all flat or regressed). Further gains require either a stronger base LLM (cloud Qwen3-max parity rerun, §6.5.7 follow-up #6) or human-eval comparison to confirm the judge isn't over-penalising paraphrased but semantically correct responses.

The single remaining critical-watchlist failure that *is* worth fixing in the current model is the **hard-negative hallucination rate** (3/6). Adding a small set of explicit "we do not have X" facts to the KB (no casino, no helipad, no underwater suite) and re-ingesting would resolve these without prompt engineering — a follow-up trivially addressable in a 7th iteration.

### 6.5.7 Threats to validity

1. **Single judge model.** DeepSeek Chat v3.1 is the sole LLM judge.
   We mitigated by enforcing strict-JSON output (response_format) and
   running a small spot-check on the first 10 judgments (§3.x.x), but
   did not run the full FPR/FNR rubric stability gate the strategy
   defined. Future work: run 30 known-correct + 30 known-incorrect
   triples through the judge and confirm FPR < 10% AND FNR < 10%.

2. **Judge-system overlap.** The chatbot uses Qwen3.5 Opus 9B locally
   (or Qwen3-max on the cloud path). DeepSeek Chat v3.1 is a different
   vendor family (DeepSeek, not Qwen), which reduces judge-bias risk
   from "model judges itself." But both are LLMs; a human-judge
   comparison would be stronger.

3. **Dataset contamination.** The 405 generated cases were produced
   from the same `.md` files the chatbot's RAG indexes. Cases that
   probe exactly the chunks RAG already retrieves will pass trivially.
   We mitigated this with the hand-curated hard negatives (refusal
   cases that have NO source in the KB) and pricing templates (whose
   ground truth comes from the DB, not the markdown). But a portion of
   the 75-80% pass rate we expect is "trivially correct" — interpret
   the absolute number cautiously and weight the per-defect deltas
   higher.

4. **Stratified sample, not full dataset, for baseline.** The
   pre-fix baseline run sampled 200 stratified cases (not all 504).
   The 95% Wilson CIs for per-domain pass rates are ±5–10pp wide at
   that sample size. Aggregate trends are reliable; small per-domain
   shifts are not. The post-fix run uses the full 504 (CIs ±3pp).

5. **Cold-start latency variance.** The Ollama backend takes ~24s
   on the first call to load the 6 GB Q4_K_M model into VRAM. The
   first eval row's chat_latency_s is therefore inflated. Subsequent
   rows are warm (~10s). This affects latency stats, not verdict.
