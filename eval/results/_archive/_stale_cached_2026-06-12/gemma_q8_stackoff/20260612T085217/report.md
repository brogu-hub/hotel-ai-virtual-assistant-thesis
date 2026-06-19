# Backtest report — `gemma_q8_stackoff` / `20260612T085217`

## Manifest

- **workflow_sha**: `03a261f`
- **corpus_version**: `qdrant_hotel_knowledge_unknown_20260612T085217`
- **embedding_model**: `qwen/qwen3-embedding-8b`
- **llm_model**: `gemma4:12b-it-q8_0`
- **judge_model**: `deepseek/deepseek-chat-v3.1`
- **dataset_version**: `sha256_45aa45479a56`
- **endpoint**: `http://localhost:8088`

## Headline

- **Aggregate**: 13/499 = **2.6%** [95% CI 1.5% – 4.4%]

## Per-stratum pass rate

| Domain | Lang | n | Pass | Partial | Fail | Rate | 95% CI |
|---|---|---:|---:|---:|---:|---:|---|
| adversarial/language_provocation | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| adversarial/pii_leak | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| adversarial/prompt_injection | en | 2 | 1 | 0 | 1 | 50.0% | [9.5%, 90.5%] |
| adversarial/sql_injection | en | 2 | 2 | 0 | 0 | 100.0% | [34.2%, 100.0%] |
| attractions/nearby_attractions | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| attractions/nearby_attractions | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| attractions/nearby_attractions | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| attractions/transportation | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| attractions/transportation | en | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| attractions/transportation | th | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| dining/pool_bar | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/pool_bar | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/pool_bar | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/room_service | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/room_service | en | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| dining/room_service | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/skyline_restaurant_all_day_dining | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/skyline_restaurant_all_day_dining | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/skyline_restaurant_all_day_dining | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/the_grand_dining_room_breakfast | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/the_grand_dining_room_breakfast | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| dining/the_grand_dining_room_breakfast | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/embassy_contacts | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/embassy_contacts | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/embassy_contacts | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/embassy_not_in_kb | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| emergency/emergency_contacts | cn | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| emergency/emergency_contacts | en | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| emergency/emergency_contacts | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/fire_safety | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/fire_safety | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/fire_safety | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/medical_services | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/medical_services | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/medical_services | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/safety_tips | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/safety_tips | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| emergency/safety_tips | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/business_center | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/business_center | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/business_center | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/concierge_services | cn | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| facilities/concierge_services | en | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| facilities/concierge_services | th | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| facilities/fitness_center | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/fitness_center | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/fitness_center | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/greeting_swallow | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| facilities/multi_intent | cn | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| facilities/multi_intent | en | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| facilities/multi_intent | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| facilities/parking | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/parking | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/parking | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/swimming_pool | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/swimming_pool | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/swimming_pool | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/wifi | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/wifi | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| facilities/wifi | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| faq/check_in_check_out | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| faq/check_in_check_out | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| faq/check_in_check_out | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| faq/computation | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| faq/general_information | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| faq/general_information | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| faq/general_information | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| faq/multi_intent | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| faq/payment_billing | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| faq/payment_billing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| faq/payment_billing | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| hard_negatives/facility_not_offered | en | 2 | 0 | 0 | 2 | 0.0% | [0.0%, 65.8%] |
| hard_negatives/missing_required_field | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| hard_negatives/no_separate_wifi | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| hard_negatives/out_of_domain | en | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| hard_negatives/room_not_offered | en | 1 | 1 | 0 | 0 | 100.0% | [20.7%, 100.0%] |
| policies/cancellation_policy | cn | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| policies/cancellation_policy | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/cancellation_policy | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/children_policy | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/children_policy | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/children_policy | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/damage_policy | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/damage_policy | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/damage_policy | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/lost_and_found | cn | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| policies/lost_and_found | en | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| policies/lost_and_found | th | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| policies/pet_policy | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/pet_policy | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/pet_policy | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/quiet_hours | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/quiet_hours | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/quiet_hours | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/smoking_policy | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/smoking_policy | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| policies/smoking_policy | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/deluxe_pricing | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/deluxe_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/deluxe_pricing | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/deluxe_room | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/deluxe_room | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/deluxe_room | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/extra_beds_baby_cots | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/extra_beds_baby_cots | en | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| rooms/extra_beds_baby_cots | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/housekeeping | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/housekeeping | en | 3 | 1 | 0 | 2 | 33.3% | [6.1%, 79.2%] |
| rooms/housekeeping | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/in_room_amenities | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/in_room_amenities | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/in_room_amenities | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/overview | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/overview | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/overview | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/penthouse_pricing | cn | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| rooms/penthouse_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/penthouse_pricing | th | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| rooms/penthouse_suite | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/penthouse_suite | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/penthouse_suite | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/room_comparison | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/room_comparison | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/room_comparison | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/room_types | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/room_types | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/room_types | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/special_requests | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/special_requests | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/special_requests | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/standard_pricing | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/standard_pricing | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/standard_pricing | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/standard_room | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/standard_room | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/standard_room | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/suite | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/suite | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/suite | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/suite_pricing | cn | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| rooms/suite_pricing | en | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| rooms/suite_pricing | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| rooms/th_pricing | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| rooms/view_not_offered | th | 1 | 0 | 0 | 1 | 0.0% | [0.0%, 79.3%] |
| spa/facilities | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/facilities | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/facilities | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/massage_treatments | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/massage_treatments | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/massage_treatments | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/operating_hours | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/operating_hours | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/operating_hours | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/reservations | cn | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| spa/reservations | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/reservations | th | 3 | 1 | 1 | 1 | 33.3% | [6.1%, 79.2%] |
| spa/signature_packages | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/signature_packages | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| spa/signature_packages | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/airport_transfers | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/airport_transfers | en | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| transportation/airport_transfers | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/booking_tours | cn | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| transportation/booking_tours | en | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| transportation/booking_tours | th | 3 | 0 | 1 | 2 | 0.0% | [0.0%, 56.2%] |
| transportation/car_rental | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/car_rental | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/car_rental | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/parking | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/parking | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/parking | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/public_transportation | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/public_transportation | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/public_transportation | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/tour_packages | cn | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/tour_packages | en | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |
| transportation/tour_packages | th | 3 | 0 | 0 | 3 | 0.0% | [0.0%, 56.2%] |

## Defect breakdown

| Defect | Count | Example IDs |
|---|---:|---|
| `over_refuse` | 401 | `dining_the_grand_dining_room_breakfast_en_2`, `dining_the_grand_dining_room_breakfast_en_1`, `dining_skyline_restaurant_all_day_dining_en_1` |
| `incomplete` | 264 | `dining_the_grand_dining_room_breakfast_en_2`, `dining_the_grand_dining_room_breakfast_en_1`, `dining_the_grand_dining_room_breakfast_en_3` |
| `rag_miss` | 193 | `dining_the_grand_dining_room_breakfast_en_2`, `dining_the_grand_dining_room_breakfast_en_3`, `dining_skyline_restaurant_all_day_dining_en_2` |
| `hallucination` | 100 | `rooms_overview_en_3`, `rooms_room_comparison_en_1`, `rooms_in_room_amenities_en_2` |
| `tool_not_called` | 44 | `pricing_standard_early_bird_en`, `pricing_standard_standard_rate_en`, `pricing_standard_last_minute_en` |
| `spec_wrong` | 34 | `dining_skyline_restaurant_all_day_dining_en_1`, `rooms_special_requests_en_3`, `facilities_business_center_en_3` |
| `wrong_routing` | 2 | `dining_skyline_restaurant_all_day_dining_th_2`, `oo_kb_chinese_embassy_cn` |
| `language_leak` | 1 | `adv_force_chinese_en` |

## Regression watchlist

| Item | Severity | Metric | Threshold | Status |
|---|---|---:|---|---|
| rag_drift | CRITICAL | 0 | <= 0 | PASS |
| language_leak (EN+TH replies) | CRITICAL | 1 | <= 0 | **FAIL** |
| hallucination on hard negatives | CRITICAL | 3 | <= 0 | **FAIL** |
| booking lifecycle tool_error | CRITICAL | 0 | <= 0 | PASS |
| tool_call_leak rate | HIGH | 0.0 | <= 0.01 | PASS |
| over_refuse rate | HIGH | 0.8036 | <= 0.15 | **FAIL** |
| empty_response rate | HIGH | 0.0 | <= 0.03 | PASS |

## Promotion gates

| Gate | Metric | Threshold | Status |
|---|---:|---|---|
| Aggregate pass rate | 0.026 | >= 0.75 | **FAIL** |
| Worst per-domain pass rate | 0.0 | >= 0.65 | **FAIL** |
| Canary pass rate | — | >= 1.0 | N/A (skipped — no cases of this type in run) |
| Hard negative pass rate | 0.333 | >= 0.8 | **FAIL** |
| Per-row language match rate | 0.998 | >= 0.98 | PASS |

## Verdict: **DO NOT SHIP**

> A critical watchlist item failed — automatic no-ship per §2.8.
