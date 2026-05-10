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
from typing import Annotated, TypedDict, Dict, List, Literal, Optional, Any, Callable, Tuple
from datetime import datetime

from langchain_core.messages import BaseMessage, ToolMessage, AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, StateGraph, START
from langgraph.graph.message import AnyMessage, add_messages
from langgraph.prebuilt import tools_condition, ToolNode
from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore
from pydantic import BaseModel, Field

# Postgres store is optional at import time — fall back to InMemoryStore if
# the installed langgraph-checkpoint-postgres doesn't ship the store module
# (older 2.0.0 pin). Downstream code treats the store as a BaseStore.
try:
    from langgraph.store.postgres.aio import AsyncPostgresStore  # type: ignore
except Exception:  # pragma: no cover — import-path compat
    AsyncPostgresStore = None  # type: ignore

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

        # Long-term memory preamble + extraction at the ROUTER level. The
        # local 9B model occasionally answers directly instead of dispatching
        # to a sub-agent — without this block, such turns see no memory.
        user_text = _last_user_text(state)
        if user_text:
            await _extract_prefs_from_text(state, user_text)

        memory = await load_guest_memory(state)
        preamble = _render_memory_preamble(memory)
        if preamble:
            prompt_template = ChatPromptTemplate.from_messages([
                ("system", preamble),
                *self.prompt_template.messages,
            ])
        else:
            prompt_template = self.prompt_template

        llm = get_llm(temperature=temperature, max_tokens=max_tokens)
        runnable = prompt_template | llm.bind_tools(self.tools)

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

    # Long-term memory: prepend a compact "Known about this guest" preamble
    # from the store so the booking agent can personalise for returning guests.
    memory = await load_guest_memory(state)
    preamble = _render_memory_preamble(memory)
    if preamble:
        booking_prompt = preamble + "\n\n" + booking_prompt

    # Guests frequently state room preferences in booking messages
    # ("Deluxe room, high floor please, no peanuts").
    user_text = _last_user_text(state)
    if user_text:
        await _extract_prefs_from_text(state, user_text)

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

    # Write-through: extract stable facts from any tool-call args (no LLM).
    await _extract_facts_from_tool_calls(state, result)

    return {"messages": [result], "current_intent": "booking"}


async def handle_service(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle hotel service queries."""
    from src.agent.hotel_tools import get_hotel_services, create_service_request

    prompts = load_hotel_prompts()
    service_prompt = prompts.get('service_prompt', '') + "\n\n" + prompts.get('main_prompt', '')

    memory = await load_guest_memory(state)
    preamble = _render_memory_preamble(memory)
    if preamble:
        service_prompt = preamble + "\n\n" + service_prompt

    # Preferences also surface inside service requests
    # ("extra pillows — I have a peanut allergy").
    user_text = _last_user_text(state)
    if user_text:
        await _extract_prefs_from_text(state, user_text)

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

    await _extract_facts_from_tool_calls(state, result)

    return {"messages": [result], "current_intent": "service"}


async def handle_knowledge(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle RAG-based knowledge queries."""
    from src.agent.hotel_tools import search_hotel_knowledge

    prompts = load_hotel_prompts()
    main_prompt = prompts.get('main_prompt', '')

    # Long-term memory: prepend preamble so the knowledge agent tailors
    # facility answers to known preferences (e.g. vegetarian menu).
    memory = await load_guest_memory(state)
    preamble = _render_memory_preamble(memory)
    if preamble:
        main_prompt = preamble + "\n\n" + main_prompt

    # Get last user message
    last_user_message = ""
    for msg in reversed(state["messages"]):
        if isinstance(msg, HumanMessage):
            last_user_message = msg.content
            break

    # Rule-based preference extraction: knowledge is the most likely spot for
    # free-text statements like "I prefer a high floor" or "no peanuts".
    if last_user_message:
        await _extract_prefs_from_text(state, last_user_message)

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

OUTPUT FORMAT — STRICT:
- Do NOT write code blocks (triple-backtick fences).
- Do NOT write pseudo tool-calls like `search_hotel_knowledge(...)` or
  `check_room_availability(...)`. The information below already IS the
  search result — just answer with it directly.
- Do NOT preface the answer with "I'll search …" or "Let me look up …"
  — go straight to the facts.

HOTEL INFORMATION (already retrieved for you):
{knowledge_result}"""),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    llm = get_llm(
        temperature=llm_settings.get('temperature', 0.3),
        max_tokens=llm_settings.get('max_tokens', 1024)
    )

    runnable = rag_prompt | llm
    result = await runnable.ainvoke(state, config)

    # Belt-and-braces: post-strip any code block that role-plays a tool call.
    # The prompt above tells the model not to emit these, but the local 9B
    # occasionally ignores the rule. Stripping here keeps the user-visible
    # answer clean AND prevents invoke_hotel_agent's has_tool_leak retry
    # from firing on a cosmetic issue.
    if isinstance(result, AIMessage) and isinstance(result.content, str):
        cleaned = strip_tool_call_codeblocks(result.content)
        if cleaned != result.content:
            logger.info("handle_knowledge: stripped leaked tool-call code block from response")
            result = AIMessage(content=cleaned, id=result.id) if result.id else AIMessage(content=cleaned)

    return {"messages": [result], "current_intent": "knowledge"}


async def handle_other_talk(state: HotelState, config: RunnableConfig) -> Dict:
    """Handle greetings and off-topic queries."""
    prompts = load_hotel_prompts()

    # Detect language and use appropriate greeting template
    greeting_templates = prompts.get('greeting_templates', {})
    main_prompt = prompts.get('main_prompt', '')

    memory = await load_guest_memory(state)
    preamble = _render_memory_preamble(memory)
    if preamble:
        main_prompt = preamble + "\n\n" + main_prompt

    # Preferences also often appear in casual chat ("I'm vegan btw").
    user_text = _last_user_text(state)
    if user_text:
        await _extract_prefs_from_text(state, user_text)

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
# Long-term Memory (PostgresStore)
# =============================================================================
#
# The checkpointer handles SHORT-TERM memory — per-session dialogue state
# keyed by thread_id=session_id. The store below handles LONG-TERM memory —
# per-guest facts that survive across sessions, keyed by user_id.
#
# Namespace convention:
#   ("guest", user_id)    — authenticated guests, indefinite retention
#   ("anon",  session_id) — anonymous sessions, purged after 30 days
#
# Write policy is rule-based (no LLM summariser): after a successful tool
# call we extract 1-2 facts from the tool's arguments and upsert them. This
# keeps per-turn latency neutral.

# Module-level store reference (populated by init_store). Sub-agent handlers
# read this at call time; the graph is also compiled with .compile(store=...)
# so LangGraph-native store access is available to future migrations.
_store = None
_store_pool = None


def _memory_namespace(state: HotelState) -> Tuple[str, str]:
    """Return the per-guest memory namespace, falling back to anon-per-session."""
    user_id = (state.get("user_id") or "").strip()
    if user_id and user_id != "guest":
        return ("guest", user_id)
    return ("anon", state.get("session_id", "unknown"))


async def load_guest_memory(state: HotelState) -> Dict[str, Any]:
    """Load all known facts for the current guest. Safe if store is unavailable."""
    if _store is None:
        return {}
    try:
        ns = _memory_namespace(state)
        items = await _store.asearch(ns)
        return {item.key: item.value for item in items}
    except Exception as e:
        logger.debug(f"load_guest_memory: store read failed ({type(e).__name__}: {e})")
        return {}


async def upsert_guest_memory(state: HotelState, key: str, value: Any) -> None:
    """Upsert one fact for the current guest. Silent no-op if store unavailable."""
    if _store is None or value in (None, "", [], {}):
        return
    try:
        ns = _memory_namespace(state)
        await _store.aput(ns, key, value)
    except Exception as e:
        logger.debug(f"upsert_guest_memory: store write failed for key={key!r} ({type(e).__name__}: {e})")


def _render_memory_preamble(memory: Dict[str, Any]) -> str:
    """Render a compact 'Known about this guest' preamble for sub-agent prompts."""
    if not memory:
        return ""

    bits: List[str] = []
    profile = memory.get("profile") or {}
    if isinstance(profile, dict):
        if profile.get("name"):
            bits.append(f"name={profile['name']}")
        if profile.get("language"):
            bits.append(f"lang={profile['language']}")
        if profile.get("loyalty_tier"):
            bits.append(f"loyalty={profile['loyalty_tier']}")
        if profile.get("email"):
            bits.append(f"email={profile['email']}")

    prefs = memory.get("preferences") or {}
    if isinstance(prefs, dict) and prefs:
        pref_bits = [f"{k}={v}" for k, v in prefs.items() if v]
        if pref_bits:
            bits.append("prefers " + ", ".join(pref_bits))
    elif isinstance(prefs, list) and prefs:
        bits.append("prefers " + ", ".join(str(p) for p in prefs))

    bookings = memory.get("recent_bookings_summary") or []
    if isinstance(bookings, list) and bookings:
        bits.append("recent bookings: " + ", ".join(str(b) for b in bookings[-3:]))

    services = memory.get("service_history_summary") or []
    if isinstance(services, list) and services:
        bits.append("recurring requests: " + ", ".join(str(s) for s in services[-3:]))

    if not bits:
        return ""
    return (
        "Known about this guest: " + "; ".join(bits) + ".\n"
        "These facts are stored by this hotel's system specifically for "
        "this guest and are SAFE to share with them. When the guest asks "
        "about their own preferences, profile, bookings, or past requests, "
        "answer directly using the facts above — do NOT claim you cannot "
        "access them. When the guest is NOT asking about their profile, "
        "use the facts to personalise your reply (e.g. suggest vegetarian "
        "options) without reciting the list unprompted. Never invent facts "
        "not listed here."
    )


# Preference keywords scanned in free-text user messages (both languages).
_PREF_KEYWORDS_EN = {
    "high floor": ("preferences", "floor", "high"),
    "low floor": ("preferences", "floor", "low"),
    "quiet room": ("preferences", "quiet", True),
    "no peanuts": ("preferences", "allergy", "peanuts"),
    "peanut allergy": ("preferences", "allergy", "peanuts"),
    "vegetarian": ("preferences", "diet", "vegetarian"),
    "vegan": ("preferences", "diet", "vegan"),
    "halal": ("preferences", "diet", "halal"),
    "king bed": ("preferences", "bed", "king"),
    "twin bed": ("preferences", "bed", "twin"),
    "extra pillows": ("preferences", "pillows", "extra"),
}
_PREF_KEYWORDS_TH = {
    "ชั้นสูง": ("preferences", "floor", "high"),
    "ชั้นต่ำ": ("preferences", "floor", "low"),
    "ห้องเงียบ": ("preferences", "quiet", True),
    "แพ้ถั่ว": ("preferences", "allergy", "peanuts"),
    "มังสวิรัติ": ("preferences", "diet", "vegetarian"),
    "ฮาลาล": ("preferences", "diet", "halal"),
    "เตียงคิง": ("preferences", "bed", "king"),
    "หมอนเพิ่ม": ("preferences", "pillows", "extra"),
}


async def _extract_prefs_from_text(state: HotelState, text: str) -> None:
    """Rule-based preference extraction from a user message. Fires 0 LLM calls."""
    if not text or _store is None:
        return
    lower = text.lower()
    prefs_delta: Dict[str, Any] = {}
    for kw, (_, pkey, pval) in _PREF_KEYWORDS_EN.items():
        if kw in lower:
            prefs_delta[pkey] = pval
    for kw, (_, pkey, pval) in _PREF_KEYWORDS_TH.items():
        if kw in text:
            prefs_delta[pkey] = pval
    if not prefs_delta:
        return

    # Merge into the existing preferences dict rather than clobber.
    current = await load_guest_memory(state)
    existing = current.get("preferences") or {}
    if not isinstance(existing, dict):
        existing = {}
    existing.update(prefs_delta)
    await upsert_guest_memory(state, "preferences", existing)


async def _extract_facts_from_tool_calls(state: HotelState, result: AIMessage) -> None:
    """
    Rule-based write-back after a sub-agent turn. Inspects tool_calls on the
    returned AIMessage and upserts the relevant memory keys. No LLM calls.
    """
    if _store is None or not isinstance(result, AIMessage):
        return
    tool_calls = getattr(result, "tool_calls", None) or []
    if not tool_calls:
        return

    current = await load_guest_memory(state)
    profile = current.get("profile") or {}
    if not isinstance(profile, dict):
        profile = {}
    bookings = current.get("recent_bookings_summary") or []
    if not isinstance(bookings, list):
        bookings = []
    services = current.get("service_history_summary") or []
    if not isinstance(services, list):
        services = []

    profile_dirty = False
    bookings_dirty = False
    services_dirty = False

    for call in tool_calls:
        name = call.get("name", "")
        args = call.get("args", {}) or {}

        if name == "create_reservation":
            if args.get("guest_email"):
                profile["email"] = args["guest_email"]
                profile_dirty = True
            if args.get("guest_name"):
                profile["name"] = args["guest_name"]
                profile_dirty = True
            summary = {
                "room_type": args.get("room_type"),
                "check_in": args.get("check_in_date"),
                "check_out": args.get("check_out_date"),
                "guests": args.get("num_guests"),
            }
            summary = {k: v for k, v in summary.items() if v is not None}
            if summary:
                bookings.append(summary)
                bookings_dirty = True

        elif name == "create_service_request":
            stype = args.get("service_type") or args.get("request_type")
            if stype:
                services.append(str(stype))
                services_dirty = True

        elif name in ("get_reservation_details", "get_guest_reservations"):
            if args.get("guest_email") and not profile.get("email"):
                profile["email"] = args["guest_email"]
                profile_dirty = True

    if profile_dirty:
        await upsert_guest_memory(state, "profile", profile)
    if bookings_dirty:
        await upsert_guest_memory(state, "recent_bookings_summary", bookings[-10:])
    if services_dirty:
        dedup: List[str] = []
        for s in services:
            if not dedup or dedup[-1] != s:
                dedup.append(s)
        await upsert_guest_memory(state, "service_history_summary", dedup[-10:])


def _last_user_text(state: HotelState) -> str:
    for msg in reversed(state.get("messages", []) or []):
        if isinstance(msg, HumanMessage):
            return msg.content or ""
    return ""


# =============================================================================
# Build the Graph
# =============================================================================

def build_hotel_graph(checkpointer=None, store=None):
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

    # Compile with store when available. .compile(store=...) is a no-op on
    # older langgraph versions that don't recognise the kwarg — fall back
    # to checkpointer-only compile in that case so the service still starts.
    if store is not None:
        try:
            graph = builder.compile(checkpointer=checkpointer, store=store)
        except TypeError:
            logger.warning("langgraph.compile() does not accept store= on this version — "
                           "falling back to checkpointer-only. Sub-agents still access the "
                           "store via the module-level _store reference.")
            graph = builder.compile(checkpointer=checkpointer)
    else:
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
# Store Initialization (long-term memory)
# =============================================================================

async def init_store():
    """
    Initialise the LangGraph store based on APP_STORE_NAME env var.

    Values:
      - "postgres": AsyncPostgresStore (persistent, cross-session, shared across workers)
      - "memory":   InMemoryStore (volatile, per-process; fine for tests)
      - "off":      store disabled — long-term memory becomes a silent no-op

    Uses a SEPARATE AsyncConnectionPool from the checkpointer so a stuck
    store query cannot starve checkpoint writes.
    """
    global _store, _store_pool

    store_name = os.getenv("APP_STORE_NAME", "postgres").lower()
    if store_name == "off":
        _store = None
        logger.info("Long-term memory store disabled (APP_STORE_NAME=off)")
        return None

    if store_name == "memory":
        _store = InMemoryStore()
        logger.info("Using InMemoryStore (volatile, per-process)")
        return _store

    # Default: postgres
    db_url = os.getenv("DATABASE_URL")
    if not db_url or AsyncPostgresStore is None:
        if not db_url:
            logger.warning("DATABASE_URL not set, falling back to InMemoryStore")
        else:
            logger.warning("langgraph.store.postgres not importable on this install — "
                           "falling back to InMemoryStore. Upgrade "
                           "langgraph-checkpoint-postgres to >=2.0.13 for persistence.")
        _store = InMemoryStore()
        return _store

    try:
        from psycopg_pool import AsyncConnectionPool

        connection_kwargs = {
            "autocommit": True,
            "prepare_threshold": 0,
        }
        _store_pool = AsyncConnectionPool(
            conninfo=db_url,
            min_size=1,
            max_size=5,
            kwargs=connection_kwargs,
        )
        _store = AsyncPostgresStore(_store_pool)
        await _store.setup()
        logger.info("PostgreSQL store initialized (long-term guest memory)")
        return _store

    except Exception as e:
        logger.error(f"Failed to init PostgreSQL store: {e}, falling back to InMemoryStore")
        _store = InMemoryStore()
        return _store


async def close_store():
    """Close the store connection pool on shutdown."""
    global _store_pool
    if _store_pool is not None:
        try:
            await _store_pool.close()
            logger.info("Store pool closed")
        except Exception as e:
            logger.debug(f"close_store: pool close failed ({type(e).__name__}: {e})")


async def prune_anon_memory(max_age_days: int = 30) -> int:
    """
    Delete anonymous-namespace entries older than max_age_days. Intended to
    run nightly from a FastAPI background task.

    Returns the number of rows deleted. Silent no-op when the active store is
    not PostgreSQL (InMemoryStore has no persistence anyway).
    """
    if _store is None or _store_pool is None:
        return 0
    try:
        max_age_days = int(max_age_days)
    except (TypeError, ValueError):
        return 0
    if max_age_days < 1:
        return 0
    try:
        async with _store_pool.connection() as conn:
            async with conn.cursor() as cur:
                # langgraph.store.postgres stores the namespace tuple joined
                # with '.' in the `prefix` column. INTERVAL is built by
                # multiplying a parameterised day count with INTERVAL '1 day'
                # — avoids string-formatting SQL.
                await cur.execute(
                    "DELETE FROM store "
                    "WHERE prefix LIKE 'anon.%%' "
                    "  AND updated_at < NOW() - (%s * INTERVAL '1 day')",
                    (max_age_days,),
                )
                deleted = cur.rowcount or 0
        if deleted:
            logger.info(f"prune_anon_memory: removed {deleted} anon store entries older than {max_age_days}d")
        return deleted
    except Exception as e:
        logger.warning(f"prune_anon_memory: failed ({type(e).__name__}: {e})")
        return 0


# =============================================================================
# Global Graph Instance
# =============================================================================

_hotel_graph = None


def get_hotel_graph(checkpointer=None, store=None):
    """Get or create the hotel LangGraph agent."""
    global _hotel_graph
    if _hotel_graph is None:
        try:
            logger.info("Building hotel LangGraph agent...")
            _hotel_graph = build_hotel_graph(
                checkpointer=checkpointer or _checkpointer,
                store=store or _store,
            )
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
    # Qwen/Hermes-style leak: <call_search_hotel_knowledge(...)>,
    # <tool_call>…</tool_call>, <function=name>…</function>. Trigger the
    # retry logic in invoke_hotel_agent for booking/service sub-agents
    # where these indicate a missed tool call (not just formatting).
    _re.compile(r"<call_(?:search_hotel_knowledge|check_room_availability|"
                r"create_reservation|confirm_reservation|cancel_reservation|"
                r"get_reservation_details|get_guest_reservations|"
                r"calculate_dynamic_price|create_service_request|"
                r"get_hotel_services|check_in_guest|check_out_guest|"
                r"update_reservation|check_upsell_opportunity|"
                r"generate_payment_link)\b", _re.IGNORECASE),
    _re.compile(r"<tool_call>[\s\S]{0,500}?</tool_call>", _re.IGNORECASE),
    _re.compile(r"<function=(?:search_hotel_knowledge|check_room_availability|"
                r"create_reservation|confirm_reservation|cancel_reservation|"
                r"get_reservation_details|get_guest_reservations|"
                r"calculate_dynamic_price|create_service_request|"
                r"get_hotel_services|check_in_guest|check_out_guest|"
                r"update_reservation|check_upsell_opportunity|"
                r"generate_payment_link)\b", _re.IGNORECASE),
]


def has_tool_leak(text: str) -> bool:
    """Return True if text contains tool-call syntax that should have been a real tool invocation."""
    if not text:
        return False
    for pat in _TOOL_LEAK_PATTERNS:
        if pat.search(text):
            return True
    return False


# Strips fenced code blocks whose body references a known hotel tool name.
# Used to clean up the RAG (knowledge) sub-agent's output where the local 9B
# model occasionally role-plays a tool call as markdown instead of answering.
# We only touch code blocks that mention our tool names, so legitimate code
# snippets (e.g. a user asking about an API example) are left alone.
_TOOL_NAMES_RE = _re.compile(
    r"search_hotel_knowledge|check_room_availability|create_reservation|"
    r"confirm_reservation|cancel_reservation|get_reservation_details|"
    r"get_guest_reservations|calculate_dynamic_price|create_service_request|"
    r"get_hotel_services|check_in_guest|check_out_guest|update_reservation|"
    r"check_upsell_opportunity|generate_payment_link",
    _re.IGNORECASE,
)
_FENCED_BLOCK_RE = _re.compile(r"```[\w-]*\n?[\s\S]*?```", _re.MULTILINE)
# Qwen/Hermes-style XML-ish tool calls the 9B sometimes leaks:
#   <call_search_hotel_knowledge(category="dining")>
#   <tool_call>search_hotel_knowledge(...)</tool_call>
#   <function=search_hotel_knowledge>{...}</function>
# Regex below captures paired tags (open..close) AND dangling opens on a
# single line. The tool-name guard inside the matcher keeps it narrow.
_XML_TOOLCALL_RE = _re.compile(
    r"(?:<call_[^>]{0,200}?>[\s\S]{0,500}?(?:</call_[^>]{0,200}?>|$))|"
    r"(?:<call_[^>]{0,200}?/?>)|"
    r"(?:<tool_call>[\s\S]{0,500}?</tool_call>)|"
    r"(?:<function=[^>]{0,200}?>[\s\S]{0,500}?</function>)",
    _re.IGNORECASE | _re.MULTILINE,
)
# Leading sentences like "I'll search ...", "Let me look up ..." — these
# typically precede a leaked code block. Drop them when the block is stripped
# so the final answer doesn't start with a dangling "I'll search for ...".
_LEAK_PREAMBLE_RE = _re.compile(
    r"^(?:I'll (?:search|look up|check|find|query).{0,80}|"
    r"Let me (?:search|look up|check|find|query).{0,80})(?:\r?\n)+",
    _re.IGNORECASE,
)


def strip_tool_call_codeblocks(text: str) -> str:
    """
    Remove tool-call syntax that leaked into LLM output.

    Covers THREE leak shapes observed from the local 9B backend:
      1. Markdown fenced code blocks   ```search_hotel_knowledge(...)```
      2. Qwen/Hermes-style XML tags    <call_search_hotel_knowledge(...)>
      3. <tool_call>…</tool_call> and  <function=name>…</function>

    Only strips blocks whose body mentions a known hotel tool name, so
    legitimate code snippets (e.g. the user asking about an API) survive.
    Also trims a leading 'I'll search …' hand-off sentence once its
    associated leak block has been removed.
    """
    if not text:
        return text

    changed = False

    def _maybe_drop(match: "_re.Match[str]") -> str:
        nonlocal changed
        block = match.group(0)
        if _TOOL_NAMES_RE.search(block):
            changed = True
            return ""
        return block

    # Pass 1: fenced code blocks.
    cleaned = _FENCED_BLOCK_RE.sub(_maybe_drop, text) if "```" in text else text

    # Pass 2: XML-style tool calls. Runs even if Pass 1 made no change —
    # the 9B sometimes emits these with no surrounding code fence.
    if "<call_" in cleaned or "<tool_call" in cleaned or "<function=" in cleaned:
        cleaned = _XML_TOOLCALL_RE.sub(_maybe_drop, cleaned)

    # Pass 3: dangling `<call_something` — response was cut off by max_tokens
    # before the closing `>`. The XML regex above requires either a close tag
    # or end-of-string INSIDE a matched block; standalone dangling opens slip
    # past it. Accept a partial tool-name prefix here (`\w{5,}`) because the
    # closing chars may have been truncated. `<call_` followed by 5+ word
    # characters is not natural English, so the false-positive risk is low.
    if _re.search(r"<call_\w{5,}", cleaned, _re.IGNORECASE):
        new_cleaned = _re.sub(
            r"<call_\w{5,}[\s\S]*$",
            "",
            cleaned,
            flags=_re.IGNORECASE | _re.MULTILINE,
        )
        if new_cleaned != cleaned:
            cleaned = new_cleaned
            changed = True

    if not changed:
        return text

    # Drop a leading hand-off sentence if one is now orphaned above blank space.
    cleaned = _LEAK_PREAMBLE_RE.sub("", cleaned, count=1)
    # Collapse 3+ blank lines left behind by the removal.
    cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# =============================================================================
# Language leak detection & stripping
# =============================================================================
# The local 9B model is Qwen-derived (Chinese-trained) and occasionally drops
# Chinese ideographs into Thai or English replies under cognitive load
# (e.g. "การตรวจสอบราคาและ可用性"). The hotel supports three first-class
# languages — Thai, English, Mandarin Chinese — so the policy is:
#
#   user latest message in EN  → reply in EN  (latin script)
#   user latest message in TH  → reply in TH  (Thai script)
#   user latest message in CN  → reply in CN  (Hanzi script)
#   any other language         → reply in EN  (default)
#
# A guest's own proper name from the user's input may be echoed back in its
# original script — that is not a leak. Anything else off-script is.

_CJK_RE = _re.compile(r"[㐀-䶿一-鿿豈-﫿぀-ヿ]")
_THAI_RE = _re.compile(r"[฀-๿]")
_LATIN_LETTER_RE = _re.compile(r"[A-Za-z]")
# Run of 2+ off-script chars (used for stripping)
_CJK_RUN_RE = _re.compile(r"[㐀-䶿一-鿿豈-﫿぀-ヿ]{2,}")
_THAI_RUN_RE = _re.compile(r"[฀-๿]{2,}")


def detect_input_language(text: str) -> str:
    """Classify a user message as 'en', 'th', or 'cn' by dominant script."""
    if not text:
        return "en"
    cn = len(_CJK_RE.findall(text))
    th = len(_THAI_RE.findall(text))
    en = len(_LATIN_LETTER_RE.findall(text))
    total = cn + th + en
    if total == 0:
        return "en"
    # >=20% threshold for non-EN to win — single-word borrowings shouldn't flip
    if cn >= th and cn >= en and cn / total >= 0.20:
        return "cn"
    if th >= cn and th >= en and th / total >= 0.20:
        return "th"
    return "en"


def has_language_leak(input_text: str, response_text: str) -> bool:
    """
    True if `response_text` contains script characters that don't match the
    expected reply language for `input_text`. CJK chars that the user provided
    in their own message (e.g. their name) are not counted as leaks — they may
    be echoed back.
    """
    if not response_text:
        return False
    expected = detect_input_language(input_text)
    user_cjk = {c for c in input_text if _CJK_RE.match(c)}

    if expected in ("en", "th"):
        # Any CJK char in the response that the user did NOT provide is a leak.
        for c in response_text:
            if _CJK_RE.match(c) and c not in user_cjk:
                return True
        return False

    # expected == "cn"
    cjk_total = len(_CJK_RE.findall(response_text))
    body_len = len(_LATIN_LETTER_RE.findall(response_text)) + len(_THAI_RE.findall(response_text)) + cjk_total
    # Thai script in a Chinese-expected reply is a clear leak
    if len(_THAI_RE.findall(response_text)) >= 5:
        return True
    # If the body is substantial but the model produced almost no Chinese, treat
    # as failure to comply with the language policy.
    if body_len >= 60 and cjk_total < 10:
        return True
    return False


def strip_language_leak(input_text: str, response_text: str) -> str:
    """
    Conservative fallback used after retries are exhausted: drop runs of 2+
    off-script characters that the user did not provide. Single off-script
    characters and user-provided proper names are left alone so the response
    stays grammatical where possible.
    """
    if not response_text:
        return response_text
    expected = detect_input_language(input_text)
    user_cjk_runs = set()
    for m in _CJK_RUN_RE.finditer(input_text):
        user_cjk_runs.add(m.group(0))

    cleaned = response_text
    if expected in ("en", "th"):
        def _drop_cjk(m: "_re.Match[str]") -> str:
            run = m.group(0)
            return run if run in user_cjk_runs else ""
        cleaned = _CJK_RUN_RE.sub(_drop_cjk, cleaned)
    elif expected == "cn":
        # In a Chinese-expected reply, Thai runs are the off-script leak. Latin
        # is permitted (brand names, English code-switches in formal Chinese).
        cleaned = _THAI_RUN_RE.sub("", cleaned)

    if cleaned != response_text:
        cleaned = _re.sub(r"[ \t]+", " ", cleaned)
        cleaned = _re.sub(r"\n{3,}", "\n\n", cleaned)
        cleaned = cleaned.strip()
    return cleaned


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
    had_lang_leak = False
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

            # Quality checks: non-empty + no tool-call leak + no language leak.
            # Language leak: Chinese ideographs in an EN/TH reply (or Thai chars
            # in a CN reply) that the user did NOT provide in their own message.
            leaked = has_tool_leak(candidate_text)
            lang_leaked = has_language_leak(message, candidate_text)
            if candidate_text and not leaked and not lang_leaked:
                response_text = candidate_text
                tool_calls = candidate_tools
                intent = result.get("current_intent", "")
                retries_used = attempt
                break  # Success

            # Failed quality check — log and retry if we have attempts left
            had_leak = had_leak or leaked
            had_lang_leak = had_lang_leak or lang_leaked
            if attempt < max_retries:
                if leaked:
                    reason = "tool-call leak"
                elif lang_leaked:
                    reason = f"language leak (expected {detect_input_language(message)})"
                else:
                    reason = "empty response"
                logger.warning(
                    f"Agent response failed quality check ({reason}) — "
                    f"retry {attempt + 1}/{max_retries} for session={session_id}"
                )
            else:
                # Out of retries — strip what we can and keep the result
                if lang_leaked and candidate_text:
                    candidate_text = strip_language_leak(message, candidate_text)
                response_text = candidate_text
                tool_calls = candidate_tools
                intent = result.get("current_intent", "")
                retries_used = attempt
                logger.warning(
                    f"Agent response still failed quality check after {max_retries} retries "
                    f"for session={session_id} (tool_leak={leaked}, lang_leak={lang_leaked})"
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
        "had_lang_leak": had_lang_leak,
        "expected_language": detect_input_language(message),
    }
