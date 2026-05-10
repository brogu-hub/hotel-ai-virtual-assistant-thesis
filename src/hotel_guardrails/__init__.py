# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Hotel AI Virtual Assistant — FastAPI + LangGraph

Provides:
- /chat endpoint for AI conversations with guardrails
- /tools/book endpoint for booking operations
- RAG integration with Qdrant
- Bilingual Thai/English support
- Safety rails for input/output

Usage:
    # Start the server
    python -m uvicorn src.hotel_guardrails.server:app --host 0.0.0.0 --port 8081 --reload

    # Or run directly
    python -m src.hotel_guardrails.server

API Endpoints:
    - GET  /health      - Health check
    - POST /chat        - General AI conversation
    - POST /chat/stream - Streaming chat (SSE)
    - POST /tools/book  - Booking operations

Configuration:
    Environment variables:
    - OPENROUTER_API_KEY: OpenRouter API key (required)
    - OPENROUTER_REFERER: HTTP-Referer header (default: https://grand-horizon-hotel.com)
    - OPENROUTER_TITLE: X-Title header (default: Grand Horizon Concierge)

Example:
    ```python
    from src.hotel_guardrails import app
    from src.hotel_guardrails.models import ChatRequest, ChatResponse

    # The app can be run with uvicorn
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8081)
    ```
"""

from .server import app
from .models import (
    ChatRequest,
    ChatResponse,
    BookingRequest,
    BookingResponse,
    HealthResponse,
    ErrorResponse,
)
from .openrouter_llm import get_openrouter_llm

__all__ = [
    # FastAPI app
    "app",
    # Request/Response models
    "ChatRequest",
    "ChatResponse",
    "BookingRequest",
    "BookingResponse",
    "HealthResponse",
    "ErrorResponse",
    # LLM utilities
    "get_openrouter_llm",
]

__version__ = "1.0.0"
