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

    model: str = Field(
        ...,
        description="Current LLM model name",
        examples=["qwen/qwen3-max"],
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
    available_models: List[Dict[str, str]] = Field(
        ...,
        description="List of available LLM models",
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
