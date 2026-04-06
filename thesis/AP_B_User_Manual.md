# Appendix B: User Manual

## B.1 System Requirements

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | NVIDIA with 12+ GB VRAM | NVIDIA RTX 5080 (16 GB) |
| RAM | 16 GB | 32 GB |
| Storage | 20 GB free | 50 GB (model weights + Docker images) |
| CPU | 4 cores | 8+ cores |

### Software

| Software | Version | Purpose |
|----------|---------|---------|
| Docker Desktop | 24+ | Container orchestration |
| NVIDIA Container Toolkit | latest | GPU access from Docker |
| Git | 2.x | Source code management |
| Python | 3.10+ | Test scripts (not needed for Docker deployment) |
| Node.js | 18+ | Frontend development (not needed for backend-only) |

## B.2 Installation

### Step 1: Clone the Repository

```bash
git clone https://github.com/<your-repo>/hote-ai-virtual-assistant-thesis.git
cd hote-ai-virtual-assistant-thesis
```

### Step 2: Configure Environment

Copy the example environment file and edit:

```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

Key settings to configure:

| Variable | Required | Example | Purpose |
|----------|----------|---------|---------|
| `OPENROUTER_API_KEY` | Yes (for cloud LLM) | `sk-or-v1-...` | Cloud LLM API access |
| `JWT_SECRET` | Yes (change from default) | Random 64-char string | JWT signing key |
| `DEFAULT_ADMIN_PASSWORD` | Yes (change from default) | Strong password | Initial admin account |
| `OLLAMA_NUM_PARALLEL` | No (default: 2) | `2` | GPU parallel slots |
| `MAX_CONCURRENT_LLM_CALLS` | No (default: 2) | `2` | App-side concurrency cap |

### Step 3: Start the Docker Stack

```bash
docker compose -p hoteai \
  -f deploy/compose/docker-compose.hotel.yaml \
  --env-file .env \
  up -d
```

This starts 5 services:

| Service | Container | Port | Status Check |
|---------|-----------|------|--------------|
| LLM Server | hotel-ollama | 11435 | `docker exec hotel-ollama ollama list` |
| Database | hotel-db | 5433 | `docker exec hotel-db pg_isready` |
| Vector Store | hotel-qdrant | 6334 | `curl http://localhost:6334/health` |
| Cache | hotel-redis | 6380 | `docker exec hotel-redis redis-cli ping` |
| API Server | hotel-api | 8088 | `curl http://localhost:8088/healthz` |

### Step 4: Pull the Local Model

```bash
docker exec hotel-ollama ollama pull fredrezones55/qwen3.5-opus:9b
```

This downloads ~6.5 GB of model weights. First run takes 5–10 minutes.

### Step 5: Ingest Hotel Knowledge

```bash
docker exec hotel-api python scripts/ingest_hotel_knowledge.py
```

This embeds the 10 hotel knowledge documents into Qdrant. Takes ~2 minutes.

### Step 6: Verify

```bash
# Health check
curl http://localhost:8088/health

# Test chat
curl -X POST http://localhost:8088/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "What time is breakfast?"}'

# Swagger UI
open http://localhost:8088/docs
```

## B.3 Guest Usage (Chat)

### Starting a Conversation

Send a POST request to `/chat` with a message. No authentication required:

```bash
curl -X POST http://localhost:8088/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, I would like to book a room"}'
```

The system automatically:
1. Detects the language (Thai or English)
2. Routes to the appropriate sub-agent (booking, knowledge, service, or general)
3. Returns a response with session_id for continuing the conversation

### Multi-Turn Conversation

Include the `session_id` from the first response to maintain context:

```bash
curl -X POST http://localhost:8088/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "A Deluxe room for next Monday to Wednesday",
    "session_id": "abc-123-def-456"
  }'
```

### Streaming Responses

For real-time token-by-token output:

```bash
curl -X POST http://localhost:8088/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me about the spa"}' \
  --no-buffer
```

## B.4 Admin Usage

### Login

```bash
curl -X POST http://localhost:8088/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "your-password"}'
```

Save the returned `access_token` for subsequent admin requests.

### Monitor Active Sessions

```bash
curl http://localhost:8088/admin/sessions \
  -H "Authorization: Bearer <token>"
```

### Take Over a Session

When a guest needs human assistance:

```bash
# Pause the bot
curl -X POST http://localhost:8088/admin/sessions/<session_id>/takeover \
  -H "Authorization: Bearer <token>"

# Send a message as staff
curl -X POST http://localhost:8088/admin/chat/override \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id": "<session_id>", "message": "Let me help you with that."}'

# Return control to the bot
curl -X POST http://localhost:8088/admin/sessions/<session_id>/release \
  -H "Authorization: Bearer <token>"
```

### View Audit Log

```bash
curl "http://localhost:8088/admin/audit?action_prefix=admin.&limit=20" \
  -H "Authorization: Bearer <token>"
```

### Switch LLM Backend

```bash
# Switch to cloud
curl -X PUT http://localhost:8088/settings/llm \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"backend": "openrouter", "model": "qwen/qwen3-max"}'

# Switch back to local
curl -X PUT http://localhost:8088/settings/llm \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"backend": "ollama"}'
```

### View Chat Scaling Metrics

```bash
curl http://localhost:8088/admin/metrics/chat \
  -H "Authorization: Bearer <token>"
```

## B.5 Running Tests

```bash
# Model evaluation (local + cloud comparison)
python scripts/eval_model_comparison.py

# Infrastructure tests (193 total)
python scripts/test_auth.py              # 72 tests
python scripts/test_auth_hardening.py    # 38 tests
python scripts/test_audit_and_scaling.py # 46 tests
python scripts/test_chat_scaling.py      # 37 tests

# Export all test results
python scripts/export_all_test_results.py
```

## B.6 Troubleshooting

| Issue | Cause | Solution |
|-------|-------|----------|
| `/chat` returns 503 | LLM queue full | Wait for current chats to finish, or switch to cloud backend |
| `/chat` returns 429 | Rate limit exceeded | Wait for Retry-After seconds |
| Model not loading | First cold start | Wait 60–90s for model to load into GPU; subsequent calls are fast |
| "Guardrails not initialized" | NeMo disabled | Set `NEMO_GUARDRAILS_ENABLED=false` (expected in Ollama mode) |
| GPU out of memory | Too many parallel slots | Reduce `OLLAMA_NUM_PARALLEL` to 1 or 2 |
| Auth 401 on admin endpoints | Missing or expired token | Re-login via `/auth/login` |
| Thai text garbled | Terminal encoding | Use `sys.stdout.reconfigure(encoding='utf-8')` in scripts |

## B.7 Environment Variable Reference

Full list of configurable environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_BACKEND` | `ollama` | Active LLM backend: `ollama` or `openrouter` |
| `OLLAMA_BASE_URL` | `http://hotel-ollama:11434/v1` | Ollama API endpoint |
| `OLLAMA_MODEL` | `fredrezones55/qwen3.5-opus:9b` | Local model name |
| `OLLAMA_NUM_PARALLEL` | `2` | Parallel inference slots |
| `OLLAMA_FLASH_ATTENTION` | `1` | Enable flash attention |
| `OPENROUTER_API_KEY` | — | Cloud LLM API key |
| `OPENROUTER_MODEL` | `qwen/qwen3-max` | Cloud model name |
| `DATABASE_URL` | `postgresql://...` | PostgreSQL connection string |
| `QDRANT_URL` | `http://hotel-qdrant:6333` | Vector store URL |
| `JWT_SECRET` | (must change) | JWT signing secret (≥32 chars) |
| `JWT_EXPIRE_HOURS` | `24` | Token lifetime |
| `MAX_CONCURRENT_LLM_CALLS` | `2` | App-side LLM concurrency cap |
| `LLM_QUEUE_TIMEOUT_SEC` | `45` | Queue timeout before 503 |
| `CHAT_RATE_LIMIT_PER_SESSION` | `30` | Messages per minute per session |
| `MAX_CONCURRENT_STREAMS` | `20` | SSE stream connection cap |
| `KNOWLEDGE_CACHE_SIZE` | `500` | RAG cache entries |
| `KNOWLEDGE_CACHE_TTL_SEC` | `300` | RAG cache TTL (seconds) |
| `LOGIN_RATE_LIMIT_PER_IP` | `100` | Login attempts per minute per IP |
| `LOGIN_RATE_LIMIT_PER_USER` | `5` | Login attempts per minute per username |
| `LOCKOUT_THRESHOLD` | `5` | Failed logins before lockout |
| `LOCKOUT_MINUTES` | `15` | Lockout duration |
| `RERANKER_BACKEND` | `none` | Reranker: `none`, `qwen`, or `nvidia` |
| `DB_POOL_MIN` | `2` | Min DB pool connections |
| `DB_POOL_MAX` | `20` | Max DB pool connections |
| `USER_CACHE_TTL_SECONDS` | `30` | User lookup cache TTL |
