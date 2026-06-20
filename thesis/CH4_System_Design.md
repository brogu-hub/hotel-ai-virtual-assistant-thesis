# Chapter 4: System Design

## 4.1 Requirements Analysis

### 4.1.1 Functional Requirements

| ID | Requirement | Priority |
|----|-------------|----------|
| FR1 | Bilingual guest conversation (Thai/English) with automatic language detection | Must |
| FR2 | Room availability checking with real-time database queries | Must |
| FR3 | Reservation CRUD (create, read, update, cancel) via natural language | Must |
| FR4 | Hotel knowledge Q&A (facilities, policies, dining, spa, transport) | Must |
| FR5 | Check-in / check-out operations | Must |
| FR6 | Admin dashboard with session monitoring and chat intervention | Must |
| FR7 | JWT authentication with user/admin role separation | Must |
| FR8 | Runtime switching between local and cloud LLM backends | Should |
| FR9 | Dynamic pricing with early-bird discounts and last-minute surcharges | Should |
| FR10 | PII redaction before LLM processing | Should |
| FR11 | Automatic escalation to human staff on frustrated guests | Could |
| FR12 | Mock payment link generation | Could |

### 4.1.2 Non-Functional Requirements

| ID | Requirement | Target |
|----|-------------|--------|
| NFR1 | Response latency (warm, single user) | < 10 seconds |
| NFR2 | Concurrent users without degradation | ≥ 2 simultaneous chats |
| NFR3 | Knowledge retrieval accuracy | ≥ 90% on hotel Q&A test set |
| NFR4 | System availability | Health check + graceful degradation |
| NFR5 | Security | bcrypt hashing, JWT with jti, rate limiting, audit log |
| NFR6 | Deployment | Docker Compose, single-command startup |

## 4.2 System Architecture

### 4.2.1 Microservice Topology

The system consists of five Docker services communicating over a dedicated bridge network:

[Figure 3.1: System architecture diagram — Five Docker containers (hotel-api:8088, hotel-ollama:11435, hotel-db:5433, hotel-qdrant:6334, hotel-redis:6380) on a shared bridge network. The hotel-api container runs FastAPI and contains the LangGraph agent, auth system, and scaling primitives. External traffic arrives from the Next.js frontend via HTTP. The Ollama container hosts the local 9B LLM model on GPU, while OpenRouter (cloud) is accessed over HTTPS when runtime-switched.]

| Container | Service | Port | Purpose |
|-----------|---------|------|---------|
| hotel-api | FastAPI + LangGraph | 8088 | Application server (all endpoints) |
| hotel-ollama | Ollama | 11435 | Local LLM inference (GPU) |
| hotel-db | PostgreSQL 16 | 5433 | Hotel database (rooms, bookings, guests, users, audit) |
| hotel-qdrant | Qdrant | 6334 | Vector store (hotel knowledge embeddings) |
| hotel-redis | Redis 7 | 6380 | Session cache |

### 4.2.2 Request Flow

The complete request flow for a guest chat message:

```
POST /chat {message, session_id}
  │
  ├─ PII redactor (regex scrub sensitive data)
  ├─ Chat rate limiter (per-session, 30/min)
  ├─ Session lock (per-session asyncio.Lock)
  ├─ Safety router (input validation)
  │
  ├─ LLM concurrency semaphore (acquire slot)
  │   │
  │   └─ LangGraph Agent
  │       ├─ Primary Assistant (routing LLM call)
  │       │   ├─ ToHotelBooking → Booking sub-agent → booking tools
  │       │   ├─ ToHotelService → Service sub-agent → service tools
  │       │   ├─ ToHotelKnowledge → Knowledge sub-agent → RAG search
  │       │   └─ HandleOtherTalk → General conversation
  │       │
  │       └─ Response
  │
  ├─ LLM semaphore release
  ├─ Escalation check (sentiment/repetition/high-value)
  ├─ Save to conversation_history
  └─ Return ChatResponse {response, session_id, tool_calls, routing_path}
```

## 4.3 LangGraph Agent Design

### 4.3.1 State Definition

The agent's state is defined as a TypedDict that flows through every node in the graph:

```python
# src/hotel_guardrails/hotel_langgraph.py

class HotelState(TypedDict):
    """State for the hotel assistant agent."""
    messages: Annotated[List[AnyMessage], add_messages]
    session_id: str
    user_id: str
    language: str            # 'th', 'en', or 'auto'
    current_intent: str      # booking, service, knowledge, other
    tool_calls_made: List[Dict[str, Any]]
```

The `messages` field uses LangGraph's `add_messages` reducer, which appends new messages to the existing list rather than replacing it — enabling multi-turn conversation history.

### 4.3.2 Primary Router and Sub-Agent Dispatch

The primary assistant acts as a **router**, not a responder. It receives the guest's message and decides which specialized sub-agent should handle it by emitting a tool call:

```python
# src/hotel_guardrails/hotel_langgraph.py

def route_primary_assistant(state: HotelState) -> Literal[
    "enter_booking", "enter_service",
    "enter_knowledge", "other_talk", "__end__"
]:
    """Route from primary assistant to specialized handlers."""
    route = tools_condition(state)
    if route == END:
        return END

    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        tool_name = tool_calls[0]["name"]
        if tool_name == ToHotelBooking.__name__:
            return "enter_booking"
        elif tool_name == ToHotelService.__name__:
            return "enter_service"
        elif tool_name == ToHotelKnowledge.__name__:
            return "enter_knowledge"
        elif tool_name == HandleOtherTalk.__name__:
            return "other_talk"
    return END
```

[Figure 3.2: LangGraph state machine diagram — Nodes: START → primary_assistant → {enter_booking → hotel_booking ↔ booking_tools, enter_service → hotel_service ↔ service_tools, enter_knowledge → hotel_knowledge, other_talk → handle_other}. Conditional edges route from primary_assistant based on tool call names. Booking and service sub-agents have tool loops (cyclic edges) that continue until the LLM stops emitting tool calls.]

### 4.3.3 Sub-Agent Architecture

Each sub-agent has:
- **A specialized system prompt** loaded from `hotel_prompt.yaml`
- **A restricted tool set** — the booking agent cannot access knowledge search tools, and vice versa
- **An independent LLM call** with appropriate `max_tokens` for its task (booking: 2048, knowledge: 1024, greetings: 512)

| Sub-Agent | Tools | max_tokens | Purpose |
|-----------|-------|------------|---------|
| Booking | 12 tools (check/create/update/cancel reservation, check-in/out, pricing, upsell, payment) | 2048 | Full booking lifecycle |
| Service | 2 tools (get_hotel_services, create_service_request) | 1024 | Amenity and service requests |
| Knowledge | RAG search (not a tool call — direct invocation) | 1024 | Hotel information Q&A |
| Other Talk | None (direct LLM response) | 512 | Greetings, thanks, off-topic |

### 4.3.4 Tools Reference

The agent exposes two structurally different classes of "tools" to the LLM, and the distinction matters when reading the binding tables below. **Routing primitives** (`ToHotelBooking`, `ToHotelService`, `ToHotelKnowledge`, `HandleOtherTalk`) are Pydantic `BaseModel` schemas defined at `src/hotel_guardrails/hotel_langgraph.py` lines 85-99; the primary assistant emits them as `tool_calls` but they do **not** touch the database, Qdrant, or any external API — they carry a single `query: str` field and are consumed by `route_primary_assistant` (L1787) to dispatch the conversation to a specialised sub-agent via `tools_condition`. **Data tools** are the real, side-effecting tools each sub-agent's LLM can invoke; they hit PostgreSQL (rooms, reservations, guests, services), Qdrant (RAG over the hotel knowledge base), or compute pricing locally before returning a bilingual Thai/English string.

**Table 4.3.4: Tools bound per sub-agent (live binding from `hotel_langgraph.py`)**

| Sub-agent | Tool name | Signature | Purpose | Touches | Sync/Async | Returns |
|---|---|---|---|---|---|---|
| Primary Assistant | `ToHotelBooking` | `ToHotelBooking(query: str)` | Route to booking sub-agent | None (routing primitive) | sync | Pydantic schema |
| Primary Assistant | `ToHotelService` | `ToHotelService(query: str)` | Route to service sub-agent | None (routing primitive) | sync | Pydantic schema |
| Primary Assistant | `ToHotelKnowledge` | `ToHotelKnowledge(query: str)` | Route to knowledge sub-agent | None (routing primitive) | sync | Pydantic schema |
| Primary Assistant | `HandleOtherTalk` | `HandleOtherTalk(query: str)` | Route to greetings / off-topic node | None (routing primitive) | sync | Pydantic schema |
| Booking | `check_room_availability` | `(check_in_date, check_out_date, room_type=None)` | List bookable rooms across dates | PMS DB: `rooms` JOIN `room_types`, anti-join `reservations` | sync | TH/EN string |
| Booking | `calculate_dynamic_price` | `(room_type, check_in_date, check_out_date)` | Apply tier multiplier and return per-night + total | PMS DB: `room_types`; local multiplier | sync | TH/EN string |
| Booking | `create_reservation` | `(guest_email, room_number, check_in_date, check_out_date, num_guests=1, special_requests=None)` | Insert reservation, auto-register guest | PMS DB: `guests` (UPSERT), `rooms`, `reservations`; `sync_audit(CHAT_BOOKING_CREATED)` | sync | TH/EN confirmation |
| Booking | `confirm_reservation` | `(reservation_id)` | Transition `pending → confirmed` | PMS DB: `reservations` UPDATE; audit | sync | TH/EN status |
| Booking | `update_reservation` | `(reservation_id, check_in_date?, check_out_date?, room_number?, num_guests?, special_requests?)` | Modify dates, room, guest count, requests; recompute total | PMS DB: `reservations`, `rooms`, `room_types`; audit | sync | TH/EN updated block |
| Booking | `cancel_reservation` | `(reservation_id, reason)` | Transition `pending` or `confirmed` → `cancelled` | PMS DB: `reservations` UPDATE; `sync_audit(CHAT_BOOKING_CANCELLED)` | sync | TH/EN cancellation |
| Booking | `check_in_guest` | `(reservation_id)` | Transition `confirmed → checked_in` | PMS DB: `reservations` UPDATE | sync | TH/EN check-in block |
| Booking | `check_out_guest` | `(reservation_id)` | Transition `checked_in → checked_out` | PMS DB: `reservations` UPDATE | sync | TH/EN check-out block |
| Booking | `get_reservation_details` | `(reservation_id)` | Fetch single reservation by id or confirmation no. | PMS DB: `reservations` JOIN `rooms` JOIN `room_types` JOIN `guests` | sync | TH/EN reservation block |
| Booking | `get_guest_reservations` | `(guest_email)` | Fetch last 10 reservations for a guest | PMS DB: same joins, `ORDER BY check_in_date DESC LIMIT 10`; WiFi password only on `checked_in` | sync | TH/EN list |
| Service | `get_hotel_services` | `()` | List active hotel services, grouped by category | PMS DB: `hotel_services WHERE is_active=true` | sync | TH/EN catalogue |
| Service | `create_service_request` | `(reservation_id, request_type, description)` | File a service ticket against a booking | PMS DB: `service_requests` INSERT | sync | TH/EN ticket id |
| Knowledge | `search_hotel_knowledge` (direct, not bound) | `(query)` | RAG over hotel KB markdown via Qdrant | Qdrant: `hotel_knowledge` collection (k=30 → top 3); no LLM tool-call round-trip | sync | TH/EN grounded context |
| Other Talk | — (no tools) | — | Greetings, thanks, off-topic chit-chat | LLM only | sync | TH/EN reply |

A subtlety worth flagging for reproducibility: `build_hotel_graph` defines a *separate* `booking_tools` list at L2164-2177 with **12** entries (it adds `check_upsell_opportunity` and `generate_payment_link`) which wires the `ToolNode` that *executes* tool calls; the LLM inside `handle_booking`, however, is bound at L712 to the **10**-tool list above. The two extra tools are therefore wired into the runtime ToolNode but are unreachable from the LLM in the current `handle_booking`, and are invoked deterministically elsewhere (the Phase J.4 `_maybe_compute_pricing_context` path; see CH6 §6.5.11). Knowledge search likewise never appears in a `bind_tools` call: `handle_knowledge` invokes `search_hotel_knowledge.invoke()` directly (L1418, L1444) as a plain RAG step and then synthesises a response with an unbound LLM (`rag_prompt | llm`, L1687).

**Per-tool descriptions — Booking sub-agent (10 tools).**

- **`check_room_availability(check_in_date, check_out_date, room_type=None)`** — Queries `rooms` JOIN `room_types` with an anti-join on `reservations` (excluding `cancelled`, `no_show`, and `checked_out`) to find rooms free across the requested range, optionally filtered by tier (Standard / Deluxe / Suite / Penthouse). Returns a bilingual list with base price, nights, and occupancy. Called **before** quoting a price and **before** `create_reservation`.
- **`calculate_dynamic_price(room_type, check_in_date, check_out_date)`** — Computes per-night and total pricing by applying the tier multiplier from `_calculate_dynamic_multiplier(check_in_date)`. Cutoffs (see §4.9.4): Same-Day +30 % (×1.30), Last-Minute +20 % (×1.20), Standard Rate (×1.00), Advance Booking 10 % off (×0.90), Early Bird 15 % off (×0.85). The Phase J.4 helper `_maybe_compute_pricing_context` synthesises an equivalent invocation envelope for the eval rubric (see CH6 §6.5.11).
- **`create_reservation(guest_email, room_number, check_in_date, check_out_date, num_guests=1, special_requests=None)`** — Auto-registers a guest if `guest_email` is new, re-runs the availability anti-join to guard against double-booking, applies the dynamic multiplier, and inserts a row into `reservations` returning a `HTL…` confirmation number. Best-effort `sync_audit(CHAT_BOOKING_CREATED)` is wrapped in an inner `try/except pass` so the audit pipeline can never break the business flow.
- **`confirm_reservation(reservation_id)`** — Transitions a `pending` reservation to `confirmed` (status-guarded UPDATE) and emits a `CHAT_BOOKING_UPDATED` audit event with the `pending->confirmed` transition tag.
- **`update_reservation(reservation_id, check_in_date?, check_out_date?, room_number?, num_guests?, special_requests?)`** — Loads the current reservation, refuses if it is already `checked_out` or `cancelled`, optionally re-binds to a new room, recomputes `nights` and `total_amount` from the new date range, and writes the change with a `CHAT_BOOKING_UPDATED` audit row capturing the changed fields.
- **`cancel_reservation(reservation_id, reason)`** — Status-guarded UPDATE that flips a `pending` or `confirmed` reservation to `cancelled`, stores the free-text `cancellation_reason`, and emits a `CHAT_BOOKING_CANCELLED` audit event including the refund amount (so ops can detect anomalous cancellation volume).
- **`check_in_guest(reservation_id)`** — Transitions `confirmed → checked_in`, stamping `actual_check_in_time`. From this point `get_guest_reservations` is allowed to reveal the room WiFi password to that guest.
- **`check_out_guest(reservation_id)`** — Transitions `checked_in → checked_out`, stamping `actual_check_out_time` and returning a bilingual farewell block.
- **`get_reservation_details(reservation_id)`** — Reads a single reservation by either UUID or `HTL…` confirmation number, joining `rooms`, `room_types`, and `guests` to render a bilingual detail block.
- **`get_guest_reservations(guest_email)`** — Returns up to the 10 most recent reservations for a guest (`ORDER BY check_in_date DESC LIMIT 10`). The WiFi password is only included for rows whose `status = 'checked_in'`, enforcing the in-stay disclosure rule from §4.7.

**Per-tool descriptions — Service sub-agent (2 tools).**

- **`get_hotel_services()`** — Reads `hotel_services WHERE is_active = true`, ordered by category and name, and renders a bilingual catalogue with price, hours, and location for each service (spa, gym, laundry, room service, etc.).
- **`create_service_request(reservation_id, request_type, description)`** — Inserts a `service_requests` row bound to a specific reservation. The request type is free-text (e.g., *Room Service*, *Extra Towels*, *Maintenance*) and the bot is prompted to extract guest preferences (allergies, pillow preferences) from the description before calling.

**Per-tool descriptions — Knowledge sub-agent (direct RAG, not LLM-bound).**

- **`search_hotel_knowledge(query)`** — Embeds the guest query with `qwen3-embedding-8b`, runs a top-k Qdrant search against the `hotel_knowledge` collection (k=30 initial, top 3 returned after reranking), and returns the concatenated chunks. `handle_knowledge` invokes this directly via `.invoke()` rather than through a `bind_tools` round-trip — there is no tool-calling LLM step in the knowledge path, only a `rag_prompt | llm` synthesis. The knowledge sub-agent can also emit a *synthetic* `AIMessage(tool_calls=…)` purely so that the eval harness can score the path via the `tool_invocation_match` rubric (see CH6 §6.3.1).

**Per-tool descriptions — Other Talk sub-agent.**

- *(no tools)* — `handle_other` answers greetings, thanks, and off-topic small talk with an unbound LLM call capped at 512 `max_tokens`, and never reaches the DB or Qdrant.

For the underlying schemas that each tool reads or writes — `rooms`, `room_types`, `reservations`, `guests`, `hotel_services`, `service_requests`, `audit_log` — see §4.4 *Database Design*. For how the eval harness verifies that the *expected* tool was called for a given utterance, see §6.3.1 *Rubric Types* (specifically the `tool_invocation_match` rubric, which asserts on `expected_tool_calls`).

## 4.4 Database Design

### 4.4.1 Entity-Relationship Diagram

[Figure 3.3: ER diagram — Core entities: room_types (1:N rooms), rooms (1:N reservations), guests (1:N reservations, 0:1 users), reservations (1:N service_requests), users (1:N audit_log), conversation_history (session_id as logical FK). Additional tables: housekeeping, hotel_services, payment_links.]

### 4.4.2 Key Tables

The PostgreSQL schema (`deploy/compose/init-scripts/init-hotel.sql`) defines 10 tables:

| Table | Rows (seeded) | Purpose |
|-------|---------------|---------|
| room_types | 4 | Standard, Deluxe, Suite, Penthouse |
| rooms | ~50 | Individual rooms with floor, status, view |
| guests | Dynamic | Guest profiles (email as unique identifier) |
| reservations | Dynamic | Bookings with confirmation number (HTL...) |
| users | Dynamic | Auth accounts (separate from guests) |
| audit_log | Dynamic | Admin action trail (JSONB details) |
| conversation_history | Dynamic | Chat messages (session_id, role, content) |
| service_requests | Dynamic | Amenity and maintenance requests |
| payment_links | Dynamic | Mock payment tokens (UUID, 30-min expiry) |
| hotel_services | ~10 | Available hotel services catalog |

## 4.5 RAG Pipeline Design

[Figure 3.4: RAG pipeline — 10 hotel knowledge markdown files (dining.md, spa.md, facilities.md, policies.md, FAQ.md, etc.) are chunked with auto-calculated chunk size based on embedding model token limit, embedded via OpenRouter qwen3-embedding-8b (4096 dimensions), and stored in Qdrant collection "hotel_knowledge". At query time: user message → embed → Qdrant top-k search (k=30 initial, top 3 returned) → context injection → LLM generates grounded response.]

### 4.5.1 Embedding Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Model | qwen/qwen3-embedding-8b | Bilingual Thai/English support |
| Dimensions | 4096 | Model's native output dimensionality |
| Chunk size | Auto-calculated (~3,200 chars) | 80% of model's token limit × 4 chars/token |
| Chunk overlap | 20% of chunk size | Preserve context across chunk boundaries |
| Distance metric | Cosine similarity | Standard for text embeddings |

## 4.6 Authentication and Authorization Design

### 4.6.1 JWT Authentication Flow

[Figure 3.5: JWT authentication sequence diagram — (1) POST /auth/register or /auth/login → (2) bcrypt password verify → (3) generate JWT with {sub, role, user_id, iat, exp, jti} → (4) return {access_token, user}. Subsequent requests: (5) Authorization: Bearer <token> → (6) decode + verify signature → (7) check jti blocklist → (8) check password_changed_at vs iat → (9) return user dict or 401.]

### 4.6.2 Access Control Matrix

[Figure 3.6: Access control matrix — every endpoint × role, mapped from the live `src/hotel_guardrails/server.py` route declarations and the `require_admin` / `get_current_user` FastAPI dependencies]

The system exposes **51 endpoints** across 13 tag groups. Each endpoint is classified into one of three authorization tiers based on the FastAPI dependency declared in its handler signature:

- **Public** (no dependency): 26 endpoints — guest-facing chat, browse, and self-service booking flows
- **Logged-in user** (`Depends(get_current_user)`): 3 endpoints — registered-account self-management
- **Admin** (`Depends(require_admin)`): 22 endpoints — all `/admin/*`, all `/dashboard/*`, plus 3 control endpoints

Each cell shows the HTTP status returned for that role × endpoint combination. `200` means access granted; `401` means the request was rejected for missing/invalid token; `403` means the token was valid but the role was insufficient.

**Tier 1 — Public endpoints (26)** — accessible to anonymous guests; no `Authorization` header required:

| Method | Endpoint | No Token | User Token | Admin Token |
|--------|----------|:--------:|:----------:|:-----------:|
| GET | `/` | 200 | 200 | 200 |
| GET | `/healthz` | 200 | 200 | 200 |
| GET | `/health` | 200 | 200 | 200 |
| POST | `/chat` | 200 | 200 | 200 |
| POST | `/chat/stream` | 200 | 200 | 200 |
| POST | `/tools/book` | 200 | 200 | 200 |
| GET | `/rooms` | 200 | 200 | 200 |
| GET | `/rooms/availability` | 200 | 200 | 200 |
| GET | `/rooms/{room_id}` | 200 | 200 | 200 |
| GET | `/bookings` | 200 | 200 | 200 |
| GET | `/bookings/{reservation_id}` | 200 | 200 | 200 |
| PATCH | `/bookings/{reservation_id}` | 200 | 200 | 200 |
| POST | `/guests` | 200 | 200 | 200 |
| GET | `/guests/{email}` | 200 | 200 | 200 |
| PATCH | `/guests/{guest_id}` | 200 | 200 | 200 |
| POST | `/sessions` | 200 | 200 | 200 |
| GET | `/sessions/{session_id}` | 200 | 200 | 200 |
| DELETE | `/sessions/{session_id}` | 200 | 200 | 200 |
| POST | `/feedback` | 200 | 200 | 200 |
| GET | `/feedback/stats` | 200 | 200 | 200 |
| GET | `/payment/{token}` | 200 | 200 | 200 |
| POST | `/payment/{token}/complete` | 200 | 200 | 200 |
| GET | `/settings/llm` | 200 | 200 | 200 |
| GET | `/settings/models` | 200 | 200 | 200 |
| POST | `/auth/register` | 200 | 200 | 200 |
| POST | `/auth/login` | 200 | 200 | 200 |

**Tier 2 — Logged-in user endpoints (3)** — require a valid JWT of any role:

| Method | Endpoint | No Token | User Token | Admin Token |
|--------|----------|:--------:|:----------:|:-----------:|
| GET | `/auth/me` | 401 | 200 | 200 |
| PATCH | `/auth/me/password` | 401 | 200 | 200 |
| POST | `/auth/logout` | 401 | 200 | 200 |

**Tier 3 — Admin-only endpoints (22)** — require JWT with `role='admin'`:

| Method | Endpoint | No Token | User Token | Admin Token |
|--------|----------|:--------:|:----------:|:-----------:|
| GET | `/auth/users` | 401 | 403 | 200 |
| POST | `/auth/admin/register` | 401 | 403 | 200 |
| PUT | `/settings/llm` | 401 | 403 | 200 |
| PUT | `/admin/rooms/{room_id}/status` | 401 | 403 | 200 |
| PUT | `/admin/bookings/{reservation_id}/status` | 401 | 403 | 200 |
| POST | `/admin/chat/override` | 401 | 403 | 200 |
| POST | `/admin/sessions/{session_id}/takeover` | 401 | 403 | 200 |
| POST | `/admin/sessions/{session_id}/release` | 401 | 403 | 200 |
| GET | `/admin/sessions` | 401 | 403 | 200 |
| GET | `/admin/sessions/{session_id}/messages` | 401 | 403 | 200 |
| GET | `/admin/sessions/{session_id}/states` | 401 | 403 | 200 |
| POST | `/admin/sessions/{session_id}/rollback` | 401 | 403 | 200 |
| POST | `/admin/sessions/{session_id}/replay` | 401 | 403 | 200 |
| GET | `/admin/audit` | 401 | 403 | 200 |
| GET | `/admin/audit/stats` | 401 | 403 | 200 |
| GET | `/admin/escalations` | 401 | 403 | 200 |
| GET | `/admin/metrics/chat` | 401 | 403 | 200 |
| GET | `/dashboard/stats` | 401 | 403 | 200 |
| GET | `/dashboard/bookings/recent` | 401 | 403 | 200 |
| GET | `/dashboard/sessions` | 401 | 403 | 200 |
| GET | `/dashboard/rooms` | 401 | 403 | 200 |
| GET | `/dashboard/revenue` | 401 | 403 | 200 |

**Design rationale.** Authentication is intentionally **decoupled from identification**. The guest-facing chat path uses *email* as the primary identifier (provided inline through natural-language booking, e.g. *"my email is `alice@example.com`"*), allowing first-time guests to reserve a room without creating an account. Account creation via `/auth/register` is optional and unlocks Tier 2 self-management (`/auth/me`, change password, logout-with-token-revocation) but does **not** unlock any booking capability the anonymous path doesn't already provide.

All 22 staff-side operations — including the privacy-sensitive ones (`/admin/sessions/{id}/messages` reading guest conversation history, `/admin/audit` viewing every system mutation, `/admin/sessions/{id}/takeover` interrupting a live conversation) — are uniformly gated by `Depends(require_admin)`, which: (1) verifies the JWT signature, (2) checks the `jti` against the in-memory token blocklist, (3) validates `iat ≥ password_changed_at` to invalidate stale tokens after password change, and (4) asserts `role='admin'` from the token claims. A user-role JWT presenting any admin endpoint receives `403 Forbidden` rather than `401 Unauthorized` — making it observable in audit logs that the credential was valid but insufficient (e.g. compromised user account being used to probe admin surfaces).

**Coverage summary**:

| Tier | Count | % of total | Validation method |
|------|------:|----------:|-------------------|
| Public (no auth) | 26 | 51% | — |
| User (any logged-in) | 3 | 6% | `Depends(get_current_user)` |
| Admin only | 22 | 43% | `Depends(require_admin)` |
| **Total** | **51** | **100%** | — |

This matrix is verified by the 21-case integration test suite documented in Appendix A (`AP_A_Test_Results.md`), which probes every admin/dashboard endpoint with each of the three role classes and asserts the expected HTTP status.

## 4.7 Frontend Design

### 4.7.1 Next.js 15 App Router

The frontend uses the **App Router** with React Server Components for server-rendered pages and `'use client'` directives for interactive components (chat, forms, dashboard). Key architectural decisions:

- **Server Components** for static pages (landing, about) — zero client JavaScript
- **Client Components** for interactive features (chat with SSE streaming, admin dashboard with real-time updates)
- **API Routes** (`/api/hotel/[...path]`) as a proxy to the backend — all backend calls go through Next.js, avoiding CORS issues

### 4.7.2 State Management Architecture

| Concern | Solution | Justification |
|---------|----------|---------------|
| Global state (auth, theme) | Zustand stores | Minimal boilerplate vs. Redux (Salah, 2024) |
| Server data (rooms, bookings) | SWR hooks | stale-while-revalidate pattern (RFC 5861) |
| Form state | React local state | No need for global store for form inputs |
| Chat messages | Zustand + SSE | Real-time streaming with persistent client state |

## 4.8 Deployment Architecture

[Figure 3.7: Docker Compose topology showing 5 services on hotel-ai-network bridge. Volume mounts: hotel-db-data (PostgreSQL persistent), hotel-ollama-data (model weights), hotel-qdrant-data (vector index). Health checks on all services. hotel-api depends_on all others with condition: service_healthy.]

```yaml
# deploy/compose/docker-compose.hotel.yaml (simplified)
services:
  hotel-ollama:   # GPU, OLLAMA_NUM_PARALLEL=2, FLASH_ATTENTION=1
  hotel-db:       # PostgreSQL 16, init-hotel.sql on first boot
  hotel-redis:    # Session cache, 12h TTL
  hotel-qdrant:   # Vector store, hotel_knowledge collection
  hotel-api:      # FastAPI, all env vars, depends_on all above
```

## 4.9 Production LLM transition — Qwen3.5-Opus-9B → Gemma 4 12B Q8_0

### 4.9.1 Original choice and what it delivered

The first production-ready local backend was `fredrezones55/qwen3.5-opus:9b` (Q5_K_M, 6.5 GB weights) served through Ollama. The 9B was selected because: (a) it is Apache-2.0, (b) Qwen's trilingual training data delivered usable EN / TH / CN coverage out-of-the-box, (c) at Q5_K_M it fits two concurrent inference slots on the RTX 5080 (16 GB) alongside the `bge-reranker-v2-m3` cross-encoder (~1.3 GB), (d) it scored 23/25 = 92 % on the original 25-case golden eval (§6.2.1) against 25/25 = 100 % for cloud Qwen3-max, and (e) warm latency held around 9 s per chat. The 9B carried the project through Phase G (per-model prompt versioning), the dual-plane memory rollout (PostgresSaver + PostgresStore, 27/27 memory test pass), and the trilingual-policy + Chinese-leak guard work that closed §5.14.7.

### 4.9.2 Why the swap

Three convergent pressures emerged during Phase H pre-production stress testing on the strategic backtest dataset (313–502 cases per language stratum, §6.5.4):

1. **TH politeness-particle discipline.** Roughly 20–25 % of TH replies under the 9B mixed the masculine ครับ and feminine ค่ะ particles within a single response. The bot's persona policy fixes the speaker as female (ค่ะ/คะ), so any ครับ leak is a defect under the `particle_mismatch` defect class.
2. **Multi-intent collapse.** On Thai turns combining two sub-questions in one utterance — typically "WiFi password + breakfast time" or "pool hours + gym floor" — the 9B dropped the second sub-question ~30 % of the time, even with explicit Phase H.B multi-intent decomposition enabled.
3. **Pronoun resolution across booking turns.** On the multi-turn comparison case `mt_en_room_type_pivot` ("Tell me about the Deluxe Room." → "How is it different from the Suite?") the 9B lost the Suite anaphora roughly 40 % of the time and asked the guest to clarify which room they meant.

Gemma 4 12B IT was Google's freshly released open-weight instruction-tuned model at that point. The internal hypothesis: the 12B parameter count plus Google's instruction-tuning recipe would close the multi-intent and pronoun-resolution gaps without a corresponding loss of TH/CN politeness. Q8_0 was selected over the Q5/Q4 alternatives because Thai instruction-following degraded measurably at lower quants — a controlled 5-case TH-particle smoke at Q5 showed 4/5 replies mixing ครับ/ค่ะ, while the same prompts at Q8 showed 0/5 mixing.

### 4.9.3 The architectural compromise

Q8_0 at 12 B parameters occupies ~12 GB on disk. With the KV cache loaded, peak VRAM consumption is ~15.8 GB — leaving ~200 MB of headroom on the 16 GB RTX 5080 alongside `bge-reranker-v2-m3`. Two consequences fall out of this budget:

- **`OLLAMA_NUM_PARALLEL` drops from 2 to 1.** The 9B Q5 had supported two concurrent inference slots (~5 s warm each, alone; ~10 s each, with both busy). Under the 12B Q8 a second concurrent inference exceeds the VRAM budget and forces layer offloading to CPU, slowing every active request by an order of magnitude. The compromise is to serialise: one inference at a time, longer per-request latency.
- **Eval driver concurrency pins to 1.** The `backtest_runner.py --max-chat-parallel` flag was previously defaulted to 2 for localhost endpoints. Phase I.B (§6.5.8.5) documented the queue-artifact regression this caused once the model swap forced `MAX_CONCURRENT_LLM_CALLS=1`: every second concurrent eval `/chat` waited 45 s on the FastAPI semaphore, timed out, and was recorded as `empty_response`. The fix pinned `--max-chat-parallel=1` for the local stack and raised `LLM_QUEUE_TIMEOUT_SEC` from 30 to 240 defensively.
- **`OLLAMA_FLASH_ATTENTION=1` stays on but Q8 KV-cache quantisation stays off.** Flash attention itself accelerates attention compute losslessly. KV-cache quantisation at q8_0 was tested but triggered the same CPU-offload path as a second concurrent inference, slowing the model ~10× — disabled (`OLLAMA_KV_CACHE_TYPE` unset).

### 4.9.4 Quantisation choice: why Q8_0 over Q4_K_M for the 12B

The 12B model exposes two viable quant levels for a 16 GB VRAM budget, and the choice between them is not the obvious "pick the smaller one and bank the headroom." Q4_K_M packs the weights to roughly 7.5 GB on disk and leaves on the order of 6 GB of KV-cache headroom after the `bge-reranker-v2-m3` cross-encoder (~1.3 GB) is loaded; Q8_0 packs the weights to roughly 12 GB and leaves on the order of 3 GB of KV-cache headroom. On paper the Q4_K_M option looks strictly better: more concurrent slots, comfortably below the layer-offload cliff, lower keep-alive cost. The 5-case TH-particle smoke run on 2026-06-12 — the same canary set described in §4.9.5 — settled it empirically. Q4_K_M produced 4/5 TH replies that mixed the masculine ครับ with the feminine ค่ะ inside a single response, violating the female-persona policy that fixes the speaker as ค่ะ-only. Q8_0 produced 0/5 such mixes on the identical prompts. The per-stay WiFi-decline TH phrasing — a short refusal sentence the bot must deliver politely when a guest asks for a second device's voucher outside the per-stay quota — degraded similarly at Q4_K_M: the refusal landed grammatically but the politeness register slipped.

The mechanism is well-understood at this point in the open-weight literature. Q4 quants compress the embedding lookup and the attention projection matrices substantially more aggressively than Q8, and for instruction-following nuances that depend on rare-token discipline — Thai particles and Chinese honorifics being the canonical examples — the lossy compression degrades behaviour non-linearly rather than smoothly. Single-intent EN factual turns are roughly indistinguishable between Q4 and Q8 on this bot; the gap opens specifically where the policy depends on a small number of high-information tokens being preserved through the forward pass.

The net decision is Q8_0 for production despite the tighter VRAM budget. `OLLAMA_NUM_PARALLEL` dropping from 2 (at Q5/Q4 on the 9B) to 1 (at Q8 on the 12B) is the explicit concurrency compromise; the resulting throughput loss is absorbed by the adaptive escalation side-channel introduced in Phase O (CH6 §6.5.17), which keeps tail-latency budgets honest by routing the rare cold-cache request to cloud Qwen3-max. The full decision banner — including the 14/14 canary tally that gated promotion — is recorded verbatim at `.env` Phase H.D lines 11-15.

### 4.9.5 Canary smoke verification

The model swap landed on 2026-06-12 with a 14-question canary smoke that exercised the highest-traffic intents — bilingual greeting, room availability, dynamic pricing, EN/TH/CN language match, refusal patterns, and basic memory recall. The result was **14/14 effective pass** on `gemma4:12b-it-q8_0` (one item required a one-line prompt tweak; the underlying behaviour was correct). The 14/14 figure is recorded verbatim in `.env` lines 11-16 and gated promotion of the swap to the production `OLLAMA_MODEL` env value.

### 4.9.6 Quantitative comparison

| Metric                                                           | Qwen3.5-Opus-9B (Q5_K_M)                  | Gemma 4 12B IT (Q8_0)                   |
| ---------------------------------------------------------------- | ----------------------------------------- | --------------------------------------- |
| Weights size on disk                                             | ~6.5 GB                                   | ~12 GB                                  |
| Peak VRAM (incl. KV cache + bge-reranker)                        | ~10 GB                                    | ~15.8 GB                                |
| `OLLAMA_NUM_PARALLEL` viable                                   | 2                                         | 1                                       |
| Warm latency (per-chat, EN single-intent)                        | ~5 s alone, ~10 s under 2-way concurrency | ~7–15 s (single slot)                  |
| Eval aggregate, 25-case golden (CH6 §6.2)                       | 92 % (23/25)                             | not re-run (suite superseded)           |
| Eval aggregate, 354-case Phase-J-aligned suite                   | not back-ported                           | **89.83 %** (post-J.3 replay)     |
| TH particle discipline (ครับ/ค่ะ mixing rate, manual sample) | ~20–25 % of TH replies                   | 0 % in 70-turn validation                |
| Multi-intent (WiFi+breakfast) drop rate                          | ~30 %                                     | ~12 % (still imperfect, Gemma floor)     |
| Tool-call discipline (`calculate_dynamic_price`)               | high false-emission (calls when not asked)| high false-omission (skips when needed) |

### 4.9.7 Why "better" is nuanced

Gemma 4 12B Q8_0 is decisively better on TH/CN politeness, instruction-following depth, multi-intent retention, and adversarial refusal phrasing. It is decisively worse on tool-call discipline: where the 9B over-invoked `calculate_dynamic_price` (a "false emission" defect class) the 12B sometimes computes the right per-night and total prices entirely in natural language without emitting the tool call at all — a "false omission" the eval rubric counts as `tool_not_called`. Phase J.4 (§6.5.11) is the engineering response to this regression: a deterministic pricing shortcut that synthesises the missing tool envelope outside the LLM, so the bot's natural-language answer surfaces alongside a real `calculate_dynamic_price` invocation.

The net aggregate is still well above the Phase F variance baseline (80.83 % on the 9B + iter3 retrieval, §6.5.5d) because the politeness and multi-intent gains dominate the tool-call regression in the case mix. Where the 9B was strong (single-intent EN factuals), the 12B is equally strong. Where the 9B was weak (TH multi-intent, pronoun resolution, refusal phrasing), the 12B is substantially better.

### 4.9.8 Production migration steps

The cutover required no application code changes — only environment knobs and one operational change in the eval driver:

```bash
# .env (production)
OLLAMA_MODEL=gemma4:12b-it-q8_0
OLLAMA_NUM_PARALLEL=1            # was 2 under the 9B
OLLAMA_MAX_LOADED_MODELS=1
OLLAMA_KEEP_ALIVE=15m
OLLAMA_FLASH_ATTENTION=1         # losslessly accelerates attention
# KV cache q8 quantisation NOT set (causes layer offload to CPU)
MAX_CONCURRENT_LLM_CALLS=1       # must equal OLLAMA_NUM_PARALLEL
LLM_QUEUE_TIMEOUT_SEC=240        # was 30; raised after Phase I.B
```

Runtime hot-swap remains available — operators can switch back to the 9B Q5_K_M (or to cloud Qwen3-max via OpenRouter) through `PUT /settings/llm` without restarting the container. The 9B image stays in the Ollama cache for emergency rollback. The `bge-reranker-v2-m3` reranker is preserved across both models; its CPU-side fallback path is exercised under load testing in §6.4.3.
