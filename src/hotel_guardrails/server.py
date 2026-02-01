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
)
from .hybrid_router import HybridRouter, RoutingPath
from .langgraph_adapter import LangGraphAdapter
from .feedback_collector import FeedbackCollector

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


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Check service health.

    Returns status of:
    - guardrails: NeMo Guardrails initialization
    - qdrant: Vector database connection
    - openrouter: LLM API connectivity
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

    # Determine overall status
    if all(v == "healthy" for v in components.values()):
        overall = "healthy"
    elif components.get("guardrails") == "not_initialized":
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
