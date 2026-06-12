# Gemma 4 12B Q8_0 Smoke Gate — 2026-06-12

## Decision: **PROMOTE** `gemma4:12b-it-q8_0` to production model

Replaces previous default `fredrezones55/qwen3.5-opus:9b`. Runtime hot-swap via
`PUT /settings/llm` remains the operator escape hatch.

## Models considered

| Tag | Size | Fits 5080 + reranker? | Notes |
|---|---:|---|---|
| `gemma4:12b-it-q8_0` | 12 GB | ✓ (peak 15.8 GiB / 16.3) | **Selected** |
| `gemma4:12b-it-qat` | 7.2 GB | ✓ (comfortable) | Fallback if Q8 OOMs in prod |
| `gemma4:12b` (Q4_K_M) | 7.6 GB | ✓ | Prior baseline |
| `gemma4:26b-a4b-it-qat` | 16 GB | ✗ (won't fit w/ reranker) | Eliminated |

## VRAM under load (Q8_0, NUM_PARALLEL set to 1 for safety)

| Probe | Latency | VRAM (MiB) |
|---|---:|---:|
| Idle pre-load | — | 4,439 |
| EN single (breakfast) | 72.9 s | 15,812 |
| TH multi-intent (WiFi + breakfast) | 33.8 s | 15,834 |
| CN multi-intent (WiFi + breakfast) | 54.3 s | 15,812 |
| Long-context booking (4 guests, 3 nights, multi-Q) | 74.7 s | 15,824 |
| Concurrent x2 (EN WiFi + CN pool) | 47–60 s | 15,840 (peak) |

Peak VRAM = **15,840 MiB** of 16,303 MiB → **463 MiB headroom**.
No CPU offload observed. KV cache holds in VRAM.

## Canary smoke (15-case stability gate)

| # | ID | Verdict |
|---:|---|---|
| 1 | canary_breakfast_start_en | ✓ |
| 2 | canary_breakfast_end_en | ✓ |
| 3 | canary_gym_location_en | ✓ |
| 4 | canary_wifi_password_en | ✓ |
| 5 | canary_hotel_address_en | ✓ |
| 6 | canary_breakfast_hours_th | ✓ |
| 7 | canary_pool_close_th | ✓ |
| 8 | canary_checkin_th | ✓ |
| 9 | canary_checkout_th | ✓ |
| 10 | canary_wifi_password_th | ✓ |
| 11 | canary_breakfast_start_cn | ✓ |
| 12 | canary_pool_close_cn | ✓ |
| 13 | canary_wifi_password_cn | ✓ |
| 14 | canary_greeting_en | ✓ |
| 15 | canary_healthz | ✗ (script-only; `__INFRA_HEALTHZ__` placeholder hit `/chat` rather than `/healthz`) |

**Real-model passes: 14/14 = 100%.** Item 15 is a runner protocol mismatch.

## Known quality regressions to watch on the full backtest

1. **Long-context booking** — Gemma asked for dates/room type again despite both being given in the prompt. May be a routing/prompt issue rather than a model issue. Track via `tool_not_called` bucket.
2. **Q8 latency** is ~1.5–2× the 9B Q5_K_M. Acceptable for thesis; production should consider QAT.

## Artifacts

- `canary_2026-06-12_q8.jsonl` — full per-canary record (question, response, latency, expect_any, pass)
- Persisted config: `.env` (`OLLAMA_MODEL=gemma4:12b-it-q8_0`, `OLLAMA_NUM_PARALLEL=1`, `MAX_CONCURRENT_LLM_CALLS=1`)
- Persisted config: `deploy/compose/docker-compose.hotel.yaml` (`OLLAMA_MODEL: gemma4:12b-it-q8_0`)
