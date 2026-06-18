# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""
Adaptive-Escalation Runtime — hybrid local/cloud routing for the hotel chatbot.

This module implements the adaptive-escalation pattern described in CH6 §6.5.17
of the thesis. It is the runtime counterpart of the dual-backtest harness used
in the Phase J–M failure analysis. The goal is to keep the cheap, low-latency
local Gemma model on the hot path for the easy 80% of turns, and only spend
tokens on the strong remote model (google/gemma-4-31b-it via OpenRouter) on
the hard residual where local Gemma is known to fail.

Two decision layers
-------------------
1.  Pre-inference detector (``precheck_hard_case``)
    Runs BEFORE local inference. Catches five recurring failure modes
    identified in the Phase J–M backtests (multi-turn co-reference, multilingual
    code-switch, numeric-arithmetic asks, rare-entity asks, and policy-conflict
    asks). When any fires we skip the local pass entirely and short-circuit to
    the cloud — this avoids burning latency on a turn local cannot win.

2.  Post-inference composite scorer (``should_escalate_post``)
    Runs AFTER local inference. Aggregates deterministic quality flags (tool
    leak, language leak, numeric incoherence, deferral, empty reply, etc.) plus
    — when the deterministic flags are inconclusive — a cheap second-opinion
    judge (``cheap_judge``, google/gemma-3-4b-it @ ~$0.0001/call).

Main entry point
----------------
``maybe_escalate(state, user_text, response_text, tool_calls, retrieval_meta)``
glues the two layers together and, when the verdict is "escalate", calls the
strong cloud model and logs the decision to the ``escalations`` table for
later precision/recall analysis.

Backwards compatibility
-----------------------
The original sentiment-based ``EscalationMonitor`` class (used by ``server.py``
to suggest human-handover on frustration/repetition signals) is preserved
verbatim at the bottom of this file. The new adaptive-escalation functions live
in the top half. The two systems are independent: ``EscalationMonitor`` decides
whether to flag the conversation for staff, while ``maybe_escalate`` decides
whether to re-answer the turn with a stronger model.

Cross-refs
----------
* ``has_tool_leak``          – src/hotel_guardrails/hotel_langgraph.py L2492
* ``has_language_leak``      – src/hotel_guardrails/hotel_langgraph.py L2643
* ``detect_input_language``  – src/hotel_guardrails/hotel_langgraph.py L2625
* ``_detect_room_type``      – src/hotel_guardrails/hotel_langgraph.py L794
* ``_extract_dates``         – src/hotel_guardrails/hotel_langgraph.py L890
* ``_extract_relative_date`` – src/hotel_guardrails/hotel_langgraph.py L834
* ``_looks_like_deferral``   – ported from scripts/eval/backtest_runner.py L313
* ``_precheck_shortcircuit`` – scripts/eval/backtest_runner.py L330
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# SECTION 1 — Pre-inference hard-case detectors
# ============================================================================
#
# Each detector is a pure function: text -> (matched, evidence). Evidence is
# a short human-readable string used for logging and for the escalation-decision
# rubric in the eval harness. None of the detectors hit the network.

# Price / time signal tokens. EN anchored with word boundaries to avoid
# matching "discost"/"rated" inside other words.
_PRICE_TIME_EN = re.compile(
    r"\b(how\s+much|cost|costs|rate|rates|price|prices|"
    r"what\s+time|when\s+does|when\s+is)\b",
    re.IGNORECASE,
)
_PRICE_TIME_TH = re.compile(r"(ราคา|เท่าไหร่|เท่าไร|กี่บาท|กี่โมง)")
_PRICE_TIME_CN = re.compile(r"(价格|总价|多少钱|费用|几点)")


def _has_price_or_time_signal(text: str) -> Tuple[bool, str]:
    if not text:
        return False, ""
    m = _PRICE_TIME_EN.search(text)
    if m:
        return True, f"en:{m.group(1).lower()}"
    m = _PRICE_TIME_TH.search(text)
    if m:
        return True, f"th:{m.group(1)}"
    m = _PRICE_TIME_CN.search(text)
    if m:
        return True, f"cn:{m.group(1)}"
    return False, ""


def _safe_entity_probe(text: str) -> Tuple[bool, bool]:
    """Return (has_room_type, has_date) using the live hotel_langgraph helpers
    when importable, falling back to a lightweight inline detector otherwise.

    The fallback exists so the eval harness can import this module without
    pulling the full LangGraph dependency stack.
    """
    if not text:
        return False, False
    try:
        from src.hotel_guardrails.hotel_langgraph import (
            _detect_room_type,
            _extract_dates,
            _extract_relative_date,
        )
        room = _detect_room_type(text) is not None
        dates = bool(_extract_dates(text)) or bool(_extract_relative_date(text))
        return room, dates
    except Exception:
        # Lightweight fallback — keep tight, this is only used in tests.
        low = text.lower()
        room_kw = (
            "deluxe", "standard room", "suite", "penthouse",
            "ดีลักซ์", "สแตนดาร์ด", "สวีท", "เพนท์เฮาส์",
            "豪华", "标准", "套房", "顶层",
        )
        room = any(k in low for k in room_kw)
        date_re = re.compile(
            r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\b"
            r"|\b\d{1,2}\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)"
            r"|\d{1,2}\s*月\s*\d{1,2}"
            r"|tomorrow|tonight|today|next\s+(?:mon|tue|wed|thu|fri|sat|sun)"
            r"|พรุ่งนี้|วันนี้|มะรืน"
            r"|明天|今天|后天|下周",
            re.IGNORECASE,
        )
        return room, bool(date_re.search(text))


def detect_multi_turn_no_context(
    user_text: str, prior_human_messages: List[str]
) -> Tuple[bool, str]:
    """Current turn asks for price/time but contains no entity, while a prior
    human turn DOES contain the entity. Local Gemma loses this co-reference
    and re-asks the guest, breaking the human-chatting illusion.
    """
    has_signal, signal_evidence = _has_price_or_time_signal(user_text or "")
    if not has_signal:
        return False, ""

    cur_room, cur_dates = _safe_entity_probe(user_text or "")
    if cur_room or cur_dates:
        # Entity is present in the current turn — local can answer.
        return False, ""

    for prev in prior_human_messages or []:
        prev_room, prev_dates = _safe_entity_probe(prev or "")
        if prev_room or prev_dates:
            ev_parts = [f"signal={signal_evidence}"]
            if prev_room:
                ev_parts.append("prior_room")
            if prev_dates:
                ev_parts.append("prior_date")
            return True, ", ".join(ev_parts)
    return False, ""


# Code-switch detector: question contains substantive characters from two of
# (latin, thai, cjk). Single foreign words (e.g. "Penthouse" inside a Thai
# sentence) do not count — we require >= 3 chars of each script.
_LATIN_LETTER_RE = re.compile(r"[A-Za-z]")
_THAI_RE = re.compile(r"[฀-๿]")
_CJK_RE = re.compile(r"[一-鿿]")


def detect_multilingual_code_switch(user_text: str) -> Tuple[bool, str]:
    """User question mixes >= 2 scripts substantially. Local Gemma tends to
    pick one script and leak the other in its reply, or refuse outright.
    """
    if not user_text:
        return False, ""
    en = len(_LATIN_LETTER_RE.findall(user_text))
    th = len(_THAI_RE.findall(user_text))
    cn = len(_CJK_RE.findall(user_text))
    scripts = [("en", en), ("th", th), ("cn", cn)]
    substantial = [name for name, n in scripts if n >= 3]
    if len(substantial) >= 2:
        return True, "+".join(substantial)
    return False, ""


# Numeric-arithmetic patterns: questions that require the model to multiply
# / sum / divide. Local Gemma frequently emits per-night rates correctly but
# bungles the total. Cloud Gemma 4 31B is reliable on the arithmetic.
_NUMERIC_ARITHMETIC_EN = re.compile(
    r"\b(total|altogether|in\s+total|sum|how\s+many\s+nights|"
    r"average\s+per\s+night|per\s+night\s+for\s+\d+|"
    r"for\s+\d+\s+nights|for\s+\d+\s+people|for\s+\d+\s+guests|"
    r"\d+\s*\*\s*\d+|\d+\s*x\s*\d+|including\s+tax)\b",
    re.IGNORECASE,
)
_NUMERIC_ARITHMETIC_TH = re.compile(
    r"(รวม|ทั้งหมด|กี่คืน|กี่บาทรวม|รวมภาษี|เฉลี่ย)"
)
_NUMERIC_ARITHMETIC_CN = re.compile(
    r"(总共|总价|一共|平均|含税|多少晚|几晚|几个人)"
)


def detect_numeric_arithmetic(user_text: str) -> Tuple[bool, str]:
    """Question asks the model to do arithmetic across nights/guests/tax.
    Local Gemma's accuracy on > 2-operand arithmetic is ~62% in Phase L logs;
    cloud is ~98%. Short-circuit to cloud."""
    if not user_text:
        return False, ""
    m = _NUMERIC_ARITHMETIC_EN.search(user_text)
    if m:
        return True, f"en:{m.group(1).lower()}"
    m = _NUMERIC_ARITHMETIC_TH.search(user_text)
    if m:
        return True, f"th:{m.group(1)}"
    m = _NUMERIC_ARITHMETIC_CN.search(user_text)
    if m:
        return True, f"cn:{m.group(1)}"
    return False, ""


# Rare-entity asks: questions about facts that are NOT in the KB head 80%.
# Detected by named-entity keywords known to be sparse in the KB.
_RARE_ENTITY_KEYWORDS = (
    # Staff names (only the GM is in the KB; concierge/F&B aren't)
    "concierge name", "executive chef", "head sommelier", "spa manager",
    "front office manager", "rooms division",
    # Vendor / partner names
    "vendor", "supplier", "partner hotel", "airline partner",
    # Granular financial / capacity questions
    "occupancy rate", "adr ", "revpar", "tax id", "vat number",
    "company registration", "license number",
    # Granular property data sparse in KB
    "square meters", "square metres", "ceiling height", "fire exit",
    "evacuation plan",
    # TH rare
    "หมายเลขทะเบียน", "ผู้จัดการแผนก", "เชฟใหญ่",
    # CN rare
    "总经理姓名", "厨师长", "营业执照", "纳税人识别号",
)


def detect_rare_entity(user_text: str) -> Tuple[bool, str]:
    """Question asks for a fact that is empirically rare in the hotel KB.
    Local Gemma tends to hallucinate or defer; cloud is more likely to retrieve
    correctly or refuse cleanly."""
    if not user_text:
        return False, ""
    low = user_text.lower()
    for kw in _RARE_ENTITY_KEYWORDS:
        if kw in low or kw in user_text:
            return True, f"kw={kw[:24]}"
    return False, ""


# Policy-conflict patterns: questions that involve two policies that can
# contradict (e.g. early check-in + cancellation; pet policy + restaurant
# access; refund + non-refundable rate). Local Gemma quotes one policy and
# misses the conflict.
_POLICY_CONFLICT_EN = re.compile(
    r"\b(but\s+i\s+booked|but\s+the\s+(rate|policy)\s+says|"
    r"non[-\s]?refundable\b.*\b(cancel|refund|change)|"
    r"early\s+check[-\s]?in.*late\s+check[-\s]?out|"
    r"refund.*non[-\s]?refundable|"
    r"pet.*restaurant|service\s+animal.*pool|"
    r"prepaid.*cancel|advance\s+purchase.*cancel)\b",
    re.IGNORECASE,
)
_POLICY_CONFLICT_TH = re.compile(
    r"(แต่จองแบบ.*ยกเลิก|ไม่คืนเงิน.*ขอคืน|เช็คอินก่อน.*เช็คเอาท์หลัง)"
)
_POLICY_CONFLICT_CN = re.compile(
    r"(不可退.*取消|不退款.*退|提前入住.*延迟退房|预付.*取消)"
)


def detect_policy_conflict(user_text: str) -> Tuple[bool, str]:
    """Question pits two policies against each other. Local Gemma usually
    answers one side and misses the conflict; cloud reliably surfaces both."""
    if not user_text:
        return False, ""
    m = _POLICY_CONFLICT_EN.search(user_text)
    if m:
        return True, f"en:{m.group(0)[:32].lower()}"
    m = _POLICY_CONFLICT_TH.search(user_text)
    if m:
        return True, f"th:{m.group(0)[:32]}"
    m = _POLICY_CONFLICT_CN.search(user_text)
    if m:
        return True, f"cn:{m.group(0)[:32]}"
    return False, ""


# Public registry: name -> detector. Iterated by ``precheck_hard_case``.
PRE_INFERENCE_DETECTORS = {
    "multi_turn_no_context": detect_multi_turn_no_context,
    "multilingual_code_switch": detect_multilingual_code_switch,
    "numeric_arithmetic": detect_numeric_arithmetic,
    "rare_entity": detect_rare_entity,
    "policy_conflict": detect_policy_conflict,
}


def precheck_hard_case(
    user_text: str,
    prior_human_messages: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run all pre-inference detectors. Returns a dict:
        {
          "escalate":  bool,
          "flags":     [str, ...],   # detector names that matched
          "evidence":  {name: str},  # short evidence per matched detector
        }

    Callers should invoke this BEFORE local inference. If ``escalate`` is True,
    skip local and go straight to ``call_cloud_model``.
    """
    prior_human_messages = prior_human_messages or []
    flags: List[str] = []
    evidence: Dict[str, str] = {}
    for name, fn in PRE_INFERENCE_DETECTORS.items():
        try:
            if name == "multi_turn_no_context":
                hit, ev = fn(user_text, prior_human_messages)
            else:
                hit, ev = fn(user_text)
        except Exception as exc:
            logger.warning("pre-inference detector %s failed: %s", name, exc)
            continue
        if hit:
            flags.append(name)
            evidence[name] = ev
    return {
        "escalate": bool(flags),
        "flags": flags,
        "evidence": evidence,
    }


# ============================================================================
# SECTION 2 — Post-inference composite scorer
# ============================================================================
#
# Aggregates deterministic quality flags (cheaper than an LLM judge, ~ <2 ms
# per turn) into an EscalationDecision. The runtime decides whether to:
#   – surface a human-handover suggestion,
#   – re-answer with the stronger cloud model,
#   – attach a confidence badge for the UI.
#
# Ported from scripts/eval/backtest_runner.py L283-327 — the runtime cannot
# import from scripts/, so we keep a frozen copy here. Keep in sync when the
# eval-side list grows.

_DEFERRAL_PATTERNS: Tuple[str, ...] = (
    # EN
    "i am currently checking", "i'm currently checking",
    "let me check", "please bear with me", "currently retrieving",
    "i will provide", "i'll provide", "one moment please",
    "i don't have that information", "i do not have that information",
    "i don't have specific", "i do not have specific",
    "i don't have the exact", "i do not have the exact",
    "do not have information regarding", "no information regarding",
    "do not have specific information",
    "do not have the specific", "don't have the specific",
    "do not have the exact number", "don't have the exact number",
    "do not have the specific number", "don't have the specific number",
    "i apologize, but i do not have", "i apologize, but i don't have",
    "i do not have information regarding", "i don't have information regarding",
    "do not have the total number", "don't have the total number",
    "not have the specific information regarding",
    "not have information regarding the total",
    # TH
    "ขณะนี้กำลังตรวจสอบ", "ขอตรวจสอบข้อมูล", "กรุณารอสักครู่",
    "ไม่ได้ระบุไว้ในข้อมูล", "ไม่ได้ระบุไว้ในระบบ", "ไม่ได้ระบุ",
    "ดิฉันไม่มีข้อมูล", "ไม่มีข้อมูลจำนวน",
    "ทางเราไม่มีข้อมูล", "ไม่มีข้อมูลจำนวนห้อง", "ไม่มีข้อมูลห้องพัก",
)


def _looks_like_deferral(response: str) -> bool:
    """Ported from scripts/eval/backtest_runner.py L313."""
    if not response or len(response) > 600:
        if not response:
            return False
        head = response[:200].lower()
        if any(p in head for p in _DEFERRAL_PATTERNS) and not any(
            c.isdigit() for c in response
        ):
            return True
        return False
    low = response.lower()
    return any(p in low for p in _DEFERRAL_PATTERNS)


# ---------------------------------------------------------------------------
# Numeric coherence: per-night * nights ~ total within 1%
# ---------------------------------------------------------------------------
_PER_NIGHT_RE = re.compile(
    r"(\d{1,3}(?:,\d{3})*)\s*(?:THB|บาท|¥|CNY|/?\s*night)",
    re.IGNORECASE,
)
_NIGHTS_RE = re.compile(r"(\d{1,2})\s*(?:nights?|คืน|晚)", re.IGNORECASE)
_TOTAL_RE = re.compile(
    r"(?:total|รวม|总共|总价)\D{0,12}(\d{1,3}(?:,\d{3})*)",
    re.IGNORECASE,
)


def _has_numeric_incoherence(response: str) -> bool:
    """Best-effort check: response asserts per_night * nights = total, and the
    arithmetic is wrong by > 1%. False on responses where any of the three
    numbers can't be parsed (we can't prove incoherence, so don't flag)."""
    if not response:
        return False
    per_m = _PER_NIGHT_RE.search(response)
    n_m = _NIGHTS_RE.search(response)
    tot_m = _TOTAL_RE.search(response)
    if not (per_m and n_m and tot_m):
        return False
    try:
        per = int(per_m.group(1).replace(",", ""))
        nights = int(n_m.group(1))
        total = int(tot_m.group(1).replace(",", ""))
    except (ValueError, IndexError):
        return False
    if per <= 0 or nights <= 0 or total <= 0:
        return False
    expected = per * nights
    if expected == 0:
        return False
    drift = abs(total - expected) / expected
    return drift > 0.01


def _expected_tool_not_called(
    expected_tool_calls: Optional[List[str]],
    actual_tool_calls: Optional[List[Dict[str, Any]]],
) -> bool:
    """True if any expected tool name is absent from actual_tool_calls."""
    if not expected_tool_calls:
        return False
    actual_names = {
        (tc or {}).get("name") or (tc or {}).get("tool")
        for tc in (actual_tool_calls or [])
    }
    return not set(expected_tool_calls).issubset(actual_names)


_MULTI_FACT_RE = re.compile(
    r"\b(and|also|plus|as\s+well\s+as)\b|และ|以及|还有",
    re.IGNORECASE,
)


def _response_too_short_for_question(user_text: str, response: str) -> bool:
    """User asked a multi-fact question (has connector) but reply is < 100 chars."""
    if not user_text or not response:
        return False
    if not _MULTI_FACT_RE.search(user_text):
        return False
    return len(response.strip()) < 100


_TERMINAL_PUNCT = {".", "!", "?", "。", "！", "？", "”", "\"", ")", "]"}


def _truncated_mid_sentence(response: str) -> bool:
    """> 200 chars and no terminal punctuation in the last 3 chars."""
    if not response or len(response) <= 200:
        return False
    tail = response.rstrip()[-3:]
    return not any(ch in _TERMINAL_PUNCT for ch in tail)


@dataclass
class EscalationDecision:
    """Result of the post-inference composite scorer."""
    escalate: bool
    confidence: str               # "high", "medium", "low", "unknown"
    flags: List[str] = field(default_factory=list)
    needs_cheap_judge: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def should_escalate_post(
    user_text: str,
    response_text: str,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    expected_tool_calls: Optional[List[str]] = None,
) -> EscalationDecision:
    """Run all post-inference signals and aggregate.

    Returns an EscalationDecision. When ``needs_cheap_judge`` is True the caller
    should invoke ``cheap_judge`` for a tie-breaker before deciding.
    """
    flags: List[str] = []

    # Empty / too-short
    if not response_text or len(response_text.strip()) < 10:
        flags.append("empty_response")

    # Tool-call leak (lazy import — keeps eval-only importers happy)
    try:
        from src.hotel_guardrails.hotel_langgraph import (
            has_tool_leak,
            has_language_leak,
        )
        if response_text and has_tool_leak(response_text):
            flags.append("tool_leak")
        if user_text and response_text and has_language_leak(user_text, response_text):
            flags.append("language_leak")
    except Exception as exc:
        logger.debug("post-check helpers unavailable: %s", exc)

    if _looks_like_deferral(response_text or ""):
        flags.append("deferral")

    if _has_numeric_incoherence(response_text or ""):
        flags.append("numeric_incoherence")

    if _expected_tool_not_called(expected_tool_calls, tool_calls):
        flags.append("expected_tool_not_called")

    if _response_too_short_for_question(user_text or "", response_text or ""):
        flags.append("response_too_short_for_question")

    if _truncated_mid_sentence(response_text or ""):
        flags.append("truncated_mid_sentence")

    # Confidence rubric:
    #   2+ flags  -> high-confidence escalate
    #   1 flag    -> medium-confidence escalate
    #   0 flags + suspect signals (e.g. very short, no tool calls when one was
    #              expected) -> needs_cheap_judge
    #   0 flags + clean      -> no escalate
    if len(flags) >= 2:
        return EscalationDecision(
            escalate=True, confidence="high", flags=flags,
        )
    if len(flags) == 1:
        return EscalationDecision(
            escalate=True, confidence="medium", flags=flags,
        )

    # No deterministic flag fired — decide if a cheap-judge tie-breaker is
    # warranted. We ask the judge when the answer is short for a non-trivial
    # question (40+ chars) AND no tool calls were made.
    short_resp = bool(response_text) and len(response_text.strip()) < 80
    nontrivial_q = bool(user_text) and len(user_text.strip()) >= 40
    no_tools = not (tool_calls or [])
    if short_resp and nontrivial_q and no_tools:
        return EscalationDecision(
            escalate=False, confidence="low", flags=[], needs_cheap_judge=True,
        )

    return EscalationDecision(
        escalate=False, confidence="high", flags=[],
    )


# ============================================================================
# SECTION 3 — Cheap second-opinion judge (gemma-3-4b-it via OpenRouter)
# ============================================================================

CHEAP_JUDGE_PROMPT = """You are a quality auditor for a hotel chatbot.

Guest question: {question}

Bot answer: {response}

{expected_facts_block}

Does the bot's answer contain SPECIFIC FACTS (numbers, names, hours, addresses) that directly address the question? Or does it defer, give policy boilerplate, or change subject?

Respond with ONLY one word:
- "ok" if it answers with specific facts
- "escalate" if it defers, deflects, or misses the question

Word only, no punctuation, no explanation."""


CHEAP_JUDGE_MODEL = "google/gemma-3-4b-it"
CHEAP_JUDGE_URL = "https://openrouter.ai/api/v1/chat/completions"
CLOUD_ESCALATION_MODEL = "google/gemma-4-31b-it"


# ---------------------------------------------------------------------------
# Per-model prompt registry
# ---------------------------------------------------------------------------
# Each LLM the bot calls gets its OWN prompt yaml. Reusing one prompt across
# model families is a bug, not a simplification — Phase N (2026-06-18)
# confirmed empirically that replaying the local-tuned prompt against cloud
# Gemma 4 31B returned EMPTY content on 10/10 cases.
#
# Registry maps OpenRouter model_id -> yaml filename (under src/agent/).
_CLOUD_PROMPT_REGISTRY = {
    "google/gemma-4-31b-it":              "hotel_prompt_gemma4_31b_cloud.yaml",
    # Future entries (uncomment when escalation targets are added):
    # "qwen/qwen3-max":                     "hotel_prompt_qwen3_max_cloud.yaml",
    # "meta-llama/llama-3.3-70b-instruct":  "hotel_prompt_llama3_70b_cloud.yaml",
    # "mistralai/mistral-large-2512":       "hotel_prompt_mistral_large_cloud.yaml",
}

_CLOUD_PROMPT_CACHE: Dict[str, Dict[str, str]] = {}


def _load_prompt_for_model(model_id: str) -> Dict[str, str]:
    """Load the per-model cloud-escalation prompt yaml (cached).

    Returns a dict with at least key ``cloud_escalation_system`` and optionally
    ``cloud_escalation_pricing_addendum``. If no yaml is registered for the
    model, returns a minimal hard-coded fallback so the system never crashes.
    """
    if model_id in _CLOUD_PROMPT_CACHE:
        return _CLOUD_PROMPT_CACHE[model_id]

    fname = _CLOUD_PROMPT_REGISTRY.get(model_id)
    if not fname:
        logger.warning(
            "No cloud-escalation prompt registered for model %r — using hard-coded fallback",
            model_id,
        )
        loaded = {
            "cloud_escalation_system": (
                "You are a hotel concierge at The Grand Horizon Hotel. "
                "Answer the guest's question using only the FACTS below. "
                "Match the guest's language. Keep replies concise.\n\n"
                "FACTS:\n{kb_digest}\n\nPRIOR CONTEXT:\n{prior_context}"
            ),
        }
        _CLOUD_PROMPT_CACHE[model_id] = loaded
        return loaded

    try:
        import yaml
        repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        path = os.path.join(repo_root, "src", "agent", fname)
        with open(path, "r", encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
        if "cloud_escalation_system" not in loaded:
            raise ValueError(f"{fname} missing required key 'cloud_escalation_system'")
        _CLOUD_PROMPT_CACHE[model_id] = loaded
        logger.info("Loaded cloud-escalation prompt for %s from %s", model_id, fname)
        return loaded
    except Exception as exc:
        logger.error("Failed to load cloud-escalation prompt %s: %s", fname, exc)
        # Cache the fallback so we don't retry the disk read on every call
        fallback = {
            "cloud_escalation_system": (
                "You are a hotel concierge at The Grand Horizon Hotel. "
                "Answer the guest's question using only the FACTS below. "
                "Match the guest's language. Keep replies concise.\n\n"
                "FACTS:\n{kb_digest}\n\nPRIOR CONTEXT:\n{prior_context}"
            ),
        }
        _CLOUD_PROMPT_CACHE[model_id] = fallback
        return fallback


def _build_cloud_system_prompt(
    model_id: str,
    kb_digest: str = "",
    prior_context: str = "",
    is_pricing: bool = False,
) -> str:
    """Format the cloud-escalation system prompt for one turn.

    The caller passes a ``kb_digest`` (compact 1-2 KB of authoritative facts
    retrieved for this turn) and optional ``prior_context`` (the last 1-2
    HumanMessage texts). If ``is_pricing=True`` and the yaml has a pricing
    addendum, it's appended.
    """
    prompts = _load_prompt_for_model(model_id)
    system = prompts["cloud_escalation_system"]
    if is_pricing and "cloud_escalation_pricing_addendum" in prompts:
        system = system + "\n" + prompts["cloud_escalation_pricing_addendum"]
    return system.format(
        kb_digest=kb_digest or "(no specific facts retrieved for this turn)",
        prior_context=prior_context or "(this is the first turn of the session)",
    )


async def cheap_judge(
    question: str,
    response: str,
    expected_facts: Optional[List[str]] = None,
    timeout: float = 10.0,
) -> Tuple[str, float]:
    """Cheap second-opinion judge using google/gemma-3-4b-it via OpenRouter.

    Invoked when the composite scorer is ambiguous (e.g. 0 flags but the reply
    looks suspect). Returns ``(verdict, latency_seconds)`` with verdict in
    ``{"ok", "escalate"}``. Fail-safe: any error / timeout -> ``("escalate", -1)``.

    Cost per call: ~$0.0001 (50 in + 4 out tokens at $0.05/$0.10 per Mtok).
    Latency budget: ~200-500 ms typical.
    """
    expected_facts_block = (
        f"Expected facts the answer should cover: {expected_facts}"
        if expected_facts
        else ""
    )
    prompt = CHEAP_JUDGE_PROMPT.format(
        question=question,
        response=response,
        expected_facts_block=expected_facts_block,
    )

    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("cheap_judge: OPENROUTER_API_KEY not set, defaulting to escalate")
        return ("escalate", -1.0)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": CHEAP_JUDGE_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 4,
        "temperature": 0.0,
    }

    start = time.monotonic()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(CHEAP_JUDGE_URL, headers=headers, json=payload)
            latency = time.monotonic() - start
            resp.raise_for_status()
            data = resp.json()
            raw = data["choices"][0]["message"]["content"]
            verdict_raw = (raw or "").strip().lower()
            if verdict_raw.startswith("ok"):
                return ("ok", latency)
            return ("escalate", latency)
    except Exception as exc:
        logger.warning("cheap_judge failed (%s); defaulting to escalate", exc)
        return ("escalate", -1.0)


# ============================================================================
# SECTION 4 — Cloud-model call + DB logging + main entry point
# ============================================================================


async def call_cloud_model(
    user_text: str,
    system_prompt: Optional[str] = None,
    model_id: str = CLOUD_ESCALATION_MODEL,
    kb_digest: str = "",
    prior_context: str = "",
    is_pricing: bool = False,
    timeout: float = 30.0,
) -> Tuple[Optional[str], int, float]:
    """Call the strong cloud model (default google/gemma-4-31b-it via OpenRouter).

    The system prompt is selected by ``model_id`` from the per-model registry
    (_CLOUD_PROMPT_REGISTRY). Phase N (2026-06-18) proved that passing the
    local-tuned prompt to a different model family produces empty replies,
    so callers should normally let this function build the right prompt by
    passing ``kb_digest`` + ``prior_context`` instead of ``system_prompt``.

    Override path: if ``system_prompt`` is non-None, it replaces the per-model
    prompt verbatim. Use only for debugging / A-B tests.

    Returns ``(response_text, latency_ms, cost_usd)``. ``response_text`` is None
    on failure. Cost is a best-effort estimate based on OpenRouter pricing for
    google/gemma-4-31b-it (currently ~$0.12 / $0.35 per Mtok in/out).
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        logger.warning("call_cloud_model: OPENROUTER_API_KEY not set")
        return (None, 0, 0.0)

    # Default to the per-model prompt; explicit override wins.
    if system_prompt is None:
        system_prompt = _build_cloud_system_prompt(
            model_id=model_id,
            kb_digest=kb_digest,
            prior_context=prior_context,
            is_pricing=is_pricing,
        )

    messages: List[Dict[str, str]] = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_text})

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_id,
        "messages": messages,
        "temperature": 0.2,
    }

    start = time.monotonic()
    try:
        import httpx
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(CHEAP_JUDGE_URL, headers=headers, json=payload)
            latency_ms = int((time.monotonic() - start) * 1000)
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"]
            usage = data.get("usage") or {}
            prompt_tok = usage.get("prompt_tokens", 0)
            completion_tok = usage.get("completion_tokens", 0)
            cost_usd = (prompt_tok * 0.10 + completion_tok * 0.30) / 1_000_000
            return (text, latency_ms, cost_usd)
    except Exception as exc:
        logger.warning("call_cloud_model failed: %s", exc)
        return (None, int((time.monotonic() - start) * 1000), 0.0)


async def _log_escalation(
    *,
    session_id: str,
    user_id: Optional[str],
    turn_index: Optional[int],
    user_text: str,
    trigger_layer: str,         # 'pre' | 'post' | 'cheap_judge'
    trigger_flags: List[str],
    local_response: Optional[str],
    local_response_ms: Optional[int],
    cloud_response: str,
    cloud_response_ms: int,
    cloud_cost_usd: float,
    final_response_source: str,  # 'cloud' | 'local'
    final_response: str,
) -> None:
    """Insert one row into the escalations audit table. Best-effort: any DB
    failure is logged and swallowed so it cannot break the chat hot path."""
    try:
        from src.hotel_guardrails.database import get_cursor
        with get_cursor() as (cur, conn):
            cur.execute(
                """
                INSERT INTO escalations (
                    session_id, user_id, turn_index, user_text,
                    trigger_layer, trigger_flags,
                    local_response, local_response_ms,
                    cloud_response, cloud_response_ms, cloud_cost_usd,
                    cloud_model,
                    final_response_source, final_response
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s,
                    %s, %s
                )
                """,
                (
                    session_id, user_id, turn_index, user_text,
                    trigger_layer, trigger_flags,
                    local_response, local_response_ms,
                    cloud_response, cloud_response_ms, cloud_cost_usd,
                    CLOUD_ESCALATION_MODEL,
                    final_response_source, final_response,
                ),
            )
            conn.commit()
    except Exception as exc:
        logger.warning("_log_escalation failed (continuing): %s", exc)


async def maybe_escalate(
    state: Optional[Dict[str, Any]],
    user_text: str,
    response_text: str,
    tool_calls: Optional[List[Dict[str, Any]]] = None,
    retrieval_meta: Optional[Dict[str, Any]] = None,
) -> Tuple[str, List[str], Dict[str, Any]]:
    """Main post-inference entry point.

    1. Run ``should_escalate_post``.
    2. If verdict is ambiguous (``needs_cheap_judge``), call ``cheap_judge``.
    3. If escalate, call cloud model and return its response.
    4. Log the decision to the escalations table.

    Returns ``(final_response, flags, metadata)``. ``final_response`` is the
    text to surface to the guest (either the original local response, or the
    cloud override). ``flags`` is the list of trigger flags. ``metadata``
    carries timing / cost / source.
    """
    state = state or {}
    retrieval_meta = retrieval_meta or {}
    expected_tools = state.get("expected_tool_calls")
    session_id = str(state.get("session_id") or state.get("thread_id") or "unknown")
    user_id = state.get("user_id")
    turn_index = state.get("turn_index")

    metadata: Dict[str, Any] = {
        "source": "local",
        "trigger_layer": None,
        "cheap_judge_verdict": None,
        "cheap_judge_latency_s": None,
        "cloud_latency_ms": None,
        "cloud_cost_usd": None,
    }

    decision = should_escalate_post(
        user_text=user_text,
        response_text=response_text,
        tool_calls=tool_calls,
        expected_tool_calls=expected_tools,
    )
    flags = list(decision.flags)
    trigger_layer = "post" if decision.escalate else None

    # Pre-check override: if a hard-case pattern was detected upstream, force
    # escalation regardless of the post-check verdict. This handles cases the
    # post-check can't see — e.g. multi-turn anaphora where the local response
    # reads as coherent prose but quotes the wrong pricing tier.
    if state.get("force_escalate"):
        decision.escalate = True
        precheck_patterns = state.get("precheck_patterns") or []
        for p in precheck_patterns:
            tag = f"pre:{p}"
            if tag not in flags:
                flags.append(tag)
        if trigger_layer is None:
            trigger_layer = "pre"

    if decision.needs_cheap_judge and not decision.escalate:
        verdict, latency = await cheap_judge(
            question=user_text,
            response=response_text,
            expected_facts=retrieval_meta.get("expected_facts"),
        )
        metadata["cheap_judge_verdict"] = verdict
        metadata["cheap_judge_latency_s"] = latency
        if verdict == "escalate":
            decision.escalate = True
            flags.append("cheap_judge_escalate")
            trigger_layer = "cheap_judge"

    if not decision.escalate:
        metadata["source"] = "local"
        metadata["trigger_layer"] = None
        return response_text, flags, metadata

    # Escalate to cloud — use the per-model prompt, NOT the bot's local
    # system_prompt (Phase N 2026-06-18 proved that pass-through breaks the
    # cloud model). The caller is expected to pre-populate state with the
    # KB digest + prior-turn context the cloud model needs.
    kb_digest = state.get("cloud_kb_digest", "")
    prior_context = state.get("cloud_prior_context", "")
    is_pricing = "pricing" in (state.get("current_intent") or "").lower() or any(
        "pricing" in f or "tool_not_called" in f for f in flags
    )
    cloud_text, cloud_ms, cloud_cost = await call_cloud_model(
        user_text=user_text,
        kb_digest=kb_digest,
        prior_context=prior_context,
        is_pricing=is_pricing,
    )
    metadata["cloud_latency_ms"] = cloud_ms
    metadata["cloud_cost_usd"] = cloud_cost
    metadata["trigger_layer"] = trigger_layer

    if not cloud_text:
        # Cloud failed -> fall back to local response, but keep the flags
        # so the UI can still surface a confidence badge.
        metadata["source"] = "local_cloud_failed"
        return response_text, flags, metadata

    metadata["source"] = "cloud"

    # Log (best effort, async-safe)
    await _log_escalation(
        session_id=session_id,
        user_id=str(user_id) if user_id is not None else None,
        turn_index=turn_index,
        user_text=user_text,
        trigger_layer=trigger_layer or "post",
        trigger_flags=flags,
        local_response=response_text,
        local_response_ms=state.get("local_response_ms"),
        cloud_response=cloud_text,
        cloud_response_ms=cloud_ms,
        cloud_cost_usd=cloud_cost,
        final_response_source="cloud",
        final_response=cloud_text,
    )

    return cloud_text, flags, metadata


# ============================================================================
# SECTION 5 — Legacy sentiment-based EscalationMonitor (preserved verbatim)
# ============================================================================
#
# The original frustration / repetition / high-value detector. Imported by
# ``server.py`` to decide whether to suggest a human handover. Kept here for
# backwards compatibility with the existing call site; orthogonal to the
# adaptive-escalation runtime above.

# Frustration signals — keywords that indicate the guest needs human help
FRUSTRATION_EN = [
    "speak to manager", "talk to a real person", "human agent",
    "this is ridiculous", "terrible service", "unacceptable",
    "worst hotel", "never coming back", "i want to complain",
    "complaint", "very upset", "extremely disappointed",
    "not working", "useless bot", "stupid bot",
]

FRUSTRATION_TH = [
    "ขอพูดกับผู้จัดการ", "ต้องการคุยกับคน", "ร้องเรียน",
    "แย่มาก", "ยอมรับไม่ได้", "ผิดหวังมาก", "โกรธ",
    "ไม่พอใจ", "เลวร้าย", "บอทไม่เก่ง", "ช่วยอะไรไม่ได้",
]

HIGH_VALUE_THRESHOLD = 50_000  # THB
HIGH_VALUE_ROOM_TYPES = {"penthouse"}
REPETITION_SIMILARITY = 0.7
REPETITION_COUNT = 3
MAX_HISTORY = 10


class EscalationMonitor:
    """Monitors conversations for auto-escalation triggers."""

    def __init__(self):
        # session_id -> deque of recent user messages
        self._session_messages: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=MAX_HISTORY)
        )

    def check_sentiment(self, message: str) -> Tuple[bool, str]:
        """Check for frustration/escalation keywords in Thai + English."""
        msg_lower = message.lower()

        for phrase in FRUSTRATION_EN:
            if phrase in msg_lower:
                return True, f"Frustrated guest (EN): '{phrase}'"

        for phrase in FRUSTRATION_TH:
            if phrase in message:
                return True, f"Frustrated guest (TH): '{phrase}'"

        return False, ""

    def check_repetition(self, session_id: str, message: str) -> Tuple[bool, str]:
        """Detect if guest is repeating the same question (bot failing)."""
        history = self._session_messages[session_id]
        history.append(message)

        if len(history) < REPETITION_COUNT:
            return False, ""

        # Count how many recent messages are similar to the current one
        similar_count = 0
        for prev in list(history)[:-1]:
            ratio = SequenceMatcher(None, message.lower(), prev.lower()).ratio()
            if ratio > REPETITION_SIMILARITY:
                similar_count += 1

        if similar_count >= REPETITION_COUNT - 1:
            return True, f"Guest repeated similar question {similar_count + 1} times"

        return False, ""

    def check_high_value(self, context: Optional[Dict]) -> Tuple[bool, str]:
        """Flag high-value bookings that may need personal attention."""
        if not context:
            return False, ""

        response = context.get("response", "")
        tool_calls = context.get("tool_calls") or []

        # Check for Penthouse mentions
        resp_lower = response.lower()
        if "penthouse" in resp_lower:
            return True, "High-value: Penthouse room inquiry"

        # Check tool call results for high amounts
        for tc in tool_calls:
            args = tc.get("args", {})
            if "total_amount" in str(args) or "penthouse" in str(args).lower():
                return True, "High-value: Premium booking detected"

        # Check response text for large amounts (rough heuristic)
        amounts = re.findall(r"(\d{1,3}(?:,\d{3})*)\s*(?:THB|บาท)", response)
        for amt_str in amounts:
            amt = int(amt_str.replace(",", ""))
            if amt >= HIGH_VALUE_THRESHOLD:
                return True, f"High-value: {amt:,} THB booking"

        return False, ""

    def should_escalate(
        self,
        session_id: str,
        message: str,
        context: Optional[Dict] = None,
    ) -> Tuple[bool, str, str]:
        """
        Check all escalation triggers.

        Returns:
            (should_escalate, reason, priority)
            priority: "high", "medium", "low"
        """
        # Sentiment (highest priority)
        triggered, reason = self.check_sentiment(message)
        if triggered:
            return True, reason, "high"

        # Repetition (high priority — bot is failing)
        triggered, reason = self.check_repetition(session_id, message)
        if triggered:
            return True, reason, "high"

        # High-value (medium priority — FYI for staff)
        triggered, reason = self.check_high_value(context)
        if triggered:
            return True, reason, "medium"

        return False, "", ""
