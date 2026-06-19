# Backtest report — `clean_stackon` / `20260614T133053`

## Manifest

- **workflow_sha**: `354faf4`
- **corpus_version**: `qdrant_hotel_knowledge_unknown_20260614T133053`
- **embedding_model**: `qwen/qwen3-embedding-8b`
- **llm_model**: `gemma4:12b-it-q8_0`
- **judge_model**: `deepseek/deepseek-chat-v3.1`
- **dataset_version**: `sha256_1bde0e5b6210`
- **endpoint**: `http://localhost:8088`

## Headline

- **Aggregate**: 76/90 = **84.4%** [95% CI 75.6% – 90.5%]

## Per-stratum pass rate

| Domain | Lang | n | Pass | Partial | Fail | Rate | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| dining/pool_bar | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/room_service | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| dining/skyline_restaurant_all_day_dining | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/the_grand_dining_room_breakfast | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/business_center | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/concierge_services | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/fitness_center | en | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| facilities/parking | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/swimming_pool | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/wifi | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/check_in_check_out | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| faq/general_information | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/payment_billing | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/cancellation_policy | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| rooms/deluxe_room | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| rooms/extra_beds_baby_cots | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| rooms/housekeeping | en | 3 | 1 | 1 | 1 | 33.3% | [6.1%, 79.2%] |
| rooms/in_room_amenities | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/overview | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/penthouse_suite | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/room_comparison | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/room_types | en | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| rooms/special_requests | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/standard_room | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/suite | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/facilities | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| spa/massage_treatments | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/operating_hours | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| spa/reservations | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| spa/signature_packages | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |

## Defect breakdown

| Defect | Count | Example IDs |
|---|---:|---|
| `incomplete` | 11 | `dining_room_service_en_2`, `rooms_deluxe_room_en_2`, `rooms_housekeeping_en_2` |
| `rag_miss` | 6 | `dining_room_service_en_2`, `rooms_housekeeping_en_2`, `spa_facilities_en_3` |
| `hallucination` | 5 | `rooms_room_types_en_1`, `rooms_room_types_en_3`, `spa_operating_hours_en_2` |
| `spec_wrong` | 2 | `rooms_room_types_en_1`, `spa_operating_hours_en_2` |

## Regression watchlist

| Item | Severity | Metric | Threshold | Status |
|---|---|---:|---|---|
| rag_drift | CRITICAL | 0 | <= 0 | PASS |
| language_leak (EN+TH replies) | CRITICAL | 0 | <= 0 | PASS |
| hallucination on hard negatives | CRITICAL | 0 | <= 0 | PASS |
| booking lifecycle tool_error | CRITICAL | 0 | <= 0 | PASS |
| tool_call_leak rate | HIGH | 0.0 | <= 0.01 | PASS |
| over_refuse rate | HIGH | 0.0 | <= 0.15 | PASS |
| empty_response rate | HIGH | 0.0 | <= 0.03 | PASS |

## Promotion gates

| Gate | Metric | Threshold | Status |
|---|---:|---|---|
| Aggregate pass rate | 0.844 | >= 0.75 | PASS |
| Worst per-domain pass rate | 0.333 | >= 0.65 | **FAIL** |
| Canary pass rate | — | >= 1.0 | N/A (skipped — no cases of this type in run) |
| Hard negative pass rate | — | >= 0.8 | N/A (skipped — no cases of this type in run) |
| Per-row language match rate | 1.0 | >= 0.98 | PASS |

## Verdict: **DO NOT SHIP**
