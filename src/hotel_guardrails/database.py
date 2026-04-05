# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Database Operations for Hotel Guardrails API

Provides async database operations for:
- Room catalog and details
- Booking management (list, update)
- Session/conversation history

Uses PostgreSQL with psycopg2 for synchronous operations,
wrapped for async compatibility.
"""

import os
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager

import psycopg2
import psycopg2.extras

logger = logging.getLogger(__name__)


# =============================================================================
# Database Connection
# =============================================================================


def get_db_connection():
    """Get database connection from environment."""
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    # Fallback to individual params
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    dbname = os.getenv("POSTGRES_DB", "railway")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "password")

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
    )


@contextmanager
def get_cursor():
    """Context manager for database cursor with auto-cleanup."""
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cursor, conn
    finally:
        if conn:
            conn.close()


# =============================================================================
# Room Operations
# =============================================================================


async def get_all_room_types() -> List[Dict[str, Any]]:
    """
    Get all room types with availability count.

    Returns:
        List of room types with details and available room counts
    """
    try:
        with get_cursor() as (cur, conn):
            # Get room types with count of available rooms
            cur.execute("""
                SELECT
                    rt.room_type_id,
                    rt.name,
                    rt.name_th,
                    rt.description,
                    rt.description_th,
                    rt.base_price,
                    rt.max_occupancy,
                    rt.amenities,
                    COUNT(CASE WHEN r.status = 'available' THEN 1 END) as available_count
                FROM room_types rt
                LEFT JOIN rooms r ON rt.room_type_id = r.room_type_id
                GROUP BY rt.room_type_id
                ORDER BY rt.base_price ASC
            """)
            rows = cur.fetchall()

            room_types = []
            for row in rows:
                # Parse amenities from JSONB
                amenities = row.get("amenities") or []
                if isinstance(amenities, dict):
                    amenities = list(amenities.keys())

                # Extract size from description if available
                size_sqm = _extract_size_from_description(row.get("description", ""))

                room_types.append({
                    "room_type_id": row["room_type_id"],
                    "name": row["name"],
                    "name_th": row["name_th"],
                    "description": row["description"],
                    "description_th": row["description_th"],
                    "base_price": float(row["base_price"]),
                    "max_occupancy": row["max_occupancy"],
                    "size_sqm": size_sqm,
                    "amenities": amenities,
                    "available_count": row["available_count"] or 0,
                    "photos": _get_room_type_photos(row["name"]),
                })

            return room_types

    except Exception as e:
        logger.error(f"Error fetching room types: {e}")
        raise


async def get_room_by_id(room_id: int) -> Optional[Dict[str, Any]]:
    """
    Get detailed information for a specific room.

    Args:
        room_id: The room ID to fetch

    Returns:
        Room details with type information, or None if not found
    """
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                SELECT
                    r.room_id,
                    r.room_number,
                    r.floor,
                    r.status,
                    r.view_type,
                    r.last_cleaned,
                    r.notes,
                    rt.room_type_id,
                    rt.name as room_type_name,
                    rt.name_th as room_type_name_th,
                    rt.description,
                    rt.description_th,
                    rt.base_price,
                    rt.max_occupancy,
                    rt.amenities
                FROM rooms r
                JOIN room_types rt ON r.room_type_id = rt.room_type_id
                WHERE r.room_id = %s
            """, (room_id,))

            row = cur.fetchone()

            if not row:
                return None

            amenities = row.get("amenities") or []
            if isinstance(amenities, dict):
                amenities = list(amenities.keys())

            return {
                "room_id": row["room_id"],
                "room_number": row["room_number"],
                "floor": row["floor"],
                "status": row["status"],
                "view_type": row["view_type"],
                "last_cleaned": row["last_cleaned"].isoformat() if row["last_cleaned"] else None,
                "room_type": {
                    "room_type_id": row["room_type_id"],
                    "name": row["room_type_name"],
                    "name_th": row["room_type_name_th"],
                    "description": row["description"],
                    "description_th": row["description_th"],
                    "base_price": float(row["base_price"]),
                    "max_occupancy": row["max_occupancy"],
                    "amenities": amenities,
                    "photos": _get_room_type_photos(row["room_type_name"]),
                },
                "pricing": {
                    "base_price": float(row["base_price"]),
                    "tax_rate": 0.07,  # 7% VAT in Thailand
                    "service_charge": 0.10,  # 10% service charge
                    "total_per_night": float(row["base_price"]) * 1.17,
                },
            }

    except Exception as e:
        logger.error(f"Error fetching room {room_id}: {e}")
        raise


async def get_room_by_number(room_number: str) -> Optional[Dict[str, Any]]:
    """
    Get room details by room number.

    Args:
        room_number: The room number (e.g., "501")

    Returns:
        Room details or None if not found
    """
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                SELECT room_id FROM rooms WHERE room_number = %s
            """, (room_number,))
            row = cur.fetchone()

            if not row:
                return None

            return await get_room_by_id(row["room_id"])

    except Exception as e:
        logger.error(f"Error fetching room by number {room_number}: {e}")
        raise


async def get_room_availability_calendar(
    start_date: date,
    end_date: date,
    room_type: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Get room availability for a date range (calendar view).

    Args:
        start_date: Start date of range
        end_date: End date of range
        room_type: Optional room type filter

    Returns:
        List of daily availability info
    """
    try:
        availability = []
        current_date = start_date

        with get_cursor() as (cur, conn):
            while current_date <= end_date:
                # Count available rooms for this date
                query = """
                    SELECT
                        rt.name as room_type,
                        rt.base_price,
                        COUNT(r.room_id) as available_count
                    FROM rooms r
                    JOIN room_types rt ON r.room_type_id = rt.room_type_id
                    WHERE r.status = 'available'
                    AND r.room_id NOT IN (
                        SELECT room_id FROM reservations
                        WHERE status NOT IN ('cancelled', 'no_show', 'checked_out')
                        AND check_in_date <= %s AND check_out_date > %s
                    )
                """
                params = [current_date, current_date]

                if room_type:
                    query += " AND LOWER(rt.name) LIKE LOWER(%s)"
                    params.append(f"%{room_type}%")

                query += " GROUP BY rt.room_type_id ORDER BY rt.base_price"

                cur.execute(query, params)
                rows = cur.fetchall()

                total_available = sum(row["available_count"] for row in rows)
                min_price = min((float(row["base_price"]) for row in rows), default=None)

                availability.append({
                    "date": current_date.isoformat(),
                    "available": total_available > 0,
                    "available_count": total_available,
                    "min_price": min_price,
                })

                current_date += timedelta(days=1)

        return availability

    except Exception as e:
        logger.error(f"Error fetching availability calendar: {e}")
        raise


# =============================================================================
# Booking Operations
# =============================================================================


async def get_bookings(
    guest_id: Optional[int] = None,
    guest_email: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Get bookings with optional filtering.

    Args:
        guest_id: Filter by guest ID
        guest_email: Filter by guest email
        status: Filter by reservation status
        page: Page number (1-indexed)
        page_size: Number of items per page

    Returns:
        Tuple of (bookings list, total count)
    """
    try:
        with get_cursor() as (cur, conn):
            # Build query with filters
            where_clauses = []
            params = []

            if guest_id:
                where_clauses.append("res.guest_id = %s")
                params.append(guest_id)

            if guest_email:
                where_clauses.append("LOWER(g.email) = LOWER(%s)")
                params.append(guest_email)

            if status:
                where_clauses.append("res.status = %s")
                params.append(status)

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            # Get total count
            count_query = f"""
                SELECT COUNT(*) as total
                FROM reservations res
                JOIN guests g ON res.guest_id = g.guest_id
                WHERE {where_sql}
            """
            cur.execute(count_query, params)
            total = cur.fetchone()["total"]

            # Get paginated results
            offset = (page - 1) * page_size
            query = f"""
                SELECT
                    res.reservation_id,
                    res.confirmation_number,
                    res.check_in_date,
                    res.check_out_date,
                    res.num_guests,
                    res.status,
                    res.total_amount,
                    res.payment_status,
                    res.special_requests,
                    res.booking_source,
                    res.cancellation_reason,
                    res.created_at,
                    res.updated_at,
                    r.room_number,
                    rt.name as room_type,
                    rt.name_th as room_type_th,
                    g.guest_id,
                    g.first_name,
                    g.last_name,
                    g.first_name_th,
                    g.last_name_th,
                    g.email,
                    g.phone,
                    g.loyalty_tier,
                    g.loyalty_points
                FROM reservations res
                JOIN rooms r ON res.room_id = r.room_id
                JOIN room_types rt ON r.room_type_id = rt.room_type_id
                JOIN guests g ON res.guest_id = g.guest_id
                WHERE {where_sql}
                ORDER BY res.check_in_date DESC, res.created_at DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(query, params + [page_size, offset])
            rows = cur.fetchall()

            bookings = []
            for row in rows:
                check_in = row["check_in_date"]
                check_out = row["check_out_date"]
                num_nights = (check_out - check_in).days if check_in and check_out else 0

                bookings.append({
                    "reservation_id": row["reservation_id"],
                    "confirmation_number": row["confirmation_number"],
                    "guest": {
                        "guest_id": row["guest_id"],
                        "first_name": row["first_name"],
                        "last_name": row["last_name"],
                        "first_name_th": row["first_name_th"],
                        "last_name_th": row["last_name_th"],
                        "email": row["email"],
                        "phone": row["phone"],
                        "loyalty_tier": row["loyalty_tier"],
                        "loyalty_points": row["loyalty_points"],
                    },
                    "room_number": row["room_number"],
                    "room_type": row["room_type"],
                    "room_type_th": row["room_type_th"],
                    "check_in_date": row["check_in_date"].isoformat(),
                    "check_out_date": row["check_out_date"].isoformat(),
                    "num_nights": num_nights,
                    "num_guests": row["num_guests"],
                    "status": row["status"],
                    "total_amount": float(row["total_amount"]) if row["total_amount"] else 0,
                    "payment_status": row["payment_status"],
                    "special_requests": row["special_requests"],
                    "booking_source": row["booking_source"],
                    "cancellation_reason": row["cancellation_reason"],
                    "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                    "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
                })

            return bookings, total

    except Exception as e:
        logger.error(f"Error fetching bookings: {e}")
        raise


async def get_booking_by_id(reservation_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a single booking by ID or confirmation number.

    Args:
        reservation_id: Reservation ID or confirmation number

    Returns:
        Booking details or None if not found
    """
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                SELECT
                    res.reservation_id,
                    res.confirmation_number,
                    res.check_in_date,
                    res.check_out_date,
                    res.num_guests,
                    res.status,
                    res.total_amount,
                    res.payment_status,
                    res.special_requests,
                    res.booking_source,
                    res.cancellation_reason,
                    res.created_at,
                    res.updated_at,
                    res.room_id,
                    r.room_number,
                    rt.name as room_type,
                    rt.name_th as room_type_th,
                    rt.base_price,
                    g.guest_id,
                    g.first_name,
                    g.last_name,
                    g.first_name_th,
                    g.last_name_th,
                    g.email,
                    g.phone,
                    g.loyalty_tier,
                    g.loyalty_points
                FROM reservations res
                JOIN rooms r ON res.room_id = r.room_id
                JOIN room_types rt ON r.room_type_id = rt.room_type_id
                JOIN guests g ON res.guest_id = g.guest_id
                WHERE res.reservation_id::text = %s OR res.confirmation_number = %s
            """, (reservation_id, reservation_id))

            row = cur.fetchone()

            if not row:
                return None

            check_in = row["check_in_date"]
            check_out = row["check_out_date"]
            num_nights = (check_out - check_in).days if check_in and check_out else 0

            return {
                "reservation_id": row["reservation_id"],
                "confirmation_number": row["confirmation_number"],
                "guest": {
                    "guest_id": row["guest_id"],
                    "first_name": row["first_name"],
                    "last_name": row["last_name"],
                    "first_name_th": row["first_name_th"],
                    "last_name_th": row["last_name_th"],
                    "email": row["email"],
                    "phone": row["phone"],
                    "loyalty_tier": row["loyalty_tier"],
                    "loyalty_points": row["loyalty_points"],
                },
                "room_id": row["room_id"],
                "room_number": row["room_number"],
                "room_type": row["room_type"],
                "room_type_th": row["room_type_th"],
                "base_price": float(row["base_price"]),
                "check_in_date": row["check_in_date"].isoformat(),
                "check_out_date": row["check_out_date"].isoformat(),
                "num_nights": num_nights,
                "num_guests": row["num_guests"],
                "status": row["status"],
                "total_amount": float(row["total_amount"]) if row["total_amount"] else 0,
                "payment_status": row["payment_status"],
                "special_requests": row["special_requests"],
                "booking_source": row["booking_source"],
                "cancellation_reason": row["cancellation_reason"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }

    except Exception as e:
        logger.error(f"Error fetching booking {reservation_id}: {e}")
        raise


async def update_booking(
    reservation_id: str,
    check_in_date: Optional[date] = None,
    check_out_date: Optional[date] = None,
    room_number: Optional[str] = None,
    num_guests: Optional[int] = None,
    special_requests: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]], Dict[str, Any]]:
    """
    Update a booking's details.

    Args:
        reservation_id: Reservation ID or confirmation number
        check_in_date: New check-in date
        check_out_date: New check-out date
        room_number: New room number
        num_guests: New number of guests
        special_requests: Updated special requests

    Returns:
        Tuple of (success, message, updated_booking, changes)
    """
    try:
        with get_cursor() as (cur, conn):
            # Get current booking
            current = await get_booking_by_id(reservation_id)
            if not current:
                return False, f"Booking {reservation_id} not found / ไม่พบการจอง {reservation_id}", None, {}

            if current["status"] in ["checked_out", "cancelled"]:
                return False, f"Cannot modify {current['status']} booking / ไม่สามารถแก้ไขการจองที่ {current['status']} แล้ว", None, {}

            # Track changes
            changes = {}
            new_room_id = current["room_id"]
            new_base_price = current["base_price"]

            # Validate and apply room change
            if room_number and room_number != current["room_number"]:
                cur.execute("""
                    SELECT r.room_id, r.room_number, rt.base_price, rt.max_occupancy
                    FROM rooms r
                    JOIN room_types rt ON r.room_type_id = rt.room_type_id
                    WHERE r.room_number = %s
                """, (room_number,))
                new_room = cur.fetchone()

                if not new_room:
                    return False, f"Room {room_number} not found / ไม่พบห้อง {room_number}", None, {}

                # Check if new room is available
                new_check_in = check_in_date or datetime.strptime(current["check_in_date"], "%Y-%m-%d").date()
                new_check_out = check_out_date or datetime.strptime(current["check_out_date"], "%Y-%m-%d").date()

                cur.execute("""
                    SELECT reservation_id FROM reservations
                    WHERE room_id = %s
                    AND reservation_id != %s
                    AND status NOT IN ('cancelled', 'no_show', 'checked_out')
                    AND check_in_date < %s AND check_out_date > %s
                """, (new_room["room_id"], current["reservation_id"], new_check_out, new_check_in))

                if cur.fetchone():
                    return False, f"Room {room_number} is not available for the selected dates / ห้อง {room_number} ไม่ว่างในวันที่เลือก", None, {}

                changes["room_number"] = {"old": current["room_number"], "new": room_number}
                new_room_id = new_room["room_id"]
                new_base_price = float(new_room["base_price"])

            # Apply date changes
            final_check_in = check_in_date or datetime.strptime(current["check_in_date"], "%Y-%m-%d").date()
            final_check_out = check_out_date or datetime.strptime(current["check_out_date"], "%Y-%m-%d").date()

            if check_in_date and str(check_in_date) != current["check_in_date"]:
                changes["check_in_date"] = {"old": current["check_in_date"], "new": str(check_in_date)}

            if check_out_date and str(check_out_date) != current["check_out_date"]:
                changes["check_out_date"] = {"old": current["check_out_date"], "new": str(check_out_date)}

            if num_guests and num_guests != current["num_guests"]:
                changes["num_guests"] = {"old": current["num_guests"], "new": num_guests}

            if special_requests is not None and special_requests != current["special_requests"]:
                changes["special_requests"] = {"old": current["special_requests"], "new": special_requests}

            # Recalculate total if dates or room changed
            nights = (final_check_out - final_check_in).days
            new_total = new_base_price * nights

            if new_total != current["total_amount"]:
                changes["total_amount"] = {"old": current["total_amount"], "new": new_total}

            # Perform update
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
            """, (
                final_check_in,
                final_check_out,
                new_room_id,
                num_guests,
                special_requests,
                new_total,
                current["reservation_id"],
            ))

            result = cur.fetchone()
            conn.commit()

            # Fetch updated booking
            updated = await get_booking_by_id(reservation_id)

            message = f"Booking {result['confirmation_number']} updated successfully / แก้ไขการจอง {result['confirmation_number']} สำเร็จ"
            return True, message, updated, changes

    except Exception as e:
        logger.error(f"Error updating booking {reservation_id}: {e}")
        return False, f"Error updating booking: {str(e)}", None, {}


# =============================================================================
# Session/Conversation Operations
# =============================================================================


async def get_conversation_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[Dict[str, Any]], int, bool]:
    """
    Get conversation messages for a session.

    Args:
        session_id: The session ID
        limit: Maximum messages to return
        offset: Number of messages to skip

    Returns:
        Tuple of (messages, total_count, has_more)
    """
    try:
        with get_cursor() as (cur, conn):
            # Get total count
            cur.execute("""
                SELECT COUNT(*) as total
                FROM conversation_history
                WHERE session_id = %s
            """, (session_id,))
            total = cur.fetchone()["total"]

            # Get messages
            cur.execute("""
                SELECT
                    conversation_id as message_id,
                    role,
                    content,
                    created_at as timestamp
                FROM conversation_history
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT %s OFFSET %s
            """, (session_id, limit, offset))

            rows = cur.fetchall()

            messages = [
                {
                    "message_id": row["message_id"],
                    "role": row["role"],
                    "content": row["content"],
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                    "metadata": None,
                }
                for row in rows
            ]

            has_more = (offset + len(messages)) < total

            return messages, total, has_more

    except Exception as e:
        logger.error(f"Error fetching messages for session {session_id}: {e}")
        # Return empty for new/non-existent sessions
        return [], 0, False


async def save_conversation_message(
    session_id: str,
    role: str,
    content: str,
    guest_id: Optional[int] = None,
) -> Optional[int]:
    """
    Save a conversation message to the database.

    Args:
        session_id: The session ID
        role: Message role ('user' or 'assistant')
        content: Message content
        guest_id: Optional guest ID

    Returns:
        Message ID if saved, None if failed
    """
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                INSERT INTO conversation_history (session_id, guest_id, role, content)
                VALUES (%s, %s, %s, %s)
                RETURNING conversation_id
            """, (session_id, guest_id, role, content))

            result = cur.fetchone()
            conn.commit()

            return result["conversation_id"] if result else None

    except Exception as e:
        logger.error(f"Error saving message: {e}")
        return None


# =============================================================================
# Helper Functions
# =============================================================================


def _extract_size_from_description(description: str) -> Optional[int]:
    """Extract room size in sqm from description."""
    if not description:
        return None

    import re
    match = re.search(r"(\d+)\s*(?:sqm|sq\.?m|square meters?)", description.lower())
    if match:
        return int(match.group(1))

    # Default sizes based on room type keywords
    desc_lower = description.lower()
    if "penthouse" in desc_lower:
        return 120
    elif "suite" in desc_lower:
        return 55
    elif "deluxe" in desc_lower:
        return 35
    elif "standard" in desc_lower:
        return 28

    return None


def _get_room_type_photos(room_type_name: str) -> List[str]:
    """Get placeholder photo URLs for room type."""
    # In production, these would come from a CDN or storage service
    base_url = "/static/rooms"
    room_type_lower = room_type_name.lower().replace(" ", "_")

    return [
        f"{base_url}/{room_type_lower}_1.jpg",
        f"{base_url}/{room_type_lower}_2.jpg",
        f"{base_url}/{room_type_lower}_3.jpg",
    ]


# =============================================================================
# Guest Operations
# =============================================================================


async def get_guest_by_email(email: str) -> Optional[Dict[str, Any]]:
    """
    Get guest information by email.

    Args:
        email: Guest email address

    Returns:
        Guest details or None if not found
    """
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                SELECT
                    guest_id,
                    email,
                    first_name,
                    last_name,
                    first_name_th,
                    last_name_th,
                    phone,
                    nationality,
                    loyalty_tier,
                    loyalty_points,
                    created_at,
                    updated_at
                FROM guests
                WHERE LOWER(email) = LOWER(%s)
            """, (email,))

            row = cur.fetchone()

            if not row:
                return None

            return {
                "guest_id": row["guest_id"],
                "email": row["email"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "first_name_th": row["first_name_th"],
                "last_name_th": row["last_name_th"],
                "phone": row["phone"],
                "nationality": row["nationality"],
                "loyalty_tier": row["loyalty_tier"],
                "loyalty_points": row["loyalty_points"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }

    except Exception as e:
        logger.error(f"Error fetching guest by email {email}: {e}")
        raise


async def get_guest_by_id(guest_id: int) -> Optional[Dict[str, Any]]:
    """
    Get guest information by ID.

    Args:
        guest_id: Guest ID

    Returns:
        Guest details or None if not found
    """
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                SELECT
                    guest_id,
                    email,
                    first_name,
                    last_name,
                    first_name_th,
                    last_name_th,
                    phone,
                    nationality,
                    loyalty_tier,
                    loyalty_points,
                    created_at,
                    updated_at
                FROM guests
                WHERE guest_id = %s
            """, (guest_id,))

            row = cur.fetchone()

            if not row:
                return None

            return {
                "guest_id": row["guest_id"],
                "email": row["email"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "first_name_th": row["first_name_th"],
                "last_name_th": row["last_name_th"],
                "phone": row["phone"],
                "nationality": row["nationality"],
                "loyalty_tier": row["loyalty_tier"],
                "loyalty_points": row["loyalty_points"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }

    except Exception as e:
        logger.error(f"Error fetching guest by id {guest_id}: {e}")
        raise


async def create_guest(
    email: str,
    first_name: str,
    last_name: str,
    first_name_th: Optional[str] = None,
    last_name_th: Optional[str] = None,
    phone: Optional[str] = None,
    nationality: Optional[str] = None,
    id_type: Optional[str] = None,
    id_number: Optional[str] = None,
    date_of_birth: Optional[str] = None,
    address: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Create a new guest.

    Args:
        email: Guest email address
        first_name: First name in English
        last_name: Last name in English
        first_name_th: First name in Thai (optional)
        last_name_th: Last name in Thai (optional)
        phone: Phone number (optional)
        nationality: Nationality (optional)
        id_type: ID document type (optional)
        id_number: ID document number (optional)
        date_of_birth: Date of birth YYYY-MM-DD (optional)
        address: Full address (optional)

    Returns:
        Tuple of (success, message, guest_data)
    """
    try:
        with get_cursor() as (cur, conn):
            # Check if email already exists
            cur.execute("""
                SELECT guest_id FROM guests WHERE LOWER(email) = LOWER(%s)
            """, (email,))

            existing = cur.fetchone()
            if existing:
                return False, f"Guest with email {email} already exists / อีเมล {email} มีอยู่แล้ว", None

            # Parse date of birth if provided
            dob = None
            if date_of_birth:
                try:
                    dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
                except ValueError:
                    return False, f"Invalid date format: {date_of_birth}. Use YYYY-MM-DD", None

            # Insert new guest
            cur.execute("""
                INSERT INTO guests (
                    email, first_name, last_name, first_name_th, last_name_th,
                    phone, nationality, id_number,
                    loyalty_tier, loyalty_points, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                RETURNING guest_id, created_at
            """, (
                email, first_name, last_name, first_name_th, last_name_th,
                phone, nationality, id_number,
                "Standard", 0  # Default loyalty tier and points
            ))

            result = cur.fetchone()
            conn.commit()

            guest_data = {
                "guest_id": result["guest_id"],
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "first_name_th": first_name_th,
                "last_name_th": last_name_th,
                "phone": phone,
                "nationality": nationality,
                "loyalty_tier": "Bronze",
                "loyalty_points": 0,
                "created_at": result["created_at"].isoformat() if result["created_at"] else None,
                "updated_at": None,
            }

            return True, f"Guest {first_name} {last_name} registered successfully / ลงทะเบียน {first_name} {last_name} สำเร็จ", guest_data

    except Exception as e:
        logger.error(f"Error creating guest: {e}")
        return False, f"Error creating guest: {str(e)}", None


async def update_guest(
    guest_id: int,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
    first_name_th: Optional[str] = None,
    last_name_th: Optional[str] = None,
    phone: Optional[str] = None,
    nationality: Optional[str] = None,
    address: Optional[str] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Update guest information.

    Args:
        guest_id: Guest ID
        first_name: New first name in English
        last_name: New last name in English
        first_name_th: New first name in Thai
        last_name_th: New last name in Thai
        phone: New phone number
        nationality: New nationality
        address: New address

    Returns:
        Tuple of (success, message, updated_guest_data)
    """
    try:
        with get_cursor() as (cur, conn):
            # Check if guest exists
            existing = await get_guest_by_id(guest_id)
            if not existing:
                return False, f"Guest {guest_id} not found / ไม่พบผู้เข้าพัก {guest_id}", None

            # Build dynamic update query
            updates = []
            params = []

            if first_name is not None:
                updates.append("first_name = %s")
                params.append(first_name)

            if last_name is not None:
                updates.append("last_name = %s")
                params.append(last_name)

            if first_name_th is not None:
                updates.append("first_name_th = %s")
                params.append(first_name_th)

            if last_name_th is not None:
                updates.append("last_name_th = %s")
                params.append(last_name_th)

            if phone is not None:
                updates.append("phone = %s")
                params.append(phone)

            if nationality is not None:
                updates.append("nationality = %s")
                params.append(nationality)

            if address is not None:
                updates.append("address = %s")
                params.append(address)

            if not updates:
                return False, "No fields to update / ไม่มีข้อมูลที่ต้องอัปเดต", existing

            updates.append("updated_at = CURRENT_TIMESTAMP")

            update_sql = f"UPDATE guests SET {', '.join(updates)} WHERE guest_id = %s RETURNING *"
            params.append(guest_id)

            cur.execute(update_sql, params)
            row = cur.fetchone()
            conn.commit()

            updated_guest = {
                "guest_id": row["guest_id"],
                "email": row["email"],
                "first_name": row["first_name"],
                "last_name": row["last_name"],
                "first_name_th": row["first_name_th"],
                "last_name_th": row["last_name_th"],
                "phone": row["phone"],
                "nationality": row["nationality"],
                "loyalty_tier": row["loyalty_tier"],
                "loyalty_points": row["loyalty_points"],
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
                "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
            }

            return True, f"Guest {guest_id} updated successfully / อัปเดตผู้เข้าพัก {guest_id} สำเร็จ", updated_guest

    except Exception as e:
        logger.error(f"Error updating guest {guest_id}: {e}")
        return False, f"Error updating guest: {str(e)}", None


# =============================================================================
# Health Check
# =============================================================================


# =============================================================================
# User / Auth Operations
# =============================================================================


async def ensure_users_table() -> None:
    """Create users table + indexes if they don't exist (idempotent)."""
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id SERIAL PRIMARY KEY,
                    username VARCHAR(64) UNIQUE NOT NULL,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(20) NOT NULL DEFAULT 'user',
                    full_name VARCHAR(200),
                    is_active BOOLEAN DEFAULT TRUE,
                    guest_id INTEGER REFERENCES guests(guest_id) ON DELETE SET NULL,
                    last_login TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    CONSTRAINT users_role_check CHECK (role IN ('user', 'admin'))
                )
            """)
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)")
            conn.commit()
            logger.info("users table ensured")
    except Exception as e:
        logger.error(f"Error ensuring users table: {e}")
        raise


async def create_user(
    username: str,
    email: str,
    password_hash: str,
    role: str = "user",
    full_name: Optional[str] = None,
    guest_id: Optional[int] = None,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Create a new user account.

    Returns:
        (success, message, user_dict) — user_dict excludes password_hash.
    """
    if role not in ("user", "admin"):
        return False, f"Invalid role: {role}", None

    try:
        with get_cursor() as (cur, conn):
            cur.execute(
                "SELECT user_id FROM users WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)",
                (username, email),
            )
            if cur.fetchone():
                return (
                    False,
                    "Username or email already exists / ชื่อผู้ใช้หรืออีเมลมีอยู่แล้ว",
                    None,
                )

            cur.execute(
                """
                INSERT INTO users (username, email, password_hash, role, full_name, guest_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING user_id, username, email, role, full_name, guest_id,
                          is_active, last_login, created_at
                """,
                (username, email, password_hash, role, full_name, guest_id),
            )
            row = cur.fetchone()
            conn.commit()
            return True, "User created successfully / สร้างผู้ใช้สำเร็จ", dict(row)
    except Exception as e:
        logger.error(f"Error creating user: {e}")
        return False, f"Error creating user: {str(e)}", None


async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Look up a user by username or email (case-insensitive). Includes password_hash."""
    try:
        with get_cursor() as (cur, conn):
            cur.execute(
                """
                SELECT user_id, username, email, password_hash, role, full_name,
                       is_active, guest_id, last_login, created_at, updated_at
                FROM users
                WHERE LOWER(username) = LOWER(%s) OR LOWER(email) = LOWER(%s)
                LIMIT 1
                """,
                (username, username),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error fetching user: {e}")
        return None


async def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Look up a user by user_id. Includes password_hash."""
    try:
        with get_cursor() as (cur, conn):
            cur.execute(
                """
                SELECT user_id, username, email, password_hash, role, full_name,
                       is_active, guest_id, last_login, created_at, updated_at
                FROM users
                WHERE user_id = %s
                """,
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error fetching user by id: {e}")
        return None


async def update_user_last_login(user_id: int) -> None:
    """Update the last_login timestamp to now."""
    try:
        with get_cursor() as (cur, conn):
            cur.execute(
                "UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE user_id = %s",
                (user_id,),
            )
            conn.commit()
    except Exception as e:
        logger.warning(f"Failed to update last_login for user {user_id}: {e}")


async def list_users(
    role: Optional[str] = None, limit: int = 100
) -> List[Dict[str, Any]]:
    """List users, optionally filtered by role. Excludes password_hash."""
    try:
        with get_cursor() as (cur, conn):
            if role:
                cur.execute(
                    """
                    SELECT user_id, username, email, role, full_name, is_active,
                           guest_id, last_login, created_at
                    FROM users
                    WHERE role = %s
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (role, min(limit, 500)),
                )
            else:
                cur.execute(
                    """
                    SELECT user_id, username, email, role, full_name, is_active,
                           guest_id, last_login, created_at
                    FROM users
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (min(limit, 500),),
                )
            return [dict(r) for r in cur.fetchall()]
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return []


async def seed_default_admin(
    username: str, email: str, password_hash: str, full_name: str = "Default Admin"
) -> bool:
    """
    Create a default admin if NO admin user exists yet.

    Returns True if a new admin was created, False if one already exists
    or on error.
    """
    try:
        with get_cursor() as (cur, conn):
            cur.execute("SELECT 1 FROM users WHERE role = 'admin' LIMIT 1")
            if cur.fetchone():
                return False

            cur.execute(
                """
                INSERT INTO users (username, email, password_hash, role, full_name)
                VALUES (%s, %s, %s, 'admin', %s)
                ON CONFLICT (username) DO NOTHING
                """,
                (username, email, password_hash, full_name),
            )
            created = cur.rowcount > 0
            conn.commit()
            return created
    except Exception as e:
        logger.error(f"Error seeding default admin: {e}")
        return False


# =============================================================================
# Admin Operations
# =============================================================================


async def admin_update_room_status(
    room_id: int, status: str, notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Update room status (available, occupied, maintenance, cleaning)."""
    valid = {"available", "occupied", "maintenance", "cleaning"}
    if status not in valid:
        return None
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                UPDATE rooms SET status = %s, notes = COALESCE(%s, notes)
                WHERE room_id = %s
                RETURNING room_id, room_number, status
            """, (status, notes, room_id))
            result = cur.fetchone()
            conn.commit()
            return dict(result) if result else None
    except Exception as e:
        logger.error(f"Error updating room status: {e}")
        return None


async def admin_update_booking_status(
    reservation_id: str, status: str, notes: Optional[str] = None
) -> Optional[Dict[str, Any]]:
    """Admin override booking status."""
    valid = {"pending", "confirmed", "checked_in", "checked_out", "cancelled", "no_show"}
    if status not in valid:
        return None
    try:
        with get_cursor() as (cur, conn):
            updates = ["status = %s"]
            params = [status]
            if notes:
                updates.append("special_requests = COALESCE(special_requests || E'\\n', '') || %s")
                params.append(f"[Admin] {notes}")
            if status == "cancelled" and notes:
                updates.append("cancellation_reason = %s")
                params.append(notes)

            params.extend([reservation_id, reservation_id])
            cur.execute(f"""
                UPDATE reservations SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP
                WHERE reservation_id::text = %s OR confirmation_number = %s
                RETURNING reservation_id, confirmation_number, status
            """, params)
            result = cur.fetchone()
            conn.commit()
            return dict(result) if result else None
    except Exception as e:
        logger.error(f"Error admin updating booking: {e}")
        return None


async def admin_send_message_to_session(
    session_id: str, message: str
) -> bool:
    """Insert an admin message into conversation history."""
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                INSERT INTO conversation_history (session_id, role, content)
                VALUES (%s, 'admin', %s)
            """, (session_id, message))
            conn.commit()
            return True
    except Exception as e:
        logger.error(f"Error saving admin message: {e}")
        return False


# =============================================================================
# Dashboard Statistics
# =============================================================================


async def get_dashboard_stats() -> Dict[str, Any]:
    """Get overview statistics for admin dashboard."""
    try:
        with get_cursor() as (cur, conn):
            stats = {}

            # Room stats
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM rooms GROUP BY status ORDER BY status
            """)
            stats["rooms"] = {row["status"]: row["count"] for row in cur.fetchall()}
            stats["rooms"]["total"] = sum(stats["rooms"].values())

            # Reservation stats
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM reservations GROUP BY status ORDER BY status
            """)
            stats["reservations"] = {row["status"]: row["count"] for row in cur.fetchall()}
            stats["reservations"]["total"] = sum(stats["reservations"].values())

            # Today's activity
            cur.execute("""
                SELECT COUNT(*) as count FROM reservations
                WHERE DATE(created_at) = CURRENT_DATE
            """)
            stats["today_new_bookings"] = cur.fetchone()["count"]

            cur.execute("""
                SELECT COUNT(*) as count FROM reservations
                WHERE check_in_date = CURRENT_DATE AND status IN ('confirmed', 'checked_in')
            """)
            stats["today_checkins"] = cur.fetchone()["count"]

            cur.execute("""
                SELECT COUNT(*) as count FROM reservations
                WHERE check_out_date = CURRENT_DATE AND status IN ('checked_in', 'checked_out')
            """)
            stats["today_checkouts"] = cur.fetchone()["count"]

            # Revenue
            cur.execute("""
                SELECT COALESCE(SUM(total_amount), 0) as total
                FROM reservations
                WHERE status NOT IN ('cancelled', 'no_show')
            """)
            stats["total_revenue"] = float(cur.fetchone()["total"])

            cur.execute("""
                SELECT COALESCE(SUM(total_amount), 0) as total
                FROM reservations
                WHERE status NOT IN ('cancelled', 'no_show')
                AND DATE(created_at) = CURRENT_DATE
            """)
            stats["today_revenue"] = float(cur.fetchone()["total"])

            # Guest stats
            cur.execute("SELECT COUNT(*) as count FROM guests")
            stats["total_guests"] = cur.fetchone()["count"]

            # Service requests
            cur.execute("""
                SELECT status, COUNT(*) as count
                FROM service_requests GROUP BY status ORDER BY status
            """)
            stats["service_requests"] = {row["status"]: row["count"] for row in cur.fetchall()}

            # Occupancy rate
            total_rooms = stats["rooms"].get("total", 1)
            occupied = stats["rooms"].get("occupied", 0)
            stats["occupancy_rate"] = round((occupied / total_rooms) * 100, 1) if total_rooms else 0

            return stats

    except Exception as e:
        logger.error(f"Error getting dashboard stats: {e}")
        return {"error": str(e)}


async def get_recent_bookings(limit: int = 20) -> List[Dict[str, Any]]:
    """Get most recent bookings for dashboard feed."""
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                SELECT r.reservation_id, r.confirmation_number, r.status,
                       r.check_in_date, r.check_out_date, r.total_amount,
                       r.created_at, r.booking_source,
                       rm.room_number, rt.name as room_type,
                       g.email, g.first_name, g.last_name
                FROM reservations r
                JOIN rooms rm ON r.room_id = rm.room_id
                JOIN room_types rt ON rm.room_type_id = rt.room_type_id
                JOIN guests g ON r.guest_id = g.guest_id
                ORDER BY r.created_at DESC
                LIMIT %s
            """, (limit,))
            rows = cur.fetchall()
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Error getting recent bookings: {e}")
        return []


async def get_active_sessions_stats() -> Dict[str, Any]:
    """Get conversation session statistics."""
    try:
        with get_cursor() as (cur, conn):
            cur.execute("""
                SELECT COUNT(DISTINCT session_id) as total_sessions,
                       COUNT(*) as total_messages,
                       COUNT(CASE WHEN role = 'user' THEN 1 END) as user_messages,
                       COUNT(CASE WHEN role = 'assistant' THEN 1 END) as bot_messages,
                       COUNT(CASE WHEN role = 'admin' THEN 1 END) as admin_messages
                FROM conversation_history
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            row = cur.fetchone()
            return dict(row) if row else {}
    except Exception as e:
        logger.error(f"Error getting session stats: {e}")
        return {"error": str(e)}


async def check_database_health() -> Dict[str, Any]:
    """
    Check database connectivity and basic operations.

    Returns:
        Health status dict
    """
    try:
        with get_cursor() as (cur, conn):
            cur.execute("SELECT 1")
            cur.fetchone()

            cur.execute("SELECT COUNT(*) as count FROM room_types")
            room_types = cur.fetchone()["count"]

            cur.execute("SELECT COUNT(*) as count FROM rooms")
            rooms = cur.fetchone()["count"]

            return {
                "status": "healthy",
                "room_types": room_types,
                "rooms": rooms,
            }

    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
        }
