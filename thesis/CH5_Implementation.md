# Chapter 5: Implementation

## 5.1 Development Environment and Tools

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Backend framework | FastAPI | 0.115 | Async REST API with auto OpenAPI docs |
| Agent framework | LangGraph | 0.2.32 | Multi-agent state machine |
| LLM interface | LangChain-OpenAI | 0.1+ | Unified LLM API for Ollama and OpenRouter |
| Database | PostgreSQL | 16 | Relational storage (rooms, bookings, users) |
| Vector store | Qdrant | latest | Embedding similarity search |
| Cache | Redis | 7.0 | Session state |
| Local LLM | Ollama | latest | GPU inference for Qwen3.5 Opus 9B |
| Cloud LLM | OpenRouter API | — | Qwen3 Max (cloud fallback) |
| Frontend | Next.js | 15.5 | React App Router with RSC |
| UI library | Ant Design | 5.29 | Enterprise component library |
| State management | Zustand | 5.0 | Lightweight global state |
| Data fetching | SWR | 2.4 | stale-while-revalidate hooks |
| Language | TypeScript | 5.x | Static typing (Gao et al., 2017) |
| Auth | PyJWT + bcrypt | 2.12 / 5.0 | JWT tokens + password hashing |
| Containerization | Docker Compose | — | 5-service orchestration |

## 5.2 Implementation Order

The system was built incrementally following the git commit history. Each phase produced a working increment deployed via Docker Compose and verified with tests before proceeding to the next.

### Phase 1: Foundation — FastAPI Server and Database (Commits 4ba78d1–acdd8d8)

The first phase established the FastAPI application server with OpenAPI documentation, PostgreSQL database schema (10 tables), and basic REST endpoints for rooms, bookings, and session history.

```python
# src/hotel_guardrails/server.py — Initial FastAPI app setup
app = FastAPI(
    title="The Grand Horizon Hotel Concierge API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)
```

Key files created:
- `src/hotel_guardrails/server.py` — FastAPI application with middleware, CORS, error handling
- `src/hotel_guardrails/database.py` — PostgreSQL connection and CRUD operations
- `src/hotel_guardrails/models.py` — Pydantic request/response models
- `deploy/compose/init-scripts/init-hotel.sql` — Database schema with 10 tables

### Phase 2: RAG Pipeline — Knowledge Base and Vector Search (Commits a886486–6386b14)

The RAG pipeline was built to enable the chatbot to answer hotel information queries (breakfast hours, WiFi password, spa services, etc.) from a structured knowledge base.

```python
# src/retrievers/hotel_knowledge/chains.py — Document ingestion
class HotelKnowledgeRetriever:
    def __init__(self):
        self.embeddings = get_openrouter_embeddings()  # qwen3-embedding-8b, 4096 dims
        self.vectorstore = create_qdrant_vectorstore(
            self.embeddings,
            collection_name="hotel_knowledge"
        )
        self.top_k_retrieval = 30  # initial candidates
        self.reranker = get_reranker(top_n=5)  # later removed for performance

    def document_search(self, content, num_docs=3):
        retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": self.top_k_retrieval}
        )
        docs = retriever.invoke(content)
        # Return top-k results (reranker disabled by default)
        return [{"source": doc.metadata.get("source"), "content": doc.page_content}
                for doc in docs[:num_docs]]
```

The knowledge base consists of 10 hotel-specific markdown documents:

| Document | Content |
|----------|---------|
| `dining.md` | Restaurant hours, menus, room service |
| `spa.md` | Spa treatments, prices, booking |
| `facilities.md` | Pool, gym, business center |
| `policies.md` | Cancellation, pets, smoking, children |
| `faq.md` | Check-in/out times, WiFi, luggage storage |
| `transport.md` | Airport transfer, taxi, BTS directions |
| `rooms.md` | Room types, amenities, views |
| `services.md` | Concierge, laundry, wake-up calls |
| `events.md` | Meeting rooms, wedding packages |
| `loyalty.md` | Loyalty program tiers and benefits |

### Phase 3: LangGraph Multi-Agent System (Commits 5073b72–10ba546)

The core AI agent was implemented as a LangGraph state machine with four specialized sub-agents. This was the most complex implementation phase, requiring iterative debugging of tool-call routing, state management, and prompt engineering.

```python
# src/hotel_guardrails/hotel_langgraph.py — Graph construction
def build_hotel_graph(checkpointer=None):
    builder = StateGraph(HotelState)

    # Nodes
    builder.add_node("primary_assistant", HotelAssistant(primary_prompt, primary_tools))
    builder.add_node("enter_booking", create_entry_node("Booking Assistant"))
    builder.add_node("enter_service", create_entry_node("Service Assistant"))
    builder.add_node("enter_knowledge", create_entry_node("Knowledge Assistant"))
    builder.add_node("hotel_booking", handle_booking)
    builder.add_node("hotel_service", handle_service)
    builder.add_node("hotel_knowledge", handle_knowledge)
    builder.add_node("other_talk", handle_other_talk)

    # Tool nodes (cyclic loops)
    builder.add_node("booking_tools", create_tool_node_with_fallback(booking_tools))
    builder.add_node("service_tools", create_tool_node_with_fallback(service_tools))

    # Edges
    builder.add_edge(START, "primary_assistant")
    builder.add_conditional_edges("primary_assistant", route_primary_assistant)
    builder.add_edge("enter_booking", "hotel_booking")
    builder.add_conditional_edges("hotel_booking", route_booking)
    builder.add_edge("booking_tools", "hotel_booking")  # cyclic tool loop
    # ... similar for service

    return builder.compile(checkpointer=checkpointer)
```

15 hotel-specific tools were implemented:

```python
# src/agent/hotel_tools.py — Example tool
@tool
def check_room_availability(
    check_in_date: str, check_out_date: str,
    room_type: Optional[str] = None
) -> str:
    """Check available rooms for specified dates."""
    with get_cursor() as (cur, conn):
        cur.execute("""
            SELECT r.room_id, r.room_number, r.floor, rt.name, rt.base_price
            FROM rooms r
            JOIN room_types rt ON r.room_type_id = rt.room_type_id
            WHERE r.status = 'available'
            AND r.room_id NOT IN (
                SELECT room_id FROM reservations
                WHERE status NOT IN ('cancelled', 'no_show')
                AND check_in_date < %s AND check_out_date > %s
            )
            ORDER BY rt.base_price ASC
        """, (check_out_date, check_in_date))
        rooms = cur.fetchall()
    # Format bilingual response...
```

| Tool | Purpose |
|------|---------|
| `check_room_availability` | Query available rooms for date range |
| `create_reservation` | Create booking with dynamic pricing |
| `confirm_reservation` | Confirm a pending booking |
| `update_reservation` | Modify dates, guests, or room |
| `cancel_reservation` | Soft-cancel with reason |
| `check_in_guest` | Mark guest as checked in |
| `check_out_guest` | Mark guest as checked out |
| `get_reservation_details` | Lookup by confirmation number (HTL...) |
| `get_guest_reservations` | Lookup by email |
| `calculate_dynamic_price` | Early bird / last-minute pricing |
| `check_upsell_opportunity` | Suggest room upgrade after booking |
| `generate_payment_link` | Create mock payment URL |
| `search_hotel_knowledge` | RAG search with knowledge cache |
| `get_hotel_services` | List available services |
| `create_service_request` | Request towels, room service, etc. |

### Phase 4: Docker Stack and Local LLM (Commit a466e45)

A self-contained Docker Compose stack was created with 5 services, replacing cloud dependencies with local alternatives:

```yaml
# deploy/compose/docker-compose.hotel.yaml
services:
  hotel-ollama:    # GPU LLM inference
    image: ollama/ollama:latest
    environment:
      OLLAMA_NUM_PARALLEL: 2
      OLLAMA_FLASH_ATTENTION: 1
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  hotel-db:        # PostgreSQL 16
  hotel-redis:     # Session cache
  hotel-qdrant:    # Vector store
  hotel-api:       # FastAPI + LangGraph
    depends_on:
      hotel-ollama: { condition: service_healthy }
      hotel-db: { condition: service_healthy }
```

Runtime model switching was implemented via a thread-safe singleton:

```python
# src/hotel_guardrails/config.py
class RuntimeLLMConfig:
    """Thread-safe singleton for runtime LLM configuration."""
    _instance = None
    _lock = threading.Lock()

    def update(self, backend=None, model=None, temperature=None, max_tokens=None):
        with self._lock:
            changes = {}
            if backend:
                self.backend = LLMBackend(backend.lower())
                changes["backend"] = backend
            if model:
                self.active_model = model
                changes["model"] = model
            # ... apply model presets
            return changes
```

### Phase 5: Authentication and Security (Commits 86529c0–b1dd1ce)

JWT authentication with role-based access control was added to separate guest (public) and admin (protected) endpoints.

```python
# src/hotel_guardrails/auth.py
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"),
                         bcrypt.gensalt(rounds=12)).decode("utf-8")

def create_access_token(data: Dict[str, Any]) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
        "jti": uuid.uuid4().hex,  # unique ID for token blocklist
    })
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")

async def get_current_user(credentials=Depends(bearer_scheme)):
    payload = decode_access_token(credentials.credentials)
    # Check jti blocklist (logged out tokens)
    if token_blocklist.contains(payload.get("jti")):
        raise HTTPException(401, "Token revoked")
    # Check password_changed_at (invalidated by password change)
    user = await db.get_user_by_username(payload["sub"])
    if int(payload["iat"]) < int(user["password_changed_at"].timestamp()):
        raise HTTPException(401, "Token invalidated by password change")
    return user
```

Production hardening added three defense layers to the login endpoint:

```python
# src/hotel_guardrails/server.py — Login rate limiting
@app.post("/auth/login")
async def auth_login(request: UserLoginRequest, http_request: Request):
    client_ip = get_client_ip(http_request)

    # Layer 1: Per-IP rate limit (100/min)
    allowed, retry_after = login_rate_limiter_ip.check_and_record(client_ip)
    if not allowed:
        raise HTTPException(429, headers={"Retry-After": str(retry_after)})

    # Layer 2: Per-username rate limit (5/min)
    allowed_u, retry_u = login_rate_limiter_user.check_and_record(username)
    if not allowed_u:
        raise HTTPException(429, headers={"Retry-After": str(retry_u)})

    # Layer 3: Account lockout (5 failures → 15-min lock)
    lockout = check_account_lockout(user)
    if lockout:
        raise HTTPException(423, headers={"Retry-After": str(lockout)})
```

### Phase 6: Audit Logging and Database Scaling (Commit db31ed7)

Every admin action, authentication event, and privacy-sensitive operation was recorded:

```python
# src/hotel_guardrails/audit.py
class AuditActions:
    LOGIN_SUCCESS = "auth.login.success"
    LOGIN_FAILED = "auth.login.failed"
    SESSION_VIEWED = "admin.session.viewed"  # admin reads guest chat
    ROOM_STATUS_CHANGED = "admin.room.status_changed"
    BOOKING_STATUS_CHANGED = "admin.booking.status_changed"
    CHAT_OVERRIDE = "admin.chat.override"
    # ... 26 action types total
```

The database connection was upgraded from per-request `psycopg2.connect()` to a `ThreadedConnectionPool`:

```python
# src/hotel_guardrails/database.py
def get_db_pool():
    global _db_pool
    if _db_pool is None:
        with _db_pool_lock:
            if _db_pool is None:
                _db_pool = pg_pool.ThreadedConnectionPool(
                    minconn=int(os.getenv("DB_POOL_MIN", "2")),
                    maxconn=int(os.getenv("DB_POOL_MAX", "20")),
                    dsn=os.getenv("DATABASE_URL"),
                )
    return _db_pool
```

### Phase 7: Chat Scaling Primitives (Commit 4b4a110)

Five concurrency primitives were added to handle multiple simultaneous users:

```python
# src/hotel_guardrails/chat_scaling.py
class LLMConcurrencyLimiter:
    """Async semaphore with queue timeout for LLM calls."""
    def __init__(self, max_concurrent: int, queue_timeout: float):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self.queue_timeout = queue_timeout

    async def acquire(self):
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.queue_timeout,
            )
        except asyncio.TimeoutError:
            raise LLMQueueTimeout("LLM queue saturated — 503")

class SessionLockManager:
    """Per-session asyncio.Lock with bounded LRU eviction."""
    def get(self, session_id: str) -> asyncio.Lock:
        with self._lock:
            if session_id not in self._locks:
                self._locks[session_id] = asyncio.Lock()
            self._locks.move_to_end(session_id)
            return self._locks[session_id]

class KnowledgeCache:
    """TTL + LRU cache for RAG query results."""
    def get(self, query: str):
        k = " ".join(query.lower().split())  # normalize
        entry = self._cache.get(k)
        if entry and time.time() - entry[0] <= self.ttl:
            self._hits += 1
            return entry[1]
        self._misses += 1
        return None
```

[Figure 5.4: Scaling component pipeline — POST /chat → chat_rate_limiter (429 if exceeded) → session_lock (serialize same-session requests) → llm_limiter (503 if all slots busy for 45s) → LangGraph → knowledge_cache (skip Qdrant if cached) → Ollama (OLLAMA_NUM_PARALLEL=2 GPU slots)]

### Phase 8: Performance Optimization (Commits 8703602–02cb9a5)

#### 8a. Reranker Removal

Profiling revealed the CrossEncoder reranker was blocking the FastAPI event loop:

```python
# src/retrievers/hotel_knowledge/chains.py — Before
RERANKER_BACKEND = os.getenv("RERANKER_BACKEND", "qwen")  # ~1-2s CPU per query

# After optimization
RERANKER_BACKEND = os.getenv("RERANKER_BACKEND", "none")  # skip reranker entirely
# Vector search alone achieves 8/8 on knowledge tests
```

Impact: Warm `/chat` latency dropped from **18s to 5s** (3.6x improvement).

#### 8b. Prompt Trimming

The system prompt was reduced from ~5,500 characters to ~2,800 characters by removing redundant bilingual duplications:

```yaml
# src/agent/hotel_prompt.yaml — Before (5,500 chars)
# Every instruction was duplicated in Thai:
# "DO NOT answer from memory. Search the knowledge base first."
# "ห้ามตอบคำถามข้อมูลโรงแรมจากความจำ ค้นหาจากฐานความรู้ก่อนเสมอ"

# After (2,800 chars) — Thai duplication removed, model is already bilingual
main_prompt: |
  You are a professional bilingual (Thai/English) hotel assistant...
  ## Tools (ALWAYS use tools — never answer from memory)
  - `search_hotel_knowledge` → hotel info
  - `check_room_availability` → room types, pricing
  ...
```

#### 8c. Ollama GPU Tuning

Benchmarking on RTX 5080 (16 GB VRAM) determined optimal parallelism:

| Config | Per-request Latency | VRAM | GPU Offload |
|--------|---------------------|------|-------------|
| `NUM_PARALLEL=4` | 30–50s | 9.9 GB | 100% GPU |
| `NUM_PARALLEL=2` (selected) | 4–9s | 9.9 GB | 100% GPU |
| `NUM_PARALLEL=2` + `Q8_0 KV` | >120s | 7.9 GB | 37% GPU / 63% CPU (broken) |

`OLLAMA_NUM_PARALLEL=2` with `FLASH_ATTENTION=1` was selected as the optimal configuration.

#### 8d. Thinking Mode Disabled for Local Model

Qwen3.5 outputs `<think>` tags natively — explicit thinking mode only added prompting overhead:

```python
# src/hotel_guardrails/config.py — Before
"presets": {"temperature": 0.3, "max_tokens": 4096, "thinking": True}

# After — native thinking, no explicit overhead, lower token budget
"presets": {"temperature": 0.3, "max_tokens": 2048, "thinking": False}
```

## 5.3 Prompt Engineering

### 5.3.1 Primary Router Prompt

The router prompt was iteratively refined to fix two recurring failures (cancel routing, service vs knowledge classification):

```python
# src/hotel_guardrails/hotel_langgraph.py — Router prompt with explicit examples
primary_prompt = f"""{main_prompt}

## Your Role
Route every guest message to exactly ONE specialist:
1. **ToHotelBooking** — reservations, availability, check-in/out, modify/cancel
   Examples: "Is there a room?", "ยกเลิกการจอง", "Check me in"
2. **ToHotelService** — room service, amenities, housekeeping, transportation
   Examples: "I need extra towels", "จองสปา"
3. **ToHotelKnowledge** — hotel info, facilities, dining, WiFi, policies
   Examples: "What time is breakfast?", "รหัส WiFi"
4. **HandleOtherTalk** — greetings, thanks, goodbye, off-topic
   Examples: "Hello", "ขอบคุณ"

IMPORTANT: "cancel my booking" → ToHotelBooking (NOT HandleOtherTalk)
"""
```

### 5.3.2 Knowledge Context Injection

The RAG context placement was critical for the 9B model. Placing knowledge BEFORE the user question caused the model to summarize the context instead of answering:

```python
# src/hotel_guardrails/hotel_langgraph.py
# WRONG: knowledge context overshadows the question
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", main_prompt),
    ("system", f"Context: {knowledge_result}"),  # ← model summarizes this
    ("human", last_user_message),
])

# CORRECT: user message first, then knowledge as supporting context
rag_prompt = ChatPromptTemplate.from_messages([
    ("system", main_prompt),
    ("human", last_user_message),  # ← model focuses on this
    ("system", f"Use this hotel information to answer:\n{knowledge_result}"),
])
```

## 5.4 PII Redaction

```python
# src/hotel_guardrails/pii_redactor.py
PII_PATTERNS = {
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "THAI_NATIONAL_ID": re.compile(r"\b\d{1}-\d{4}-\d{5}-\d{2}-\d{1}\b"),
    "PASSPORT": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
    "PHONE_TH": re.compile(r"\b0[689]\d[-\s]?\d{3}[-\s]?\d{4}\b"),
    "PHONE_INTL": re.compile(r"\b\+\d{1,3}[-\s]?\d{1,4}[-\s]?\d{3,4}[-\s]?\d{3,4}\b"),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}

def redact_pii(text: str, preserve_email: bool = False):
    """Guest: 'My card is 4111-1111-1111-1111' → LLM sees: 'My card is [CREDIT_CARD]'"""
    redacted = text
    found = {}
    for label, pattern in PII_PATTERNS.items():
        if label == "EMAIL" and preserve_email:
            continue  # preserve email during booking flow
        matches = pattern.findall(redacted)
        if matches:
            found[label] = matches
            redacted = pattern.sub(f"[{label}]", redacted)
    return redacted, found
```

[Figure 5.3: PII redaction flow — guest types "My card is 4111-1111-1111-1111" → regex matches CREDIT_CARD → LLM sees "My card is [CREDIT_CARD]" → response does not echo the number.]

## 5.5 Human Escalation System

```python
# src/hotel_guardrails/escalation.py
class EscalationMonitor:
    FRUSTRATION_EN = ["terrible", "worst", "unacceptable", "speak to manager", "complaint"]
    FRUSTRATION_TH = ["แย่มาก", "ขอพูดกับผู้จัดการ", "ร้องเรียน", "ผิดหวัง"]

    def check_sentiment(self, message):
        for word in self.FRUSTRATION_EN + self.FRUSTRATION_TH:
            if word.lower() in message.lower():
                return True, f"Frustration keyword: '{word}'"
        return False, None

    def check_repetition(self, session_id, message):
        """3+ messages with >70% similarity = guest is stuck."""
        history = self._session_messages[session_id]
        similar_count = sum(1 for prev in history
                          if SequenceMatcher(None, message, prev).ratio() > 0.7)
        return similar_count >= 3, f"Repetition detected ({similar_count} similar)"

    def check_high_value(self, context):
        """Auto-escalate for bookings > 50,000 THB or Penthouse."""
        amount = context.get("total_amount", 0)
        room_type = context.get("room_type", "")
        return amount > 50000 or room_type == "Penthouse", "High-value booking"
```

## 5.6 Frontend Implementation

The frontend was built with Next.js 15 (App Router), Ant Design 5 for UI components, Zustand for global state, and SWR for server data fetching.

### 5.6.1 Chat Interface

[Figure 5.5: Chat interface screenshot — showing the hotel chatbot with message bubbles, Thai/English responses, booking confirmations, and typing indicator during SSE streaming.]

The chat interface uses Server-Sent Events for real-time token streaming:

```typescript
// src/services/hotelAssistant/index.ts — SSE streaming client
export async function streamChat(message: string, sessionId: string,
                                  onToken: (token: string) => void) {
  const response = await fetch('/api/hotel/chat/stream', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  const reader = response.body?.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader!.read();
    if (done) break;
    const chunk = decoder.decode(value);
    // Parse SSE: "data: {"content": "token", "done": false}\n\n"
    const lines = chunk.split('\n').filter(l => l.startsWith('data: '));
    for (const line of lines) {
      const data = JSON.parse(line.slice(6));
      if (data.content) onToken(data.content);
      if (data.done) return data.session_id;
    }
  }
}
```

### 5.6.2 Room Catalog and Booking

[Figure 5.6: Room catalog page — showing room type cards with photos, prices, availability status, and "Book Now" buttons. Each card displays room size, max occupancy, and amenities.]

[Figure 5.7: Booking wizard — multi-step form with date picker, room type selection, guest count, email input, dynamic pricing display, and confirmation summary.]

```typescript
// src/app/hotel/bookings/features/BookingWizard.tsx — Multi-step booking
const BookingWizard: React.FC = () => {
  const [step, setStep] = useState<'dates' | 'room' | 'details' | 'confirm'>('dates');

  return (
    <Steps current={['dates','room','details','confirm'].indexOf(step)}>
      <Step title="Dates" />
      <Step title="Room Type" />
      <Step title="Guest Details" />
      <Step title="Confirm & Pay" />
    </Steps>
    {/* Step content with Ant Design Form, DatePicker, Select */}
  );
};
```

### 5.6.3 Admin Dashboard

[Figure 5.8: Admin dashboard overview — showing room occupancy donut chart, today's check-ins/check-outs, revenue summary, and recent bookings feed.]

[Figure 5.9: Admin session monitor — live list of active chat sessions with last-message preview, bot/admin status indicator, and "Takeover" button.]

[Figure 5.10: Admin chat viewer — full conversation history for a session, with role indicators (guest/bot/admin/system), message timestamps, and admin reply input field.]

```typescript
// src/app/hotel/admin/sessions/[sessionId]/page.tsx — Chat viewer
export default function SessionDetailPage({ params }: { params: { sessionId: string } }) {
  const { data } = useSWR(`/api/hotel/admin/sessions/${params.sessionId}/messages`,
    fetcher, { refreshInterval: 3000 }  // poll every 3s for live updates
  );

  return (
    <Card title={`Session: ${params.sessionId}`}>
      <MessageList messages={data?.messages} />
      <AdminReplyInput sessionId={params.sessionId} />
      <Space>
        <Button danger onClick={handleTakeover}>Take Over</Button>
        <Button onClick={handleRelease}>Release to Bot</Button>
      </Space>
    </Card>
  );
}
```

### 5.6.4 Settings and Model Switcher

[Figure 5.11: Settings page — showing current LLM backend (Ollama/OpenRouter), model name, temperature slider, max tokens input, and available models dropdown with "Switch" button.]

```typescript
// src/app/hotel/settings/page.tsx — Runtime model switching
const handleSwitch = async (backend: string, model: string) => {
  await fetch('/api/hotel/settings/llm', {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ backend, model }),
  });
  mutate('/api/hotel/settings/llm');  // SWR revalidate
  message.success(`Switched to ${model}`);
};
```

### 5.6.5 Authentication UI

[Figure 5.12: Login/Register modal — showing username/email input, password field, "Login" and "Register" tabs, and error messages for wrong password or duplicate username.]

```typescript
// src/app/hotel/features/AuthModal.tsx — Login form
const AuthModal: React.FC<{ open: boolean; onClose: () => void }> = ({ open, onClose }) => {
  const login = useHotelStore(s => s.login);

  const handleLogin = async (values: { username: string; password: string }) => {
    const res = await fetch('/api/hotel/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(values),
    });
    if (res.ok) {
      const { access_token, user } = await res.json();
      login(access_token, user);
      onClose();
    } else if (res.status === 429) {
      message.error('Too many attempts. Please wait.');
    }
  };

  return (
    <Modal open={open} onCancel={onClose} title="Login">
      <Form onFinish={handleLogin}>
        <Form.Item name="username" rules={[{ required: true }]}>
          <Input placeholder="Username or email" />
        </Form.Item>
        <Form.Item name="password" rules={[{ required: true }]}>
          <Input.Password placeholder="Password" />
        </Form.Item>
        <Button type="primary" htmlType="submit">Login</Button>
      </Form>
    </Modal>
  );
};
```

### 5.6.6 State Management with Zustand

```typescript
// src/store/hotel/slices/auth.ts — Auth state slice
interface AuthSlice {
  token: string | null;
  user: User | null;
  isAdmin: boolean;
  login: (token: string, user: User) => void;
  logout: () => void;
}

export const createAuthSlice: StateCreator<AuthSlice> = (set) => ({
  token: typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null,
  user: null,
  isAdmin: false,
  login: (token, user) => {
    localStorage.setItem('auth_token', token);
    set({ token, user, isAdmin: user.role === 'admin' });
  },
  logout: () => {
    localStorage.removeItem('auth_token');
    set({ token: null, user: null, isAdmin: false });
  },
});
```

### 5.6.7 API Proxy (Avoiding CORS)

All backend calls go through a Next.js API route that proxies to the FastAPI server:

```typescript
// src/app/api/hotel/[...path]/route.ts — Catch-all proxy
export async function POST(request: Request, { params }: { params: { path: string[] } }) {
  const path = params.path.join('/');
  const body = await request.json();
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };

  // Forward auth header if present
  const auth = request.headers.get('Authorization');
  if (auth) headers['Authorization'] = auth;

  const res = await fetch(`${BACKEND_URL}/${path}`, {
    method: 'POST', headers, body: JSON.stringify(body),
  });
  return new Response(res.body, { status: res.status, headers: res.headers });
}
```

This eliminates CORS issues entirely — the browser only talks to the Next.js origin, and Next.js makes server-to-server calls to FastAPI.

## 5.7 LLM Integration — Runtime Switching

[Figure 5.1: Runtime model switching — Admin calls PUT /settings/llm with `{"backend": "openrouter"}`. The RuntimeLLMConfig singleton updates thread-safely. The next `/chat` call uses the new backend. Switching back to Ollama is equally instant.]

```python
# src/hotel_guardrails/hotel_langgraph.py — get_llm() with backend branching
def get_llm(temperature=0.3, max_tokens=2048, streaming=False):
    runtime_config = get_runtime_llm_config()

    if runtime_config.backend == LLMBackend.OLLAMA:
        return ChatOpenAI(
            model=runtime_config.ollama_model,
            openai_api_base=runtime_config.ollama_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    else:  # OpenRouter cloud
        runtime_config.rate_limiter.wait_and_acquire()
        model_kwargs = {}
        if runtime_config.thinking:
            model_kwargs["extra_body"] = {"reasoning": {"effort": "high"}}
        return ChatOpenAI(
            model=runtime_config.openrouter_model,
            openai_api_base=runtime_config.openrouter_base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            model_kwargs=model_kwargs,
        )
```

[Figure 4.2: Prompt template structure — main_prompt (core rules, language detection, tool catalog) is combined with booking_flow (multi-step booking guide) or service_prompt (service request handling) depending on the routed sub-agent.]
