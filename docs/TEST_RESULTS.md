# Test Results & Model Tuning Report

Date: 2026-04-03

## Models Tested

| Model | Backend | Type | Cost (in/out per 1M) |
|-------|---------|------|---------------------|
| fredrezones55/qwen3.5-opus:9b | Ollama (local) | Dense 9B | Free |
| qwen/qwen3-max | OpenRouter | Qwen3 flagship | $0.78/$3.90 |
| minimax/minimax-m2.7 | OpenRouter | MoE agentic | $0.30/$1.20 |

---

## Final Test Results (All Parts A-F)

Tested on: `fredrezones55/qwen3.5-opus:9b` (Ollama local)

### Part A: Infrastructure (7/7 PASS)

| Test | Result | Detail |
|------|--------|--------|
| A1: GET /healthz | PASS | 200 OK |
| A2: GET /health | PASS | All components healthy |
| A3: GET /settings/llm | PASS | backend=ollama confirmed |
| A4a: Switch to openrouter | PASS | Runtime switch works |
| A4b: Switch back to ollama | PASS | Seamless toggle |
| A5: GET /rooms | PASS | 4 room types loaded |
| A6: GET /rooms/availability | PASS | Calendar data returned |

### Part B: Knowledge/RAG (6/6 PASS)

| Test | Result | Detail |
|------|--------|--------|
| B7: "What time is breakfast?" | PASS | Correct hours from RAG |
| B8: "What's the WiFi password?" | PASS | HOTEL2024GUEST returned |
| B9: "Cancellation policy?" | PASS | 48-hour policy from RAG |
| B10: "สปาเปิดกี่โมงครับ" (Thai spa) | PASS | Thai response with hours |
| B11: "Do you allow pets?" | PASS | Pet policy + fee info |
| B12: "Airport to hotel?" | PASS | Transport info from RAG |

### Part C: Booking Workflow (9/10 PASS)

| Test | Result | Detail |
|------|--------|--------|
| C13: Pre-register guest | PASS | API guest creation works |
| C14: "next Monday" availability | PASS | Natural language date parsed |
| C15: Room types + prices | PASS | 4 types with correct prices |
| C16: Booking request | PASS | Agent responds with options |
| C17: Reservation in DB | PASS | HTL number created, DB verified |
| C18: Confirm booking | PASS | status=confirmed in DB |
| C19: Update room type | PASS | Agent processes update |
| C20: Special requests | PASS | Updated in DB |
| C21: Reservation details | PASS | Full details with HTL number |
| C22: Cancel reservation | FAIL | Agent didn't call cancel tool in that turn |

### Part D: Advanced Scenarios (4/4 PASS)

| Test | Result | Detail |
|------|--------|--------|
| D23: Multi-room request | PASS | Agent understands 2-room request |
| D24: "this weekend" + ocean view | PASS | Natural date + preference |
| D25: Cheapest room tonight | PASS | Price comparison response |
| D26: Thai full booking request | PASS | Thai response with booking flow |

### Part E: Service Requests (3/4 PASS)

| Test | Result | Detail |
|------|--------|--------|
| E27: Extra towels | PASS | Service request acknowledged |
| E28: Hotel services list | FAIL | Routed to knowledge instead of get_hotel_services tool |
| E29: Spa booking | PASS | Spa info returned |
| E30: Airport pickup | PASS | Transport service info |

### Part F: Edge Cases (3/3 PASS)

| Test | Result | Detail |
|------|--------|--------|
| F31: Book for yesterday | PASS | Graceful rejection |
| F32: 100 guests | PASS | Explains max occupancy limits |
| F33: Off-topic weather | PASS | Redirects to hotel topics |

### Summary: 32/34 (94% pass rate)

---

## Model Comparison: Head-to-Head

Tested on identical queries with proper UTF-8 encoding via Python requests.

### Thai Breakfast Query: "สวัสดีครับ อาหารเช้าเปิดกี่โมงครับ"

| Model | Result | Time | Response Quality |
|-------|--------|------|-----------------|
| qwen3.5-opus:9b (Ollama) | PASS | ~15s | Correct hours, location, menu details |
| qwen/qwen3-max | PASS | 32s | Correct hours, location, 50+ menu items, dietary options |
| minimax/minimax-m2.7 | PASS | 39s | Correct hours, polite Thai response |

### Thai Spa Query: "สปาเปิดกี่โมง ราคาเท่าไหร่ครับ"

| Model | Result | Time | Response Quality |
|-------|--------|------|-----------------|
| qwen/qwen3-max | PASS | 12s | Hours + starting price |
| minimax/minimax-m2.7 | PASS | 32s | Detailed with emoji, formatted table |

### English Booking: "Book Deluxe room, Apr dates, 2 guests, email provided"

| Model | Result | Time | Response Quality |
|-------|--------|------|-----------------|
| qwen3.5-opus:9b (Ollama) | PASS | ~20s | Created reservation, HTL number |
| qwen/qwen3-max | PASS | 16s | One-shot booking, HTL number, clean format |
| minimax/minimax-m2.7 | PASS | 33s | Created reservation, bilingual response |

### Multi-Turn Thai Booking (5 turns, same session)

| Model | Result | Turns | Total Time |
|-------|--------|-------|-----------|
| qwen/qwen3-max | PASS | 5/5 | ~72s | 
| minimax/minimax-m2.7 | Not tested multi-turn | - | - |
| qwen3.5-opus:9b (Ollama) | PASS (after tuning) | 5/5 | ~90s |

### Verdict

| Metric | qwen3.5-opus:9b | qwen/qwen3-max | minimax-m2.7 |
|--------|-----------------|-----------------|--------------|
| Speed | Medium (~15-20s) | Fast (~12-32s) | Slow (~30-40s) |
| Cost | Free (local GPU) | $0.78/$3.90 | $0.30/$1.20 |
| Thai quality | Good | Excellent | Good |
| Tool calling | Reliable (after tuning) | Very reliable | Reliable |
| Multi-turn context | Works | Works | Not tested |
| Best for | Development | Production (default) | Budget production |

---

## Tuning Changes Made (2026-04-03)

### Issue 1: Agent Not Calling create_reservation Tool

**Symptom:** Agent checked room availability but stopped there, asking guest to pick room number instead of booking automatically.

**Root cause:** Booking prompt was too passive — told agent to "present options" rather than act.

**Fix:** Updated `src/agent/hotel_prompt.yaml` booking_flow prompt to be action-oriented:
- "Pick the FIRST available room automatically"
- "Don't ask for room numbers"
- Natural conversation guide instead of rigid steps

**Result:** Agent now books on first try when all info is provided.

### Issue 2: RAG Knowledge Responses Were Generic Summaries

**Symptom:** Agent received RAG context but responded with "I notice you've provided a document, but no question was included" instead of answering the question.

**Root cause:** The RAG prompt put the knowledge context BEFORE the user messages in the ChatPromptTemplate. The 9B model treated the large knowledge text as the "input" and couldn't find the user's question.

**Fix:** Restructured `handle_knowledge()` in `src/hotel_guardrails/hotel_langgraph.py`:
```
Before: system(prompt + knowledge) → messages
After:  system(prompt) → messages → system(knowledge + "answer the question above")
```
Also trimmed knowledge context to max 2000 chars to prevent overshadowing.

**Result:** Part B went from 3/6 PASS to 6/6 PASS.

### Issue 3: Multi-Turn Context Lost Between Turns

**Symptom:** By turn 4-5 of a booking conversation, the agent forgot earlier context (dates, room selection, email).

**Root cause:** `invoke_hotel_agent()` rebuilt the full message history from `conversation_history` param AND the MemorySaver checkpointer had its own state. This caused duplicate/conflicting messages.

**Fix:** Changed `invoke_hotel_agent()` in `src/hotel_guardrails/hotel_langgraph.py` to only send the NEW message — MemorySaver already preserves conversation history:
```python
# Before: rebuilt all history + new message
messages = [history...] + [new_message]

# After: only new message, checkpointer handles history
messages = [new_message]
```

**Result:** Full 5-turn Thai booking conversation works with context preserved across all turns.

### Issue 4: Guest Registration Required Before Booking

**Symptom:** `create_reservation` returned "ไม่พบผู้เข้าพัก... กรุณาลงทะเบียนก่อน" when email was new.

**Root cause:** Tool required pre-registered guest. User requirement: no account creation needed.

**Fix:** Added auto-registration in `create_reservation()` in `src/agent/hotel_tools.py`:
```python
# If guest email not found, auto-create with email only
if not guest:
    cur.execute("INSERT INTO guests (email, first_name, ...) VALUES (%s, 'Guest', ...)")
```

**Result:** New guests can book with just an email — no registration friction.

### Issue 5: Guest Registration Schema Mismatch

**Symptom:** POST /guests returned 400 — `column "id_type" does not exist`.

**Root cause:** `create_guest()` in `src/hotel_guardrails/database.py` referenced columns `id_type`, `date_of_birth`, `address` that don't exist in the actual schema.

**Fix:** Removed non-existent columns from the INSERT query, matched to actual table schema.

**Result:** Guest registration API works correctly.

### Issue 6: Thai Text Encoding on Windows

**Symptom:** Thai test queries from curl produced garbled text; agent responded "your message appears garbled."

**Root cause:** Windows curl sends UTF-8 bytes but the terminal uses cp1252 encoding, mangling Thai characters.

**Fix:** 
- Test script: added `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`
- Replaced Unicode symbols (checkmarks, arrows) with ASCII equivalents
- Used Python `requests` library instead of curl for Thai tests

**Result:** All Thai tests pass correctly through Python requests.

### Issue 7: Hardcoded Hotel Knowledge in Prompt

**Symptom:** Hotel info (breakfast times, WiFi password, spa prices) was hardcoded in `hotel_prompt.yaml` — not modular or editable.

**Root cause:** Original prompt had 50 lines of facility details embedded directly.

**Fix:** Removed hardcoded hotel info from `src/agent/hotel_prompt.yaml`. Replaced with instruction to use `search_hotel_knowledge` tool. All info now comes from RAG (Qdrant knowledge base loaded from `data/hotel/*.md`).

**Result:** Hotel information is fully modular — edit markdown files and re-ingest to update.

---

## Per-Model Optimization Presets

Auto-applied when switching models via `PUT /settings/llm`.

| Model | Temperature | Max Tokens | Thinking | Rationale |
|-------|-------------|------------|----------|-----------|
| qwen3.5-opus:9b (Ollama) | 0.3 | 2048 | On (built-in) | Balanced for tool calling |
| qwen/qwen3-max | 0.3 | 2048 | On (reasoning param) | Reliable reasoning |
| qwen/qwen3.5-397b-a17b | 0.3 | 2048 | On | Latest, most capable |
| qwen/qwen3.5-flash | 0.3 | 1024 | Off | Speed over reasoning |
| minimax/minimax-m2.7 | 0.3 | 2048 | On | Agentic workloads |

Unknown models get auto-detected presets based on name patterns:
- `*opus*`, `*max*`, `*large*`, `*pro*` → temp=0.2, max=2048, thinking=on
- `*thinking*` → temp=0.1, max=4096, thinking=on
- `*flash*`, `*mini*`, `*small*` → temp=0.4, max=1024, thinking=off
- Default → temp=0.3, max=1024, thinking=on

Implementation: `get_model_presets()` in `src/hotel_guardrails/config.py`
