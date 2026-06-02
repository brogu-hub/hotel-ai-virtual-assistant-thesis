---
type: concept
status: implemented
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/hotel_langgraph.py
  - src/hotel_guardrails/server.py
tags: [concept, memory, privacy, gdpr, retention, ttl]
---

# Anonymous Namespace TTL

> [!key-insight]
> Long-term guest memory is stored indefinitely under `("guest", user_id)`. For visitors who never authenticate, memory is instead keyed by `("anon", session_id)` and automatically purged after 30 days — a privacy-motivated retention cap enforced by a nightly sweeper.

## Motivation

The [[dual_plane_memory]] model stores guest facts (preferences, allergies, booking summaries, service history) so returning guests feel recognised. That is obviously correct for **authenticated** guests who have explicitly logged in with a stable `user_id`.

Anonymous visitors are a different case:

- Their identifier is only a browser-generated `session_id`.
- They have not consented to cross-session storage.
- Keeping their data indefinitely would be a privacy hazard and — for EU guests of The Grand Horizon Hotel — would conflict with GDPR's data minimisation principle.

The thesis's compliance framing ([[eu_ai_act_2026]], [[pii_redaction_and_compliance]]) requires that anonymous data have a bounded lifetime.

## Namespace Rule

The `_memory_namespace(state)` helper in `hotel_langgraph.py` selects:

```python
if user_id and user_id != "guest":
    return ("guest", user_id)          # indefinite retention
else:
    return ("anon", session_id)        # 30-day TTL
```

The literal string `"guest"` is treated as "no identity", because the `ChatRequest` default is `user_id="guest"` when the client omits the field.

## The Sweeper: `prune_anon_memory()`

Located at `src/hotel_guardrails/hotel_langgraph.py:1096`. A parameterised `DELETE` against the `store` table:

```sql
DELETE FROM store
WHERE prefix LIKE 'anon.%'
  AND updated_at < NOW() - ($1 * INTERVAL '1 day');
```

Key design choices:

- **Parameterised `INTERVAL`.** The day count is passed as a parameter (`%s * INTERVAL '1 day'`), not string-formatted into the SQL. Avoids injection even though the value originates in-process.
- **`prefix LIKE 'anon.%'`.** The `langgraph.store.postgres` schema serialises namespace tuples as dot-joined strings in the `prefix` column. Matching `anon.%` selects all two-level anon namespaces regardless of `session_id`.
- **Graceful degradation.** If `_store is None` or `_store_pool is None` (store is InMemoryStore or disabled) the function is a silent no-op returning 0.
- **Integer coercion.** `max_age_days` is coerced with `int()`; non-numeric input returns 0 without touching the database.

## Scheduling: FastAPI Lifespan

`server.py`'s lifespan context launches a background task that awaits `prune_anon_memory(max_age_days=30)` every 24 hours. The task is cancelled cleanly on shutdown. No external cron dependency — the sweeper lives inside the application process.

Trade-off: if the process is restarted hourly (e.g. during a deploy storm), the sweeper may run more frequently than once every 24h. Acceptable — the `DELETE` is idempotent and cheap.

## What Stays, What Goes

| Namespace | Retention | Example |
|---|---|---|
| `("guest", "alice-123")` | Indefinite | Alice's allergy preference lasts years |
| `("anon", "sess-a1b2")` | 30 days | An anonymous visitor's preference expires |

Short-term checkpoints in `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` are **not** touched by this sweeper. A separate checkpoint-retention policy would be needed if session state accumulation becomes an operational concern.

## Thesis Framing

For the compliance chapter, the TTL can be positioned as:

- A **technical implementation** of GDPR Art. 5(1)(e) "storage limitation".
- A **policy boundary** that differentiates identified from anonymous visitors.
- A **design pattern** transferable to other tenant-scoped LLM apps: anonymous users get bounded-lifetime memory, identified users get indefinite memory, and the distinction is carried structurally in the namespace tuple rather than as an ad-hoc flag.

## Observability

`prune_anon_memory()` logs at `INFO` when rows are deleted and at `WARNING` on failure — both with the deleted count. In production, Railway log aggregation captures these, and the count is a useful signal for dashboarding (a sudden spike may indicate session-ID churn or bot traffic).

## Related

- [[components/hotel_langgraph]] — hosts `prune_anon_memory()` and `_memory_namespace()`
- [[components/anon_memory_sweeper]] — component-level documentation
- [[components/server]] — lifespan scheduling
- [[concepts/dual_plane_memory]] — the two-plane memory model
- [[concepts/pii_redaction_and_compliance]] — adjacent privacy controls
- [[papers/eu_ai_act_2026]] — regulatory motivation
- [[entities/PostgreSQL]] — backing store
