# Chapter 5: Testing and Evaluation

## 5.1 Evaluation Methodology

### 5.1.1 Test Design

The evaluation strategy uses two complementary approaches:

1. **Model evaluation** — 25 test cases covering hotel-domain tasks, scored for accuracy against expected behaviors
2. **Infrastructure testing** — 193 automated assertions verifying auth, security, scaling, and API correctness

### 5.1.2 Golden Dataset (25 Test Cases)

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

### 5.1.3 Scoring Criteria

A response **passes** if all three conditions are met:
1. **Keyword score ≥ 50%** — at least half of expected keywords appear in the response
2. **Language correct** — if a language check is specified, the response must be in that language (< 20% Thai characters for English, > 10 Thai characters for Thai)
3. **Has response** — the response is non-empty and no error occurred

## 5.2 Model Evaluation Results

### 5.2.1 Overall Accuracy

| Metric | Qwen3.5 Opus 9B (Local) | Qwen3 Max (Cloud) |
|--------|--------------------------|---------------------|
| **Overall accuracy** | **23/25 (92%)** | **25/25 (100%)** |
| Keyword accuracy | 81% | 89% |
| Language accuracy | 100% | 100% |
| Errors / timeouts | 0 | 0 |

[Figure 5.1: Model accuracy comparison bar chart — Local 92% vs Cloud 100%. Both models achieve 100% on knowledge and booking categories. Differences are in greeting (75% vs 100%) and edge cases (75% vs 100%).]

### 5.2.2 Per-Category Breakdown

| Category | Local 9B | Cloud | Agreement |
|----------|----------|-------|-----------|
| Knowledge (8 cases) | **8/8 (100%)** | **8/8 (100%)** | Perfect |
| Booking (6 cases) | **6/6 (100%)** | **6/6 (100%)** | Perfect |
| Greeting (4 cases) | **3/4 (75%)** | **4/4 (100%)** | 3/4 agree |
| Language (3 cases) | **3/3 (100%)** | **3/3 (100%)** | Perfect |
| Edge Cases (4 cases) | **3/4 (75%)** | **4/4 (100%)** | 3/4 agree |

[Figure 5.2: Per-category accuracy heatmap — rows are categories, columns are models. Color intensity represents accuracy (green = 100%, yellow = 75%). Knowledge, Booking, and Language are fully green for both models.]

### 5.2.3 Latency Analysis

| Metric | Local 9B | Cloud |
|--------|----------|-------|
| Average | 9,879 ms | 8,921 ms |
| Median (p50) | 9,049 ms | 6,703 ms |
| p95 | 18,360 ms | 37,955 ms |

[Figure 5.3: Latency distribution box plot — Local 9B shows tighter distribution (most requests 6–12s) with lower p95. Cloud shows lower median but higher p95 variance due to network latency and API queue times.]

The local model has **more consistent latency** (lower p95) despite similar average — a key advantage for user experience, since the worst-case response time is more predictable.

### 5.2.4 Cohen's Kappa Inter-Model Agreement

$$\kappa = 0.000$$

Interpretation: κ = 0.000 does **not** mean the models disagree. It indicates that the observed agreement (92% — both models agree on 23/25 cases) is close to what would be expected by chance given that both models pass almost everything. This is a known behavior of κ when both raters have high accuracy — the denominator $(1 - p_e)$ approaches zero, making κ unstable.

In practical terms: **both models produce the same pass/fail verdict on 23 of 25 test cases** (92% agreement).

[Figure 5.6: Cohen's Kappa 2×2 confusion matrix — Both Pass: 23, Local Pass/Cloud Fail: 0, Local Fail/Cloud Pass: 2, Both Fail: 0. The two disagreements are G03 (thank you) and E03 (multi-room group booking).]

### 5.2.5 Failure Analysis

**G03 (Thank you response)** — The local 9B model responded politely but did not include enough of the expected keywords ("thank", "welcome", "help", "pleasure"). The response was still appropriate but scored below the 50% keyword threshold. This is a **scoring artifact**, not a capability gap.

**E03 (Multi-room group booking)** — The local model failed to route "I want to book 3 rooms for 10 people" to the booking handler. The cloud model correctly identified the booking intent and responded with availability. This represents a genuine **routing capability gap** in the 9B model for complex multi-entity requests.

## 5.3 Infrastructure Test Results (193/193)

### 5.3.1 Test Suite Summary

| Suite | Tests | Passed | Coverage |
|-------|-------|--------|----------|
| Auth Baseline | 72 | 72 | Login, register, JWT validation, role separation, public endpoints |
| Auth Hardening | 38 | 38 | Rate limiting, account lockout, token blocklist, password change, logout |
| Audit + DB Scaling | 46 | 46 | Audit log CRUD, filters, pagination, DB pool, user cache, concurrent queries |
| Chat Scaling | 37 | 37 | LLM semaphore, session locks, chat rate limit, SSE stream cap, metrics endpoint |

[Figure 5.5: Infrastructure test coverage pie chart — Auth Baseline 37%, Hardening 20%, Audit+Scaling 24%, Chat Scaling 19%. Total: 193 tests covering authentication, security, database, and concurrent-user scaling.]

### 5.3.2 Key Verifications

- **Access control**: Every admin/dashboard endpoint verified with 3 scenarios (no token → 401, user token → 403, admin token → 200)
- **Rate limiting**: Per-IP and per-username login limits trigger 429 with Retry-After header
- **Token revocation**: Logged-out tokens are rejected on subsequent requests; old tokens stay blocked after new login
- **Password-change invalidation**: Changing password invalidates ALL prior tokens (persistent via `password_changed_at`, survives server restart)
- **Concurrent chat**: 5 parallel `/chat` requests to different sessions complete in 3 seconds (not serialized)

## 5.4 Performance Optimization Results

### 5.4.1 Before/After Benchmarks

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

### 5.4.2 Ollama GPU Tuning (RTX 5080, 16 GB)

| Config | VRAM Used | GPU % | Per-Request Latency |
|--------|-----------|-------|---------------------|
| NUM_PARALLEL=4 | 9.9 GB | 100% | 30–50s |
| **NUM_PARALLEL=2** | **9.9 GB** | **100%** | **4–9s** |
| NUM_PARALLEL=2 + Q8_0 KV | 7.9 GB | **37% GPU / 63% CPU** | >120s (broken) |

The key insight: `OLLAMA_NUM_PARALLEL` divides the GPU's fixed token/sec throughput across active sequences. Reducing from 4 to 2 halved throughput per slot but **doubled per-request speed** — the better trade-off for interactive hotel chat.

### 5.4.3 Scaling Metrics Under Load

| Benchmark | Result |
|-----------|--------|
| 30 concurrent `GET /auth/me` | total **0.06s**, p95 **20ms** |
| 50 sequential `GET /admin/audit` | **50/50** success |
| 20 concurrent `GET /admin/audit` | total **0.16s**, all 200 |
| 2 concurrent `/chat` (within GPU slots) | **14.5s** wall time |
| 4 concurrent `/chat` (2 queued) | **19.7s** wall time, 0 failures |
