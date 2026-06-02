---
type: component
path:
  - "src/hotel_guardrails/hotel_langgraph.py"
  - "src/hotel_guardrails/server.py"
status: active
parent_module: hotel_guardrails
tags: [component, memory, ttl, gdpr, scheduler, novel-contribution]
date_ingested: 2026-04-20
---

# anon_memory_sweeper — 30-Day TTL Scheduler

> [!note]
> Function-level view. For the concept-level write-up (GDPR framing, namespace rule, thesis positioning) see [[concepts/anon_namespace_ttl]].

## Scope

Two pieces collaborate:

- `prune_anon_memory(max_age_days=30)` at `src/hotel_guardrails/hotel_langgraph.py:1096` — the DELETE query itself
- The background task scheduled by `server.py`'s `lifespan` context — the 24h invocation cadence

## The DELETE

```sql
DELETE FROM store
WHERE prefix LIKE 'anon.%'
  AND updated_at < NOW() - ($1 * INTERVAL '1 day');
```

Key points:

- **Parameterised INTERVAL** — the day count multiplies `INTERVAL '1 day'` via parameter binding, not string formatting. Injection-safe even though the value originates in-process.
- **Prefix match** — `langgraph.store.postgres` serialises namespace tuples as dot-joined strings in the `prefix` column; `anon.%` matches any two-level anon namespace regardless of `session_id`.
- **No pagination** — a single statement; a cold start after long downtime may DELETE many rows at once but is idempotent.
- **Row count returned** — `cur.rowcount` captured for logging.

## Guard rails

The function short-circuits and returns 0 if:

- `_store is None` or `_store_pool is None` (store disabled or running as `InMemoryStore`)
- `max_age_days` cannot be coerced to `int` or is < 1 — defensive against misconfigured env

Exceptions are caught, logged at WARNING, and the function returns 0 rather than failing the enclosing task.

## Scheduler

In `server.py`'s `lifespan`:

```python
async def _anon_sweeper_task():
    while True:
        await asyncio.sleep(24 * 3600)
        await prune_anon_memory(max_age_days=30)

sweeper = asyncio.create_task(_anon_sweeper_task())
try:
    yield
finally:
    sweeper.cancel()
    await close_store()
    await close_checkpointer()
```

- Runs inside the same event loop as the FastAPI app — no external cron, no worker process.
- Cancelled cleanly on shutdown.
- Restarts re-initialise the timer from scratch; a frequent-deploy environment may run the sweeper many times in a day, which is acceptable since the DELETE is idempotent.

## Observability

- INFO log when rows are deleted: `prune_anon_memory: removed N anon store entries older than 30d`
- WARNING log on failure with exception class and message
- Row count can be scraped from logs for dashboarding; a sustained zero suggests no anon traffic, while spikes can indicate bot activity or session-ID churn

## Authenticated guests are untouched

The sweeper only targets `anon.%` prefixes. Guests identified by a stable `user_id` store their memory under `guest.%` and are **never** swept — retention is indefinite.

## Configurable lifetime

`max_age_days` can be changed by passing a different value at task creation. The thesis default of 30 days is a compliance-and-UX compromise (long enough that a guest who returns within the month is recognised; short enough that stale anon sessions don't accumulate).

## Related

- [[concepts/anon_namespace_ttl]] — concept page (GDPR, thesis framing, transferability)
- [[concepts/dual_plane_memory]] — where anon namespaces fit
- [[components/guest_memory_store]] — the sibling lifecycle controller
- [[components/server]] — hosts the scheduler task
- [[components/hotel_langgraph]] — hosts `prune_anon_memory()`
- [[papers/eu_ai_act_2026]] — regulatory backdrop
- [[entities/PostgreSQL]]
