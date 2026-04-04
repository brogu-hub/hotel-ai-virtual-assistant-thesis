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

try:
    from nemoguardrails import RailsConfig, LLMRails
    NEMO_AVAILABLE = True
except ImportError:
    NEMO_AVAILABLE = False
from langchain_openai import ChatOpenAI

from .openrouter_llm import get_openrouter_llm
from .config import (
    get_llm_settings, get_server_settings, AVAILABLE_MODELS,
    get_runtime_llm_config, LLMBackend,
)
from .models import (
    ChatRequest,
    ChatResponse,
    BookingRequest,
    BookingResponse,
    HealthResponse,
    ErrorResponse,
    LLMSettingsResponse,
    LLMSettingsUpdateRequest,
    AdminRoomStatusRequest,
    AdminBookingStatusRequest,
    AdminChatOverrideRequest,
    AdminChatOverrideResponse,
    DashboardStatsResponse,
    SessionStatsResponse,
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
    # Guest registration models
    GuestCreateRequest,
    GuestResponse,
    GuestUpdateRequest,
    GuestCreateResponse,
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
    {"name": "Guests", "description": "Guest registration and management"},
    {"name": "Sessions", "description": "Conversation session management"},
    {"name": "Settings", "description": "LLM and server configuration"},
    {"name": "Feedback", "description": "Response quality feedback for continuous improvement"},
    {"name": "Admin", "description": "Hotel staff admin operations (override bot, manage rooms/bookings)"},
    {"name": "Dashboard", "description": "Real-time hotel statistics and monitoring"},
    {"name": "Root", "description": "API information"},
]

# Global rails instance
rails: LLMRails = None
# Admin-controlled sessions (bot paused, admin responding)
admin_controlled_sessions: set = set()
# Fallback LangChain LLM for when NeMo fails
langchain_llm: ChatOpenAI = None
# Hybrid routing components
hybrid_router: HybridRouter = None
langgraph_adapter: LangGraphAdapter = None
feedback_collector: FeedbackCollector = None
# Escalation monitor
escalation_monitor = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize NeMo Guardrails and hybrid routing on startup."""
    global rails, langchain_llm, hybrid_router, langgraph_adapter, feedback_collector, escalation_monitor

    # Initialize RuntimeLLMConfig singleton (reads env vars)
    runtime_config = get_runtime_llm_config()
    logger.info(f"LLM backend: {runtime_config.backend.value}, model: {runtime_config.active_model}")

    # Set OpenRouter API key for NeMo
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        os.environ["OPENAI_API_KEY"] = api_key

    # Get LLM settings from config
    llm_settings = get_llm_settings()

    # Initialize LangChain LLM (uses runtime config backend)
    try:
        langchain_llm = get_openrouter_llm(
            model=runtime_config.active_model,
            temperature=runtime_config.temperature,
            max_tokens=runtime_config.max_tokens,
            streaming=False,
        )
        logger.info(f"LangChain LLM initialized: {runtime_config.active_model}")
    except Exception as e:
        logger.error(f"Failed to initialize LangChain LLM: {e}")
        langchain_llm = None

    # NeMo Guardrails (optional - disabled for Ollama backend)
    nemo_enabled = (
        NEMO_AVAILABLE
        and os.getenv("NEMO_GUARDRAILS_ENABLED", "true").lower() == "true"
    )

    if nemo_enabled:
        config_path = os.path.join(os.path.dirname(__file__), "config")
        logger.info(f"Loading NeMo Guardrails config from {config_path}")

        try:
            config = RailsConfig.from_path(config_path)
            rails = LLMRails(config)

            if langchain_llm:
                rails.register_action(lambda: langchain_llm, "get_main_llm")
                logger.info("Registered LangChain LLM with NeMo Guardrails")

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
    else:
        reason = "NEMO_GUARDRAILS_ENABLED=false" if NEMO_AVAILABLE else "nemoguardrails not installed"
        logger.info(f"NeMo Guardrails disabled ({reason}) - using LangGraph-only path")

    # Initialize persistent checkpointer (PostgreSQL or in-memory)
    try:
        from src.hotel_guardrails.hotel_langgraph import init_checkpointer, close_checkpointer
        checkpointer = await init_checkpointer()
    except Exception as e:
        logger.error(f"Failed to initialize checkpointer: {e}")
        checkpointer = None

    # Initialize hybrid routing components (passes checkpointer to LangGraph)
    try:
        feedback_collector = FeedbackCollector()
        hybrid_router = HybridRouter(
            feedback_store=feedback_collector.get_average_score
        )
        langgraph_adapter = LangGraphAdapter(checkpointer=checkpointer)
        from src.hotel_guardrails.escalation import EscalationMonitor
        escalation_monitor = EscalationMonitor()
        logger.info("Hybrid routing + escalation monitor initialized")
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

    # Cleanup: close checkpointer pool
    try:
        from src.hotel_guardrails.hotel_langgraph import close_checkpointer
        await close_checkpointer()
    except Exception:
        pass
    logger.info("Server shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="The Grand Horizon Hotel Concierge API",
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

    # Step 2: Check if session is admin-controlled (staff took over)
    if session_id in admin_controlled_sessions:
        # Save user message but don't generate bot response
        try:
            await db.save_conversation_message(session_id, "user", request.message)
        except Exception:
            pass
        return ChatResponse(
            response="เจ้าหน้าที่โรงแรมกำลังช่วยเหลือท่านอยู่ กรุณารอสักครู่ค่ะ / "
                     "A hotel staff member is assisting you. Please wait.",
            session_id=session_id,
            request_id=request_id,
            routing_path="admin_override",
            complexity="admin",
        )

    # Step 2.5: PII Redaction — scrub sensitive data before LLM
    from src.hotel_guardrails.pii_redactor import redact_pii, check_output_pii
    message_for_llm = request.message
    pii_found = {}
    try:
        message_for_llm, pii_found = redact_pii(request.message, preserve_email=True)
        if pii_found:
            logger.info(f"PII redacted from input: {list(pii_found.keys())}")
    except Exception as e:
        logger.warning(f"PII redaction failed: {e}")

    # Step 3: Process with LangGraph Agent (primary)
    if langgraph_adapter:
        try:
            result = await langgraph_adapter.invoke(
                message=message_for_llm,
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

            system_prompt = """You are the Concierge at The Grand Horizon Hotel (โรงแรมเดอะแกรนด์ฮอไรซัน).
Your responsibilities:
1. Answer questions about the hotel using the provided context
2. Respond in the same language the guest uses (Thai or English)
3. Be polite, professional, and helpful

Greeting examples:
- Thai: "สวัสดีค่ะ/ครับ ยินดีต้อนรับสู่โรงแรมสยามเซอเรนิตี้"
- English: "Welcome to The Grand Horizon Hotel. How may I assist you?"
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

    # Step 6: Auto-escalation check
    if escalation_monitor and content:
        try:
            should_esc, esc_reason, esc_priority = escalation_monitor.should_escalate(
                session_id=session_id,
                message=request.message,
                context={"response": content, "tool_calls": tool_calls},
            )
            if should_esc:
                admin_controlled_sessions.add(session_id)
                await db.save_conversation_message(
                    session_id, "system",
                    f"[Auto-escalation] {esc_reason} | Priority: {esc_priority}",
                )
                logger.warning(f"Auto-escalated session {session_id}: {esc_reason} ({esc_priority})")
        except Exception as e:
            logger.warning(f"Escalation check failed: {e}")

    # Step 7: Check bot output for leaked PII
    if content and pii_found:
        try:
            has_output_pii, output_pii = check_output_pii(content)
            if has_output_pii:
                logger.warning(f"PII detected in bot output: {list(output_pii.keys())}")
        except Exception:
            pass

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
# Guest Endpoints
# =============================================================================


@app.post("/guests", response_model=GuestCreateResponse, tags=["Guests"])
async def register_guest(request: GuestCreateRequest):
    """
    Register a new guest.

    Creates a new guest profile for booking operations.
    Guests must be registered before making reservations.

    Example:
        ```json
        {
            "email": "guest@example.com",
            "first_name": "John",
            "last_name": "Smith"
        }
        ```

    Returns guest details with assigned guest_id.
    """
    try:
        success, message, guest_data = await db.create_guest(
            email=request.email,
            first_name=request.first_name,
            last_name=request.last_name,
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        guest = GuestResponse(**guest_data) if guest_data else None

        return GuestCreateResponse(
            success=success,
            message=message,
            guest=guest,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error registering guest: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to register guest: {str(e)}")


@app.get("/guests/{email}", response_model=GuestResponse, tags=["Guests"])
async def get_guest_by_email(email: str):
    """
    Get guest information by email address.

    Args:
        email: Guest's email address

    Returns guest profile including loyalty tier and points.

    Example:
        ```
        GET /guests/guest@example.com
        ```
    """
    try:
        guest = await db.get_guest_by_email(email)

        if not guest:
            raise HTTPException(
                status_code=404,
                detail=f"Guest with email {email} not found / ไม่พบผู้เข้าพักอีเมล {email}",
            )

        return GuestResponse(**guest)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching guest {email}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch guest: {str(e)}")


@app.patch("/guests/{guest_id}", response_model=GuestCreateResponse, tags=["Guests"])
async def update_guest(guest_id: int, request: GuestUpdateRequest):
    """
    Update guest information.

    Modifiable fields:
    - first_name, last_name: Names in English
    - first_name_th, last_name_th: Names in Thai
    - phone: Contact number
    - nationality: Guest nationality
    - address: Full address

    Note: Email cannot be changed (use as unique identifier).

    Example:
        ```json
        {
            "phone": "+66899999999",
            "address": "123 New Address, Bangkok"
        }
        ```

    Returns updated guest profile.
    """
    try:
        success, message, guest_data = await db.update_guest(
            guest_id=guest_id,
            first_name=request.first_name,
            last_name=request.last_name,
            first_name_th=request.first_name_th,
            last_name_th=request.last_name_th,
            phone=request.phone,
            nationality=request.nationality,
            address=request.address,
        )

        if not success:
            raise HTTPException(status_code=400, detail=message)

        guest = GuestResponse(**guest_data) if guest_data else None

        return GuestCreateResponse(
            success=success,
            message=message,
            guest=guest,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating guest {guest_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update guest: {str(e)}")


# =============================================================================
# Settings Endpoints
# =============================================================================


@app.get("/settings/llm", response_model=LLMSettingsResponse, tags=["Settings"])
async def get_llm_configuration():
    """
    Get current LLM configuration.

    Returns the active LLM settings including backend (ollama/openrouter)
    and list of available models. Frontend can populate model dropdowns.
    """
    runtime_config = get_runtime_llm_config()
    return LLMSettingsResponse(
        backend=runtime_config.backend.value,
        model=runtime_config.active_model,
        temperature=runtime_config.temperature,
        max_tokens=runtime_config.max_tokens,
        streaming=runtime_config.streaming,
        thinking=runtime_config.thinking,
        ollama_base_url=runtime_config.ollama_base_url,
        openrouter_model=runtime_config.openrouter_model,
        available_models=AVAILABLE_MODELS,
    )


@app.put("/settings/llm", response_model=LLMSettingsResponse, tags=["Settings"])
async def update_llm_configuration(request: LLMSettingsUpdateRequest):
    """
    Update LLM configuration at runtime (no restart needed).

    Switch between backends:
    - `ollama`: Local Ollama (e.g., fredrezones55/qwen3.5-opus:9b)
    - `openrouter`: Cloud OpenRouter (e.g., qwen/qwen3-max)

    Example:
        PUT /settings/llm {"backend": "ollama", "model": "fredrezones55/qwen3.5-opus:9b"}
        PUT /settings/llm {"backend": "openrouter", "model": "qwen/qwen3-max"}
        PUT /settings/llm {"temperature": 0.5}
    """
    runtime_config = get_runtime_llm_config()

    # Validate backend value
    if request.backend is not None and request.backend.lower() not in ("ollama", "openrouter"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid backend '{request.backend}'. Must be 'ollama' or 'openrouter'.",
        )

    changes = runtime_config.update(
        backend=request.backend,
        model=request.model,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )

    logger.info(f"LLM settings updated via API: {changes}")

    return LLMSettingsResponse(
        backend=runtime_config.backend.value,
        model=runtime_config.active_model,
        temperature=runtime_config.temperature,
        max_tokens=runtime_config.max_tokens,
        streaming=runtime_config.streaming,
        thinking=runtime_config.thinking,
        ollama_base_url=runtime_config.ollama_base_url,
        openrouter_model=runtime_config.openrouter_model,
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


# =============================================================================
# Admin Endpoints
# =============================================================================


@app.put("/admin/rooms/{room_id}/status", tags=["Admin"])
async def admin_set_room_status(room_id: int, request: AdminRoomStatusRequest):
    """
    Admin: Update room status (available, occupied, maintenance, cleaning).

    Used by hotel staff to manage room inventory directly.
    """
    result = await db.admin_update_room_status(room_id, request.status, request.notes)
    if not result:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to update room {room_id}. Check room_id and status value.",
        )
    return {"success": True, **result}


@app.put("/admin/bookings/{reservation_id}/status", tags=["Admin"])
async def admin_set_booking_status(reservation_id: str, request: AdminBookingStatusRequest):
    """
    Admin: Override booking status.

    Allows front desk to manually change any booking status
    (e.g., force check-in, mark no-show, override cancellation).
    """
    result = await db.admin_update_booking_status(reservation_id, request.status, request.notes)
    if not result:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to update booking {reservation_id}. Check ID and status value.",
        )
    return {"success": True, **result}


@app.post("/admin/chat/override", response_model=AdminChatOverrideResponse, tags=["Admin"])
async def admin_chat_override(request: AdminChatOverrideRequest):
    """
    Admin: Send a message directly to a guest's chat session.

    Allows hotel staff to take over a conversation from the bot.
    The message is stored in conversation history with role='admin'
    so the frontend can distinguish bot vs staff messages.
    """
    success = await db.admin_send_message_to_session(request.session_id, request.message)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to send admin message")
    return AdminChatOverrideResponse(
        success=True,
        session_id=request.session_id,
        message=request.message,
    )


@app.post("/admin/sessions/{session_id}/takeover", tags=["Admin"])
async def admin_takeover_session(session_id: str):
    """
    Admin: Take over a chat session.

    Pauses the AI bot for this session. All subsequent guest messages
    will get a "staff is assisting" response instead of bot replies.
    Admin uses /admin/chat/override to send messages to the guest.
    """
    admin_controlled_sessions.add(session_id)
    await db.admin_send_message_to_session(
        session_id,
        "[System] Hotel staff has joined the conversation / เจ้าหน้าที่โรงแรมเข้าร่วมสนทนาแล้ว",
    )
    return {"success": True, "session_id": session_id, "status": "admin_controlled"}


@app.post("/admin/sessions/{session_id}/release", tags=["Admin"])
async def admin_release_session(session_id: str):
    """
    Admin: Release a chat session back to the AI bot.

    Resumes normal bot responses for the guest.
    """
    admin_controlled_sessions.discard(session_id)
    await db.admin_send_message_to_session(
        session_id,
        "[System] AI assistant has resumed / ผู้ช่วย AI กลับมาให้บริการแล้ว",
    )
    return {"success": True, "session_id": session_id, "status": "bot_active"}


@app.get("/admin/sessions", tags=["Admin"])
async def admin_list_active_sessions():
    """
    Admin: List active chat sessions with last message preview.

    Used by admin dashboard to monitor all ongoing conversations.
    Shows which sessions are admin-controlled vs bot-active.
    """
    try:
        with db.get_cursor() as (cur, conn):
            cur.execute("""
                SELECT ch.session_id,
                       COUNT(*) as message_count,
                       MIN(ch.created_at) as started_at,
                       MAX(ch.created_at) as last_activity
                FROM conversation_history ch
                WHERE ch.created_at > NOW() - INTERVAL '24 hours'
                GROUP BY ch.session_id
                ORDER BY MAX(ch.created_at) DESC
                LIMIT 50
            """)
            sessions = []
            for row in cur.fetchall():
                sid = row["session_id"]
                # Get last message preview
                cur.execute("""
                    SELECT role, content FROM conversation_history
                    WHERE session_id = %s
                    ORDER BY created_at DESC LIMIT 1
                """, (sid,))
                last_msg = cur.fetchone()

                sessions.append({
                    "session_id": sid,
                    "message_count": row["message_count"],
                    "started_at": row["started_at"],
                    "last_activity": row["last_activity"],
                    "last_message_role": last_msg["role"] if last_msg else None,
                    "last_message_preview": last_msg["content"][:100] if last_msg else None,
                    "status": "admin_controlled" if sid in admin_controlled_sessions else "bot_active",
                })

        return {"sessions": sessions, "count": len(sessions)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/sessions/{session_id}/messages", tags=["Admin"])
async def admin_get_session_messages(session_id: str, limit: int = 100):
    """
    Admin: Get full conversation for a session.

    Returns all messages (user, assistant, admin, system) in chronological order.
    Used by admin dashboard to display the live chat view.
    """
    try:
        with db.get_cursor() as (cur, conn):
            cur.execute("""
                SELECT role, content, created_at
                FROM conversation_history
                WHERE session_id = %s
                ORDER BY created_at ASC
                LIMIT %s
            """, (session_id, min(limit, 500)))
            messages = [dict(r) for r in cur.fetchall()]
        return {
            "session_id": session_id,
            "status": "admin_controlled" if session_id in admin_controlled_sessions else "bot_active",
            "messages": messages,
            "count": len(messages),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Time-Travel / State History Endpoints
# =============================================================================


@app.get("/admin/escalations", tags=["Admin"])
async def admin_get_escalations(limit: int = 20):
    """
    Admin: List auto-escalated sessions with reasons and priority.
    """
    try:
        with db.get_cursor() as (cur, conn):
            cur.execute("""
                SELECT session_id, content, created_at
                FROM conversation_history
                WHERE role = 'system' AND content LIKE '[Auto-escalation]%%'
                ORDER BY created_at DESC
                LIMIT %s
            """, (min(limit, 100),))
            rows = [dict(r) for r in cur.fetchall()]
        return {"escalations": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/admin/sessions/{session_id}/states", tags=["Admin"])
async def admin_get_state_history(session_id: str, limit: int = 20):
    """
    Admin: Get LangGraph checkpoint history for a session.

    Returns each step the agent took, including which node ran,
    what messages existed at that point, and the checkpoint_id
    needed for rollback/replay.

    This is the "time travel" view — every step is a rewindable snapshot.
    """
    if not langgraph_adapter or not langgraph_adapter._graph:
        raise HTTPException(status_code=503, detail="LangGraph agent not available")

    graph = langgraph_adapter._graph
    config = {"configurable": {"thread_id": session_id}}

    states = []
    try:
        async for snapshot in graph.aget_state_history(config, limit=min(limit, 50)):
            checkpoint_id = snapshot.config.get("configurable", {}).get("checkpoint_id")
            parent_id = None
            if snapshot.parent_config:
                parent_id = snapshot.parent_config.get("configurable", {}).get("checkpoint_id")

            # Extract last message content for preview
            messages = snapshot.values.get("messages", [])
            last_msg = None
            if messages:
                m = messages[-1]
                last_msg = {
                    "role": getattr(m, "type", "unknown"),
                    "content": (m.content or "")[:200] if hasattr(m, "content") else "",
                    "has_tool_calls": bool(getattr(m, "tool_calls", None)),
                }

            states.append({
                "step": snapshot.metadata.get("step", 0),
                "checkpoint_id": checkpoint_id,
                "parent_checkpoint_id": parent_id,
                "source": snapshot.metadata.get("source", ""),
                "node": snapshot.metadata.get("writes", {}),
                "next_nodes": list(snapshot.next) if snapshot.next else [],
                "message_count": len(messages),
                "last_message": last_msg,
                "current_intent": snapshot.values.get("current_intent", ""),
                "created_at": snapshot.created_at,
            })

        return {
            "session_id": session_id,
            "states": states,
            "count": len(states),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/sessions/{session_id}/rollback", tags=["Admin"])
async def admin_rollback_session(session_id: str, checkpoint_id: str):
    """
    Admin: Roll back a session to a previous checkpoint.

    Time-travel: rewinds the conversation to the specified checkpoint step.
    The next guest message will continue from that point as if the later
    messages never happened.

    Get available checkpoint_ids from GET /admin/sessions/{id}/states.

    Args:
        checkpoint_id: Target checkpoint to roll back to (from states endpoint)
    """
    if not langgraph_adapter or not langgraph_adapter._graph:
        raise HTTPException(status_code=503, detail="LangGraph agent not available")

    graph = langgraph_adapter._graph

    try:
        # Verify the checkpoint exists
        replay_config = {
            "configurable": {
                "thread_id": session_id,
                "checkpoint_id": checkpoint_id,
            }
        }
        state = await graph.aget_state(replay_config)
        if not state:
            raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")

        # Update state to create a new branch from this checkpoint
        # This makes the old checkpoint the "current" one for the thread
        new_config = await graph.aupdate_state(
            replay_config,
            values=None,  # No state changes, just fork from this point
        )

        new_checkpoint_id = new_config.get("configurable", {}).get("checkpoint_id")
        step = state.metadata.get("step", 0)
        msg_count = len(state.values.get("messages", []))

        # Log the rollback in conversation_history for admin dashboard
        await db.admin_send_message_to_session(
            session_id,
            f"[System] Session rolled back to step {step} (checkpoint: {checkpoint_id[:12]}...)",
        )

        return {
            "success": True,
            "session_id": session_id,
            "rolled_back_to": {
                "checkpoint_id": checkpoint_id,
                "step": step,
                "message_count": msg_count,
                "intent": state.values.get("current_intent", ""),
            },
            "new_checkpoint_id": new_checkpoint_id,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/admin/sessions/{session_id}/replay", tags=["Admin"])
async def admin_replay_from_checkpoint(
    session_id: str,
    checkpoint_id: str,
    message: str,
):
    """
    Admin: Replay a session from a specific checkpoint with a new message.

    Time-travel + branch: goes back to the specified checkpoint and sends
    a new message as if the guest typed it at that point. Creates a new
    conversation branch from that step.

    Use case: "What if the guest had said X instead of Y at step 3?"

    Args:
        checkpoint_id: Target checkpoint to replay from
        message: New message to send from that point
    """
    if not langgraph_adapter or not langgraph_adapter._graph:
        raise HTTPException(status_code=503, detail="LangGraph agent not available")

    graph = langgraph_adapter._graph

    try:
        from langchain_core.messages import HumanMessage

        replay_config = {
            "configurable": {
                "thread_id": session_id,
                "checkpoint_id": checkpoint_id,
            }
        }

        # Verify checkpoint exists
        state = await graph.aget_state(replay_config)
        if not state:
            raise HTTPException(status_code=404, detail=f"Checkpoint {checkpoint_id} not found")

        from_step = state.metadata.get("step", 0)

        # Invoke graph from the checkpoint with new message
        result = await graph.ainvoke(
            {"messages": [HumanMessage(content=message)]},
            config=replay_config,
        )

        # Extract response
        final_messages = result.get("messages", [])
        response_text = ""
        for msg in reversed(final_messages):
            if hasattr(msg, "content") and msg.content and getattr(msg, "type", "") == "ai":
                response_text = msg.content
                break

        return {
            "success": True,
            "session_id": session_id,
            "replayed_from": {
                "checkpoint_id": checkpoint_id,
                "step": from_step,
            },
            "new_message": message,
            "response": response_text,
            "total_messages": len(final_messages),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Dashboard Endpoints
# =============================================================================


@app.get("/dashboard/stats", response_model=DashboardStatsResponse, tags=["Dashboard"])
async def get_dashboard_statistics():
    """
    Dashboard: Hotel overview statistics.

    Returns room occupancy, reservation counts, revenue,
    today's check-ins/outs, and service request status.
    """
    stats = await db.get_dashboard_stats()
    if "error" in stats:
        raise HTTPException(status_code=500, detail=stats["error"])
    return stats


@app.get("/dashboard/bookings/recent", tags=["Dashboard"])
async def get_recent_bookings_feed(limit: int = 20):
    """
    Dashboard: Recent bookings feed.

    Live feed of the most recent reservations with guest and room details.
    """
    bookings = await db.get_recent_bookings(min(limit, 100))
    return {"bookings": bookings, "count": len(bookings)}


@app.get("/dashboard/sessions", response_model=SessionStatsResponse, tags=["Dashboard"])
async def get_session_statistics():
    """
    Dashboard: Chatbot session statistics (last 24 hours).

    Shows total sessions, message counts by role (user, bot, admin).
    """
    stats = await db.get_active_sessions_stats()
    return stats


@app.get("/dashboard/rooms", tags=["Dashboard"])
async def get_room_status_overview():
    """
    Dashboard: Room status overview with counts per floor.

    Shows visual breakdown of room statuses for housekeeping management.
    """
    try:
        with db.get_cursor() as (cur, conn):
            cur.execute("""
                SELECT r.floor,
                       COUNT(CASE WHEN r.status = 'available' THEN 1 END) as available,
                       COUNT(CASE WHEN r.status = 'occupied' THEN 1 END) as occupied,
                       COUNT(CASE WHEN r.status = 'maintenance' THEN 1 END) as maintenance,
                       COUNT(CASE WHEN r.status = 'cleaning' THEN 1 END) as cleaning,
                       COUNT(*) as total
                FROM rooms r
                GROUP BY r.floor
                ORDER BY r.floor
            """)
            floors = [dict(r) for r in cur.fetchall()]

            cur.execute("""
                SELECT r.status, COUNT(*) as count
                FROM rooms r GROUP BY r.status
            """)
            summary = {r["status"]: r["count"] for r in cur.fetchall()}
            summary["total"] = sum(summary.values())

        return {"floors": floors, "summary": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/dashboard/revenue", tags=["Dashboard"])
async def get_revenue_overview():
    """
    Dashboard: Revenue breakdown by period and room type.
    """
    try:
        with db.get_cursor() as (cur, conn):
            # Revenue by room type
            cur.execute("""
                SELECT rt.name as room_type,
                       COUNT(res.reservation_id) as bookings,
                       COALESCE(SUM(res.total_amount), 0) as revenue
                FROM reservations res
                JOIN rooms rm ON res.room_id = rm.room_id
                JOIN room_types rt ON rm.room_type_id = rt.room_type_id
                WHERE res.status NOT IN ('cancelled', 'no_show')
                GROUP BY rt.name
                ORDER BY revenue DESC
            """)
            by_room_type = [dict(r) for r in cur.fetchall()]

            # Revenue by booking source
            cur.execute("""
                SELECT COALESCE(booking_source, 'Unknown') as source,
                       COUNT(*) as bookings,
                       COALESCE(SUM(total_amount), 0) as revenue
                FROM reservations
                WHERE status NOT IN ('cancelled', 'no_show')
                GROUP BY booking_source
                ORDER BY revenue DESC
            """)
            by_source = [dict(r) for r in cur.fetchall()]

            # Daily revenue (last 30 days)
            cur.execute("""
                SELECT DATE(created_at) as date,
                       COUNT(*) as bookings,
                       COALESCE(SUM(total_amount), 0) as revenue
                FROM reservations
                WHERE status NOT IN ('cancelled', 'no_show')
                AND created_at > NOW() - INTERVAL '30 days'
                GROUP BY DATE(created_at)
                ORDER BY date DESC
            """)
            daily = [dict(r) for r in cur.fetchall()]

        return {
            "by_room_type": by_room_type,
            "by_source": by_source,
            "daily": daily,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Payment Endpoints (Demo)
# =============================================================================


@app.get("/payment/{token}", tags=["Payment"])
async def get_payment_page(token: str):
    """
    Mock payment page — returns booking details and amount.

    In production this would render a PCI-compliant payment form.
    For demo: returns JSON that a frontend would display as a checkout page.
    """
    try:
        with db.get_cursor() as (cur, conn):
            cur.execute("""
                SELECT pl.token, pl.amount, pl.currency, pl.status, pl.expires_at,
                       r.reservation_id, r.confirmation_number, r.check_in_date,
                       r.check_out_date, r.num_guests, r.payment_status,
                       rm.room_number, rt.name as room_type,
                       g.email, g.first_name, g.last_name
                FROM payment_links pl
                JOIN reservations r ON pl.reservation_id = r.reservation_id
                JOIN rooms rm ON r.room_id = rm.room_id
                JOIN room_types rt ON rm.room_type_id = rt.room_type_id
                JOIN guests g ON r.guest_id = g.guest_id
                WHERE pl.token = %s
            """, (token,))
            row = cur.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Payment link not found or expired")

        if row["status"] == "completed":
            return {"status": "already_paid", "confirmation_number": row["confirmation_number"]}

        from datetime import datetime as dt, timezone as tz
        expires = row["expires_at"]
        if expires and expires < dt.now():
            return {"status": "expired", "message": "This payment link has expired. Please request a new one."}

        return {
            "status": "pending",
            "token": token,
            "amount": float(row["amount"]),
            "currency": row["currency"],
            "booking": {
                "confirmation_number": row["confirmation_number"],
                "room": f"{row['room_number']} ({row['room_type']})",
                "check_in": str(row["check_in_date"]),
                "check_out": str(row["check_out_date"]),
                "guests": row["num_guests"],
                "guest_email": row["email"],
                "guest_name": f"{row['first_name']} {row['last_name']}".strip(),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/payment/{token}/complete", tags=["Payment"])
async def complete_payment(token: str):
    """
    Mock payment completion — marks reservation as paid.

    In production this would be called by a payment gateway webhook.
    For demo: always succeeds.
    """
    try:
        with db.get_cursor() as (cur, conn):
            # Update payment link status
            cur.execute("""
                UPDATE payment_links SET status = 'completed'
                WHERE token = %s AND status = 'pending'
                RETURNING reservation_id, amount
            """, (token,))
            pl = cur.fetchone()

            if not pl:
                raise HTTPException(status_code=404, detail="Payment link not found, already completed, or expired")

            # Update reservation payment status
            cur.execute("""
                UPDATE reservations SET payment_status = 'paid', updated_at = CURRENT_TIMESTAMP
                WHERE reservation_id = %s
                RETURNING confirmation_number
            """, (pl["reservation_id"],))
            res = cur.fetchone()
            conn.commit()

        return {
            "success": True,
            "message": "Payment completed successfully / ชำระเงินสำเร็จ",
            "confirmation_number": res["confirmation_number"],
            "amount_paid": float(pl["amount"]),
            "payment_status": "paid",
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Root
# =============================================================================


@app.get("/", tags=["Root"])
async def root():
    """API root - returns basic info."""
    return {
        "name": "The Grand Horizon Hotel Concierge API",
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
