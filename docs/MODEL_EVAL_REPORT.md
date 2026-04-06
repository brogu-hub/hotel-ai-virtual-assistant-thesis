# Hotel AI Chatbot — Model Evaluation Report

**Date:** 2026-04-06 16:22
**Local model:** Qwen3.5 Opus 9B (Ollama, fredrezones55/qwen3.5-opus:9b)
**Cloud model:** Qwen3 Max (OpenRouter, qwen/qwen3-max)
**Test cases:** 25
**Evaluation criteria:** keyword matching, language detection, response completeness, latency

## Summary

| Metric | Qwen3.5 Opus 9B (Ollama, fredrezones55/qwen3.5-opus:9b) | Qwen3 Max (OpenRouter, qwen/qwen3-max) |
|---|---|---|
| Overall accuracy | 23/25 (92%) | 25/25 (100%) |
| Keyword accuracy | 80% | 88% |
| Language accuracy | 100% | 100% |
| Avg latency | 9905ms | 8852ms |
| p50 latency | 9049ms | 6703ms |
| p95 latency | 18360ms | 13933ms |
| Errors / timeouts | 1 | 1 |

### Cohen's Kappa (inter-model agreement)

**κ = 0.000** (poor agreement)

Interpretation: κ measures how often both models agree on pass/fail
beyond what would be expected by chance. Higher = more consistent.

### Per-category accuracy — Local

| Category | Passed | Total | Accuracy |
|---|---|---|---|
| Booking | 6 | 6 | 100% |
| Edge | 3 | 4 | 75% |
| Greeting | 3 | 4 | 75% |
| Knowledge | 8 | 8 | 100% |
| Language | 3 | 3 | 100% |

### Per-category accuracy — Cloud

| Category | Passed | Total | Accuracy |
|---|---|---|---|
| Booking | 6 | 6 | 100% |
| Edge | 4 | 4 | 100% |
| Greeting | 4 | 4 | 100% |
| Knowledge | 8 | 8 | 100% |
| Language | 3 | 3 | 100% |

## Detailed Results — Local

### K01 [PASS] — Knowledge (EN)

**Input:** `What time is breakfast?`

**Expected:** Should retrieve breakfast hours from knowledge base

**Response:** Breakfast is served daily from **6:30 AM to 10:30 AM** at **The Grand Dining Room**, located on the **1st Floor near the main lobby**.

This is complimentary for all in-house guests. The menu features an international buffet with over 50 dishes, plus Thai, Western, and Japanese stations, fresh tropical fruits, bakery items, and beverages.

**Scoring:** keywords=2/4, lang=ok, latency=34624ms
**Routing:** langgraph
**Latency:** 34624ms

---

### K02 [PASS] — Knowledge (EN)

**Input:** `What is the WiFi password?`

**Expected:** Should retrieve WiFi info from knowledge base

**Response:** I'll look up the WiFi password information for you.

```
search_hotel_knowledge
```

---

**WiFi Information for The Grand Horizon Hotel:**

**Password:** Welcome2026

**Network Details:**
- **Network Name (SSID):** GrandHorizon_Guest
- **Security:** WPA2
- **Speed:** High-speed fiber connection throughout the hotel

**Coverage Areas:**
- All guest rooms
- Lobby and public areas
- Swimming pool deck
- Restaurant and bar areas
- Spa and wellness center
- Fitness center

**Additional Notes:**
- Free for all registered guests
- Guest password is also available at the front desk
- Password may be displayed on your room key card or welcome letter

Is there anything else you'd like to know about our hotel facilities?

**Scoring:** keywords=2/3, lang=ok, latency=9049ms
**Routing:** langgraph
**Latency:** 9049ms

---

### K03 [PASS] — Knowledge (TH)

**Input:** `สระว่ายน้ำเปิดกี่โมง`

**Expected:** Should respond in Thai with pool hours

**Response:** สวัสดีค่ะ! ยินดีต้อนรับสู่ The Grand Horizon Hotel

**สระว่ายน้ำ** เปิดให้บริการดังนี้:

**เวลาเปิด-ปิด:** 06:00 - 21:00 น. ทุกวัน

**สถานที่ตั้ง:** ดาดฟ้าชั้น 5 (Rooftop)

**ข้อมูลเพิ่มเติม:**
- ขนาดสระ: 25 x 10 เมตร
- ความลึก: 1.2 - 1.8 เมตร
- อุณหภูมิน้ำ: 28-30°C (สระอุ่นตลอดทั้งปี)
- ประเภท: สระอินฟินิตี้พร้อมวิวเมือง

**สิ่งอำนวยความสะดวก:**
- ผ้าเช็ดตัวฟรีบริเวณสระ
- เก้าอี้อาบแดดและร่ม
- สระเด็ก (ความลึก 0.6 เมตร แยกพื้นที่ น้ำอุ่น)
- แจกคูซซี่/อ่างน้ำร้อน (38°C)
- ห้องเปลี่ยนเสื้อผ้าพร้อมฝักบัวและล็อกเกอร์
- มีเจ้าหน้าที่ดูแลสระ
- บริการสระว่ายน้ำ (10:00 - 20:00 น.)

**กฎระเบียบ:**
- ห้ามดำน้ำ
- เด็กต่ำกว่า 12 ปี ต้องมีผู้ใหญ่ดูแล
- ห้ามใช้ภาชนะแก้วบริเวณสระ
- ต้องอาบน้ำก่อนลงสระ

มีอะไรให้ช่วยเพิ่มเติมอีกไหมคะ?

**Scoring:** keywords=2/2, lang=ok, latency=10532ms
**Routing:** langgraph
**Latency:** 10532ms

---

### K04 [PASS] — Knowledge (EN)

**Input:** `Do you allow pets?`

**Expected:** Should retrieve pet policy with fee and weight limit

**Response:** Yes, The Grand Horizon Hotel welcomes small pets!

**Pet Policy Details:**

| Detail | Information |
|--------|-------------|
| **Allowed Pets** | Small pets only (under 5 kg / 11 lbs) |
| **Pet Fee** | 500 THB per night |
| **Pet Deposit** | 2,000 THB (fully refundable upon checkout) |
| **Pet-Friendly Rooms** | Limited availability — please request when booking |

**Pet Rules:**
- Pets must be leashed in all public areas
- Pets are **not allowed** in restaurants, spa, swimming pool, or fitness center
- Do not leave pets unattended in your room
- Guests are responsible for any damage caused by their pets

**Important:** Pet-friendly rooms have limited availability. Please mention your pet requirements when making your reservation to ensure we can accommodate you properly.

**Scoring:** keywords=3/3, lang=ok, latency=8267ms
**Routing:** langgraph
**Latency:** 8267ms

---

### K05 [PASS] — Knowledge (EN)

**Input:** `What is your cancellation policy?`

**Expected:** Should mention 48-hour free cancellation

**Response:** ---

**Cancellation Policy at The Grand Horizon Hotel**

**Free Cancellation:** More than 48 hours before your check-in date

**Within 48 Hours:** A charge of 1 night's room rate will apply

**No-Show:** Full payment for the entire stay will be charged

**Early Departure:** No refund for unused nights

---

**How to Cancel:**
- Online through our official website
- Call: +66 2 123 4567
- Email: reservations@grandparadise.com

---

If you need to make any changes to your reservation, please contact us at least 48 hours before your check-in to avoid additional charges.

**Scoring:** keywords=3/3, lang=ok, latency=8008ms
**Routing:** langgraph
**Latency:** 8008ms

---

### K06 [PASS] — Knowledge (EN)

**Input:** `Where is the spa and what treatments do you offer?`

**Expected:** Should give spa location, hours, and treatment types

**Response:** **Serenity Spa & Wellness Center**

**Location:** 3rd Floor

**Operating Hours:** Daily 10:00 AM - 10:00 PM (Last booking at 8:30 PM)

---

**Massage Treatments & Prices:**

| Treatment | 60 min | 90 min | 120 min |
|-----------|--------|--------|---------|
| **Thai Traditional Massage** | 1,500 THB | 2,000 THB | 2,500 THB |
| **Aromatherapy Oil Massage** | 1,800 THB | 2,500 THB | — |
| **Deep Tissue Massage** | 2,000 THB | 2,800 THB | — |
| **Foot Reflexology** | 1,200 THB | — | — |

**Aromatherapy Oils Available:**
- Lavender (Relaxation)
- Lemongrass (Energizing)
- Eucalyptus (Refreshing)
- Thai Jasmine (Romance)

**Signature Package — Royal Thai Experience:**
- **Duration:** 3 hours
- **Price:** 5,500 THB
- **Includes:** Thai herbal steam (30 min) + Thai traditional massage (90 min) + 

**Scoring:** keywords=3/3, lang=ok, latency=9822ms
**Routing:** langgraph
**Latency:** 9822ms

---

### K07 [PASS] — Knowledge (EN)

**Input:** `What time is check-in and check-out?`

**Expected:** Should give check-in 2PM and check-out noon

**Response:** **Check-in & Check-out Times**

**Check-in:** 2:00 PM (14:00)
- Early check-in may be available upon request, subject to room availability. No charge if available.

**Check-out:** 12:00 PM (noon)
- Late check-out is available for **500 THB per hour** until 6:00 PM (18:00).
- Please contact the front desk to arrange late check-out.

**Luggage Storage:**
Complimentary luggage storage is available at the concierge desk before check-in and after check-out at no additional charge.

**Express Check-out:**
Available — simply drop your key card in the express check-out box at the front desk, and your receipt will be emailed to you.

**Scoring:** keywords=4/4, lang=ok, latency=9677ms
**Routing:** langgraph
**Latency:** 9677ms

---

### K08 [PASS] — Knowledge (TH)

**Input:** `มีบริการรถรับส่งสนามบินไหม`

**Expected:** Should respond in Thai about airport transfer

**Response:** สวัสดีค่ะ ยินดีให้บริการค่ะ

**ใช่ค่ะ! The Grand Horizon Hotel มีบริการรถรับส่งสนามบินทั้ง 2 แห่งค่ะ**

---

## 🛫 **สนามบินสุวรรณภูมิ (BKK)**
- **ระยะทาง:** 30 กม.
- **เวลาเดินทาง:** 45-60 นาที

| ประเภทรถ | ราคา |
|-----------|------|
| Private Sedan | 1,500 บาท (สูงสุด 3 คน) |
| Luxury Sedan (BMW/Mercedes) | 2,500 บาท |
| Van (8 คน) | 2,500 บาท |

---

## 🛫 **สนามบินดอนเมือง (DMK)**
- **ระยะทาง:** 25 กม.
- **เวลาเดินทาง:** 30-45 นาที

| ประเภทรถ | ราคา |
|-----------|------|
| Private Sedan | 1,200 บาท |
| Van (8 คน) | 2,000 บาท |

---

## 📞 **การจอง**
กรุณาติดต่อ **Concierge** ล่วงหน้า **24 ชั่วโมง** เพื่อจองบริการรถรับส่งสนามบินค่ะ

---

**ต้องการให้ Concierge ช่วยจองรถรับส่งสนามบินให้ท่านหรือไม่คะ?**

**Scoring:** keywords=2/2, lang=ok, latency=10392ms
**Routing:** langgraph
**Latency:** 10392ms

---

### B01 [PASS] — Booking (EN)

**Input:** `Is there a room available next Monday?`

**Expected:** Should use check_room_availability tool and show room types

**Response:** Yes, there are several rooms available for check-in on Monday, April 13, 2026 (for a one-night stay).

**Available Standard Rooms:**

| Room | Floor | View | Price (1 night) |
|------|-------|------|-----------------|
| 102 | 1 | Pool View | 2,500 THB |
| 105 | 1 | Mountain View | 2,500 THB |
| 106 | 1 | City View | 2,500 THB |
| 107 | 1 | Mountain View | 2,500 THB |
| 109 | 1 | Garden View | 2,500 THB |
| 110 | 1 | Garden View | 2,500 THB |
| 113 | 1 | Garden View | 2,500 THB |
| 115 | 1 | City View | 2,500 THB |
| 201 | 2 | Garden View | 2,500 THB |
| 202 | 2 | Garden View | 2,500 THB |

All rooms accommodate up to 2 guests.

Would you like to:
1. **Book a room** - I'll need your email address and preferred room (or I can select one for you)
2. **Check availability for different dates** 

**Scoring:** keywords=4/4, lang=ok, latency=12038ms
**Routing:** langgraph
**Latency:** 12038ms

---

### B02 [PASS] — Booking (EN)

**Input:** `How much is a Deluxe room per night?`

**Expected:** Should retrieve price from database via tool, not from memory

**Response:** ## Deluxe Room Price / ราคาห้องดีลักซ์

**4,500 THB per night** / **4,500 บาท/คืน**

### Room Details / รายละเอียดห้อง

| Feature | Detail |
|---------|--------|
| **Size** | 45 sqm / 45 ตร.ม. |
| **Price** | 4,500 THB per night |
| **Max Guests** | 2 adults + 1 child |
| **Bed** | 1 King bed |
| **Amenities** | ✓ City view | ✓ Work desk | ✓ Minibar | ✓ Free WiFi | ✓ Breakfast | |

### Included in Price / รวมในราคา

- ✓ Complimentary breakfast
- ✓ Free high-speed WiFi
- ✓ Minibar refreshments
- ✓ Daily housekeeping
- ✓ 24-hour front desk service

### Booking Information / ข้อมูลการจอง

**To book a Deluxe Room:**
- **Phone:** +66 2 123 4567
- **Email:** reservations@grandparadise.com
- **Website:** www.grandparadise.com

**Cancellation Policy:**
- Free cancellation: More than 48 hours befor

**Scoring:** keywords=3/4, lang=ok, latency=13856ms
**Routing:** langchain_fallback
**Latency:** 13856ms

---

### B03 [PASS] — Booking (EN)

**Input:** `I want to cancel my booking HTL260405001`

**Expected:** Should route to booking handler and attempt cancellation

**Response:** I'm sorry, but I couldn't find a reservation with the number HTL260405001 in our system. This could mean:

1. The reservation number may have been entered incorrectly
2. The reservation might have already been cancelled
3. The reservation might have been deleted from the system

To help you further, could you please verify the reservation number? Alternatively, if you have your email address associated with the booking, I can look up your reservations using that.

Please provide the correct reservation number or your email address, and I'll be happy to assist you with your cancellation request.

**Scoring:** keywords=1/1, lang=ok, latency=7823ms
**Routing:** langgraph
**Latency:** 7823ms

---

### B04 [PASS] — Booking (TH)

**Input:** `มีห้องว่างวันที่ 15-17 เดือนหน้าไหม`

**Expected:** Should check availability for next month 15-17 in Thai

**Response:** สวัสดีค่ะ! ยินดีต้อนรับสู่โรงแรมแกรนด์ฮอไรซอน

สำหรับช่วงวันที่ 15-17 เมษายน 2026 (3 คืน) ฉันจะตรวจสอบห้องว่างให้ค่ะ

กรุณาระบุ:
1. **จำนวนผู้เข้าพัก** (กี่ท่าน)
2. **ประเภทห้องที่ต้องการ** (Standard, Deluxe, Suite, หรือ Penthouse)

หรือถ้าไม่แน่ใจ ฉันสามารถแนะนำห้องที่มีว่างพร้อมราคาให้ค่ะ

**Scoring:** keywords=2/2, lang=ok, latency=6332ms
**Routing:** langgraph
**Latency:** 6332ms

---

### B05 [PASS] — Booking (EN)

**Input:** `I'd like to book a Standard room for tomorrow for 2 nights. My email is test@example.com`

**Expected:** Should attempt to create reservation with dates and email

**Response:** Your Standard room reservation has been successfully confirmed!

**Reservation Details:**
- **Confirmation Number:** HTL2604060308
- **Room:** 102 (Standard Room)
- **Check-in Date:** April 7, 2026 (tomorrow)
- **Check-out Date:** April 9, 2026
- **Number of Nights:** 2
- **Number of Guests:** 1
- **Price:** 3,250 THB/night (Same-Day +30% surcharge applied)
- **Total Amount:** 6,500 THB

**Important Notes:**
- Your reservation is now confirmed and ready for check-in
- Please arrive at the front desk by 3:00 PM on April 7 for check-in
- Late check-in after 3:00 PM may incur additional charges
- A payment link will be sent to your email shortly for the total amount

Is there anything else you would like to know about your stay or any special requests you would like to make?

**Scoring:** keywords=2/3, lang=ok, latency=18360ms
**Routing:** langgraph
**Latency:** 18360ms

---

### B06 [PASS] — Booking (EN)

**Input:** `Can you check my booking? My email is john@hotel.com`

**Expected:** Should use get_guest_reservations with the email

**Response:** I've checked your email address (john@hotel.com) in our system, but no reservations were found associated with it.

This could mean:
- You haven't made a booking yet
- The email address used for booking was different
- The booking may have been cancelled
- There could be a typo in the email address

Would you like me to help you with something else? For example, I can:
- Check room availability for new booking
- Help you create a new reservation
- Or if you have a confirmation number (starting with HTL), I can look up that specific booking for you

**Scoring:** keywords=2/2, lang=ok, latency=6458ms
**Routing:** langgraph
**Latency:** 6458ms

---

### G01 [PASS] — Greeting (EN)

**Input:** `Hello!`

**Expected:** Should warmly greet and offer to help

**Response:** Hello! Welcome to The Grand Horizon Hotel. How may I assist you today?

**Scoring:** keywords=3/3, lang=ok, latency=5154ms
**Routing:** langchain_fallback
**Latency:** 5154ms

---

### G02 [PASS] — Greeting (TH)

**Input:** `สวัสดีครับ`

**Expected:** Should respond in Thai with greeting

**Response:** สวัสดีค่ะ! ยินดีที่ได้ต้อนรับคุณสู่โรงแรมเดอะแกรนด์ฮอไรซัน

สวัสดีค่ะ! ยินดีที่ได้ต้อนรับคุณสู่โรงแรมเดอะแกรนด์ฮอไรซัน

มีอะไรให้ฉันช่วยคุณวันนี้ไหมคะ? ฉันพร้อมช่วยเหลือคุณในเรื่องต่างๆ เช่น:

- **การเช็คน/เช็คว์** (Check-in/Check-out)
- **การฝากกระเป๋า** (Luggage storage)
- **การจองร้านอาหาร** (Restaurant reservations)
- **การซื้อตั๋ว** (Tickets for shows/attractions)
- **การจัดดอกไม้และของขวัญ** (Flower and gift arrangements)
- **การแลกเปลี่ยนเงิน** (Currency exchange)
- **หรือข้อมูลอื่นๆ** ที่คุณต้องการทราบ

กรุณาบอกฉันว่าต้องการความช่วยเหลือด้านใดนะคะ 😊

**Scoring:** keywords=2/2, lang=ok, latency=10488ms
**Routing:** langchain_fallback
**Latency:** 10488ms

---

### G03 [FAIL] — Greeting (EN)

**Input:** `Thank you for your help!`

**Expected:** Should acknowledge thanks politely

**Response:** You're very welcome! 😊

I'm always happy to assist you during your stay at The Grand Horizon Hotel.

If you need anything else, please don't hesitate to ask:
- **Room service** (Dial 1)
- **Front desk** (Dial 0)
- **Concierge** (for recommendations, reservations, etc.)

I hope you have a wonderful time in Bangkok! 🇹🇭

สวัสดีค่ะ/ครับ!

**Scoring:** keywords=1/4, lang=ok, latency=7319ms
**Routing:** langchain_fallback
**Latency:** 7319ms

---

### G04 [PASS] — Greeting (EN)

**Input:** `What's the weather like today?`

**Expected:** Should handle gracefully, redirect to hotel services

**Response:** I'm sorry, but I don't have access to real-time weather information in my system. The hotel information I have available doesn't include current weather forecasts.

To get today's weather, I'd recommend:

1. **Check a weather app** on your phone (like AccuWeather, Weather.com, or your phone's built-in weather app)
2. **Search online** for "[your city] weather today"
3. **Ask the hotel concierge** (located in the Main Lobby) - they often have local weather information and can provide recommendations based on conditions

Would you like me to help you with any other information from the hotel guide, such as:
- Directions to nearby attractions
- Restaurant recommendations
- Transportation options
- Or any other questions about the hotel services?

**Scoring:** keywords=0/0, lang=ok, latency=9617ms
**Routing:** langchain_fallback
**Latency:** 9617ms

---

### L01 [PASS] — Language (EN)

**Input:** `Tell me about breakfast`

**Expected:** Response MUST be in English (not Thai)

**Response:** I'll search for the most accurate breakfast information for you.

```
search_hotel_knowledge(query="breakfast details")
```

---

## Breakfast at The Grand Horizon Hotel

### 🍽️ The Grand Dining Room - Breakfast Buffet

| **Details** | **Information** |
|-------------|-----------------|
| **Location** | 1st Floor, near the main lobby |
| **Hours** | 6:30 AM – 10:30 AM daily (including holidays) |
| **Price** | **Complimentary** for all in-house guests |

### 🍳 Breakfast Menu Highlights

**International Buffet**
- Over 50 dishes from around the world
- Fresh tropical fruits: mango, papaya, dragon fruit, watermelon, pineapple
- Fresh juices, coffee, tea, smoothies

**Thai Breakfast Station**
- Jok (rice porridge)
- Khao Tom (rice soup)
- Pad Thai
- Thai omelette

**Western Station**
- Made-t

**Scoring:** keywords=1/1, lang=ok, latency=9112ms
**Routing:** langgraph
**Latency:** 9112ms

---

### L02 [PASS] — Language (TH)

**Input:** `อาหารเช้าเสิร์ฟกี่โมง`

**Expected:** Response MUST be in Thai (not English)

**Response:** **อาหารเช้าเสิร์ฟเวลา 06:30 - 10:30 น. ทุกวัน**

**สถานที่:** ชั้น 1 ใกล้ล็อบบี้หลัก

**รายละเอียดเพิ่มเติม:**
- **ราคา:** ฟรีสำหรับแขกที่พักทุกห้อง
- **เมนู:** Buffet อาหารนานาชาติกว่า 50 รายการ พร้อมสถานีอาหารไทย (โจ๊ก, ข้าวต้ม, ผัดไทย, ไข่เจียวไทย), อาหารตะวันตก (ไข่ตามสั่ง, แพนเค้ก, วาฟเฟิล), อาหารญี่ปุ่น (ซุปมิโซะ, ปลาย่าง, ข้าว, ผักดอง), ผลไม้เขตร้อนสดใหม่, ขนมปังและเบเกอรี่สดใหม่
- **ตัวเลือกพิเศษ:** มีเมนูมังสวิรัติ, ไร้ผัก, ฮาลาล และไร้กลูเตน (แจ้งล่วงหน้า)

หากต้องการข้อมูลเพิ่มเติมเกี่ยวกับเมนูอาหารหรือการสั่งอาหารเข้าห้อง (Room Service) สามารถแจ้งได้เลยค่ะ

**Scoring:** keywords=1/1, lang=ok, latency=8201ms
**Routing:** langgraph
**Latency:** 8201ms

---

### L03 [PASS] — Language (EN)

**Input:** `Where is the gym?`

**Expected:** Response in English with gym location

**Response:** The Fitness Center is located on the **4th Floor** of The Grand Horizon Hotel.

**Hours:** 24 hours (keycard access for all guests)

**Equipment includes:**
- 8 treadmills
- 4 elliptical machines
- 4 stationary bikes
- Free weights (dumbbells 2-50 kg)
- Weight machines
- Yoga mats and exercise balls
- Stretching area

**Personal Training:**
- Available by appointment
- Price: 1,000 THB per session (1 hour)
- To book: Dial 404 from your room

The fitness center is complimentary for all hotel guests.

**Scoring:** keywords=2/3, lang=ok, latency=8165ms
**Routing:** langgraph
**Latency:** 8165ms

---

### E01 [PASS] — Edge (EN)

**Input:** `I need extra towels in room 501`

**Expected:** Should route to service handler for amenity request

**Response:** I'd be happy to help you with extra towels for room 501. However, to process this request, I need your reservation ID or confirmation number.

Could you please provide your reservation ID or confirmation number so I can create the service request for extra towels?

**Scoring:** keywords=1/1, lang=ok, latency=5847ms
**Routing:** langgraph
**Latency:** 5847ms

---

### E02 [PASS] — Edge (EN)

**Input:** `Is there a room available on December 31st for New Year's Eve?`

**Expected:** Should check availability for the specific date

**Response:** # New Year's Eve Room Availability

**มีห้องพักว่างสำหรับคืนวันที่ 31 ธันวาคม - 1 มกราคม (วันสิ้นปี):**

## ห้องพักที่มีว่าง:

| ห้อง | ชั้น | ทิวทัศน์ | ราคา | รองรับ |
|------|-----|---------|------|--------|
| 102 | 1 | ทิวทัศน์สระว่ายน้ำ | 2,500 บาท/คืน | 2 ท่าน |
| 105 | 1 | ทิวทัศน์ภูเขา | 2,500 บาท/คืน | 2 ท่าน |
| 106 | 1 | ทิวทัศน์เมือง | 2,500 บาท/คืน | 2 ท่าน |
| 107 | 1 | ทิวทัศน์ภูเขา | 2,500 บาท/คืน | 2 ท่าน |
| 108 | 1 | ทิวทัศน์สระว่ายน้ำ | 2,500 บาท/คืน | 2 ท่าน |
| 109 | 1 | ทิวทัศน์สวน | 2,500 บาท/คืน | 2 ท่าน |
| 110 | 1 | ทิวทัศน์สวน | 2,500 บาท/คืน | 2 ท่าน |
| 113 | 1 | ทิวทัศน์สวน | 2,500 บาท/คืน | 2 ท่าน |
| 115 | 1 | ทิวทัศน์เมือง | 2,500 บาท/คืน | 2 ท่าน |
| 201 | 2 | ทิวทัศน์สวน | 2,500 บาท/คืน | 2 ท่าน |

## ราคา:
- **2,500 บาท ต่อคืน** (รวมภาษีแล้ว)

---

**คุ

**Scoring:** keywords=2/4, lang=ok, latency=12977ms
**Routing:** langgraph
**Latency:** 12977ms

---

### E03 [FAIL] — Edge (EN)

**Input:** `I want to book 3 rooms for a group of 10 people`

**Expected:** Should route to booking and handle multi-room request

**Response:** สวัสดีค่ะ ยินดีต้อนรับสู่ The Grand Horizon Hotel!

เพื่อช่วยคุณจองห้องสำหรับกลุ่ม 10 ท่าน ฉันจำเป็นต้องขอข้อมูลเพิ่มเติมดังนี้ค่ะ:

1. **วันที่เข้าพักและวันเช็คเอาท์** - กรุณาระบุวันที่ต้องการเข้าพักและวันที่จะเช็คเอาท์
2. **ประเภทห้องที่ต้องการ** - เช่น Standard, Deluxe, Suite หรือ Penthouse (ถ้าไม่ระบุ ฉันจะแนะนำตามความเหมาะสม)
3. **อีเมลของผู้เข้าพัก** - จำเป็นต้องมีเพื่อสร้างการจอง

กรุณาแจ้งข้อมูลเหล่านี้ให้ฉันทราบค่ะ ฉันจะตรวจสอบความพร้อมของห้องและดำเนินการจองให้ทันทีค่ะ

**Scoring:** keywords=0/1, lang=ok, latency=5497ms
**Routing:** langgraph
**Latency:** 5497ms

---

### E04 [PASS] — Edge (EN)

**Input:** ``

**Expected:** Should handle empty message gracefully (422 or polite response)

**Response:** (empty)

**Scoring:** graceful error handling
**Routing:** validation_error
**Latency:** 6ms
**Error:** validation_error

---

## Detailed Results — Cloud

### K01 [PASS] — Knowledge (EN)

**Input:** `What time is breakfast?`

**Expected:** Should retrieve breakfast hours from knowledge base

**Response:** Breakfast is served daily from **6:30 AM to 10:30 AM** at **The Grand Dining Room**, located on the **1st floor near the main lobby**.  

It is **complimentary for all in-house guests** and features an international buffet with over 50 dishes, including Thai, Western, and Japanese stations, fresh tropical fruits, pastries, and beverages. Vegetarian, vegan, halal, and gluten-free options are available upon request.

**Scoring:** keywords=2/4, lang=ok, latency=6457ms
**Routing:** langgraph
**Latency:** 6457ms

---

### K02 [PASS] — Knowledge (EN)

**Input:** `What is the WiFi password?`

**Expected:** Should retrieve WiFi info from knowledge base

**Response:** The WiFi password at The Grand Horizon Hotel is **GrandHorizon2026**.  

WiFi is complimentary for all guests and available throughout the hotel, including guest rooms, lobby, pool area, and fitness center. No login or additional steps are required—just select the network **"GrandHorizon_Guest"** and enter the password above.

**Scoring:** keywords=2/3, lang=ok, latency=5527ms
**Routing:** langgraph
**Latency:** 5527ms

---

### K03 [PASS] — Knowledge (TH)

**Input:** `สระว่ายน้ำเปิดกี่โมง`

**Expected:** Should respond in Thai with pool hours

**Response:** สระว่ายน้ำของโรงแรมเปิดให้บริการทุกวันตั้งแต่เวลา **06:00 น. ถึง 21:00 น.** ค่ะ  
ตั้งอยู่ที่ **ดาดฟ้าชั้น 5** เป็นสระอินฟินิตี้น้ำอุ่นขนาด 25 x 10 เมตร พร้อมวิวเมือง และมีสระเด็กแยกต่างหากด้วยค่ะ  

หากมีคำถามเพิ่มเติม ยินดีช่วยเหลือเสมอเลยนะคะ! 😊

**Scoring:** keywords=2/2, lang=ok, latency=8176ms
**Routing:** langgraph
**Latency:** 8176ms

---

### K04 [PASS] — Knowledge (EN)

**Input:** `Do you allow pets?`

**Expected:** Should retrieve pet policy with fee and weight limit

**Response:** Yes, we allow small pets weighing under 5 kg (11 lbs).  

- **Pet fee:** 500 THB per night  
- **Refundable deposit:** 2,000 THB  
- **Pet-friendly rooms:** Limited availability—please request at the time of booking  

**Important rules:**  
- Pets must be leashed in all public areas  
- Not permitted in restaurants, spa, pool, or fitness center  
- Must not be left unattended in the room  
- Guests are responsible for any damage caused by their pet  

For availability and to arrange pet accommodation, please let us know when making your reservation.

**Scoring:** keywords=3/3, lang=ok, latency=7591ms
**Routing:** langgraph
**Latency:** 7591ms

---

### K05 [PASS] — Knowledge (EN)

**Input:** `What is your cancellation policy?`

**Expected:** Should mention 48-hour free cancellation

**Response:** Our cancellation policy is as follows:

- **Free Cancellation**: If you cancel more than 48 hours before your scheduled check-in date, no charge will apply.  
- **Within 48 Hours**: If you cancel within 48 hours of your check-in date, a charge of **1 night’s room rate** will apply.  
- **No-Show**: If you do not arrive and do not cancel, you will be charged the **full amount for your entire stay**.  
- **Early Departure**: If you check out before your scheduled departure date, **no refund** will be issued for unused nights.

You can cancel your reservation:  
- Online through our website  
- By calling **+66 2 123 4567**  
- By emailing **reservations@grandparadise.com**  

Please note that all times are based on **Bangkok local time (GMT+7)**.

**Scoring:** keywords=3/3, lang=ok, latency=8727ms
**Routing:** langgraph
**Latency:** 8727ms

---

### K06 [PASS] — Knowledge (EN)

**Input:** `Where is the spa and what treatments do you offer?`

**Expected:** Should give spa location, hours, and treatment types

**Response:** The Serenity Spa & Wellness Center is located on the **3rd floor** of The Grand Horizon Hotel and is open **daily from 10:00 AM to 10:00 PM**, with the last treatment booking accepted at **8:30 PM**.

We offer the following treatments:

**Massage Treatments:**  
- **Thai Traditional Massage**:  
  - 60 min: 1,500 THB  
  - 90 min: 2,000 THB  
  - 120 min: 2,500 THB  

- **Aromatherapy Oil Massage** (choose from Lavender, Lemongrass, Eucalyptus, or Thai Jasmine):  
  - 60 min: 1,800 THB  
  - 90 min: 2,500 THB  

- **Deep Tissue Massage**:  
  - 60 min: 2,000 THB  
  - 90 min: 2,800 THB  

- **Foot Reflexology**:  
  - 45 min: 900 THB  
  - 60 min: 1,200 THB  

**Signature Package:**  
- **Royal Thai Experience** (3 hours – 5,500 THB): Includes herbal steam, Thai traditional massage, Thai f

**Scoring:** keywords=3/3, lang=ok, latency=13774ms
**Routing:** langgraph
**Latency:** 13774ms

---

### K07 [PASS] — Knowledge (EN)

**Input:** `What time is check-in and check-out?`

**Expected:** Should give check-in 2PM and check-out noon

**Response:** Check-in time is 2:00 PM (14:00), and check-out time is 12:00 PM (noon).  

Early check-in is available at no extra charge if rooms are ready. Late check-out is available for 500 THB per hour until 6:00 PM—please arrange this in advance with the front desk.  

Complimentary luggage storage is also available before check-in and after check-out at the concierge desk.

**Scoring:** keywords=4/4, lang=ok, latency=6312ms
**Routing:** langgraph
**Latency:** 6312ms

---

### K08 [PASS] — Knowledge (TH)

**Input:** `มีบริการรถรับส่งสนามบินไหม`

**Expected:** Should respond in Thai about airport transfer

**Response:** มีค่ะ! ทางโรงแรมให้บริการรถรับส่งสนามบินทั้งจากสนามบินสุวรรณภูมิ (BKK) และดอนเมือง (DMK) ดังนี้:

**สนามบินสุวรรณภูมิ (BKK)**  
- ระยะทาง: 30 กม.  
- เวลาเดินทาง: 45–60 นาที  
- **รถเก๋งส่วนตัว**: 1,500 บาท (รองรับได้สูงสุด 3 ท่าน)  
- **รถหรู (BMW/Mercedes)**: 2,500 บาท  
- **รถตู้ (8 ท่าน)**: 2,500 บาท  

**สนามบินดอนเมือง (DMK)**  
- ระยะทาง: 25 กม.  
- เวลาเดินทาง: 30–45 นาที  
- **รถเก๋งส่วนตัว**: 1,200 บาท  
- **รถตู้ (8 ท่าน)**: 2,000 บาท  

**การจอง**: กรุณาติดต่อแผนกคอนเซียร์จอย่างน้อย 24 ชั่วโมงล่วงหน้าค่ะ  
หากต้องการจองหรือสอบถามเพิ่มเติม แจ้งได้เลยนะคะ 😊

**Scoring:** keywords=2/2, lang=ok, latency=13311ms
**Routing:** langgraph
**Latency:** 13311ms

---

### B01 [PASS] — Booking (EN)

**Input:** `Is there a room available next Monday?`

**Expected:** Should use check_room_availability tool and show room types

**Response:** Thank you for your inquiry! To check room availability for next Monday (April 14, 2026), could you please let me know:

1. Your preferred check-out date (how many nights would you like to stay?)
2. Your preferred room type (Standard, Deluxe, Suite, or Penthouse)?

This will help me find the best available options for you!

**Scoring:** keywords=4/4, lang=ok, latency=5667ms
**Routing:** langgraph
**Latency:** 5667ms

---

### B02 [PASS] — Booking (EN)

**Input:** `How much is a Deluxe room per night?`

**Expected:** Should retrieve price from database via tool, not from memory

**Response:** # Deluxe Room Pricing

## Answer

The **Deluxe Room** costs **3,500 THB per night**.

## Room Details

| Feature | Details |
|---------|---------|
| **Price** | 3,500 THB per night |
| **Size** | 35 sqm |
| **Max Guests** | 3 adults |
| **Amenities** | ✓ Breakfast included<br>✓ Free WiFi<br>✓ Free minibar |

## Additional Information

- **Breakfast**: Included in the price
- **WiFi**: Complimentary high-speed internet
- **Minibar**: Complimentary refreshments

## Booking Options

- **Online**: Through the official website
- **Phone**: +66 2 123 4567
- **Email**: reservations@grandparadise.com

---

*Note: Prices are subject to seasonal variations and special promotions. Please verify current rates at the time of booking.*

**Scoring:** keywords=3/4, lang=ok, latency=12794ms
**Routing:** langchain_fallback
**Latency:** 12794ms

---

### B03 [PASS] — Booking (EN)

**Input:** `I want to cancel my booking HTL260405001`

**Expected:** Should route to booking handler and attempt cancellation

**Response:** I'm sorry, but I couldn't find a reservation with the confirmation number HTL260405001. 

Could you please:
- Double-check the confirmation number, or
- Provide the email address used for the booking so I can look it up?

I'll be happy to assist you with the cancellation once I locate your reservation.

**Scoring:** keywords=1/1, lang=ok, latency=8427ms
**Routing:** langgraph
**Latency:** 8427ms

---

### B04 [PASS] — Booking (TH)

**Input:** `มีห้องว่างวันที่ 15-17 เดือนหน้าไหม`

**Expected:** Should check availability for next month 15-17 in Thai

**Response:** มีห้องว่างสำหรับวันที่ 15-17 พฤษภาคม 2569 ค่ะ โดยมีห้องสแตนดาร์ดให้เลือกหลายห้อง ทั้งวิวสระว่ายน้ำ วิวภูเขา วิวเมือง และวิวสวน ราคาห้องละ 2,500 บาทต่อคืน (รวม 2 คืน เป็นเงิน 5,000 บาท) รองรับได้ 2 ท่านค่ะ

หากคุณต้องการจอง รบกวนแจ้ง:
1. ประเภทห้องที่ต้องการ (สแตนดาร์ด/ดีลักซ์/สวีท/เพนท์เฮาส์)
2. จำนวนผู้เข้าพัก
3. อีเมลของคุณ เพื่อดำเนินการจองค่ะ

หรือหากต้องการดูราคาจริงพร้อมส่วนลดหรือค่าธรรมเนียมเพิ่มเติม แจ้งได้เลยนะคะค่ะ

**Scoring:** keywords=2/2, lang=ok, latency=13933ms
**Routing:** langgraph
**Latency:** 13933ms

---

### B05 [PASS] — Booking (EN)

**Input:** `I'd like to book a Standard room for tomorrow for 2 nights. My email is test@example.com`

**Expected:** Should attempt to create reservation with dates and email

**Response:** Your reservation has been successfully confirmed! Here are your booking details:

**Confirmation Number:** HTL2604060309  
**Room:** 105 (Standard Room, Mountain View, 1st floor)  
**Dates:** April 7-9, 2026 (2 nights)  
**Guests:** 2  
**Total Price:** 6,500 THB (3,250 THB/night with same-day booking surcharge)

**Upgrade Opportunity:**  
We have a Deluxe Room available (Room 403, Garden View) for an additional 2,600 THB/night (5,200 THB total for your stay). Would you be interested in this upgrade?

**Payment:**  
Please complete your payment using this secure link (valid for 30 minutes):  
https://pay.grandhorizon.hotel/checkout/5061a3d1-435a-4b25-a547-9a8cea5b8b37

Thank you for choosing The Grand Horizon Hotel! Is there anything else I can assist you with?

**Scoring:** keywords=3/3, lang=ok, latency=37955ms
**Routing:** langgraph
**Latency:** 37955ms

---

### B06 [PASS] — Booking (EN)

**Input:** `Can you check my booking? My email is john@hotel.com`

**Expected:** Should use get_guest_reservations with the email

**Response:** I couldn't find any reservations associated with the email address john@hotel.com. 

Could you please double-check the email address or provide your confirmation number (which starts with HTL...) if you have it? This will help me locate your booking accurately.

**Scoring:** keywords=2/2, lang=ok, latency=6703ms
**Routing:** langgraph
**Latency:** 6703ms

---

### G01 [PASS] — Greeting (EN)

**Input:** `Hello!`

**Expected:** Should warmly greet and offer to help

**Response:** Hello! Welcome to The Grand Horizon Hotel. How may I assist you today? Whether you'd like to check room availability, make a reservation, or learn more about our facilities and services, I'm here to help!

**Scoring:** keywords=3/3, lang=ok, latency=4095ms
**Routing:** langgraph
**Latency:** 4095ms

---

### G02 [PASS] — Greeting (TH)

**Input:** `สวัสดีครับ`

**Expected:** Should respond in Thai with greeting

**Response:** สวัสดีครับ! ยินดีต้อนรับสู่ The Grand Horizon Hotel ค่ะ  
มีอะไรที่สามารถช่วยคุณได้บ้างไหมครับ? เช่น สอบถามข้อมูลห้องพัก จองห้อง หรือบริการอื่นๆ ของโรงแรม? 😊

**Scoring:** keywords=2/2, lang=ok, latency=5224ms
**Routing:** langgraph
**Latency:** 5224ms

---

### G03 [PASS] — Greeting (EN)

**Input:** `Thank you for your help!`

**Expected:** Should acknowledge thanks politely

**Response:** You're very welcome! 😊  
If you need any assistance with your stay at The Grand Horizon Hotel—whether it's booking a room, exploring our dining options, spa services, or anything else—I'm here to help.  

Feel free to ask anytime!

**Scoring:** keywords=2/4, lang=ok, latency=5830ms
**Routing:** langgraph
**Latency:** 5830ms

---

### G04 [PASS] — Greeting (EN)

**Input:** `What's the weather like today?`

**Expected:** Should handle gracefully, redirect to hotel services

**Response:** I'm sorry, but I don't have access to real-time weather data. However, you can check the current weather in Bangkok using a trusted weather service like the Weather Channel, AccuWeather, or your smartphone’s weather app.

If you're planning outdoor activities during your stay with us at The Grand Horizon Hotel, our concierge team would be happy to assist with recommendations based on the forecast—just let us know!  

Would you like help with anything else? 😊

**Scoring:** keywords=0/0, lang=ok, latency=7242ms
**Routing:** langgraph
**Latency:** 7242ms

---

### L01 [PASS] — Language (EN)

**Input:** `Tell me about breakfast`

**Expected:** Response MUST be in English (not Thai)

**Response:** Breakfast at The Grand Horizon Hotel is served at **The Grand Dining Room**, located on the **1st floor near the main lobby**.  

**Hours:** 6:30 AM – 10:30 AM daily (including holidays)  
**Price:** Complimentary for all in-house guests  

The breakfast features an **international buffet with over 50 dishes**, including:  
- **Thai station**: Jok (rice porridge), Khao Tom, Pad Thai, and Thai omelette  
- **Western station**: Made-to-order eggs, pancakes, waffles, bacon, and sausages  
- **Japanese station**: Miso soup, grilled fish, rice, and pickles  
- **Fresh tropical fruits**: Mango, papaya, dragon fruit, watermelon, and pineapple  
- **Bakery**: Fresh pastries, croissants, Danish, and assorted breads  
- **Beverages**: Fresh juices, coffee, tea, and smoothies  

Vegetarian, vegan, ha

**Scoring:** keywords=1/1, lang=ok, latency=9430ms
**Routing:** langgraph
**Latency:** 9430ms

---

### L02 [PASS] — Language (TH)

**Input:** `อาหารเช้าเสิร์ฟกี่โมง`

**Expected:** Response MUST be in Thai (not English)

**Response:** อาหารเช้าเสิร์ฟที่ **The Grand Dining Room** ชั้น 1 ใกล้ล็อบบี้หลัก  
**เวลา 06:30 – 10:30 น. ทุกวัน** (รวมวันหยุด)  

สำหรับผู้เข้าพักทุกท่าน **รับประทานฟรี** ค่ะ  

เมนูมีทั้งบุฟเฟต์นานาชาติกว่า 50 รายการ ทั้งไทย (โจ๊ก ข้าวต้ม ผัดไทย ไข่เจียว) ฝรั่ง (ไข่ทำสด แพนเค้ก เบคอน) ญี่ปุ่น (ซุปมิโซะ ปลาอบ) ผลไม้สด ขนมอบ และมีตัวเลือกมังสวิรัติ ฮาลาล หรือกลูเตนฟรี ตามคำขอค่ะ 🌟

**Scoring:** keywords=1/1, lang=ok, latency=10731ms
**Routing:** langgraph
**Latency:** 10731ms

---

### L03 [PASS] — Language (EN)

**Input:** `Where is the gym?`

**Expected:** Response in English with gym location

**Response:** The gym (Fitness Center) is located on the **4th Floor** and is open **24 hours** with keycard access. It’s **complimentary for all hotel guests**.

**Equipment includes:**
- 8 treadmills  
- 4 elliptical machines  
- 4 stationary bikes  
- Free weights (2–50 kg)  
- Weight machines  
- Yoga mats, exercise balls, and a stretching area  

**Personal training** is available by appointment at **1,000 THB per 1-hour session**. To book, dial **404** from your room phone.

**Scoring:** keywords=3/3, lang=ok, latency=6571ms
**Routing:** langgraph
**Latency:** 6571ms

---

### E01 [PASS] — Edge (EN)

**Input:** `I need extra towels in room 501`

**Expected:** Should route to service handler for amenity request

**Response:** Thank you for your request! I’ve created a service request for extra towels to be delivered to Room 501.  

Your request has been logged under service type **Extra Towels**, and housekeeping will deliver them to your room shortly.  

**Estimated response time:** Within 15–20 minutes.  

If you need anything else, feel free to let us know!

**Scoring:** keywords=1/1, lang=ok, latency=5470ms
**Routing:** langgraph
**Latency:** 5470ms

---

### E02 [PASS] — Edge (EN)

**Input:** `Is there a room available on December 31st for New Year's Eve?`

**Expected:** Should check availability for the specific date

**Response:** Thank you for your inquiry! To check availability for New Year's Eve (December 31st), I'll need to know your check-out date as well. Could you please let me know when you plan to depart?

Also, do you have a preferred room type? Our options include:
- Standard Room
- Deluxe Room  
- Suite
- Penthouse

Once I have these details, I can check availability and provide you with exact pricing for your stay.

**Scoring:** keywords=3/4, lang=ok, latency=5994ms
**Routing:** langgraph
**Latency:** 5994ms

---

### E03 [PASS] — Edge (EN)

**Input:** `I want to book 3 rooms for a group of 10 people`

**Expected:** Should route to booking and handle multi-room request

**Response:** Thank you for choosing The Grand Horizon Hotel! To assist with your group booking for 3 rooms and 10 guests, could you please provide:

1. Your preferred check-in and check-out dates
2. Your preferred room type (Standard, Deluxe, Suite, or Penthouse)

Once I have these details, I can check availability and provide pricing for your group reservation.

**Scoring:** keywords=1/1, lang=ok, latency=5352ms
**Routing:** langgraph
**Latency:** 5352ms

---

### E04 [PASS] — Edge (EN)

**Input:** ``

**Expected:** Should handle empty message gracefully (422 or polite response)

**Response:** (empty)

**Scoring:** graceful error handling
**Routing:** validation_error
**Latency:** 5ms
**Error:** validation_error

---

## Disagreements (where models differ on pass/fail)

| ID | Category | Local | Cloud | Notes |
|---|---|---|---|---|
| G03 | Greeting | FAIL | PASS | Should acknowledge thanks politely |
| E03 | Edge | FAIL | PASS | Should route to booking and handle multi-room request |

## Infrastructure Test Results (Auth, Hardening, Audit, Scaling)

**Date:** 2026-04-06 16:24
**Total: 193/193 (100%)**

| Suite | Tests | Passed | Failed | Time |
|---|---|---|---|---|
| Auth Baseline | 72 | 72 | 0 | 4s |
| Auth Hardening | 38 | 38 | 0 | 10s |
| Audit + DB Scaling | 46 | 46 | 0 | 8s |
| Chat Scaling | 37 | 37 | 0 | 8s |
