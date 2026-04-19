# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Hotel LangGraph Agent - Embedded State Machine

A LangGraph-based agent for hotel operations that runs directly in the
hotel_guardrails server (no external HTTP calls required).

Uses:
- OpenRouter (qwen/qwen3-max) with NVIDIA fallback for LLM
- OpenRouter (qwen/qwen3-embedding-8b) for embeddings
- Hotel tools from src/agent/hotel_tools.py

Architecture:
    START
      |
      v
    primary_assistant
      |
      +---> hotel_booking (booking operations)
      |         |
      |         v
      |     booking_tools --> hotel_booking
      |
      +---> hotel_service (info queries)
      |         |
      |         v
      |     service_tools --> hotel_service
      |
      +---> hotel_knowledge (RAG search)
      |
      +---> other_talk (greetings, off-topic)
      |
      v
     END
"""

import os
import re as _re
import yaml
import logging
from typing import Annotated, TypedDict, Dict, List, Literal, Optional, Any, Callable
from datetime import datetime

from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import tools_condition, ToolNode
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# =============================================================================
# State Definition
# =============================================================================

class HotelState(TypedDict):
    """State for the hotel assistant agent."""
    messages: Annotated[List[AnyMessage], add_messages]
    session_id: str
    user_id: str
    language: str  # 'th', 'en', or 'auto'
    current_intent: str  # booking, service, knowledge, other
    tool_calls_made: List[Dict[str, Any]]


# =============================================================================
# Routing Tools (for sub-agent dispatch)
# =============================================================================

class ToHotelBooking(BaseModel):
    """Route to hotel booking assistant for reservations, check-in/out, updates."""
    query: str = Field(description="The booking-related request")

class ToHotelService(BaseModel):
    """Route to service assistant for hotel services and amenities info."""
    query: str = Field(description="The service-related question")

class ToHotelKnowledge(BaseModel):
    """Route to RAG search for hotel information from knowledge base."""
    query: str = Field(description="The information query")

class HandleOtherTalk(BaseModel):
    """Handle greetings, small talk, and off-topic queries."""
    query: str = Field(description="The greeting or off-topic message")


# =============================================================================
# Load Prompts
# =============================================================================

def load_hotel_prompts() -> Dict[str, Any]:
    """Load prompts from hotel_prompt.yaml and inject current date/time."""
    # Try multiple paths for Railway compatibility
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "agent", "hotel_prompt.yaml"),
        "/app/src/agent/hotel_prompt.yaml",
        "src/agent/hotel_prompt.yaml",
    ]

    prompts = None
    for prompt_path in possible_paths:
        try:
            if os.path.exists(prompt_path):
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    prompts = yaml.safe_load(f)
                    logger.info(f"Loaded prompts from: {prompt_path}")
                    break
        except Exception as e:
            logger.warning(f"Failed to load prompts from {prompt_path}: {e}")

    if prompts is None:
        logger.warning("Using default prompts - no prompt file found")
        prompts = {
            "main_prompt": """You are a professional hotel assistant for The Grand Horizon Hotel.
You can communicate fluently in both Thai and English.
Always respond in the same language the guest uses.

For Thai speakers, use polite particles (ครับ/ค่ะ).
For English speakers, be professional and warm.
"""
        }

    # Inject current date and time into prompts (Bangkok timezone GMT+7)
    from datetime import timezone, timedelta
    bangkok_tz = timezone(timedelta(hours=7))
    now = datetime.now(bangkok_tz)
    current_date = now.strftime("%Y-%m-%d")  # e.g., 2025-02-04
    current_time = now.strftime("%H:%M")      # e.g., 14:30
    current_month = now.strftime("%B %Y")     # e.g., February 2025

    # Replace placeholders in main_prompt
    if "main_prompt" in prompts and prompts["main_prompt"]:
        prompts["main_prompt"] = prompts["main_prompt"].format(
            current_date=current_date,
            current_time=current_time,
            current_month=current_month,
        )
        logger.info(f"Injected current date into prompts: {current_date} {current_time}")

    return prompts


# =============================================================================
# LLM Initialization
# =============================================================================

def get_llm(temperature: float = 0.3, max_tokens: int = 2048, streaming: bool = False):
    """
    Get LLM using RuntimeLLMConfig.
    Supports Ollama (local) and OpenRouter (cloud), switchable at runtime.
    """
    from langchain_openai import ChatOpenAI
    from src.hotel_guardrails.config import get_runtime_llm_config, LLMBackend, resolve_thinking_model

    runtime_config = get_runtime_llm_config()

    # Use runtime config values, but allow per-call overrides
    temp = temperature
    tokens = max_tokens

    if runtime_config.backend == LLMBackend.OLLAMA:
        # Qwen3.5 on Ollama splits output into reasoning/content fields.
        # With think=True, streaming chunks have content="" (tokens go to
        # delta.reasoning which langchain doesn't expose). Disable thinking
        # so all tokens go to content for proper SSE streaming.
        logger.info(f"Using Ollama LLM: {runtime_config.ollama_model} (thinking={runtime_config.thinking})")
        return ChatOpenAI(
            model=runtime_config.ollama_model,
            openai_api_key="sk-ollama-not-needed",
            openai_api_base=runtime_config.ollama_base_url,
            temperature=temp,
            max_tokens=tokens,
            streaming=streaming,
        )
    else:
        # Rate limit OpenRouter calls to prevent 429
        runtime_config.rate_limiter.wait_and_acquire()
        model = runtime_config.openrouter_model
        logger.info(f"Using OpenRouter LLM: {model} (thinking={runtime_config.thinking})")

        api_key = runtime_config.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")

        # Build extra body params for OpenRouter reasoning
        model_kwargs = {}
        if runtime_config.thinking:
            # Enable reasoning via OpenRouter's reasoning parameter
            model_kwargs["extra_body"] = {
                "reasoning": {
                    "effort": "high",
                },
            }

        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=runtime_config.openrouter_base_url,
            temperature=temp,
            max_tokens=tokens,
            streaming=streaming,
            model_kwargs=model_kwargs,
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", "https://grand-horizon-hotel.com"),
                "X-Title": os.getenv("OPENROUTER_TITLE", "Grand Horizon Concierge"),
            },
        )


# =============================================================================
# Tool Node with Fallback
# =============================================================================

def create_tool_node_with_fallback(tools: List) -> ToolNode:
    """Create a tool node with error handling."""
    # Simple ToolNode without complex fallback (more compatible)
    return ToolNode(tools)


# =============================================================================
# Agent Nodes
# =============================================================================

class HotelAssistant:
    """
    Base assistant that routes to specialized sub-agents.
    Similar to the primary_assistant in the original agent.
    """

    def __init__(self, prompt: str, tools: List):
        self.prompt_template = ChatPromptTemplate.from_messages([
            ("system", prompt),
            MessagesPlaceholder("messages"),
        ])
        self.tools = tools

    async def __call__(self, state: HotelState, config: RunnableConfig) -> Dict:
        llm_settings = config.get('configurable', {}).get('llm_settings', {})
        temperature = llm_settings.get('temperature', 0.3)
        max_tokens = llm_settings.get('max_tokens', 1024)

        llm = get_llm(temperature=temperature, max_tokens=max_tokens)
        runnable = self.prompt_template | llm.bind_tools(self.tools)

        result = await runnable.ainvoke(state, config)
        return {"messages": [result]}


async def handle_booking(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle hotel booking operations."""
    from src.agent.hotel_tools import (
        check_room_availability,
        create_reservation,
        confirm_reservation,
        update_reservation,
        cancel_reservation,
        check_in_guest,
        check_out_guest,
        get_reservation_details,
        get_guest_reservations,
    )

    prompts = load_hotel_prompts()
    booking_prompt = prompts.get('booking_flow', '') + "\n\n" + prompts.get('main_prompt', '')

    booking_tools = [
        check_room_availability,
        create_reservation,
        confirm_reservation,
        update_reservation,
        cancel_reservation,
        check_in_guest,
        check_out_guest,
        get_reservation_details,
        get_guest_reservations,
    ]

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", booking_prompt),
        MessagesPlaceholder("messages"),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    llm = get_llm(
        temperature=llm_settings.get('temperature', 0.3),
        max_tokens=llm_settings.get('max_tokens', 2048)
    )

    runnable = prompt_template | llm.bind_tools(booking_tools)
    result = await runnable.ainvoke(state, config)

    return {"messages": [result], "current_intent": "booking"}


async def handle_service(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle hotel service queries."""
    from src.agent.hotel_tools import get_hotel_services, create_service_request

    prompts = load_hotel_prompts()
    service_prompt = prompts.get('service_prompt', '') + "\n\n" + prompts.get('main_prompt', '')

    service_tools = [get_hotel_services, create_service_request]

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", service_prompt),
        MessagesPlaceholder("messages"),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    llm = get_llm(
        temperature=llm_settings.get('temperature', 0.3),
        max_tokens=llm_settings.get('max_tokens', 1024)
    )

    runnable = prompt_template | llm.bind_tools(service_tools)
    result = await runnable.ainvoke(state, config)

    return {"messages": [result], "current_intent": "service"}


async def handle_knowledge(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle RAG-based knowledge queries."""
    from src.agent.hotel_tools import search_hotel_knowledge

    prompts = load_hotel_prompts()
    main_prompt = prompts.get('main_prompt', '')

    # Get last user message
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    # Search knowledge base
    try:
        knowledge_result = search_hotel_knowledge.invoke(last_user_message)
        # Trim to prevent overshadowing the user question (max ~2000 chars)
        if len(knowledge_result) > 2000:
            knowledge_result = knowledge_result[:2000] + "\n..."
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        knowledge_result = "No information found."

    # Generate response: user message first, then knowledge context
    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", main_prompt),
        ("human", last_user_message),
        ("system", f"""Use this hotel information to answer the guest's question above.
Be direct and specific. Include times, prices, locations.
Answer in the same language the guest used.

{knowledge_result}"""),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    llm = get_llm(
        temperature=llm_settings.get('temperature', 0.3),
        max_tokens=llm_settings.get('max_tokens', 1024)
    )

    runnable = rag_prompt | llm
    result = await runnable.ainvoke(state, config)

    return {"messages": [result], "current_intent": "knowledge"}


async def handle_other_talk(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle greetings and off-topic queries."""
    prompts = load_hotel_prompts()

    # Detect language and use appropriate greeting template
    greeting_templates = prompts.get('greeting_templates', {})
    main_prompt = prompts.get('main_prompt', '')

    other_prompt = f"""{main_prompt}

You are handling a greeting or general conversation.
Be friendly and welcoming. Offer to help with hotel services.

For Thai speakers, use polite particles (ครับ/ค่ะ).
For English speakers, be professional and warm.
"""

    prompt_template = ChatPromptTemplate.from_messages([
        ("system", other_prompt),
        MessagesPlaceholder("messages"),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    llm = get_llm(
        temperature=llm_settings.get('temperature', 0.3),
        max_tokens=llm_settings.get('max_tokens', 512)
    )

    runnable = prompt_template | llm
    result = await runnable.ainvoke(state, config)

    return {"messages": [result], "current_intent": "other"}


# =============================================================================
# Entry Nodes (for tool call routing)
# =============================================================================

def create_entry_node(assistant_name: str) -> Callable:
    """Create an entry node that acknowledges routing to a sub-agent."""
    def entry_node(state: HotelState) -> Dict:
        tool_call_id = state["messages"][-1].tool_calls[0]["id"]
        return {
            "messages": [
                ToolMessage(
                    content=f"Routing to {assistant_name}. Processing request...",
                    tool_call_id=tool_call_id,
                )
            ]
        }
    return entry_node


# =============================================================================
# Routing Functions
# =============================================================================

def route_primary_assistant(state: HotelState) -> Literal[
    "enter_booking",
    "enter_service",
    "enter_knowledge",
    "other_talk",
    "__end__"
]:
    """Route from primary assistant to specialized handlers."""
    route = tools_condition(state)
    if route == END:
        return END

    tool_calls = state["messages"][-1].tool_calls
    if tool_calls:
        tool_name = tool_calls[0]["name"]
        if tool_name == ToHotelBooking.__name__:
            return "enter_booking"
        elif tool_name == ToHotelService.__name__:
            return "enter_service"
        elif tool_name == ToHotelKnowledge.__name__:
            return "enter_knowledge"
        elif tool_name == HandleOtherTalk.__name__:
            return "enter_other"

    return END


def route_booking(state: HotelState) -> Literal["booking_tools", "__end__"]:
    """Route from booking assistant to tools or end."""
    route = tools_condition(state)
    if route == END:
        return END
    return "booking_tools"


def route_service(state: HotelState) -> Literal["service_tools", "__end__"]:
    """Route from service assistant to tools or end."""
    route = tools_condition(state)
    if route == END:
        return END
    return "service_tools"


# =============================================================================
# Build the Graph
# =============================================================================

def build_hotel_graph(checkpointer=None):
    """Build and return the hotel LangGraph agent."""

    # Load prompts
    prompts = load_hotel_prompts()
    main_prompt = prompts.get('main_prompt', 'You are a hotel assistant.')

    # Primary assistant prompt with explicit routing examples
    # (the 9B model needs concrete examples to get edge cases right)
    primary_prompt = f"""{main_prompt}

## Your Role
You are the primary router. Route every guest message to exactly ONE specialist:

1. **ToHotelBooking** — reservations, availability, check-in/out, modify/cancel bookings, payment
   Examples: "Is there a room available?", "I want to cancel my booking", "Check me in", "ยกเลิกการจอง"
2. **ToHotelService** — room service, extra amenities, housekeeping, maintenance, transportation, wake-up
   Examples: "I need extra towels", "Can I get room service?", "จองสปา", "ขอหมอนเพิ่ม"
3. **ToHotelKnowledge** — hotel info, facilities, dining, WiFi, policies, hours, directions, amenities
   Examples: "What time is breakfast?", "Where is the gym?", "รหัส WiFi", "pet policy",
   "ห้องประชุมมีไหม", "สระว่ายน้ำเปิดกี่โมง", "ร้านอาหารเปิดกี่โมง", "มี X ไหม",
   "สปามีบริการอะไร", "นโยบายยกเลิก", "Do you have meeting rooms?"
4. **HandleOtherTalk** — ONLY pure greetings/thanks/goodbye with NO question attached
   Examples: "Hello", "Thank you", "สวัสดี", "ขอบคุณ", "Goodbye", "Hi"

IMPORTANT routing rules:
- "cancel my booking" / "ยกเลิกการจอง" → ToHotelBooking (NOT HandleOtherTalk)
- "what services do you have?" → ToHotelKnowledge (general info, NOT ToHotelService)
- "I need a spa booking" → ToHotelService (specific service request)
- Any question about hotel facilities (rooms, spa, dining, pool, etc.) → ToHotelKnowledge
- Any Thai question ending with "มีไหม" / "กี่โมง" / "ที่ไหน" / "อย่างไร" → ToHotelKnowledge
- When in doubt between Knowledge and Service, prefer ToHotelKnowledge
- HandleOtherTalk ONLY for greetings without questions (Hello, Hi, Thanks, Bye)

Always route. Never answer directly without routing first.
"""

    # Primary assistant tools (routing only)
    primary_tools = [ToHotelBooking, ToHotelService, ToHotelKnowledge, HandleOtherTalk]

    # Import hotel tools
    from src.agent.hotel_tools import (
        check_room_availability,
        create_reservation,
        confirm_reservation,
        update_reservation,
        cancel_reservation,
        check_in_guest,
        check_out_guest,
        get_reservation_details,
        get_guest_reservations,
        get_hotel_services,
        create_service_request,
        calculate_dynamic_price,
        check_upsell_opportunity,
        generate_payment_link,
    )

    booking_tools = [
        check_room_availability,
        calculate_dynamic_price,
        create_reservation,
        confirm_reservation,
        update_reservation,
        cancel_reservation,
        check_in_guest,
        check_out_guest,
        get_reservation_details,
        get_guest_reservations,
        check_upsell_opportunity,
        generate_payment_link,
    ]

    service_tools = [get_hotel_services, create_service_request]

    # Build the graph
    builder = StateGraph(HotelState)

    # Primary assistant node
    builder.add_node("primary_assistant", HotelAssistant(primary_prompt, primary_tools))

    # Entry nodes for sub-agents
    builder.add_node("enter_booking", create_entry_node("Booking Assistant"))
    builder.add_node("enter_service", create_entry_node("Service Assistant"))
    builder.add_node("enter_knowledge", create_entry_node("Knowledge Assistant"))
    builder.add_node("enter_other", create_entry_node("General Assistant"))

    # Sub-agent nodes
    builder.add_node("hotel_booking", handle_booking)
    builder.add_node("hotel_service", handle_service)
    builder.add_node("hotel_knowledge", handle_knowledge)
    builder.add_node("other_talk", handle_other_talk)

    # Tool nodes
    builder.add_node("booking_tools", create_tool_node_with_fallback(booking_tools))
    builder.add_node("service_tools", create_tool_node_with_fallback(service_tools))

    # Edges from START
    builder.add_edge(START, "primary_assistant")

    # Conditional edges from primary assistant
    builder.add_conditional_edges(
        "primary_assistant",
        route_primary_assistant,
        {
            "enter_booking": "enter_booking",
            "enter_service": "enter_service",
            "enter_knowledge": "enter_knowledge",
            "enter_other": "enter_other",
            END: END,
        }
    )

    # Entry -> Sub-agent edges
    builder.add_edge("enter_booking", "hotel_booking")
    builder.add_edge("enter_service", "hotel_service")
    builder.add_edge("enter_knowledge", "hotel_knowledge")
    builder.add_edge("enter_other", "other_talk")

    # Sub-agent routing
    builder.add_conditional_edges("hotel_booking", route_booking)
    builder.add_conditional_edges("hotel_service", route_service)

    # Tool -> Sub-agent edges (loop back)
    builder.add_edge("booking_tools", "hotel_booking")
    builder.add_edge("service_tools", "hotel_service")

    # End edges
    builder.add_edge("hotel_knowledge", END)
    builder.add_edge("other_talk", END)

    # Compile with checkpointer (passed in, or fallback to MemorySaver)
    if checkpointer is None:
        checkpointer = MemorySaver()
        logger.info("Using MemorySaver (in-memory, volatile)")

    graph = builder.compile(checkpointer=checkpointer)
    return graph


# =============================================================================
# Checkpointer Initialization
# =============================================================================

_checkpointer = None
_checkpointer_pool = None


async def init_checkpointer():
    """
    Initialize the LangGraph checkpointer based on APP_CHECKPOINTER_NAME env var.

    - "postgres": Persistent to PostgreSQL (survives restarts)
    - "memory": In-memory only (volatile, for dev/testing)
    """
    global _checkpointer, _checkpointer_pool

    checkpointer_name = os.getenv("APP_CHECKPOINTER_NAME", "postgres").lower()

    if checkpointer_name == "postgres":
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            logger.warning("DATABASE_URL not set, falling back to MemorySaver")
            _checkpointer = MemorySaver()
            return _checkpointer

        try:
            from psycopg_pool import AsyncConnectionPool
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            connection_kwargs = {
                "autocommit": True,
                "prepare_threshold": 0,
            }

            _checkpointer_pool = AsyncConnectionPool(
                conninfo=db_url,
                min_size=2,
                max_size=10,
                kwargs=connection_kwargs,
            )
            _checkpointer = AsyncPostgresSaver(_checkpointer_pool)
            await _checkpointer.setup()

            logger.info("PostgreSQL checkpointer initialized (persistent memory)")
            return _checkpointer

        except Exception as e:
            logger.error(f"Failed to init PostgreSQL checkpointer: {e}, falling back to MemorySaver")
            _checkpointer = MemorySaver()
            return _checkpointer
    else:
        logger.info("Using MemorySaver checkpointer (in-memory, volatile)")
        _checkpointer = MemorySaver()
        return _checkpointer


async def close_checkpointer():
    """Close the checkpointer connection pool on shutdown."""
    global _checkpointer_pool
    if _checkpointer_pool is not None:
        await _checkpointer_pool.close()
        logger.info("Checkpointer pool closed")


# =============================================================================
# Global Graph Instance
# =============================================================================

_hotel_graph = None


def get_hotel_graph(checkpointer=None):
    """Get or create the hotel LangGraph agent."""
    global _hotel_graph
    if _hotel_graph is None:
        try:
            logger.info("Building hotel LangGraph agent...")
            _hotel_graph = build_hotel_graph(checkpointer=checkpointer or _checkpointer)
            logger.info("Hotel LangGraph agent ready")
        except Exception as e:
            logger.error(f"Failed to build hotel LangGraph agent: {e}")
            import traceback
            traceback.print_exc()
            raise
    return _hotel_graph


# =============================================================================
# Response Quality Checks
# =============================================================================

# Patterns indicating the LLM leaked tool-call syntax into the response body
# (9B model sometimes writes the call as text instead of executing it).
_TOOL_LEAK_PATTERNS = [
    _re.compile(r"```[\s\S]*?\b(?:search_hotel_knowledge|check_room_availability|"
                r"create_reservation|confirm_reservation|cancel_reservation|"
                r"get_reservation_details|get_guest_reservations|"
                r"calculate_dynamic_price|create_service_request|"
                r"get_hotel_services|check_in_guest|check_out_guest|"
                r"update_reservation|check_upsell_opportunity|"
                r"generate_payment_link)\s*\(", _re.IGNORECASE),
    _re.compile(r"\b(?:search_hotel_knowledge|check_room_availability|"
                r"create_reservation|cancel_reservation|get_reservation_details|"
                r"get_guest_reservations|calculate_dynamic_price|"
                r"create_service_request|get_hotel_services)\s*\("),
    _re.compile(r'\{\s*"name"\s*:\s*"(?:ToHotel|Handle)', _re.IGNORECASE),
    _re.compile(r"\bToHotel(?:Booking|Service|Knowledge)\s*\("),
]


def has_tool_leak(text: str) -> bool:
    """Return True if text contains tool-call syntax that should have been a real tool invocation."""
    if not text:
        return False
    for pat in _TOOL_LEAK_PATTERNS:
        if pat.search(text):
            return True
    return False


# =============================================================================
# Async Invocation
# =============================================================================

async def invoke_hotel_agent(
    message: str,
    session_id: str,
    user_id: str = "guest",
    language: str = "auto",
    conversation_history: Optional[List[Dict[str, str]]] = None,  # unused — MemorySaver handles history
    llm_settings: Optional[Dict] = None,
    max_retries: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Invoke the hotel LangGraph agent.

    Retries if the response is empty or contains leaked tool-call syntax.
    The retry count comes from the active model's preset:
      - Local 9B (Ollama): 2 retries (more forgiving for flaky local model)
      - Cloud (OpenRouter): 1 retry (avoid doubling API costs)

    Args:
        message: User message
        session_id: Session ID for conversation tracking
        user_id: User/guest identifier
        language: Response language preference
        conversation_history: Previous messages (unused — MemorySaver handles history)
        llm_settings: LLM configuration overrides
        max_retries: Override retry count (default: from active model preset)

    Returns:
        Dict with response, success status, and metadata.
        Includes `retries` count and `had_leak` flag for observability.
    """
    graph = get_hotel_graph()

    # Per-model retry budget (2 for local 9B, 1 for cloud models)
    if max_retries is None:
        try:
            from src.hotel_guardrails.config import get_runtime_llm_config
            max_retries = get_runtime_llm_config().max_retries
        except Exception:
            max_retries = 2

    response_text = ""
    tool_calls = []
    intent = ""
    retries_used = 0
    had_leak = False
    last_error = None

    for attempt in range(max_retries + 1):
        # Only send the NEW message — MemorySaver checkpointer has history
        initial_state = {
            "messages": [HumanMessage(content=message)],
            "session_id": session_id,
            "user_id": user_id,
            "language": language,
            "current_intent": "",
            "tool_calls_made": [],
        }
        config = RunnableConfig(
            configurable={
                "thread_id": session_id,
                "llm_settings": llm_settings or {},
            }
        )

        try:
            result = await graph.ainvoke(initial_state, config)

            # Extract the assistant's final response
            final_messages = result.get("messages", [])
            candidate_text = ""
            candidate_tools = []
            for msg in reversed(final_messages):
                if isinstance(msg, AIMessage):
                    if msg.content:
                        candidate_text = msg.content
                    if msg.tool_calls:
                        candidate_tools = [
                            {"name": tc["name"], "args": tc.get("args", {})}
                            for tc in msg.tool_calls
                        ]
                    break

            # Quality checks: non-empty + no tool-call leak
            leaked = has_tool_leak(candidate_text)
            if candidate_text and not leaked:
                response_text = candidate_text
                tool_calls = candidate_tools
                intent = result.get("current_intent", "")
                retries_used = attempt
                break  # Success

            # Failed quality check — log and retry if we have attempts left
            had_leak = had_leak or leaked
            if attempt < max_retries:
                reason = "tool-call leak" if leaked else "empty response"
                logger.warning(
                    f"Agent response failed quality check ({reason}) — "
                    f"retry {attempt + 1}/{max_retries} for session={session_id}"
                )
            else:
                # Out of retries — keep whatever we got
                response_text = candidate_text
                tool_calls = candidate_tools
                intent = result.get("current_intent", "")
                retries_used = attempt
                logger.warning(
                    f"Agent response still failed quality check after {max_retries} retries "
                    f"for session={session_id} (leaked={leaked})"
                )

        except Exception as e:
            last_error = e
            if attempt < max_retries:
                logger.warning(f"Agent error ({type(e).__name__}) — retry {attempt + 1}/{max_retries}")
            else:
                import traceback
                logger.error(f"Hotel LangGraph agent error: {e}")
                logger.error(f"Traceback: {traceback.format_exc()}")
                return {
                    "success": False,
                    "response": None,
                    "path": "langgraph",
                    "error": f"{type(e).__name__}: {str(e) or type(e).__name__}",
                    "retries": attempt,
                }

    return {
        "success": True,
        "response": response_text,
        "path": "langgraph",
        "intent": intent,
        "tool_calls": tool_calls,
        "session_id": session_id,
        "retries": retries_used,
        "had_leak": had_leak,
    }
