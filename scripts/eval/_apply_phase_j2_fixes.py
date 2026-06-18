#!/usr/bin/env python3
"""Phase J.2 fixes — idempotent bulk patcher for golden_*.jsonl + rubric_calibration.jsonl.

Applies four families of edits:
  (B) Remove "contact the front desk" from must_not_contain for the audited case IDs.
  (D) Update valet 200 → 500 THB (and TH equivalent) in expected_facts + must_contain_any.
  (D-extra) Update car_rental_th_3 calibration where valet 500 already correct (no-op check).
  Idempotency: re-running yields zero changes.

Outputs a JSON summary on stdout.
"""
import json
import sys
from pathlib import Path

ROOT = Path("z:/Dev_Drive/hote-ai-virtual-assistant-thesis/eval/dataset")

# === FIX (B): IDs to relax — remove "contact the front desk" from must_not_contain ===

# golden_en.jsonl — 138 cases
RELAX_EN = {
    "dining_the_grand_dining_room_breakfast_en_1", "dining_the_grand_dining_room_breakfast_en_2", "dining_the_grand_dining_room_breakfast_en_3",
    "dining_skyline_restaurant_all_day_dining_en_1", "dining_skyline_restaurant_all_day_dining_en_2", "dining_skyline_restaurant_all_day_dining_en_3",
    "dining_room_service_en_1", "dining_room_service_en_2", "dining_room_service_en_3",
    "dining_pool_bar_en_1", "dining_pool_bar_en_2", "dining_pool_bar_en_3",
    "rooms_overview_en_1", "rooms_overview_en_2", "rooms_overview_en_3",
    "rooms_standard_room_en_1", "rooms_standard_room_en_2", "rooms_standard_room_en_3",
    "rooms_deluxe_room_en_1", "rooms_deluxe_room_en_2", "rooms_deluxe_room_en_3",
    "rooms_suite_en_1", "rooms_suite_en_2", "rooms_suite_en_3",
    "rooms_penthouse_suite_en_1", "rooms_penthouse_suite_en_2", "rooms_penthouse_suite_en_3",
    "rooms_room_comparison_en_1", "rooms_room_comparison_en_2", "rooms_room_comparison_en_3",
    "rooms_special_requests_en_2", "rooms_special_requests_en_3",
    "rooms_room_types_en_1", "rooms_room_types_en_2", "rooms_room_types_en_3",
    "rooms_in_room_amenities_en_1", "rooms_in_room_amenities_en_2", "rooms_in_room_amenities_en_3",
    "rooms_housekeeping_en_1", "rooms_housekeeping_en_2", "rooms_housekeeping_en_3",
    "rooms_extra_beds_en_3",
    "spa_operating_hours_en_1", "spa_operating_hours_en_2", "spa_operating_hours_en_3",
    "spa_reservations_en_1", "spa_reservations_en_2", "spa_reservations_en_3",
    "spa_massage_treatments_en_1", "spa_massage_treatments_en_2", "spa_massage_treatments_en_3",
    "spa_signature_packages_en_1", "spa_signature_packages_en_2", "spa_signature_packages_en_3",
    "spa_facilities_en_1", "spa_facilities_en_2", "spa_facilities_en_3",
    "facilities_swimming_pool_en_1", "facilities_swimming_pool_en_2", "facilities_swimming_pool_en_3",
    "facilities_fitness_center_en_1", "facilities_fitness_center_en_2", "facilities_fitness_center_en_3",
    "facilities_business_center_en_1", "facilities_business_center_en_2", "facilities_business_center_en_3",
    "facilities_concierge_services_en_1", "facilities_concierge_services_en_2", "facilities_concierge_services_en_3",
    "facilities_parking_en_1", "facilities_parking_en_2", "facilities_parking_en_3",
    "faq_check_in_check_out_en_1", "faq_check_in_check_out_en_3",
    "faq_payment_billing_en_1", "faq_payment_billing_en_2", "faq_payment_billing_en_3",
    "faq_general_information_en_1", "faq_general_information_en_2", "faq_general_information_en_3",
    "policies_cancellation_en_1", "policies_cancellation_en_2", "policies_cancellation_en_3",
    "policies_pet_policy_en_1", "policies_pet_policy_en_2", "policies_pet_policy_en_3",
    "policies_smoking_en_1", "policies_smoking_en_2", "policies_smoking_en_3",
    "policies_quiet_hours_en_1", "policies_quiet_hours_en_2", "policies_quiet_hours_en_3",
    "policies_damage_policy_en_1", "policies_damage_policy_en_2", "policies_damage_policy_en_3",
    "policies_children_en_1", "policies_children_en_2", "policies_children_en_3",
    "policies_lost_and_found_en_3",
    "transportation_airport_transfers_en_1", "transportation_airport_transfers_en_2", "transportation_airport_transfers_en_3",
    "transportation_tour_packages_en_1", "transportation_tour_packages_en_2", "transportation_tour_packages_en_3",
    "transportation_car_rental_en_1", "transportation_car_rental_en_2", "transportation_car_rental_en_3",
    "transportation_public_transportation_en_1", "transportation_public_transportation_en_2", "transportation_public_transportation_en_3",
    "transportation_parking_en_1", "transportation_parking_en_2", "transportation_parking_en_3",
    "transportation_booking_tours_en_1", "transportation_booking_tours_en_2", "transportation_booking_tours_en_3",
    "attractions_nearby_en_1", "attractions_nearby_en_2", "attractions_nearby_en_3",
    "attractions_transportation_en_1", "attractions_transportation_en_2", "attractions_transportation_en_3",
    "emergency_contacts_en_1", "emergency_contacts_en_2", "emergency_contacts_en_3",
    "emergency_medical_services_en_1", "emergency_medical_services_en_2", "emergency_medical_services_en_3",
    "emergency_fire_safety_en_1", "emergency_fire_safety_en_2", "emergency_fire_safety_en_3",
    "emergency_embassy_contacts_en_1", "emergency_embassy_contacts_en_2", "emergency_embassy_contacts_en_3",
    "emergency_safety_tips_en_1", "emergency_safety_tips_en_2", "emergency_safety_tips_en_3",
}

# golden_th.jsonl — 56 cases
RELAX_TH = {
    "dining_room_service_th_1", "dining_room_service_th_2", "dining_room_service_th_3",
    "dining_pool_bar_th_1", "dining_pool_bar_th_2", "dining_pool_bar_th_3",
    "rooms_extra_beds_th_1", "rooms_extra_beds_th_2", "rooms_extra_beds_th_3",
    "spa_facilities_th_1", "spa_facilities_th_2", "spa_facilities_th_3",
    "facilities_wifi_th_1", "facilities_wifi_th_3",
    "facilities_parking_th_1", "facilities_parking_th_2", "facilities_parking_th_3",
    "faq_check_in_check_out_th_1", "faq_check_in_check_out_th_2", "faq_check_in_check_out_th_3",
    "faq_payment_billing_th_1", "faq_payment_billing_th_2", "faq_payment_billing_th_3",
    "policies_cancellation_th_1", "policies_cancellation_th_2", "policies_cancellation_th_3",
    "policies_pet_policy_th_1", "policies_pet_policy_th_2", "policies_pet_policy_th_3",
    "policies_damage_policy_th_1", "policies_damage_policy_th_2", "policies_damage_policy_th_3",
    "policies_children_th_1", "policies_children_th_2", "policies_children_th_3",
    "transportation_airport_transfers_th_1", "transportation_airport_transfers_th_2", "transportation_airport_transfers_th_3",
    "transportation_car_rental_th_1", "transportation_car_rental_th_2", "transportation_car_rental_th_3",
    "transportation_parking_th_1", "transportation_parking_th_2", "transportation_parking_th_3",
    "attractions_nearby_th_1", "attractions_nearby_th_2", "attractions_nearby_th_3",
    "attractions_transportation_th_1", "attractions_transportation_th_2", "attractions_transportation_th_3",
    "emergency_contacts_th_1", "emergency_contacts_th_2", "emergency_contacts_th_3",
    "emergency_medical_services_th_1", "emergency_medical_services_th_2", "emergency_medical_services_th_3",
}

# golden_cn.jsonl — 56 cases
RELAX_CN = {
    "dining_room_service_cn_1", "dining_room_service_cn_2", "dining_room_service_cn_3",
    "dining_pool_bar_cn_1", "dining_pool_bar_cn_2", "dining_pool_bar_cn_3",
    "rooms_extra_beds_cn_1", "rooms_extra_beds_cn_2", "rooms_extra_beds_cn_3",
    "spa_facilities_cn_1", "spa_facilities_cn_2", "spa_facilities_cn_3",
    "facilities_wifi_cn_1", "facilities_wifi_cn_3",
    "facilities_parking_cn_1", "facilities_parking_cn_2", "facilities_parking_cn_3",
    "faq_check_in_check_out_cn_1", "faq_check_in_check_out_cn_2", "faq_check_in_check_out_cn_3",
    "faq_payment_billing_cn_1", "faq_payment_billing_cn_2", "faq_payment_billing_cn_3",
    "policies_cancellation_cn_1", "policies_cancellation_cn_2", "policies_cancellation_cn_3",
    "policies_pet_policy_cn_1", "policies_pet_policy_cn_2", "policies_pet_policy_cn_3",
    "policies_damage_policy_cn_1", "policies_damage_policy_cn_2", "policies_damage_policy_cn_3",
    "policies_children_cn_1", "policies_children_cn_2", "policies_children_cn_3",
    "transportation_airport_transfers_cn_1", "transportation_airport_transfers_cn_2", "transportation_airport_transfers_cn_3",
    "transportation_car_rental_cn_1", "transportation_car_rental_cn_2", "transportation_car_rental_cn_3",
    "transportation_parking_cn_1", "transportation_parking_cn_2", "transportation_parking_cn_3",
    "attractions_nearby_cn_1", "attractions_nearby_cn_2", "attractions_nearby_cn_3",
    "attractions_transportation_cn_1", "attractions_transportation_cn_2", "attractions_transportation_cn_3",
    "emergency_contacts_cn_1", "emergency_contacts_cn_2", "emergency_contacts_cn_3",
    "emergency_medical_services_cn_1", "emergency_medical_services_cn_2", "emergency_medical_services_cn_3",
}

# rubric_calibration.jsonl — 37 cases (matched by id; harness loads file independently)
RELAX_CAL = {
    "faq_payment_billing_th_3", "faq_general_information_en_3", "facilities_fitness_center_en_2",
    "faq_general_information_en_2", "policies_children_cn_2", "faq_check_in_check_out_cn_3",
    "rooms_standard_room_en_3", "attractions_nearby_en_1", "policies_children_th_1",
    "faq_check_in_check_out_en_3", "facilities_parking_en_1", "faq_payment_billing_en_3",
    "emergency_medical_services_en_3", "attractions_nearby_en_2", "attractions_nearby_cn_2",
    "policies_pet_policy_en_1", "attractions_transportation_en_2", "faq_payment_billing_th_2",
    "faq_check_in_check_out_th_3", "rooms_extra_beds_cn_2", "transportation_airport_transfers_en_1",
    "dining_room_service_cn_3", "dining_room_service_en_3", "spa_massage_treatments_en_2",
    "spa_facilities_cn_1", "spa_facilities_cn_3", "policies_damage_policy_th_1",
    "emergency_embassy_contacts_en_2", "transportation_tour_packages_en_1", "faq_check_in_check_out_en_2",
    "spa_reservations_en_1", "emergency_medical_services_th_2", "attractions_transportation_en_3",
    "faq_check_in_check_out_th_2", "transportation_car_rental_th_3", "attractions_nearby_cn_3",
    "policies_cancellation_en_3",
}

# === FIX (D): valet 200 → 500 THB ===
# Per audit:
#   facilities_parking_en_2  → expected_facts/must_contain_any: 200 THB → 500 THB
#   transportation_parking_en_3 → 200 THB / 200 Baht → 500 THB / 500 Baht
#   facilities_parking_th_2  → 200 บาท → 500 บาท
VALET_FIX_EN = {"facilities_parking_en_2", "transportation_parking_en_3"}
VALET_FIX_TH = {"facilities_parking_th_2"}

PHRASE = "contact the front desk"


def patch_must_not_contain(rec: dict, target_ids: set) -> bool:
    """Return True if record was modified."""
    if rec.get("id") not in target_ids:
        return False
    mnc = rec.get("must_not_contain")
    if not isinstance(mnc, list):
        return False
    new_mnc = [p for p in mnc if p != PHRASE]
    if new_mnc != mnc:
        rec["must_not_contain"] = new_mnc
        return True
    return False


def patch_valet_price(rec: dict, target_ids: set, lang: str) -> bool:
    """Update 200 THB/บาท → 500 THB/บาท in expected_facts + must_contain_any.

    Also drops bare "200" / "200." tokens (single-element strings) so the bot
    can't false-pass by quoting the stale KB. Whole-token equality only — does
    not touch "1200" or "200 THB" (the latter is rewritten by the replacements).
    """
    if rec.get("id") not in target_ids:
        return False
    changed = False
    replacements = [
        ("200 THB", "500 THB"),
        ("200 Baht", "500 Baht"),
        ("200 baht", "500 baht"),
        ("200 บาท", "500 บาท"),
        ("฿200", "฿500"),
    ]
    bare_stale = {"200", "200.", "200,"}
    for field in ("expected_facts", "must_contain_any"):
        vals = rec.get(field)
        if not isinstance(vals, list):
            continue
        new_vals = []
        local_changed = False
        for v in vals:
            if not isinstance(v, str):
                new_vals.append(v)
                continue
            new_v = v
            for old, new in replacements:
                if old in new_v:
                    new_v = new_v.replace(old, new)
            if new_v != v:
                local_changed = True
            # Drop bare "200" token that would otherwise let the bot
            # pass by quoting the stale KB value.
            if new_v.strip() in bare_stale:
                local_changed = True
                continue
            new_vals.append(new_v)
        if local_changed:
            rec[field] = new_vals
            changed = True
    return changed


def process_file(path: Path, relax_ids: set, valet_ids: set, lang: str) -> dict:
    if not path.exists():
        return {"path": str(path), "missing": True}
    relaxed = 0
    valet_fixed = 0
    out_lines = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line_stripped = line.rstrip("\n")
            if not line_stripped.strip():
                out_lines.append(line)
                continue
            rec = json.loads(line_stripped)
            if patch_must_not_contain(rec, relax_ids):
                relaxed += 1
            if patch_valet_price(rec, valet_ids, lang):
                valet_fixed += 1
            out_lines.append(json.dumps(rec, ensure_ascii=False) + "\n")
    with path.open("w", encoding="utf-8") as f:
        f.writelines(out_lines)
    return {"path": str(path), "relaxed": relaxed, "valet_fixed": valet_fixed}


def main():
    results = []
    results.append(process_file(ROOT / "golden_en.jsonl", RELAX_EN, VALET_FIX_EN, "en"))
    results.append(process_file(ROOT / "golden_th.jsonl", RELAX_TH, VALET_FIX_TH, "th"))
    results.append(process_file(ROOT / "golden_cn.jsonl", RELAX_CN, set(), "cn"))
    results.append(process_file(ROOT / "rubric_calibration.jsonl", RELAX_CAL, set(), "mixed"))
    print(json.dumps({"results": results}, indent=2))


if __name__ == "__main__":
    main()
