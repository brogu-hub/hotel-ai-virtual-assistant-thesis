#!/usr/bin/env python3
"""Test Thai politeness particle consistency (ครับ/ค่ะ/คะ)."""
import sys
import json
import requests

sys.stdout.reconfigure(encoding="utf-8")

CASES = [
    # (message, user_particle_hint, description)
    ("อาหารเช้ากี่โมงคะ", "female_q", "Female speaker question"),
    ("WiFi รหัสอะไรครับ", "male", "Male speaker question"),
    ("ขอบคุณค่ะ", "female_s", "Female speaker thanks"),
    ("สวัสดีครับ", "male", "Male greeting"),
    ("มีห้องว่างไหมคะ", "female_q", "Female question about availability"),
    ("ห้องไหนดีครับ", "male", "Male question about rooms"),
    ("ยกเลิกการจองค่ะ", "female_s", "Female booking cancel"),
]


def analyze(resp):
    """Count particle usage and detect inconsistencies."""
    krap = resp.count("ครับ")  # male
    ka_falling = resp.count("ค่ะ")  # female statement
    ka_rising = resp.count("คะ")  # female question
    # Check for mixing male + female in same response
    mixing = krap > 0 and (ka_falling > 0 or ka_rising > 0)
    # Check ends with sentence ending
    return {
        "ครับ": krap,
        "ค่ะ": ka_falling,
        "คะ": ka_rising,
        "mixing": mixing,
    }


print("=" * 80)
print("Thai Politeness Particle Test")
print("=" * 80)
print()

for msg, hint, desc in CASES:
    print(f"{'─' * 80}")
    print(f"USER ({desc}): {msg}")
    print(f"  Hint: user used {hint}")
    try:
        r = requests.post(
            "http://localhost:8088/chat",
            json={"message": msg},
            timeout=120,
        )
        data = r.json()
        resp = data.get("response", "")
    except Exception as e:
        print(f"  ERROR: {e}")
        continue

    counts = analyze(resp)
    print(f"  ครับ={counts['ครับ']}, ค่ะ={counts['ค่ะ']}, คะ={counts['คะ']}, mixing={counts['mixing']}")

    # Warnings
    warnings = []
    if counts["mixing"]:
        warnings.append("⚠ Mixed male/female particles in same response")
    if hint == "male" and counts["ค่ะ"] + counts["คะ"] > 0 and counts["ครับ"] == 0:
        warnings.append("⚠ User used ครับ but bot responded with ค่ะ/คะ only")
    if hint.startswith("female") and counts["ครับ"] > 0 and counts["ค่ะ"] + counts["คะ"] == 0:
        warnings.append("⚠ User used ค่ะ/คะ but bot responded with ครับ only")
    # ค่ะ vs คะ grammar check
    if "คะ?" in resp or "ค่ะ?" in resp:
        # ค่ะ should NOT appear before "?" (question mark needs คะ)
        if "ค่ะ?" in resp:
            warnings.append("⚠ ค่ะ before '?' should be คะ")

    for w in warnings:
        print(f"  {w}")
    print(f"  Response: {resp[:250]}")
    print()
