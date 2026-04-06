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

[Figure 3.6: Access control matrix]

| Endpoint Category | No Token | User Token | Admin Token |
|-------------------|----------|------------|-------------|
| `/chat`, `/rooms`, `/health` | 200 | 200 | 200 |
| `/auth/me` | 401 | 200 | 200 |
| `/admin/*` (11 endpoints) | 401 | 403 | 200 |
| `/dashboard/*` (5 endpoints) | 401 | 403 | 200 |
| `PUT /settings/llm` | 401 | 403 | 200 |

This design ensures that **guest chat flow requires no authentication** (email-only identification), while all hotel staff operations are protected behind admin JWT.

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
