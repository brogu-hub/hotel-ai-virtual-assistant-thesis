# Plan: PostgresStore + PostgresSaver (short- and long-term memory)

> Approved plan (2026-04-19). Mirrored from `~/.claude/plans/` into the repo so it lives alongside the code and the thesis.

## Context

The Hotel AI Virtual Assistant needs **persistent memory** on two planes:

- **Short-term memory** (within a session) — conversation state checkpointing, so messages, tool results, and sub-agent routing survive worker crashes and allow replay/time-travel.
- **Long-term memory** (across sessions) — durable guest facts, preferences, and context that the 4 sub-agents can recall on a returning guest's next visit (different `session_id`, same `user_id`).

Alongside the code changes this plan also covers:

- A **Chapter 2 (Literature Review)** section the user can copy into the thesis, with citations added to `thesis/REFERENCES.md`.
- **Diagram updates** — new/edited PNGs using the naming convention: `*_edited_mem.png` for edits, `*_mem.png` for brand-new figures.
- **Extended tests** in `scripts/test_4_subagents.py` that specifically exercise cross-turn and cross-session recall.

### What already exists

- `AsyncPostgresSaver` (short-term checkpointing) is **already wired** at `src/hotel_guardrails/hotel_langgraph.py:623-669`, compiled into the graph at line 611, and initialised from the FastAPI lifespan at `src/hotel_guardrails/server.py:193-199`.
- `langgraph-checkpoint-postgres==2.0.0` is already pinned in `src/hotel_guardrails/requirements.txt:25`.
- `thread_id` is threaded as `session_id` at `hotel_langgraph.py:799`.
- `HotelState` (lines 61-69) already carries `session_id`, `user_id`, `language`, `current_intent`, `tool_calls_made` — no schema change needed to add `user_id`-scoped long-term memory.

### What is missing

- `langgraph-store-postgres` (long-term `BaseStore`) is **not installed** and **not wired**.
- Sub-agents `handle_booking` / `handle_service` / `handle_knowledge` / `handle_other_talk` (`hotel_langgraph.py:252-402`) do not read or write any long-term memory.
- No mechanism to surface a returning guest's preferences, allergies, loyalty tier, or prior booking quirks on a new `session_id`.
- Thesis CH2 does not discuss persistent agent memory. Figures 2.2 and 4.2 show LangGraph without the memory plane.

## Recommended approach

### Part A — Code

1. **Short-term (PostgresSaver) — verify, not reimplement**
   - Keep the existing `AsyncPostgresSaver` path; add a one-liner `/healthz` probe that runs `SELECT 1 FROM checkpoints LIMIT 1`.
   - No schema change.

2. **Long-term (PostgresStore) — new**
   - Add `langgraph-store-postgres` (or equivalent versioned import) to `src/hotel_guardrails/requirements.txt`.
   - Add `init_store()` / `close_store()` beside `init_checkpointer()` in `hotel_langgraph.py`, reusing the same `DATABASE_URL` but a **separate** `AsyncConnectionPool`. Env flag: `APP_STORE_NAME` (`postgres` default / `memory` / `off`).
   - Change `build_hotel_graph(checkpointer)` → `build_hotel_graph(checkpointer, store=None)` and pass `store` to `.compile(checkpointer=checkpointer, store=store)`.
   - Update lifespan at `server.py:193-251` to `init_store()` right after `init_checkpointer()` and pass both into `LangGraphAdapter`.

3. **Memory namespace convention**
   - Two-level tuple namespace: `("guest", user_id)` for per-guest memory; `("guest", user_id, "preferences")` for sub-spaces.
   - Keys per guest: `profile`, `preferences`, `recent_bookings_summary`, `service_history_summary`.
   - Write-through helper `update_guest_memory(user_id, key, value)`; read-through helper `load_guest_memory(user_id)`.

4. **Sub-agent wiring**
   - `_inject_memory_preamble(state, store, user_id)` fetches the namespace and prepends a compact "Known about this guest: …" system message to each sub-agent's `ChatPromptTemplate`.
   - Rule-based write-back: inspect the returned `AIMessage` and tool results; if a fact was asserted via a tool call argument (e.g. `create_reservation(room_type=...)`), upsert the relevant key. No LLM summariser in v1.

5. **Anonymous sessions**
   - If `user_id` is absent, fall back to `("anon", session_id)` — store still works but memory is effectively session-scoped.

### Part B — Thesis

**Placement**: new **§2.3.4 Persistent State and Memory in Agentic Systems** inside the existing "Agentic AI and Orchestration" section at `thesis/CH2_Literature_Review.md:42`, immediately after §2.3.3 (Tool Calling).

**Content** (dual-memory pattern, checkpointer vs. store abstractions, hospitality-specific motivation, forward-reference to CH4/CH5) is drafted in the appendix of this plan.

**New references** to append under a new "Agent Memory and State Persistence" heading in `thesis/REFERENCES.md`:

- LangChain AI. (2024). *LangGraph — Persistence: Checkpointers and Stores*.
- LangChain AI. (2024). *LangGraph — Memory: Short-term and Long-term*.
- Park, J. S., et al. (2023). *Generative Agents: Interactive Simulacra of Human Behavior*. UIST '23.
- Packer, C., et al. (2023). *MemGPT: Towards LLMs as Operating Systems*. arXiv:2310.08560.
- Zhong, W., et al. (2024). *MemoryBank: Enhancing Large Language Models with Long-Term Memory*. AAAI '24.
- PostgreSQL Global Development Group. (2024). *PostgreSQL 16 Documentation — Concurrency Control*.

### Part C — Diagrams

Three deliverables authored as Mermaid `.mmd` sources in `thesis/figures/` so they stay text-editable and re-renderable with `mermaid-config.json`:

1. **NEW** — `Fig_2.4_Persistent_Memory_Architecture_mem.{mmd,png}` — conceptual figure for CH2 §2.3.4.
2. **EDITED** — `Fig_4.2_LangGraph_State_Machine_edited_mem.png` — adds checkpointer rail + store box with "load / upsert guest memory" arrows.
3. **EDITED** — `Fig_2.2_LangGraph_Concept_edited_mem.png` — adds a memory annotation layer.

Render: `npx -p @mermaid-js/mermaid-cli mmdc -c thesis/figures/mermaid-config.json -i <src>.mmd -o <dst>.png -w 1600 -H 1000`.

### Part D — Tests (`scripts/test_4_subagents.py`)

The current test file generates a fresh UUID `session_id` for every case and therefore cannot prove memory works. Extend rather than rewrite:

1. Add a new `memory` category to `TEST_CASES` (parallel to `knowledge`/`booking`/`service`/`other_talk`/`edge`). Each case is a **list of turns** plus optional `user_id` / `session_id` overrides.
2. Extend the runner with `run_multi_turn(turns, session_id, user_id)` helper. Keep single-turn path backward-compatible — multi-turn iff case has a `turns` key.
3. Concrete cases:
   - *Short-term, booking*: turn 1 "Book a Deluxe for April 25-27, email user@test.com"; turn 2 "Actually make that 2 guests" → assert April 25, Deluxe, 2 guests.
   - *Short-term, name recall*: turn 1 "Hi, I'm Alice"; turn 2 "What did I just tell you my name was?" → assert "Alice".
   - *Short-term, Thai*: turn 1 "จองห้อง Suite วันที่ 10-12 พฤษภาคม"; turn 2 "เปลี่ยนเป็น Deluxe ได้ไหม" → assert Thai response mentions Deluxe + original dates.
   - *Long-term, preference recall* (shared `user_id`, different `session_id`): session A "Please remember I prefer a high floor, no peanuts"; session B "What do you know about my room preferences?" → assert "high floor" and "peanuts".
   - *Long-term, returning guest*: session A books a reservation; session B "Any upcoming bookings for me?" → assert the HTL code appears.
   - *Namespace isolation*: user A stores a preference; user B asks "what do you know about me?" → A-only preference must **not** leak.
4. New CLI flag `--agent memory` so tests can be run in isolation.

## Decisions locked (confirmed with user)

1. **Thesis placement** — new **§2.3.4** inside the existing "Agentic AI and Orchestration" section. Not a new top-level §2.8.
2. **Write policy** — rule-based extraction only in v1. No LLM summariser. Zero added per-turn latency.
3. **Retention** — indefinite for known users (`("guest", user_id)`); 30-day TTL for anonymous (`("anon", session_id)`). Implementation: nightly `DELETE FROM store WHERE namespace[1] = 'anon' AND updated_at < NOW() - INTERVAL '30 days'`, scheduled via an asyncio task in the FastAPI lifespan (runs once/24h).

## Critical files

| File | Role in change |
|---|---|
| `src/hotel_guardrails/requirements.txt` | Add `langgraph-store-postgres` |
| `src/hotel_guardrails/hotel_langgraph.py` | New `init_store`/`close_store`; new `_inject_memory_preamble`; `build_hotel_graph(checkpointer, store)`; rule-based write-through in each `handle_*` |
| `src/hotel_guardrails/server.py` | Call `init_store()` in lifespan; pass `store` to `LangGraphAdapter`; schedule anon TTL sweeper |
| `src/hotel_guardrails/langgraph_adapter.py` | Accept `store` in `__init__` |
| `scripts/test_4_subagents.py` | Add `memory` category + multi-turn runner |
| `thesis/CH2_Literature_Review.md` | Insert §2.3.4 after line ~61 |
| `thesis/REFERENCES.md` | Append "Agent Memory and State Persistence" section |
| `thesis/figures/Fig_2.4_Persistent_Memory_Architecture_mem.{mmd,png}` | NEW |
| `thesis/figures/Fig_4.2_LangGraph_State_Machine_edited_mem.png` | EDITED |
| `thesis/figures/Fig_2.2_LangGraph_Concept_edited_mem.png` | EDITED |

## Reused existing infrastructure (no duplication)

- `AsyncConnectionPool` pattern already used for the checkpointer pool (`hotel_langgraph.py:650-655`) — copy the shape for the store pool.
- `DATABASE_URL` env var already available; no new secret.
- `HotelState.user_id` already present on every turn — no state schema change.
- FastAPI lifespan already handles startup/shutdown cleanup.
- `scripts/test_4_subagents.py` already has `has_keyword`, `is_thai`, `has_tool_leak`, retry loop, JSON report — all reusable.

## Verification

1. **Unit sanity**: `docker compose -f deploy/compose/docker-compose.dev.yaml up -d` then `GET /healthz` — confirm the new store-setup line appears in the log (`"PostgreSQL store initialized"`).
2. **Schema check**: `psql $DATABASE_URL -c "\dt"` — expect `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` (existing) **plus** `store`, `store_migrations` (new).
3. **Short-term recall**: `python scripts/test_4_subagents.py --agent memory` — the three short-term cases must pass.
4. **Long-term recall**: cross-session cases must pass. Spot-check `SELECT namespace, key FROM store WHERE namespace[1]='guest' LIMIT 20;`.
5. **Regression**: full run `python scripts/test_4_subagents.py` — existing per-agent pass rates must not drop.
6. **Thesis render**: `npx mermaid-cli` produces the three PNGs with correct `_mem` / `_edited_mem` suffixes and CH2 previews cleanly.

---

## APPENDIX — Drop-in Chapter 2 §2.3.4 text

> **2.3.4 Persistent State and Memory in Agentic Systems**
>
> Conversational agents exhibit two categorically different memory needs. **Short-term memory** retains the turn-by-turn content of a single dialogue — the messages, tool calls, and intermediate reasoning — and must survive process restarts if the system is to be production-grade. **Long-term memory** retains facts about a user across sessions — preferences, history, and salient traits — and is the mechanism by which an agent feels personalised on a returning visit rather than starting from zero. This distinction parallels the episodic/semantic split in cognitive memory models and has become standard in the agent-systems literature (Park et al., 2023; Packer et al., 2023; Zhong et al., 2024).
>
> LangGraph exposes these two needs through two separate abstractions. The `BaseCheckpointSaver` interface is invoked after every node transition and persists the full graph state keyed by `thread_id`; its PostgreSQL implementation, `PostgresSaver`, writes to a small family of `checkpoints`, `checkpoint_blobs`, and `checkpoint_writes` tables and allows exact replay as well as "time-travel" debugging (LangChain AI, 2024a). The `BaseStore` interface, in contrast, is thread-agnostic: it exposes a namespaced key-value API (`get`, `put`, `search`) against which any node in any graph execution can read or write, and its `PostgresStore` implementation backs those operations with ACID-compliant PostgreSQL rows (LangChain AI, 2024b). Separating the two is deliberate — their access patterns, consistency requirements, and retention policies differ, and coupling them would compromise both.
>
> For the hospitality domain this separation is directly motivated. Buhalis and Moldavska (2022) identify "context retention across turns" as one of three prerequisites for a usable AI concierge; the checkpointer satisfies this. Buhalis, O'Connor, and Leung (2023) further argue that the value proposition of AI in hospitality is not one-off assistance but *continuous* personalisation across a guest's lifetime relationship with the property; this demands the second, cross-session layer that a long-term store provides. PostgreSQL is a natural substrate for both: its MVCC concurrency model (PostgreSQL Global Development Group, 2024) guarantees that concurrent sub-agent writes to the same guest's memory namespace do not corrupt each other, while its operational maturity is an implicit requirement for a system that will hold personally-identifying guest data.
>
> This thesis implements both layers — `PostgresSaver` for short-term dialogue persistence and `PostgresStore` for long-term guest memory — and wires the long-term layer into each of the four sub-agents so that context recall is uniform across booking, service, knowledge, and general-conversation flows. The concrete implementation is described in Chapter 4 (System Design) and Chapter 5 (Implementation); Figure 2.4 illustrates the conceptual architecture.

### References to append under a new heading "Agent Memory and State Persistence" in `thesis/REFERENCES.md`

```markdown
## Agent Memory and State Persistence

LangChain AI. (2024a). LangGraph — Persistence: Checkpointers and Stores. https://langchain-ai.github.io/langgraph/concepts/persistence/

LangChain AI. (2024b). LangGraph — Memory: Short-term and Long-term. https://langchain-ai.github.io/langgraph/concepts/memory/

Packer, C., Wooders, S., Lin, K., Fang, V., Patil, S. G., Stoica, I., & Gonzalez, J. E. (2023). MemGPT: Towards LLMs as Operating Systems. *arXiv preprint arXiv:2310.08560*. https://arxiv.org/abs/2310.08560

Park, J. S., O'Brien, J. C., Cai, C. J., Morris, M. R., Liang, P., & Bernstein, M. S. (2023). Generative Agents: Interactive Simulacra of Human Behavior. *Proceedings of the 36th Annual ACM Symposium on User Interface Software and Technology (UIST '23)*. https://doi.org/10.1145/3586183.3606763

PostgreSQL Global Development Group. (2024). PostgreSQL 16 Documentation — Chapter 13: Concurrency Control. https://www.postgresql.org/docs/16/mvcc.html

Zhong, W., Guo, L., Gao, Q., Ye, H., & Wang, Y. (2024). MemoryBank: Enhancing Large Language Models with Long-Term Memory. *Proceedings of the AAAI Conference on Artificial Intelligence*, 38(17). https://doi.org/10.1609/aaai.v38i17.29874
```

### Figure caption for `Fig_2.4_Persistent_Memory_Architecture_mem.png`

> **Figure 2.4** Persistent memory architecture in the hotel assistant. The LangGraph agent maintains two distinct memory planes backed by PostgreSQL: a `PostgresSaver` checkpointer that persists per-session dialogue state (keyed by `thread_id = session_id`) and a `PostgresStore` that persists per-guest long-term memory (keyed by `user_id` under the `(guest, user_id)` namespace). Each of the four sub-agents reads from the store on entry and writes through it on exit, while the checkpointer is invoked automatically by the framework after every node transition.
