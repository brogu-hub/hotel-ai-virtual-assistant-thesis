# Appendix A: Test Results and Development Timeline

## A.1 Model Evaluation — Full 25-Case Results

### Test Configuration
- **Local model**: Qwen3.5 Opus 9B (fredrezones55/qwen3.5-opus:9b) on Ollama, RTX 5080 16GB
- **Cloud model**: Qwen3 Max (qwen/qwen3-max) on OpenRouter
- **Evaluation script**: `scripts/eval_model_comparison.py`
- **Scoring**: keyword matching (≥50% threshold), language detection, response completeness

### Results Table

| ID | Category | Language | Input | Local | Cloud | Local Latency | Cloud Latency |
|----|----------|----------|-------|-------|-------|---------------|---------------|
| K01 | Knowledge | EN | What time is breakfast? | PASS | PASS | 34,624ms | 6,457ms |
| K02 | Knowledge | EN | What is the WiFi password? | PASS | PASS | 9,049ms | 5,527ms |
| K03 | Knowledge | TH | สระว่ายน้ำเปิดกี่โมง | PASS | PASS | 10,532ms | 8,176ms |
| K04 | Knowledge | EN | Do you allow pets? | PASS | PASS | 8,267ms | 7,591ms |
| K05 | Knowledge | EN | What is your cancellation policy? | PASS | PASS | 8,008ms | 8,727ms |
| K06 | Knowledge | EN | Where is the spa and what treatments do you offer? | PASS | PASS | 9,822ms | 13,774ms |
| K07 | Knowledge | EN | What time is check-in and check-out? | PASS | PASS | 9,677ms | 6,312ms |
| K08 | Knowledge | TH | มีบริการรถรับส่งสนามบินไหม | PASS | PASS | 10,392ms | 13,311ms |
| B01 | Booking | EN | Is there a room available next Monday? | PASS | PASS | 12,038ms | 5,667ms |
| B02 | Booking | EN | How much is a Deluxe room per night? | PASS | PASS | 13,856ms | 12,794ms |
| B03 | Booking | EN | I want to cancel my booking HTL260405001 | PASS | PASS | 7,823ms | 8,427ms |
| B04 | Booking | TH | มีห้องว่างวันที่ 15-17 เดือนหน้าไหม | PASS | PASS | 6,332ms | 13,933ms |
| B05 | Booking | EN | Book a Standard room for tomorrow, 2 nights, test@example.com | PASS | PASS | 18,360ms | 37,955ms |
| B06 | Booking | EN | Can you check my booking? Email: john@hotel.com | PASS | PASS | 6,458ms | 6,703ms |
| G01 | Greeting | EN | Hello! | PASS | PASS | 5,154ms | 4,095ms |
| G02 | Greeting | TH | สวัสดีครับ | PASS | PASS | 10,488ms | 5,224ms |
| G03 | Greeting | EN | Thank you for your help! | **FAIL** | PASS | 7,319ms | 5,830ms |
| G04 | Greeting | EN | What's the weather like today? | PASS | PASS | 9,617ms | 7,242ms |
| L01 | Language | EN | Tell me about breakfast | PASS | PASS | 9,112ms | 9,430ms |
| L02 | Language | TH | อาหารเช้าเสิร์ฟกี่โมง | PASS | PASS | 8,201ms | 10,731ms |
| L03 | Language | EN | Where is the gym? | PASS | PASS | 8,165ms | 6,571ms |
| E01 | Edge | EN | I need extra towels in room 501 | PASS | PASS | 5,847ms | 5,470ms |
| E02 | Edge | EN | Room available on December 31st for NYE? | PASS | PASS | 12,977ms | 5,994ms |
| E03 | Edge | EN | I want to book 3 rooms for a group of 10 people | **FAIL** | PASS | 5,497ms | 5,352ms |
| E04 | Edge | EN | (empty message) | PASS | PASS | — | — |

### Failure Analysis

**G03 (Local FAIL)**: The 9B model responded politely ("You're welcome! If there's anything else I can help you with during your stay at The Grand Horizon Hotel, please don't hesitate to ask.") but only hit 1/4 expected keywords ("thank", "welcome", "help", "pleasure"). The word "pleasure" was not used. This is a **scoring threshold issue** — the response quality is adequate.

**E03 (Local FAIL)**: The 9B model routed "3 rooms for 10 people" to the general talk handler instead of the booking handler. The cloud model correctly identified the booking intent. This represents a genuine **routing capability gap** in the 9B model for multi-entity requests.

## A.2 Infrastructure Test Results (193/193)

### Summary

| Suite | Script | Tests | Passed | Failed | Time |
|-------|--------|-------|--------|--------|------|
| Auth Baseline | `test_auth.py` | 72 | 72 | 0 | 4s |
| Auth Hardening | `test_auth_hardening.py` | 38 | 38 | 0 | 10s |
| Audit + DB Scaling | `test_audit_and_scaling.py` | 46 | 46 | 0 | 8s |
| Chat Scaling | `test_chat_scaling.py` | 37 | 37 | 0 | 8s |
| **Total** | | **193** | **193** | **0** | **30s** |

### Test Coverage by Category

| Category | Tests | Key Verifications |
|----------|-------|-------------------|
| Login / Register / JWT | 17 | Token structure, expiry, username+email login, duplicate rejection |
| Access Control Matrix | 21 | Every admin/dashboard endpoint × {no-auth, user, admin} |
| Rate Limiting | 8 | Per-IP, per-username, per-session, Retry-After headers |
| Account Lockout | 4 | 5 failures → lock, correct password still rejected while locked |
| Token Blocklist | 9 | Logout revokes token, double logout, fresh login works |
| Password Change | 9 | Wrong password rejected, old tokens invalidated, role preserved |
| Audit Log | 30 | CRUD, filters, pagination, access control, action coverage |
| DB Connection Pool | 2 | 50 sequential + 20 concurrent queries all succeed |
| User Cache | 3 | Populate, password change invalidation, correct rejection |
| Chat Rate Limit | 3 | Per-session 429 under burst, different session independent |
| LLM Semaphore | 3 | max_concurrent counter, total_acquired counter |
| Knowledge Cache | 6 | hits/misses/hit_rate/ttl fields present and correct |
| SSE Stream Cap | 4 | max_concurrent, active, total_accepted, total_rejected |
| Parallel Chats | 3 | 5 concurrent sessions complete in parallel (~3s) |

## A.3 Performance Optimization Benchmarks

### Before/After Comparison

| Optimization | Before | After | Factor |
|-------------|--------|-------|--------|
| Reranker removal | 18s warm chat | 5s warm chat | 3.6× |
| Prompt trimming (5,500→2,800 chars) | — | — | -50% tokens |
| OLLAMA_NUM_PARALLEL (4→2) | 30–50s per chat | 4–9s per chat | 4–8× |
| Flash attention | — | Enabled | Faster attention |
| Knowledge cache (500/5min) | 500ms per RAG | 1ms cached (76% HR) | 500× |
| DB pool (min=2, max=20) | New conn per request | Pooled | Eliminated setup cost |

### VRAM Budget (RTX 5080, 16 GB)

| Component | VRAM |
|-----------|------|
| Model weights (Q5_K_M) | ~6.5 GB |
| KV cache (2 slots × 4096 ctx) | ~1.5 GB |
| Framework overhead | ~0.6 GB |
| Desktop / other | ~1.3 GB |
| **Total used** | **~9.9 GB (61%)** |
| **Free headroom** | **~6.0 GB (37%)** |

## A.4 Development Timeline (Gantt Chart)

This table is formatted for easy copy-paste into Microsoft Word. Each `████` cell represents active work in that bi-weekly period.

| Phase | Task | Jan W1-2 | Jan W3-4 | Feb W1-2 | Feb W3-4 | Mar W1-2 | Mar W3-4 | Apr W1-2 | Apr W3-4 |
|-------|------|:--------:|:--------:|:--------:|:--------:|:--------:|:--------:|:--------:|:--------:|
| **Research** | Literature review | ████ | ████ | | | | | | |
| **Research** | LangGraph / RAG study | | ████ | ████ | | | | | |
| **Design** | System architecture | | | ████ | ████ | | | | |
| **Design** | Database schema | | | ████ | | | | | |
| **Backend** | FastAPI server | | | ████ | ████ | | | | |
| **Backend** | LangGraph multi-agent | | | ████ | ████ | | | | |
| **Backend** | RAG pipeline (Qdrant) | | | ████ | ████ | | | | |
| **Backend** | Hotel tools (CRUD) | | | | ████ | ████ | | | |
| **Backend** | Railway deployment | | | ████ | | | | | |
| **Frontend** | Next.js + Ant Design | | | | | ████ | ████ | | |
| **Frontend** | Chat UI + SSE | | | | | ████ | ████ | | |
| **Frontend** | Admin dashboard | | | | | | ████ | ████ | |
| **Security** | JWT auth + RBAC | | | | | | | ████ | |
| **Security** | Rate limit + lockout | | | | | | | ████ | |
| **Scaling** | LLM semaphore + cache | | | | | | | ████ | |
| **Scaling** | Audit log + DB pool | | | | | | | ████ | |
| **Integration** | Ollama local + switch | | | | | | | ████ | |
| **Testing** | Model eval (25 cases) | | | | | | | ████ | |
| **Testing** | Infra tests (193) | | | | | | | ████ | |
| **Testing** | Perf optimization | | | | | | | | ████ |
| **Thesis** | Chapters 1–4 | | | | | | ████ | ████ | ████ |
| **Thesis** | Chapters 5–7 + review | | | | | | | ████ | ████ |

## A.5 Source Code Repository Structure

```
hote-ai-virtual-assistant-thesis/
├── src/
│   ├── hotel_guardrails/     # Primary service (FastAPI + LangGraph)
│   │   ├── server.py         # 52 API endpoints
│   │   ├── hotel_langgraph.py # Multi-agent state machine
│   │   ├── auth.py           # JWT + bcrypt + rate limiting
│   │   ├── chat_scaling.py   # 5 concurrency primitives
│   │   ├── audit.py          # Admin audit logging
│   │   ├── database.py       # PostgreSQL operations
│   │   ├── pii_redactor.py   # Regex PII scrubbing
│   │   ├── escalation.py     # Human handover triggers
│   │   └── models.py         # Pydantic request/response models
│   ├── agent/                # Hotel tools + prompt templates
│   ├── common/               # LLM wrappers, embeddings, vector store
│   └── retrievers/           # RAG retrieval services
├── deploy/compose/           # Docker Compose + init SQL
├── data/hotel/               # 10 hotel knowledge markdown files
├── scripts/                  # Test + evaluation scripts
├── docs/                     # Architecture docs + test reports
└── thesis/                   # This document
```

## A.6 API Endpoint Summary (52 endpoints)

| Category | Count | Key Endpoints |
|----------|-------|---------------|
| Auth | 7 | register, login, logout, me, password change, admin register, user list |
| Chat | 2 | /chat (JSON), /chat/stream (SSE) |
| Rooms | 3 | list, availability, detail |
| Booking | 4 | list, detail, update, direct book |
| Guests | 3 | register, lookup, update |
| Sessions | 3 | create, detail, delete |
| Admin | 14 | room/booking status, chat override, takeover/release, sessions, states, rollback, replay, escalations, audit, audit stats, metrics |
| Dashboard | 5 | stats, bookings, sessions, rooms, revenue |
| Settings | 3 | LLM config, model list, feedback |
| Payment | 2 | payment page, complete payment |
| Health | 2 | /healthz, /health |
| Root | 1 | / |

Full OpenAPI spec: `docs/api_references/openapi.json`
