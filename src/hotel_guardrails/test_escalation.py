# SPDX-FileCopyrightText: Copyright (c) 2024 Hotel AI Operations Assistant
# SPDX-License-Identifier: Apache-2.0
"""Unit tests for the adaptive-escalation runtime.

Coverage:
  * one test per pre-inference detector (positive + negative)
  * one test per post-check signal
  * mock-based test for cheap_judge (httpx mocked; prompt-shape + parsing)
  * mock-based test for maybe_escalate orchestration

No live OpenRouter calls in this file.
"""
from __future__ import annotations

import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from src.hotel_guardrails import escalation as esc


# ----------------------------------------------------------------------
# Helper: drive coroutines synchronously inside unittest
# ----------------------------------------------------------------------
def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ============================================================================
# Pre-inference detectors
# ============================================================================
class TestMultiTurnNoContext(unittest.TestCase):
    def test_positive_price_in_current_but_room_in_prior(self):
        prior = ["I'm looking at the Deluxe room for next Friday"]
        cur = "How much is it?"
        hit, ev = esc.detect_multi_turn_no_context(cur, prior)
        self.assertTrue(hit)
        self.assertIn("signal=", ev)

    def test_negative_entity_in_current_turn(self):
        cur = "How much is the Deluxe room?"
        hit, _ = esc.detect_multi_turn_no_context(cur, [])
        self.assertFalse(hit)

    def test_negative_no_signal(self):
        prior = ["I want a Deluxe room"]
        hit, _ = esc.detect_multi_turn_no_context("Sounds good, thanks!", prior)
        self.assertFalse(hit)


class TestMultilingualCodeSwitch(unittest.TestCase):
    def test_positive_en_plus_thai(self):
        # >=3 latin AND >=3 thai chars
        hit, ev = esc.detect_multilingual_code_switch(
            "Can I book ห้องดีลักซ์ please?"
        )
        self.assertTrue(hit)
        self.assertIn("en", ev)
        self.assertIn("th", ev)

    def test_negative_pure_english(self):
        hit, _ = esc.detect_multilingual_code_switch(
            "Can I book a Deluxe room please?"
        )
        self.assertFalse(hit)

    def test_negative_single_borrowed_word(self):
        # Penthouse borrowed into Thai sentence — only 8 latin chars, but the
        # rest is Thai. This is intentionally a positive (>=3 of each)
        # because the model still has to handle the script mix.
        text = "Penthouse"
        hit, _ = esc.detect_multilingual_code_switch(text)
        self.assertFalse(hit)


class TestNumericArithmetic(unittest.TestCase):
    def test_positive_total_keyword(self):
        hit, ev = esc.detect_numeric_arithmetic(
            "What's the total for 3 nights?"
        )
        self.assertTrue(hit)
        self.assertTrue(ev.startswith("en:"))

    def test_positive_thai_total(self):
        hit, ev = esc.detect_numeric_arithmetic("รวมทั้งหมดกี่บาท")
        self.assertTrue(hit)
        self.assertTrue(ev.startswith("th:"))

    def test_negative_simple_lookup(self):
        hit, _ = esc.detect_numeric_arithmetic("What's the room rate?")
        self.assertFalse(hit)


class TestRareEntity(unittest.TestCase):
    def test_positive_executive_chef(self):
        hit, ev = esc.detect_rare_entity(
            "Who is the executive chef at the hotel?"
        )
        self.assertTrue(hit)
        self.assertIn("kw=", ev)

    def test_negative_common_room_question(self):
        hit, _ = esc.detect_rare_entity("What's in the Deluxe room?")
        self.assertFalse(hit)


class TestPolicyConflict(unittest.TestCase):
    def test_positive_nonrefundable_cancel(self):
        hit, ev = esc.detect_policy_conflict(
            "I booked a non-refundable rate, can I cancel and get a refund?"
        )
        self.assertTrue(hit)
        self.assertTrue(ev.startswith("en:"))

    def test_negative_plain_cancellation_question(self):
        hit, _ = esc.detect_policy_conflict("What's your cancellation policy?")
        self.assertFalse(hit)


class TestPrecheckHardCase(unittest.TestCase):
    def test_aggregator_returns_flags(self):
        result = esc.precheck_hard_case(
            "What's the total for 3 nights?",
            prior_human_messages=[],
        )
        self.assertTrue(result["escalate"])
        self.assertIn("numeric_arithmetic", result["flags"])

    def test_aggregator_clean(self):
        result = esc.precheck_hard_case(
            "Hello",
            prior_human_messages=[],
        )
        self.assertFalse(result["escalate"])
        self.assertEqual(result["flags"], [])


# ============================================================================
# Post-inference signals
# ============================================================================
class TestPostSignals(unittest.TestCase):
    def test_empty_response_flag(self):
        d = esc.should_escalate_post(
            user_text="What time is check-in?",
            response_text="",
        )
        self.assertTrue(d.escalate)
        self.assertIn("empty_response", d.flags)

    def test_deferral_flag(self):
        d = esc.should_escalate_post(
            user_text="How many rooms?",
            response_text="I'm currently checking, please bear with me.",
        )
        self.assertTrue(d.escalate)
        self.assertIn("deferral", d.flags)

    def test_numeric_incoherence_flag(self):
        # 5000/night x 3 nights = 15000, but bot says total 20000.
        text = "The Deluxe is 5,000 THB / night. For 3 nights total = 20,000 THB."
        d = esc.should_escalate_post(
            user_text="What's the total for 3 nights at the Deluxe?",
            response_text=text,
        )
        self.assertIn("numeric_incoherence", d.flags)

    def test_numeric_coherent_does_not_flag(self):
        text = "The Deluxe is 5,000 THB / night. For 3 nights total = 15,000 THB."
        d = esc.should_escalate_post(
            user_text="What's the total for 3 nights at the Deluxe?",
            response_text=text,
        )
        self.assertNotIn("numeric_incoherence", d.flags)

    def test_expected_tool_not_called_flag(self):
        d = esc.should_escalate_post(
            user_text="Is the Deluxe available tomorrow?",
            response_text="Yes, it's available.",
            tool_calls=[],
            expected_tool_calls=["check_room_availability"],
        )
        self.assertIn("expected_tool_not_called", d.flags)

    def test_expected_tool_was_called_no_flag(self):
        d = esc.should_escalate_post(
            user_text="Is the Deluxe available tomorrow?",
            response_text="Yes, it's available.",
            tool_calls=[{"name": "check_room_availability", "args": {}}],
            expected_tool_calls=["check_room_availability"],
        )
        self.assertNotIn("expected_tool_not_called", d.flags)

    def test_response_too_short_for_multifact_question(self):
        d = esc.should_escalate_post(
            user_text="What are the pool hours and the gym hours please?",
            response_text="6 AM to 10 PM.",
        )
        self.assertIn("response_too_short_for_question", d.flags)

    def test_truncated_mid_sentence(self):
        long = "The Deluxe room features a king bed, ocean view, marble bathroom" * 4
        # Trim terminal punctuation
        long = long.rstrip(".!?") + " and"
        d = esc.should_escalate_post(
            user_text="Tell me about the Deluxe room",
            response_text=long,
        )
        self.assertIn("truncated_mid_sentence", d.flags)

    def test_clean_response_no_flags(self):
        d = esc.should_escalate_post(
            user_text="Hi",
            response_text="Hello! How can I help you today at The Grand Horizon?",
        )
        self.assertFalse(d.escalate)
        self.assertEqual(d.flags, [])

    def test_ambiguous_triggers_cheap_judge(self):
        # Long-ish question, short generic-looking reply, no tools called
        d = esc.should_escalate_post(
            user_text="Can you tell me what the wedding package includes for 50 guests?",
            response_text="Yes we offer wedding packages.",
            tool_calls=[],
        )
        self.assertTrue(d.needs_cheap_judge)
        self.assertFalse(d.escalate)


# ============================================================================
# Cheap-judge (mocked)
# ============================================================================
class TestCheapJudge(unittest.TestCase):
    def _make_mock_response(self, content: str):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json = MagicMock(
            return_value={"choices": [{"message": {"content": content}}]}
        )
        return mock_resp

    def test_verdict_ok_parsed(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                return_value=self._make_mock_response("ok")
            )
            with patch("httpx.AsyncClient", return_value=mock_client):
                verdict, latency = _run(
                    esc.cheap_judge("Q?", "A with specific facts at 6 AM")
                )
            self.assertEqual(verdict, "ok")
            self.assertGreaterEqual(latency, 0.0)
            # Verify prompt shape: model is gemma-3-4b-it, temperature 0, max_tokens 4
            call_kwargs = mock_client.post.call_args.kwargs
            payload = call_kwargs["json"]
            self.assertEqual(payload["model"], esc.CHEAP_JUDGE_MODEL)
            self.assertEqual(payload["max_tokens"], 4)
            self.assertEqual(payload["temperature"], 0.0)
            self.assertIn("Guest question: Q?", payload["messages"][0]["content"])

    def test_verdict_escalate_parsed(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(
                return_value=self._make_mock_response("escalate")
            )
            with patch("httpx.AsyncClient", return_value=mock_client):
                verdict, _ = _run(
                    esc.cheap_judge("Q?", "I'll get back to you.")
                )
            self.assertEqual(verdict, "escalate")

    def test_missing_key_returns_escalate(self):
        with patch.dict("os.environ", {}, clear=True):
            verdict, latency = _run(esc.cheap_judge("Q?", "A"))
            self.assertEqual(verdict, "escalate")
            self.assertEqual(latency, -1.0)

    def test_network_error_returns_escalate(self):
        with patch.dict("os.environ", {"OPENROUTER_API_KEY": "test-key"}):
            mock_client = MagicMock()
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(side_effect=RuntimeError("boom"))
            with patch("httpx.AsyncClient", return_value=mock_client):
                verdict, _ = _run(esc.cheap_judge("Q?", "A"))
            self.assertEqual(verdict, "escalate")


# ============================================================================
# maybe_escalate orchestration (mocked cloud call + log)
# ============================================================================
class TestMaybeEscalate(unittest.TestCase):
    def test_clean_no_escalation(self):
        async def _go():
            return await esc.maybe_escalate(
                state={"session_id": "s1"},
                user_text="Hi",
                response_text="Hello! How can I help you today?",
                tool_calls=[],
            )
        final, flags, meta = _run(_go())
        self.assertEqual(final, "Hello! How can I help you today?")
        self.assertEqual(flags, [])
        self.assertEqual(meta["source"], "local")

    def test_deferral_triggers_cloud(self):
        async def _call_cloud_stub(*args, **kwargs):
            return ("Cloud answer with facts.", 250, 0.0003)

        async def _log_stub(**kwargs):
            return None

        with patch.object(esc, "call_cloud_model", side_effect=_call_cloud_stub):
            with patch.object(esc, "_log_escalation", side_effect=_log_stub):
                async def _go():
                    return await esc.maybe_escalate(
                        state={"session_id": "s1"},
                        user_text="How many rooms total?",
                        response_text="I'm currently checking, please bear with me.",
                    )
                final, flags, meta = _run(_go())
        self.assertEqual(final, "Cloud answer with facts.")
        self.assertIn("deferral", flags)
        self.assertEqual(meta["source"], "cloud")
        self.assertEqual(meta["cloud_latency_ms"], 250)


if __name__ == "__main__":
    unittest.main()
