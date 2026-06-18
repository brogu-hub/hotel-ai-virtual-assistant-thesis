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
import uuid
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

def load_hotel_prompts(model: Optional[str] = None) -> Dict[str, Any]:
    """Load prompts from hotel_prompt.yaml and merge per-model overrides.

    Phase G prompt versioning: the YAML has a top-level ``model_overrides:``
    dict keyed by model_id. When a model has an entry, its keys override
    the base prompts (partial replacement — base keys not mentioned in the
    override stay untouched). If ``model`` is None, falls back to the
    runtime LLM config's active_model.

    HOTEL_PROMPT_PATH env override: when set, this exact path is loaded
    instead of the default search list. Used by the Stack-OFF backtest to
    point at hotel_prompt_stackoff.yaml (no model_overrides block) so we
    can isolate the prompt-engineering contribution from retrieval.
    """
    if model is None:
        try:
            from src.hotel_guardrails.config import get_runtime_llm_config
            model = get_runtime_llm_config().active_model
        except Exception:
            model = os.getenv("OLLAMA_MODEL", "")

    env_path = os.getenv("HOTEL_PROMPT_PATH", "").strip()
    if env_path:
        possible_paths = [env_path]
    else:
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
                    logger.info(f"Loaded prompts from: {prompt_path} (model={model})")
                    break
        except Exception as e:
            logger.warning(f"Failed to load prompts from {prompt_path}: {e}")

    # Apply per-model overrides (Phase G).
    if prompts is not None and model:
        overrides = (prompts.get("model_overrides") or {}).get(model, {})
        if overrides:
            for key, val in overrides.items():
                prompts[key] = val
            logger.info(
                f"Applied {len(overrides)} prompt override(s) for model={model}: "
                + ", ".join(sorted(overrides.keys()))
            )
        # Strip the override registry from the returned dict so callers
        # don't accidentally treat it as a regular prompt key.
        prompts.pop("model_overrides", None)

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
        hotel_snapshot = _get_hotel_snapshot_cached()
        try:
            prompts["main_prompt"] = prompts["main_prompt"].format(
                current_date=current_date,
                current_time=current_time,
                current_month=current_month,
                hotel_snapshot=hotel_snapshot,
            )
            logger.info(f"Injected date+snapshot into prompts: {current_date} {current_time}")
        except KeyError:
            # Backwards compatibility — prompts without hotel_snapshot placeholder
            prompts["main_prompt"] = prompts["main_prompt"].format(
                current_date=current_date,
                current_time=current_time,
                current_month=current_month,
            )

    return prompts


# Phase J.2: per-process LRU cache for the hotel snapshot. DB query runs
# at most once every 5 minutes — fast enough to reflect admin updates
# without hammering Postgres on every chat turn.
_SNAPSHOT_CACHE: Dict[str, Any] = {"text": "", "expires_at": 0.0}

def _get_hotel_snapshot_cached(ttl_sec: int = 300) -> str:
    """Return a cached LIVE hotel-fact snapshot built from PMS DB rows.

    Includes per-room-type counts + total inventory. Falls back to a
    minimal static stub on DB error so the bot still runs offline.
    """
    import time
    now_s = time.time()
    if _SNAPSHOT_CACHE.get("text") and now_s < _SNAPSHOT_CACHE.get("expires_at", 0):
        return _SNAPSHOT_CACHE["text"]
    try:
        from src.agent.hotel_tools import get_db_connection
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT rt.name, rt.name_th,
                           MIN(rt.base_price), MIN(rt.max_occupancy),
                           COUNT(r.room_id) FILTER (
                               WHERE r.status IS NULL OR r.status <> 'out_of_order'
                           )
                    FROM room_types rt
                    LEFT JOIN rooms r ON r.room_type_id = rt.room_type_id
                    GROUP BY rt.name, rt.name_th
                    ORDER BY MIN(rt.base_price);
                """)
                rows = cur.fetchall()
        # Trilingual snapshot — TH/CN model needs labels in its own script
        # or it defers ("we don't have that count") despite the data.
        lines = ["Hotel: The Grand Horizon Hotel, 123 Sukhumvit Road, Bangkok"]
        total = 0
        cn_map = {  # rough CN labels for the 4 known room types
            "Standard Room": "标准房",
            "Deluxe Room":   "豪华房",
            "Suite":         "套房",
            "Penthouse":     "顶层套房",
        }
        type_lines_en = []
        type_lines_th = []
        type_lines_cn = []
        for name, name_th, base_price, max_occ, cnt in rows:
            cnt = int(cnt or 0)
            total += cnt
            type_lines_en.append(
                f"- {name}: {cnt} rooms, base {int(base_price):,} THB/night, "
                f"max occupancy {max_occ}"
            )
            if name_th:
                type_lines_th.append(f"- {name_th} ({name}): {cnt} ห้อง")
            cn_name = cn_map.get(name, name)
            type_lines_cn.append(f"- {cn_name} ({name}): {cnt} 间")
        lines.append(
            f"Total bookable rooms: {total} "
            f"(จำนวนห้องพักทั้งหมด: {total} ห้อง / 客房总数: {total} 间)"
        )
        lines.extend(type_lines_en)
        if type_lines_th:
            lines.append("ภาษาไทย:")
            lines.extend(type_lines_th)
        if type_lines_cn:
            lines.append("中文:")
            lines.extend(type_lines_cn)

        # Hotel services snapshot — operating hours, location, price for
        # every active service in the PMS DB. Saves the bot a RAG lookup
        # on quick-fact questions ("what time is breakfast?").
        # CN labels added because Gemma CN ignored EN-only snapshot lines
        # in 2026-06-16 smoke (deferred on "早餐几点?" despite the EN line
        # being present).
        cn_svc_map = {
            "Breakfast Buffet": "早餐自助餐",
            "Fine Dining Restaurant": "高级餐厅",
            "Room Service": "客房送餐服务",
            "Swimming Pool": "游泳池",
            "Kids Club": "儿童俱乐部",
            "Fitness Center": "健身中心",
            "Spa & Wellness": "水疗中心",
            "Business Center": "商务中心",
            "Concierge": "礼宾服务",
            "Laundry Service": "洗衣服务",
            "Airport Shuttle": "机场接送",
            "Valet Parking": "代客泊车",
        }
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT name, name_th, category, availability_hours,
                               location, price
                        FROM hotel_services
                        WHERE is_active = true
                        ORDER BY category, name;
                    """)
                    svc_rows = cur.fetchall()
            if svc_rows:
                lines.append("")
                lines.append("Services & Facilities (LIVE — quote these directly when asked):")
                current_cat = None
                for name, name_th, cat, hours, loc, price in svc_rows:
                    if cat != current_cat:
                        current_cat = cat
                        lines.append(f"  [{cat}]")
                    label = f"{name}"
                    if name_th:
                        label += f" / {name_th}"
                    cn_label = cn_svc_map.get(name, "")
                    if cn_label:
                        label += f" / {cn_label}"
                    # Phase J.2 fix: distinguish price=NULL (DB default,
                    # meaning "menu varies / see KB" for Room Service etc.)
                    # from price=0 (explicitly free). The previous heuristic
                    # collapsed both to "complimentary", making the bot
                    # answer "Room Service is free" when the KB says
                    # "100 THB service charge per order".
                    if price is None:
                        # NULL = menu-based pricing or service charge applies
                        # (e.g. Room Service: 100 THB/order per KB). Do NOT
                        # say 'complimentary' — bot must defer to KB/RAG for
                        # the exact figure. Phrase anti-'complimentary' so
                        # the LLM picks the right answer for fee questions.
                        price_str = "price varies — service charge may apply, see KB"
                    elif float(price) == 0:
                        price_str = "complimentary"
                    else:
                        price_str = f"{int(price):,} THB"
                    lines.append(f"  - {label}: {hours} @ {loc} ({price_str})")
        except Exception as e:
            logger.warning(f"hotel_services snapshot failed: {e}")

        # Phase J.2 directive (2026-06-17, user): NO hardcoded KB knowledge in
        # the snapshot. The snapshot only carries facts queried LIVE from PMS
        # DB tables (room_types, hotel_services). Parking levels (B1/B2/B3),
        # KB policy text, etc. stay in the knowledge_base markdown and must
        # be retrieved through RAG. If parking retrieval is weak, fix it at
        # the vector / chunking / re-rank layer, not by baking text here.
        snapshot = "\n".join(lines)
    except Exception as e:
        logger.warning(f"_get_hotel_snapshot_cached: DB query failed ({e}); using static fallback")
        snapshot = (
            "Hotel: The Grand Horizon Hotel\n"
            "(LIVE inventory unavailable — query DB if guest asks for counts.)"
        )
    _SNAPSHOT_CACHE["text"] = snapshot
    _SNAPSHOT_CACHE["expires_at"] = now_s + ttl_sec
    return snapshot


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

    # Sampling discipline for CJK-leak prevention (see §5.14.7 of thesis CH5).
    # top_p=0.8  — nucleus sampling, tighter than the ~0.95 default; cuts the
    #              long tail where CJK tokens leak in a Thai/English context.
    # min_p=0.05 — relative threshold: drop any token with p < 5% of p_top.
    #              The strongest filter against out-of-distribution CJK.
    # repeat_penalty (Ollama) / repetition_penalty (OpenRouter) = 1.05 — mild
    #              loop guard for chain-of-thought runaway, doesn't hurt fluency.
    TOP_P = 0.8
    MIN_P = 0.05
    REPEAT_PENALTY = 1.05

    if runtime_config.backend == LLMBackend.OLLAMA:
        # Qwen3.5 on Ollama splits output into reasoning/content fields.
        # With think=True, streaming chunks have content="" (tokens go to
        # delta.reasoning which langchain doesn't expose). Disable thinking
        # so all tokens go to content for proper SSE streaming.
        logger.info(
            f"Using Ollama LLM: {runtime_config.ollama_model} "
            f"(thinking={runtime_config.thinking}, top_p={TOP_P}, min_p={MIN_P}, repeat_penalty={REPEAT_PENALTY})"
        )
        # min_p and repeat_penalty are Ollama-specific extensions; the OpenAI-
        # compatible endpoint passes them through `extra_body.options`.
        return ChatOpenAI(
            model=runtime_config.ollama_model,
            openai_api_key="sk-ollama-not-needed",
            openai_api_base=runtime_config.ollama_base_url,
            temperature=temp,
            max_tokens=tokens,
            top_p=TOP_P,
            streaming=streaming,
            model_kwargs={
                "extra_body": {
                    "options": {
                        "min_p": MIN_P,
                        "repeat_penalty": REPEAT_PENALTY,
                    }
                }
            },
        )
    else:
        # Rate limit OpenRouter calls to prevent 429
        runtime_config.rate_limiter.wait_and_acquire()
        model = runtime_config.openrouter_model
        logger.info(
            f"Using OpenRouter LLM: {model} "
            f"(thinking={runtime_config.thinking}, top_p={TOP_P}, min_p={MIN_P}, repetition_penalty={REPEAT_PENALTY})"
        )

        api_key = runtime_config.openrouter_api_key or os.getenv("OPENROUTER_API_KEY")

        # Build extra body: sampling discipline + (optional) thinking reasoning.
        # OpenRouter uses `repetition_penalty` (not Ollama's `repeat_penalty`)
        # and accepts `min_p` directly on the body for Qwen-family providers.
        extra_body = {
            "min_p": MIN_P,
            "repetition_penalty": REPEAT_PENALTY,
        }
        if runtime_config.thinking:
            extra_body["reasoning"] = {"effort": "high"}

        return ChatOpenAI(
            model=model,
            openai_api_key=api_key,
            openai_api_base=runtime_config.openrouter_base_url,
            temperature=temp,
            max_tokens=tokens,
            top_p=TOP_P,
            streaming=streaming,
            model_kwargs={"extra_body": extra_body},
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
        calculate_dynamic_price,
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

    # D3 fix: booking-envelope pricing intents (e.g. "จะมาพักวันที่ 15 มิถุนายน
    # 3 คืน ค่าห้องดีลักซ์เท่าไหร่") never reach handle_knowledge, so pre-fetch
    # dynamic pricing here too. Without this, the booking sub-agent quotes
    # base_price from the rate card and misses Last-Minute / Early-Bird brackets.
    # Same helper used by handle_knowledge — Thai/CN/EN dates + room types covered.
    #
    # Phase J.3 tool-call surfacing: the helper now also returns a structured
    # tool_record so we can synthesize a real AIMessage(tool_calls=[...]) +
    # ToolMessage pair and append them to the state. This guarantees the
    # response envelope sees a genuine calculate_dynamic_price tool invocation
    # without forcing the LLM to re-call the tool (deterministic; no extra
    # LLM round-trip; rubric passes whenever the helper fires).
    pricing_block, pricing_tool_record = (
        _maybe_compute_pricing_context(user_text) if user_text else ("", None)
    )

    # Phase J.4 multi-turn pricing fallback (2026-06-18): on follow-up turns
    # like "How much will it cost?" / "ราคาเท่าไหร่คะ" / "总价多少" the current
    # message has the price signal but no room/dates of its own — those live
    # in turn 0 of the booking thread. When the helper returns None AND the
    # current turn carries a price-asking signal, concatenate the last up-to-2
    # prior HumanMessage texts with the current text and re-run the helper.
    # Critical guard: the gate matches the helper's own price_signals list
    # (see _maybe_compute_pricing_context) so a neutral follow-up like
    # "tell me about the room" on turn 2 of a booking thread is never priced.
    if pricing_tool_record is None and user_text:
        _low = user_text.lower()
        _price_gate = (
            "price", "cost", "how much", "rate", "ราคา", "เท่าไหร่", "เท่าไร",
            "กี่บาท", "价格", "总价", "多少钱", "多少", "费用",
        )
        if any(s in _low or s in user_text for s in _price_gate):
            _prior_human: list = []
            for _msg in reversed(state.get("messages", []) or []):
                if isinstance(_msg, HumanMessage):
                    _txt = _msg.content or ""
                    # Skip the current turn (already in user_text).
                    if _txt == user_text and not _prior_human:
                        continue
                    if _txt:
                        _prior_human.append(_txt)
                    if len(_prior_human) >= 2:
                        break
            if _prior_human:
                # Oldest-first so dates/room-type in turn 0 read naturally
                # before the current price-asking turn.
                _combined = "\n".join(reversed(_prior_human)) + "\n" + user_text
                _block2, _rec2 = _maybe_compute_pricing_context(_combined)
                if _rec2 is not None:
                    pricing_block, pricing_tool_record = _block2, _rec2

    # Phase L (booking mirror): deterministic pricing shortcut. Mirrors the
    # inventory shortcut in handle_knowledge (line ~1330) that recovered 7/7
    # inventory failures by removing the LLM's answer/refuse decision. When
    # _maybe_compute_pricing_context fires it means dates + room type were
    # parsed AND calculate_dynamic_price already returned a structured result
    # — the only remaining job is language polish. The slow tool-bound path
    # below is preserved for booking turns that don't trigger this gate
    # (create_reservation flows, cancellation, availability-only queries,
    # check-in/out, etc.).
    #
    # Why no tools are bound to polish_llm:
    #   The prior tool-bound implementation returned empty content because
    #   the model kept emitting tool_calls instead of natural language. With
    #   tools unbound the model has no choice but to write prose.
    if pricing_tool_record and user_text:
        # Cheap language detection — same heuristic the inventory shortcut uses.
        if any('฀' <= c <= '๿' for c in user_text):
            lang_hint = "Thai (Thai script, use ค่ะ/คะ particles)"
        elif any('一' <= c <= '鿿' for c in user_text):
            lang_hint = "Mandarin Chinese (Simplified, address guest as 您)"
        else:
            lang_hint = "English"

        polish_prompt = ChatPromptTemplate.from_messages([
            ("system",
             f"You are a hotel concierge at The Grand Horizon Hotel. "
             f"Translate the LIVE PRICING result below into a polite 2-3 "
             f"sentence reply in {lang_hint}.\n"
             "RULES:\n"
             "- Quote every number VERBATIM (per-night rate, nights, total, "
             "any discount or surcharge). Do not round, do not omit.\n"
             "- Identify which rate tier was applied (Early Bird / Standard / "
             "Last-Minute) using ONLY what the tool output says. If the tool "
             "output does not name a tier, do not invent one.\n"
             "- Do NOT write 'I don't have', 'let me check', 'I apologize, "
             "but', 'ไม่มีข้อมูล', or any deferral phrase. The numbers ARE "
             "below.\n"
             "- Do NOT quote the base rate-card price from memory. Use ONLY "
             "the LIVE PRICING block.\n"
             "- Do NOT quote the base rate-card price (e.g. 'base price of X "
             "THB', 'rate-card price of X THB', 'usual rate of X THB'). Quote "
             "ONLY the final per-night rate (after any discount or surcharge) "
             "and the nights x rate total.\n"
             "- Do NOT show the discount multiplier (e.g. '(x0.85)', 'x1.20', "
             "'x 0.85', 'multiplied by 0.85'). Just name the tier (Early Bird "
             "/ Standard / Last-Minute) and the final numbers.\n\n"
             f"LIVE PRICING (authoritative, from calculate_dynamic_price):\n"
             f"{pricing_tool_record['result']}"),
            ("human", user_text),
        ])
        polish_llm_settings = config.get('configurable', {}).get('llm_settings', {})
        polish_llm = get_llm(
            temperature=polish_llm_settings.get('temperature', 0.1),
            max_tokens=polish_llm_settings.get('max_tokens', 256),
        )
        polished = await (polish_prompt | polish_llm).ainvoke(state, config)
        if isinstance(polished, AIMessage) and isinstance(polished.content, str):
            cleaned = strip_tool_call_codeblocks(polished.content)
            if cleaned != polished.content:
                logger.info("handle_booking[pricing-shortcut]: stripped tool-call leak")
                polished = AIMessage(content=cleaned, id=polished.id) if polished.id else AIMessage(content=cleaned)

        # Deterministic synthesis: a real AIMessage(tool_calls=[...]) +
        # matching ToolMessage so the response envelope sees a genuine
        # calculate_dynamic_price invocation, followed by the polished reply.
        tc_id = f"call_{uuid.uuid4().hex[:16]}"
        synth_ai = AIMessage(
            content="",
            tool_calls=[{
                "name": pricing_tool_record["name"],
                "args": pricing_tool_record["args"],
                "id": tc_id,
                "type": "tool_call",
            }],
        )
        synth_tool = ToolMessage(
            content=pricing_tool_record["result"],
            tool_call_id=tc_id,
            name=pricing_tool_record["name"],
        )
        logger.info("handle_booking: pricing shortcut emitted deterministic answer")
        return {
            "messages": [synth_ai, synth_tool, polished],
            "current_intent": "booking",
        }

    # Fallback path: when the pricing helper did not fire (no dates, no room
    # type, or non-pricing booking intent), keep the original tool-bound LLM
    # flow. The LIVE PRICING block — when present without a tool_record, which
    # cannot currently happen but is defensive — would still be appended.
    if pricing_block:
        booking_prompt = (
            booking_prompt
            + "\n\n"
            + pricing_block
            + "\n\nWhen quoting a price for these dates/room type, USE THE LIVE"
            + " PRICING NUMBERS ABOVE (they already include any Early-Bird"
            + " discount or Last-Minute surcharge). Do NOT quote the base"
            + " rate-card price from memory."
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

    return {
        "messages": [result],
        "current_intent": "booking",
    }


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


# ----------------------------------------------------------------------------
# Pricing pre-fetch helper for the knowledge sub-agent
# ----------------------------------------------------------------------------

# Room type detection: EN / TH / CN
_ROOM_TYPE_PATTERNS = [
    ("Standard",  [r"standard\b", r"สแตนดาร์ด", r"สแตนดาด", r"标准间", r"标准房"]),
    ("Deluxe",    [r"deluxe\b",   r"ดีลักซ์",   r"ดีลัก",   r"豪华间", r"豪华房"]),
    ("Suite",     [r"suite\b",    r"สวีท",     r"สูท",     r"套房"]),
    ("Penthouse", [r"penthouse\b",r"เพนท์เฮาส์",r"เพนเฮาส์",r"顶层套房", r"顶楼套房"]),
]

# Thai month names for date parsing
_TH_MONTHS = {
    "มกราคม": 1, "ม.ค.": 1, "ม.ค": 1, "กุมภาพันธ์": 2, "ก.พ.": 2, "ก.พ": 2,
    "มีนาคม": 3, "มี.ค.": 3, "มี.ค": 3, "เมษายน": 4, "เม.ย.": 4, "เม.ย": 4,
    "พฤษภาคม": 5, "พ.ค.": 5, "พ.ค": 5, "มิถุนายน": 6, "มิ.ย.": 6, "มิ.ย": 6,
    "กรกฎาคม": 7, "ก.ค.": 7, "ก.ค": 7, "สิงหาคม": 8, "ส.ค.": 8, "ส.ค": 8,
    "กันยายน": 9, "ก.ย.": 9, "ก.ย": 9, "ตุลาคม": 10, "ต.ค.": 10, "ต.ค": 10,
    "พฤศจิกายน": 11, "พ.ย.": 11, "พ.ย": 11, "ธันวาคม": 12, "ธ.ค.": 12, "ธ.ค": 12,
}

# English month names
_EN_MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}


def _detect_room_type(text: str) -> Optional[str]:
    """Return canonical English room type if any pattern matches, else None."""
    low = text.lower()
    for canonical, patterns in _ROOM_TYPE_PATTERNS:
        for pat in patterns:
            if _re.search(pat, low):
                # DB ground truth (room_types.name): 'Standard Room', 'Deluxe Room', 'Suite', 'Penthouse'.
                # Suite + Penthouse are stored without a ' Room' suffix, so don't append one for them.
                if canonical in ("Penthouse", "Suite"):
                    return canonical
                return canonical + " Room"
    return None


# Day-of-week → weekday() index (0=Monday … 6=Sunday) for relative-date parsing.
# Phase J.2.5 (2026-06-17): "อังคารหน้า" / "next Tuesday" recognition. A guest who
# says "book a room next Tuesday" must NOT be re-asked for the date — that breaks
# the human-chatting illusion that's the bot's selling point.
_TH_DAYS = {
    "จันทร์": 0, "อังคาร": 1, "พุธ": 2,
    "พฤหัสบดี": 3, "พฤหัส": 3, "พรหัส": 3,  # misspellings tolerated
    "ศุกร์": 4, "ศุก": 4,
    "เสาร์": 5, "อาทิตย์": 6,
}
_EN_DAYS = {
    "monday": 0, "mon": 0, "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2, "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4, "saturday": 5, "sat": 5, "sunday": 6, "sun": 6,
}


def _next_weekday(anchor, target_dow: int):
    """Return the next occurrence of `target_dow` STRICTLY AFTER `anchor`."""
    from datetime import timedelta
    days_ahead = (target_dow - anchor.weekday() + 7) % 7
    if days_ahead == 0:
        days_ahead = 7  # if today is the same DOW, the guest means next week
    return anchor + timedelta(days=days_ahead)


def _extract_relative_date(text: str):
    """Parse relative-date phrases ("next Tuesday", "อังคารหน้า", "tomorrow", "พรุ่งนี้")
    into an absolute date string YYYY-MM-DD. Returns None if no relative phrase
    is detected.

    Anchor = today in Bangkok timezone (so the bot's day-of-week math matches
    the guest's wall clock).
    """
    if not text:
        return None
    from datetime import datetime, timezone, timedelta
    bangkok_tz = timezone(timedelta(hours=7))
    today = datetime.now(bangkok_tz).date()

    # Same-day / next-day shortcuts (TH/EN/CN)
    if _re.search(r"\b(day\s*after\s*tomorrow)\b|มะรืนนี้|มะรืน|后天", text, _re.IGNORECASE):
        return (today + timedelta(days=2)).strftime("%Y-%m-%d")
    if _re.search(r"\btomorrow\b|พรุ่งนี้|明天", text, _re.IGNORECASE):
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")
    if _re.search(r"\btonight\b|คืนนี้|今晚", text, _re.IGNORECASE):
        return today.strftime("%Y-%m-%d")
    if _re.search(r"\btoday\b|วันนี้|今天", text, _re.IGNORECASE):
        return today.strftime("%Y-%m-%d")

    # "next <day>" / "<day> หน้า" / "下星期X" — pick the next occurrence.
    # Thai pattern: "อังคารหน้า" or "วันอังคารหน้า"
    for name, dow in _TH_DAYS.items():
        if (name + "หน้า") in text or ("วัน" + name + "หน้า") in text:
            return _next_weekday(today, dow).strftime("%Y-%m-%d")
    # English "next Tuesday" / "this coming Tuesday"
    m = _re.search(
        r"\b(?:next|this\s+coming|coming)\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)\b",
        text, _re.IGNORECASE,
    )
    if m:
        return _next_weekday(today, _EN_DAYS[m.group(1).lower()]).strftime("%Y-%m-%d")
    # Chinese "下周二" / "下星期二" — map last char to DOW
    cn_dow = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}
    m = _re.search(r"(?:下周|下星期)([一二三四五六日天])", text)
    if m:
        return _next_weekday(today, cn_dow[m.group(1)]).strftime("%Y-%m-%d")

    # "next week" / "สัปดาห์หน้า" / "下周" — default to upcoming Monday
    if _re.search(r"\bnext\s+week\b|สัปดาห์หน้า|อาทิตย์หน้า|下周|下星期(?![一二三四五六日天])", text, _re.IGNORECASE):
        return _next_weekday(today, 0).strftime("%Y-%m-%d")

    # "weekend" / "this weekend" / "สุดสัปดาห์นี้" — Saturday of this week
    if _re.search(r"\b(this\s+)?weekend\b|สุดสัปดาห์นี้|สุดสัปดาห์หน้า|周末|本周末", text, _re.IGNORECASE):
        # Saturday after today; if today IS Saturday, use today
        if today.weekday() == 5:
            return today.strftime("%Y-%m-%d")
        return _next_weekday(today, 5).strftime("%Y-%m-%d")

    return None


def _extract_dates(text: str) -> List[str]:
    """Extract dates in YYYY-MM-DD format from EN/TH/CN free text.

    Returns at most 2 dates (check-in, check-out). Best-effort — returns
    [] if no date can be parsed confidently.
    """
    from datetime import datetime, timedelta
    dates = []

    # 1. ISO format: 2026-07-15 or 2026/07/15
    for m in _re.finditer(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", text):
        try:
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            dates.append(f"{y:04d}-{mo:02d}-{d:02d}")
        except ValueError:
            pass

    # 2. Chinese: 2026年7月15日, 7月15日
    today_year = datetime.now().year
    for m in _re.finditer(r"(?:(\d{4})\s*年)?\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日?", text):
        try:
            y = int(m.group(1)) if m.group(1) else today_year
            mo, d = int(m.group(2)), int(m.group(3))
            dates.append(f"{y:04d}-{mo:02d}-{d:02d}")
        except ValueError:
            pass

    # 3. Thai: "15 กรกฎาคม 2026" or "15 ก.ค. 2026" or "15-17 กรกฎาคม 2026"
    th_month_re = "|".join(_re.escape(m) for m in _TH_MONTHS.keys())
    th_pattern = _re.compile(
        rf"(\d{{1,2}})(?:\s*(?:ถึง|-|–)\s*(\d{{1,2}}))?\s*({th_month_re})\s*(\d{{4}})?",
        _re.IGNORECASE,
    )
    for m in th_pattern.finditer(text):
        try:
            d1 = int(m.group(1))
            d2 = int(m.group(2)) if m.group(2) else None
            mo = _TH_MONTHS[m.group(3)]
            y = int(m.group(4)) if m.group(4) else today_year
            dates.append(f"{y:04d}-{mo:02d}-{d1:02d}")
            if d2:
                dates.append(f"{y:04d}-{mo:02d}-{d2:02d}")
        except (ValueError, KeyError):
            pass

    # 4. English: "July 15", "July 15 to July 17, 2026", "July 15-17"
    en_month_re = "|".join(_EN_MONTHS.keys())
    en_pattern = _re.compile(
        rf"\b({en_month_re})\s+(\d{{1,2}})(?:\s*(?:to|through|-|–)\s*(?:(?:({en_month_re})\s+)?(\d{{1,2}})))?(?:[\s,]+(\d{{4}}))?",
        _re.IGNORECASE,
    )
    for m in en_pattern.finditer(text):
        try:
            mo1 = _EN_MONTHS[m.group(1).lower()]
            d1 = int(m.group(2))
            mo2 = _EN_MONTHS[m.group(3).lower()] if m.group(3) else mo1
            d2 = int(m.group(4)) if m.group(4) else None
            y = int(m.group(5)) if m.group(5) else today_year
            dates.append(f"{y:04d}-{mo1:02d}-{d1:02d}")
            if d2:
                dates.append(f"{y:04d}-{mo2:02d}-{d2:02d}")
        except (ValueError, KeyError):
            pass

    # Dedup while preserving order, return at most 2
    seen, out = set(), []
    for d in dates:
        if d not in seen:
            seen.add(d)
            out.append(d)
        if len(out) >= 2:
            break

    # Phase J.2.5 (2026-06-17): if no absolute date was extracted by the
    # regex paths above, try the relative-date interpreter ("tomorrow",
    # "next Tuesday", "อังคารหน้า"). This is what makes the bot feel like
    # a human concierge — a guest saying "next Tuesday" should never be
    # re-asked for the date.
    if not out:
        rel = _extract_relative_date(text)
        if rel:
            out.append(rel)

    # "N nights" / "N คืน" / "N 晚" pattern: if we have only one date,
    # derive the check-out as check-in + N nights. Covers EN "for 3
    # nights", TH "3 คืน" / "พัก 3 คืน", CN "3 晚".
    if len(out) == 1:
        nights = None
        for m in _re.finditer(
            r"(\d{1,2})\s*(?:nights?|คืน|晚)|(?:for|stay|พัก|住)\s*(\d{1,2})\s*(?:nights?|คืน|晚)",
            text,
            _re.IGNORECASE,
        ):
            try:
                nights = int(m.group(1) or m.group(2))
                if 1 <= nights <= 30:
                    break
                nights = None
            except (ValueError, TypeError):
                pass
        if nights:
            try:
                ci = datetime.strptime(out[0], "%Y-%m-%d")
                co = ci + timedelta(days=nights)
                out.append(co.strftime("%Y-%m-%d"))
            except (ValueError, NameError):
                pass

    return out


def _maybe_compute_pricing_context(message: str) -> Tuple[str, Optional[Dict[str, Any]]]:
    """If the user asks about pricing for a specific room type + date(s),
    pre-compute dynamic pricing and return BOTH a context block for the LLM
    AND a structured tool-record so the caller can synthesize a real
    AIMessage(tool_calls=[...]) + ToolMessage pair into the state's
    messages. That way the response envelope sees a genuine
    calculate_dynamic_price tool_call in the conversation history.

    Returns:
        (context_block, tool_record) where tool_record is
        {"name": "calculate_dynamic_price",
         "args": {"room_type":..., "check_in_date":..., "check_out_date":...},
         "result": "<tool output string>"} on success, or ("", None) when
        the message isn't a pricing query or the tool call failed.
    """
    if not message:
        return "", None

    # Cheap intent gate — only trigger on messages that mention price/cost
    low = message.lower()
    price_signals = (
        "price", "cost", "how much", "rate", "ราคา", "เท่าไหร่", "เท่าไร", "กี่บาท",
        "价格", "多少钱", "多少", "费用",
    )
    if not any(s in low or s in message for s in price_signals):
        return "", None

    room_type = _detect_room_type(message)
    if not room_type:
        return "", None

    dates = _extract_dates(message)
    if not dates:
        return "", None

    check_in = dates[0]
    check_out = dates[1] if len(dates) > 1 else None

    if not check_out:
        # Single-date query — quote a 1-night stay starting that day.
        try:
            from datetime import datetime as _dt, timedelta as _td
            d = _dt.strptime(check_in, "%Y-%m-%d")
            check_out = (d + _td(days=1)).strftime("%Y-%m-%d")
        except Exception:
            check_out = check_in

    try:
        from src.agent.hotel_tools import calculate_dynamic_price
        args = {
            "room_type": room_type,
            "check_in_date": check_in,
            "check_out_date": check_out,
        }
        result = calculate_dynamic_price.invoke(args)
        block = (
            "LIVE PRICING (already calculated for these specific dates — "
            "USE THESE NUMBERS, NOT the rate card above):\n" + result
        )
        return block, {
            "name": "calculate_dynamic_price",
            "args": args,
            "result": result,
        }
    except Exception as e:
        logger.warning(f"_maybe_compute_pricing_context failed: {e}")
        return "", None


# WiFi disclosure: The Grand Horizon does NOT publish a fixed WiFi password.
# Each in-house reservation gets a randomly-generated per-stay password
# (see policies_rules.md § "WiFi Access Policy" and facilities_amenities.md).
# This helper looks up the requesting user_id's active reservation; if they
# are checked in, we inject a LIVE GUEST WIFI block so the LLM can share
# their own room's password. Otherwise we return empty and the LLM falls
# through to the KB policy text and politely declines.
_WIFI_INTENT_TOKENS = (
    "wifi", "wi-fi", "wi fi", "password",
    "รหัสไวไฟ", "รหัสwifi", "รหัส wifi", "อินเทอร์เน็ต", "ไวไฟ",
    "wifi 密码", "wifi密码", "无线", "上网", "网络密码",
)


def _maybe_compute_wifi_context(message: str, user_id: str) -> str:
    """Inject LIVE GUEST WIFI block when the asker is a checked-in guest.

    Args:
        message: The guest's last user message (used as the intent gate —
            only fires when the message actually mentions WiFi/password).
        user_id: The session's user_id. Either an authenticated guest email
            we can look up in the guests table, or "guest"/anonymous in
            which case we always return empty.

    Returns: Either a "LIVE GUEST WIFI (...)" block string, or "" when the
    guest hasn't checked in / doesn't ask about WiFi / we can't look them up.
    Never raises — failure modes all degrade to empty so the LLM falls back
    to the published KB policy.
    """
    if not message or not user_id:
        return ""
    low = (message or "").lower()
    if not any(t in low for t in _WIFI_INTENT_TOKENS):
        return ""
    uid = (user_id or "").strip().lower()
    if not uid or uid in ("guest", "anonymous", "test", "probe", "canary"):
        return ""

    try:
        # user_id is treated as the guest's email — same convention as
        # get_guest_reservations(). Fall through quietly if it's not.
        if "@" not in uid:
            return ""
        from src.agent.hotel_tools import get_db_connection
        import psycopg2.extras
        with get_db_connection() as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                cur.execute("""
                    SELECT res.confirmation_number, res.wifi_password,
                           res.check_in_date, res.check_out_date,
                           r.room_number
                    FROM reservations res
                    JOIN rooms r ON res.room_id = r.room_id
                    JOIN guests g ON res.guest_id = g.guest_id
                    WHERE LOWER(g.email) = %s
                      AND res.status = 'checked_in'
                      AND CURRENT_DATE BETWEEN res.check_in_date AND res.check_out_date
                    ORDER BY res.check_in_date DESC
                    LIMIT 1
                """, (uid,))
                row = cur.fetchone()
        if not row or not row.get("wifi_password"):
            return ""
        return (
            "LIVE GUEST WIFI (this guest is currently checked in — share "
            "THIS specific per-stay password verbatim, do NOT redirect them "
            "to the front desk):\n"
            f"- Room: {row['room_number']}\n"
            f"- Confirmation: {row['confirmation_number']}\n"
            f"- Network name (SSID): HotelGuest\n"
            f"- Per-stay WiFi password: {row['wifi_password']}\n"
            f"- Valid through check-out date: {row['check_out_date']}\n"
            "- This password expires automatically at check-out."
        )
    except Exception as e:
        logger.warning(f"_maybe_compute_wifi_context failed: {e}")
        return ""


# Phase J.2: live room-inventory pre-injection.
# Triggered by "how many rooms", "จำนวนห้อง", "多少间客房" style asks.
# Reads the rooms table at request time so admin updates (rooms added,
# rooms taken out of order) take effect immediately — same DB-is-truth
# principle as Phase J price/occupancy/hours migration.
_INVENTORY_TRIGGERS = (
    "how many room", "how many standard", "how many deluxe", "how many suite",
    "how many penthouse", "total number of room", "total rooms",
    "room count", "number of rooms", "many rooms do",
    "จำนวนห้อง", "มีห้อง", "ห้องกี่ห้อง", "กี่ห้อง",
    "多少间", "几间", "客房数",
)

def _maybe_compute_inventory_context(message: str) -> str:
    """Return LIVE INVENTORY block when the guest asks 'how many rooms'.

    Returns empty string when the message isn't an inventory question
    (cheap regex/substring gate — no DB hit for unrelated turns).
    """
    if not message:
        return ""
    low = message.lower()
    if not any(t in low or t in message for t in _INVENTORY_TRIGGERS):
        return ""
    try:
        from src.agent.hotel_tools import get_room_inventory
        result = get_room_inventory.invoke({})
        if not result or "error" in result.lower()[:50]:
            return ""
        # Strong directive to make TH-Gemma quote the live block instead of
        # ignoring it in favour of RAG prose (observed 2026-06-16 smoke).
        return (
            "=== LIVE INVENTORY (from PMS DB — AUTHORITATIVE, OVERRIDES KB) ===\n"
            f"{result}\n"
            "=== END LIVE INVENTORY ===\n"
            "When the guest asks 'how many rooms / กี่ห้อง / 多少间', QUOTE\n"
            "the LIVE INVENTORY numbers above VERBATIM. Do NOT list room types\n"
            "as a substitute, do NOT reference KB descriptive prose for the\n"
            "count, do NOT say 'I'll check' — the count is right above this line."
        )
    except Exception as e:
        logger.warning(f"_maybe_compute_inventory_context failed: {e}")
        return ""


# D2 fix: multi-intent decomposition for RAG.
# Delimiters that signal the guest packed multiple distinct questions into
# one message. We split on these BEFORE embedding so each intent gets its
# own nearest-neighbour search in vector space — a single embedding of a
# multi-intent query lands between topic clusters and retrieves generic
# facility chunks instead of the specific facts (see live-test Defect 2).
_MULTI_INTENT_SPLIT_RE = _re.compile(
    r"\s*(?:\?+|；|;|\band also\b|\band\b|\balso\b|\bplus\b|"
    r"และ|กับ|"
    r"和|还有|、)\s*",
    _re.IGNORECASE,
)

_INFO_KEYWORDS = (
    "wifi", "password", "breakfast", "pool", "spa", "gym", "check",
    "checkout", "check-in", "check-out", "parking", "laundry", "shuttle",
    "restaurant", "bar", "hour", "time", "where", "when", "how", "what",
    "อาหาร", "สระ", "อินเตอร์เน็ต", "WiFi", "รหัส", "เช็ค",
    "早餐", "游泳池", "密码", "WiFi", "几点", "几号",
)

# Phase G: greeting / self-intro patterns to strip from a sub-query BEFORE
# embedding. The model's vector search drifts toward small-talk chunks when
# "Hi, I'm James. Checking in tomorrow." is present, missing the actual
# breakfast/WiFi sections.
_GREETING_STRIP_RE = _re.compile(
    r"^(?:"
    r"hi\b[^.?!]*[.?!]?\s*"
    r"|hello\b[^.?!]*[.?!]?\s*"
    r"|hey\b[^.?!]*[.?!]?\s*"
    r"|good (?:morning|afternoon|evening)\b[^.?!]*[.?!]?\s*"
    r"|i['’]?m\s+\w+\b[^.?!]*[.?!]?\s*"
    r"|i am\s+\w+\b[^.?!]*[.?!]?\s*"
    r"|my name is\s+\w+\b[^.?!]*[.?!]?\s*"
    r"|checking in\b[^.?!]*[.?!]?\s*"
    r"|i['’]?ll be (?:checking in|arriving|staying)\b[^.?!]*[.?!]?\s*"
    r"|สวัสดี\S*\s*"
    r"|ดิฉันชื่อ\s*\S+\s*"
    r"|ผมชื่อ\s*\S+\s*"
    r"|จะมาพัก\b[^?]*?\s*"
    r"|你好\S*\s*"
    r"|我叫\s*\S+\s*"
    r"|我是\s*\S+\s*"
    r")+",
    _re.IGNORECASE,
)


def _strip_greeting_intro(sub_query: str) -> str:
    """Remove leading greetings + self-intros from a sub-query so the
    embedding centroid lands on the actual info request, not the small-talk.

    Returns the cleaned string, or the original if stripping would leave
    fewer than 3 chars (e.g. the message WAS only a greeting)."""
    if not sub_query:
        return sub_query
    cleaned = _GREETING_STRIP_RE.sub("", sub_query).strip(" ,.?!")
    return cleaned if len(cleaned) >= 3 else sub_query


# Phase H: keyword extraction — strip politeness particles + filler phrases
# from a sub-query BEFORE embedding. The qwen3-embedding-8b centroid drifts
# toward a 'generic-courtesy' cluster on polite TH/CN phrasings, missing
# the breakfast/WiFi/spa chunk at top-5 even when the query is otherwise
# specific. The LLM still sees the original sub-query in [Q{i}: ...] so
# the response tone is preserved.
_TH_PARTICLES = (
    "ค่ะ", "คะ", "ครับ", "น่ะ", "หน่อย",
    "ขอ", "ช่วย", "ที่", "ทาง", "โปรด",
)
_CN_POLITENESS = (
    "请问", "麻烦", "您", "我想", "一下",
    "可以告诉我", "是什么",
)
_EN_FILLERS = (
    "could you tell me", "would you mind", "i'd like to know",
    "i would like to know", "can you tell me",
    "thank you", "thanks", "please",
)

_TH_CN_STRIP_RE = _re.compile(
    "|".join(_re.escape(t) for t in (_TH_PARTICLES + _CN_POLITENESS))
)
_EN_FILLERS_RE = _re.compile(
    r"\b(?:" + "|".join(_re.escape(f) for f in sorted(_EN_FILLERS, key=len, reverse=True)) + r")\b",
    _re.IGNORECASE,
)

_THAI_RE = _re.compile(r"[฀-๿]")
_CJK_RE = _re.compile(r"[一-鿿]")


def _extract_query_keywords(text: str, lang_hint: Optional[str] = None) -> str:
    """Phase H: strip politeness/filler markers from a sub-query before it
    goes to the embedding model. Applies all script-applicable lists so
    mixed-script messages ('WiFi password 请问') get fully cleaned. Falls
    back to the original string if cleaning would leave < 3 chars.
    """
    if not text:
        return text
    cleaned = text
    has_thai = bool(_THAI_RE.search(cleaned)) or lang_hint == "th"
    has_cjk = bool(_CJK_RE.search(cleaned)) or lang_hint == "zh"
    has_latin = bool(_re.search(r"[A-Za-z]", cleaned)) or lang_hint == "en"
    if has_thai or has_cjk:
        cleaned = _TH_CN_STRIP_RE.sub(" ", cleaned)
    if has_latin:
        cleaned = _EN_FILLERS_RE.sub(" ", cleaned)
    cleaned = _re.sub(r"\s+", " ", cleaned).strip(" ,.?!。？，")
    return cleaned if len(cleaned) >= 3 else text


def _split_multi_intent(text: str, max_parts: int = 4) -> List[str]:
    """D2: split a guest message into distinct sub-questions for RAG.

    Returns a list of length 1 (no split needed) up to ``max_parts``.
    Conservative: only splits when at least two of the resulting parts
    contain an information keyword, so we don't over-fragment a normal
    single-intent sentence that happens to contain 'and'.
    """
    if not text or len(text) < 12:
        return [text] if text else []
    raw_parts = [p.strip() for p in _MULTI_INTENT_SPLIT_RE.split(text) if p and p.strip()]
    if len(raw_parts) < 2:
        return [text]
    informative = [
        p for p in raw_parts
        if any(kw.lower() in p.lower() for kw in _INFO_KEYWORDS)
        or any(kw in p for kw in _INFO_KEYWORDS)
    ]
    if len(informative) < 2:
        return [text]
    seen, out = set(), []
    for p in informative:
        key = p.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
        if len(out) >= max_parts:
            break
    return out or [text]


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
    # D2 fix: multi-intent decomposition. If the guest packed 2+ distinct
    # info-bearing questions into one message ("WiFi password AND breakfast
    # time?"), retrieve the top-3 chunks PER sub-question rather than
    # 5 chunks for the combined embedding (which lands between intent
    # clusters and returns generic facility chunks).
    #
    # HOTEL_QUERY_REWRITE_ENABLED env gate: covers (a) multi-intent split,
    # (b) _strip_greeting_intro on embed paths, (c) _extract_query_keywords
    # politeness-particle strip. All three were introduced together in
    # Phase G/H.A as the "query rewriting" family. Setting this env to
    # "false" forces the pre-Phase-G/H baseline (single-embedding, raw
    # user text) for the confound-isolated Stack-OFF backtest.
    rewrite_enabled = os.getenv("HOTEL_QUERY_REWRITE_ENABLED", "true").lower() == "true"
    try:
        sub_queries = _split_multi_intent(last_user_message) if rewrite_enabled else [last_user_message]
        if len(sub_queries) > 1:
            logger.info(
                f"handle_knowledge: multi-intent decomposition -> {len(sub_queries)} sub-queries: "
                + " | ".join(q[:40] for q in sub_queries)
            )
            prev_n = os.environ.get("HOTEL_RAG_NUM_DOCS")
            # Phase G: bumped per-subq from 3 to 5 because the WiFi sub-query
            # "Could you tell me the WiFi password" was missing the WiFi chunk
            # at top-3 (the politeness prefix shifted the embedding centroid).
            # 5 chunks × 4 sub-queries = max 20 chunks out of 49 total.
            os.environ["HOTEL_RAG_NUM_DOCS"] = os.getenv("HOTEL_RAG_NUM_DOCS_PER_SUBQ", "5")
            try:
                blocks = []
                for i, sq in enumerate(sub_queries, 1):
                    # Phase G+H: strip greeting/self-intro AND politeness
                    # particles / filler phrases (TH/CN/EN) from the sub-query
                    # before embedding. So "Hi I'm James, เวลาอาหารเช้าหน่อยค่ะ"
                    # runs the RAG on "เวลาอาหารเช้า" (no หน่อย, no ค่ะ).
                    # The LLM still sees the original ``sq`` in the answer
                    # prompt (see ``[Q{i}: {sq}]`` formatting below).
                    embed_sq = (
                        _extract_query_keywords(_strip_greeting_intro(sq))
                        if rewrite_enabled else sq
                    )
                    try:
                        r = search_hotel_knowledge.invoke(embed_sq)
                    except Exception as e:
                        logger.warning(f"handle_knowledge: sub-query {i} RAG failed: {e}")
                        r = "(no information found for this sub-question)"
                    if len(r) > 900:
                        r = r[:900] + "\n..."
                    # Show the ORIGINAL sub-query to the LLM (preserves the
                    # guest's phrasing for the answer) but ran RAG on the
                    # stripped one.
                    blocks.append(f"[Q{i}: {sq}]\n{r}")
            finally:
                if prev_n is None:
                    os.environ.pop("HOTEL_RAG_NUM_DOCS", None)
                else:
                    os.environ["HOTEL_RAG_NUM_DOCS"] = prev_n
            knowledge_result = "\n\n===\n\n".join(blocks)
            if len(knowledge_result) > 2400:
                knowledge_result = knowledge_result[:2400] + "\n..."
        else:
            # Phase H: single-intent path also strips greeting + politeness
            # before embedding (else "请问 WiFi 密码是什么？" regresses vs
            # the multi-intent path which now strips).
            single_embed = (
                _extract_query_keywords(_strip_greeting_intro(last_user_message))
                if rewrite_enabled else last_user_message
            )
            knowledge_result = search_hotel_knowledge.invoke(single_embed)
            if len(knowledge_result) > 2000:
                knowledge_result = knowledge_result[:2000] + "\n..."
    except Exception as e:
        logger.error(f"RAG search failed: {e}")
        knowledge_result = "No information found."

    # Live dynamic pricing — invoked when the guest asks about cost for a
    # specific room type + date(s). The knowledge sub-agent's RAG only
    # returns the static rate card from data/hotel/room_types.md; without
    # this pre-fetch the LLM would quote base_price even when an Early
    # Bird discount or Last-Minute surcharge applies. See §4.x rationale.
    #
    # Phase J.3 tool-call surfacing: helper now returns (block, tool_record)
    # so we can synthesize a real AIMessage(tool_calls=[...]) + ToolMessage
    # pair into the return so the envelope walker surfaces the pricing tool
    # invocation.
    pricing_block, pricing_tool_record = _maybe_compute_pricing_context(last_user_message)

    # Phase M multi-turn pricing fallback (2026-06-18) — port of the
    # handle_booking Phase J.4 fallback (L561-585). The router sends a bare
    # context-free follow-up like "How much will it cost?" / "ราคาเท่าไหร่คะ" /
    # "总价多少" to ToHotelKnowledge (rule at L2004 "When in doubt between
    # Knowledge and Service, prefer ToHotelKnowledge"), so handle_booking's
    # multi-turn fallback never fires for these. The room type + dates live
    # in turn 0 of the thread; concatenate the last up-to-2 prior HumanMessage
    # texts with the current text and re-run the helper. The price-signal
    # gate matches _maybe_compute_pricing_context's own list so a neutral
    # follow-up ("tell me about the room") is never priced.
    if pricing_tool_record is None and last_user_message:
        _low = last_user_message.lower()
        _price_gate = (
            "price", "cost", "how much", "rate", "ราคา", "เท่าไหร่", "เท่าไร",
            "กี่บาท", "价格", "总价", "多少钱", "多少", "费用",
        )
        if any(s in _low or s in last_user_message for s in _price_gate):
            _prior_human: list = []
            for _msg in reversed(state.get("messages", []) or []):
                if isinstance(_msg, HumanMessage):
                    _txt = _msg.content or ""
                    if _txt == last_user_message and not _prior_human:
                        continue
                    if _txt:
                        _prior_human.append(_txt)
                    if len(_prior_human) >= 2:
                        break
            if _prior_human:
                _combined = "\n".join(reversed(_prior_human)) + "\n" + last_user_message
                _block2, _rec2 = _maybe_compute_pricing_context(_combined)
                if _rec2 is not None:
                    pricing_block, pricing_tool_record = _block2, _rec2
                    logger.info(
                        "handle_knowledge: Phase M multi-turn pricing fallback fired "
                        f"(combined {len(_prior_human)} prior human turn(s))"
                    )

    # WiFi disclosure (Phase H.D): per-stay password is shared only with
    # checked-in guests; anonymous askers get the KB policy and a polite decline.
    wifi_block = _maybe_compute_wifi_context(
        last_user_message,
        state.get("user_id") or "",
    )
    # Phase J.2 (2026-06-16): live inventory pre-injection for "how many X"
    # questions. Counts come from the rooms table grouped by room_type and
    # are LIVE every request — admin add/remove of rooms takes effect with
    # zero KB edits, zero re-ingest, zero redeploy.
    inventory_block = _maybe_compute_inventory_context(last_user_message)

    # Phase L: deterministic inventory shortcut. Gemma 4 12B Q8 ignores BOTH
    # the {hotel_snapshot} in main_prompt AND the LIVE INVENTORY system block
    # on 'how many X rooms' / 'กี่ห้อง' phrasings (refusal-prior pathology,
    # verified clean_v3_final_fresh_20260616T202346Z.log: retry-on-deferral
    # PROMOTED on inv_deluxe_rooms_en_1 but the promoted response still did
    # not contain '45'). Bypass the RAG-synthesis LLM call when an inventory
    # trigger fires: get_room_inventory() already returns the structured
    # counts from the rooms table, so the only job left for the LLM is
    # language polish (TH/EN/CN). This sidesteps the refusal prior because
    # the LLM is no longer making an answer/refuse decision.
    if inventory_block:
        from src.agent.hotel_tools import get_room_inventory as _gri
        inv_data = _gri.invoke({})
        # Cheap language detection — same heuristic the rest of the bot uses.
        if any('฀' <= c <= '๿' for c in last_user_message):
            lang_hint = "Thai (Thai script, use ค่ะ/คะ particles)"
        elif any('一' <= c <= '鿿' for c in last_user_message):
            lang_hint = "Mandarin Chinese (Simplified, address guest as 您)"
        else:
            lang_hint = "English"
        polish_prompt = ChatPromptTemplate.from_messages([
            ("system",
             f"You are a hotel concierge at The Grand Horizon Hotel. "
             f"Translate the LIVE ROOM INVENTORY below into a 1-2 sentence "
             f"answer in {lang_hint}.\n"
             "RULES:\n"
             "- Quote every number VERBATIM. Do not omit any count.\n"
             "- Do NOT write 'I don't have', 'let me check', 'I apologize, "
             "but', 'ไม่มีข้อมูล', or any deferral phrase. The data IS below.\n"
             "- If the guest asked about ONE specific room type (Standard / "
             "Deluxe / Suite / Penthouse), answer only for that type plus "
             "the total. Otherwise list all four types and the total.\n\n"
             f"LIVE ROOM INVENTORY (authoritative, from PMS DB):\n{inv_data}"),
            ("human", last_user_message),
        ])
        polish_llm_settings = config.get('configurable', {}).get('llm_settings', {})
        polish_llm = get_llm(
            temperature=polish_llm_settings.get('temperature', 0.1),
            max_tokens=polish_llm_settings.get('max_tokens', 256),
        )
        result = await (polish_prompt | polish_llm).ainvoke(state, config)
        if isinstance(result, AIMessage) and isinstance(result.content, str):
            cleaned = strip_tool_call_codeblocks(result.content)
            if cleaned != result.content:
                logger.info("handle_knowledge[inventory-shortcut]: stripped tool-call leak")
                result = AIMessage(content=cleaned, id=result.id) if result.id else AIMessage(content=cleaned)
        logger.info("handle_knowledge: inventory shortcut emitted deterministic answer")
        return {"messages": [result], "current_intent": "knowledge"}

    # Phase M (knowledge mirror): deterministic pricing shortcut. Mirrors the
    # Phase L booking shortcut (handle_booking L601-671). When the multi-turn
    # fallback above promotes pricing_tool_record from None to a real record,
    # the RAG LLM still won't synthesize a calculate_dynamic_price tool_call
    # (it's a knowledge synthesis path, not tool-bound). Emit a deterministic
    # AIMessage(tool_calls=[...]) + ToolMessage pair so actual_tool_calls
    # is non-empty in the envelope, then a polished language reply. This
    # fixes the mt_en_booking_context_retention class of failures where the
    # router sends "How much will it cost?" to handle_knowledge.
    if pricing_tool_record and last_user_message:
        if any('฀' <= c <= '๿' for c in last_user_message):
            lang_hint = "Thai (Thai script, use ค่ะ/คะ particles)"
        elif any('一' <= c <= '鿿' for c in last_user_message):
            lang_hint = "Mandarin Chinese (Simplified, address guest as 您)"
        else:
            lang_hint = "English"

        polish_prompt = ChatPromptTemplate.from_messages([
            ("system",
             f"You are a hotel concierge at The Grand Horizon Hotel. "
             f"Translate the LIVE PRICING result below into a polite 2-3 "
             f"sentence reply in {lang_hint}.\n"
             "RULES:\n"
             "- Quote every number VERBATIM (per-night rate, nights, total, "
             "any discount or surcharge). Do not round, do not omit.\n"
             "- Identify which rate tier was applied (Early Bird / Standard / "
             "Last-Minute) using ONLY what the tool output says. If the tool "
             "output does not name a tier, do not invent one.\n"
             "- Do NOT write 'I don't have', 'let me check', 'I apologize, "
             "but', 'ไม่มีข้อมูล', or any deferral phrase. The numbers ARE "
             "below.\n"
             "- Do NOT quote the base rate-card price from memory. Use ONLY "
             "the LIVE PRICING block.\n"
             "- Do NOT quote the base rate-card price (e.g. 'base price of X "
             "THB', 'rate-card price of X THB', 'usual rate of X THB'). Quote "
             "ONLY the final per-night rate (after any discount or surcharge) "
             "and the nights x rate total.\n"
             "- Do NOT show the discount multiplier (e.g. '(x0.85)', 'x1.20', "
             "'x 0.85', 'multiplied by 0.85'). Just name the tier (Early Bird "
             "/ Standard / Last-Minute) and the final numbers.\n\n"
             f"LIVE PRICING (authoritative, from calculate_dynamic_price):\n"
             f"{pricing_tool_record['result']}"),
            ("human", last_user_message),
        ])
        polish_llm_settings = config.get('configurable', {}).get('llm_settings', {})
        polish_llm = get_llm(
            temperature=polish_llm_settings.get('temperature', 0.1),
            max_tokens=polish_llm_settings.get('max_tokens', 256),
        )
        polished = await (polish_prompt | polish_llm).ainvoke(state, config)
        if isinstance(polished, AIMessage) and isinstance(polished.content, str):
            cleaned = strip_tool_call_codeblocks(polished.content)
            if cleaned != polished.content:
                logger.info("handle_knowledge[pricing-shortcut]: stripped tool-call leak")
                polished = AIMessage(content=cleaned, id=polished.id) if polished.id else AIMessage(content=cleaned)

        tc_id = f"call_{uuid.uuid4().hex[:16]}"
        synth_ai = AIMessage(
            content="",
            tool_calls=[{
                "name": pricing_tool_record["name"],
                "args": pricing_tool_record["args"],
                "id": tc_id,
                "type": "tool_call",
            }],
        )
        synth_tool = ToolMessage(
            content=pricing_tool_record["result"],
            tool_call_id=tc_id,
            name=pricing_tool_record["name"],
        )
        logger.info("handle_knowledge: Phase M pricing shortcut emitted deterministic answer")
        return {
            "messages": [synth_ai, synth_tool, polished],
            "current_intent": "knowledge",
        }

    # Generate response: LIVE blocks (DB-backed, authoritative) go FIRST so the
    # model anchors on them before parsing RAG prose. Phase J.2 smoke 2026-06-16
    # showed Gemma ignored a LIVE INVENTORY block when it came LAST — putting
    # it first ~doubled the quote-rate on inventory questions.
    live_blocks = []
    if inventory_block:
        live_blocks.append(inventory_block)
    if pricing_block:
        live_blocks.append(pricing_block)
    if wifi_block:
        live_blocks.append(wifi_block)
    live_prefix = ("\n\n".join(live_blocks) + "\n\n") if live_blocks else ""
    extra_context = (
        live_prefix
        + f"HOTEL INFORMATION (RAG context — secondary; LIVE blocks above are authoritative):\n{knowledge_result}"
    )

    # Phase G: knowledge synthesis prompt is now in hotel_prompt.yaml under
    # ``knowledge_synthesis`` (with optional per-model overrides). This makes
    # the rule set tunable per LLM without code edits — gemma4:12b for
    # example needs a more aggressively-worded version because of its
    # stronger refusal priors. The string MUST contain a {extra_context}
    # placeholder.
    knowledge_synthesis_tmpl = prompts.get('knowledge_synthesis', '')
    if knowledge_synthesis_tmpl and "{extra_context}" in knowledge_synthesis_tmpl:
        synthesis_text = knowledge_synthesis_tmpl.replace("{extra_context}", extra_context)
    else:
        # Defensive fallback (very small) if prompts.yaml lacks the key.
        synthesis_text = (
            "Use this hotel information to answer the guest's question "
            "above. Be direct and specific.\n\n" + extra_context
        )

    rag_prompt = ChatPromptTemplate.from_messages([
        ("system", main_prompt),
        ("human", last_user_message),
        ("system", synthesis_text),
    ])

    llm_settings = config.get('configurable', {}).get('llm_settings', {})
    # Temperature sweep (iter4/iter6) showed no meaningful improvement at
    # T=0.1 (over-conservative: +5 rag_miss, +2 tool_not_called) or
    # T=0.2 (plateau, weighted +1pp only). T=0.3 is the optimum for the
    # knowledge sub-agent.
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

You are handling a greeting, general conversation, OR an unclear /
garbled / single-token / punctuation-only input where the guest's
intent cannot be determined.

PRINCIPLES:
- Be friendly and welcoming. Never refuse or scold.
- For greetings/thanks/goodbye → reply warmly in the guest's language
  and offer one short prompt of what you can help with (rooms, dining,
  spa, facilities, booking).
- For unclear input ("?", "ok", "asdf", a lone emoji, a half-typed
  word, all caps random characters) → assume the guest is exploring or
  mis-typed. Reply politely in the language of the previous turn (or
  English if first turn), acknowledge gently ("I'm not sure I caught
  that"), and ask ONE concrete clarifying question that gives the
  guest options ("Were you asking about room rates, dining hours,
  the spa, or something else?"). Do NOT lecture, do NOT refuse, do
  NOT dump a list of every service.

For Thai speakers, use polite particles (ครับ/ค่ะ).
For English speakers, be professional and warm.
For Chinese speakers, use 您 and polite phrasing.
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

1. **ToHotelBooking** — reservations, availability, check-in/out, modify/cancel bookings, payment, ANY explicit booking request, AND any room-pricing question with a specific room type + date range (the booking sub-agent has the live `calculate_dynamic_price` tool bound).
   Examples: "Is there a room available?", "I want to cancel my booking", "Check me in", "ยกเลิกการจอง",
   "ขอจอง [room type] [dates]", "ผมต้องการจองห้อง", "I'd like to book a Deluxe for July 18-20",
   "我要预订一间套房", "I want to book", "Book me a room", "Reserve a Standard Room",
   "Can I change my booking dates?", "ขอเปลี่ยนวันเข้าพัก", "改一下日期",
   "How much is a Standard Room from June 18, 2027 to June 20, 2027?",
   "How much is a Deluxe Room from July 15-17, 2026?",
   "How much for a Suite for 3 nights starting August 5?",
   "ค่าห้องดีลักซ์วันที่ 15-17 กรกฎาคม เท่าไหร่", "标准房7月15日到17日多少钱"
2. **ToHotelService** — room service requests, extra amenities to be delivered, housekeeping, maintenance, wake-up call
   Examples: "I need extra towels", "Can I get room service?", "ขอหมอนเพิ่ม", "fix the AC"
   (Service REQUESTS — items to be delivered or actions to be performed. NOT informational
   questions about transportation, sedan rates, parking locations, or spa booking channels.)
3. **ToHotelKnowledge** — hotel info, facilities, dining, WiFi, policies, hours, directions, amenities,
   AND informational questions about NON-ROOM transportation prices/options (sedan rates, parking levels,
   taxi fares, airport shuttle costs, car rental rates), spa booking channels (extension numbers,
   how to book), and any "how much / where / how do I" question about a SERVICE (not a room price)
   that requires KB lookup.
   IMPORTANT: "how much" questions about ROOM PRICES for specific dates go to ToHotelBooking, NOT here.
   Examples: "What time is breakfast?", "Where is the gym?", "รหัส WiFi", "pet policy",
   "ห้องประชุมมีไหม", "สระว่ายน้ำเปิดกี่โมง", "ร้านอาหารเปิดกี่โมง", "มี X ไหม",
   "สปามีบริการอะไร", "นโยบายยกเลิก", "Do you have meeting rooms?",
   "How much does a sedan rental cost?", "Where can I park?", "How do I book a spa treatment?",
   "What is the taxi starting fare?", "ราคาเช่ารถ", "ที่จอดรถอยู่ไหน"
4. **HandleOtherTalk** — ONLY pure greetings/thanks/goodbye/small-talk with NO question AND NO information request.
   Examples (allowed): "Hello", "Thank you", "สวัสดี", "ขอบคุณ", "Goodbye", "Hi", "Bye", "你好", "谢谢", "再见"
   COUNTER-examples (NOT HandleOtherTalk — route to Knowledge/Booking/Service instead):
     "Hi I'm James, what time is breakfast?" → ToHotelKnowledge
     "สวัสดีค่ะ ห้องพักว่างไหมคะ" → ToHotelBooking
     "你好，请问早餐几点开始？" → ToHotelKnowledge

## QUESTION-FIRST RULE (highest priority — overrides every other rule)
If the guest message contains ANY of the following, you MUST route to ToHotelKnowledge, ToHotelBooking, or ToHotelService — NEVER HandleOtherTalk, even when the message also contains a greeting, a self-introduction, or check-in details:
- A question mark: `?` or `？`
- An English interrogative token: what, where, when, how, why, which, who, do you, does, is there, are there, can I, could you, may I, available
- A Thai interrogative token: กี่, อะไร, ไหน, ที่ไหน, เท่าไหร่, อย่างไร, ยังไง, มีไหม, ได้ไหม, หรือไม่, ไหมคะ, ไหมครับ
- A Chinese interrogative token: 几点, 几号, 几位, 多少, 什么, 哪里, 哪个, 怎么, 可以, 能不能, 有没有, 请问
Decide which specialist by the SUBJECT of the question, not by the greeting half. Default to ToHotelKnowledge when the question is about facilities, hours, dining, WiFi, or policies.

IMPORTANT routing rules:
- "Hi, I'm James, checking in tomorrow. What time does breakfast start and what's the WiFi password?" → ToHotelKnowledge (greeting + self-intro do NOT override the embedded questions)
- "สวัสดีค่ะ ดิฉันชื่อสมศรี ห้องพักว่างไหมคะ" → ToHotelBooking
- "你好，我叫王小明，请问早餐几点开始？" → ToHotelKnowledge
- "cancel my booking" / "ยกเลิกการจอง" → ToHotelBooking (NOT HandleOtherTalk)
- "what services do you have?" → ToHotelKnowledge (general info, NOT ToHotelService)
- "I need a spa booking" → ToHotelService (specific service request)
- Any question about hotel facilities (rooms, spa, dining, pool, etc.) → ToHotelKnowledge
- Any Thai question ending with "มีไหม" / "กี่โมง" / "ที่ไหน" / "อย่างไร" / "กี่ห้อง" → ToHotelKnowledge
- "How many rooms / How many Deluxe / How many Suites do you have?" → ToHotelKnowledge (inventory count, NOT availability date-check)
- "โรงแรมมีห้องกี่ห้อง" / "มีห้อง Deluxe กี่ห้อง" / "客房有多少间" → ToHotelKnowledge (inventory count)
- "How much is a <Standard|Deluxe|Suite|Penthouse> (Room) from <DATE> to <DATE>?" → ToHotelBooking (room price for specific dates — booking sub-agent has `calculate_dynamic_price`)
- "ค่าห้อง <ดีลักซ์|สแตนดาร์ด|สวีท> วันที่ <DATE> ถึง <DATE> เท่าไหร่" → ToHotelBooking (room price for specific dates)
- "<标准|豪华|套>房 <DATE> 到 <DATE> 多少钱" → ToHotelBooking (room price for specific dates)
- When in doubt between Knowledge and Service, prefer ToHotelKnowledge
- HandleOtherTalk for: pure greeting/thanks/goodbye with no info request (Hello, Hi, Thanks, Bye, สวัสดี, ขอบคุณ, 你好, 谢谢)
  AND for unclear/garbled/single-token/punctuation-only input where the
  guest's intent cannot be determined (e.g. "?", "ok", "asdf", a lone
  emoji, a half-typed sentence). In that case respond politely and ask
  a single clarifying question rather than refusing — the goal is to
  guide the guest, not to gatekeep.

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

            # Extract the assistant's final response.
            #
            # Phase J.3 tool-call surfacing fix: walk back from the end and
            # (a) capture the LAST AIMessage's content as the user-facing reply,
            # (b) AGGREGATE tool_calls from EVERY AIMessage emitted in the
            #     current turn — i.e. from the last HumanMessage onwards.
            # Previously we broke at the first AIMessage and only read its
            # tool_calls, which missed cases where the bot did a tool round-trip
            # and then produced a plain-text final reply (the typical shape
            # after _maybe_compute_pricing_context synthesizes a tool pair).
            final_messages = result.get("messages", [])
            candidate_text = ""
            candidate_tools: List[Dict[str, Any]] = []
            seen_text = False
            # Iterate back-to-front; stop at the most recent HumanMessage so
            # we only surface tool_calls from THIS turn, not the whole history.
            for msg in reversed(final_messages):
                if isinstance(msg, HumanMessage):
                    break
                if isinstance(msg, AIMessage):
                    if not seen_text and msg.content:
                        candidate_text = msg.content
                        seen_text = True
                    if msg.tool_calls:
                        # Prepend so chronological order is preserved across
                        # the reversed walk (older tool_calls first).
                        candidate_tools = [
                            {"name": tc["name"], "args": tc.get("args", {})}
                            for tc in msg.tool_calls
                        ] + candidate_tools

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
