#!/usr/bin/env python3
# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Generate Mock Hotel Knowledge Documents

Creates comprehensive bilingual (Thai/English) hotel information documents
for testing the RAG system accuracy.

Usage:
    python scripts/generate_hotel_knowledge.py

Output:
    Creates markdown files in data/hotel/ directory
"""

import os
from pathlib import Path

# Output directory
OUTPUT_DIR = Path("data/hotel")


# ============================================================================
# HOTEL KNOWLEDGE CONTENT (BILINGUAL THAI/ENGLISH)
# ============================================================================

HOTEL_FAQ = """# Hotel Frequently Asked Questions / คำถามที่พบบ่อย

## Check-in & Check-out / เช็คอิน-เช็คเอาท์

**Q: What time is check-in? / เช็คอินได้ตอนกี่โมง?**
A: Check-in time is 2:00 PM (14:00). Early check-in may be available upon request subject to room availability. There is no charge for early check-in if rooms are available.
เช็คอินได้ตั้งแต่ 14:00 น. สามารถขอเช็คอินก่อนเวลาได้หากห้องว่าง ไม่มีค่าใช้จ่ายเพิ่มเติมหากห้องว่าง

**Q: What time is check-out? / เช็คเอาท์ตอนกี่โมง?**
A: Check-out time is 12:00 PM (noon). Late check-out is available for 500 THB per hour until 6:00 PM. Please contact the front desk to arrange late check-out.
เช็คเอาท์ภายใน 12:00 น. (เที่ยง) สามารถขอเช็คเอาท์ล่าช้าได้ 500 บาทต่อชั่วโมง จนถึง 18:00 น. กรุณาติดต่อแผนกต้อนรับล่วงหน้า

**Q: Can I store luggage before check-in or after check-out? / ฝากกระเป๋าได้ไหม?**
A: Yes, complimentary luggage storage is available at the concierge desk. We can store your luggage before check-in and after check-out at no additional charge.
ได้ค่ะ/ครับ ฝากกระเป๋าได้ฟรีที่แผนกต้อนรับ ทั้งก่อนเช็คอินและหลังเช็คเอาท์

**Q: Is express check-out available? / มีบริการเช็คเอาท์ด่วนไหม?**
A: Yes, express check-out is available. Simply drop your key card in the express check-out box at the front desk and your receipt will be emailed to you.
มีค่ะ/ครับ เพียงหย่อนคีย์การ์ดในกล่อง Express Check-out ที่เคาน์เตอร์ ใบเสร็จจะส่งไปทางอีเมล

## Payment & Billing / การชำระเงิน

**Q: What payment methods do you accept? / รับชำระเงินด้วยวิธีใดบ้าง?**
A: We accept Visa, MasterCard, American Express, JCB, and UnionPay credit cards. Cash payments are accepted in Thai Baht only. We do not accept personal checks.
รับบัตรเครดิต Visa, MasterCard, American Express, JCB และ UnionPay รับเงินสดเฉพาะเงินบาท ไม่รับเช็คส่วนบุคคล

**Q: Is a deposit required? / ต้องวางมัดจำไหม?**
A: Yes, a credit card authorization or cash deposit of 2,000 THB per night is required at check-in for incidentals.
ต้องค่ะ/ครับ วางมัดจำบัตรเครดิตหรือเงินสด 2,000 บาทต่อคืน สำหรับค่าใช้จ่ายเพิ่มเติม

## General Information / ข้อมูลทั่วไป

**Q: What is the hotel address? / ที่อยู่โรงแรม?**
A: The Grand Horizon Hotel, 123 Sukhumvit Road, Khlong Toei, Bangkok 10110, Thailand.
โรงแรม เดอะ แกรนด์ ฮอไรซัน 123 ถนนสุขุมวิท แขวงคลองเตย กรุงเทพฯ 10110

**Q: What is the hotel phone number? / เบอร์โทรศัพท์โรงแรม?**
A: Main line: +66 2 123 4567. Front Desk: Extension 0. Room Service: Extension 1.
โทรศัพท์หลัก: +66 2 123 4567 แผนกต้อนรับ: กด 0 รูมเซอร์วิส: กด 1

**Q: Is the hotel near public transportation? / ใกล้รถไฟฟ้าไหม?**
A: Yes, we are a 5-minute walk from Asok BTS Station and Sukhumvit MRT Station.
ใช่ค่ะ/ครับ เดินจากสถานี BTS อโศกและ MRT สุขุมวิทประมาณ 5 นาที
"""

DINING_SERVICES = """# Dining Services / บริการอาหาร

## The Grand Dining Room - Breakfast / ห้องอาหารเช้า

**Location:** 1st Floor, near the main lobby
**Hours:** 6:30 AM - 10:30 AM daily (every day including holidays)
**Price:** Complimentary for all in-house guests

สถานที่: ชั้น 1 ใกล้ล็อบบี้หลัก
เวลา: 06:30 - 10:30 น. ทุกวัน (รวมวันหยุด)
ราคา: ฟรีสำหรับผู้เข้าพักทุกท่าน

**Breakfast Menu Highlights:**
- International buffet with over 50 dishes
- Thai breakfast station: Jok (rice porridge), Khao Tom (rice soup), Pad Thai, Thai omelette
- Western station: Made-to-order eggs, pancakes, waffles, bacon, sausages
- Japanese station: Miso soup, grilled fish, rice, pickles
- Fresh tropical fruits: Mango, papaya, dragon fruit, watermelon, pineapple
- Bakery: Fresh pastries, croissants, Danish, breads
- Beverages: Fresh juices, coffee, tea, smoothies
- Vegetarian, vegan, halal, and gluten-free options available upon request

## Skyline Restaurant - All-Day Dining / ร้านอาหารสกายไลน์

**Location:** 25th Floor with panoramic city views
**Hours:** 11:00 AM - 11:00 PM
**Cuisine:** International and Thai fusion
**Dress Code:** Smart casual (no shorts or sandals for dinner)

สถานที่: ชั้น 25 วิวพาโนรามาเมือง
เวลา: 11:00 - 23:00 น.
อาหาร: นานาชาติและไทยฟิวชัน
การแต่งกาย: Smart casual (ไม่รับกางเกงขาสั้นหรือรองเท้าแตะตอนมื้อเย็น)

**Popular Dishes:**
- Tom Yum Goong (spicy shrimp soup) - 380 THB
- Pad Thai with prawns - 320 THB
- Green curry with chicken - 350 THB
- Grilled ribeye steak - 1,200 THB
- Fresh seafood platter - 1,800 THB

## Room Service / รูมเซอร์วิส

**Available:** 24 hours a day, 7 days a week
**Delivery Time:** 30-45 minutes
**Minimum Order:** None
**Service Charge:** 100 THB per order

เปิดให้บริการ: 24 ชั่วโมง 7 วัน
เวลาจัดส่ง: 30-45 นาที
ขั้นต่ำ: ไม่มี
ค่าบริการ: 100 บาทต่อออเดอร์

**How to Order:**
- Dial 0 on your room phone or press "Room Service" button
- Browse the in-room dining menu in your room
- Place orders through the hotel app

โทร: กด 0 หรือกดปุ่ม "Room Service" บนโทรศัพท์ในห้อง
ดูเมนูจากสมุดเมนูในห้อง หรือสั่งผ่านแอปโรงแรม

## Pool Bar / พูลบาร์

**Location:** 5th Floor Pool Deck
**Hours:** 10:00 AM - 8:00 PM
**Offerings:** Light snacks, salads, sandwiches, cocktails, fresh juices

สถานที่: ดาดฟ้าสระว่ายน้ำ ชั้น 5
เวลา: 10:00 - 20:00 น.
เมนู: ของว่าง สลัด แซนวิช ค็อกเทล น้ำผลไม้สด
"""

SPA_WELLNESS = """# Serenity Spa & Wellness Center / สปาและศูนย์เวลเนส

## Operating Hours / เวลาเปิดให้บริการ

**Daily:** 10:00 AM - 10:00 PM
**Last Booking:** 8:30 PM
**Location:** 3rd Floor

เปิดทุกวัน: 10:00 - 22:00 น.
รับจองคิวสุดท้าย: 20:30 น.
สถานที่: ชั้น 3

## Reservations / การจอง

Advance booking is highly recommended, especially on weekends.
แนะนำให้จองล่วงหน้า โดยเฉพาะวันหยุดสุดสัปดาห์

**How to Book:**
- Call extension 303 from your room
- Visit the spa reception on the 3rd floor
- Book through the hotel app

โทร: กด 303 จากห้องพัก
เดินมาจองที่สปาชั้น 3
จองผ่านแอปโรงแรม

## Massage Treatments / บริการนวด

### Thai Traditional Massage / นวดแผนไทยโบราณ
Ancient Thai healing art combining acupressure, stretching, and energy work.
ศาสตร์การนวดไทยโบราณผสมผสานการกดจุด การยืดเหยียด และการปรับพลังงาน

- 60 minutes: 1,500 THB
- 90 minutes: 2,000 THB
- 120 minutes: 2,500 THB

### Aromatherapy Oil Massage / นวดน้ำมันอโรมา
Relaxing massage with essential oils of your choice.
นวดผ่อนคลายด้วยน้ำมันหอมระเหยตามชอบ

Available Oils / น้ำมันที่เลือกได้:
- Lavender (Relaxation) / ลาเวนเดอร์ (ผ่อนคลาย)
- Lemongrass (Energizing) / ตะไคร้ (กระตุ้นพลังงาน)
- Eucalyptus (Refreshing) / ยูคาลิปตัส (สดชื่น)
- Thai Jasmine (Romance) / มะลิไทย (โรแมนติก)

- 60 minutes: 1,800 THB
- 90 minutes: 2,500 THB

### Deep Tissue Massage / นวดกดจุดลึก
Firm pressure massage targeting muscle tension and knots.
นวดแรงเน้นคลายกล้ามเนื้อที่ตึงและปมกล้ามเนื้อ

- 60 minutes: 2,000 THB
- 90 minutes: 2,800 THB

### Foot Reflexology / นวดเท้าสะท้อนจุด
Traditional foot massage stimulating reflex points.
นวดเท้าแบบดั้งเดิมกระตุ้นจุดสะท้อน

- 45 minutes: 900 THB
- 60 minutes: 1,200 THB

## Signature Packages / แพ็คเกจพิเศษ

### Royal Thai Experience / แพ็คเกจราชาไทย
Duration: 3 hours / ระยะเวลา: 3 ชั่วโมง
Price: 5,500 THB

Includes:
- Thai herbal steam (30 min)
- Thai traditional massage (90 min)
- Thai facial treatment (60 min)
- Herbal tea and light refreshments

รวม: อบไอน้ำสมุนไพร + นวดแผนไทย + ทรีตเมนต์หน้า + ชาสมุนไพรและของว่าง

### Couples Retreat / แพ็คเกจคู่รัก
Duration: 2 hours / ระยะเวลา: 2 ชั่วโมง
Price: 6,000 THB (for 2 persons)

Private couple's suite with:
- Champagne welcome
- Aromatherapy massage for two
- Chocolate strawberries

ห้องส่วนตัวสำหรับคู่รัก: แชมเปญต้อนรับ + นวดอโรมาสำหรับ 2 ท่าน + สตรอว์เบอร์รี่ช็อคโกแลต

## Facilities / สิ่งอำนวยความสะดวก

- Steam room (wet and dry)
- Sauna
- Jacuzzi
- Relaxation lounge
- Private treatment rooms

ห้องอบไอน้ำ (แบบเปียกและแห้ง) ซาวน่า จากุซซี่ ห้องพักผ่อน ห้องทรีตเมนต์ส่วนตัว
"""

FACILITIES_AMENITIES = """# Hotel Facilities & Amenities / สิ่งอำนวยความสะดวก

## Swimming Pool / สระว่ายน้ำ

**Location:** 5th Floor Rooftop
**Hours:** 6:00 AM - 9:00 PM daily
**Pool Size:** 25 meters x 10 meters
**Depth:** 1.2 meters - 1.8 meters

สถานที่: ดาดฟ้าชั้น 5
เวลา: 06:00 - 21:00 น. ทุกวัน
ขนาดสระ: 25 x 10 เมตร
ความลึก: 1.2 - 1.8 เมตร

**Amenities:**
- Pool towels available poolside (free)
- Sun loungers and umbrellas
- Children's pool (0.5m depth, separate area)
- Changing rooms with showers and lockers
- Pool attendant on duty

สิ่งอำนวยความสะดวก:
- ผ้าเช็ดตัวฟรีที่สระ
- เก้าอี้อาบแดดและร่ม
- สระเด็ก (ลึก 0.5 เมตร แยกพื้นที่)
- ห้องเปลี่ยนเสื้อผ้าพร้อมฝักบัวและล็อกเกอร์
- มีเจ้าหน้าที่ดูแลสระ

**Pool Rules:**
- No diving
- Children under 12 must be accompanied by adult
- No glass containers in pool area
- Showering required before entering pool

## Fitness Center / ฟิตเนสเซ็นเตอร์

**Location:** 4th Floor
**Hours:** 24 hours (keycard access)
**Access:** Complimentary for all guests

สถานที่: ชั้น 4
เวลา: 24 ชั่วโมง (เข้าด้วยคีย์การ์ด)
การใช้บริการ: ฟรีสำหรับผู้เข้าพัก

**Equipment:**
- Treadmills (8 units)
- Elliptical machines (4 units)
- Stationary bikes (4 units)
- Free weights (dumbbells 2-50 kg)
- Weight machines
- Yoga mats and exercise balls
- Stretching area

**Personal Training:**
- Available by appointment
- Price: 1,000 THB per session (1 hour)
- Contact: Dial 404 from your room

เทรนเนอร์ส่วนตัว: 1,000 บาทต่อครั้ง (1 ชั่วโมง) โทรจองที่ 404

## Business Center / ศูนย์ธุรกิจ

**Location:** 2nd Floor
**Hours:** 8:00 AM - 8:00 PM daily

สถานที่: ชั้น 2
เวลา: 08:00 - 20:00 น. ทุกวัน

**Services:**
- Printing: 5 THB per page (B&W), 15 THB (color)
- Scanning: Free
- Fax: 20 THB per page (domestic), 50 THB (international)
- Computer workstations
- Meeting rooms (advance booking required)

บริการ: พิมพ์ 5 บาท/หน้า (ขาวดำ) 15 บาท (สี) สแกนฟรี แฟกซ์ 20 บาท (ในประเทศ) 50 บาท (ต่างประเทศ)

## WiFi / อินเทอร์เน็ตไร้สาย

**Network Name:** HotelGuest
**Password:** HOTEL2024GUEST
**Speed:** 100 Mbps
**Coverage:** Throughout the entire hotel
**Price:** Complimentary for all guests

ชื่อเครือข่าย: HotelGuest
รหัสผ่าน: HOTEL2024GUEST
ความเร็ว: 100 Mbps
ครอบคลุม: ทั่วทั้งโรงแรม
ราคา: ฟรีสำหรับผู้เข้าพักทุกท่าน

**High-Speed Premium WiFi:**
- Speed: 500 Mbps
- Price: 300 THB per day
- Contact front desk to upgrade

WiFi ความเร็วสูงพรีเมียม: 500 Mbps ราคา 300 บาท/วัน ติดต่อแผนกต้อนรับ

## Concierge Services / บริการ Concierge

**Location:** Main Lobby
**Hours:** 24 hours

สถานที่: ล็อบบี้หลัก
เวลา: 24 ชั่วโมง

**Services Available:**
- Tour bookings and recommendations
- Restaurant reservations
- Airport transfer arrangements
- Ticket purchases (shows, attractions)
- Flower and gift arrangements
- Laundry and dry cleaning
- Currency exchange
- Postal services

บริการ: จองทัวร์ จองร้านอาหาร รถรับส่งสนามบิน ซื้อตั๋ว ส่งดอกไม้ ซักรีด แลกเงิน ไปรษณีย์

## Parking / ที่จอดรถ

**Location:** Basement Level 1-3
**Hours:** 24 hours
**Price:** 100 THB per entry for non-guests, complimentary for in-house guests
**Valet Parking:** Available, 200 THB

ที่ตั้ง: ชั้นใต้ดิน 1-3
เวลา: 24 ชั่วโมง
ราคา: 100 บาท/ครั้ง สำหรับบุคคลภายนอก, ฟรีสำหรับผู้เข้าพัก
Valet: 200 บาท
"""

POLICIES_RULES = """# Hotel Policies & Rules / นโยบายและกฎระเบียบ

## Cancellation Policy / นโยบายยกเลิก

**Free Cancellation:** More than 48 hours before check-in date
**Within 48 hours:** 1 night charge will apply
**No-Show:** Full stay charge will apply
**Early Departure:** No refund for unused nights

ยกเลิกฟรี: ล่วงหน้ามากกว่า 48 ชั่วโมงก่อนเช็คอิน
ภายใน 48 ชั่วโมง: คิดค่าห้อง 1 คืน
ไม่มาเข้าพัก: คิดค่าห้องทั้งหมด
ออกก่อนกำหนด: ไม่คืนเงินคืนที่ไม่ได้ใช้

**How to Cancel:**
- Online through our website
- Call: +66 2 123 4567
- Email: reservations@grandparadise.com

วิธียกเลิก: ผ่านเว็บไซต์ โทร +66 2 123 4567 หรืออีเมล reservations@grandparadise.com

## Pet Policy / นโยบายสัตว์เลี้ยง

**Pets Allowed:** Small pets only (under 5 kg / 11 lbs)
**Pet Fee:** 500 THB per night
**Pet Deposit:** 2,000 THB (refundable)
**Pet-Friendly Rooms:** Limited availability, please request when booking

อนุญาตสัตว์เลี้ยง: เฉพาะสัตว์เลี้ยงขนาดเล็ก (น้ำหนักไม่เกิน 5 กก.)
ค่าสัตว์เลี้ยง: 500 บาท/คืน
เงินประกัน: 2,000 บาท (คืนให้เมื่อเช็คเอาท์)
ห้องรับสัตว์เลี้ยง: มีจำกัด กรุณาแจ้งเมื่อจอง

**Pet Rules:**
- Pets must be leashed in public areas
- Pets not allowed in restaurants, spa, pool, or fitness center
- Do not leave pets unattended in room
- Guests are responsible for pet damage

กฎสัตว์เลี้ยง: ต้องใส่สายจูงในพื้นที่สาธารณะ ห้ามนำเข้าร้านอาหาร สปา สระว่ายน้ำ ฟิตเนส ห้ามทิ้งไว้ในห้องตามลำพัง ผู้เข้าพักรับผิดชอบความเสียหาย

## Smoking Policy / นโยบายการสูบบุหรี่

**Hotel Policy:** 100% Non-smoking property
**Smoking Areas:** Designated outdoor area on ground floor terrace only
**Violation Fee:** 5,000 THB cleaning fee for smoking in room

นโยบาย: โรงแรมปลอดบุหรี่ 100%
พื้นที่สูบบุหรี่: เฉพาะบริเวณระเบียงชั้น 1 ที่กำหนดเท่านั้น
ค่าปรับ: 5,000 บาท หากสูบบุหรี่ในห้องพัก

## Quiet Hours / เวลาสงบ

**Quiet Hours:** 10:00 PM - 8:00 AM
Please maintain low noise levels during these hours.
Excessive noise complaints may result in a warning or removal from the hotel.

เวลาสงบ: 22:00 - 08:00 น.
กรุณารักษาความสงบในช่วงเวลาดังกล่าว

## Damage Policy / นโยบายความเสียหาย

Guests are responsible for any damage caused to hotel property during their stay.
Damage charges will be applied to the credit card on file.

ผู้เข้าพักรับผิดชอบความเสียหายที่เกิดกับทรัพย์สินของโรงแรม
ค่าเสียหายจะเรียกเก็บจากบัตรเครดิตที่ลงทะเบียนไว้

## Children Policy / นโยบายเด็ก

- Children under 12 stay free when sharing existing bedding with parents
- Extra bed for children: 500 THB per night
- Babysitting service available: 400 THB per hour (24-hour advance notice required)
- Kids club: Available for ages 4-12, daily 9:00 AM - 5:00 PM, complimentary

เด็กอายุต่ำกว่า 12 ปี พักฟรีเมื่อใช้เตียงเดิม
เตียงเสริมเด็ก: 500 บาท/คืน
บริการเลี้ยงเด็ก: 400 บาท/ชั่วโมง (แจ้งล่วงหน้า 24 ชั่วโมง)
Kids Club: สำหรับเด็ก 4-12 ปี เปิด 09:00-17:00 น. ฟรี

## Lost and Found / ของหาย-ของสูญหาย

Items found will be kept for 90 days.
Contact the front desk or email: lostandfound@grandparadise.com

ของที่พบจะเก็บรักษาไว้ 90 วัน
ติดต่อแผนกต้อนรับหรืออีเมล lostandfound@grandparadise.com
"""

ROOM_GUIDE = """# Room Guide / คู่มือห้องพัก

## Room Types / ประเภทห้อง

### Standard Room / ห้องสแตนดาร์ด
**Size:** 32 sqm
**Price:** 2,500 THB per night
**Max Guests:** 2 adults
**Bed:** 1 King or 2 Twin beds

ขนาด: 32 ตร.ม.
ราคา: 2,500 บาท/คืน
รองรับ: 2 ท่าน
เตียง: คิงไซส์ 1 เตียง หรือ เตียงเดี่ยว 2 เตียง

**Amenities:**
- City view
- 43" LED TV with cable channels
- Free WiFi
- Mini bar
- In-room safe
- Coffee/tea making facilities
- Bathtub and shower
- Complimentary toiletries
- Hairdryer
- Iron and ironing board
- Air conditioning

### Deluxe Room / ห้องดีลักซ์
**Size:** 45 sqm
**Price:** 4,500 THB per night
**Max Guests:** 2 adults + 1 child
**Bed:** 1 King bed

ขนาด: 45 ตร.ม.
ราคา: 4,500 บาท/คืน
รองรับ: 2 ผู้ใหญ่ + 1 เด็ก
เตียง: คิงไซส์ 1 เตียง

**Additional Amenities:**
- Partial city view
- Larger bathroom with separate shower and bathtub
- Bathrobe and slippers
- Nespresso coffee machine
- Daily newspaper
- Turndown service

### Suite / ห้องสวีท
**Size:** 72 sqm
**Price:** 8,500 THB per night
**Max Guests:** 4 adults
**Bed:** 1 King bed + sofa bed

ขนาด: 72 ตร.ม.
ราคา: 8,500 บาท/คืน
รองรับ: 4 ท่าน
เตียง: คิงไซส์ 1 เตียง + โซฟาเบด

**Additional Amenities:**
- Panoramic city view
- Separate living room
- Dining area
- Kitchenette with microwave
- 55" LED TV
- Premium toiletries (L'Occitane)
- Executive lounge access
- Priority restaurant reservations

### Penthouse / ห้องเพนท์เฮาส์
**Size:** 150 sqm
**Price:** 25,000 THB per night
**Max Guests:** 6 adults
**Bed:** 2 King beds

ขนาด: 150 ตร.ม.
ราคา: 25,000 บาท/คืน
รองรับ: 6 ท่าน
เตียง: คิงไซส์ 2 เตียง

**Additional Amenities:**
- Private rooftop terrace
- Private jacuzzi
- Full kitchen
- 65" OLED TV
- Bose sound system
- Personal butler service
- Complimentary airport transfer
- Complimentary spa treatment (1 hour)
- Complimentary minibar

## In-Room Amenities / สิ่งอำนวยความสะดวกในห้อง

### Television / โทรทัศน์
- Over 100 channels including international news, movies, and sports
- Chromecast available for streaming
- Pay-per-view movies available

### Mini Bar / มินิบาร์
- Restocked daily
- Prices listed in mini bar menu
- Complimentary water bottles (2 per day)

น้ำเปล่าฟรี 2 ขวด/วัน

### Room Safe / ตู้เซฟ
- Electronic safe in wardrobe
- Fits laptop up to 15"
- Instructions inside safe door

### Air Conditioning / แอร์
- Individual climate control
- Temperature range: 18-28°C
- Controls on bedside panel

### Room Service / รูมเซอร์วิส
- Available 24 hours
- Dial 0 or press Room Service on phone
- Menu in room compendium

## Housekeeping / แม่บ้าน

**Daily Cleaning:** 9:00 AM - 4:00 PM
Use "Make Up Room" sign for service
Use "Do Not Disturb" sign for privacy

ทำความสะอาดประจำวัน: 09:00 - 16:00 น.
แขวนป้าย "Make Up Room" หากต้องการให้ทำความสะอาด
แขวนป้าย "Do Not Disturb" หากต้องการความเป็นส่วนตัว

**Extra Items Available (complimentary):**
- Extra towels
- Extra pillows (soft/firm)
- Extra blankets
- Dental kit
- Shaving kit
- Sewing kit
- Shower cap

ของเพิ่มเติม (ฟรี): ผ้าเช็ดตัว หมอน ผ้าห่ม ชุดแปรงสีฟัน ชุดโกนหนวด ชุดเย็บผ้า หมวกอาบน้ำ
"""

LOCAL_ATTRACTIONS = """# Local Attractions & Transportation / สถานที่ท่องเที่ยวและการเดินทาง

## Nearby Attractions / สถานที่ใกล้เคียง

### Within Walking Distance (5-15 minutes) / ระยะเดิน 5-15 นาที

**Terminal 21 Shopping Mall** - 5 min walk
World-themed shopping mall with restaurants and cinema
ห้างสรรพสินค้าธีมทั่วโลก มีร้านอาหารและโรงภาพยนตร์

**Emquartier & Emporium** - 10 min walk
Luxury shopping and dining destination
แหล่งช้อปปิ้งและร้านอาหารระดับหรู

**Benchasiri Park** - 15 min walk
Green oasis in the city, perfect for jogging
สวนสาธารณะกลางเมือง เหมาะสำหรับวิ่ง

### Popular Attractions / สถานที่ท่องเที่ยวยอดนิยม

**Grand Palace & Wat Phra Kaew** - 30 min by taxi
Thailand's most sacred temple and former royal residence
วัดพระแก้วและพระบรมมหาราชวัง
Hours: 8:30 AM - 3:30 PM | Entrance: 500 THB

**Wat Arun (Temple of Dawn)** - 35 min by taxi
Iconic riverside temple with stunning architecture
วัดอรุณราชวราราม
Hours: 8:00 AM - 6:00 PM | Entrance: 100 THB

**Chatuchak Weekend Market** - 20 min by BTS
One of the world's largest outdoor markets
ตลาดนัดจตุจักร
Hours: Sat-Sun 9:00 AM - 6:00 PM | Free entrance

**Khao San Road** - 25 min by taxi
Famous backpacker street with nightlife
ถนนข้าวสาร
Best visited in the evening

## Transportation / การเดินทาง

### BTS Skytrain / รถไฟฟ้า BTS
**Nearest Station:** Asok (5 min walk)
**Hours:** 6:00 AM - 12:00 midnight
**Single Trip:** 16-59 THB depending on distance
**Day Pass:** 140 THB (unlimited rides)

สถานีใกล้สุด: อโศก (เดิน 5 นาที)
เวลา: 06:00 - 24:00 น.
เที่ยวเดียว: 16-59 บาท
บัตรวัน: 140 บาท

### MRT Subway / รถไฟฟ้าใต้ดิน MRT
**Nearest Station:** Sukhumvit (5 min walk, connected to Asok BTS)
**Hours:** 6:00 AM - 12:00 midnight
**Single Trip:** 16-42 THB

สถานีใกล้สุด: สุขุมวิท (เดิน 5 นาที เชื่อมต่อ BTS อโศก)

### Taxi / แท็กซี่
- Metered taxis available 24 hours
- Starting fare: 35 THB
- Request "Meter please" / "เปิดมิเตอร์ด้วยครับ/ค่ะ"
- Approximate fares from hotel:
  - Suvarnabhumi Airport: 350-450 THB (45-60 min)
  - Don Mueang Airport: 300-400 THB (30-45 min)
  - Grand Palace: 150-200 THB (30-40 min)

### Hotel Airport Transfer / รถรับส่งสนามบิน
**Suvarnabhumi Airport (BKK):**
- Private sedan: 1,500 THB
- Luxury sedan: 2,500 THB
- Van (up to 8 pax): 2,500 THB

**Don Mueang Airport (DMK):**
- Private sedan: 1,200 THB
- Van (up to 8 pax): 2,000 THB

Book at least 24 hours in advance at the concierge
จองล่วงหน้า 24 ชั่วโมงที่ Concierge

### Grab / Bolt
- Ride-hailing apps available
- Download app and request from hotel lobby
- Estimated wait time: 5-10 minutes

แอปเรียกรถ ดาวน์โหลดและเรียกจากล็อบบี้โรงแรม
"""

EMERGENCY_CONTACTS = """# Emergency Information / ข้อมูลฉุกเฉิน

## Emergency Contacts / เบอร์ฉุกเฉิน

### Hotel Emergency / ฉุกเฉินภายในโรงแรม
**Security:** Dial 999 from room phone or call +66 2 123 4599
**Front Desk (24 hours):** Dial 0

รปภ.: กด 999 จากโทรศัพท์ในห้อง หรือ +66 2 123 4599
แผนกต้อนรับ (24 ชม.): กด 0

### Thai Emergency Services / บริการฉุกเฉินประเทศไทย
**Police:** 191
**Fire:** 199
**Ambulance/Medical Emergency:** 1669
**Tourist Police:** 1155 (English available)

ตำรวจ: 191
ดับเพลิง: 199
ฉุกเฉินการแพทย์: 1669
ตำรวจท่องเที่ยว: 1155 (มีเจ้าหน้าที่พูดภาษาอังกฤษ)

## Medical Services / บริการทางการแพทย์

### Nearest Hospital / โรงพยาบาลใกล้สุด
**Bumrungrad International Hospital**
- Address: 33 Sukhumvit Soi 3
- Phone: +66 2 066 8888
- Distance: 10 minutes by taxi
- 24-hour emergency room
- English-speaking doctors

โรงพยาบาลบำรุงราษฎร์
ที่อยู่: 33 ซอยสุขุมวิท 3
โทร: +66 2 066 8888
ระยะทาง: 10 นาทีโดยแท็กซี่

### 24-Hour Pharmacy / ร้านยา 24 ชั่วโมง
**Boots Pharmacy (Terminal 21)**
- 5 minutes walk from hotel
- Open 10:00 AM - 10:00 PM

**Fascino Pharmacy (Soi 21)**
- 3 minutes walk
- Open 24 hours

## Fire Safety / ความปลอดภัยอัคคีภัย

### In Case of Fire / กรณีเกิดเพลิงไหม้

1. **Stay Calm** - Do not panic
   อย่าตกใจ

2. **Alert Others** - Sound the alarm if possible
   แจ้งผู้อื่น กดปุ่มแจ้งเหตุถ้าทำได้

3. **DO NOT use elevators** - Use stairs only
   ห้ามใช้ลิฟต์ ใช้บันไดเท่านั้น

4. **Feel the door** - If hot, do not open
   สัมผัสประตู ถ้าร้อน ห้ามเปิด

5. **Stay low** - Crawl under smoke
   ก้มต่ำใต้ควัน

6. **Go to assembly point** - Hotel parking lot
   ไปจุดรวมพล: ลานจอดรถโรงแรม

### Emergency Exits / ทางหนีไฟ
- Emergency exits located at both ends of each floor
- Floor plans posted behind room door
- Emergency lighting will guide you
- Hotel staff will assist evacuation

ทางหนีไฟอยู่ปลายทั้งสองด้านของทุกชั้น
แผนผังชั้นติดไว้หลังประตูห้อง
มีไฟฉุกเฉินนำทาง
พนักงานจะช่วยอพยพ

## Embassy Contacts / สถานทูต

**United States Embassy:** +66 2 205 4000
**British Embassy:** +66 2 305 8333
**Australian Embassy:** +66 2 344 6300
**Japanese Embassy:** +66 2 207 8500
**Chinese Embassy:** +66 2 245 7032
**German Embassy:** +66 2 287 9000
**French Embassy:** +66 2 657 5100

## Safety Tips / คำแนะนำความปลอดภัย

1. Keep valuables in the room safe
   เก็บของมีค่าในตู้เซฟ

2. Do not open door to strangers - verify with front desk
   อย่าเปิดประตูให้คนแปลกหน้า โทรตรวจสอบกับแผนกต้อนรับ

3. Carry hotel business card when going out
   พกนามบัตรโรงแรมเมื่อออกไปข้างนอก

4. Be aware of your surroundings
   ระวังสิ่งรอบข้าง

5. Report suspicious activity to security
   แจ้ง รปภ. หากพบสิ่งผิดปกติ
"""


def main():
    """Generate all hotel knowledge documents."""
    print("Generating hotel knowledge documents...")

    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Document content mapping
    documents = {
        "hotel_faq.md": HOTEL_FAQ,
        "dining_services.md": DINING_SERVICES,
        "spa_wellness.md": SPA_WELLNESS,
        "facilities_amenities.md": FACILITIES_AMENITIES,
        "policies_rules.md": POLICIES_RULES,
        "room_guide.md": ROOM_GUIDE,
        "local_attractions.md": LOCAL_ATTRACTIONS,
        "emergency_contacts.md": EMERGENCY_CONTACTS,
    }

    # Write each document
    for filename, content in documents.items():
        filepath = OUTPUT_DIR / filename
        filepath.write_text(content, encoding="utf-8")
        print(f"  Created: {filepath}")

    print(f"\nGenerated {len(documents)} documents in {OUTPUT_DIR}/")
    print("\nDocuments ready for ingestion into Qdrant vector store.")
    print("Run: python scripts/test_hotel_rag.py to test the RAG system")


if __name__ == "__main__":
    main()
