#!/usr/bin/env python3
"""
Hotel AI Operations Assistant - Synthetic Hotel Dataset Generator

Generates realistic bilingual (Thai/English) hotel data:
- Guests with loyalty tiers and preferences
- Room types and rooms
- Reservations with various statuses
- Service requests and housekeeping tasks
- Hotel amenities and services

Usage:
    python scripts/generate_hotel_dataset.py

Environment variables:
    DATABASE_URL - PostgreSQL connection string
"""

import os
import random
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

import psycopg2
from psycopg2.extras import execute_values
from faker import Faker

# Initialize Faker for both English and Thai
fake_en = Faker('en_US')
fake_th = Faker('th_TH')

# Configuration
LOYALTY_TIERS = ['Standard', 'Silver', 'Gold', 'Platinum', 'Diamond']
ROOM_STATUSES = ['available', 'occupied', 'maintenance', 'cleaning']
RESERVATION_STATUSES = ['pending', 'confirmed', 'checked_in', 'checked_out', 'cancelled', 'no_show']
SERVICE_REQUEST_TYPES = [
    'Room Service', 'Extra Towels', 'Pillow Request', 'Maintenance',
    'Housekeeping', 'Wake-up Call', 'Transportation', 'Concierge',
    'Laundry', 'Mini Bar Refill'
]
SERVICE_REQUEST_TYPES_TH = [
    'บริการห้องพัก', 'ขอผ้าเช็ดตัวเพิ่ม', 'ขอหมอนเพิ่ม', 'แจ้งซ่อม',
    'แม่บ้าน', 'ปลุกตื่น', 'รถรับส่ง', 'บริการ Concierge',
    'ซักรีด', 'เติมมินิบาร์'
]
PRIORITIES = ['low', 'normal', 'high', 'urgent']
HOUSEKEEPING_TASKS = ['Daily Cleaning', 'Deep Clean', 'Turndown Service', 'Checkout Clean']
VIEW_TYPES = ['City View', 'Garden View', 'Pool View', 'Ocean View', 'Mountain View']

# Room type definitions (bilingual)
ROOM_TYPES = [
    {
        'name': 'Standard Room',
        'name_th': 'ห้องสแตนดาร์ด',
        'description': 'Comfortable room with essential amenities for a pleasant stay.',
        'description_th': 'ห้องพักสบายพร้อมสิ่งอำนวยความสะดวกครบครัน',
        'base_price': 2500.00,
        'max_occupancy': 2,
        'amenities': ['WiFi', 'TV', 'Air Conditioning', 'Mini Fridge', 'Safe Box']
    },
    {
        'name': 'Deluxe Room',
        'name_th': 'ห้องดีลักซ์',
        'description': 'Spacious room with premium amenities and city view.',
        'description_th': 'ห้องพักกว้างขวางพร้อมสิ่งอำนวยความสะดวกระดับพรีเมียม วิวเมือง',
        'base_price': 4500.00,
        'max_occupancy': 2,
        'amenities': ['WiFi', 'Smart TV', 'Air Conditioning', 'Mini Bar', 'Coffee Maker', 'City View', 'Bathtub']
    },
    {
        'name': 'Suite',
        'name_th': 'ห้องสวีท',
        'description': 'Luxurious suite with separate living area and premium services.',
        'description_th': 'ห้องสวีทหรูหราพร้อมพื้นที่นั่งเล่นแยกและบริการระดับพรีเมียม',
        'base_price': 8500.00,
        'max_occupancy': 4,
        'amenities': ['WiFi', 'Smart TV', 'Air Conditioning', 'Full Bar', 'Jacuzzi', 'Living Room', 'Balcony', 'Butler Service']
    },
    {
        'name': 'Penthouse',
        'name_th': 'ห้องเพนท์เฮาส์',
        'description': 'Ultimate luxury experience with panoramic views and exclusive amenities.',
        'description_th': 'ประสบการณ์หรูหราสูงสุดพร้อมวิวพาโนรามาและสิ่งอำนวยความสะดวกพิเศษ',
        'base_price': 25000.00,
        'max_occupancy': 6,
        'amenities': ['WiFi', 'Smart TV', 'Air Conditioning', 'Private Bar', 'Jacuzzi', 'Private Terrace', 'Butler Service', 'Private Chef']
    }
]

# Hotel services (bilingual)
HOTEL_SERVICES = [
    {'name': 'Spa & Wellness', 'name_th': 'สปาและเวลเนส', 'category': 'Wellness', 'price': 2500.00, 'hours': '9:00 AM - 9:00 PM', 'location': 'Level 3'},
    {'name': 'Fitness Center', 'name_th': 'ฟิตเนส', 'category': 'Wellness', 'price': 0.00, 'hours': '6:00 AM - 10:00 PM', 'location': 'Level 2'},
    {'name': 'Swimming Pool', 'name_th': 'สระว่ายน้ำ', 'category': 'Recreation', 'price': 0.00, 'hours': '7:00 AM - 9:00 PM', 'location': 'Rooftop'},
    {'name': 'Fine Dining Restaurant', 'name_th': 'ร้านอาหารหรู', 'category': 'Dining', 'price': None, 'hours': '6:00 PM - 11:00 PM', 'location': 'Level 1'},
    {'name': 'Breakfast Buffet', 'name_th': 'บุฟเฟ่ต์อาหารเช้า', 'category': 'Dining', 'price': 850.00, 'hours': '6:30 AM - 10:30 AM', 'location': 'Level 1'},
    {'name': 'Room Service', 'name_th': 'บริการห้องพัก', 'category': 'Dining', 'price': None, 'hours': '24 Hours', 'location': 'In-Room'},
    {'name': 'Business Center', 'name_th': 'ศูนย์ธุรกิจ', 'category': 'Business', 'price': 0.00, 'hours': '24 Hours', 'location': 'Lobby Level'},
    {'name': 'Concierge', 'name_th': 'บริการ Concierge', 'category': 'Services', 'price': 0.00, 'hours': '24 Hours', 'location': 'Lobby'},
    {'name': 'Valet Parking', 'name_th': 'บริการจอดรถ', 'category': 'Transportation', 'price': 500.00, 'hours': '24 Hours', 'location': 'Entrance'},
    {'name': 'Airport Shuttle', 'name_th': 'รถรับส่งสนามบิน', 'category': 'Transportation', 'price': 1200.00, 'hours': '5:00 AM - 11:00 PM', 'location': 'Lobby'},
    {'name': 'Laundry Service', 'name_th': 'บริการซักรีด', 'category': 'Services', 'price': None, 'hours': '7:00 AM - 8:00 PM', 'location': 'In-Room'},
    {'name': 'Kids Club', 'name_th': 'คิดส์คลับ', 'category': 'Recreation', 'price': 0.00, 'hours': '9:00 AM - 6:00 PM', 'location': 'Level 2'},
]

# Thai first names and last names
THAI_FIRST_NAMES = ['สมชาย', 'สมหญิง', 'ประเสริฐ', 'พรทิพย์', 'วิชัย', 'สุภาพร', 'อนุชา', 'นภาพร', 'ธนกร', 'ปิยะ']
THAI_LAST_NAMES = ['สุขใจ', 'มั่งมี', 'ใจดี', 'รักษ์ดี', 'สว่างวงศ์', 'เจริญสุข', 'พงษ์ไพศาล', 'วัฒนา', 'ศรีสุข', 'พิมพ์ทอง']


def generate_guest_preferences() -> Dict[str, Any]:
    """Generate random guest preferences."""
    preferences = {
        'room_temperature': random.choice(['cool', 'moderate', 'warm']),
        'pillow_type': random.choice(['soft', 'firm', 'hypoallergenic']),
        'newspaper': random.choice([None, 'Bangkok Post', 'The Nation', 'Local Thai']),
        'dietary_restrictions': random.choice([None, 'vegetarian', 'vegan', 'halal', 'kosher']),
        'floor_preference': random.choice(['low', 'high', 'no preference']),
        'quiet_room': random.choice([True, False]),
        'smoking': random.choice([True, False]),
        'early_checkin': random.choice([True, False]),
        'late_checkout': random.choice([True, False]),
    }
    return {k: v for k, v in preferences.items() if v is not None}


def get_db_connection():
    """Get database connection from environment."""
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url)

    # Fallback to individual params
    return psycopg2.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.getenv('POSTGRES_DB', 'railway'),
        user=os.getenv('POSTGRES_USER', 'postgres'),
        password=os.getenv('POSTGRES_PASSWORD', 'password')
    )


def create_tables(cur):
    """Create hotel tables if they don't exist."""
    print("Creating tables...")

    # Read and execute the SQL file
    sql_path = os.path.join(os.path.dirname(__file__), '..', 'deploy', 'compose', 'init-scripts', 'init-hotel.sql')

    if os.path.exists(sql_path):
        with open(sql_path, 'r') as f:
            sql = f.read()
        cur.execute(sql)
        print("  Tables created from init-hotel.sql")
    else:
        print(f"  Warning: {sql_path} not found, tables should already exist")


def generate_room_types(cur) -> List[int]:
    """Generate room type records and return IDs."""
    print("Generating room types...")

    room_type_ids = []
    for room_type in ROOM_TYPES:
        cur.execute("""
            INSERT INTO room_types (name, name_th, description, description_th, base_price, max_occupancy, amenities)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            RETURNING room_type_id
        """, (
            room_type['name'],
            room_type['name_th'],
            room_type['description'],
            room_type['description_th'],
            room_type['base_price'],
            room_type['max_occupancy'],
            json.dumps(room_type['amenities'])
        ))
        result = cur.fetchone()
        if result:
            room_type_ids.append(result[0])

    if not room_type_ids:
        cur.execute("SELECT room_type_id FROM room_types")
        room_type_ids = [row[0] for row in cur.fetchall()]

    print(f"  Created/found {len(room_type_ids)} room types")
    return room_type_ids


def generate_rooms(cur, room_type_ids: List[int], num_floors: int = 10, rooms_per_floor: int = 15) -> List[int]:
    """Generate room records."""
    print(f"Generating rooms ({num_floors} floors x {rooms_per_floor} rooms)...")

    room_ids = []
    for floor in range(1, num_floors + 1):
        for room_num in range(1, rooms_per_floor + 1):
            room_number = f"{floor}{room_num:02d}"

            # Higher floors have better room types
            if floor >= 9:
                room_type_id = room_type_ids[3] if len(room_type_ids) > 3 else room_type_ids[-1]
            elif floor >= 7:
                room_type_id = room_type_ids[2] if len(room_type_ids) > 2 else room_type_ids[-1]
            elif floor >= 4:
                room_type_id = room_type_ids[1] if len(room_type_ids) > 1 else room_type_ids[0]
            else:
                room_type_id = room_type_ids[0]

            status = random.choices(ROOM_STATUSES, weights=[70, 20, 5, 5])[0]
            view_type = random.choice(VIEW_TYPES)
            last_cleaned = datetime.now() - timedelta(hours=random.randint(1, 48))

            cur.execute("""
                INSERT INTO rooms (room_number, room_type_id, floor, status, view_type, last_cleaned)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (room_number) DO NOTHING
                RETURNING room_id
            """, (room_number, room_type_id, floor, status, view_type, last_cleaned))

            result = cur.fetchone()
            if result:
                room_ids.append(result[0])

    if not room_ids:
        cur.execute("SELECT room_id FROM rooms")
        room_ids = [row[0] for row in cur.fetchall()]

    print(f"  Created/found {len(room_ids)} rooms")
    return room_ids


def generate_guests(cur, num_guests: int = 100) -> List[int]:
    """Generate guest records."""
    print(f"Generating {num_guests} guests...")

    guest_ids = []
    for i in range(num_guests):
        tier = random.choices(LOYALTY_TIERS, weights=[50, 25, 15, 7, 3])[0]
        points = random.randint(0, 10000) if tier != 'Standard' else random.randint(0, 1000)

        # Mix of Thai and international guests
        if random.random() < 0.6:  # 60% Thai guests
            first_name = fake_en.first_name()
            last_name = fake_en.last_name()
            first_name_th = random.choice(THAI_FIRST_NAMES)
            last_name_th = random.choice(THAI_LAST_NAMES)
            nationality = 'Thai'
        else:
            first_name = fake_en.first_name()
            last_name = fake_en.last_name()
            first_name_th = None
            last_name_th = None
            nationality = random.choice(['USA', 'UK', 'Japan', 'China', 'Singapore', 'Australia', 'Germany', 'France'])

        email = f"{first_name.lower()}.{last_name.lower()}{random.randint(1, 999)}@{fake_en.free_email_domain()}"

        cur.execute("""
            INSERT INTO guests (first_name, last_name, first_name_th, last_name_th, email, phone, nationality, loyalty_tier, loyalty_points, preferences)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (email) DO NOTHING
            RETURNING guest_id
        """, (
            first_name,
            last_name,
            first_name_th,
            last_name_th,
            email,
            fake_en.phone_number()[:20],
            nationality,
            tier,
            points,
            json.dumps(generate_guest_preferences())
        ))

        result = cur.fetchone()
        if result:
            guest_ids.append(result[0])

    if not guest_ids:
        cur.execute("SELECT guest_id FROM guests LIMIT %s", (num_guests,))
        guest_ids = [row[0] for row in cur.fetchall()]

    print(f"  Created/found {len(guest_ids)} guests")
    return guest_ids


def generate_reservations(cur, guest_ids: List[int], room_ids: List[int], num_reservations: int = 300) -> List[int]:
    """Generate reservation records."""
    print(f"Generating {num_reservations} reservations...")

    # Get room prices
    cur.execute("""
        SELECT r.room_id, rt.base_price
        FROM rooms r
        JOIN room_types rt ON r.room_type_id = rt.room_type_id
    """)
    room_prices = {row[0]: row[1] for row in cur.fetchall()}

    special_requests_options = [
        "Early check-in requested",
        "Late check-out needed",
        "Anniversary celebration - please arrange flowers",
        "Honeymoon - special setup requested",
        "Allergic to feathers - need hypoallergenic pillows",
        "Business traveler - need quiet room",
        "Traveling with infant - need crib",
        "Wheelchair accessible room required",
        "ขอเช็คอินก่อนเวลา",
        "ขอเช็คเอาท์ช้า",
        "วันครบรอบแต่งงาน ขอจัดดอกไม้",
        "ฮันนีมูน ขอจัดห้องพิเศษ",
        None
    ]

    booking_sources = ['Direct', 'Booking.com', 'Agoda', 'Expedia', 'Hotels.com', 'Corporate', 'Travel Agent', 'Walk-in']

    reservation_ids = []
    for _ in range(num_reservations):
        guest_id = random.choice(guest_ids)
        room_id = random.choice(room_ids)

        # Generate dates (past, present, and future reservations)
        days_offset = random.randint(-60, 60)
        check_in = datetime.now().date() + timedelta(days=days_offset)
        stay_length = random.randint(1, 7)
        check_out = check_in + timedelta(days=stay_length)

        # Status based on dates
        today = datetime.now().date()
        if check_out < today:
            status = random.choices(['checked_out', 'cancelled', 'no_show'], weights=[80, 15, 5])[0]
        elif check_in <= today <= check_out:
            status = 'checked_in'
        elif check_in > today:
            status = random.choices(['confirmed', 'pending', 'cancelled'], weights=[70, 20, 10])[0]
        else:
            status = 'confirmed'

        base_price = float(room_prices.get(room_id, 2500))
        total_amount = base_price * stay_length * random.uniform(0.9, 1.2)

        payment_status = 'paid' if status in ['checked_out', 'checked_in'] else random.choice(['pending', 'partial', 'paid'])
        num_guests = random.randint(1, 4)

        cancellation_reason = None
        if status == 'cancelled':
            cancellation_reason = random.choice([
                'Change of plans',
                'Found better rate elsewhere',
                'Flight cancelled',
                'Medical emergency',
                'เปลี่ยนแผนการเดินทาง',
                'พบราคาดีกว่า'
            ])

        cur.execute("""
            INSERT INTO reservations
            (guest_id, room_id, check_in_date, check_out_date, num_guests, status, total_amount, payment_status, special_requests, booking_source, cancellation_reason)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING reservation_id
        """, (
            guest_id, room_id, check_in, check_out, num_guests, status,
            round(total_amount, 2), payment_status,
            random.choice(special_requests_options),
            random.choice(booking_sources),
            cancellation_reason
        ))

        result = cur.fetchone()
        if result:
            reservation_ids.append(result[0])

    print(f"  Created {len(reservation_ids)} reservations")
    return reservation_ids


def generate_service_requests(cur, reservation_ids: List[int], guest_ids: List[int], num_requests: int = 150):
    """Generate service request records."""
    print(f"Generating {num_requests} service requests...")

    staff_names = [fake_en.name() for _ in range(10)]

    count = 0
    for _ in range(num_requests):
        reservation_id = random.choice(reservation_ids) if reservation_ids else None
        guest_id = random.choice(guest_ids)

        request_idx = random.randint(0, len(SERVICE_REQUEST_TYPES) - 1)
        request_type = SERVICE_REQUEST_TYPES[request_idx]
        request_type_th = SERVICE_REQUEST_TYPES_TH[request_idx]

        priority = random.choices(PRIORITIES, weights=[30, 50, 15, 5])[0]
        status = random.choices(['pending', 'in_progress', 'completed', 'cancelled'], weights=[30, 25, 40, 5])[0]

        created_at = datetime.now() - timedelta(hours=random.randint(0, 72))
        resolved_at = created_at + timedelta(hours=random.randint(1, 4)) if status == 'completed' else None

        description = fake_en.sentence()
        description_th = f"ขอ{request_type_th}" if random.random() < 0.5 else None

        cur.execute("""
            INSERT INTO service_requests
            (reservation_id, guest_id, request_type, description, description_th, status, priority, assigned_to, created_at, resolved_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            reservation_id, guest_id, request_type,
            description, description_th,
            status, priority,
            random.choice(staff_names) if status != 'pending' else None,
            created_at, resolved_at
        ))
        count += 1

    print(f"  Created {count} service requests")


def generate_housekeeping(cur, room_ids: List[int], num_tasks: int = 200):
    """Generate housekeeping task records."""
    print(f"Generating {num_tasks} housekeeping tasks...")

    staff_names = [fake_en.name() for _ in range(15)]

    for _ in range(num_tasks):
        room_id = random.choice(room_ids)
        task_type = random.choice(HOUSEKEEPING_TASKS)
        status = random.choices(['pending', 'in_progress', 'completed'], weights=[30, 20, 50])[0]

        scheduled_date = datetime.now().date() + timedelta(days=random.randint(-3, 3))
        completed_at = datetime.now() - timedelta(hours=random.randint(0, 24)) if status == 'completed' else None

        cur.execute("""
            INSERT INTO housekeeping
            (room_id, task_type, status, assigned_to, scheduled_date, completed_at, notes)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            room_id, task_type, status,
            random.choice(staff_names),
            scheduled_date, completed_at,
            fake_en.sentence() if random.random() > 0.7 else None
        ))

    print(f"  Created {num_tasks} housekeeping tasks")


def generate_hotel_services(cur):
    """Generate hotel services records."""
    print("Generating hotel services...")

    for service in HOTEL_SERVICES:
        description = fake_en.paragraph()
        description_th = f"{service['name_th']} - บริการคุณภาพระดับพรีเมียม"

        cur.execute("""
            INSERT INTO hotel_services (name, name_th, category, description, description_th, price, availability_hours, location, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            service['name'],
            service['name_th'],
            service['category'],
            description,
            description_th,
            service['price'],
            service['hours'],
            service['location'],
            True
        ))

    print(f"  Created {len(HOTEL_SERVICES)} hotel services")


def print_summary(cur):
    """Print summary of generated data."""
    print("\n" + "=" * 60)
    print("Dataset Summary")
    print("=" * 60)

    tables = ['room_types', 'rooms', 'guests', 'reservations', 'service_requests', 'housekeeping', 'hotel_services']
    for table in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM {table}")
            count = cur.fetchone()[0]
            print(f"  {table}: {count} records")
        except Exception as e:
            print(f"  {table}: Error - {e}")


def main():
    print("\n" + "=" * 60)
    print("Hotel Dataset Generator")
    print("=" * 60)
    print(f"Database: {os.getenv('POSTGRES_HOST', 'localhost')}:{os.getenv('POSTGRES_PORT', '5432')}")
    print()

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Create tables
        create_tables(cur)
        conn.commit()

        # Generate data
        room_type_ids = generate_room_types(cur)
        conn.commit()

        room_ids = generate_rooms(cur, room_type_ids)
        conn.commit()

        guest_ids = generate_guests(cur, num_guests=100)
        conn.commit()

        generate_hotel_services(cur)
        conn.commit()

        reservation_ids = generate_reservations(cur, guest_ids, room_ids, num_reservations=300)
        conn.commit()

        generate_service_requests(cur, reservation_ids, guest_ids, num_requests=150)
        conn.commit()

        generate_housekeeping(cur, room_ids, num_tasks=200)
        conn.commit()

        print_summary(cur)

        print("\n" + "=" * 60)
        print("Dataset generation completed successfully!")
        print("=" * 60)

    except Exception as e:
        print(f"\nError: {e}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
