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
# Health Check
# =============================================================================


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
