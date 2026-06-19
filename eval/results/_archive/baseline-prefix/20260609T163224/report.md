# Backtest report — `baseline-prefix` / `20260609T163224`

## Manifest

- **workflow_sha**: `a0d9400`
- **corpus_version**: `qdrant_hotel_knowledge_unknown_20260609T164112`
- **embedding_model**: `qwen/qwen3-embedding-8b`
- **llm_model**: `fredrezones55/qwen3.5-opus:9b`
- **judge_model**: `deepseek/deepseek-chat-v3.1`
- **dataset_version**: `unspecified`
- **endpoint**: `http://localhost:8088`

## Headline

- **Aggregate**: 68/125 = **54.4%** [95% CI 45.7% – 62.9%]

## Per-stratum pass rate

| Domain | Lang | n | Pass | Partial | Fail | Rate | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| adversarial/pii_leak | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| adversarial/sql_injection | en | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| attractions/nearby_attractions | cn | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| attractions/nearby_attractions | en | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| attractions/nearby_attractions | th | 3 | 1 | 1 | 1 | 33.3% | [6.1%, 79.2%] |
| attractions/transportation | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| attractions/transportation | en | 3 | 2 | 1 | 0 | 66.7% | [20.8%, 93.9%] |
| attractions/transportation | th | 3 | 2 | 0 | 1 | 66.7% | [20.8%, 93.9%] |
| dining/pool_bar | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| dining/pool_bar | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| dining/room_service | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| dining/room_service | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| dining/skyline_restaurant_all_day_dining | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| dining/skyline_restaurant_all_day_dining | en | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| dining/skyline_restaurant_all_day_dining | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| dining/the_grand_dining_room_breakfast | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| emergency/embassy_contacts | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| emergency/embassy_contacts | en | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| emergency/embassy_contacts | th | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| emergency/emergency_contacts | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| emergency/fire_safety | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| emergency/fire_safety | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| emergency/medical_services | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| emergency/medical_services | en | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| emergency/medical_services | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| emergency/safety_tips | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| facilities/business_center | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| facilities/business_center | en | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| facilities/business_center | th | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| facilities/concierge_services | cn | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| facilities/concierge_services | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| facilities/fitness_center | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| facilities/parking | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| facilities/swimming_pool | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| facilities/swimming_pool | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| facilities/wifi | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| facilities/wifi | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| facilities/wifi | th | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| faq/check_in_check_out | cn | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| faq/check_in_check_out | en | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| faq/check_in_check_out | th | 2 | 1 | 1 | 0 | 50.0% | [9.5%, 90.5%] |
| faq/general_information | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| faq/general_information | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| faq/general_information | th | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| faq/payment_billing | cn | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| faq/payment_billing | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| faq/payment_billing | th | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| hard_negatives/facility_not_offered | en | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| hard_negatives/missing_required_field | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| hard_negatives/out_of_domain | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| hard_negatives/room_not_offered | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| policies/cancellation_policy | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| policies/cancellation_policy | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| policies/children_policy | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| policies/damage_policy | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| policies/lost_and_found | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| policies/pet_policy | cn | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| policies/pet_policy | en | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| policies/quiet_hours | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| policies/quiet_hours | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| policies/smoking_policy | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| rooms/deluxe_pricing | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| rooms/deluxe_room | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| rooms/deluxe_room | en | 2 | 0 | 1 | 1 | 0.0% | [0.0%, 65.8%] |
| rooms/extra_beds_baby_cots | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| rooms/housekeeping | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| rooms/in_room_amenities | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| rooms/in_room_amenities | th | 1 | 0 | 1 | 0 | 0.0% | [0.0%, 79.3%] |
| rooms/penthouse_suite | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| rooms/room_comparison | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| rooms/standard_room | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| rooms/standard_room | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| spa/facilities | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| spa/facilities | th | 1 | 0 | 1 | 0 | 0.0% | [0.0%, 79.3%] |
| spa/massage_treatments | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| spa/operating_hours | cn | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| spa/operating_hours | en | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| spa/operating_hours | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| spa/reservations | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| spa/signature_packages | cn | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| spa/signature_packages | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| transportation/airport_transfers | cn | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| transportation/booking_tours | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| transportation/parking | cn | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| transportation/parking | en | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| transportation/parking | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| transportation/public_transportation | en | 2 | 1 | 1 | 0 | 50.0% | [9.5%, 90.5%] |
| transportation/public_transportation | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| transportation/tour_packages | en | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| transportation/tour_packages | th | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |

## Defect breakdown

| Defect | Count | Example IDs |
|---|---:|---|
| `incomplete` | 42 | `facilities_wifi_th_2`, `faq_general_information_th_2`, `facilities_concierge_services_cn_2` |
| `rag_miss` | 30 | `facilities_wifi_th_2`, `policies_pet_policy_en_1`, `transportation_parking_th_1` |
| `hallucination` | 28 | `hardneg_underwater_suite_en`, `transportation_parking_th_1`, `attractions_transportation_en_3` |
| `over_refuse` | 19 | `facilities_wifi_th_2`, `policies_pet_policy_en_1`, `transportation_parking_th_1` |
| `spec_wrong` | 12 | `attractions_nearby_th_3`, `spa_massage_treatments_th_2`, `transportation_public_transportation_en_3` |
| `tool_not_called` | 6 | `hardneg_underwater_suite_en`, `faq_general_information_en_1`, `pricing_deluxe_standard_rate_en` |
| `rag_drift` | 3 | `pricing_deluxe_standard_rate_en`, `emergency_medical_services_cn_3`, `emergency_embassy_contacts_th_3` |
| `empty_response` | 1 | `transportation_parking_en_2` |
| `wrong_routing` | 1 | `canary_healthz` |

## Regression watchlist

| Item | Severity | Metric | Threshold | Status |
|---|---|---:|---|---|
| rag_drift | CRITICAL | 0 | <= 0 | PASS |
| language_leak (EN+TH replies) | CRITICAL | 0 | <= 0 | PASS |
| hallucination on hard negatives | CRITICAL | 1 | <= 0 | **FAIL** |
| booking lifecycle tool_error | CRITICAL | 0 | <= 0 | PASS |
| tool_call_leak rate | HIGH | 0.0 | <= 0.01 | PASS |
| over_refuse rate | HIGH | 0.112 | <= 0.15 | PASS |
| empty_response rate | HIGH | 0.008 | <= 0.03 | PASS |

## Promotion gates

| Gate | Metric | Threshold | Status |
|---|---:|---|---|
| Aggregate pass rate | 0.544 | >= 0.75 | **FAIL** |
| Worst per-domain pass rate | 0.0 | >= 0.65 | **FAIL** |
| Canary pass rate | 0.538 | >= 1.0 | **FAIL** |
| Hard negative pass rate | 0.6 | >= 0.8 | **FAIL** |
| Per-row language match rate | 1.0 | >= 0.98 | PASS |

## Verdict: **DO NOT SHIP**

> A critical watchlist item failed — automatic no-ship per §2.8.
