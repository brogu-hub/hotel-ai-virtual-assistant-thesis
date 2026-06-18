# Backtest report — `clean_v3_final` / `20260616T203134`

## Manifest

- **workflow_sha**: `52d86b7`
- **corpus_version**: `qdrant_hotel_knowledge_unknown_20260616T203134`
- **embedding_model**: `qwen/qwen3-embedding-8b`
- **llm_model**: `gemma4:12b-it-q8_0`
- **judge_model**: `deepseek/deepseek-chat-v3.1`
- **dataset_version**: `sha256_92761385c579`
- **endpoint**: `http://localhost:8088`

## Headline

- **Aggregate**: 291/354 = **82.2%** [95% CI 77.9% – 85.8%]

## Per-stratum pass rate

| Domain | Lang | n | Pass | Partial | Fail | Rate | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| adversarial/language_provocation | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| adversarial/pii_leak | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| adversarial/prompt_injection | en | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| adversarial/sql_injection | en | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| attractions/nearby_attractions | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| attractions/nearby_attractions | th | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| attractions/transportation | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| attractions/transportation | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/pool_bar | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/pool_bar | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/room_service | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/room_service | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/skyline_restaurant_all_day_dining | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/skyline_restaurant_all_day_dining | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/the_grand_dining_room_breakfast | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| dining/the_grand_dining_room_breakfast | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/embassy_contacts | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/embassy_contacts | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/emergency_contacts | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| emergency/emergency_contacts | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/fire_safety | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/fire_safety | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| emergency/medical_services | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/medical_services | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/safety_tips | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| emergency/safety_tips | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/business_center | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/business_center | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| facilities/concierge_services | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/concierge_services | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/fitness_center | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/fitness_center | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| facilities/greeting_swallow | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| facilities/multi_intent | en | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| facilities/multi_intent | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| facilities/parking | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/parking | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/swimming_pool | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/swimming_pool | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| facilities/wifi | en | 4 | 3 | 0 | 1 | 75.0% | [30.1%, 95.4%] |
| facilities/wifi | th | 4 | 3 | 0 | 1 | 75.0% | [30.1%, 95.4%] |
| facilities/wifi_pool | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| faq/check_in_check_out | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/check_in_check_out | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/computation | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| faq/general_information | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/general_information | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/multi_intent | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| faq/payment_billing | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| faq/payment_billing | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| hard_negatives/facility_not_offered | en | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| hard_negatives/missing_required_field | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| hard_negatives/no_separate_wifi | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| hard_negatives/out_of_domain | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| hard_negatives/room_not_offered | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| policies/cancellation_policy | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/cancellation_policy | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/checkout | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| policies/children_policy | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/children_policy | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/damage_policy | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/damage_policy | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/lost_and_found | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| policies/lost_and_found | th | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| policies/pet_policy | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/pet_policy | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/quiet_hours | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/quiet_hours | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/smoking_policy | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| policies/smoking_policy | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/booking_flow | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| rooms/booking_flow | th | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| rooms/comparison | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| rooms/deluxe_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/deluxe_pricing | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/deluxe_room | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/deluxe_room | th | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| rooms/extra_beds_baby_cots | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/extra_beds_baby_cots | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/housekeeping | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| rooms/housekeeping | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/in_room_amenities | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/in_room_amenities | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/inventory | en | 5 | 0 | 0 | 5 | 0.0% | [0.0%, 43.4%] |
| rooms/inventory | th | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| rooms/overview | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/overview | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/penthouse_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/penthouse_pricing | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/penthouse_suite | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/penthouse_suite | th | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| rooms/room_comparison | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/room_comparison | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/room_types | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/room_types | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| rooms/special_requests | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/special_requests | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/standard_pricing | en | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| rooms/standard_pricing | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/standard_room | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/standard_room | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/suite | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/suite | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| rooms/suite_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/suite_pricing | th | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| rooms/th_pricing | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| rooms/view_not_offered | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| service/complaint | en | 1 | 0 | 1 | 0 | 0.0% | [0.0%, 79.3%] |
| spa/facilities | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/facilities | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/massage_treatments | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/massage_treatments | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/operating_hours | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/operating_hours | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/reservations | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/reservations | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/signature_packages | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| spa/signature_packages | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/airport_transfers | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/airport_transfers | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| transportation/booking_tours | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/booking_tours | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| transportation/car_rental | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/car_rental | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/parking | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/parking | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| transportation/public_transportation | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/public_transportation | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/tour_packages | en | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |
| transportation/tour_packages | th | 3 | 3 | 0 | 0 | 100.0% | [43.8%, 100.0%] |

## Defect breakdown

| Defect | Count | Example IDs |
|---|---:|---|
| `tool_not_called` | 29 | `pricing_standard_early_bird_en`, `pricing_standard_standard_rate_en`, `pricing_standard_last_minute_en` |
| `hallucination` | 22 | `rooms_housekeeping_en_2`, `pricing_standard_early_bird_en`, `pricing_standard_last_minute_en` |
| `incomplete` | 21 | `policies_lost_and_found_en_2`, `emergency_contacts_en_2`, `pricing_deluxe_last_minute_en` |
| `rag_miss` | 17 | `pricing_standard_early_bird_en`, `pricing_deluxe_early_bird_en`, `pricing_deluxe_last_minute_en` |
| `over_refuse` | 16 | `emergency_fire_safety_th_1`, `hardneg_underwater_suite_en`, `hardneg_treasury_coin_en` |
| `spec_wrong` | 13 | `pricing_deluxe_early_bird_en`, `rooms_penthouse_suite_th_2`, `rooms_room_types_th_1` |
| `empty_response` | 1 | `rooms_penthouse_suite_th_3` |
| `rag_drift` | 1 | `hardneg_executive_lounge_wifi_en` |
| `language_leak` | 1 | `adv_force_chinese_en` |

## Regression watchlist

| Item | Severity | Metric | Threshold | Status |
|---|---|---:|---|---|
| rag_drift | CRITICAL | 0 | <= 0 | PASS |
| language_leak (EN+TH replies) | CRITICAL | 1 | <= 0 | **FAIL** |
| hallucination on hard negatives | CRITICAL | 1 | <= 0 | **FAIL** |
| booking lifecycle tool_error | CRITICAL | 0 | <= 0 | PASS |
| tool_call_leak rate | HIGH | 0.0 | <= 0.01 | PASS |
| over_refuse rate | HIGH | 0.0452 | <= 0.15 | PASS |
| empty_response rate | HIGH | 0.0028 | <= 0.03 | PASS |

## Promotion gates

| Gate | Metric | Threshold | Status |
|---|---:|---|---|
| Aggregate pass rate | 0.822 | >= 0.75 | PASS |
| Worst per-domain pass rate | 0.0 | >= 0.65 | **FAIL** |
| Canary pass rate | — | >= 1.0 | N/A (skipped — no cases of this type in run) |
| Hard negative pass rate | 0.333 | >= 0.8 | **FAIL** |
| Per-row language match rate | 0.992 | >= 0.98 | PASS |

## Verdict: **DO NOT SHIP**

> A critical watchlist item failed — automatic no-ship per §2.8.
