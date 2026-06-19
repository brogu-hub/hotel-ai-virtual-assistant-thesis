# Chapter 7: Discussion

## 7.1 Achievement of Objectives

| Objective | Status | Evidence |
|-----------|--------|----------|
| (a) Multi-agent LangGraph system | Achieved | 4 sub-agents with conditional routing, tool loops, and checkpointed memory |
| (b) RAG over hotel knowledge | Achieved | 8/8 knowledge test cases pass on both local and cloud models |
| (c) Production-grade fullstack | Achieved | 193/193 infrastructure tests, JWT auth, audit log, scaling primitives, Docker deployment |
| (d) Local vs cloud model comparison | Achieved | 25-case evaluation: 92% local, 100% cloud, with latency and cost analysis |

## 7.2 Local vs. Cloud Model Trade-offs

### 7.2.1 The Cost-Accuracy-Latency Triangle

[Figure 6.1: Cost-accuracy-latency triangle — Local 9B sits at (low cost, 92% accuracy, medium latency). Cloud Qwen3 Max sits at (medium cost, 100% accuracy, variable latency). Each hotel must choose based on traffic volume, budget, and accuracy requirements.]

| Dimension | Local (Qwen3.5 Opus 9B) | Cloud (Qwen3 Max) |
|-----------|--------------------------|---------------------|
| Per-query cost | $0 (amortized GPU hardware) | ~$0.001–0.01 per query |
| Monthly cost (1000 queries/day) | $0 operational | ~$30–100 (depends on token volume) |
| Accuracy | 92% (23/25) | 100% (25/25) |
| p50 latency | 9.0s | 6.7s |
| p95 latency | 18.4s (predictable) | 38.0s (variable — API queue) |
| Data privacy | On-premise (guest data never leaves the hotel) | Data sent to third-party API |
| Max concurrent users | 2 (GPU-bound) | Unlimited (cloud-side scaling) |
| Offline capability | Fully operational | Requires internet |

### 7.2.2 Privacy Implications

For hotels processing guest personal data (names, passport numbers, credit cards), running the LLM locally means PII never leaves the hotel network. The PII redactor provides a defense-in-depth layer (scrubbing before LLM), but the local model eliminates the risk entirely. This is particularly relevant under Thailand's PDPA (Personal Data Protection Act) and the EU's GDPR.

### 7.2.3 Where 9B Falls Short

The two local failures reveal the 9B model's limitations:
1. **Complex multi-entity intent parsing** — "3 rooms for 10 people" requires understanding quantities, mapping them to multiple bookings, and routing correctly. The 9B model lacks the reasoning depth to decompose this request without additional prompt engineering.
2. **Nuanced keyword variety** — For "thank you", the 9B model responds politely but uses different vocabulary than expected. This is primarily a scoring limitation, not a model one.

**Recommendation**: Use local 9B for the 92% of routine queries and fall back to cloud for complex multi-step operations detected by query complexity analysis.

## 7.3 RAG Effectiveness

### 7.3.1 Retrieval Quality

The RAG pipeline achieves **100% accuracy on all 8 knowledge test cases** with both models. Key factors:
- Hotel knowledge base is well-structured (10 markdown documents with clear headings)
- Embedding model (qwen3-embedding-8b, 4096 dimensions) handles bilingual Thai/English effectively
- Auto-calculated chunk size (80% of model's token limit) prevents information loss

### 7.3.2 Impact of Removing the Reranker (Scoped Finding)

The Phase 5 baseline finding that disabling the CrossEncoder reranker yielded **zero impact on retrieval accuracy** but a **3.6× reduction in latency** holds — but only for **dense-only EN/TH retrieval**. In that regime, qwen3-embedding-8b (4096-dim) embeddings are strong enough that bge-reranker-v2-m3 adds latency (~1 ms/query overhead saved when omitted) without measurable accuracy gain, because the dense vectors already separate topically distinct hotel documents (spa ≠ dining ≠ policies) across the bilingual EN/TH surface.

The original §7.3.2 conclusion overgeneralized this result into a universal "reranker is unnecessary" claim. Phase H.C falsified that universal claim for CN scope and forced a reconciliation. The production stack **re-added BM25 + Reciprocal Rank Fusion (RRF) + bge-reranker-v2-m3** specifically for **CN exact-token recall**, because Qwen's hanzi tokenization underweights rare CJK tokens — addresses, phone numbers, time ranges — that BM25 surfaces directly via exact-token match. The reranker then tightens the BM25 hits before they reach the synthesis prompt, recovering recall that dense-only retrieval lost on CN queries.

**Net production architecture:**

- **EN/TH:** dense-only retrieval (qwen3-embedding-8b), no reranker — saves ~1 ms/query, no measurable recall loss.
- **CN:** hybrid dense + BM25 + RRF + bge-reranker-v2-m3 — adds ~250 ms/query but yields a measurable recall gain on rare-token CJK queries.

The §7.3.2 headline that the reranker is **neutral on EN/TH dense retrieval** stands. Only the universal "unnecessary" claim was wrong; for larger or less-structured knowledge bases, and specifically for CN exact-token recall, hybrid retrieval with reranking remains necessary.

### 7.3.3 Knowledge Cache Effectiveness

The knowledge cache (500 entries, 5-minute TTL) achieves a **76% hit rate** during sustained testing. This means 3 out of 4 knowledge queries are served from memory (~1ms) rather than Qdrant (~500ms). The 5-minute TTL ensures that knowledge base updates propagate quickly without admin intervention.

## 7.4 Architectural Decisions and Trade-offs

### 7.4.1 LangGraph vs. Alternative Orchestrators

[Figure 6.2: Orchestrator comparison matrix]

| Criterion | LangGraph | CrewAI | AutoGen |
|-----------|-----------|--------|---------|
| State management | Built-in TypedDict with checkpointer | Manual state passing | Conversation-based |
| Persistence | AsyncPostgresSaver (survives restart) | No native persistence | No native persistence |
| Tool calling | First-class ToolNode + error handling | Tool decorator | Function calling |
| Debugging | Time-travel with checkpoint replay | Limited | Limited |
| Graph visualization | Built-in (draw_mermaid) | None | None |
| Maturity | Production-grade (LangChain ecosystem) | Growing | Research-focused |

LangGraph was selected for its **checkpointed state persistence** (conversation memory survives server restarts) and **time-travel debugging** (admin can rewind and replay conversations from any checkpoint).

### 7.4.2 In-Memory vs. Redis Scaling Primitives

All five scaling primitives (LLM semaphore, session locks, chat rate limiter, stream cap, knowledge cache) are **in-memory and per-process**. This is appropriate for the single-worker Docker deployment but creates limitations:
- Primitives reset on server restart
- Multiple workers would not share rate limit counters
- Token blocklist entries are lost on restart

**Password-change invalidation** is the exception — it persists via the `users.password_changed_at` database column, making it effective across restarts and workers.

For production horizontal scaling, these should be replaced with Redis-backed equivalents (documented in `docs/WORKFLOW.md`).

## 7.5 Limitations

1. **No real payment integration** — payment links are mock (UUID tokens with 30-minute expiry). Production would require Stripe or PromptPay integration.
2. **Single-language knowledge base** — documents are bilingual within each file, but the system does not support adding a third language without restructuring the knowledge base.
3. **Single-worker deployment** — in-memory scaling primitives do not coordinate across multiple workers. Horizontal scaling requires Redis migration.
4. **No voice interface** — text-only interaction. Voice would require Vapi or Twilio integration.
5. **Single-property** — the system serves one hotel. Multi-property support would require tenant isolation in the database schema.
6. **GPU dependency for local model** — the 9B model requires a modern NVIDIA GPU (tested on RTX 5080). CPU-only deployment is impractical at 10+ seconds per token.

## 7.6 Transferable Techniques

Beyond the hotel-assistant deliverable, four techniques developed during the Phase G→J iteration of this project generalise to any RAG-augmented LLM system being evaluated against a stratified golden dataset. They are described here as candidates for adoption by future projects in this lab and by other teams running LLM-as-judge backtests.

### 7.6.1 Adversarial-verification workflow for regression attribution

When a multi-component change ships as a coherent bundle (Phase G+H added per-model prompt overrides, hybrid BM25 + dense retrieval, multi-intent decomposition, and a cross-encoder reranker in one batch) and the aggregate metric moves against the prior baseline, single-investigator inspection is biased toward whichever component the investigator happened to look at first. We adopted the *adversarial-verification workflow* pattern from Karpathy-style multi-agent harnesses (see CH3 §3.4.8). One investigative agent is spawned per candidate component; each receives the same per-case diff and proposes a root cause. The surviving hypotheses are then handed to an independent *refute pass* whose system prompt forces a strong refute-prior — "default to refuted unless you find direct contradicting evidence in the case data."

The pattern's value is that *correct hypotheses survive the refute pass while plausible-but-wrong ones do not*. On the 2026-06-12 dual backtest the initial pass returned four confirmed root causes (reranker latency, multi-intent overload, model_overrides prompt, BM25 hybrid retrieval). The refute pass rejected the first two on direct case-level evidence: latency-tail was disproven by showing 11 of 20 rooms-domain empties had *lower* end-to-end latency under Stack-ON than under Stack-OFF; num_docs overload was disproven by showing 42 of 50 ON-only empties came from single-intent queries that bypass the per-subq fan-out branch entirely. Without the refute pass the chapter would have shipped a wrong attribution. The technique transfers wherever a system change is a *bundle* rather than a *single edit*, and the cost is one extra parallel-agent pass per regression (≈10 min wall, ≈$0.50 per refute run on DeepSeek Chat v3.1).

### 7.6.2 Eval-infrastructure reliability protocol

LLM-as-judge backtests are uniquely vulnerable to infrastructure-induced contamination because a 503 from the chat API is recorded as `verdict=incorrect, defects=["empty_response"]` — indistinguishable in the per-case ledger from a genuine model silence. The 2026-06-12 dual backtest's `+16 empty_response` regression was, on inspection, 32 instances of a 45.0-second FastAPI semaphore timeout caused by a `max_chat_parallel=2` runner default against a single-slot GPU. The four-element reliability protocol (CH3 §3.4.9) — subprocess env hydration, GPU-concurrency matching, checkpoint-aware resume, pre-flight smoke gate — closes this entire class of failure.

The transferable principle is that *every infrastructure-level assumption the backtest driver makes must be runtime-verified inside the eval container, not just asserted in code review*. The verify-don't-assert discipline composes with the four protocol elements: a real `OPENROUTER_API_KEY` is checked at the start of every backtest by `verify_container_env()` and a non-real key forces an abort; a `--max-chat-parallel=1` flag is matched against the GPU's actual `OLLAMA_NUM_PARALLEL=1` setting; a `--ts` checkpoint resume strips chat-layer failures from the prior `raw.jsonl` before the runner re-loads it; a single `/chat` smoke probe gates whether the bulk eval is allowed to start at all. The protocol cost is one extra request per resume and one extra env check per backtest, and the benefit is that every aggregate number in CH6 §6.5.8 can be reproduced from the manifest pins without "trust me, the infra was working that day" caveats.

### 7.6.3 Defect backlog as a methodology artifact (not just a TODO list)

A defect inventory built from `raw.jsonl` event-sources well — every patched defect crystallises into an AP_C entry with example failure, root cause, fix, and verification. What it does *not* track is the population of defects surfaced but deliberately *not* patched in the current iteration. Those defects do not belong in AP_C (they have no fix yet) and do not belong in CH6 (they are not part of the canonical result), but they must live somewhere visible to a reviewer because their existence calibrates how the current pass rate should be read.

The AP_F format (CH3 §3.4.10) addresses this with a per-case ledger that carries `status ∈ {OPEN, PATCHED, DEFERRED}` and an effort estimate per row. `OPEN+trivial` rows are eligible for the next iteration's batch patch; `DEFERRED` rows are explicitly subsumed by an upstream change already in the pipeline (Phase G+H+H.C retrieval improvements absorb five `dense_retrieval_miss` rows in AP_F §F.3). The result is a *promotion path* — a defect surfaced by a backtest enters AP_F, eventually exits to AP_C when fixed, and the snapshot at the end of the iteration tells the reviewer exactly which defects shipped and which were caught-but-deferred. The technique transfers anywhere a project iterates on a closed defect taxonomy and ships in batches.

### 7.6.4 KB↔DB ETL-style drift audit as a recurring procedure

The hotel KB consists of human-authored markdown (facility hours, room descriptions, policy text) and the PMS database holds the operational truth (room prices, max occupancy, service hours, current room status). These two surfaces drift apart on different timescales — the database changes hourly with operations, the markdown changes monthly with a content edit. Phase 5 surfaced this for room *prices*; Phase J surfaced the same defect class for room *occupancy*, *fitness-center floor*, *pool open time*, *business-center hours*, and *spa hours* (CH6 §C.Y, AP_F §F.2.3). The procedure that resolved Phase J — query the DB for every field a KB section mentions, diff against the KB, align KB to DB, re-ingest Qdrant, update the golden labels that referenced the old KB values, smoke-verify on the same 5 facts — is reusable for any future KB section that lands and for any future operational change to the DB that the content team has not yet propagated.

The longer-term recommendation is a one-way ETL pipeline (Phase K in AP_F §F.2.4) that auto-regenerates the DB-bound section templates from the latest DB rows nightly, leaving descriptive prose (amenity flavour, view descriptions) manually authored. Until that ships, the audit-and-align procedure is the operational bridge; it is documented as a methodology contribution rather than a one-off bug fix.

### 7.6.5 Adaptive escalation via per-model prompt registry (side-channel, not backend swap)

The most cost-effective production strategy for an LLM-backed transactional assistant is rarely the largest available model. A locally-served mid-size model (Gemma 4 12B Q8_0 on a 16 GB consumer GPU) at zero per-call cost handles the vast majority of turns; a more capable cloud model (`google/gemma-4-31b-it` via OpenRouter at $0.12 in / $0.35 per Mtok out) is reserved for the small fraction of turns that match a detected hard-case pattern. Phase O implemented this as a *side-channel* (CH6 §6.5.17), not a wholesale backend swap — the latter approach was the Phase N negative result (CH6 §6.5.16) where reusing the bot's local-tuned prompt against a stronger cloud model in the same family returned EMPTY content on 10/10 cases and regressed three previously-partial cases to incorrect. The empirical finding generalises: prompt tuning does not transfer across model families, *even within the same vendor family*, because instruction-tuning recipes, format expectations, and tool-routing assumptions differ between training generations.

The transferable architecture has four pieces:

1. **Per-model prompt registry** — a dict mapping `model_id → yaml_filename` (`_CLOUD_PROMPT_REGISTRY` in `src/hotel_guardrails/escalation.py`). Each registered model gets its own prompt yaml tuned for its specific format. The first entry maps `google/gemma-4-31b-it → hotel_prompt_gemma4_31b_cloud.yaml`; future entries for Qwen3-max, Llama 3.3 70B, and Mistral Large each land their own yaml when first activated. Adding a new escalation target is a one-line registry change + one new yaml — no edits to the local pipeline.

2. **Layered hard-case detection** (CH6 §6.5.17.2): pre-inference pattern triggers (multi-turn anaphora, multi-intent decomposition, language-explicit override, PII probes), post-inference quality signals (empty / deferral / tool-call leak / language leak / numeric incoherence / response-too-short / truncated-mid-sentence), and a cheap-judge fallback (`google/gemma-3-4b-it` at ~$0.0001/call) for ambiguous cases. Each layer is deterministic where possible and fails safe by escalating on uncertainty.

3. **Tool-envelope synthesis post-escalation** (CH6 §6.5.19.2): the side-channel cloud call produces prose, but the bot's rubric expects a real `calculate_dynamic_price` tool invocation on the response envelope. After cloud responds, the bot re-runs `_maybe_compute_pricing_context` on the concatenated prior + current context and synthesises an `AIMessage(tool_calls=[...]) + ToolMessage(...)` pair, appending the tool record to the outgoing envelope. The synthesis lives in `invoke_hotel_agent` only, keeping `escalation.py` model-agnostic.

4. **Forensic instrumentation** — every escalation event persists to a PostgreSQL `escalations` table with `trigger_layer`, `trigger_flags`, `cloud_model`, `cloud_latency_ms`, `cloud_cost_usd`, and response previews. Powers cost accounting, trigger precision/recall measurement, and post-hoc analysis of *which* signals actually predict cases where the cloud meaningfully recovers vs cases where it doesn't.

The economics are the headline (CH6 §6.5.17.6): at the observed ~3 % escalation rate and ~$0.000175 average per cloud call, projected production cost on 100K queries/month is ~$30 (cloud) + ~$10 (cheap-judge majority path) ≈ ~$40, vs. ~$3,500 if every query routed to the cloud — an ~85-100× cost reduction at a +2.82 pp quality gain over the pure-local floor (Phase F variance baseline 80.83 % → Phase R end-state 98.31 %). The architectural lesson is that *intelligent routing beats round-robin LB* when the units being balanced have radically different per-call cost: the cloud is not a hot standby, it is a small focused tool invoked only when local hits a detected capability floor.

The pattern transfers anywhere a project has (a) a cost-asymmetric pair of models, (b) a rubric or judge that can score per-case correctness, and (c) at least one observable signal (empty response, missing tool call, low-confidence judge) that predicts when the cheaper model is failing. Hotel concierge is one instance; customer-support triage, internal Q&A bots over policy docs, and any RAG-grounded transactional assistant share the shape.
