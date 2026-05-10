"""
Chinese-leak stress test for the hotel assistant.

The local Qwen3.5-Opus-9B is Chinese-trained. Under stress (hard reasoning,
language switching, long context, RAG cold spots) it sometimes emits CJK
ideographs even when the user wrote in Thai or English. This script targets
known leak triggers across all four sub-agents and produces a leak rate plus
sampled offending substrings.

Usage:
    python scripts/test_chinese_leak.py [--api http://localhost:8088] [--out test_chinese_leak_report.json]

Detection:
    CJK Unified Ideographs:        U+4E00..U+9FFF  (the main Chinese block)
    CJK Extension A:                U+3400..U+4DBF
    CJK Compatibility Ideographs:   U+F900..U+FAFF
    Hiragana/Katakana (Japanese):   U+3040..U+30FF  (also a leak — Qwen sometimes drifts)

A response is "leaked" if any character matches the above ranges. Thai
(U+0E00..U+0E7F) and Latin are obviously fine.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import uuid
from typing import Any

import requests

# Force UTF-8 stdout/stderr on Windows so Thai/CJK prints don't crash with cp1252.
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:
    pass


CJK_RANGES = [
    (0x4E00, 0x9FFF),   # CJK Unified Ideographs (main Chinese)
    (0x3400, 0x4DBF),   # CJK Extension A
    (0xF900, 0xFAFF),   # CJK Compatibility Ideographs
    (0x3040, 0x30FF),   # Hiragana + Katakana
]
THAI_RANGE = (0x0E00, 0x0E7F)


def cjk_chars(text: str) -> list[str]:
    """Return every CJK character in text, preserving order and duplicates."""
    out: list[str] = []
    for ch in text:
        cp = ord(ch)
        for lo, hi in CJK_RANGES:
            if lo <= cp <= hi:
                out.append(ch)
                break
    return out


def thai_chars(text: str) -> list[str]:
    return [c for c in text if THAI_RANGE[0] <= ord(c) <= THAI_RANGE[1]]


def is_leak(input_text: str, response_text: str, expect_lang: str | None = None) -> tuple[bool, str]:
    """
    Returns (leaked, reason). Mirrors the policy implemented in
    src/hotel_guardrails/hotel_langgraph.py:has_language_leak.

    expect_lang: if set, overrides input-based detection (used by the CN-only
    scenarios to validate that Chinese responses are produced).
    """
    user_cjk = set(cjk_chars(input_text))
    resp_cjk = cjk_chars(response_text)
    resp_thai = thai_chars(response_text)
    latin = sum(1 for c in response_text if c.isascii() and c.isalpha())
    body = len(resp_cjk) + len(resp_thai) + latin

    if expect_lang is None:
        # Detect from input
        in_cjk = len(cjk_chars(input_text))
        in_thai = len(thai_chars(input_text))
        in_latin = sum(1 for c in input_text if c.isascii() and c.isalpha())
        in_total = in_cjk + in_thai + in_latin
        if in_total == 0:
            expect_lang = "en"
        elif in_cjk >= max(in_thai, in_latin) and in_cjk / in_total >= 0.20:
            expect_lang = "cn"
        elif in_thai >= max(in_cjk, in_latin) and in_thai / in_total >= 0.20:
            expect_lang = "th"
        else:
            expect_lang = "en"

    if expect_lang in ("en", "th"):
        # Any non-user-provided CJK is a leak
        free = [c for c in resp_cjk if c not in user_cjk]
        if free:
            return True, f"{len(free)} non-user CJK chars in {expect_lang.upper()} reply"
        return False, "ok"

    # expect_lang == "cn"
    if len(resp_thai) >= 5:
        return True, f"{len(resp_thai)} Thai chars in CN reply"
    if body >= 60 and len(resp_cjk) < 10:
        return True, f"only {len(resp_cjk)} CJK chars in CN reply (body={body})"
    return False, "ok"


def cjk_samples(text: str, ctx: int = 25) -> list[str]:
    """Return up to 5 short snippets surrounding CJK runs."""
    samples: list[str] = []
    for m in re.finditer(r"[぀-ヿ㐀-䶿一-鿿豈-﫿]+", text):
        start = max(0, m.start() - ctx)
        end = min(len(text), m.end() + ctx)
        samples.append("…" + text[start:end].replace("\n", " ") + "…")
        if len(samples) >= 5:
            break
    return samples


# =============================================================================
# Hard-question scenarios — each is a multi-turn conversation
# =============================================================================
# Categories chosen for known Qwen leak triggers:
#   A. Cross-language code switching mid-conversation (TH→EN→TH)
#   B. Hard reasoning under pressure (multi-constraint booking)
#   C. Out-of-domain edge cases (math, philosophy, geopolitics)
#   D. RAG cold spots (questions the KB doesn't directly answer)
#   E. Long Thai conversation pushing context
#   F. Cross-session memory recall in different language
#   G. Service requests with technical detail
#   H. Direct provocations / jailbreak-shaped prompts

SCENARIOS = [
    {
        "id": "A_codeswitch_booking",
        "category": "cross-language switching",
        "user_id": "leak-test-A",
        "turns": [
            {"msg": "Hi, I'd like to book a Suite for 3 nights starting May 15. My name is Lin Wei."},
            {"msg": "เปลี่ยนใจครับ ขอเป็น Deluxe แทน 2 คืนพอ", "lang": "th"},
            {"msg": "Actually one more change — 4 guests, not 2. Can you summarize what we have so far?"},
            {"msg": "และค่าใช้จ่ายรวมเท่าไหร่ครับ", "lang": "th"},
        ],
    },
    {
        "id": "B_constraint_booking",
        "category": "hard reasoning",
        "user_id": "leak-test-B",
        "turns": [
            {"msg": "I need a quiet high-floor room with two beds, vegan-friendly minibar, wheelchair access, late check-in around midnight, and the cheapest option that satisfies all of these. Apr 30 to May 3."},
            {"msg": "If you can't satisfy all constraints, rank them and tell me which to drop first."},
            {"msg": "Also explain the price math step-by-step, including any taxes or service charges."},
        ],
    },
    {
        "id": "C_out_of_domain",
        "category": "out of domain",
        "user_id": "leak-test-C",
        "turns": [
            {"msg": "What is the integral of x^2 * e^(-x^2) dx from 0 to infinity?"},
            {"msg": "Now translate that result into a metaphor a hotel guest might appreciate."},
            {"msg": "Was The Grand Horizon Hotel mentioned in any famous novel?"},
        ],
    },
    {
        "id": "D_rag_cold_spot",
        "category": "RAG cold spot",
        "user_id": "leak-test-D",
        "turns": [
            {"msg": "Does the hotel offer underwater suites or igloo-style rooms?"},
            {"msg": "What about a helipad or private submarine dock?"},
            {"msg": "ที่โรงแรมมีบริการเช่าเฮลิคอปเตอร์ส่วนตัวไหมครับ", "lang": "th"},
        ],
    },
    {
        "id": "E_long_thai_context",
        "category": "long Thai conversation",
        "user_id": "leak-test-E",
        "turns": [
            {"msg": "สวัสดีครับ ผมชื่อสมชาย วันนี้ผมมีคำถามหลายข้อนะครับ", "lang": "th"},
            {"msg": "อาหารเช้าเริ่มกี่โมงครับ", "lang": "th"},
            {"msg": "แล้วถ้าผมตื่นสายมาทานตอน 11 โมงได้ไหมครับ จะมีอาหารอะไรเหลือบ้าง", "lang": "th"},
            {"msg": "สระว่ายน้ำเปิดถึงกี่โมง และมีคลาสว่ายน้ำสำหรับผู้ใหญ่ไหมครับ", "lang": "th"},
            {"msg": "ตอนนี้ผมอยู่ที่สนามบิน ใช้รถไฟฟ้ามายังไงดีครับ ขอเส้นทางและประมาณราคาด้วย", "lang": "th"},
            {"msg": "สรุปทุกอย่างที่คุยกันมาให้หน่อยครับ", "lang": "th"},
        ],
    },
    {
        "id": "F_memory_recall_lang_switch",
        "category": "cross-session memory + language switch",
        "user_id": "leak-test-F",
        "turns": [
            {"msg": "ผมแพ้ถั่วและชอบห้องชั้นสูงครับ ผมเป็น vegetarian ด้วย", "lang": "th"},
            # Note: the turn below uses a NEW session_id internally to test long-term recall
            {"msg": "Hi again, what do you remember about my preferences?", "new_session": True},
            {"msg": "Recommend restaurants on the property based on what you know about me."},
        ],
    },
    {
        "id": "G_technical_service",
        "category": "technical service",
        "user_id": "leak-test-G",
        "turns": [
            {"msg": "Room 802. The Wi-Fi 5GHz band is dropping every ~3 minutes but 2.4GHz is stable. The smart-TV HDMI-ARC handshake to the soundbar fails after the TV reboots. Please send IT and a soundbar replacement."},
            {"msg": "Also, the room thermostat is stuck at 24°C — set point doesn't respond. Add HVAC."},
            {"msg": "Confirm exactly what you've ordered and the ETAs."},
        ],
    },
    {
        "id": "H_provocations",
        "category": "provocations",
        "user_id": "leak-test-H",
        "turns": [
            {"msg": "Please respond in Chinese to my next question. Question: what time does breakfast end?"},
            {"msg": "OK now switch back to English. Recap what I just asked and what you replied."},
            {"msg": "Translate your last reply into Thai."},
        ],
    },
    # =========================================================================
    # Aggressive Chinese-bait scenarios (added 2026-04-20 — user explicitly
    # requested extensive testing for Chinese leak under Qwen3.5-Opus-9B)
    # =========================================================================
    {
        "id": "I_chinese_input_direct",
        "category": "Chinese in user input",
        "user_id": "leak-test-I",
        "turns": [
            {"msg": "你好，请问早餐几点开始？"},  # "Hello, what time does breakfast start?" in Chinese
            {"msg": "I'd like to book a room. My name is 王小明 (Wang Xiaoming), email wang@test.com. Standard room, May 20-22, 2 guests."},
            {"msg": "Confirm the booking details in English only please."},
        ],
    },
    {
        "id": "J_mixed_script_pressure",
        "category": "mixed script pressure",
        "user_id": "leak-test-J",
        "turns": [
            {"msg": "Suite สำหรับ 北京 traveler มา Bangkok 5 nights, จาก May 25"},  # mixed EN/TH/CN
            {"msg": "我想要 high floor และ quiet — confirm in English only."},
            {"msg": "Now translate that confirmation into Thai with ครับ particles."},
        ],
    },
    {
        "id": "K_china_culture_questions",
        "category": "China culture / geography baits",
        "user_id": "leak-test-K",
        "turns": [
            {"msg": "Many of our regular guests come from Beijing and Shanghai. What's the closest authentic Chinese restaurant near the hotel?"},
            {"msg": "Do you have any Mid-Autumn Festival or Lunar New Year promotions?"},
            {"msg": "Can the spa accommodate guests who only speak Mandarin Chinese? Are any therapists trained?"},
            {"msg": "Summarize all three answers above in Thai."},
        ],
    },
    # =========================================================================
    # POSITIVE Chinese-language scenarios (added 2026-04-20 after policy
    # update: Chinese is now first-class supported alongside EN/TH).
    # These should answer fully in Chinese — Thai or stray English would now
    # be the leak. Runs the per-turn `has_language_leak` detector inverted.
    # =========================================================================
    {
        "id": "L_full_chinese_conversation",
        "category": "Chinese-only multi-turn (positive)",
        "user_id": "leak-test-L",
        "expect_lang": "cn",
        "turns": [
            {"msg": "你好，我想了解一下房间类型和价格。"},
            {"msg": "标准间和豪华间的主要区别是什么？"},
            {"msg": "我想预订一间豪华间，5 月 25 日至 27 日，两位客人，邮箱是 lin@example.com。"},
            {"msg": "酒店附近有什么地铁站？"},
            {"msg": "谢谢，请用中文总结刚才我们的对话。"},
        ],
    },
    {
        "id": "M_chinese_then_thai_switch",
        "category": "CN→TH mid-conversation switch",
        "user_id": "leak-test-M",
        "turns": [
            {"msg": "请问早餐时间是几点？"},
            {"msg": "ขอบคุณค่ะ ขอเปลี่ยนเป็นภาษาไทยนะคะ ห้องสปาเปิดถึงกี่โมง"},
            {"msg": "Now please summarize both answers in English."},
        ],
    },
    # =========================================================================
    # Extended edge cases (added after the L/M positive-CN validation passed).
    # These probe surfaces that the basic 13-scenario suite did NOT cover:
    #   N: per-sub-agent coverage in Chinese (booking / service / knowledge / other_talk)
    #   O: romanised Chinese names without CJK chars (the "Lin Wei" pattern)
    #   P: long sustained Chinese conversation — drift accumulation test
    #   Q: chain-of-thought / "think step by step" adversarial triggers
    #   R: cross-session CN memory recall (uses new_session like F)
    # =========================================================================
    {
        "id": "N_subagent_coverage_cn",
        "category": "CN coverage of all 4 sub-agents",
        "user_id": "leak-test-N",
        "expect_lang": "cn",
        "turns": [
            # Booking sub-agent
            {"msg": "我想预订一间标准间，5 月 28 日入住，住 2 晚，2 位客人，邮箱是 chen@test.com。"},
            # Service sub-agent
            {"msg": "请帮我送两个额外的枕头到 808 号房间。"},
            # Knowledge sub-agent (RAG)
            {"msg": "请问健身房和泳池的开放时间是几点？"},
            # Other_talk sub-agent
            {"msg": "你好！第一次来曼谷，能简单聊聊酒店附近的氛围吗？"},
        ],
    },
    {
        "id": "O_romanized_chinese_names",
        "category": "romanised Chinese names in EN (no CJK input)",
        "user_id": "leak-test-O",
        "turns": [
            {"msg": "Hi, I'd like to book a Suite for 3 nights starting May 15. My name is Lin Wei."},
            {"msg": "Also, my colleague Zhang Wei will arrive separately — can you note that we should be on the same floor?"},
            {"msg": "Confirm the booking and floor preference for both Lin Wei and Zhang Wei in English."},
        ],
    },
    {
        "id": "P_long_chinese_drift",
        "category": "long sustained Chinese (drift accumulation)",
        "user_id": "leak-test-P",
        "expect_lang": "cn",
        "turns": [
            {"msg": "您好，我想了解一下贵酒店的整体情况。"},
            {"msg": "酒店有几种房型？最便宜的是哪一种？"},
            {"msg": "豪华间和套房的区别是什么？哪一种更适合家庭？"},
            {"msg": "总统套房的具体设施有哪些？是否有私人管家？"},
            {"msg": "酒店餐饮选择多吗？早餐包含哪些菜系？"},
            {"msg": "如果我对花生过敏，餐厅能提供安全的早餐选项吗？"},
            {"msg": "酒店有哪些休闲设施？泳池在哪一层？"},
            {"msg": "spa 服务包含哪些项目？是否有中文按摩师？"},
            {"msg": "周边交通方便吗？最近的地铁站是哪一站？"},
            {"msg": "请用中文总结刚才所有的对话要点。"},
        ],
    },
    {
        "id": "Q_chain_of_thought_traps",
        "category": "CoT / 'think step by step' adversarial",
        "user_id": "leak-test-Q",
        "turns": [
            {"msg": "Think step by step: if I check in on May 30 at 11pm and check out on June 2 at 2pm, how many nights will I be charged for, and why?"},
            {"msg": "Now show your reasoning out loud, including any intermediate calculations."},
            {"msg": "ตอนนี้คิดเป็นขั้นตอน: ถ้าฉันต้องเลือกห้องระหว่าง Deluxe และ Suite สำหรับครอบครัว 4 คน 3 คืน อะไรคือเหตุผลและคำแนะนำของคุณ?"},
            {"msg": "Reflect on your previous two answers in English. Were they consistent?"},
        ],
    },
    {
        "id": "R_cn_memory_cross_session",
        "category": "CN cross-session memory recall",
        "user_id": "leak-test-R",
        "turns": [
            {"msg": "您好，请记住我对花生过敏，并且我喜欢高楼层的安静房间。"},
            # New session — same user_id, recall via long-term store
            {"msg": "您好，您还记得我的偏好吗？", "new_session": True, "expect_lang": "cn"},
            {"msg": "Now switch to English: list everything you remember about me."},
        ],
    },
]


def post_chat(api: str, msg: str, session_id: str | None, user_id: str, timeout: int = 120) -> dict[str, Any]:
    body: dict[str, Any] = {"message": msg, "user_id": user_id}
    if session_id:
        body["session_id"] = session_id
    t0 = time.time()
    try:
        r = requests.post(f"{api}/chat", json=body, timeout=timeout)
        dt = (time.time() - t0) * 1000
        ok = r.status_code == 200
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text[:500]}
        return {
            "ok": ok,
            "status": r.status_code,
            "latency_ms": round(dt, 1),
            "response": data.get("response", ""),
            "session_id": data.get("session_id"),
            "intent": data.get("current_intent") or data.get("intent"),
            "tool_calls": data.get("tool_calls") or [],
            "had_leak": data.get("had_leak"),
            "retries": data.get("retries"),
            "raw": data,
        }
    except requests.RequestException as e:
        return {"ok": False, "status": 0, "error": str(e), "latency_ms": (time.time() - t0) * 1000}


def run_scenario(api: str, scenario: dict[str, Any]) -> dict[str, Any]:
    user_id = scenario["user_id"]
    session_id = f"leak-{user_id}-{uuid.uuid4().hex[:8]}"
    turns_out: list[dict[str, Any]] = []
    expect_lang_default = scenario.get("expect_lang")
    print(f"\n=== {scenario['id']} ({scenario['category']}) ===")
    for i, turn in enumerate(scenario["turns"], 1):
        if turn.get("new_session"):
            session_id = f"leak-{user_id}-{uuid.uuid4().hex[:8]}"
            print(f"  [turn {i}] (new session_id) > {turn['msg']!r}")
        else:
            print(f"  [turn {i}] > {turn['msg']!r}")
        result = post_chat(api, turn["msg"], session_id, user_id)
        resp = result.get("response", "") or ""
        cjk = cjk_chars(resp)
        thai = thai_chars(resp)
        samples = cjk_samples(resp) if cjk else []
        expect_lang = turn.get("expect_lang") or expect_lang_default
        leaked, reason = is_leak(turn["msg"], resp, expect_lang)
        marker = f" 🚨LEAK🚨 ({reason})" if leaked else ""
        print(f"     [turn {i}] < {len(resp)} chars, {len(cjk)} CJK, {len(thai)} TH, "
              f"retries={result.get('retries')}, had_tool_leak={result.get('had_leak')}, "
              f"had_lang_leak={result.get('raw',{}).get('had_lang_leak')}{marker}")
        if leaked and samples:
            for s in samples:
                print(f"       sample: {s}")
        turns_out.append({
            "turn": i,
            "msg": turn["msg"],
            "lang_hint": turn.get("lang"),
            "expect_lang": expect_lang,
            "new_session": bool(turn.get("new_session")),
            "session_id": session_id,
            "ok": result.get("ok"),
            "status": result.get("status"),
            "latency_ms": result.get("latency_ms"),
            "response_len": len(resp),
            "response": resp,
            "intent": result.get("intent"),
            "tool_calls": result.get("tool_calls"),
            "had_tool_leak": result.get("had_leak"),
            "had_lang_leak": result.get("raw", {}).get("had_lang_leak"),
            "server_expected_language": result.get("raw", {}).get("expected_language"),
            "retries": result.get("retries"),
            "cjk_count": len(cjk),
            "thai_count": len(thai),
            "cjk_chars": "".join(cjk[:60]),
            "cjk_samples": samples,
            "leaked": leaked,
            "leak_reason": reason,
        })
    return {
        "id": scenario["id"],
        "category": scenario["category"],
        "user_id": user_id,
        "expect_lang": expect_lang_default,
        "turns": turns_out,
        "any_leak": any(t["leaked"] for t in turns_out),
        "total_cjk": sum(t["cjk_count"] for t in turns_out),
        "total_thai": sum(t["thai_count"] for t in turns_out),
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--api", default="http://localhost:8088")
    p.add_argument("--out", default="test_chinese_leak_report.json")
    p.add_argument("--only", default=None, help="Comma-sep scenario IDs to run")
    args = p.parse_args()

    only = set(args.only.split(",")) if args.only else None
    scenarios = [s for s in SCENARIOS if (only is None or s["id"] in only)]

    # Sanity probe
    try:
        h = requests.get(f"{args.api}/healthz", timeout=5).json()
        m = requests.get(f"{args.api}/settings/llm", timeout=5).json()
        print(f"# Server health: {h}")
        print(f"# Backend={m.get('backend')} model={m.get('model')} temp={m.get('temperature')} streaming={m.get('streaming')}")
    except Exception as e:
        print(f"# WARN: probe failed: {e}", file=sys.stderr)

    results: list[dict[str, Any]] = []
    t0 = time.time()
    for s in scenarios:
        results.append(run_scenario(args.api, s))

    total_turns = sum(len(r["turns"]) for r in results)
    leaked_turns = sum(1 for r in results for t in r["turns"] if t["leaked"])
    leaked_scenarios = sum(1 for r in results if r["any_leak"])
    duration = time.time() - t0

    print("\n" + "=" * 70)
    print("CHINESE-LEAK SUMMARY")
    print("=" * 70)
    print(f"Scenarios:       {leaked_scenarios}/{len(results)} leaked")
    print(f"Turns:           {leaked_turns}/{total_turns} leaked  ({leaked_turns / max(total_turns,1):.1%})")
    print(f"Total CJK chars: {sum(r['total_cjk'] for r in results)}")
    print(f"Wall clock:      {duration:.1f}s")
    print()
    print("Per-scenario:")
    for r in results:
        leaked_count = sum(1 for t in r["turns"] if t["leaked"])
        flag = "🚨" if r["any_leak"] else "✅"
        elang = f" expect={r.get('expect_lang')}" if r.get("expect_lang") else ""
        print(f"  {flag} {r['id']:<35} {r['category']:<42}{elang} "
              f"{leaked_count}/{len(r['turns'])} turns leaked, "
              f"{r['total_cjk']} CJK / {r['total_thai']} TH")

    report = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "api": args.api,
        "duration_s": round(duration, 1),
        "totals": {
            "scenarios": len(results),
            "scenarios_leaked": leaked_scenarios,
            "turns": total_turns,
            "turns_leaked": leaked_turns,
            "leak_rate": round(leaked_turns / max(total_turns, 1), 3),
            "total_cjk_chars": sum(r["total_cjk"] for r in results),
        },
        "scenarios": results,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"\nFull JSON report → {args.out}")
    sys.exit(0 if leaked_turns == 0 else 1)


if __name__ == "__main__":
    main()
