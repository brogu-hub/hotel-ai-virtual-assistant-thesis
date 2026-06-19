# Backtest report — `clean_stackoff` / `20260613T133026`

## Manifest

- **workflow_sha**: `5809c4d`
- **corpus_version**: `qdrant_hotel_knowledge_unknown_20260613T133026`
- **embedding_model**: `qwen/qwen3-embedding-8b`
- **llm_model**: `gemma4:12b-it-q8_0`
- **judge_model**: `deepseek/deepseek-chat-v3.1`
- **dataset_version**: `sha256_1bde0e5b6210`
- **endpoint**: `http://localhost:8088`

## Headline

- **Aggregate**: 210/274 = **76.6%** [95% CI 71.3% – 81.3%]

## Per-stratum pass rate

| Domain | Lang | n | Pass | Partial | Fail | Rate | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| attractions/nearby_attractions | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| attractions/transportation | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| dining/pool_bar | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/pool_bar | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/room_service | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| dining/room_service | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| dining/skyline_restaurant_all_day_dining | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/skyline_restaurant_all_day_dining | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/the_grand_dining_room_breakfast | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/the_grand_dining_room_breakfast | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/embassy_contacts | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/emergency_contacts | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| emergency/fire_safety | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/medical_services | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| emergency/safety_tips | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/business_center | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| facilities/business_center | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| facilities/concierge_services | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/concierge_services | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/fitness_center | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| facilities/fitness_center | th | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| facilities/parking | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/parking | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/swimming_pool | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/swimming_pool | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/wifi | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/wifi | th | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| faq/check_in_check_out | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| faq/check_in_check_out | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/general_information | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/general_information | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| faq/payment_billing | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/payment_billing | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/cancellation_policy | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| policies/cancellation_policy | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| policies/children_policy | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| policies/children_policy | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/damage_policy | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/damage_policy | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/lost_and_found | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| policies/lost_and_found | th | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| policies/pet_policy | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| policies/pet_policy | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| policies/quiet_hours | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/quiet_hours | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| policies/smoking_policy | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| policies/smoking_policy | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| rooms/deluxe_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/deluxe_room | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| rooms/deluxe_room | th | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| rooms/extra_beds_baby_cots | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| rooms/extra_beds_baby_cots | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/housekeeping | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| rooms/housekeeping | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/in_room_amenities | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/in_room_amenities | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/overview | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/overview | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/penthouse_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/penthouse_suite | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/penthouse_suite | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| rooms/room_comparison | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/room_comparison | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/room_types | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| rooms/room_types | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| rooms/special_requests | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/special_requests | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/standard_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/standard_room | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/standard_room | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/suite | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/suite | th | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| rooms/suite_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/facilities | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/facilities | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/massage_treatments | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| spa/massage_treatments | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/operating_hours | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| spa/operating_hours | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| spa/reservations | en | 3 | 1 | 1 | 1 | 33.3% | [6.1%, 79.2%] |
| spa/reservations | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| spa/signature_packages | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/signature_packages | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/airport_transfers | en | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| transportation/airport_transfers | th | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| transportation/booking_tours | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| transportation/car_rental | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| transportation/car_rental | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| transportation/parking | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/public_transportation | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| transportation/tour_packages | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/tour_packages | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |

## Defect breakdown

| Defect | Count | Example IDs |
|---|---:|---|
| `incomplete` | 40 | `dining_room_service_en_2`, `rooms_deluxe_room_en_2`, `rooms_housekeeping_en_2` |
| `hallucination` | 31 | `dining_room_service_en_2`, `rooms_room_types_en_1`, `spa_operating_hours_en_2` |
| `rag_miss` | 16 | `facilities_business_center_en_3`, `faq_check_in_check_out_en_2`, `policies_pet_policy_en_1` |
| `spec_wrong` | 15 | `rooms_room_types_en_1`, `spa_operating_hours_en_2`, `facilities_fitness_center_en_1` |
| `over_refuse` | 13 | `spa_massage_treatments_en_1`, `policies_pet_policy_en_1`, `policies_smoking_en_1` |
| `tool_not_called` | 12 | `pricing_standard_early_bird_en`, `pricing_standard_standard_rate_en`, `pricing_standard_last_minute_en` |
| `empty_response` | 1 | `rooms_suite_th_2` |

## Regression watchlist

| Item | Severity | Metric | Threshold | Status |
|---|---|---:|---|---|
| rag_drift | CRITICAL | 0 | <= 0 | PASS |
| language_leak (EN+TH replies) | CRITICAL | 0 | <= 0 | PASS |
| hallucination on hard negatives | CRITICAL | 0 | <= 0 | PASS |
| booking lifecycle tool_error | CRITICAL | 0 | <= 0 | PASS |
| tool_call_leak rate | HIGH | 0.0 | <= 0.01 | PASS |
| over_refuse rate | HIGH | 0.0474 | <= 0.15 | PASS |
| empty_response rate | HIGH | 0.0036 | <= 0.03 | PASS |

## Promotion gates

| Gate | Metric | Threshold | Status |
|---|---:|---|---|
| Aggregate pass rate | 0.766 | >= 0.75 | PASS |
| Worst per-domain pass rate | 0.0 | >= 0.65 | **FAIL** |
| Canary pass rate | — | >= 1.0 | N/A (skipped — no cases of this type in run) |
| Hard negative pass rate | — | >= 0.8 | N/A (skipped — no cases of this type in run) |
| Per-row language match rate | 1.0 | >= 0.98 | PASS |

## Verdict: **DO NOT SHIP**
