---
type: component
status: active
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/escalation.py
related:
  - concepts/human_in_the_loop
  - flows/admin_monitoring
  - components/audit
  - modules/hotel_guardrails
tags: [component, escalation, human-in-the-loop, sentiment, monitoring]
---

# Component: escalation.py

## Purpose

`escalation.py` implements an automatic escalation monitor for the hotel chatbot. It detects conditions where a conversation should be handed off to a human staff member and surfaces those signals to the admin dashboard. The monitor operates in-process as a stateful class (`EscalationMonitor`) that accumulates per-session message history and applies three independent trigger checks on each incoming guest message.

This is the in-code realization of the [[concepts/human_in_the_loop]] concept as documented in the thesis research.

## Trigger taxonomy

Three escalation triggers are checked in priority order:

| Priority | Trigger | Mechanism | Result |
|---|---|---|---|
| High | Frustrated guest language | Keyword list (EN + TH) | `"high"` priority |
| High | Bot-failing repetition | SequenceMatcher similarity ≥ 0.7, 3+ times | `"high"` priority |
| Medium | High-value booking | Amount ≥ 50,000 THB or Penthouse room | `"medium"` priority |

Once any trigger fires, the remaining checks are short-circuited (sentiment → repetition → high-value).

## Trigger 1: Sentiment / frustration keywords

`check_sentiment(message)` scans the message against two hardcoded keyword lists: English (`FRUSTRATION_EN`, 15 phrases) and Thai (`FRUSTRATION_TH`, 11 phrases).

English phrases include: `"speak to manager"`, `"talk to a real person"`, `"human agent"`, `"terrible service"`, `"worst hotel"`, `"useless bot"`, `"stupid bot"`, etc.

Thai phrases include: `"ขอพูดกับผู้จัดการ"`, `"ต้องการคุยกับคน"`, `"ร้องเรียน"`, `"โกรธ"`, `"บอทไม่เก่ง"`, etc.

English matching is case-insensitive (`.lower()`). Thai matching is case-sensitive (Thai script has no case), direct substring match.

> [!gap] Keyword-only sentiment — no NLP
> There is no NLP-based sentiment scoring. A guest expressing frustration differently from the exact keyword phrases will not trigger escalation. For example, `"this is a nightmare"` or `"completely useless"` would not fire. The list is a starting point but needs expansion or replacement with a lightweight sentiment classifier for production use.

## Trigger 2: Repetition detection

`check_repetition(session_id, message)` maintains a `deque(maxlen=10)` of recent messages per session. It appends the current message, then compares it to all previous messages using `difflib.SequenceMatcher`. If at least `REPETITION_COUNT - 1` (i.e., 2) prior messages have a similarity ratio above `REPETITION_SIMILARITY` (0.7), escalation is triggered.

The interpretation: the guest has asked essentially the same question 3 or more times in the last 10 messages. This is the "bot is failing" signal — the AI is not providing a satisfying answer and the guest is stuck.

> [!note] Per-session state is in-memory
> `_session_messages` is a dict held inside the `EscalationMonitor` instance. Message history is reset when the server process restarts and is not shared across workers. For a single-container demo this is fine; multi-worker deployments would lose escalation history across restarts.

## Trigger 3: High-value booking

`check_high_value(context)` inspects the `context` dict from the LangGraph agent response (if provided). It looks for:

1. The word `"penthouse"` in the response text (case-insensitive)
2. `"total_amount"` or `"penthouse"` in tool-call args
3. Amount strings matching `(\d{1,3}(?:,\d{3})*)\s*(?:THB|บาท)` in the response, parsed and compared against `HIGH_VALUE_THRESHOLD = 50,000` THB

The heuristic is intentionally coarse — it scans the text of the LLM response for currency amounts rather than reading structured booking data.

> [!gap] High-value trigger is heuristic
> The `check_high_value` method relies on pattern-matching the LLM's text output for amounts. This means it can miss high-value bookings if the response is phrased differently, and could false-positive on responses that mention prices in passing. A more reliable implementation would hook into the booking tool's structured return value.

## `should_escalate()` — main API

```python
def should_escalate(
    session_id: str,
    message: str,
    context: Optional[Dict] = None,
) -> Tuple[bool, str, str]:
    # Returns: (should_escalate, reason_string, priority)
    # priority: "high" | "medium" | ""
```

The caller receives a boolean flag, a human-readable reason string for the admin dashboard (e.g., `"Frustrated guest (EN): 'terrible service'"`), and a priority level.

## Escalation channel and state transfer

> [!gap] No escalation dispatch channel in this module
> `escalation.py` only *detects* that escalation is needed — it does not dispatch a notification, queue a work item, send an email, or update session status. The actual state change (`status → admin_controlled`) and the escalation queue are managed by `server.py`'s endpoint handlers. This module is a detection library only, not a full human-in-the-loop orchestrator.

There is no Slack webhook, email integration, or ticket system connected to the escalation trigger. The admin must monitor `GET /admin/escalations` to discover escalated sessions. For a production hotel deployment, push notification to on-duty staff would be needed.

## Configuration constants

| Constant | Value | Purpose |
|---|---|---|
| `HIGH_VALUE_THRESHOLD` | 50,000 THB | Booking value above which staff attention is warranted |
| `HIGH_VALUE_ROOM_TYPES` | `{"penthouse"}` | Room types that always escalate |
| `REPETITION_SIMILARITY` | 0.7 | SequenceMatcher ratio threshold |
| `REPETITION_COUNT` | 3 | Number of similar messages before escalation |
| `MAX_HISTORY` | 10 | Messages kept per session in the deque |

None of these are configurable via environment variables — they are hardcoded module-level constants.

> [!gap] Constants not configurable
> All escalation thresholds are hardcoded. A hotelier who wants to adjust the high-value threshold from 50,000 to 30,000 THB, or tighten the repetition window, must edit source code. Env-var configuration for these constants would make the system more operationally flexible.

## Bilingual design

The dual English/Thai keyword lists represent a conscious internationalization decision. The Grand Horizon Hotel serves both international and domestic Thai guests. The asymmetric matching (case-insensitive for English, case-sensitive for Thai) is correct because Thai has no case distinction.

## Related

- [[concepts/human_in_the_loop]] — the concept this implements
- [[flows/admin_monitoring]] — admin-side view of escalated sessions; `GET /admin/escalations`
- [[components/audit]] — `ESCALATIONS_VIEWED` audit action
- [[modules/hotel_guardrails]] — module overview
