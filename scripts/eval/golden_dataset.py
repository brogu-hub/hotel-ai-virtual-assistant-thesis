# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Golden Dataset Generator for RAG Evaluation

Generates bilingual Q&A pairs from hotel markdown files for testing
RAG accuracy. Each pair includes:
- Question (English and Thai)
- Expected answer extracted from source
- Expected keywords that must appear
- Source file reference

Usage:
    from scripts.eval.golden_dataset import generate_golden_dataset, load_golden_dataset

    # Generate new dataset
    dataset = generate_golden_dataset("data/hotel", "scripts/eval/dataset.json")

    # Load existing dataset
    dataset = load_golden_dataset("scripts/eval/dataset.json")
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from .models import (
    GoldenQAPair,
    GoldenDataset,
    Language,
    Category,
    Difficulty,
)

logger = logging.getLogger(__name__)

# Predefined Q&A pairs extracted from hotel markdown files
# Each category has English and Thai versions
GOLDEN_QA_PAIRS: List[dict] = [
    # === DINING (dining_services.md) ===
    {
        "id": "dining_en_01",
        "question": "What time is breakfast?",
        "expected_answer": "Breakfast is served at The Grand Dining Room from 6:30 AM to 10:30 AM daily, including holidays. It's complimentary for all in-house guests.",
        "expected_context": ["dining_services.md"],
        "expected_keywords": ["6:30", "10:30", "Grand Dining", "complimentary", "free"],
        "language": Language.ENGLISH,
        "category": Category.DINING,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "dining_th_01",
        "question": "อาหารเช้าเสิร์ฟกี่โมง?",
        "expected_answer": "อาหารเช้าเสิร์ฟที่ห้อง The Grand Dining Room ตั้งแต่ 06:30 - 10:30 น. ทุกวัน รวมวันหยุด ฟรีสำหรับผู้เข้าพักทุกท่าน",
        "expected_context": ["dining_services.md"],
        "expected_keywords": ["06:30", "10:30", "Grand Dining", "ฟรี"],
        "language": Language.THAI,
        "category": Category.DINING,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "dining_en_02",
        "question": "Is room service available 24 hours?",
        "expected_answer": "Yes, room service is available 24 hours a day, 7 days a week. Delivery time is 30-45 minutes and there's a 100 THB service charge per order.",
        "expected_context": ["dining_services.md"],
        "expected_keywords": ["24 hours", "30-45", "100 THB", "service charge"],
        "language": Language.ENGLISH,
        "category": Category.DINING,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "dining_th_02",
        "question": "รูมเซอร์วิสเปิด 24 ชั่วโมงไหม?",
        "expected_answer": "รูมเซอร์วิสเปิดให้บริการ 24 ชั่วโมง 7 วัน เวลาจัดส่ง 30-45 นาที ค่าบริการ 100 บาทต่อออเดอร์",
        "expected_context": ["dining_services.md"],
        "expected_keywords": ["24 ชั่วโมง", "30-45", "100 บาท"],
        "language": Language.THAI,
        "category": Category.DINING,
        "difficulty": Difficulty.EASY,
    },
    # === FACILITIES (facilities_amenities.md) ===
    {
        "id": "facilities_en_01",
        "question": "What is the WiFi password?",
        "expected_answer": "The WiFi network name is 'HotelGuest' and the password is 'HOTEL2024GUEST'. Speed is 100 Mbps and it's complimentary for all guests throughout the hotel.",
        "expected_context": ["facilities_amenities.md"],
        "expected_keywords": ["HotelGuest", "HOTEL2024GUEST", "100 Mbps", "complimentary"],
        "language": Language.ENGLISH,
        "category": Category.FACILITIES,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "facilities_th_01",
        "question": "รหัส WiFi คืออะไร?",
        "expected_answer": "ชื่อเครือข่าย WiFi คือ 'HotelGuest' รหัสผ่านคือ 'HOTEL2024GUEST' ความเร็ว 100 Mbps ใช้ได้ฟรีทั่วทั้งโรงแรม",
        "expected_context": ["facilities_amenities.md"],
        "expected_keywords": ["HotelGuest", "HOTEL2024GUEST", "100 Mbps", "ฟรี"],
        "language": Language.THAI,
        "category": Category.FACILITIES,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "facilities_en_02",
        "question": "What are the swimming pool hours?",
        "expected_answer": "The swimming pool is on the 5th Floor Rooftop and is open from 6:00 AM to 9:00 PM daily. The pool is 25x10 meters with depths from 1.2 to 1.8 meters. Pool towels are available for free.",
        "expected_context": ["facilities_amenities.md"],
        "expected_keywords": ["5th Floor", "6:00 AM", "9:00 PM", "25", "free"],
        "language": Language.ENGLISH,
        "category": Category.FACILITIES,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "facilities_th_02",
        "question": "สระว่ายน้ำเปิดกี่โมง?",
        "expected_answer": "สระว่ายน้ำอยู่ดาดฟ้าชั้น 5 เปิดให้บริการ 06:00 - 21:00 น. ทุกวัน ขนาดสระ 25x10 เมตร ลึก 1.2-1.8 เมตร มีผ้าเช็ดตัวฟรี",
        "expected_context": ["facilities_amenities.md"],
        "expected_keywords": ["ชั้น 5", "06:00", "21:00", "25", "ฟรี"],
        "language": Language.THAI,
        "category": Category.FACILITIES,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "facilities_en_03",
        "question": "Is the gym open 24 hours?",
        "expected_answer": "Yes, the Fitness Center on the 4th Floor is open 24 hours with keycard access. It's complimentary for all guests. Personal training is available at 1,000 THB per session.",
        "expected_context": ["facilities_amenities.md"],
        "expected_keywords": ["24 hours", "4th Floor", "keycard", "complimentary", "1,000"],
        "language": Language.ENGLISH,
        "category": Category.FACILITIES,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "facilities_th_03",
        "question": "ฟิตเนสเปิด 24 ชั่วโมงไหม?",
        "expected_answer": "ใช่ค่ะ ฟิตเนสเซ็นเตอร์อยู่ชั้น 4 เปิด 24 ชั่วโมง เข้าด้วยคีย์การ์ด ฟรีสำหรับผู้เข้าพัก เทรนเนอร์ส่วนตัว 1,000 บาทต่อครั้ง",
        "expected_context": ["facilities_amenities.md"],
        "expected_keywords": ["24 ชั่วโมง", "ชั้น 4", "ฟรี", "1,000"],
        "language": Language.THAI,
        "category": Category.FACILITIES,
        "difficulty": Difficulty.MEDIUM,
    },
    # === SPA (spa_wellness.md) ===
    {
        "id": "spa_en_01",
        "question": "What are the spa operating hours?",
        "expected_answer": "The Serenity Spa is open daily from 10:00 AM to 10:00 PM, located on the 3rd Floor. Last booking is at 8:30 PM. Advance booking is recommended, especially on weekends.",
        "expected_context": ["spa_wellness.md"],
        "expected_keywords": ["10:00 AM", "10:00 PM", "3rd Floor", "8:30 PM"],
        "language": Language.ENGLISH,
        "category": Category.SPA,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "spa_th_01",
        "question": "สปาเปิดกี่โมง?",
        "expected_answer": "สปา Serenity เปิดทุกวัน 10:00 - 22:00 น. อยู่ชั้น 3 รับจองคิวสุดท้าย 20:30 น. แนะนำให้จองล่วงหน้าโดยเฉพาะวันหยุดสุดสัปดาห์",
        "expected_context": ["spa_wellness.md"],
        "expected_keywords": ["10:00", "22:00", "ชั้น 3", "20:30"],
        "language": Language.THAI,
        "category": Category.SPA,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "spa_en_02",
        "question": "How much is a Thai massage?",
        "expected_answer": "Thai Traditional Massage prices are: 60 minutes for 1,500 THB, 90 minutes for 2,000 THB, and 120 minutes for 2,500 THB. It combines acupressure, stretching, and energy work.",
        "expected_context": ["spa_wellness.md"],
        "expected_keywords": ["1,500", "2,000", "2,500", "THB", "60", "90", "120"],
        "language": Language.ENGLISH,
        "category": Category.SPA,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "spa_th_02",
        "question": "นวดแผนไทยราคาเท่าไหร่?",
        "expected_answer": "นวดแผนไทยโบราณ: 60 นาที 1,500 บาท, 90 นาที 2,000 บาท, 120 นาที 2,500 บาท ผสมผสานการกดจุด การยืดเหยียด และการปรับพลังงาน",
        "expected_context": ["spa_wellness.md"],
        "expected_keywords": ["1,500", "2,000", "2,500", "บาท", "60", "90", "120"],
        "language": Language.THAI,
        "category": Category.SPA,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "spa_en_03",
        "question": "What is the Royal Thai Experience package?",
        "expected_answer": "The Royal Thai Experience is a 3-hour signature package for 5,500 THB. It includes Thai herbal steam (30 min), Thai traditional massage (90 min), Thai facial treatment (60 min), plus herbal tea and light refreshments.",
        "expected_context": ["spa_wellness.md"],
        "expected_keywords": ["3 hours", "5,500", "herbal steam", "massage", "facial"],
        "language": Language.ENGLISH,
        "category": Category.SPA,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "spa_th_03",
        "question": "แพ็คเกจราชาไทยคืออะไร?",
        "expected_answer": "แพ็คเกจราชาไทยเป็นแพ็คเกจพิเศษ 3 ชั่วโมง ราคา 5,500 บาท รวมอบไอน้ำสมุนไพร 30 นาที นวดแผนไทย 90 นาที ทรีตเมนต์หน้า 60 นาที พร้อมชาสมุนไพรและของว่าง",
        "expected_context": ["spa_wellness.md"],
        "expected_keywords": ["3 ชั่วโมง", "5,500", "อบไอน้ำ", "นวด", "ทรีตเมนต์"],
        "language": Language.THAI,
        "category": Category.SPA,
        "difficulty": Difficulty.MEDIUM,
    },
    # === POLICY (policies_rules.md) ===
    {
        "id": "policy_en_01",
        "question": "What is the cancellation policy?",
        "expected_answer": "Free cancellation is available more than 48 hours before check-in. Within 48 hours, 1 night charge applies. No-show incurs full stay charge. Early departure has no refund for unused nights.",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["48 hours", "free", "1 night", "no-show", "full"],
        "language": Language.ENGLISH,
        "category": Category.POLICY,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "policy_th_01",
        "question": "นโยบายยกเลิกการจองเป็นอย่างไร?",
        "expected_answer": "ยกเลิกฟรีล่วงหน้ามากกว่า 48 ชั่วโมงก่อนเช็คอิน ภายใน 48 ชั่วโมงคิดค่าห้อง 1 คืน ไม่มาเข้าพักคิดค่าห้องทั้งหมด ออกก่อนกำหนดไม่คืนเงินคืนที่ไม่ได้ใช้",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["48 ชั่วโมง", "ฟรี", "1 คืน", "ไม่มา", "ทั้งหมด"],
        "language": Language.THAI,
        "category": Category.POLICY,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "policy_en_02",
        "question": "Can I bring my pet to the hotel?",
        "expected_answer": "Small pets under 5 kg are allowed. There's a pet fee of 500 THB per night and a refundable deposit of 2,000 THB. Pet-friendly rooms have limited availability. Pets must be leashed in public areas and are not allowed in restaurants, spa, pool, or fitness center.",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["5 kg", "500 THB", "2,000", "leashed", "not allowed"],
        "language": Language.ENGLISH,
        "category": Category.POLICY,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "policy_th_02",
        "question": "พาสัตว์เลี้ยงมาได้ไหม?",
        "expected_answer": "อนุญาตเฉพาะสัตว์เลี้ยงขนาดเล็กน้ำหนักไม่เกิน 5 กก. ค่าสัตว์เลี้ยง 500 บาท/คืน เงินประกัน 2,000 บาท (คืนให้เมื่อเช็คเอาท์) ต้องใส่สายจูงในพื้นที่สาธารณะ ห้ามนำเข้าร้านอาหาร สปา สระว่ายน้ำ ฟิตเนส",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["5 กก", "500 บาท", "2,000", "สายจูง", "ห้าม"],
        "language": Language.THAI,
        "category": Category.POLICY,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "policy_en_03",
        "question": "Is smoking allowed in the hotel?",
        "expected_answer": "The hotel is 100% non-smoking. Smoking is only allowed at the designated outdoor area on the ground floor terrace. There's a 5,000 THB cleaning fee for smoking in the room.",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["non-smoking", "ground floor", "terrace", "5,000 THB"],
        "language": Language.ENGLISH,
        "category": Category.POLICY,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "policy_th_03",
        "question": "สูบบุหรี่ในโรงแรมได้ไหม?",
        "expected_answer": "โรงแรมปลอดบุหรี่ 100% สูบบุหรี่ได้เฉพาะบริเวณระเบียงชั้น 1 ที่กำหนดเท่านั้น หากสูบบุหรี่ในห้องพักมีค่าปรับ 5,000 บาท",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["ปลอดบุหรี่", "ชั้น 1", "ระเบียง", "5,000 บาท"],
        "language": Language.THAI,
        "category": Category.POLICY,
        "difficulty": Difficulty.EASY,
    },
    # === FAQ (hotel_faq.md) ===
    {
        "id": "faq_en_01",
        "question": "What time is check-in and check-out?",
        "expected_answer": "Check-in time is 2:00 PM (14:00). Check-out time is 12:00 PM (noon). Early check-in and late check-out may be available upon request, subject to availability.",
        "expected_context": ["hotel_faq.md"],
        "expected_keywords": ["2:00 PM", "14:00", "12:00", "noon", "early", "late"],
        "language": Language.ENGLISH,
        "category": Category.FAQ,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "faq_th_01",
        "question": "เช็คอินและเช็คเอาท์กี่โมง?",
        "expected_answer": "เช็คอินได้ตั้งแต่ 14:00 น. เช็คเอาท์ภายใน 12:00 น. สามารถขอเช็คอินก่อนเวลาหรือเช็คเอาท์ล่าช้าได้หากห้องว่าง",
        "expected_context": ["hotel_faq.md"],
        "expected_keywords": ["14:00", "12:00", "เช็คอิน", "เช็คเอาท์"],
        "language": Language.THAI,
        "category": Category.FAQ,
        "difficulty": Difficulty.EASY,
    },
    # === ROOM TYPES (room_types.md) ===
    {
        "id": "room_en_01",
        "question": "What room types are available?",
        "expected_answer": "We offer 4 room types: Standard Room (28 sqm, 2,500 THB), Deluxe Room (35 sqm, 3,500 THB), Suite (55 sqm, 5,500 THB), and Penthouse Suite (120 sqm, 15,000 THB). All rooms include breakfast, WiFi, and minibar.",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["Standard", "Deluxe", "Suite", "Penthouse", "sqm"],
        "language": Language.ENGLISH,
        "category": Category.ROOM,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "room_th_01",
        "question": "มีห้องพักประเภทไหนบ้าง?",
        "expected_answer": "เรามีห้องพัก 4 ประเภท: Standard Room (28 ตร.ม. 2,500 บาท), Deluxe Room (35 ตร.ม. 3,500 บาท), Suite (55 ตร.ม. 5,500 บาท), Penthouse Suite (120 ตร.ม. 15,000 บาท) ทุกห้องรวมอาหารเช้า WiFi และมินิบาร์",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["Standard", "Deluxe", "Suite", "Penthouse", "ตร.ม."],
        "language": Language.THAI,
        "category": Category.ROOM,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "room_en_02",
        "question": "Does the Deluxe room have a bathtub?",
        "expected_answer": "Yes, the Deluxe Room features a separate bathtub and rain shower. It also includes a work desk, sitting area, and city or garden view balcony.",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["bathtub", "rain shower", "balcony", "Deluxe"],
        "language": Language.ENGLISH,
        "category": Category.ROOM,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "room_th_02",
        "question": "ห้อง Deluxe มีอ่างอาบน้ำไหม?",
        "expected_answer": "มีค่ะ ห้อง Deluxe มีอ่างอาบน้ำแยกและฝักบัวเรนชาวเวอร์ มีโต๊ะทำงาน มุมนั่งเล่น และระเบียงวิวเมืองหรือสวน",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["อ่างอาบน้ำ", "ฝักบัว", "ระเบียง", "Deluxe"],
        "language": Language.THAI,
        "category": Category.ROOM,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "room_en_03",
        "question": "What is the size of the Penthouse Suite?",
        "expected_answer": "The Penthouse Suite is 120 square meters, located on the top floor. It features a private terrace with panoramic views, separate living and dining areas, kitchenette, jacuzzi, and 24-hour butler service.",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["120", "terrace", "panoramic", "butler", "Penthouse"],
        "language": Language.ENGLISH,
        "category": Category.ROOM,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "room_th_03",
        "question": "ห้อง Penthouse ใหญ่แค่ไหน?",
        "expected_answer": "Penthouse Suite กว้าง 120 ตร.ม. อยู่ชั้นบนสุด มีระเบียงส่วนตัววิวพาโนรามา ห้องนั่งเล่นและห้องอาหารแยก ครัวเล็ก อ่างจากุซซี่ และบัตเลอร์ 24 ชั่วโมง",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["120", "ระเบียง", "พาโนรามา", "บัตเลอร์", "Penthouse"],
        "language": Language.THAI,
        "category": Category.ROOM,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "room_en_04",
        "question": "Can I request extra beds?",
        "expected_answer": "Extra beds are available for 800 THB per night. Maximum 1 extra bed per room for Standard and Deluxe, 2 for Suite, and 3 for Penthouse. Baby cots are complimentary upon request.",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["800", "extra bed", "baby cot", "complimentary"],
        "language": Language.ENGLISH,
        "category": Category.ROOM,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "room_th_04",
        "question": "ขอเตียงเสริมได้ไหม?",
        "expected_answer": "เตียงเสริมมีให้บริการ 800 บาท/คืน เพิ่มได้สูงสุด 1 เตียงสำหรับ Standard/Deluxe, 2 เตียงสำหรับ Suite, 3 เตียงสำหรับ Penthouse เปลเด็กฟรีเมื่อแจ้งล่วงหน้า",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["800", "เตียงเสริม", "เปล", "ฟรี"],
        "language": Language.THAI,
        "category": Category.ROOM,
        "difficulty": Difficulty.MEDIUM,
    },
    # === TRANSPORTATION (transportation.md) ===
    {
        "id": "transport_en_01",
        "question": "Is there airport shuttle?",
        "expected_answer": "Yes, we offer airport shuttle service. From Suvarnabhumi Airport: 1,200 THB (45-60 min), from Don Mueang: 1,000 THB (30-45 min). Advance booking 24 hours recommended. Complimentary shuttle to nearby BTS station hourly.",
        "expected_context": ["transportation.md"],
        "expected_keywords": ["1,200", "1,000", "Suvarnabhumi", "Don Mueang", "shuttle"],
        "language": Language.ENGLISH,
        "category": Category.TRANSPORTATION,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "transport_th_01",
        "question": "มีรถรับส่งสนามบินไหม?",
        "expected_answer": "มีค่ะ รถรับส่งสนามบิน: สุวรรณภูมิ 1,200 บาท (45-60 นาที), ดอนเมือง 1,000 บาท (30-45 นาที) แนะนำจองล่วงหน้า 24 ชม. มีรถฟรีไป BTS ใกล้เคียงทุกชั่วโมง",
        "expected_context": ["transportation.md"],
        "expected_keywords": ["1,200", "1,000", "สุวรรณภูมิ", "ดอนเมือง", "ฟรี"],
        "language": Language.THAI,
        "category": Category.TRANSPORTATION,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "transport_en_02",
        "question": "Can you arrange a tour to Grand Palace?",
        "expected_answer": "Yes, we offer half-day Grand Palace and Temple tour at 1,500 THB per person. Includes air-conditioned van, English-speaking guide, entrance fees, and bottled water. Tours depart at 8:30 AM and 1:00 PM daily.",
        "expected_context": ["transportation.md"],
        "expected_keywords": ["Grand Palace", "1,500", "guide", "entrance", "8:30"],
        "language": Language.ENGLISH,
        "category": Category.TRANSPORTATION,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "transport_th_02",
        "question": "จัดทัวร์พระบรมมหาราชวังได้ไหม?",
        "expected_answer": "ได้ค่ะ มีทัวร์ครึ่งวันพระบรมมหาราชวังและวัด 1,500 บาท/ท่าน รวมรถตู้ปรับอากาศ ไกด์พูดอังกฤษ ค่าเข้าชม และน้ำดื่ม ออกเดินทาง 08:30 และ 13:00 น. ทุกวัน",
        "expected_context": ["transportation.md"],
        "expected_keywords": ["พระบรมมหาราชวัง", "1,500", "ไกด์", "ค่าเข้า", "08:30"],
        "language": Language.THAI,
        "category": Category.TRANSPORTATION,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "transport_en_03",
        "question": "Is there parking available?",
        "expected_answer": "Yes, we have underground parking with 24-hour security. Rates: hotel guests 200 THB/day, visitors 50 THB/hour (first 30 minutes free). Valet parking available for 300 THB.",
        "expected_context": ["transportation.md"],
        "expected_keywords": ["parking", "200", "50", "valet", "300"],
        "language": Language.ENGLISH,
        "category": Category.TRANSPORTATION,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "transport_th_03",
        "question": "มีที่จอดรถไหม?",
        "expected_answer": "มีค่ะ ที่จอดรถใต้ดินมีรปภ. 24 ชม. ผู้เข้าพัก 200 บาท/วัน ผู้มาเยือน 50 บาท/ชม. (30 นาทีแรกฟรี) บริการ Valet 300 บาท",
        "expected_context": ["transportation.md"],
        "expected_keywords": ["ที่จอดรถ", "200", "50", "Valet", "300"],
        "language": Language.THAI,
        "category": Category.TRANSPORTATION,
        "difficulty": Difficulty.EASY,
    },
    # === EMERGENCY (emergency_contacts.md) ===
    {
        "id": "emergency_en_01",
        "question": "What is the emergency contact number?",
        "expected_answer": "For emergencies, call Front Desk at extension 0 or direct line 02-123-4567 (24 hours). For medical emergency, our in-house clinic is on the 2nd floor (8 AM - 8 PM) or call 1669 for ambulance.",
        "expected_context": ["emergency_contacts.md"],
        "expected_keywords": ["02-123-4567", "extension 0", "1669", "2nd floor", "clinic"],
        "language": Language.ENGLISH,
        "category": Category.EMERGENCY,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "emergency_th_01",
        "question": "เบอร์ฉุกเฉินคือเบอร์อะไร?",
        "expected_answer": "กรณีฉุกเฉินโทรหา Front Desk กด 0 หรือสายตรง 02-123-4567 (24 ชม.) ฉุกเฉินทางการแพทย์ คลินิกในโรงแรมชั้น 2 (8:00-20:00 น.) หรือโทร 1669 เรียกรถพยาบาล",
        "expected_context": ["emergency_contacts.md"],
        "expected_keywords": ["02-123-4567", "กด 0", "1669", "ชั้น 2", "คลินิก"],
        "language": Language.THAI,
        "category": Category.EMERGENCY,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "emergency_en_02",
        "question": "Is there a doctor on call?",
        "expected_answer": "Yes, we have an in-house clinic on the 2nd floor open 8 AM - 8 PM with a nurse. A doctor is on-call 24 hours and can be in the hotel within 30 minutes. Consultation fee is 1,500 THB.",
        "expected_context": ["emergency_contacts.md"],
        "expected_keywords": ["doctor", "on-call", "24 hours", "30 minutes", "1,500"],
        "language": Language.ENGLISH,
        "category": Category.EMERGENCY,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "emergency_th_02",
        "question": "มีหมอประจำโรงแรมไหม?",
        "expected_answer": "มีคลินิกในโรงแรมชั้น 2 เปิด 8:00-20:00 น. มีพยาบาลประจำ แพทย์เวรตลอด 24 ชม. มาถึงภายใน 30 นาที ค่าตรวจ 1,500 บาท",
        "expected_context": ["emergency_contacts.md"],
        "expected_keywords": ["แพทย์", "24 ชม.", "30 นาที", "1,500", "คลินิก"],
        "language": Language.THAI,
        "category": Category.EMERGENCY,
        "difficulty": Difficulty.MEDIUM,
    },
    # === COMPLEX/MULTI-PART QUESTIONS ===
    {
        "id": "complex_en_01",
        "question": "I'm arriving at 10 AM, can I check in early and have breakfast?",
        "expected_answer": "Check-in is normally at 2 PM, but early check-in may be available based on room availability. Breakfast is served until 10:30 AM at The Grand Dining Room. We recommend contacting us in advance to arrange early check-in and late breakfast.",
        "expected_context": ["hotel_faq.md", "dining_services.md"],
        "expected_keywords": ["2 PM", "14:00", "10:30", "early", "availability"],
        "language": Language.ENGLISH,
        "category": Category.FAQ,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "complex_th_01",
        "question": "ผมจะมาถึง 10 โมงเช้า เช็คอินก่อนได้ไหม แล้วทันกินข้าวเช้าไหม?",
        "expected_answer": "เช็คอินปกติ 14:00 น. แต่สามารถขอเช็คอินก่อนได้ขึ้นอยู่กับห้องว่าง อาหารเช้าเสิร์ฟถึง 10:30 น. ที่ The Grand Dining Room แนะนำแจ้งล่วงหน้าเพื่อจัดเตรียมเช็คอินก่อนและอาหารเช้าพิเศษ",
        "expected_context": ["hotel_faq.md", "dining_services.md"],
        "expected_keywords": ["14:00", "10:30", "ก่อน", "ห้องว่าง"],
        "language": Language.THAI,
        "category": Category.FAQ,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "complex_en_02",
        "question": "What's included in the Suite and can I book a spa treatment?",
        "expected_answer": "The Suite (55 sqm, 5,500 THB) includes separate living area, kitchenette, premium minibar, breakfast, and butler service. Spa is on 3rd floor, open 10 AM - 10 PM. Thai massage from 1,500 THB (60 min). Advance booking recommended.",
        "expected_context": ["room_types.md", "spa_wellness.md"],
        "expected_keywords": ["55", "5,500", "Suite", "spa", "1,500", "massage"],
        "language": Language.ENGLISH,
        "category": Category.ROOM,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "complex_th_02",
        "question": "ห้อง Suite มีอะไรบ้าง แล้วจองสปาได้ไหม?",
        "expected_answer": "Suite (55 ตร.ม. 5,500 บาท) มีห้องนั่งเล่นแยก ครัวเล็ก มินิบาร์พรีเมียม อาหารเช้า และบัตเลอร์ สปาอยู่ชั้น 3 เปิด 10:00-22:00 น. นวดแผนไทยเริ่ม 1,500 บาท (60 นาที) แนะนำจองล่วงหน้า",
        "expected_context": ["room_types.md", "spa_wellness.md"],
        "expected_keywords": ["55", "5,500", "Suite", "สปา", "1,500", "นวด"],
        "language": Language.THAI,
        "category": Category.ROOM,
        "difficulty": Difficulty.HARD,
    },
    # === EDGE CASES ===
    {
        "id": "edge_en_01",
        "question": "Do you have gluten-free breakfast options?",
        "expected_answer": "Yes, we accommodate dietary requirements including gluten-free, vegetarian, vegan, and halal options. Please inform the restaurant staff or note it during booking. Our chef can prepare special meals upon request.",
        "expected_context": ["dining_services.md"],
        "expected_keywords": ["gluten-free", "dietary", "vegetarian", "halal", "special"],
        "language": Language.ENGLISH,
        "category": Category.DINING,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "edge_th_01",
        "question": "มีอาหารเช้าสำหรับคนแพ้กลูเตนไหม?",
        "expected_answer": "มีค่ะ เรารองรับความต้องการด้านอาหารรวมถึงปลอดกลูเตน มังสวิรัติ วีแกน และฮาลาล กรุณาแจ้งพนักงานร้านอาหารหรือระบุตอนจอง เชฟสามารถเตรียมอาหารพิเศษได้",
        "expected_context": ["dining_services.md"],
        "expected_keywords": ["กลูเตน", "มังสวิรัติ", "วีแกน", "ฮาลาล", "พิเศษ"],
        "language": Language.THAI,
        "category": Category.DINING,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "edge_en_02",
        "question": "Is the pool heated?",
        "expected_answer": "The rooftop pool maintains a comfortable temperature year-round. Water temperature is kept at 28-30°C. The pool also has a children's section (0.6m depth) and poolside bar service.",
        "expected_context": ["facilities_amenities.md"],
        "expected_keywords": ["temperature", "28", "30", "children", "poolside"],
        "language": Language.ENGLISH,
        "category": Category.FACILITIES,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "edge_th_02",
        "question": "สระว่ายน้ำอุ่นไหม?",
        "expected_answer": "สระบนดาดฟ้ามีอุณหภูมิน้ำเหมาะสมตลอดปี รักษาอุณหภูมิที่ 28-30°C มีโซนเด็ก (ลึก 0.6 ม.) และบริการบาร์ริมสระ",
        "expected_context": ["facilities_amenities.md"],
        "expected_keywords": ["อุณหภูมิ", "28", "30", "เด็ก", "บาร์"],
        "language": Language.THAI,
        "category": Category.FACILITIES,
        "difficulty": Difficulty.MEDIUM,
    },
    # === NEGATIVE/BOUNDARY CASES ===
    {
        "id": "negative_en_01",
        "question": "Can I cook in my room?",
        "expected_answer": "Cooking appliances are not allowed in Standard and Deluxe rooms for safety reasons. Suite and Penthouse have a kitchenette with microwave and electric kettle. Room service is available 24 hours as an alternative.",
        "expected_context": ["policies_rules.md", "room_types.md"],
        "expected_keywords": ["not allowed", "safety", "kitchenette", "microwave", "room service"],
        "language": Language.ENGLISH,
        "category": Category.POLICY,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "negative_th_01",
        "question": "ทำอาหารในห้องได้ไหม?",
        "expected_answer": "ห้าม Standard และ Deluxe ใช้เครื่องทำอาหารเพื่อความปลอดภัย Suite และ Penthouse มีครัวเล็กพร้อมไมโครเวฟและกาต้มน้ำ มี Room Service 24 ชม. เป็นทางเลือก",
        "expected_context": ["policies_rules.md", "room_types.md"],
        "expected_keywords": ["ห้าม", "ปลอดภัย", "ครัวเล็ก", "ไมโครเวฟ", "Room Service"],
        "language": Language.THAI,
        "category": Category.POLICY,
        "difficulty": Difficulty.MEDIUM,
    },
    # === GREETING & SMALL TALK ===
    {
        "id": "greeting_en_01",
        "question": "Hello, I just arrived at the hotel",
        "expected_answer": "Welcome to The Grand Horizon Hotel! We're delighted to have you. Our front desk is available 24/7 to assist you. Is there anything specific you'd like to know about our facilities or services?",
        "expected_context": [],
        "expected_keywords": ["welcome", "Grand Horizon", "front desk", "assist"],
        "language": Language.ENGLISH,
        "category": Category.FAQ,
        "difficulty": Difficulty.EASY,
    },
    {
        "id": "greeting_th_01",
        "question": "สวัสดีครับ เพิ่งมาถึงโรงแรม",
        "expected_answer": "สวัสดีค่ะ ยินดีต้อนรับสู่โรงแรม The Grand Horizon Hotel ทีม Front Desk พร้อมให้บริการ 24 ชั่วโมง มีอะไรให้ช่วยเหลือไหมคะ?",
        "expected_context": [],
        "expected_keywords": ["ยินดีต้อนรับ", "Grand Horizon", "Front Desk", "ช่วยเหลือ"],
        "language": Language.THAI,
        "category": Category.FAQ,
        "difficulty": Difficulty.EASY,
    },
    # === BOOKING INTENTS (for hybrid routing tests) ===
    {
        "id": "booking_en_01",
        "question": "I want to book a Deluxe room for next Friday",
        "expected_answer": "I can help you book a Deluxe Room. The Deluxe Room is 35 sqm at 3,500 THB per night, featuring a bathtub, work desk, and balcony. Could you please provide your check-out date and number of guests?",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["book", "Deluxe", "3,500", "35", "check-out"],
        "language": Language.ENGLISH,
        "category": Category.ROOM,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_th_01",
        "question": "อยากจองห้อง Deluxe ศุกร์หน้า",
        "expected_answer": "ยินดีช่วยจองห้อง Deluxe ค่ะ ห้อง Deluxe 35 ตร.ม. ราคา 3,500 บาท/คืน มีอ่างอาบน้ำ โต๊ะทำงาน และระเบียง ขอทราบวันเช็คเอาท์และจำนวนผู้เข้าพักค่ะ?",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["จอง", "Deluxe", "3,500", "35", "เช็คเอาท์"],
        "language": Language.THAI,
        "category": Category.ROOM,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_en_02",
        "question": "Can you cancel my reservation?",
        "expected_answer": "I can help with cancellation. Free cancellation is available more than 48 hours before check-in. Within 48 hours, 1 night charge applies. Could you please provide your reservation number or guest name?",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["cancel", "48 hours", "free", "reservation", "1 night"],
        "language": Language.ENGLISH,
        "category": Category.POLICY,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_th_02",
        "question": "ช่วยยกเลิกการจองได้ไหม?",
        "expected_answer": "ยินดีช่วยยกเลิกค่ะ ยกเลิกฟรีล่วงหน้ามากกว่า 48 ชม. ภายใน 48 ชม. คิดค่าห้อง 1 คืน ขอหมายเลขการจองหรือชื่อผู้จองค่ะ?",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["ยกเลิก", "48 ชม.", "ฟรี", "การจอง", "1 คืน"],
        "language": Language.THAI,
        "category": Category.POLICY,
        "difficulty": Difficulty.HARD,
    },
    # === COMPARISON QUESTIONS ===
    {
        "id": "compare_en_01",
        "question": "What's the difference between Deluxe and Suite?",
        "expected_answer": "Deluxe Room: 35 sqm, 3,500 THB, bathtub, work desk, balcony. Suite: 55 sqm, 5,500 THB, separate living area, kitchenette, premium minibar, butler service. Suite is 20 sqm larger with more amenities and butler service.",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["35", "55", "3,500", "5,500", "butler", "kitchenette"],
        "language": Language.ENGLISH,
        "category": Category.ROOM,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "compare_th_01",
        "question": "Deluxe กับ Suite ต่างกันยังไง?",
        "expected_answer": "Deluxe: 35 ตร.ม. 3,500 บาท มีอ่างอาบน้ำ โต๊ะทำงาน ระเบียง Suite: 55 ตร.ม. 5,500 บาท มีห้องนั่งเล่นแยก ครัวเล็ก มินิบาร์พรีเมียม บัตเลอร์ Suite ใหญ่กว่า 20 ตร.ม. มีสิ่งอำนวยความสะดวกและบัตเลอร์มากกว่า",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["35", "55", "3,500", "5,500", "บัตเลอร์", "ครัวเล็ก"],
        "language": Language.THAI,
        "category": Category.ROOM,
        "difficulty": Difficulty.HARD,
    },
    # === SPECIFIC TIME QUESTIONS ===
    {
        "id": "time_en_01",
        "question": "When is happy hour at the bar?",
        "expected_answer": "Happy Hour at the Lobby Bar is from 5:00 PM to 7:00 PM daily. Enjoy 50% off selected cocktails and wines. The bar is open from 11:00 AM to midnight.",
        "expected_context": ["dining_services.md"],
        "expected_keywords": ["5:00", "7:00", "50%", "cocktails", "midnight"],
        "language": Language.ENGLISH,
        "category": Category.DINING,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "time_th_01",
        "question": "บาร์มี Happy Hour ตอนไหน?",
        "expected_answer": "Happy Hour ที่ Lobby Bar 17:00-19:00 น. ทุกวัน ลดราคา 50% เครื่องดื่มค็อกเทลและไวน์ที่เลือก บาร์เปิด 11:00-24:00 น.",
        "expected_context": ["dining_services.md"],
        "expected_keywords": ["17:00", "19:00", "50%", "ค็อกเทล", "24:00"],
        "language": Language.THAI,
        "category": Category.DINING,
        "difficulty": Difficulty.MEDIUM,
    },
    # === PAYMENT/BILLING QUESTIONS ===
    {
        "id": "payment_en_01",
        "question": "What payment methods do you accept?",
        "expected_answer": "We accept cash (THB only), credit cards (Visa, Mastercard, AMEX, JCB), debit cards, and mobile payments (PromptPay, TrueMoney). For bills over 10,000 THB, we also accept bank transfer.",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["Visa", "Mastercard", "PromptPay", "cash", "bank transfer"],
        "language": Language.ENGLISH,
        "category": Category.POLICY,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "payment_th_01",
        "question": "รับชำระเงินวิธีไหนบ้าง?",
        "expected_answer": "รับเงินสด (บาทเท่านั้น) บัตรเครดิต (Visa, Mastercard, AMEX, JCB) บัตรเดบิต และชำระผ่านมือถือ (พร้อมเพย์, ทรูมันนี่) บิลมากกว่า 10,000 บาทรับโอนธนาคาร",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["Visa", "Mastercard", "พร้อมเพย์", "เงินสด", "โอน"],
        "language": Language.THAI,
        "category": Category.POLICY,
        "difficulty": Difficulty.MEDIUM,
    },
    # === BOOKING CRUD OPERATIONS ===
    # CREATE - New Reservation
    # NOTE: Room prices are dynamic and can vary based on availability/demand
    {
        "id": "booking_create_en_01",
        "question": "I'd like to make a reservation for 2 adults from March 15 to March 18",
        "expected_answer": "I'll check available rooms for March 15-18 (3 nights) for 2 adults. Here are the available options with current prices. Please select your preferred room and provide your email to proceed with the reservation.",
        "expected_context": [],
        "expected_keywords": ["available", "March", "15", "18", "room", "email"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_create_th_01",
        "question": "อยากจองห้องพักสำหรับ 2 คน วันที่ 15-18 มีนาคม",
        "expected_answer": "ตรวจสอบห้องว่างสำหรับวันที่ 15-18 มีนาคม (3 คืน) สำหรับ 2 ท่าน มีห้องว่างพร้อมราคาให้เลือก กรุณาเลือกห้องและแจ้งอีเมลเพื่อดำเนินการจอง",
        "expected_context": [],
        "expected_keywords": ["ห้องว่าง", "มีนาคม", "15", "18", "เลือก", "อีเมล"],
        "language": Language.THAI,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_create_en_02",
        "question": "Book a Suite for my anniversary weekend, I need a room with a view",
        "expected_answer": "I'd be happy to help you book a Suite for your anniversary! To check Suite availability with a view, please provide your check-in and check-out dates and your email address.",
        "expected_context": [],
        "expected_keywords": ["Suite", "anniversary", "view", "dates", "email"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    # READ - Check Reservation Status
    {
        "id": "booking_read_en_01",
        "question": "Can you check my reservation? My name is John Smith",
        "expected_answer": "I'll look up your reservation, Mr. Smith. Could you please provide your email address used for booking?",
        "expected_context": [],
        "expected_keywords": ["reservation", "email", "booking", "happy"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "booking_read_th_01",
        "question": "ช่วยเช็คการจองให้หน่อย ชื่อสมชาย ใจดี",
        "expected_answer": "ยินดีค่ะคุณสมชาย รบกวนขออีเมลที่ใช้จองค่ะ เพื่อค้นหาข้อมูลการจองของคุณ",
        "expected_context": [],
        "expected_keywords": ["สมชาย", "อีเมล", "การจอง", "ค่ะ"],
        "language": Language.THAI,
        "category": Category.BOOKING,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "booking_read_en_02",
        "question": "What's the status of booking confirmation BK-2024-001234?",
        "expected_answer": "I'll check the booking BK-2024-001234. If not found, please verify the confirmation number or provide email address.",
        "expected_context": [],
        "expected_keywords": ["BK-2024", "confirmation", "email", "booking"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.MEDIUM,
    },
    # UPDATE - Modify Reservation
    {
        "id": "booking_update_en_01",
        "question": "I need to change my check-in date from March 15 to March 17",
        "expected_answer": "I can help you change your check-in date from March 15 to March 17. Please provide your reservation ID or confirmation number.",
        "expected_context": [],
        "expected_keywords": ["change", "check-in", "March", "reservation", "confirmation"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_update_th_01",
        "question": "อยากเปลี่ยนวันเช็คอินจาก 15 มีนา เป็น 17 มีนา",
        "expected_answer": "ยินดีช่วยเปลี่ยนวันเช็คอินจาก 15 มีนาคม เป็น 17 มีนาคมค่ะ กรุณาแจ้งหมายเลขการจอง",
        "expected_context": [],
        "expected_keywords": ["เปลี่ยน", "มีนาคม", "หมายเลข", "การจอง"],
        "language": Language.THAI,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_update_en_02",
        "question": "Can I upgrade my Standard room to a Deluxe?",
        "expected_answer": "I'd be happy to help you upgrade from Standard to Deluxe. Please provide your reservation ID or confirmation number so I can check Deluxe availability for your dates and process the upgrade.",
        "expected_context": [],
        "expected_keywords": ["upgrade", "Standard", "Deluxe", "reservation", "confirmation"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_update_th_02",
        "question": "อยากอัพเกรดจากห้อง Standard เป็น Deluxe ได้ไหม?",
        "expected_answer": "ยินดีช่วยอัพเกรดจาก Standard เป็น Deluxe ค่ะ กรุณาแจ้งหมายเลขการจองหรือ Confirmation Number เพื่อตรวจสอบห้อง Deluxe ว่างและดำเนินการอัพเกรด",
        "expected_context": [],
        "expected_keywords": ["อัพเกรด", "Standard", "Deluxe", "หมายเลข", "การจอง"],
        "language": Language.THAI,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_update_en_03",
        "question": "I want to add an extra bed to my room",
        "expected_answer": "Extra beds are available at 800 THB per night. Maximum capacity varies by room: 1 extra bed for Standard/Deluxe, 2 for Suite, 3 for Penthouse. Baby cots are complimentary. Shall I add this to your reservation?",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["extra bed", "800", "maximum", "cot", "reservation"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "booking_update_th_03",
        "question": "อยากเพิ่มเตียงเสริมในห้อง",
        "expected_answer": "เตียงเสริม 800 บาท/คืน จำนวนสูงสุดตามห้อง: Standard/Deluxe 1 เตียง, Suite 2 เตียง, Penthouse 3 เตียง เปลเด็กฟรี ต้องการเพิ่มในการจองไหมคะ?",
        "expected_context": ["room_types.md"],
        "expected_keywords": ["เตียงเสริม", "800", "สูงสุด", "เปล", "ฟรี"],
        "language": Language.THAI,
        "category": Category.BOOKING,
        "difficulty": Difficulty.MEDIUM,
    },
    # DELETE - Cancel Reservation
    {
        "id": "booking_delete_en_01",
        "question": "I need to cancel my booking for next week",
        "expected_answer": "I'll help you cancel your booking. Please note our cancellation policy: Free cancellation more than 48 hours before check-in. Within 48 hours, 1 night charge applies. May I have your confirmation number to proceed?",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["cancel", "48 hours", "free", "1 night", "confirmation"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_delete_th_01",
        "question": "ต้องการยกเลิกการจองสัปดาห์หน้า",
        "expected_answer": "ยินดีช่วยยกเลิกการจองค่ะ นโยบายยกเลิก: ยกเลิกฟรีล่วงหน้ามากกว่า 48 ชม. ภายใน 48 ชม. คิดค่าห้อง 1 คืน ขอหมายเลขยืนยันการจองเพื่อดำเนินการค่ะ",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["ยกเลิก", "48 ชม.", "ฟรี", "1 คืน", "หมายเลข"],
        "language": Language.THAI,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_delete_en_02",
        "question": "Cancel reservation BK-2024-005678, I won't be able to make it",
        "expected_answer": "I'll process the cancellation for BK-2024-005678. Checking your check-in date to apply the correct policy. If more than 48 hours away, cancellation is free. I'll confirm the refund amount once processed.",
        "expected_context": ["policies_rules.md"],
        "expected_keywords": ["cancel", "BK-2024", "48 hours", "free", "refund"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    # LIST - View All Bookings
    {
        "id": "booking_list_en_01",
        "question": "Can you show me all my reservations under this phone number?",
        "expected_answer": "I'll search for all reservations linked to your phone number. Please provide the number you used for booking. I'll show you upcoming and past reservations with their status.",
        "expected_context": [],
        "expected_keywords": ["reservations", "phone", "upcoming", "past", "status"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.MEDIUM,
    },
    {
        "id": "booking_list_th_01",
        "question": "ดูการจองทั้งหมดของผม เบอร์โทร 081-234-5678",
        "expected_answer": "ค้นหาการจองทั้งหมดที่ผูกกับเบอร์ 081-234-5678 ค่ะ จะแสดงการจองที่กำลังจะมาถึงและที่ผ่านมาพร้อมสถานะ",
        "expected_context": [],
        "expected_keywords": ["การจอง", "เบอร์", "กำลังจะมา", "สถานะ"],
        "language": Language.THAI,
        "category": Category.BOOKING,
        "difficulty": Difficulty.MEDIUM,
    },
    # === MULTI-TURN BOOKING CONVERSATIONS ===
    # NOTE: Prices are dynamic - focus on behavior (handling multiple requests)
    {
        "id": "booking_multiturn_en_01",
        "question": "I booked a Standard room but now I want Suite instead, and also add airport transfer",
        "expected_answer": "I'll help with both requests: room upgrade to Suite and airport transfer. Please provide your booking confirmation number so I can check Suite availability and arrange the transfer.",
        "expected_context": [],
        "expected_keywords": ["upgrade", "Suite", "airport", "transfer", "confirmation"],
        "language": Language.ENGLISH,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
    {
        "id": "booking_multiturn_th_01",
        "question": "จองห้อง Standard ไว้แต่อยากเปลี่ยนเป็น Suite และเพิ่มรถรับสนามบินด้วย",
        "expected_answer": "ยินดีช่วยทั้ง 2 เรื่องค่ะ: อัพเกรดเป็น Suite และรถรับสนามบิน กรุณาแจ้งหมายเลขการจองเพื่อตรวจสอบห้อง Suite ว่างและจัดรถรับส่ง",
        "expected_context": [],
        "expected_keywords": ["อัพเกรด", "Suite", "สนามบิน", "รถรับ", "หมายเลข"],
        "language": Language.THAI,
        "category": Category.BOOKING,
        "difficulty": Difficulty.HARD,
    },
]


def generate_golden_dataset(
    hotel_data_dir: str = "data/hotel",
    output_path: str = "scripts/eval/dataset.json",
) -> GoldenDataset:
    """
    Generate golden dataset from predefined Q&A pairs.

    The Q&A pairs are manually curated from hotel markdown files
    to ensure accuracy for evaluation.

    Args:
        hotel_data_dir: Path to hotel data directory (for validation)
        output_path: Path to save generated dataset

    Returns:
        GoldenDataset with all Q&A pairs
    """
    logger.info(f"Generating golden dataset from {hotel_data_dir}")

    # Validate source files exist
    hotel_path = Path(hotel_data_dir)
    if hotel_path.exists():
        source_files = set()
        for pair_data in GOLDEN_QA_PAIRS:
            source_files.update(pair_data["expected_context"])

        for source in source_files:
            source_path = hotel_path / source
            if not source_path.exists():
                logger.warning(f"Source file not found: {source_path}")

    # Create Q&A pairs
    pairs = []
    for pair_data in GOLDEN_QA_PAIRS:
        pair = GoldenQAPair(
            id=pair_data["id"],
            question=pair_data["question"],
            expected_answer=pair_data["expected_answer"],
            expected_context=pair_data["expected_context"],
            expected_keywords=pair_data["expected_keywords"],
            language=pair_data["language"],
            category=pair_data["category"],
            difficulty=pair_data.get("difficulty", Difficulty.MEDIUM),
        )
        pairs.append(pair)

    # Create dataset
    dataset = GoldenDataset(
        version="1.0.0",
        generated_at=datetime.now().isoformat(),
        total_pairs=len(pairs),
        pairs=pairs,
    )

    # Save to file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(dataset.model_dump(), f, ensure_ascii=False, indent=2)

    logger.info(f"Generated {len(pairs)} Q&A pairs, saved to {output_path}")
    return dataset


def load_golden_dataset(path: str = "scripts/eval/dataset.json") -> GoldenDataset:
    """
    Load golden dataset from JSON file.

    Args:
        path: Path to dataset JSON file

    Returns:
        GoldenDataset instance
    """
    dataset_path = Path(path)

    if not dataset_path.exists():
        logger.warning(f"Dataset not found at {path}, generating new one...")
        return generate_golden_dataset(output_path=path)

    with open(dataset_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    dataset = GoldenDataset(**data)
    logger.info(f"Loaded {dataset.total_pairs} Q&A pairs from {path}")
    return dataset


def get_dataset_stats(dataset: GoldenDataset) -> dict:
    """
    Get statistics about the dataset.

    Args:
        dataset: GoldenDataset instance

    Returns:
        Dictionary with statistics
    """
    stats = {
        "total": dataset.total_pairs,
        "by_language": {},
        "by_category": {},
        "by_difficulty": {},
    }

    for pair in dataset.pairs:
        # Count by language
        lang = pair.language.value
        stats["by_language"][lang] = stats["by_language"].get(lang, 0) + 1

        # Count by category
        cat = pair.category.value
        stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1

        # Count by difficulty
        diff = pair.difficulty.value
        stats["by_difficulty"][diff] = stats["by_difficulty"].get(diff, 0) + 1

    return stats


if __name__ == "__main__":
    # Generate dataset when run directly
    logging.basicConfig(level=logging.INFO)
    dataset = generate_golden_dataset()
    stats = get_dataset_stats(dataset)
    print(f"\nDataset Statistics:")
    print(f"  Total pairs: {stats['total']}")
    print(f"  By language: {stats['by_language']}")
    print(f"  By category: {stats['by_category']}")
    print(f"  By difficulty: {stats['by_difficulty']}")
