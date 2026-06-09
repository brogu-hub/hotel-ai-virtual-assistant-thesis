# Chapter 3: Methodology

## 3.1 Research Approach

This thesis follows the **Design Science Research (DSR)** methodology, which is appropriate for information systems research where the goal is to create and evaluate an artifact — in this case, a hotel AI virtual assistant. The DSR framework consists of three cycles: relevance (identifying the real-world problem), design (building the artifact), and rigor (grounding in existing knowledge and evaluation).

The development process combines:
1. **Literature-driven design** — technology choices and architecture patterns are grounded in published research (Chapter 2)
2. **Iterative prototyping** — the system was built incrementally over 16 weeks with continuous testing at each stage
3. **Empirical evaluation** — the final system is evaluated against a golden dataset with quantitative metrics (Chapter 5)

## 3.2 Development Process

### 3.2.1 Agile Iteration Cycle

Development followed a modified agile process with 2-week sprints:

```
Sprint cycle (repeated 8 times):
  1. Define sprint goal (e.g., "LangGraph multi-agent routing")
  2. Implement features
  3. Write automated tests
  4. Evaluate against test cases
  5. Optimize based on results
  6. Document in WORKFLOW.md
```

Each sprint produced a working increment deployed via Docker Compose. The git history records the progression:

| Sprint | Period | Deliverable | Tests Added |
|--------|--------|-------------|-------------|
| 1 | Jan W1–2 | Literature review, technology selection | — |
| 2 | Jan W3–Feb W2 | FastAPI server, PostgreSQL schema, Qdrant RAG | RAG accuracy tests |
| 3 | Feb W3–Mar W1 | LangGraph multi-agent state machine, hotel tools | Workflow integration tests |
| 4 | Mar W2–3 | Next.js frontend, chat SSE, admin dashboard | — |
| 5 | Mar W4–Apr W1 | JWT auth, RBAC, rate limiting, audit log | 72 + 38 auth tests |
| 6 | Apr W1 | Chat scaling (LLM semaphore, session locks, cache) | 46 + 37 scaling tests |
| 7 | Apr W1–2 | Ollama GPU tuning, reranker removal, prompt optimization | Performance benchmarks |
| 8 | Apr W2 | Model evaluation (25 cases), thesis writing | Evaluation framework |

### 3.2.2 Version Control and Documentation

All code changes were tracked in Git with conventional commit messages (`feat:`, `fix:`, `perf:`, `docs:`). Architecture decisions were documented in `docs/WORKFLOW.md` as they were made, not retroactively — ensuring the documentation reflects the actual reasoning at each decision point.

## 3.3 Technology Selection

### 3.3.1 Selection Criteria

Technologies were selected based on five criteria:

| Criterion | Weight | Rationale |
|-----------|--------|-----------|
| **Fitness for hotel domain** | High | Must support bilingual (Thai/English), real-time booking, multi-turn conversations |
| **Local deployment capability** | High | Hotel data privacy — guest PII should stay on-premise |
| **Open-source availability** | Medium | Reproducibility for thesis evaluation |
| **Community maturity** | Medium | Stability, documentation quality, bug resolution speed |
| **Integration compatibility** | Medium | Components must work together in a Docker Compose stack |

### 3.3.2 LLM Framework Selection

[Figure 3.1: LLM orchestration framework comparison matrix]

| Criterion | LangGraph | CrewAI | AutoGen | LangChain (plain) |
|-----------|-----------|--------|---------|--------------------|
| State persistence | ✅ AsyncPostgresSaver | ❌ Manual | ❌ Manual | ❌ Manual |
| Cyclic tool loops | ✅ Native graph edges | ⚠️ Limited | ⚠️ Limited | ❌ Sequential |
| Time-travel debug | ✅ Checkpoint replay | ❌ | ❌ | ❌ |
| Sub-agent routing | ✅ Conditional edges | ✅ Role-based | ✅ Conversation | ⚠️ Router chain |
| Production maturity | ✅ LangChain ecosystem | ⚠️ Growing | ⚠️ Research | ✅ Mature |

**Decision**: LangGraph was selected for its checkpointed state persistence (conversation memory survives server restarts), native cyclic tool loops (booking sub-agent can call tools repeatedly until done), and time-travel debugging (admin can rewind conversations). These features are critical for a hotel booking system where conversations span multiple turns and must be recoverable.

### 3.3.3 LLM Model Selection

| Criterion | Qwen3.5 Opus 9B (Local) | Qwen3 Max (Cloud) |
|-----------|--------------------------|---------------------|
| Deployment | On-premise (Ollama, single GPU) | OpenRouter API |
| Cost per query | $0 (amortized hardware) | ~$0.001–0.01 |
| Bilingual (Thai/English) | ✅ Native | ✅ Native |
| Tool calling | ✅ Structured JSON | ✅ Structured JSON |
| Context window | 4,096 tokens (practical) | 262,144 tokens |
| Data privacy | ✅ On-premise | ❌ Third-party API |
| Concurrent capacity | 2 (GPU-bound) | Unlimited |

**Decision**: Both models are deployed. The local 9B model serves as the primary backend (zero cost, on-premise privacy) with cloud Qwen3 Max as a runtime-switchable fallback for high-traffic periods or complex multi-step queries that exceed the 9B model's reasoning capacity.

### 3.3.4 Vector Database Selection

| Criterion | Qdrant | Milvus | Pinecone | ChromaDB |
|-----------|--------|--------|----------|----------|
| Open-source | ✅ | ✅ | ❌ (cloud only) | ✅ |
| Docker-native | ✅ | ⚠️ (complex) | ❌ | ✅ |
| Performance | ✅ Rust-based | ✅ | ✅ | ⚠️ Python |
| Bilingual support | ✅ (model-dependent) | ✅ | ✅ | ✅ |

**Decision**: Qdrant was selected for its Docker-native single-container deployment, Rust-based performance, and straightforward REST API. The original NVIDIA blueprint used Milvus, but Qdrant's simpler deployment model was preferred for the self-contained Docker stack.

### 3.3.5 Frontend Framework Selection

| Criterion | Next.js 15 | Remix | Vite + React | Vue 3 |
|-----------|------------|-------|--------------|-------|
| Server-Side Rendering | ✅ RSC native | ✅ | ❌ (SPA only) | ✅ (Nuxt) |
| API route proxy | ✅ Built-in | ✅ | ❌ | ⚠️ |
| TypeScript | ✅ First-class | ✅ | ✅ | ✅ |
| Enterprise UI library | ✅ Ant Design | ✅ | ✅ | ⚠️ (less mature) |
| SSE streaming support | ✅ | ✅ | ✅ | ✅ |

**Decision**: Next.js 15 with App Router was selected for its built-in API route proxy (eliminating CORS issues between frontend and backend), React Server Components for fast initial page loads, and first-class TypeScript support. Ant Design 5 was selected as the UI component library for its enterprise-grade components (60+ including Table, Form, Modal, Descriptions) and Thai locale support.

### 3.3.6 Authentication Approach

| Approach | Stateless JWT | Session cookies | OAuth 2.0 |
|----------|--------------|-----------------|-----------|
| Server-side state | None | Redis/DB session store | Token + provider |
| Scalability | ✅ Horizontal (no shared state) | ⚠️ Requires session store | ✅ |
| Implementation complexity | Low | Medium | High |
| Logout granularity | ⚠️ Requires blocklist | ✅ Delete session | ✅ |
| Suitable for demo/thesis | ✅ | ✅ | ❌ (over-engineered) |

**Decision**: Stateless JWT with HS256 was selected for its simplicity and horizontal scalability. The known JWT limitation (no instant revocation) was mitigated by adding a `jti`-based in-memory blocklist and persistent `password_changed_at` invalidation (Chapter 4, Section 4.5).

## 3.4 Evaluation Methodology

### 3.4.1 Evaluation Framework

The system is evaluated at two levels:

1. **Functional correctness** — does the chatbot produce correct, relevant, bilingual responses to hotel-domain queries?
2. **Non-functional quality** — does the system meet latency, concurrency, security, and reliability requirements?

### 3.4.2 Golden Dataset Design

A golden dataset of **25 test cases** was designed to cover the full range of hotel chatbot interactions:

| Category | Cases | Design Rationale |
|----------|-------|-------------------|
| Knowledge (K01–K08) | 8 | Covers all 10 knowledge documents; includes both Thai and English queries |
| Booking (B01–B06) | 6 | Full CRUD lifecycle: check, price, cancel, create, lookup; includes date parsing |
| Greeting (G01–G04) | 4 | Hello, thank you, off-topic; tests conversational appropriateness |
| Language (L01–L03) | 3 | Explicit language detection verification (EN→EN, TH→TH) |
| Edge Cases (E01–E04) | 4 | Service request, holiday booking, multi-room group, empty message |

Each test case specifies:
- **Input message** — the guest's query (Thai or English)
- **Expected keywords** — terms that must appear in a correct response
- **Expected behavior** — natural language description of the correct action
- **Language check** — optional flag to verify response language matches input

### 3.4.3 Scoring Methodology

A response is scored as **PASS** if all three conditions are met:

1. **Keyword accuracy ≥ 50%** — at least half of expected keywords appear (case-insensitive)
2. **Language correctness** — if a language check is specified, response must be in the correct language (measured by Thai character ratio: < 20% for English, > 10 Thai characters for Thai)
3. **Response completeness** — non-empty response with no HTTP error

This scoring is intentionally conservative: a response can be helpful and correct but still fail if it uses synonyms not in the keyword list. The 50% threshold accommodates this — a response that captures the key facts will pass even without exact keyword matches.

### 3.4.4 Inter-Model Agreement (Cohen's Kappa)

To quantify how consistently the local and cloud models handle the same test cases, **Cohen's Kappa (κ)** is computed:

$$\kappa = \frac{p_o - p_e}{1 - p_e}$$

where:
- $p_o$ = proportion of test cases where both models agree (both pass or both fail)
- $p_e$ = expected agreement by chance, given each model's individual pass rate

| κ Range | Interpretation |
|---------|----------------|
| < 0.20 | Poor agreement |
| 0.21–0.40 | Fair |
| 0.41–0.60 | Moderate |
| 0.61–0.80 | Substantial |
| 0.81–1.00 | Almost perfect |

### 3.4.5 Infrastructure Testing Strategy

Beyond model evaluation, the system's non-functional properties are verified through **193 automated assertions** organized into four test suites:

| Suite | Focus | Strategy |
|-------|-------|----------|
| Auth Baseline (72) | JWT correctness, role separation, public endpoint access | Every endpoint × {no-auth, user, admin} |
| Auth Hardening (38) | Rate limiting, lockout, logout, password invalidation | Deliberate attack scenarios (brute force, token reuse) |
| Audit + Scaling (46) | Audit log completeness, DB pool, user cache | Filter/pagination queries, concurrent load |
| Chat Scaling (37) | LLM semaphore, session locks, rate limit, metrics | Burst traffic simulation, parallel session tests |

### 3.4.6 Performance Benchmarking

Performance is measured across three dimensions:

1. **Latency** — per-request response time (average, p50, p95) for both local and cloud models
2. **Throughput** — number of concurrent chat sessions the system can serve without degradation
3. **Resource efficiency** — GPU VRAM usage, DB connection pool utilization, knowledge cache hit rate

Benchmarks are run on the target deployment hardware (RTX 5080, 16 GB VRAM) to produce actionable capacity planning data. Before/after measurements are taken for each optimization (reranker removal, prompt trimming, Ollama parallelism tuning) to quantify the impact of individual changes.

### 3.4.7 Strategic Backtest Methodology (LLM-as-Judge)

The 25-case golden dataset in §3.4.2 is sufficient for the canonical happy paths but cannot surface long-tail defects such as knowledge-base drift, retrieval misses on facts buried deep in a chunk, or tool calls omitted on routing edge cases. To address this we adopted a *strategic backtest* methodology adapted from the Treasury RAG evaluation framework. The pipeline is documented end-to-end in Chapter 6 §6.5 and Appendix C; this section gives the methodological rationale.

**Two-phase loop.** The methodology combines a fast *iterative improvement loop* (60–160 case stratified samples per iteration, single-layer patches, plateau detection) with a *strategic backtest* (full 504-case dataset, per-stratum Wilson 95% CI, regression watchlist, promotion gate). Iteration is bounded by either a defect-bucket plateau (≤ 1 pp aggregate improvement across two consecutive runs) or an OpenRouter spend cap.

**Coverage matrix.** The 504-case dataset is stratified across `domain × language × complexity × register × input_completeness`. Every cell carries ≥ 5 cases (sparse cells acceptable; empty cells block release). 159 cases per language (EN/TH/CN) plus 27 special cases: 15 hand-curated canaries (stability sentinels with deterministic pass/fail), 6 hard negatives (questions where the *correct* answer is refusal — e.g. "does the hotel have a casino?"), and 6 adversarial probes (SQL drop, prompt injection, PII leak, language provocation).

**Source-grounded Q&A generation.** The main 405 cases are generated by `google/gemini-2.5-flash` (via OpenRouter), prompted with the exact text of one knowledge-base section at a time and required to produce strict-JSON Q&A pairs that include `expected_facts`, `must_contain_any`, `must_not_contain` tokens, and a defect category being tested. The 36 dynamic-pricing cases are *not* LLM-generated — they are built deterministically from `room_types.base_price` (DB) × the four price brackets in `_calculate_dynamic_multiplier()`, so the ground truth and the system under test share their arithmetic source.

**LLM-as-judge with structured output.** Each chatbot response is graded by `deepseek/deepseek-chat-v3.1` (via OpenRouter). DeepSeek was chosen over Gemini 2.5 Pro for three reasons: (i) cost — ~10 × cheaper per judged token (~$0.21 per full 504-case run), (ii) vendor diversity from the chatbot (Qwen family), reducing judge-bias risk, and (iii) reliable structured-JSON output. The judge prompt enforces a six-dimension rubric (factual_accuracy, language_match, tool_invocation, no_hallucination, completeness, safety) with a hallucination override and returns a list of applicable defect tags from a fixed 15-tag taxonomy.

**Defect taxonomy.** Every judged response carries 0 or more tags from: `rag_miss`, `rag_drift`, `room_conflation`, `spec_wrong`, `incomplete`, `tool_not_called`, `tool_error`, `hallucination`, `language_leak`, `tool_call_leak`, `particle_mismatch`, `wrong_routing`, `empty_response`, `format_error`, `over_refuse`. The taxonomy is closed (no `other` bucket beyond `misc`) so cross-run aggregation is unambiguous.

**Statistical reporting.** All pass rates are reported with a Wilson 95% confidence interval (preferred over naive ±√(p(1−p)/n) at small n and near 0/1). The per-stratum table breaks scores by domain × language, with a separate `Δ vs previous` column for delta tracking. The aggregate pass rate alone is *not* a ship signal — every per-domain cell must meet a minimum threshold (≥65% to ship; the user-set "highest accuracy" loop pushes ≥80%).

**Confound isolation.** Each iteration changes exactly one layer (`retrieval | prompt | model | KB content`); model swaps that require prompt adjustments are recorded as two separate iterations (model-only delta, then prompt-only delta). Patch logs include an *expected Δ* and an *actual Δ* column — a wrong hypothesis is still data.

**Regression watchlist.** Independent of the iteration's top bucket, every run checks a fixed list of regressions: any drift between `data/hotel/*.md` and `room_types.base_price` (auto no-ship), any CJK leak in EN/TH replies (regression of §5.14.7), any hallucination on hard negatives, and the `tool_call_leak` rate (regression of §5.14.2). A critical-severity failure on the watchlist forces a no-ship verdict regardless of aggregate.

**Threats to validity.** See Chapter 6 §6.5.7 — single judge model, judge–system vendor overlap mitigation, dataset contamination on KB-derived cases, sample-size effects on baseline CIs, and cold-start latency variance are all explicitly documented as limitations rather than hidden.

## 3.5 Ethical Considerations

### 3.5.1 Guest Data Privacy

Guest conversations may contain personally identifiable information (credit card numbers, passport numbers, phone numbers). The system mitigates privacy risks through:
- **PII redaction** — regex-based scrubbing before LLM processing (Chapter 4, Section 4.5.3)
- **Local LLM deployment** — guest data never leaves the hotel network when using Ollama
- **Audit logging** — every admin access to guest conversations is recorded with actor identity, IP, and timestamp

### 3.5.2 AI Transparency

The chatbot does not impersonate a human. System messages clearly indicate when a human staff member takes over (`[System] Hotel staff has joined the conversation`), and the AI identifies itself as a virtual assistant in greeting templates. Responses are grounded in the RAG knowledge base rather than hallucinated — the prompt explicitly instructs "DO NOT answer from memory; search the knowledge base first."

### 3.5.3 Bias Mitigation

The bilingual design ensures equal service quality for Thai and English speakers. Language detection is based on the guest's latest message (not assumptions about nationality), and the evaluation dataset includes balanced Thai and English test cases to verify parity.
