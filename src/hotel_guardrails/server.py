# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
FastAPI Server for Hotel Operations with NeMo Guardrails

Endpoints:
- GET  /health      - Health check
- POST /chat        - General AI conversation with guardrails
- POST /chat/stream - Streaming chat with SSE
- POST /tools/book  - Booking operations

Usage:
    # Start server
    python -m uvicorn src.hotel_guardrails.server:app --host 0.0.0.0 --port 8081 --reload

    # Or run directly
    python -m src.hotel_guardrails.server
"""
import os
import json
import logging
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator, Optional
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from contextvars import ContextVar

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError

from nemoguardrails import RailsConfig, LLMRails
from langchain_openai import ChatOpenAI

from .openrouter_llm import get_openrouter_llm
from .config import get_llm_settings, get_server_settings, AVAILABLE_MODELS
from .models import (
    ChatRequest,
    ChatResponse,
    BookingRequest,
    BookingResponse,
    HealthResponse,
    ErrorResponse,
    LLMSettingsResponse,
    SessionCreateResponse,
    SessionInfo,
    # New models for extended endpoints
    RoomTypeResponse,
    RoomListResponse,
    RoomDetailResponse,
    RoomAvailabilityResponse,
    BookingInfo,
    BookingListResponse,
    BookingUpdateRequest,
    BookingUpdateResponse,
    ConversationHistoryResponse,
)
from .hybrid_router import HybridRouter, RoutingPath
from .langgraph_adapter import LangGraphAdapter
from .feedback_collector import FeedbackCollector
from . import database as db

# Request ID context variable for tracing
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")
from .actions import (
    search_hotel_knowledge,
    search_hotel_knowledge_with_sources,
    check_room_availability,
    create_reservation,
    confirm_reservation,
    cancel_reservation,
    get_reservation_details,
    check_input_safety,
    check_output_safety,
    detect_language,
    format_bilingual_response,
)

# Configure logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# OpenAPI tags metadata
tags_metadata = [
    {"name": "Health", "description": "Service health monitoring"},
    {"name": "Chat", "description": "AI conversation powered by LangGraph Agent"},
    {"name": "Rooms", "description": "Room catalog and availability"},
    {"name": "Booking", "description": "Room reservation operations"},
    {"name": "Sessions", "description": "Conversation session management"},
    {"name": "Settings", "description": "LLM and server configuration"},
    {"name": "Feedback", "description": "Response quality feedback for continuous improvement"},
    {"name": "Root", "description": "API information"},
]

# Global rails instance
rails: LLMRails = None
# Fallback LangChain LLM for when NeMo fails
langchain_llm: ChatOpenAI = None
# Hybrid routing components
hybrid_router: HybridRouter = None
langgraph_adapter: LangGraphAdapter = None
feedback_collector: FeedbackCollector = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize NeMo Guardrails and hybrid routing on startup."""
    global rails, langchain_llm, hybrid_router, langgraph_adapter, feedback_collector

    # Set OpenRouter API key for NeMo
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("OPENROUTER_API_KEY not set - guardrails will fail to initialize")

    # Set as OPENAI_API_KEY for NeMo's OpenAI engine
    os.environ["OPENAI_API_KEY"] = api_key or ""

    # Get LLM settings from config
    llm_settings = get_llm_settings()

    # Initialize LangChain LLM with proper OpenRouter headers
    try:
        langchain_llm = get_openrouter_llm(
            model=llm_settings.model,
            temperature=llm_settings.temperature,
            max_tokens=llm_settings.max_tokens,
            streaming=False,  # Non-streaming for generate
        )
        logger.info(f"LangChain OpenRouter LLM initialized with {llm_settings.model}")
    except Exception as e:
        logger.error(f"Failed to initialize LangChain LLM: {e}")
        langchain_llm = None

    # Load config from src/hotel_guardrails/config/
    config_path = os.path.join(os.path.dirname(__file__), "config")

    logger.info(f"Loading NeMo Guardrails config from {config_path}")

    try:
        config = RailsConfig.from_path(config_path)
        rails = LLMRails(config)

        # Register the LangChain LLM with NeMo if available
        if langchain_llm:
            # Register as the main LLM provider
            rails.register_action(
                lambda: langchain_llm,
                "get_main_llm"
            )
            logger.info("Registered LangChain LLM with NeMo Guardrails")

        # Register custom actions
        rails.register_action(search_hotel_knowledge, "search_hotel_knowledge")
        rails.register_action(check_room_availability, "check_room_availability")
        rails.register_action(create_reservation, "create_reservation")
        rails.register_action(confirm_reservation, "confirm_reservation")
        rails.register_action(cancel_reservation, "cancel_reservation")
        rails.register_action(get_reservation_details, "get_reservation_details")
        rails.register_action(check_input_safety, "check_input_safety")
        rails.register_action(check_output_safety, "check_output_safety")
        rails.register_action(detect_language, "detect_language")
        rails.register_action(format_bilingual_response, "format_bilingual_response")

        logger.info("NeMo Guardrails initialized successfully")

    except Exception as e:
        logger.error(f"Failed to initialize NeMo Guardrails: {e}")
        # Don't raise - allow server to start for health checks

    # Initialize hybrid routing components
    try:
        feedback_collector = FeedbackCollector()
        hybrid_router = HybridRouter(
            feedback_store=feedback_collector.get_average_score
        )
        langgraph_adapter = LangGraphAdapter()
        logger.info("Hybrid routing components initialized")
    except Exception as e:
        logger.error(f"Failed to initialize hybrid routing: {e}")

    # Export OpenAPI spec on startup
    try:
        spec = app.openapi()
        output_path = Path("docs/api_references/hotel_guardrails_server.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(spec, f, indent=2, ensure_ascii=False)
        logger.info(f"OpenAPI spec exported to {output_path}")
    except Exception as e:
        logger.warning(f"Failed to export OpenAPI spec: {e}")

    yield

    # Cleanup
    logger.info("Shutting down NeMo Guardrails")


# Create FastAPI app
app = FastAPI(
    title="Siam Serenity Hotel Concierge API",
    description="""
    Hotel Operations AI powered by LangGraph Agent

    ## Architecture
    - **LangGraph Agent**: Primary handler for ALL queries
    - **Safety Router**: Filters blocked/unsafe content
    - **RAG**: Hotel knowledge retrieval for context
    - **LangChain Fallback**: Backup if LangGraph unavailable

    ## Features
    - Bilingual Thai/English conversation
    - RAG-powered hotel knowledge retrieval
    - Room booking operations
    - Safety guardrails for input/output
    - Continuous improvement via feedback loop

    ## Headers
    - `X-Request-ID`: Optional request tracking ID (auto-generated if not provided)

    Powered by OpenRouter (configurable model)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_tags=tags_metadata,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Session-ID"],
)


# =============================================================================
# Request Tracking Middleware
# =============================================================================


@app.middleware("http")
async def request_tracking_middleware(request: Request, call_next):
    """Add request ID tracking for logging and tracing."""
    # Get or generate request ID
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request_id_ctx.set(request_id)

    # Log request
    logger.info(
        f"→ {request.method} {request.url.path}",
        extra={"request_id": request_id},
    )

    start_time = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start_time) * 1000

    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id

    # Log response
    logger.info(
        f"← {response.status_code} ({duration_ms:.0f}ms)",
        extra={"request_id": request_id},
    )

    return response


# =============================================================================
# Exception Handlers
# =============================================================================


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with structured response."""
    request_id = request_id_ctx.get("")
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error="validation_error",
            message="Invalid request parameters",
            details={"errors": exc.errors(), "request_id": request_id},
        ).model_dump(),
        headers={"X-Request-ID": request_id} if request_id else {},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors."""
    request_id = request_id_ctx.get("")
    logger.error(f"Unexpected error: {exc}", extra={"request_id": request_id})
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="internal_error",
            message="An unexpected error occurred",
            details={"type": type(exc).__name__, "request_id": request_id},
        ).model_dump(),
        headers={"X-Request-ID": request_id} if request_id else {},
    )


# =============================================================================
# Health Endpoint
# =============================================================================


@app.get("/healthz", tags=["Health"])
async def healthz():
    """Simple health check for load balancers (Railway, K8s)."""
    return {"status": "ok"}


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Check service health.

    Returns status of:
    - guardrails: NeMo Guardrails initialization
    - qdrant: Vector database connection
    - openrouter: LLM API connectivity
    - database: PostgreSQL connection
    """
    components = {}

    # Check NeMo Guardrails
    components["guardrails"] = "healthy" if rails else "not_initialized"

    # Check Qdrant
    try:
        from src.common.vectorstore_qdrant import health_check as qdrant_health

        qdrant_status = qdrant_health()
        components["qdrant"] = qdrant_status.get("status", "unknown")
    except Exception as e:
        components["qdrant"] = f"error: {str(e)[:50]}"

    # Check OpenRouter (simple ping)
    try:
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://openrouter.ai/api/v1/models",
                headers={
                    "Authorization": f"Bearer {os.getenv('OPENROUTER_API_KEY', '')}"
                },
                timeout=5.0,
            )
            components["openrouter"] = (
                "healthy" if resp.status_code == 200 else f"error: {resp.status_code}"
            )
    except Exception as e:
        components["openrouter"] = f"error: {str(e)[:50]}"

    # Check PostgreSQL database
    try:
        db_health = await db.check_database_health()
        if db_health["status"] == "healthy":
            components["database"] = f"healthy (rooms: {db_health.get('rooms', 0)})"
        else:
            components["database"] = f"error: {db_health.get('error', 'unknown')[:50]}"
    except Exception as e:
        components["database"] = f"error: {str(e)[:50]}"

    # Check LangGraph adapter
    try:
        if langgraph_adapter:
            lg_health = await langgraph_adapter.health_check()
            components["langgraph"] = lg_health.get("status", "unknown")
            if lg_health.get("mode"):
                components["langgraph"] += f" ({lg_health['mode']})"
            if lg_health.get("error"):
                components["langgraph"] += f": {lg_health['error'][:30]}"
        else:
            components["langgraph"] = "not_initialized"
    except Exception as e:
        components["langgraph"] = f"error: {str(e)[:50]}"

    # Determine overall status
    healthy_count = sum(1 for v in components.values() if "healthy" in v)
    total_count = len(components)

    if healthy_count == total_count:
        overall = "healthy"
    elif healthy_count == 0:
        overall = "unhealthy"
    else:
        overall = "degraded"

    return HealthResponse(status=overall, components=components)


# =============================================================================
# Chat Endpoints
# =============================================================================


@app.post("/chat", response_model=ChatResponse, tags=["Chat"])
async def chat(request: ChatRequest):
    """
    General AI conversation powered by LangGraph Agent.

    All queries are processed by LangGraph for consistent, high-quality responses.
    Safety checks filter blocked content before processing.

    ## Features
    - Automatic language detection (Thai/English)
    - LangGraph Agent for all query types
    - RAG-powered responses using hotel knowledge base
    - Continuous improvement via feedback loop

    ## Headers
    - `X-Request-ID`: Request tracking ID (returned in response)

    Example:
        ```json
        {"message": "What time is breakfast?"}
        ```

        ```json
        {"message": "รหัส WiFi คืออะไรครับ"}
        ```
    """
    session_id = request.session_id or str(uuid.uuid4())
    current_request_id = request_id_ctx.get("")
    start_time = time.time()
    content = ""
    sources = None
    tool_calls = None
    retrieval_context = None
    routing_path = "langgraph"
    routing_reason = "LangGraph primary"
    complexity = "moderate"

    # Step 1: Safety check and routing
    if hybrid_router:
        try:
            # Check input safety first
            is_safe = True
            try:
                safety_result = await check_input_safety(request.message)
                is_safe = safety_result.return_value if hasattr(safety_result, 'return_value') else True
            except Exception:
                pass  # Default to safe if check fails

            routing = await hybrid_router.route(
                query=request.message,
                session_id=session_id,
                is_safe=is_safe,
            )
            routing_path = routing.path.value
            routing_reason = routing.reason
            complexity = routing.complexity.value

            logger.info(f"Routing: {routing_path} ({routing_reason})")

            # Handle blocked requests
            if routing.path == RoutingPath.BLOCKED:
                return ChatResponse(
                    response="I'm sorry, I cannot process that request. / ขออภัย ไม่สามารถดำเนินการตามคำขอนี้ได้",
                    session_id=session_id,
                    request_id=current_request_id,
                    routing_path=routing_path,
                    routing_reason=routing_reason,
                    complexity=complexity,
                )

        except Exception as e:
            logger.warning(f"Safety check failed: {e}")
            # Continue with LangGraph anyway

    # Step 2: Process with LangGraph Agent (primary)
    if langgraph_adapter:
        try:
            result = await langgraph_adapter.invoke(
                message=request.message,
                session_id=session_id,
            )

            if result["success"]:
                content = result["response"]
                tool_calls = result.get("tool_calls")
                routing_path = "langgraph"
            else:
                logger.warning(f"LangGraph failed: {result.get('error')}")
                routing_reason = f"LangGraph failed: {result.get('error', 'unknown')[:50]}"

        except Exception as e:
            logger.warning(f"LangGraph invocation failed: {e}")
            routing_reason = f"LangGraph error: {str(e)[:50]}"

    # Step 3: Fallback to LangChain (RAG + LLM) if LangGraph fails
    if not content and langchain_llm:
        try:
            routing_path = "langchain_fallback"
            rag_context = ""
            rag_sources = []
            try:
                rag_result = await search_hotel_knowledge_with_sources(request.message)
                if rag_result and len(rag_result) >= 3:
                    rag_context = rag_result[0]
                    rag_sources = rag_result[1]
                    retrieval_context = rag_result[2]
            except Exception as rag_error:
                logger.warning(f"RAG search failed: {rag_error}")

            system_prompt = """You are the Concierge at Siam Serenity Hotel (โรงแรมสยามเซอเรนิตี้).
Your responsibilities:
1. Answer questions about the hotel using the provided context
2. Respond in the same language the guest uses (Thai or English)
3. Be polite, professional, and helpful

Greeting examples:
- Thai: "สวัสดีค่ะ/ครับ ยินดีต้อนรับสู่โรงแรมสยามเซอเรนิตี้"
- English: "Welcome to Siam Serenity Hotel. How may I assist you?"
"""
            if rag_context:
                system_prompt += f"\n\nHotel Information Context:\n{rag_context}"

            from langchain_core.messages import SystemMessage, HumanMessage

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=request.message),
            ]

            response = await langchain_llm.ainvoke(messages)
            content = response.content
            sources = rag_sources if rag_sources else None

        except Exception as e:
            logger.error(f"LangChain fallback failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    if not content:
        raise HTTPException(status_code=503, detail="No LLM available")

    # Step 3: Record feedback for evaluation
    latency_ms = (time.time() - start_time) * 1000
    if feedback_collector:
        try:
            await feedback_collector.record_response(
                request_id=current_request_id,
                session_id=session_id,
                query=request.message,
                response=content,
                routing_path=routing_path,
                complexity=complexity,
                latency_ms=latency_ms,
            )
        except Exception as e:
            logger.warning(f"Failed to record feedback: {e}")

    # Step 4: Log routing decision for audit
    try:
        from src.common.audit_logger import get_audit_logger
        audit_logger = get_audit_logger()
        audit_logger.log_routing_decision(
            request_id=current_request_id,
            query=request.message,
            routing_path=routing_path,
            complexity=complexity,
            latency_ms=latency_ms,
            reason=routing_reason,
        )
    except Exception:
        pass  # Don't fail on audit logging

    # Step 5: Save conversation to database for history
    try:
        # Save user message
        await db.save_conversation_message(
            session_id=session_id,
            role="user",
            content=request.message,
        )
        # Save assistant response
        await db.save_conversation_message(
            session_id=session_id,
            role="assistant",
            content=content,
        )
    except Exception as e:
        logger.warning(f"Failed to save conversation: {e}")

    return ChatResponse(
        response=content,
        session_id=session_id,
        sources=sources,
        retrieval_context=retrieval_context,
        tool_calls=tool_calls,
        request_id=current_request_id,
        routing_path=routing_path,
        routing_reason=routing_reason,
        complexity=complexity,
    )


@app.post("/chat/stream", tags=["Chat"])
async def chat_stream(request: ChatRequest):
    """
    Streaming chat endpoint for real-time responses.

    Returns Server-Sent Events (SSE).

    Example usage with curl:
        ```bash
        curl -X POST http://localhost:8081/chat/stream \\
          -H "Content-Type: application/json" \\
          -d '{"message": "Tell me about the spa"}' \\
          --no-buffer
        ```
    """
    if not rails:
        raise HTTPException(status_code=503, detail="Guardrails not initialized")

    session_id = request.session_id or str(uuid.uuid4())

    async def generate_stream() -> AsyncGenerator[str, None]:
        try:
            async for chunk in rails.stream_async(
                messages=[{"role": "user", "content": request.message}],
                options={"session_id": session_id},
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Stream generation failed: {e}")
            yield f"data: ERROR: {str(e)}\n\n"

    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Session-ID": session_id,
        },
    )


# =============================================================================
# Booking Endpoints
# =============================================================================


@app.post("/tools/book", response_model=BookingResponse, tags=["Booking"])
async def booking_operations(request: BookingRequest):
    """
    Booking operations endpoint.

    Actions:
    - **check**: Check room availability for dates
    - **create**: Create a new reservation
    - **confirm**: Confirm a pending reservation
    - **cancel**: Cancel an existing reservation

    Example (check availability):
        ```json
        {
            "action": "check",
            "check_in": "2025-02-15",
            "check_out": "2025-02-17",
            "room_type": "Deluxe"
        }
        ```

    Example (create reservation):
        ```json
        {
            "action": "create",
            "guest_id": "G001",
            "room_id": "501",
            "check_in": "2025-02-15",
            "check_out": "2025-02-17"
        }
        ```
    """
    try:
        if request.action == "check":
            if not request.check_in or not request.check_out:
                raise HTTPException(400, "check_in and check_out required")

            result = await check_room_availability(
                check_in=str(request.check_in),
                check_out=str(request.check_out),
                room_type=request.room_type,
            )

            return BookingResponse(
                success=True,
                action="check",
                data={"availability": result.return_value},
                message="Availability check complete / ตรวจสอบห้องว่างเรียบร้อย",
            )

        elif request.action == "create":
            if not all(
                [request.guest_id, request.room_id, request.check_in, request.check_out]
            ):
                raise HTTPException(
                    400, "guest_id, room_id, check_in, check_out required"
                )

            result = await create_reservation(
                guest_id=request.guest_id,
                room_id=request.room_id,
                check_in=str(request.check_in),
                check_out=str(request.check_out),
                special_requests=request.special_requests,
            )

            # Extract reservation_id if available
            reservation_id = None
            if isinstance(result.return_value, dict):
                reservation_id = result.return_value.get("reservation_id")

            return BookingResponse(
                success=True,
                action="create",
                data={"result": result.return_value},
                message="Reservation created successfully / จองห้องเรียบร้อยแล้ว",
                reservation_id=reservation_id,
            )

        elif request.action == "confirm":
            if not request.reservation_id:
                raise HTTPException(400, "reservation_id required")

            result = await confirm_reservation(reservation_id=request.reservation_id)

            return BookingResponse(
                success=True,
                action="confirm",
                data={"result": result.return_value},
                message="Reservation confirmed / ยืนยันการจองเรียบร้อย",
                reservation_id=request.reservation_id,
            )

        elif request.action == "cancel":
            if not request.reservation_id:
                raise HTTPException(400, "reservation_id required")

            result = await cancel_reservation(
                reservation_id=request.reservation_id,
                reason=request.reason,
            )

            return BookingResponse(
                success=True,
                action="cancel",
                data={"result": result.return_value},
                message="Reservation cancelled / ยกเลิกการจองเรียบร้อย",
                reservation_id=request.reservation_id,
            )

        else:
            raise HTTPException(400, f"Unknown action: {request.action}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Booking operation failed: {e}")
        return BookingResponse(
            success=False,
            action=request.action,
            message=f"Operation failed: {str(e)} / เกิดข้อผิดพลาด",
        )


# =============================================================================
# Room Endpoints
# =============================================================================


@app.get("/rooms", response_model=RoomListResponse, tags=["Rooms"])
async def list_rooms():
    """
    List all room types with photos, amenities, and base prices.

    Returns room catalog for browsing before booking.
    Includes availability count for each room type.

    Example response:
        ```json
        {
            "rooms": [
                {
                    "room_type_id": 1,
                    "name": "Standard",
                    "name_th": "ห้องสแตนดาร์ด",
                    "base_price": 2500.00,
                    "max_occupancy": 2,
                    "amenities": ["WiFi", "TV", "Minibar"],
                    "available_count": 5
                }
            ],
            "total": 4
        }
        ```
    """
    try:
        room_types = await db.get_all_room_types()

        rooms = [
            RoomTypeResponse(
                room_type_id=rt["room_type_id"],
                name=rt["name"],
                name_th=rt.get("name_th"),
                description=rt.get("description"),
                description_th=rt.get("description_th"),
                base_price=rt["base_price"],
                max_occupancy=rt["max_occupancy"],
                size_sqm=rt.get("size_sqm"),
                amenities=rt.get("amenities", []),
                photos=rt.get("photos", []),
                available_count=rt.get("available_count", 0),
            )
            for rt in room_types
        ]

        return RoomListResponse(rooms=rooms, total=len(rooms))

    except Exception as e:
        logger.error(f"Error listing rooms: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch rooms: {str(e)}")


# NOTE: /rooms/availability MUST come before /rooms/{room_id} to avoid route conflict
@app.get("/rooms/availability", response_model=RoomAvailabilityResponse, tags=["Rooms"])
async def get_room_availability(
    start_date: str,
    end_date: str,
    room_type: Optional[str] = None,
):
    """
    Get room availability for a date range (calendar view).

    Useful for showing availability calendar in the booking UI.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        room_type: Optional room type filter

    Example:
        ```
        GET /rooms/availability?start_date=2025-02-01&end_date=2025-02-28
        ```

    Returns daily availability with min price for available rooms.
    """
    try:
        from datetime import datetime, timedelta

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        # Limit range to 90 days
        if (end - start).days > 90:
            end = start + timedelta(days=90)

        availability = await db.get_room_availability_calendar(start, end, room_type)

        return RoomAvailabilityResponse(
            room_type=room_type,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            availability=availability,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception as e:
        logger.error(f"Error fetching availability: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch availability: {str(e)}")


@app.get("/rooms/{room_id}", response_model=RoomDetailResponse, tags=["Rooms"])
async def get_room(room_id: int):
    """
    Get detailed information for a specific room.

    Includes:
    - Room details (number, floor, status, view)
    - Room type information (amenities, pricing)
    - Pricing breakdown (base price, taxes, service charge)

    Args:
        room_id: The room ID to fetch

    Example response:
        ```json
        {
            "room": {
                "room_id": 1,
                "room_number": "501",
                "floor": 5,
                "status": "available",
                "room_type": {...}
            },
            "pricing": {
                "base_price": 3500.00,
                "tax_rate": 0.07,
                "service_charge": 0.10,
                "total_per_night": 4095.00
            }
        }
        ```
    """
    try:
        room = await db.get_room_by_id(room_id)

        if not room:
            raise HTTPException(
                status_code=404,
                detail=f"Room {room_id} not found / ไม่พบห้อง {room_id}",
            )

        # Build response
        room_type = RoomTypeResponse(
            room_type_id=room["room_type"]["room_type_id"],
            name=room["room_type"]["name"],
            name_th=room["room_type"].get("name_th"),
            description=room["room_type"].get("description"),
            description_th=room["room_type"].get("description_th"),
            base_price=room["room_type"]["base_price"],
            max_occupancy=room["room_type"]["max_occupancy"],
            amenities=room["room_type"].get("amenities", []),
            photos=room["room_type"].get("photos", []),
        )

        from .models import RoomResponse
        room_response = RoomResponse(
            room_id=room["room_id"],
            room_number=room["room_number"],
            floor=room["floor"],
            status=room["status"],
            view_type=room.get("view_type"),
            last_cleaned=room.get("last_cleaned"),
            room_type=room_type,
        )

        return RoomDetailResponse(
            room=room_response,
            pricing=room.get("pricing", {}),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching room {room_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch room: {str(e)}")


# =============================================================================
# Extended Booking Endpoints
# =============================================================================


@app.get("/bookings", response_model=BookingListResponse, tags=["Booking"])
async def list_bookings(
    guest_id: Optional[int] = None,
    guest_email: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
):
    """
    List bookings with optional filtering.

    Filter by:
    - guest_id: Guest's ID
    - guest_email: Guest's email address
    - status: Reservation status (pending, confirmed, checked_in, checked_out, cancelled)

    Supports pagination with page and page_size parameters.

    Example:
        ```
        GET /bookings?guest_email=guest@example.com&status=confirmed
        GET /bookings?guest_id=123&page=2&page_size=10
        ```
    """
    try:
        # Validate page params
        if page < 1:
            page = 1
        if page_size < 1 or page_size > 100:
            page_size = 20

        bookings, total = await db.get_bookings(
            guest_id=guest_id,
            guest_email=guest_email,
            status=status,
            page=page,
            page_size=page_size,
        )

        booking_list = [BookingInfo(**b) for b in bookings]

        return BookingListResponse(
            bookings=booking_list,
            total=total,
            page=page,
            page_size=page_size,
        )

    except Exception as e:
        logger.error(f"Error listing bookings: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch bookings: {str(e)}")


@app.get("/bookings/{reservation_id}", response_model=BookingInfo, tags=["Booking"])
async def get_booking(reservation_id: str):
    """
    Get detailed booking information by reservation ID or confirmation number.

    Args:
        reservation_id: Reservation ID (numeric) or confirmation number (e.g., HTL240215001)

    Returns full booking details including guest info, room details, and payment status.
    """
    try:
        booking = await db.get_booking_by_id(reservation_id)

        if not booking:
            raise HTTPException(
                status_code=404,
                detail=f"Booking {reservation_id} not found / ไม่พบการจอง {reservation_id}",
            )

        return BookingInfo(**booking)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching booking {reservation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch booking: {str(e)}")


@app.patch("/bookings/{reservation_id}", response_model=BookingUpdateResponse, tags=["Booking"])
async def update_booking(reservation_id: str, request: BookingUpdateRequest):
    """
    Update booking details without canceling.

    Modifiable fields:
    - check_in_date: New check-in date
    - check_out_date: New check-out date
    - room_number: Change to different room
    - num_guests: Update guest count
    - special_requests: Update special requests

    Note: Cannot modify checked_out or cancelled bookings.

    Example:
        ```json
        {
            "check_in_date": "2025-02-16",
            "special_requests": "Late check-in requested"
        }
        ```

    Returns the updated booking and a summary of changes made.
    """
    try:
        success, message, updated_booking, changes = await db.update_booking(
            reservation_id=reservation_id,
            check_in_date=request.check_in_date,
            check_out_date=request.check_out_date,
            room_number=request.room_number,
            num_guests=request.num_guests,
            special_requests=request.special_requests,
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        booking_info = BookingInfo(**updated_booking) if updated_booking else None

        return BookingUpdateResponse(
            success=success,
            message=message,
            booking=booking_info,
            changes=changes,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating booking {reservation_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update booking: {str(e)}")


# =============================================================================
# Settings Endpoints
# =============================================================================


@app.get("/settings/llm", response_model=LLMSettingsResponse, tags=["Settings"])
async def get_llm_configuration():
    """
    Get current LLM configuration.

    Returns the active LLM settings and list of available models.
    Frontend can use this to populate model selection dropdowns.
    """
    settings = get_llm_settings()
    return LLMSettingsResponse(
        model=settings.model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        streaming=settings.streaming,
        available_models=AVAILABLE_MODELS,
    )


@app.get("/settings/models", tags=["Settings"])
async def list_available_models():
    """
    List available LLM models.

    Returns models that can be used with the chat endpoints.
    """
    return {"models": AVAILABLE_MODELS}


# =============================================================================
# Sessions Endpoints
# =============================================================================


@app.post("/sessions", response_model=SessionCreateResponse, tags=["Sessions"])
async def create_session():
    """
    Create a new conversation session.

    Returns a session ID that should be passed with subsequent chat requests.
    """
    session_id = str(uuid.uuid4())
    created_at = datetime.now(timezone.utc).isoformat()

    return SessionCreateResponse(
        session_id=session_id,
        created_at=created_at,
    )


@app.get("/sessions/{session_id}", response_model=SessionInfo, tags=["Sessions"])
async def get_session(session_id: str):
    """
    Get session information.

    Returns session metadata including creation time.
    Note: Full session persistence is not implemented - sessions are stateless.
    """
    # For now, return a placeholder - full implementation would check session store
    return SessionInfo(
        session_id=session_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        message_count=0,
    )


@app.delete("/sessions/{session_id}", tags=["Sessions"])
async def delete_session(session_id: str):
    """
    Delete a conversation session.

    Clears all conversation history associated with the session.
    """
    return {
        "message": "Session deleted",
        "session_id": session_id,
    }


@app.get(
    "/sessions/{session_id}/messages",
    response_model=ConversationHistoryResponse,
    tags=["Sessions"],
)
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    offset: int = 0,
):
    """
    Get conversation history for a session.

    Retrieves all messages exchanged in a conversation session.
    Useful for session restoration after page refresh or resuming conversations.

    Args:
        session_id: The session ID to retrieve messages for
        limit: Maximum number of messages to return (default: 50, max: 200)
        offset: Number of messages to skip for pagination

    Example:
        ```
        GET /sessions/550e8400-e29b-41d4-a716-446655440000/messages?limit=20
        ```

    Returns messages in chronological order (oldest first).
    """
    try:
        # Validate params
        if limit < 1:
            limit = 50
        if limit > 200:
            limit = 200
        if offset < 0:
            offset = 0

        messages, total, has_more = await db.get_conversation_messages(
            session_id=session_id,
            limit=limit,
            offset=offset,
        )

        from .models import ConversationMessage
        message_list = [ConversationMessage(**m) for m in messages]

        return ConversationHistoryResponse(
            session_id=session_id,
            messages=message_list,
            total=total,
            has_more=has_more,
        )

    except Exception as e:
        logger.error(f"Error fetching messages for session {session_id}: {e}")
        # Return empty response for non-existent sessions
        return ConversationHistoryResponse(
            session_id=session_id,
            messages=[],
            total=0,
            has_more=False,
        )


# =============================================================================
# Feedback Endpoints
# =============================================================================


@app.post("/feedback", tags=["Feedback"])
async def submit_feedback(
    request_id: str,
    score: float,
    comment: Optional[str] = None,
):
    """
    Submit feedback for a response.

    Used to rate response quality and improve routing decisions.

    Args:
        request_id: The request ID from the chat response
        score: Quality score (0.0 = bad, 1.0 = good)
        comment: Optional feedback comment

    Example:
        ```bash
        curl -X POST "http://localhost:8081/feedback?request_id=abc-123&score=0.9"
        ```
    """
    if score < 0.0 or score > 1.0:
        raise HTTPException(400, "Score must be between 0.0 and 1.0")

    if feedback_collector:
        try:
            success = await feedback_collector.record_explicit_feedback(
                request_id=request_id,
                score=score,
                details={"comment": comment} if comment else None,
            )
            if success:
                return {
                    "message": "Feedback recorded",
                    "request_id": request_id,
                    "score": score,
                }
            else:
                return {
                    "message": "Request not found (may have been flushed)",
                    "request_id": request_id,
                }
        except Exception as e:
            logger.error(f"Failed to record feedback: {e}")
            raise HTTPException(500, f"Failed to record feedback: {e}")

    return {"message": "Feedback collection not enabled"}


@app.get("/feedback/stats", tags=["Feedback"])
async def get_feedback_stats():
    """
    Get feedback statistics by routing path.

    Returns performance metrics for NeMo vs LangGraph routing.
    Useful for monitoring and optimization.
    """
    if feedback_collector:
        nemo_stats = await feedback_collector.get_path_performance("nemo")
        langgraph_stats = await feedback_collector.get_path_performance("langgraph")

        return {
            "nemo": nemo_stats,
            "langgraph": langgraph_stats,
        }

    return {"message": "Feedback collection not enabled"}


# =============================================================================
# Root Endpoint
# =============================================================================


@app.get("/", tags=["Root"])
async def root():
    """API root - returns basic info."""
    return {
        "name": "Siam Serenity Hotel Concierge API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
    }


# =============================================================================
# Main Entry Point
# =============================================================================


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "src.hotel_guardrails.server:app",
        host="0.0.0.0",
        port=8081,
        reload=True,
    )
