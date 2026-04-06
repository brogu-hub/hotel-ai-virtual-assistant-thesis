# Appendix A: Test Results and Development Timeline

## A.1 Model Evaluation — Full 25-Case Results

### Test Configuration
- **Local model**: Qwen3.5 Opus 9B (fredrezones55/qwen3.5-opus:9b) on Ollama, RTX 5080 16GB
- **Cloud model**: Qwen3 Max (qwen/qwen3-max) on OpenRouter
- **Evaluation script**: `scripts/eval_model_comparison.py`
- **Scoring**: keyword matching (≥50% threshold), language detection, response completeness

### A.1.1 Knowledge Retrieval (K01–K08)

---

**K01 — What time is breakfast? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 34,624ms | 6,457ms |
| **Response** | Breakfast is served daily from **6:30 AM to 10:30 AM** at **The Grand Dining Room**, located on the **1st Floor near the main lobby**. This is complimentary for all in-house guests. The menu features an international buffet with over 50 dishes, plus Thai, Western, and Japanese stations, fresh tropical fruits, bakery items, and beverages. | Breakfast is served daily from **6:30 AM to 10:30 AM** at **The Grand Dining Room**, located on the **1st floor near the main lobby**. It is **complimentary for all in-house guests** and features an international buffet with over 50 dishes, including Thai, Western, and Japanese stations, fresh tropical fruits, pastries, and beverages. Vegetarian, vegan, halal, and gluten-free options are available upon request. |
| **Score** | keywords=2/4 | keywords=2/4 |

---

**K02 — What is the WiFi password? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 9,049ms | 5,527ms |
| **Response** | **Password:** Welcome2026. **Network:** GrandHorizon_Guest. **Security:** WPA2. Coverage: all guest rooms, lobby, pool deck, restaurants, spa, fitness center. Free for all registered guests. | The WiFi password is **GrandHorizon2026**. WiFi is complimentary for all guests and available throughout the hotel. Select network **"GrandHorizon_Guest"** and enter the password. |
| **Score** | keywords=2/3 | keywords=2/3 |

---

**K03 — สระว่ายน้ำเปิดกี่โมง (Pool hours?) [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 10,532ms | 8,176ms |
| **Response** | สระว่ายน้ำเปิดให้บริการ **06:00 - 21:00 น. ทุกวัน** ตั้งอยู่ที่ **ดาดฟ้าชั้น 5** เป็นสระอินฟินิตี้น้ำอุ่นขนาด 25 x 10 เมตร มีสระเด็กแยก อุณหภูมิน้ำ 28-30°C ผ้าเช็ดตัวฟรี เก้าอี้อาบแดดและร่ม | สระว่ายน้ำเปิดให้บริการทุกวันตั้งแต่ **06:00 น. ถึง 21:00 น.** ตั้งอยู่ที่ **ดาดฟ้าชั้น 5** เป็นสระอินฟินิตี้น้ำอุ่น 25 x 10 เมตร มีสระเด็กแยก |
| **Score** | keywords=2/2 | keywords=2/2 |

---

**K04 — Do you allow pets? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 8,267ms | 7,591ms |
| **Response** | Yes! Small pets only (under **5 kg** / 11 lbs). Pet fee: **500 THB**/night. Deposit: 2,000 THB (refundable). Pets must be leashed, not allowed in restaurants/spa/pool/fitness. | Yes, small pets under **5 kg**. Fee: **500 THB**/night. Deposit: 2,000 THB refundable. Must be leashed in public areas. Not permitted in restaurants, spa, pool, or fitness center. |
| **Score** | keywords=3/3 | keywords=3/3 |

---

**K05 — Cancellation policy? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 8,008ms | 8,727ms |
| **Response** | Free cancellation: more than **48 hours** before check-in. Within 48 hours: 1 night charge. No-show: full stay charge. Early departure: no refund. Cancel via website, +66 2 123 4567, or email. | Free cancellation: more than **48 hours** before check-in. Within 48 hours: 1 night charge. No-show: full stay charge. Early departure: no refund. Cancel online, by calling +66 2 123 4567, or emailing reservations@grandparadise.com. |
| **Score** | keywords=3/3 | keywords=3/3 |

---

**K06 — Spa location and treatments? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 9,822ms | 13,774ms |
| **Response** | **Serenity Spa, 3rd Floor**. Hours: 10AM–10PM (last booking 8:30PM). Thai Traditional **Massage**: 60min 1,500 THB / 90min 2,000 THB. Aromatherapy: 60min 1,800 THB. Deep Tissue: 60min 2,000 THB. Royal Thai Experience package: 3 hours, 5,500 THB. | **Serenity Spa, 3rd Floor**. Hours: 10AM–10PM (last booking 8:30PM). Thai Traditional **Massage**: 1,500–2,500 THB. Aromatherapy: 1,800–2,500 THB. Deep Tissue: 2,000–2,800 THB. Foot Reflexology: 900–1,200 THB. Royal Thai Experience: 3 hours, 5,500 THB. |
| **Score** | keywords=3/3 | keywords=3/3 |

---

**K07 — Check-in/check-out times? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 9,677ms | 6,312ms |
| **Response** | Check-in: **2:00 PM (14:00)**. Early check-in free if available. Check-out: **12:00 PM (noon)**. Late check-out: 500 THB/hour until 6PM. Luggage storage free. Express check-out available. | Check-in: **2:00 PM (14:00)**. Check-out: **12:00 PM (noon)**. Early check-in free if rooms ready. Late check-out 500 THB/hour until 6PM. Free luggage storage. |
| **Score** | keywords=4/4 | keywords=4/4 |

---

**K08 — มีบริการรถรับส่งสนามบินไหม (Airport transfer?) [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 10,392ms | 13,311ms |
| **Response** | มีค่ะ! **สุวรรณภูมิ**: Private Sedan 1,500 บาท, Luxury 2,500 บาท, Van 2,500 บาท. **ดอนเมือง**: Sedan 1,200 บาท, Van 2,000 บาท. จองล่วงหน้า 24 ชม. | มีค่ะ! **สุวรรณภูมิ**: Sedan 1,500 บาท (3 คน), Luxury 2,500 บาท, Van 2,500 บาท. **ดอนเมือง**: Sedan 1,200 บาท, Van 2,000 บาท. จองล่วงหน้า 24 ชม. |
| **Score** | keywords=2/2 | keywords=2/2 |

### A.1.2 Booking Operations (B01–B06)

---

**B01 — Room available next Monday? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 12,038ms | 5,667ms |
| **Response** | Yes, several Standard rooms available for April 13, 2026. Lists 10 rooms (102, 105, 106, 107, 109, 110, 113, 115, 201, 202) at 2,500 THB. Offers to book or check other dates. | To check availability for April 14, asks for check-out date and preferred room type (Standard, Deluxe, Suite, Penthouse). |
| **Score** | keywords=4/4 | keywords=4/4 |

---

**B02 — Deluxe room price? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 13,856ms | 12,794ms |
| **Response** | **4,500 THB/night**. 45 sqm, 1 King bed, max 2+1, city view, minibar, free WiFi, breakfast included. | **3,500 THB/night**. 35 sqm, max 3 adults, breakfast + WiFi + minibar included. |
| **Score** | keywords=3/4 | keywords=3/4 |

---

**B03 — Cancel booking HTL260405001 [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 7,823ms | 8,427ms |
| **Response** | Couldn't find reservation HTL260405001. Suggests checking the number or providing email for lookup. | Couldn't find HTL260405001. Asks to double-check number or provide email. |
| **Score** | keywords=1/1 | keywords=1/1 |

---

**B04 — มีห้องว่างวันที่ 15-17 เดือนหน้าไหม [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 6,332ms | 13,933ms |
| **Response** | ตรวจสอบช่วง 15-17 เมษายน 2026 (3 คืน). ถามจำนวนผู้เข้าพัก ประเภทห้อง | มีห้องว่าง 15-17 พฤษภาคม สแตนดาร์ด 2,500 บาท/คืน. ถามประเภทห้อง จำนวนผู้เข้าพัก อีเมล |
| **Score** | keywords=2/2 | keywords=2/2 |

---

**B05 — Book Standard, tomorrow, 2 nights, test@example.com [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 18,360ms | 37,955ms |
| **Response** | ✅ Confirmed! HTL2604060308, Room 102 (Standard), April 7–9. **3,250 THB/night** (same-day +30% surcharge). Total: 6,500 THB. | ✅ Confirmed! HTL2604060309, Room 105 (Standard, Mountain View). **3,250 THB/night** (same-day surcharge). Total: 6,500 THB. Also offers Deluxe upgrade + payment link. |
| **Score** | keywords=2/3 | keywords=3/3 |

---

**B06 — Check booking by email john@hotel.com [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 6,458ms | 6,703ms |
| **Response** | No reservations found for john@hotel.com. Offers to check availability or create new booking. | No reservations found. Asks to double-check email or provide confirmation number. |
| **Score** | keywords=2/2 | keywords=2/2 |

### A.1.3 Greetings & Small Talk (G01–G04)

---

**G01 — Hello! [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 5,154ms | 4,095ms |
| **Response** | Hello! Welcome to The Grand Horizon Hotel. How may I assist you today? | Hello! Welcome to The Grand Horizon Hotel. How may I assist you today? Whether you'd like to check room availability, make a reservation, or learn about our facilities, I'm here to help! |

---

**G02 — สวัสดีครับ [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 10,488ms | 5,224ms |
| **Response** | สวัสดีค่ะ! ยินดีที่ได้ต้อนรับคุณสู่โรงแรมเดอะแกรนด์ฮอไรซัน มีอะไรให้ช่วยคุณวันนี้ไหมคะ? | สวัสดีครับ! ยินดีต้อนรับสู่ The Grand Horizon Hotel ค่ะ มีอะไรที่สามารถช่วยคุณได้บ้างไหมครับ? |

---

**G03 — Thank you! [Local FAIL / Cloud PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 7,319ms | 5,830ms |
| **Response** | You're very welcome! 😊 I'm always happy to assist you. If you need anything: Room service (Dial 1), Front desk (Dial 0), Concierge. สวัสดีค่ะ/ครับ! | You're very welcome! 😊 If you need assistance with booking, dining, spa services, or anything else — I'm here to help. Feel free to ask anytime! |
| **Verdict** | **FAIL** (keywords=1/4) | **PASS** (keywords=2/4) |

---

**G04 — What's the weather? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 9,617ms | 7,242ms |
| **Response** | No access to real-time weather. Suggests weather apps, searching online, or asking the concierge. Offers help with hotel info instead. | No access to real-time weather. Suggests Weather Channel, AccuWeather, or smartphone app. Concierge can help with activity recommendations. |

### A.1.4 Language Detection (L01–L03)

---

**L01 — Tell me about breakfast [Both PASS, language=EN ✓]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 9,112ms | 9,430ms |
| **Response** | The Grand Dining Room, 1st Floor. Hours: 6:30 AM–10:30 AM. Complimentary. International buffet 50+ dishes: Thai station (Jok, Khao Tom, Pad Thai), Western (eggs, pancakes, waffles), Japanese (miso, grilled fish). | The Grand Dining Room, 1st Floor. Hours: 6:30 AM–10:30 AM. Complimentary. International buffet 50+ dishes: Thai, Western, Japanese stations. Fresh tropical fruits, bakery, beverages. |

---

**L02 — อาหารเช้าเสิร์ฟกี่โมง [Both PASS, language=TH ✓]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 8,201ms | 10,731ms |
| **Response** | อาหารเช้าเสิร์ฟ **06:30 - 10:30 น. ทุกวัน** ชั้น 1 ใกล้ล็อบบี้ ฟรีทุกห้อง บุฟเฟต์ 50+ รายการ มีมังสวิรัติ ฮาลาล กลูเตนฟรี | อาหารเช้าเสิร์ฟที่ The Grand Dining Room ชั้น 1 **06:30-10:30 น. ทุกวัน** ฟรี บุฟเฟต์ 50+ รายการ มีมังสวิรัติ ฮาลาล กลูเตนฟรี |

---

**L03 — Where is the gym? [Both PASS, language=EN ✓]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 8,165ms | 6,571ms |
| **Response** | Fitness Center on **4th Floor**. 24-hour keycard access. 8 treadmills, 4 ellipticals, 4 bikes, free weights 2–50 kg. Personal training: 1,000 THB/session (dial 404). Complimentary. | Fitness Center on **4th Floor**. 24-hour keycard access. 8 treadmills, 4 ellipticals, 4 bikes, free weights 2–50 kg. Personal training: 1,000 THB/session (dial 404). |

### A.1.5 Edge Cases (E01–E04)

---

**E01 — Extra towels in room 501 [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 5,847ms | 5,470ms |
| **Response** | Happy to help. Needs reservation ID or confirmation number to create service request. | Created service request for extra towels to Room 501. Estimated delivery: 15–20 minutes. |

---

**E02 — Room for December 31st NYE? [Both PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 12,977ms | 5,994ms |
| **Response** | Lists available Standard rooms for Dec 31 with prices (2,500 THB/night). Shows 10 rooms across floors 1–2. | Asks for check-out date and preferred room type to check availability and pricing. |

---

**E03 — Book 3 rooms for 10 people [Local FAIL / Cloud PASS]**

| | Local (9B) | Cloud (Qwen3 Max) |
|---|---|---|
| **Latency** | 5,497ms | 5,352ms |
| **Response** | *(responded in Thai instead of English)* จองห้องสำหรับกลุ่ม 10 ท่าน ถามวันเข้าพัก ประเภทห้อง อีเมล | Thank you for choosing our hotel! To assist with 3 rooms for 10 guests, asks for dates and room type preference. |
| **Verdict** | **FAIL** (keywords=0/1 "room") | **PASS** (keywords=1/1) |

---

**E04 — (empty message) [Both PASS — graceful error handling]**

Both models return HTTP 422 (validation error) — the empty message is caught by Pydantic's `min_length=1` validator before reaching the LLM.

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

### Backend Repository (`hote-ai-virtual-assistant-thesis/`)

```
hote-ai-virtual-assistant-thesis/
├── src/
│   ├── hotel_guardrails/          # Primary service (FastAPI + LangGraph)
│   │   ├── server.py              # 52 API endpoints, middleware, lifespan
│   │   ├── hotel_langgraph.py     # Multi-agent state machine (4 sub-agents)
│   │   ├── auth.py                # JWT + bcrypt + rate limiting + cache
│   │   ├── chat_scaling.py        # LLM semaphore, session locks, RAG cache
│   │   ├── audit.py               # Admin audit logging (26 action types)
│   │   ├── database.py            # PostgreSQL ops + connection pool
│   │   ├── pii_redactor.py        # Regex PII scrubbing (6 patterns)
│   │   ├── escalation.py          # Human handover triggers
│   │   ├── models.py              # Pydantic request/response models
│   │   ├── config.py              # Runtime LLM config + model presets
│   │   ├── hybrid_router.py       # Safety filter + routing
│   │   ├── langgraph_adapter.py   # Server ↔ LangGraph bridge
│   │   ├── openrouter_llm.py      # OpenRouter/Ollama LLM wrapper
│   │   ├── feedback_collector.py  # Response quality feedback
│   │   └── config/                # NeMo Guardrails config (optional)
│   ├── agent/                     # Hotel tools + prompts
│   │   ├── hotel_tools.py         # 15 LangChain @tool functions
│   │   ├── hotel_prompt.yaml      # System prompt templates (~2,800 chars)
│   │   ├── main.py                # Original NVIDIA agent
│   │   └── tools.py               # Original RAG tools
│   ├── common/                    # Shared utilities
│   │   ├── llm_openrouter.py      # OpenRouter LLM provider
│   │   ├── llm_fallback.py        # Multi-provider fallback chain
│   │   ├── embeddings_openrouter.py # Embedding service
│   │   ├── vectorstore_qdrant.py  # Qdrant adapter
│   │   ├── reranker_qwen.py       # Qwen CrossEncoder (disabled by default)
│   │   ├── reranker_nvidia.py     # NVIDIA NIM reranker (legacy)
│   │   ├── configuration.py       # Config system
│   │   └── audit_logger.py        # Generic audit logging
│   ├── retrievers/
│   │   └── hotel_knowledge/
│   │       └── chains.py          # RAG pipeline (chunk, embed, search)
│   ├── analytics/                 # Sentiment + summarization
│   └── ingest_service/            # Document ingestion
├── deploy/compose/
│   ├── docker-compose.hotel.yaml  # 5-service Docker stack
│   └── init-scripts/
│       └── init-hotel.sql         # Database schema (10 tables)
├── data/hotel/                    # 10 hotel knowledge markdown files
├── scripts/
│   ├── eval_model_comparison.py   # 25-case model evaluation
│   ├── export_all_test_results.py # 193-test result exporter
│   ├── test_auth.py               # 72 auth baseline tests
│   ├── test_auth_hardening.py     # 38 hardening tests
│   ├── test_audit_and_scaling.py  # 46 audit + DB scaling tests
│   ├── test_chat_scaling.py       # 37 chat concurrency tests
│   └── ingest_hotel_knowledge.py  # Qdrant data loader
├── thesis/                        # This document
├── docs/                          # Architecture docs + test reports
├── CLAUDE.md                      # Project overview for AI assistants
└── .env                           # Environment configuration (not committed)
```

### Frontend Repository (`hotel-ai-nextjs/`)

```
hotel-ai-nextjs/
├── src/
│   ├── app/
│   │   ├── layout.tsx                    # Root layout (Ant Design provider)
│   │   ├── page.tsx                      # Landing page
│   │   ├── api/hotel/[...path]/
│   │   │   └── route.ts                  # Backend proxy (all /api/hotel/* → :8088)
│   │   └── hotel/
│   │       ├── layout.tsx                # Hotel app layout (sidebar, auth)
│   │       ├── page.tsx                  # Main chat interface
│   │       ├── features/
│   │       │   ├── AuthModal.tsx         # Login/register modal
│   │       │   ├── ChangePasswordModal.tsx # Password change dialog
│   │       │   ├── ChatHeader.tsx        # Chat header with model indicator
│   │       │   ├── ChatInput.tsx         # Message input + send button
│   │       │   ├── ContactModal.tsx      # Hotel contact info modal
│   │       │   ├── MessageList.tsx       # Chat message rendering (SSE)
│   │       │   ├── RequireAdmin.tsx      # Admin route guard HOC
│   │       │   ├── hotelInfo.ts          # Static hotel data
│   │       │   └── receipt.ts            # Booking receipt formatter
│   │       ├── rooms/
│   │       │   ├── page.tsx              # Room catalog browse
│   │       │   ├── [roomId]/page.tsx     # Individual room detail
│   │       │   └── features/
│   │       │       ├── RoomCard.tsx       # Room type card component
│   │       │       └── AvailabilityCalendar.tsx # Date picker calendar
│   │       ├── bookings/
│   │       │   ├── page.tsx              # Booking list/search
│   │       │   ├── [id]/page.tsx         # Booking detail + modify
│   │       │   └── features/
│   │       │       └── BookingWizard.tsx  # Multi-step booking form
│   │       ├── payment/
│   │       │   └── [token]/page.tsx      # Mock payment page
│   │       ├── settings/
│   │       │   ├── layout.tsx            # Settings layout
│   │       │   └── page.tsx              # LLM model switcher + config
│   │       └── admin/
│   │           ├── layout.tsx            # Admin layout (RequireAdmin)
│   │           ├── page.tsx              # Dashboard overview
│   │           ├── sessions/
│   │           │   ├── page.tsx          # Live session monitor
│   │           │   └── [sessionId]/page.tsx # Session detail + chat viewer
│   │           ├── bookings/page.tsx     # Booking management
│   │           ├── rooms/page.tsx        # Room status management
│   │           └── timetravel/page.tsx   # LangGraph checkpoint browser
│   ├── services/hotelAssistant/
│   │   ├── index.ts                      # API client (fetch + SSE)
│   │   └── types.ts                      # TypeScript API types
│   ├── store/hotel/
│   │   ├── store.ts                      # Zustand store root
│   │   ├── index.ts                      # Store exports
│   │   └── slices/
│   │       ├── auth.ts                   # Auth state (token, user, role)
│   │       ├── bookings.ts              # Booking state + SWR
│   │       ├── chat.ts                   # Chat messages + SSE stream
│   │       ├── rooms.ts                  # Room catalog state
│   │       └── session.ts               # Session management
│   └── locales/
│       └── hotel.ts                      # Thai/English translations
├── docs/
│   └── THESIS_CITATIONS.md              # Frontend technology citations
├── package.json                          # Dependencies (Next.js, Ant Design, etc.)
├── tsconfig.json                         # TypeScript config
└── next.config.ts                        # Next.js configuration
```

## A.6 API Endpoint Reference (52 endpoints)

Full OpenAPI spec: `docs/api_references/openapi.json`

### Authentication (7 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/auth/register` | Public | Register new user account, returns JWT |
| POST | `/auth/login` | Public | Login (username or email), rate-limited, lockout-protected |
| GET | `/auth/me` | Bearer | Current authenticated user profile |
| POST | `/auth/logout` | Bearer | Revoke current JWT (jti added to blocklist) |
| PATCH | `/auth/me/password` | Bearer | Change password, invalidates all prior tokens |
| POST | `/auth/admin/register` | Admin | Create new admin account |
| GET | `/auth/users` | Admin | List all users (filter by role) |

### Chat (2 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/chat` | Public | Main chatbot conversation (PII-scrubbed, rate-limited, session-locked) |
| POST | `/chat/stream` | Public | Streaming chat via SSE (token-by-token output) |

### Rooms (3 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/rooms` | Public | List all room types with availability count |
| GET | `/rooms/availability` | Public | Calendar availability (date range × room type) |
| GET | `/rooms/{room_id}` | Public | Individual room detail with pricing breakdown |

### Booking (4 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/bookings` | Public | List bookings (filter by email, status, date range) |
| GET | `/bookings/{reservation_id}` | Public | Single booking detail by reservation ID |
| PATCH | `/bookings/{reservation_id}` | Public | Update booking (dates, guests, special requests) |
| POST | `/tools/book` | Public | Direct booking operations (check/create/confirm/cancel) |

### Guests (3 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/guests` | Public | Register guest profile (email as unique identifier) |
| GET | `/guests/{email}` | Public | Lookup guest by email |
| PATCH | `/guests/{guest_id}` | Public | Update guest profile (name, phone, nationality) |

### Sessions (4 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/sessions` | Public | Create new conversation session |
| GET | `/sessions/{session_id}` | Public | Get session info (created_at, message_count) |
| DELETE | `/sessions/{session_id}` | Public | End conversation session |
| GET | `/sessions/{session_id}/messages` | Public | Get conversation history (paginated) |

### Settings (3 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/settings/llm` | Public | Current LLM config (backend, model, temperature, thinking) |
| PUT | `/settings/llm` | Admin | Switch model at runtime (Ollama ↔ OpenRouter, change temperature/tokens) |
| GET | `/settings/models` | Public | List available LLM models with presets |

### Admin Operations (15 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| PUT | `/admin/rooms/{room_id}/status` | Admin | Set room status (available/occupied/maintenance/cleaning) |
| PUT | `/admin/bookings/{reservation_id}/status` | Admin | Override booking status (check-in, no-show, cancel) |
| POST | `/admin/chat/override` | Admin | Send staff message directly to guest session |
| GET | `/admin/sessions` | Admin | List active chat sessions with previews and status |
| GET | `/admin/sessions/{session_id}/messages` | Admin | Full session chat history (privacy-audited) |
| POST | `/admin/sessions/{session_id}/takeover` | Admin | Pause bot, admin takes over conversation |
| POST | `/admin/sessions/{session_id}/release` | Admin | Resume bot for session |
| GET | `/admin/sessions/{session_id}/states` | Admin | LangGraph checkpoint history (time-travel view) |
| POST | `/admin/sessions/{session_id}/rollback` | Admin | Rewind session to previous checkpoint |
| POST | `/admin/sessions/{session_id}/replay` | Admin | Branch from checkpoint with new message |
| GET | `/admin/escalations` | Admin | List auto-escalated sessions with reasons |
| GET | `/admin/audit` | Admin | Query audit log (filters + pagination) |
| GET | `/admin/audit/stats` | Admin | Audit log summary statistics (24h) |
| GET | `/admin/metrics/chat` | Admin | Chat scaling runtime metrics (LLM/cache/rate limit) |

### Dashboard (5 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/dashboard/stats` | Admin | Hotel overview (occupancy, revenue, check-ins/outs, guests) |
| GET | `/dashboard/bookings/recent` | Admin | Live feed of latest reservations |
| GET | `/dashboard/sessions` | Admin | Chatbot session statistics (24h) |
| GET | `/dashboard/rooms` | Admin | Room status breakdown by floor |
| GET | `/dashboard/revenue` | Admin | Revenue by room type, source, daily trend (30 days) |

### Feedback (2 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/feedback` | Public | Submit response quality feedback (score + comment) |
| GET | `/feedback/stats` | Public | Feedback statistics (average scores) |

### Payment (2 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/payment/{token}` | Public | Mock payment page (booking details + amount) |
| POST | `/payment/{token}/complete` | Public | Mock payment completion (marks as paid) |

### Health (2 endpoints)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/healthz` | Public | Load balancer health check (simple 200 OK) |
| GET | `/health` | Public | Component health status (guardrails, database, langgraph, qdrant) |

### Root (1 endpoint)

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | Public | API root — returns name, version, docs URL |
