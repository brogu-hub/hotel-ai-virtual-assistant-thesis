-- Migration: create escalations table for adaptive-escalation
-- precision/recall instrumentation.
--
-- Logs every escalation decision (pre / post / cheap_judge) so we can later
-- compute false-positive / false-negative rates and tune trigger thresholds.
-- Cross-ref: src/hotel_guardrails/escalation.py, CH6 §6.5.17.

CREATE TABLE IF NOT EXISTS escalations (
    id                    BIGSERIAL PRIMARY KEY,
    ts                    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    session_id            TEXT NOT NULL,
    user_id               TEXT,
    turn_index            INTEGER,                     -- 0 = first turn of session, 1 = second, ...
    user_text             TEXT NOT NULL,
    trigger_layer         TEXT NOT NULL
        CHECK (trigger_layer IN ('pre', 'post', 'cheap_judge')),
    trigger_flags         TEXT[] NOT NULL,             -- e.g. ARRAY['multi_turn_no_context','deferral']
    local_response        TEXT,                         -- NULL when trigger_layer = 'pre' (no local pass)
    local_response_ms     INTEGER,
    cloud_response        TEXT NOT NULL,
    cloud_response_ms     INTEGER,
    cloud_cost_usd        NUMERIC(10,6),
    cloud_model           TEXT NOT NULL DEFAULT 'google/gemma-4-31b-it',
    final_response_source TEXT NOT NULL
        CHECK (final_response_source IN ('cloud', 'local')),
    final_response        TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_escalations_session ON escalations(session_id);
CREATE INDEX IF NOT EXISTS idx_escalations_ts      ON escalations(ts DESC);
CREATE INDEX IF NOT EXISTS idx_escalations_flags   ON escalations USING gin(trigger_flags);
CREATE INDEX IF NOT EXISTS idx_escalations_layer   ON escalations(trigger_layer);
