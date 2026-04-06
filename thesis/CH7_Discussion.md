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

### 7.3.2 Impact of Removing the Reranker

Disabling the CrossEncoder reranker had **zero impact on retrieval accuracy** but **3.6× reduction in latency**. This finding contradicts the general RAG literature recommendation to always rerank — but is explained by the domain characteristics:
- Only 10 documents in the knowledge base (not thousands)
- Documents are topically distinct (spa ≠ dining ≠ policies)
- The embedding model is already bilingual-optimized

For larger or less-structured knowledge bases, reranking would likely be necessary.

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
