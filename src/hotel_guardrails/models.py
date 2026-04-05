# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Pydantic Models for Hotel Guardrails API

Request and response models for:
- /chat endpoint (general AI conversation)
- /tools/book endpoint (booking operations)
- /health endpoint (service health check)

Usage:
    from src.hotel_guardrails.models import ChatRequest, ChatResponse

    request = ChatRequest(message="What time is breakfast?")
"""
from typing import Optional, List, Dict, Any
from datetime import date

from pydantic import BaseModel, Field


class LLMOverrides(BaseModel):
    """Optional per-request LLM configuration overrides."""

    model: Optional[str] = Field(
        None,
        description="Override model for this request",
        examples=["qwen/qwen3-max", "anthropic/claude-3-haiku"],
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Override temperature (0.0-2.0)",
    )
    max_tokens: Optional[int] = Field(
        None,
        ge=1,
        le=8192,
        description="Override max tokens",
    )


class ChatRequest(BaseModel):
    """Request model for /chat endpoint."""

    message: str = Field(
        ...,
        description="User message in Thai or English",
        min_length=1,
        max_length=4096,
        examples=["What time is breakfast?", "รหัส WiFi คืออะไรครับ"],
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID for conversation context. If not provided, a new session is created.",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    language: Optional[str] = Field(
        "auto",
        description="Preferred response language: 'th' (Thai), 'en' (English), or 'auto' (detect from input)",
        pattern="^(th|en|auto)$",
    )
    llm_settings: Optional[LLMOverrides] = Field(
        None,
        description="Optional per-request LLM configuration overrides",
    )


class ChatResponse(BaseModel):
    """Response model for /chat endpoint."""

    response: str = Field(
        ...,
        description="AI response in Thai or English",
    )
    session_id: str = Field(
        ...,
        description="Session ID for continuing the conversation",
    )
    sources: Optional[List[str]] = Field(
        None,
        description="RAG sources used to generate the response",
    )
    retrieval_context: Optional[List[str]] = Field(
        None,
        description="Actual retrieved document chunks used for RAG evaluation",
    )
    tool_calls: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Tools executed during response generation",
    )
    request_id: Optional[str] = Field(
        None,
        description="Request tracking ID for debugging (from X-Request-ID header)",
    )

    # Hybrid routing metadata
    routing_path: Optional[str] = Field(
        None,
        description="Which path handled the request: 'nemo' (fast) or 'langgraph' (complex)",
        examples=["nemo", "langgraph"],
    )
    routing_reason: Optional[str] = Field(
        None,
        description="Human-readable reason for the routing decision",
        examples=["Simple query - using fast path", "Complex query requiring multi-step reasoning"],
    )
    complexity: Optional[str] = Field(
        None,
        description="Query complexity classification: 'simple', 'moderate', or 'complex'",
        examples=["simple", "moderate", "complex"],
    )


class BookingRequest(BaseModel):
    """Request model for /tools/book endpoint."""

    action: str = Field(
        ...,
        description="Booking action: 'check' (availability), 'create', 'confirm', or 'cancel'",
        pattern="^(check|create|confirm|cancel)$",
        examples=["check", "create", "confirm", "cancel"],
    )
    guest_id: Optional[str] = Field(
        None,
        description="Guest ID (required for 'create' action)",
        examples=["G001", "GUEST-12345"],
    )
    room_type: Optional[str] = Field(
        None,
        description="Room type: Standard, Deluxe, Suite, or Penthouse",
        examples=["Deluxe", "Suite"],
    )
    room_id: Optional[str] = Field(
        None,
        description="Specific room ID (required for 'create' action)",
        examples=["501", "ROOM-501"],
    )
    reservation_id: Optional[str] = Field(
        None,
        description="Reservation ID (required for 'confirm' and 'cancel' actions)",
        examples=["RES-2024-001", "12345"],
    )
    check_in: Optional[date] = Field(
        None,
        description="Check-in date (required for 'check' and 'create' actions)",
        examples=["2025-02-15"],
    )
    check_out: Optional[date] = Field(
        None,
        description="Check-out date (required for 'check' and 'create' actions)",
        examples=["2025-02-17"],
    )
    special_requests: Optional[str] = Field(
        None,
        description="Special requests for the reservation",
        max_length=1000,
        examples=["Late check-in, high floor preferred"],
    )
    reason: Optional[str] = Field(
        None,
        description="Cancellation reason (optional for 'cancel' action)",
        max_length=500,
        examples=["Change of travel plans"],
    )


class BookingResponse(BaseModel):
    """Response model for /tools/book endpoint."""

    success: bool = Field(
        ...,
        description="Whether the operation was successful",
    )
    action: str = Field(
        ...,
        description="Action that was performed",
    )
    data: Optional[Dict[str, Any]] = Field(
        None,
        description="Result data from the operation",
    )
    message: str = Field(
        ...,
        description="Human-readable message in Thai/English",
    )
    reservation_id: Optional[str] = Field(
        None,
        description="Reservation ID if created or affected",
    )


class HealthResponse(BaseModel):
    """Response model for /health endpoint."""

    status: str = Field(
        ...,
        description="Overall service status: 'healthy', 'degraded', or 'unhealthy'",
        examples=["healthy", "degraded"],
    )
    components: Dict[str, str] = Field(
        ...,
        description="Status of individual components",
        examples=[
            {
                "guardrails": "healthy",
                "qdrant": "healthy",
                "openrouter": "healthy",
            }
        ],
    )


class ErrorResponse(BaseModel):
    """Standard error response model."""

    error: str = Field(
        ...,
        description="Error type",
        examples=["validation_error", "internal_error"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details",
    )


class StreamChunk(BaseModel):
    """Model for SSE stream chunks."""

    content: str = Field(
        ...,
        description="Partial response content",
    )
    done: bool = Field(
        False,
        description="Whether this is the final chunk",
    )
    session_id: Optional[str] = Field(
        None,
        description="Session ID (included in final chunk)",
    )


class LLMSettingsResponse(BaseModel):
    """Response model for /settings/llm endpoint."""

    backend: str = Field(
        ...,
        description="Active LLM backend: 'ollama' or 'openrouter'",
        examples=["ollama"],
    )
    model: str = Field(
        ...,
        description="Current LLM model name",
        examples=["fredrezones55/qwen3.5-opus:9b"],
    )
    temperature: float = Field(
        ...,
        description="Current temperature setting",
    )
    max_tokens: int = Field(
        ...,
        description="Current max tokens setting",
    )
    streaming: bool = Field(
        ...,
        description="Whether streaming is enabled",
    )
    thinking: bool = Field(
        False,
        description="Whether thinking/reasoning mode is enabled",
    )
    ollama_base_url: Optional[str] = Field(
        None,
        description="Ollama API base URL",
    )
    openrouter_model: Optional[str] = Field(
        None,
        description="OpenRouter model (for reference when on Ollama)",
    )
    available_models: List[Dict[str, Any]] = Field(
        ...,
        description="List of available LLM models",
    )


class LLMSettingsUpdateRequest(BaseModel):
    """Request model for PUT /settings/llm endpoint."""

    backend: Optional[str] = Field(
        None,
        description="Switch backend: 'ollama' or 'openrouter'",
        examples=["ollama"],
    )
    model: Optional[str] = Field(
        None,
        description="Model name to use",
        examples=["fredrezones55/qwen3.5-opus:9b", "qwen/qwen3-max"],
    )
    temperature: Optional[float] = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature (0.0-2.0)",
    )
    max_tokens: Optional[int] = Field(
        None,
        ge=1,
        le=8192,
        description="Maximum response tokens",
    )


class SessionCreateResponse(BaseModel):
    """Response model for POST /sessions endpoint."""

    session_id: str = Field(
        ...,
        description="New session ID",
    )
    created_at: str = Field(
        ...,
        description="Session creation timestamp (ISO format)",
    )


class SessionInfo(BaseModel):
    """Response model for GET /sessions/{id} endpoint."""

    session_id: str = Field(
        ...,
        description="Session ID",
    )
    created_at: str = Field(
        ...,
        description="Session creation timestamp",
    )
    last_activity: Optional[str] = Field(
        None,
        description="Last activity timestamp",
    )
    message_count: int = Field(
        default=0,
        description="Number of messages in session",
    )


# =============================================================================
# Room Models
# =============================================================================


class RoomAmenity(BaseModel):
    """Amenity included in a room."""

    name: str = Field(..., description="Amenity name in English")
    name_th: Optional[str] = Field(None, description="Amenity name in Thai")
    icon: Optional[str] = Field(None, description="Icon name for UI (e.g., 'wifi', 'tv')")


class RoomTypeResponse(BaseModel):
    """Response model for room type information."""

    room_type_id: int = Field(..., description="Room type ID")
    name: str = Field(..., description="Room type name in English")
    name_th: Optional[str] = Field(None, description="Room type name in Thai")
    description: Optional[str] = Field(None, description="Description in English")
    description_th: Optional[str] = Field(None, description="Description in Thai")
    base_price: float = Field(..., description="Base price per night in THB")
    max_occupancy: int = Field(..., description="Maximum number of guests")
    size_sqm: Optional[int] = Field(None, description="Room size in square meters")
    bed_type: Optional[str] = Field(None, description="Bed configuration")
    view_type: Optional[str] = Field(None, description="View type (city, pool, garden)")
    amenities: List[str] = Field(default=[], description="List of amenities")
    photos: List[str] = Field(default=[], description="URLs to room photos")
    available_count: Optional[int] = Field(None, description="Number of available rooms of this type")


class RoomResponse(BaseModel):
    """Response model for individual room information."""

    room_id: int = Field(..., description="Unique room ID")
    room_number: str = Field(..., description="Room number (e.g., '501')")
    floor: int = Field(..., description="Floor number")
    status: str = Field(
        ...,
        description="Room status: 'available', 'occupied', 'cleaning', 'maintenance'",
        examples=["available", "occupied"],
    )
    view_type: Optional[str] = Field(None, description="View from this specific room")
    last_cleaned: Optional[str] = Field(None, description="Last cleaning timestamp")
    room_type: RoomTypeResponse = Field(..., description="Room type details")


class RoomListResponse(BaseModel):
    """Response model for room listing endpoint."""

    rooms: List[RoomTypeResponse] = Field(..., description="List of room types")
    total: int = Field(..., description="Total number of room types")


class RoomDetailResponse(BaseModel):
    """Response model for detailed room information."""

    room: RoomResponse = Field(..., description="Room details")
    pricing: Dict[str, Any] = Field(
        default={},
        description="Pricing breakdown (base_price, taxes, fees)",
    )
    availability: Optional[Dict[str, Any]] = Field(
        None,
        description="Availability info for next 30 days",
    )


# =============================================================================
# Booking Models
# =============================================================================


class GuestInfo(BaseModel):
    """Guest information for booking."""

    guest_id: int = Field(..., description="Guest ID")
    first_name: str = Field(..., description="First name in English")
    last_name: str = Field(..., description="Last name in English")
    first_name_th: Optional[str] = Field(None, description="First name in Thai")
    last_name_th: Optional[str] = Field(None, description="Last name in Thai")
    email: str = Field(..., description="Email address")
    phone: Optional[str] = Field(None, description="Phone number")
    loyalty_tier: Optional[str] = Field(None, description="Loyalty program tier")
    loyalty_points: Optional[int] = Field(None, description="Loyalty points balance")


class BookingInfo(BaseModel):
    """Detailed booking/reservation information."""

    reservation_id: int = Field(..., description="Reservation ID")
    confirmation_number: str = Field(
        ...,
        description="Confirmation number (e.g., HTL240215001)",
        examples=["HTL240215001"],
    )
    guest: GuestInfo = Field(..., description="Guest information")
    room_number: str = Field(..., description="Assigned room number")
    room_type: str = Field(..., description="Room type name")
    room_type_th: Optional[str] = Field(None, description="Room type name in Thai")
    check_in_date: str = Field(..., description="Check-in date (YYYY-MM-DD)")
    check_out_date: str = Field(..., description="Check-out date (YYYY-MM-DD)")
    num_nights: int = Field(..., description="Number of nights")
    num_guests: int = Field(..., description="Number of guests")
    status: str = Field(
        ...,
        description="Reservation status",
        examples=["pending", "confirmed", "checked_in", "checked_out", "cancelled"],
    )
    total_amount: float = Field(..., description="Total amount in THB")
    payment_status: str = Field(
        ...,
        description="Payment status",
        examples=["pending", "paid", "refunded"],
    )
    special_requests: Optional[str] = Field(None, description="Special requests")
    booking_source: Optional[str] = Field(None, description="Booking source")
    cancellation_reason: Optional[str] = Field(None, description="Cancellation reason if cancelled")
    created_at: str = Field(..., description="Booking creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class BookingListResponse(BaseModel):
    """Response model for booking list endpoint."""

    bookings: List[BookingInfo] = Field(..., description="List of bookings")
    total: int = Field(..., description="Total number of bookings")
    page: int = Field(default=1, description="Current page number")
    page_size: int = Field(default=20, description="Items per page")


class BookingUpdateRequest(BaseModel):
    """Request model for PATCH /bookings/{reservation_id} endpoint."""

    check_in_date: Optional[date] = Field(
        None,
        description="New check-in date (YYYY-MM-DD)",
        examples=["2025-02-15"],
    )
    check_out_date: Optional[date] = Field(
        None,
        description="New check-out date (YYYY-MM-DD)",
        examples=["2025-02-17"],
    )
    room_number: Optional[str] = Field(
        None,
        description="New room number",
        examples=["502"],
    )
    num_guests: Optional[int] = Field(
        None,
        ge=1,
        le=10,
        description="Updated number of guests",
    )
    special_requests: Optional[str] = Field(
        None,
        max_length=1000,
        description="Updated special requests",
    )


class BookingUpdateResponse(BaseModel):
    """Response model for PATCH /bookings/{reservation_id} endpoint."""

    success: bool = Field(..., description="Whether the update was successful")
    message: str = Field(..., description="Human-readable message in Thai/English")
    booking: Optional[BookingInfo] = Field(None, description="Updated booking details")
    changes: Dict[str, Any] = Field(
        default={},
        description="Fields that were changed with old and new values",
    )


# =============================================================================
# Session Message Models
# =============================================================================


class ConversationMessage(BaseModel):
    """A single message in a conversation."""

    message_id: Optional[int] = Field(None, description="Message ID")
    role: str = Field(
        ...,
        description="Message role: 'user' or 'assistant'",
        examples=["user", "assistant"],
    )
    content: str = Field(..., description="Message content")
    timestamp: str = Field(..., description="Message timestamp (ISO format)")
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata (sources, tool_calls, etc.)",
    )


class ConversationHistoryResponse(BaseModel):
    """Response model for GET /sessions/{session_id}/messages endpoint."""

    session_id: str = Field(..., description="Session ID")
    messages: List[ConversationMessage] = Field(..., description="List of messages")
    total: int = Field(..., description="Total number of messages")
    has_more: bool = Field(default=False, description="Whether there are more messages")


# =============================================================================
# Room Availability Models (for calendar view)
# =============================================================================


class RoomAvailabilityDay(BaseModel):
    """Availability for a single day."""

    date: str = Field(..., description="Date (YYYY-MM-DD)")
    available: bool = Field(..., description="Whether rooms are available")
    available_count: int = Field(..., description="Number of available rooms")
    min_price: Optional[float] = Field(None, description="Minimum price for available rooms")


class RoomAvailabilityResponse(BaseModel):
    """Response model for room availability calendar."""

    room_type: Optional[str] = Field(None, description="Room type filter if applied")
    start_date: str = Field(..., description="Start date of range")
    end_date: str = Field(..., description="End date of range")
    availability: List[RoomAvailabilityDay] = Field(..., description="Daily availability")


# =============================================================================
# Guest Registration Models
# =============================================================================


class GuestCreateRequest(BaseModel):
    """Request model for POST /guests endpoint (guest registration)."""

    email: str = Field(
        ...,
        description="Guest email address (used as unique identifier)",
        examples=["guest@example.com"],
    )
    first_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="First name",
        examples=["John"],
    )
    last_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Last name",
        examples=["Smith"],
    )


class GuestResponse(BaseModel):
    """Response model for guest information."""

    guest_id: int = Field(..., description="Unique guest ID")
    email: str = Field(..., description="Guest email address")
    first_name: str = Field(..., description="First name in English")
    last_name: str = Field(..., description="Last name in English")
    first_name_th: Optional[str] = Field(None, description="First name in Thai")
    last_name_th: Optional[str] = Field(None, description="Last name in Thai")
    phone: Optional[str] = Field(None, description="Phone number")
    nationality: Optional[str] = Field(None, description="Nationality")
    loyalty_tier: Optional[str] = Field(None, description="Loyalty program tier")
    loyalty_points: Optional[int] = Field(None, description="Loyalty points balance")
    created_at: str = Field(..., description="Registration timestamp (ISO format)")
    updated_at: Optional[str] = Field(None, description="Last update timestamp")


class GuestUpdateRequest(BaseModel):
    """Request model for PATCH /guests/{guest_id} endpoint."""

    first_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="First name in English",
    )
    last_name: Optional[str] = Field(
        None,
        min_length=1,
        max_length=100,
        description="Last name in English",
    )
    first_name_th: Optional[str] = Field(
        None,
        max_length=100,
        description="First name in Thai",
    )
    last_name_th: Optional[str] = Field(
        None,
        max_length=100,
        description="Last name in Thai",
    )
    phone: Optional[str] = Field(
        None,
        max_length=20,
        description="Phone number",
    )
    nationality: Optional[str] = Field(
        None,
        max_length=50,
        description="Nationality",
    )
    address: Optional[str] = Field(
        None,
        max_length=500,
        description="Full address",
    )


class GuestCreateResponse(BaseModel):
    """Response model for POST /guests endpoint."""

    success: bool = Field(..., description="Whether registration was successful")
    message: str = Field(..., description="Human-readable message in Thai/English")
    guest: Optional[GuestResponse] = Field(None, description="Registered guest details")


# =============================================================================
# Authentication Models
# =============================================================================


class UserRegisterRequest(BaseModel):
    """Request model for POST /auth/register endpoint."""

    username: str = Field(
        ...,
        min_length=3,
        max_length=64,
        pattern=r"^[a-zA-Z0-9_.\-]+$",
        description="Unique username (letters, numbers, . _ -)",
        examples=["john_doe", "jane.smith"],
    )
    email: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="Email address (must be unique)",
        examples=["user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Password (minimum 8 characters)",
    )
    full_name: Optional[str] = Field(
        None,
        max_length=200,
        description="Full display name (optional)",
    )


class UserLoginRequest(BaseModel):
    """Request model for POST /auth/login endpoint."""

    username: str = Field(
        ...,
        description="Username or email address",
        examples=["john_doe", "user@example.com"],
    )
    password: str = Field(
        ...,
        min_length=1,
        description="Account password",
    )


class UserResponse(BaseModel):
    """Public user information (excludes password_hash)."""

    user_id: int = Field(..., description="Unique user ID")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    role: str = Field(
        ...,
        description="Account role: 'user' or 'admin'",
        examples=["user", "admin"],
    )
    full_name: Optional[str] = Field(None, description="Full display name")
    is_active: bool = Field(True, description="Whether the account is active")
    guest_id: Optional[int] = Field(
        None,
        description="Linked guest_id if user has a guest profile",
    )
    last_login: Optional[str] = Field(None, description="Last login timestamp (ISO)")
    created_at: str = Field(..., description="Account creation timestamp (ISO)")


class TokenResponse(BaseModel):
    """Response model for /auth/login and /auth/register."""

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type (always 'bearer')")
    expires_in: int = Field(..., description="Token lifetime in seconds")
    user: UserResponse = Field(..., description="Authenticated user profile")


# =============================================================================
# Admin Models
# =============================================================================


class AdminRoomStatusRequest(BaseModel):
    """Request to update room status."""
    status: str = Field(..., description="New status: available, occupied, maintenance, cleaning")
    notes: Optional[str] = Field(None, description="Admin notes")


class AdminBookingStatusRequest(BaseModel):
    """Request to override booking status."""
    status: str = Field(..., description="New status: pending, confirmed, checked_in, checked_out, cancelled, no_show")
    notes: Optional[str] = Field(None, description="Admin notes / reason")


class AdminChatOverrideRequest(BaseModel):
    """Admin sends a message directly to a guest session (overriding bot)."""
    session_id: str = Field(..., description="Target session ID")
    message: str = Field(..., min_length=1, max_length=4096, description="Admin message to guest")


class AdminChatOverrideResponse(BaseModel):
    """Response after admin chat override."""
    success: bool
    session_id: str
    message: str


# =============================================================================
# Dashboard Models
# =============================================================================


class DashboardStatsResponse(BaseModel):
    """Hotel dashboard overview statistics."""
    rooms: Dict[str, Any] = Field(..., description="Room status breakdown")
    reservations: Dict[str, Any] = Field(..., description="Reservation status breakdown")
    today_new_bookings: int = Field(0, description="Bookings created today")
    today_checkins: int = Field(0, description="Expected check-ins today")
    today_checkouts: int = Field(0, description="Expected check-outs today")
    total_revenue: float = Field(0, description="Total revenue (non-cancelled)")
    today_revenue: float = Field(0, description="Revenue from today's bookings")
    total_guests: int = Field(0, description="Total registered guests")
    service_requests: Dict[str, Any] = Field(default_factory=dict, description="Service request status breakdown")
    occupancy_rate: float = Field(0, description="Current occupancy percentage")


class RecentBookingItem(BaseModel):
    """Single recent booking for dashboard feed."""
    reservation_id: int
    confirmation_number: Optional[str] = None
    status: str
    check_in_date: Any
    check_out_date: Any
    total_amount: Optional[float] = None
    created_at: Any
    booking_source: Optional[str] = None
    room_number: Optional[str] = None
    room_type: Optional[str] = None
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class SessionStatsResponse(BaseModel):
    """Conversation session statistics."""
    total_sessions: int = 0
    total_messages: int = 0
    user_messages: int = 0
    bot_messages: int = 0
    admin_messages: int = 0
