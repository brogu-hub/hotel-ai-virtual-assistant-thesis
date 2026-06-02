---
type: component
path: "src/hotel_guardrails/actions.py"
status: active
parent_module: hotel_guardrails
tags: [component, tools, rag, safety, booking, bilingual]
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/actions.py
---

# actions.py — Hotel Tool Catalog

## Purpose

`actions.py` is the tool layer of the `hotel_guardrails` service. It provides async Python functions that wrap three distinct concerns: RAG-based knowledge retrieval, booking CRUD (delegated to `src/agent/hotel_tools.py`), safety classification, and bilingual utilities. These functions are called directly by `server.py` endpoint handlers and, in some cases, bound as tools to LangGraph sub-agent tool nodes.

> [!note]
> The booking actions in this file are **thin wrappers** — they delegate to `src/agent/hotel_tools.py` via LangChain `.invoke()`. The actual SQL-level booking logic lives in `hotel_tools.py` and `database.py`. `actions.py` contributes error handling, bilingual error messages (Thai / English), and a uniform `dict(return_value=...)` response envelope.

---

## Tool Catalog

### RAG Group

| Tool | Signature | Returns | Called by |
|---|---|---|---|
| `search_hotel_knowledge` | `(query: str) → dict` | `{"return_value": str}` | `knowledge_subagent`, direct server calls |
| `search_hotel_knowledge_with_sources` | `(query: str) → tuple` | `(content: str, sources: list[str], retrieval_context: list[str])` | Evaluation scripts, DeepEval runner |

#### `search_hotel_knowledge`

The primary RAG entry point. Lazily initializes a `HotelKnowledgeRetriever` singleton (from `src/retrievers/hotel_knowledge/chains.py`) on first call. Calls `retriever.document_search(query, num_docs=3)` which executes a Qdrant vector search followed by optional reranking. Retrieved documents are concatenated with double newlines and returned as a single string. On no-results, the fallback string is bilingual: `"ขออภัยค่ะ ไม่พบข้อมูลที่ต้องการ / Sorry, I couldn't find that information."` — consistent with the Thai-first guest persona.

> [!note]
> `_retriever` is a module-level singleton initialized inside `get_retriever()` behind a simple `None` check (not thread-safe). This is safe only because all callers are async on the same event loop thread. A concurrent multi-process deployment (multiple gunicorn workers) would share nothing — each process creates its own retriever instance and Qdrant connection.

#### `search_hotel_knowledge_with_sources`

Extended variant returning a three-element tuple `(content, sources, retrieval_context)`. `sources` is a list of document source strings from result metadata. `retrieval_context` is the raw chunk list, used by DeepEval's `RAGASMetric` for faithfulness and context precision scoring. Not bound to any sub-agent tool node — called directly from evaluation harnesses.

---

### Booking Group

All booking tools delegate to LangChain-wrapped functions in `src/agent/hotel_tools.py` via `tool.invoke({...})`.

| Tool | Signature | Input fields | Returns | Sub-agent |
|---|---|---|---|---|
| `check_room_availability` | `(check_in, check_out, room_type=None)` | dates (YYYY-MM-DD), optional type string | `{"return_value": str}` | `hotel_booking` |
| `create_reservation` | `(guest_id, room_id, check_in, check_out, special_requests=None)` | guest & room IDs, dates, optional notes | `{"return_value": str}` confirmation | `hotel_booking` |
| `confirm_reservation` | `(reservation_id: str)` | reservation ID or confirmation number | `{"return_value": str}` | `hotel_booking` |
| `cancel_reservation` | `(reservation_id, reason=None)` | ID + optional cancellation reason | `{"return_value": str}` | `hotel_booking` |
| `get_reservation_details` | `(reservation_id: str)` | ID or confirmation number | `{"return_value": str}` details | `hotel_booking` |

#### `check_room_availability`

Passes `room_type` as `"any"` when omitted. Internally the hotel_tools layer queries the `rooms` and `reservations` tables with a date-overlap check. Returns a human-readable string suitable for direct inclusion in a chat response.

#### `create_reservation`

Requires pre-obtained `guest_id` and `room_id`. The LangGraph booking sub-agent typically resolves these in prior turns (collecting email → look up or create guest → select room). The function logs `guest_id` and `room_id` at INFO level on success — these log entries are a secondary channel for memory extraction: conversation summarizers downstream can parse tool-call args to build structured guest fact records.

> [!note]
> **Memory cross-reference:** The thesis memory system (see [[concepts/persistent_memory_chatbot]]) proposes extracting structured facts from successful `create_reservation` and `create_service_request` tool-call argument logs. The `logger.info(f"Reservation created: guest={guest_id}, room={room_id}")` line at line 183 is an example of this pattern. A more robust implementation would emit a structured JSON event to a side channel.

#### `cancel_reservation`

Defaults `reason` to `"Guest requested cancellation"` when not supplied. The cancellation reason is stored in the `reservations.cancellation_reason` column (see [[components/database]]).

---

### Safety Group

| Tool | Signature | Returns | Called by |
|---|---|---|---|
| `check_input_safety` | `(user_message: Optional[str]) → dict` | `{"return_value": bool}` | NeMo Guardrails config (planned), direct calls |
| `check_output_safety` | `(bot_message: Optional[str]) → dict` | `{"return_value": bool}` | NeMo Guardrails config (planned), direct calls |

> [!note]
> These are **lightweight regex classifiers**, not neural safety models. They operate on keyword pattern matching only. The more sophisticated safety layer is `hybrid_router.py` which runs upstream before `actions.py` is ever invoked.

#### `check_input_safety`

Checks the lowercased message against 12 blocked patterns covering SQL injection (`"drop table"`, `"delete from"`, `"sql injection"`), script injection (`"exec("`, `"eval("`, `"xss"`, `"script injection"`), and general cyber terms (`"hack"`, `"exploit"`, `"attack"`, `"illegal"`, `"password bypass"`). Returns `True` (safe) for empty input. Returns `False` and logs a WARNING on match.

#### `check_output_safety`

Guards against sensitive data appearing in model output. Checks for 10 patterns: `"credit card"`, `"card number"`, `"cvv"`, `"password:"`, `"api_key"`, `"secret_key"`, `"private key"`, `"access_token"`, `"bearer "`, `"authorization:"`. Returns `False` (block) on match. This is the last-line defense before a response is sent to the guest.

> [!note]
> The NeMo Guardrails `config/` directory referenced in CLAUDE.md **does not exist** in the current codebase. The `check_input_safety` and `check_output_safety` functions were clearly written with NeMo Guardrails action hooks in mind (matching the NeMo `@action` callable signature), but are currently called ad-hoc if used at all. See [[modules/hotel_guardrails]] for the contradiction callout.

---

### Utility Group

| Tool | Signature | Returns | Called by |
|---|---|---|---|
| `detect_language` | `(text: str) → dict` | `{"return_value": "th" or "en"}` | LLM prompt building, sub-agents |
| `format_bilingual_response` | `(thai_text, english_text) → dict` | `{"return_value": "thai / english"}` | Response formatters |

#### `detect_language`

Heuristic character-set detection. Builds a set intersection between the input text and the set of Thai Unicode consonants (`กขฃคฅฆงจ...`). If any Thai character is present, returns `"th"`. Otherwise returns `"en"`. This binary classification is sufficient for the Thai/English bilingual use case but would not handle mixed-script messages or other languages.

#### `format_bilingual_response`

Formats `"thai_text / english_text"` — the same slash-separator convention used throughout the codebase for bilingual fallback messages. Used by sub-agents when they need to produce a bilingual response string from separately-translated components.

---

## Dependency Graph

```
actions.py
  ├── src/retrievers/hotel_knowledge/chains.py  (HotelKnowledgeRetriever)
  └── src/agent/hotel_tools.py  (check_room_availability, create_reservation,
                                  confirm_reservation, cancel_reservation,
                                  get_reservation_details)
```

The booking tools do **not** call `database.py` directly. `database.py` is called by `server.py` REST endpoint handlers and by `hotel_tools.py` internally.

## Related

- [[components/database]] — PostgreSQL ops layer; booking tools indirectly invoke it via hotel_tools.py
- [[components/knowledge_subagent]] — primary consumer of `search_hotel_knowledge`
- [[references/hotel_knowledge_base]] — the document corpus RAG'd over
- [[flows/reservation_lifecycle]] — how create/confirm/cancel chain together
- [[modules/hotel_guardrails]] — parent module
- [[components/hotel_langgraph]] — sub-agents that call these tools
