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

## 5.2 LLM Integration

### 5.2.1 Runtime Model Switching

The system supports switching between local and cloud LLM at runtime without server restart, via `PUT /settings/llm`:

```python
# src/hotel_guardrails/hotel_langgraph.py

def get_llm(temperature=0.3, max_tokens=2048, streaming=False):
    runtime_config = get_runtime_llm_config()

    if runtime_config.backend == LLMBackend.OLLAMA:
        return ChatOpenAI(
            model=runtime_config.ollama_model,
            openai_api_base=runtime_config.ollama_base_url,
            temperature=temp, max_tokens=tokens,
        )
    else:  # OpenRouter
        runtime_config.rate_limiter.wait_and_acquire()
        model_kwargs = {}
        if runtime_config.thinking:
            model_kwargs["extra_body"] = {"reasoning": {"effort": "high"}}
        return ChatOpenAI(
            model=runtime_config.openrouter_model,
            openai_api_base=runtime_config.openrouter_base_url,
            temperature=temp, max_tokens=tokens,
            model_kwargs=model_kwargs,
        )
```

[Figure 4.1: Runtime model switching — Admin calls PUT /settings/llm with `{"backend": "openrouter"}`. The RuntimeLLMConfig singleton updates thread-safely. The next `/chat` call uses the new backend. Switching back to Ollama is equally instant.]

### 5.2.2 Model Presets

Each model has optimized presets tuned for hotel tasks:

| Model | Temperature | Max Tokens | Thinking | Rationale |
|-------|------------|------------|----------|-----------|
| Qwen3.5 Opus 9B (Ollama) | 0.3 | 2048 | Off | Native `<think>` tags; explicit thinking adds overhead |
| Qwen3 Max (OpenRouter) | 0.1 | 4096 | On | Cloud model benefits from extended reasoning |

## 5.3 LangGraph Agent Implementation

### 5.3.1 Prompt Engineering

The system prompt was iteratively optimized from ~5,500 characters to ~2,800 characters (50% reduction) to improve 9B model comprehension:

```yaml
# src/agent/hotel_prompt.yaml (optimized excerpt)
main_prompt: |
  You are a professional bilingual (Thai/English) hotel assistant
  for The Grand Horizon Hotel, a luxury 5-star hotel in Thailand.

  **CRITICAL LANGUAGE RULE**: Detect the guest's language from
  their LATEST message only.
  - English message → respond ENTIRELY in English
  - Thai message → respond ENTIRELY in Thai
  - NEVER mix languages.

  ## Tools (ALWAYS use tools — never answer from memory)
  - `search_hotel_knowledge` → hotel info
  - `check_room_availability` → room types, pricing
  - `create_reservation` / `cancel_reservation` → booking ops
  - `calculate_dynamic_price` → actual pricing with discounts
```

[Figure 4.2: Prompt template structure — main_prompt (core rules, language detection, tool catalog) is combined with booking_flow (multi-step booking guide) or service_prompt (service request handling) depending on the routed sub-agent.]

### 5.3.2 Knowledge Sub-Agent with RAG

The knowledge sub-agent retrieves hotel information using direct RAG search (not via LLM tool calling, for efficiency):

```python
# src/hotel_guardrails/hotel_langgraph.py

async def handle_knowledge(state, config):
    # Get last user message
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    # Search knowledge base (with caching)
    knowledge_result = search_hotel_knowledge.invoke(last_user_message)
    if len(knowledge_result) > 2000:
        knowledge_result = knowledge_result[:2000] + "\n..."

    # Prompt: user message FIRST, then knowledge context
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", main_prompt),
        ("human", last_user_message),
        ("system", f"Use this hotel information to answer:\n{knowledge_result}"),
    ])
```

**Key design decision**: placing the user message *before* the knowledge context prevents the 9B model from summarizing the context instead of answering the question — a failure mode discovered during testing.

## 5.4 RAG Pipeline Implementation

### 5.4.1 Knowledge Cache

Common hotel queries ("what time is breakfast?", "WiFi password?") hit repeatedly. A TTL+LRU cache avoids redundant Qdrant searches:

```python
# src/hotel_guardrails/chat_scaling.py

class KnowledgeCache:
    def get(self, query: str) -> Optional[Any]:
        k = " ".join(query.lower().split())  # normalize
        with self._lock:
            entry = self._cache.get(k)
            if entry is None:
                self._misses += 1
                return None
            ts, value = entry
            if time.time() - ts > self.ttl:
                self._cache.pop(k, None)
                self._misses += 1
                return None
            self._cache.move_to_end(k)  # LRU
            self._hits += 1
            return value
```

Cache configuration: 500 entries max, 5-minute TTL. Hit rate measured at 76% during sustained testing.

### 5.4.2 Reranker Removal

The CrossEncoder reranker (`BAAI/bge-reranker-v2-m3`) was initially used to re-score the top-30 Qdrant results. It was disabled after profiling revealed:

1. **~1–2 seconds CPU-bound work per query** — the CrossEncoder runs PyTorch inference on CPU
2. **Event loop blocking** — being synchronous inside an async endpoint, it froze the entire FastAPI server for that duration
3. **No accuracy improvement** — embedding search already achieved 8/8 on knowledge tests

## 5.5 Security Implementation

### 5.5.1 Password Hashing and JWT

```python
# src/hotel_guardrails/auth.py

def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")

def create_access_token(data: Dict[str, Any], ...) -> str:
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({
        "iat": now,
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
        "jti": uuid.uuid4().hex,  # unique token ID for blocklist
    })
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")
```

### 5.5.2 Login Rate Limiting and Account Lockout

Login is protected by three layers:

1. **Per-IP sliding window** (100 attempts/minute) — stops mass brute-force from one source
2. **Per-username sliding window** (5 attempts/minute) — stops credential stuffing on one account
3. **Account lockout** — 5 cumulative failures lock the account for 15 minutes (`users.locked_until` column)

### 5.5.3 PII Redaction

```python
# src/hotel_guardrails/pii_redactor.py

PII_PATTERNS = {
    "CREDIT_CARD": re.compile(r"\b(?:\d{4}[-\s]?){3}\d{4}\b"),
    "THAI_NATIONAL_ID": re.compile(r"\b\d{1}-\d{4}-\d{5}-\d{2}-\d{1}\b"),
    "PASSPORT": re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"),
    "PHONE_TH": re.compile(r"\b0[689]\d[-\s]?\d{3}[-\s]?\d{4}\b"),
    "EMAIL": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
}
```

[Figure 4.5: PII redaction flow — guest types "My card is 4111-1111-1111-1111" → regex matches CREDIT_CARD → LLM sees "My card is [CREDIT_CARD]" → response does not echo the number.]

### 5.5.4 Audit Logging

Every admin action, authentication event, and privacy-sensitive operation (admin reading guest conversations) is recorded in the `audit_log` table with actor identity, IP address, user agent, success flag, and JSONB details.

## 5.6 Scaling Implementation

### 5.6.1 LLM Concurrency Semaphore

The core scaling primitive — prevents Ollama queue saturation:

```python
# src/hotel_guardrails/chat_scaling.py

class LLMConcurrencyLimiter:
    async def acquire(self) -> None:
        with self._lock:
            self._waiting += 1
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.queue_timeout,  # 45s
            )
        except asyncio.TimeoutError:
            raise LLMQueueTimeout(
                "LLM queue saturated — could not acquire slot"
            )
        with self._lock:
            self._waiting -= 1
            self._in_flight += 1
```

[Figure 4.3: Scaling component pipeline — POST /chat → chat_rate_limiter (429 if exceeded) → session_lock (serialize same-session requests) → llm_limiter (503 if all slots busy for 45s) → LangGraph → knowledge_cache (skip Qdrant if cached) → Ollama (OLLAMA_NUM_PARALLEL=2 GPU slots)]

### 5.6.2 DB Connection Pool

Replaced per-request `psycopg2.connect()` with `ThreadedConnectionPool` (min=2, max=20). Connections are checked out for the duration of a query and returned to the pool on completion — eliminating connection setup overhead.

### 5.6.3 User Lookup Cache

Every authenticated request triggers `get_current_user` which queries the `users` table. A TTL-based in-memory cache (30-second TTL, max 5,000 entries) reduces this to one DB hit per user per 30 seconds. The cache is invalidated on password change, account disable, and failed login attempts.

## 5.7 Frontend Implementation

### 5.7.1 Chat Interface with SSE Streaming

The chat interface uses Server-Sent Events for real-time token-by-token streaming:
- Frontend opens a `POST /chat/stream` connection
- Backend streams `data: {"content": "token", "done": false}` events
- Final event: `data: {"content": "", "done": true, "session_id": "..."}`
- Frontend renders tokens as they arrive using a Zustand store

### 5.7.2 Admin Dashboard

The admin dashboard provides:
- **Session monitor** — live list of active chat sessions with last-message preview
- **Chat viewer** — full conversation history with role indicators (user/bot/admin/system)
- **Takeover/release** — admin can pause the bot and respond directly to guests
- **Audit log viewer** — filterable, paginated audit trail
- **Room/booking status** — override controls for front-desk operations
- **LLM model switcher** — dropdown to change backend at runtime
- **Metrics dashboard** — scaling primitive stats (LLM slots, cache hit rate, active streams)

### 5.7.3 Authentication Flow

The frontend stores the JWT in localStorage (demo-appropriate; httpOnly cookies recommended for production). Every admin API call includes `Authorization: Bearer <token>`. On 401, the user is redirected to the login page. On 403, an "access denied" message is shown.

## 5.8 Human Escalation System

The escalation monitor checks three triggers after every bot response:

1. **Sentiment** — keyword matching for frustration phrases in Thai and English ("terrible", "แย่มาก", "speak to manager", "ร้องเรียน")
2. **Repetition** — `difflib.SequenceMatcher` detects 3+ messages with >70% similarity in the last 5 messages (guest is stuck in a loop)
3. **High-value** — total booking amount > 50,000 THB or Penthouse room type

When triggered, the session is auto-escalated: the bot is paused, a system message is injected, and the session appears in the admin dashboard escalation queue.
