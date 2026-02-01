# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Hotel Agent Tools - Full CRUD Operations for Booking Management

Provides LangChain tools for:
- Checking room availability
- Creating, confirming, updating, and canceling reservations
- Managing service requests
- Guest check-in/check-out operations

All tools connect to the Railway PostgreSQL database.
"""

import os
import logging
import time
from datetime import datetime, timedelta
from typing import Optional
from functools import lru_cache
from urllib.parse import urlparse

import psycopg2
import psycopg2.extras
from pydantic import BaseModel, Field
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Import audit logger
try:
    from src.common.audit_logger import get_audit_logger
except ImportError:
    get_audit_logger = None


def get_db_connection():
    """Get database connection from environment."""
    database_url = os.getenv('DATABASE_URL')
    if database_url:
        return psycopg2.connect(database_url)

    # Fallback to individual params
    host = os.getenv('POSTGRES_HOST', 'localhost')
    port = os.getenv('POSTGRES_PORT', '5432')
    dbname = os.getenv('POSTGRES_DB', 'railway')
    user = os.getenv('POSTGRES_USER', 'postgres')
    password = os.getenv('POSTGRES_PASSWORD', 'password')

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password
    )


# =============================================================================
# READ Operations
# =============================================================================

@tool
def check_room_availability(check_in_date: str, check_out_date: str, room_type: Optional[str] = None) -> str:
    """
    Check available rooms for given dates and optionally filter by room type.

    Args:
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        room_type: Optional room type filter (Standard, Deluxe, Suite, Penthouse)

    Returns:
        List of available rooms with details
    """
    try:
        query = """
        SELECT r.room_id, r.room_number, r.floor, r.view_type,
               rt.name as room_type, rt.name_th, rt.base_price, rt.max_occupancy,
               rt.amenities
        FROM rooms r
        JOIN room_types rt ON r.room_type_id = rt.room_type_id
        WHERE r.status = 'available'
        AND r.room_id NOT IN (
            SELECT room_id FROM reservations
            WHERE status NOT IN ('cancelled', 'no_show', 'checked_out')
            AND check_in_date < %s AND check_out_date > %s
        )
        """

        params = [check_out_date, check_in_date]

        if room_type:
            query += " AND LOWER(rt.name) LIKE LOWER(%s)"
            params.append(f"%{room_type}%")

        query += " ORDER BY rt.base_price, r.floor, r.room_number LIMIT 10"

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, params)
                rooms = cur.fetchall()

        if not rooms:
            return f"ไม่พบห้องว่างสำหรับวันที่ {check_in_date} ถึง {check_out_date} / No rooms available for {check_in_date} to {check_out_date}"

        result = f"ห้องว่างสำหรับ {check_in_date} - {check_out_date}:\n\n"
        for room in rooms:
            nights = (datetime.strptime(check_out_date, '%Y-%m-%d') - datetime.strptime(check_in_date, '%Y-%m-%d')).days
            total = float(room['base_price']) * nights
            result += f"- ห้อง {room['room_number']} ({room['room_type']} / {room['name_th']})\n"
            result += f"  ชั้น {room['floor']}, {room['view_type']}\n"
            result += f"  ราคา: {room['base_price']:,.0f} บาท/คืน (รวม {total:,.0f} บาท {nights} คืน)\n"
            result += f"  รองรับ: {room['max_occupancy']} ท่าน\n\n"

        return result

    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


@tool
def get_reservation_details(reservation_id: str) -> str:
    """
    Get details of a specific reservation by ID or confirmation number.

    Args:
        reservation_id: Reservation ID or confirmation number (e.g., HTL240215001)

    Returns:
        Detailed reservation information
    """
    try:
        query = """
        SELECT res.reservation_id, res.confirmation_number, res.check_in_date, res.check_out_date,
               res.num_guests, res.status, res.total_amount, res.payment_status,
               res.special_requests, res.booking_source, res.cancellation_reason,
               r.room_number, rt.name as room_type, rt.name_th,
               g.first_name, g.last_name, g.first_name_th, g.last_name_th, g.email, g.phone
        FROM reservations res
        JOIN rooms r ON res.room_id = r.room_id
        JOIN room_types rt ON r.room_type_id = rt.room_type_id
        JOIN guests g ON res.guest_id = g.guest_id
        WHERE res.reservation_id::text = %s OR res.confirmation_number = %s
        """

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, (reservation_id, reservation_id))
                res = cur.fetchone()

        if not res:
            return f"ไม่พบการจองหมายเลข {reservation_id} / Reservation {reservation_id} not found"

        guest_name = f"{res['first_name']} {res['last_name']}"
        if res['first_name_th']:
            guest_name += f" ({res['first_name_th']} {res['last_name_th']})"

        result = f"""
รายละเอียดการจอง / Reservation Details:
==========================================
หมายเลขยืนยัน: {res['confirmation_number']}
สถานะ: {res['status']}

ผู้เข้าพัก: {guest_name}
อีเมล: {res['email']}
โทร: {res['phone']}

ห้อง: {res['room_number']} ({res['room_type']} / {res['name_th']})
เช็คอิน: {res['check_in_date']}
เช็คเอาท์: {res['check_out_date']}
จำนวนผู้เข้าพัก: {res['num_guests']} ท่าน

ยอดรวม: {res['total_amount']:,.0f} บาท
สถานะการชำระ: {res['payment_status']}

ความต้องการพิเศษ: {res['special_requests'] or '-'}
"""

        if res['cancellation_reason']:
            result += f"\nเหตุผลยกเลิก: {res['cancellation_reason']}"

        return result

    except Exception as e:
        logger.error(f"Error getting reservation details: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


@tool
def get_guest_reservations(guest_email: str) -> str:
    """
    Get all reservations for a guest by email.

    Args:
        guest_email: Guest's email address

    Returns:
        List of guest's reservations
    """
    try:
        query = """
        SELECT res.reservation_id, res.confirmation_number, res.check_in_date, res.check_out_date,
               res.status, res.total_amount, r.room_number, rt.name as room_type
        FROM reservations res
        JOIN rooms r ON res.room_id = r.room_id
        JOIN room_types rt ON r.room_type_id = rt.room_type_id
        JOIN guests g ON res.guest_id = g.guest_id
        WHERE LOWER(g.email) = LOWER(%s)
        ORDER BY res.check_in_date DESC
        LIMIT 10
        """

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query, (guest_email,))
                reservations = cur.fetchall()

        if not reservations:
            return f"ไม่พบการจองสำหรับ {guest_email}"

        result = f"การจองของ {guest_email}:\n\n"
        for res in reservations:
            result += f"- {res['confirmation_number']} | {res['room_type']} ห้อง {res['room_number']}\n"
            result += f"  {res['check_in_date']} - {res['check_out_date']} | {res['status']}\n"
            result += f"  ยอด: {res['total_amount']:,.0f} บาท\n\n"

        return result

    except Exception as e:
        logger.error(f"Error getting guest reservations: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


@tool
def get_hotel_services() -> str:
    """
    Get list of available hotel services and amenities.

    Returns:
        List of hotel services with prices and hours
    """
    try:
        query = """
        SELECT name, name_th, category, price, availability_hours, location
        FROM hotel_services
        WHERE is_active = true
        ORDER BY category, name
        """

        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute(query)
                services = cur.fetchall()

        if not services:
            return "ไม่พบข้อมูลบริการ"

        result = "บริการของโรงแรม / Hotel Services:\n\n"
        current_category = None

        for svc in services:
            if svc['category'] != current_category:
                current_category = svc['category']
                result += f"\n=== {current_category} ===\n"

            price_str = f"{svc['price']:,.0f} บาท" if svc['price'] else "ฟรี / Free"
            result += f"- {svc['name']} ({svc['name_th']})\n"
            result += f"  ราคา: {price_str} | เวลา: {svc['availability_hours']} | ที่: {svc['location']}\n"

        return result

    except Exception as e:
        logger.error(f"Error getting hotel services: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


# =============================================================================
# CREATE Operations
# =============================================================================

@tool
def create_reservation(
    guest_email: str,
    room_number: str,
    check_in_date: str,
    check_out_date: str,
    num_guests: int = 1,
    special_requests: Optional[str] = None
) -> str:
    """
    Create a new room reservation.

    Args:
        guest_email: Guest's email address (must be registered)
        room_number: Room number to book (e.g., "501")
        check_in_date: Check-in date (YYYY-MM-DD)
        check_out_date: Check-out date (YYYY-MM-DD)
        num_guests: Number of guests (default 1)
        special_requests: Special requests or notes

    Returns:
        Confirmation number and booking details
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Get guest ID
                cur.execute("SELECT guest_id FROM guests WHERE LOWER(email) = LOWER(%s)", (guest_email,))
                guest = cur.fetchone()
                if not guest:
                    return f"ไม่พบผู้เข้าพักอีเมล {guest_email} กรุณาลงทะเบียนก่อน"

                guest_id = guest['guest_id']

                # Get room ID and price
                cur.execute("""
                    SELECT r.room_id, rt.base_price, rt.name, rt.max_occupancy
                    FROM rooms r
                    JOIN room_types rt ON r.room_type_id = rt.room_type_id
                    WHERE r.room_number = %s
                """, (room_number,))
                room = cur.fetchone()
                if not room:
                    return f"ไม่พบห้อง {room_number}"

                if num_guests > room['max_occupancy']:
                    return f"ห้อง {room_number} รองรับได้สูงสุด {room['max_occupancy']} ท่าน"

                # Check availability
                cur.execute("""
                    SELECT reservation_id FROM reservations
                    WHERE room_id = %s
                    AND status NOT IN ('cancelled', 'no_show', 'checked_out')
                    AND check_in_date < %s AND check_out_date > %s
                """, (room['room_id'], check_out_date, check_in_date))

                if cur.fetchone():
                    return f"ห้อง {room_number} ไม่ว่างในวันที่ระบุ"

                # Calculate total
                nights = (datetime.strptime(check_out_date, '%Y-%m-%d') - datetime.strptime(check_in_date, '%Y-%m-%d')).days
                total_amount = float(room['base_price']) * nights

                # Create reservation
                cur.execute("""
                    INSERT INTO reservations
                    (guest_id, room_id, check_in_date, check_out_date, num_guests, status, total_amount, payment_status, special_requests, booking_source)
                    VALUES (%s, %s, %s, %s, %s, 'pending', %s, 'pending', %s, 'AI Assistant')
                    RETURNING reservation_id, confirmation_number
                """, (guest_id, room['room_id'], check_in_date, check_out_date, num_guests, total_amount, special_requests))

                result = cur.fetchone()
                conn.commit()

                return f"""
การจองสำเร็จ! / Booking Created!
==========================================
หมายเลขยืนยัน: {result['confirmation_number']}
ห้อง: {room_number} ({room['name']})
วันที่: {check_in_date} - {check_out_date} ({nights} คืน)
จำนวนผู้เข้าพัก: {num_guests} ท่าน
ยอดรวม: {total_amount:,.0f} บาท

สถานะ: รอการยืนยัน (Pending)
กรุณายืนยันการจองเพื่อดำเนินการต่อ
"""

    except Exception as e:
        logger.error(f"Error creating reservation: {e}")
        return f"เกิดข้อผิดพลาดในการจอง: {str(e)}"


@tool
def confirm_reservation(reservation_id: str) -> str:
    """
    Confirm a pending reservation.

    Args:
        reservation_id: Reservation ID or confirmation number

    Returns:
        Confirmation status
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    UPDATE reservations
                    SET status = 'confirmed', updated_at = CURRENT_TIMESTAMP
                    WHERE (reservation_id::text = %s OR confirmation_number = %s)
                    AND status = 'pending'
                    RETURNING confirmation_number, check_in_date, check_out_date
                """, (reservation_id, reservation_id))

                result = cur.fetchone()
                conn.commit()

                if not result:
                    return f"ไม่พบการจองที่รอยืนยัน หมายเลข {reservation_id}"

                return f"""
ยืนยันการจองสำเร็จ! / Reservation Confirmed!
==========================================
หมายเลขยืนยัน: {result['confirmation_number']}
วันเช็คอิน: {result['check_in_date']}
วันเช็คเอาท์: {result['check_out_date']}

สถานะ: ยืนยันแล้ว (Confirmed)
ขอบคุณที่ใช้บริการครับ/ค่ะ
"""

    except Exception as e:
        logger.error(f"Error confirming reservation: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


@tool
def create_service_request(
    reservation_id: str,
    request_type: str,
    description: str
) -> str:
    """
    Create a service request for a reservation.

    Args:
        reservation_id: Reservation ID or confirmation number
        request_type: Type of request (e.g., Room Service, Extra Towels, Maintenance)
        description: Description of the request

    Returns:
        Service request confirmation
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Get reservation and guest
                cur.execute("""
                    SELECT reservation_id, guest_id FROM reservations
                    WHERE reservation_id::text = %s OR confirmation_number = %s
                """, (reservation_id, reservation_id))
                res = cur.fetchone()

                if not res:
                    return f"ไม่พบการจองหมายเลข {reservation_id}"

                cur.execute("""
                    INSERT INTO service_requests
                    (reservation_id, guest_id, request_type, description, status, priority)
                    VALUES (%s, %s, %s, %s, 'pending', 'normal')
                    RETURNING request_id
                """, (res['reservation_id'], res['guest_id'], request_type, description))

                result = cur.fetchone()
                conn.commit()

                return f"""
บันทึกคำขอบริการแล้ว / Service Request Created!
==========================================
หมายเลขคำขอ: {result['request_id']}
ประเภท: {request_type}
รายละเอียด: {description}

สถานะ: รอดำเนินการ
ทีมงานจะติดต่อกลับโดยเร็ว
"""

    except Exception as e:
        logger.error(f"Error creating service request: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


# =============================================================================
# UPDATE Operations
# =============================================================================

@tool
def update_reservation(
    reservation_id: str,
    check_in_date: Optional[str] = None,
    check_out_date: Optional[str] = None,
    room_number: Optional[str] = None,
    num_guests: Optional[int] = None,
    special_requests: Optional[str] = None
) -> str:
    """
    Update an existing reservation.

    Args:
        reservation_id: Reservation ID or confirmation number
        check_in_date: New check-in date (YYYY-MM-DD)
        check_out_date: New check-out date (YYYY-MM-DD)
        room_number: New room number
        num_guests: New number of guests
        special_requests: Updated special requests

    Returns:
        Updated reservation details
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                # Get current reservation
                cur.execute("""
                    SELECT res.*, r.room_number, rt.base_price
                    FROM reservations res
                    JOIN rooms r ON res.room_id = r.room_id
                    JOIN room_types rt ON r.room_type_id = rt.room_type_id
                    WHERE res.reservation_id::text = %s OR res.confirmation_number = %s
                """, (reservation_id, reservation_id))
                current = cur.fetchone()

                if not current:
                    return f"ไม่พบการจองหมายเลข {reservation_id}"

                if current['status'] in ['checked_out', 'cancelled']:
                    return f"ไม่สามารถแก้ไขการจองที่ {current['status']} แล้ว"

                # Prepare updates
                new_check_in = check_in_date or str(current['check_in_date'])
                new_check_out = check_out_date or str(current['check_out_date'])
                new_room_id = current['room_id']
                new_base_price = float(current['base_price'])

                # If changing room
                if room_number and room_number != current['room_number']:
                    cur.execute("""
                        SELECT r.room_id, rt.base_price
                        FROM rooms r
                        JOIN room_types rt ON r.room_type_id = rt.room_type_id
                        WHERE r.room_number = %s
                    """, (room_number,))
                    new_room = cur.fetchone()
                    if not new_room:
                        return f"ไม่พบห้อง {room_number}"
                    new_room_id = new_room['room_id']
                    new_base_price = float(new_room['base_price'])

                # Recalculate total
                nights = (datetime.strptime(new_check_out, '%Y-%m-%d') - datetime.strptime(new_check_in, '%Y-%m-%d')).days
                new_total = new_base_price * nights

                # Update
                cur.execute("""
                    UPDATE reservations
                    SET check_in_date = %s,
                        check_out_date = %s,
                        room_id = %s,
                        num_guests = COALESCE(%s, num_guests),
                        special_requests = COALESCE(%s, special_requests),
                        total_amount = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE reservation_id = %s
                    RETURNING confirmation_number
                """, (new_check_in, new_check_out, new_room_id, num_guests, special_requests, new_total, current['reservation_id']))

                result = cur.fetchone()
                conn.commit()

                return f"""
แก้ไขการจองสำเร็จ! / Reservation Updated!
==========================================
หมายเลขยืนยัน: {result['confirmation_number']}
วันใหม่: {new_check_in} - {new_check_out} ({nights} คืน)
ยอดใหม่: {new_total:,.0f} บาท
"""

    except Exception as e:
        logger.error(f"Error updating reservation: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


@tool
def check_in_guest(reservation_id: str) -> str:
    """
    Check in a guest with a confirmed reservation.

    Args:
        reservation_id: Reservation ID or confirmation number

    Returns:
        Check-in confirmation
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    UPDATE reservations
                    SET status = 'checked_in', updated_at = CURRENT_TIMESTAMP
                    WHERE (reservation_id::text = %s OR confirmation_number = %s)
                    AND status = 'confirmed'
                    RETURNING confirmation_number, room_id
                """, (reservation_id, reservation_id))

                result = cur.fetchone()

                if not result:
                    return f"ไม่พบการจองที่ยืนยันแล้วหมายเลข {reservation_id}"

                # Update room status
                cur.execute("""
                    UPDATE rooms SET status = 'occupied' WHERE room_id = %s
                """, (result['room_id'],))

                conn.commit()

                return f"""
เช็คอินสำเร็จ! / Check-in Complete!
==========================================
หมายเลขยืนยัน: {result['confirmation_number']}
สถานะ: เช็คอินแล้ว (Checked In)

ยินดีต้อนรับสู่โรงแรมครับ/ค่ะ!
Welcome to our hotel!
"""

    except Exception as e:
        logger.error(f"Error checking in guest: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


@tool
def check_out_guest(reservation_id: str) -> str:
    """
    Check out a guest.

    Args:
        reservation_id: Reservation ID or confirmation number

    Returns:
        Check-out confirmation with final bill
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    UPDATE reservations
                    SET status = 'checked_out', payment_status = 'paid', updated_at = CURRENT_TIMESTAMP
                    WHERE (reservation_id::text = %s OR confirmation_number = %s)
                    AND status = 'checked_in'
                    RETURNING confirmation_number, room_id, total_amount
                """, (reservation_id, reservation_id))

                result = cur.fetchone()

                if not result:
                    return f"ไม่พบการจองที่เช็คอินแล้วหมายเลข {reservation_id}"

                # Update room status
                cur.execute("""
                    UPDATE rooms SET status = 'cleaning' WHERE room_id = %s
                """, (result['room_id'],))

                conn.commit()

                return f"""
เช็คเอาท์สำเร็จ! / Check-out Complete!
==========================================
หมายเลขยืนยัน: {result['confirmation_number']}
ยอดชำระ: {result['total_amount']:,.0f} บาท
สถานะ: เช็คเอาท์แล้ว (Checked Out)

ขอบคุณที่ใช้บริการ หวังว่าจะได้ต้อนรับอีกครั้งครับ/ค่ะ
Thank you for staying with us!
"""

    except Exception as e:
        logger.error(f"Error checking out guest: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


# =============================================================================
# CANCEL Operations
# =============================================================================

@tool
def cancel_reservation(reservation_id: str, reason: str) -> str:
    """
    Cancel a reservation.

    Args:
        reservation_id: Reservation ID or confirmation number
        reason: Reason for cancellation

    Returns:
        Cancellation confirmation
    """
    try:
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    UPDATE reservations
                    SET status = 'cancelled',
                        cancellation_reason = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE (reservation_id::text = %s OR confirmation_number = %s)
                    AND status IN ('pending', 'confirmed')
                    RETURNING confirmation_number, check_in_date, total_amount
                """, (reason, reservation_id, reservation_id))

                result = cur.fetchone()
                conn.commit()

                if not result:
                    return f"ไม่พบการจองที่สามารถยกเลิกได้หมายเลข {reservation_id}"

                return f"""
ยกเลิกการจองสำเร็จ / Reservation Cancelled
==========================================
หมายเลขยืนยัน: {result['confirmation_number']}
วันเช็คอินเดิม: {result['check_in_date']}
เหตุผล: {reason}

สถานะ: ยกเลิกแล้ว (Cancelled)

หากต้องการจองใหม่ สามารถแจ้งได้ตลอดเวลาครับ/ค่ะ
"""

    except Exception as e:
        logger.error(f"Error cancelling reservation: {e}")
        return f"เกิดข้อผิดพลาด: {str(e)}"


# =============================================================================
# RAG Operations - Hotel Knowledge Search
# =============================================================================

# NOTE: No hardcoded fallback knowledge - all information must come from
# the RAG knowledge base (Qdrant) to ensure accuracy and consistency.
# If RAG fails, we inform the guest to contact Front Desk.


@tool
def search_hotel_knowledge(query: str) -> str:
    """
    Search hotel knowledge base for information about facilities,
    services, policies, and amenities.

    Use this tool when guests ask about:
    - Breakfast/dining hours and locations
    - WiFi password and internet access
    - Spa services and treatments
    - Swimming pool and gym hours
    - Hotel policies (cancellation, pets, smoking)
    - Check-in/check-out times
    - Room amenities and features
    - Local attractions and transportation

    Args:
        query: The guest's question in Thai or English

    Returns:
        Relevant information from hotel knowledge base
    """
    try:
        from src.retrievers.hotel_knowledge.chains import HotelKnowledgeRetriever

        retriever = HotelKnowledgeRetriever()
        results = retriever.document_search(query, num_docs=3)

        if results:
            # Format results from RAG
            response_parts = []
            for r in results:
                response_parts.append(r["content"])
            return "\n\n---\n\n".join(response_parts)

        # No results found in knowledge base
        logger.warning(f"No RAG results found for query: {query}")
        return (
            "ขออภัยค่ะ ไม่พบข้อมูลที่ต้องการในระบบ กรุณาติดต่อ Front Desk โทร 0 เพื่อสอบถามเพิ่มเติม\n"
            "Sorry, this information is not available in our system. "
            "Please contact Front Desk at extension 0 for assistance."
        )

    except Exception as e:
        logger.error(f"RAG retriever error: {e}")
        return (
            "ขออภัยค่ะ ระบบข้อมูลไม่พร้อมใช้งานชั่วคราว กรุณาติดต่อ Front Desk โทร 0\n"
            "Sorry, our information system is temporarily unavailable. "
            "Please contact Front Desk at extension 0 for assistance."
        )


# =============================================================================
# Tool Classes for Agent Routing (similar to original tools.py pattern)
# =============================================================================

class ToHotelBookingAssistant(BaseModel):
    """
    Transfers work to a specialized assistant for hotel booking operations.
    Handles room availability, reservations, check-in/check-out, and service requests.
    """
    query: str = Field(
        description="The booking-related query or request from the guest."
    )
    guest_email: Optional[str] = Field(
        default=None,
        description="Guest's email if known."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "ผมอยากจองห้อง Deluxe วันที่ 15-17 กุมภาพันธ์",
                "guest_email": "guest@example.com"
            }
        }


class ToHotelServiceAssistant(BaseModel):
    """
    Transfers work to handle hotel service inquiries and requests.
    Provides information about amenities, services, and handles service requests.
    """
    query: str = Field(
        description="The service-related query from the guest."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "สปาเปิดกี่โมง?"
            }
        }


# Export all tools
HOTEL_TOOLS = [
    # READ operations
    check_room_availability,
    get_reservation_details,
    get_guest_reservations,
    get_hotel_services,
    # CREATE operations
    create_reservation,
    confirm_reservation,
    create_service_request,
    # UPDATE operations
    update_reservation,
    check_in_guest,
    check_out_guest,
    # CANCEL operations
    cancel_reservation,
    # RAG - Hotel Knowledge
    search_hotel_knowledge,
]
