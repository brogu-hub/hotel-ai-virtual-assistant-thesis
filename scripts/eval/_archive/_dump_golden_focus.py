"""Dump specific golden cases (utf-8 safe) for accuracy-impact triage."""
import json, sys
sys.stdout.reconfigure(encoding="utf-8")
ids = [
    # rooms domain
    "rooms_room_types_en_3", "rooms_extra_beds_en_2", "rooms_deluxe_room_en_2",
    "rooms_housekeeping_en_2", "rooms_room_types_en_1",
    # facilities
    "facilities_fitness_center_en_1", "facilities_fitness_center_en_3", "facilities_wifi_th_2",
    "facilities_business_center_th_1",
    # spa
    "spa_operating_hours_en_2", "spa_operating_hours_th_2", "spa_operating_hours_cn_2",
    "spa_reservations_en_1", "spa_facilities_en_3",
    # transportation - LARGEST PROBLEM AREA
    "transportation_car_rental_en_1", "transportation_car_rental_en_3",
    "transportation_parking_en_1", "transportation_public_transportation_en_3",
    "transportation_booking_tours_en_2", "transportation_airport_transfers_en_2",
    # policies
    "policies_smoking_en_1", "policies_lost_and_found_en_1", "policies_lost_and_found_en_2",
    "policies_cancellation_en_3",
    # emergency / faq
    "emergency_contacts_en_2", "emergency_medical_services_en_2", "faq_check_in_check_out_en_2",
    # pricing
    "pricing_deluxe_standard_rate_en", "pricing_suite_standard_rate_en", "pricing_standard_last_minute_en",
]
files = ["eval/dataset/golden_en.jsonl", "eval/dataset/golden_th.jsonl", "eval/dataset/golden_cn.jsonl"]
for f in files:
    for line in open(f, encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("id") in ids:
            print(f"== {rec['id']} [{f.split('/')[-1]}] ==")
            print(f"  Q: {rec.get('question','')[:140]}")
            print(f"  expected_facts: {rec.get('expected_facts')}")
            print(f"  must_contain_any: {rec.get('must_contain_any')}")
            print(f"  must_not_contain: {rec.get('must_not_contain')}")
            print(f"  source_files: {rec.get('source_files')}")
            print(f"  expected_tool_calls: {rec.get('expected_tool_calls')}")
            print()
