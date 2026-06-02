---
type: concept
status: implemented
date_ingested: 2026-04-20
sources:
  - src/hotel_guardrails/hotel_langgraph.py
  - src/agent/hotel_prompt.yaml
  - src/hotel_guardrails/server.py
  - src/hotel_guardrails/models.py
  - scripts/test_chinese_leak.py
tags: [concept, language, qwen, multilingual, post-processing, novel-contribution]
---

# Language Leak & Three-Language Policy (EN / TH / CN)

> [!key-insight]
> The hotel assistant supports three first-class languages — **English, Thai, Mandarin Chinese** — chosen because Chinese tourists are a significant guest segment for Thai luxury hotels. The local Qwen3.5-Opus-9B is Chinese-trained, so the policy must both *enable* clean Chinese replies for Chinese-speaking guests and *prevent* Chinese ideographs from leaking into Thai or English replies. This concept page documents both halves.

## Why this exists

The empirical motivation is the [Chinese-leak stress test](../experiments/chinese-leak-test-2026-04-20.md): under cognitive load (long Thai conversation about technical issues), the local 9B occasionally drops Chinese words like 可用性 ("availability") into otherwise pure Thai responses — the model reaches for a token and produces it in Chinese instead of translating. The test caught it on the **G_technical_service** scenario, turn 3:

> `- ✅ การตรวจสอบราคาและ可用性  **ขออภัยที่สับสน** - ...`

Three CJK characters in a 760-char Thai response. The original `strip_tool_call_codeblocks` ([[tool_call_codeblock_leak]]) only handles tool-call leaks — language drift had no guard.

## Policy

| Detected input language | Reply language |
|---|---|
| English (Latin dominant) | English (no Thai or CJK) |
| Thai (Thai script dominant) | Thai (no Latin words for branded names allowed; no CJK) |
| Chinese (CJK dominant) | Mandarin Chinese (Hanzi; no Thai) |
| Anything else | English (default fallback) |

**Detection rule**: a script wins when its character count is the highest of the three AND ≥ 20% of the total (Latin + Thai + CJK) letter count. Otherwise English. See `detect_input_language()` at `src/hotel_guardrails/hotel_langgraph.py:~1310`.

**Proper-name exception**: a CJK substring that appears in the user's own input message may be echoed in the response regardless of expected reply language. This preserves names like `王小明 (Wang Xiaoming)` in confirmation tables. The whitelist is computed per-turn from the user's `HumanMessage`.

## Architecture — front and back

The policy is enforced in two complementary layers, mirroring the [[tool_call_codeblock_leak]] dual-layer pattern:

### Front: system prompts updated
- **`src/agent/hotel_prompt.yaml`** — `main_prompt` now declares trilingual support, lists the four routing rules (EN→EN, TH→TH, CN→CN, other→EN), and adds a Chinese tone block (use `您`, default Simplified, professional 5-star concierge register). The proper-name exception is stated explicitly.
- **`src/hotel_guardrails/server.py:~1107`** — the LangChain fallback prompt mirrors the same trilingual contract with example greetings in all three languages.
- **`src/hotel_guardrails/models.py`** — `ChatRequest.language` regex bumped from `^(th|en|auto)$` to `^(th|en|cn|auto)$`. Clients can now opt-in to a forced reply language.

### Back: detector + retry + strip post-processor

In `hotel_langgraph.py`, three new helpers parallel `has_tool_leak` / `strip_tool_call_codeblocks`:

| Helper | Purpose |
|---|---|
| `detect_input_language(text)` | Returns `'en' / 'th' / 'cn'` by dominant-script ratio (≥20% threshold) |
| `has_language_leak(input_text, response_text)` | True when expected reply script and response script disagree |
| `strip_language_leak(input_text, response_text)` | Last-resort fallback: drops runs of 2+ off-script characters, preserving user-provided proper names |

Wired into the existing retry loop in `invoke_hotel_agent()`:

```python
leaked = has_tool_leak(candidate_text)
lang_leaked = has_language_leak(message, candidate_text)
if candidate_text and not leaked and not lang_leaked:
    # success
else:
    # retry up to max_retries (2 for local 9B, 1 for cloud); on final
    # attempt, strip_language_leak() salvages what it can.
```

The retry budget is unchanged: 2 for Ollama 9B, 1 for OpenRouter cloud.

## What "leak" means in each direction

| Expected reply | Leak signal |
|---|---|
| EN | Any CJK char in response that the user did NOT provide |
| TH | Any CJK char in response that the user did NOT provide. (Latin words for brand names like "The Grand Horizon" are fine.) |
| CN | (a) ≥5 Thai characters in response, or (b) response body ≥60 letters but <10 CJK characters (model failed to produce Chinese) |

Two detection asymmetries are intentional:
- The CN side allows Latin freely (formal Mandarin frequently borrows English brand and technical terms).
- The EN/TH side is strict on CJK because Qwen-style "Chinese drift" is the leak we're guarding.

## Strip strategy (last resort)

Stripping is only applied after retries are exhausted. The strategy:

- **EN/TH expected**: drop CJK runs of length ≥ 2 that did NOT appear in the user's input. Single-character CJK (rare punctuation drift) is left alone to avoid mangling legitimate cases.
- **CN expected**: drop Thai runs of length ≥ 2. Latin is left alone.
- After any strip: collapse `\n{3,}` to `\n\n`, normalise spaces, `.strip()`.

Stripping is preferred only as a salvage. The retry-first approach minimises broken sentences (G's case "การตรวจสอบราคาและ可用性" stripped naively becomes "การตรวจสอบราคาและ" — grammatically incomplete). A retry usually yields a clean Thai sentence that translates "availability" properly.

## Validation evidence

[chinese-leak-test-2026-04-20](../experiments/chinese-leak-test-2026-04-20.md) — 13 multi-turn scenarios, 46 turns total, against live local Qwen3.5-Opus-9B:

- **Before fix**: 3/38 turns leaked (7.9%) including the G_technical 可用性 case.
- **After fix**: **0/46 turns leaked** including 5 turns of pure-Chinese conversation, a 3-turn CN→TH→EN switch, and the same G_technical scenario that previously leaked.

## Thesis framing

For Chapter 5 (Implementation):

- **Tri-lingual support is a market fit decision, not a generic feature**. Thailand's 5-star hospitality segment serves Chinese tourists at scale; a hotel concierge that can't operate in Mandarin loses a primary customer demographic. Adopting a Chinese-trained model (Qwen) makes this both feasible and necessary.
- **Detector + retry + strip is a transferable pattern**. The same shape applies to any local LLM that drifts: identify the failure mode, attach a deterministic detector, give the LLM another shot, and salvage as a last resort. Same pattern as [[tool_call_codeblock_leak]] — observed-shape catalog, not generic regex.
- **User-provided whitelist is the key to false-positive control**. Naive CJK stripping would ruin Chinese name echoes; whitelisting user-provided characters preserves correct multilingual behaviour while still catching genuine drift.

## Open follow-ups

- Cloud Qwen3-max wasn't re-tested; expected to pass at least as well as the local 9B (it scored 100% on the prior eval suite).
- Single-character CJK leaks are not currently stripped, only retried — if a single-char leak survives all retries it remains visible.
- The `had_lang_leak` field is returned from `invoke_hotel_agent()` but not currently surfaced through `ChatResponse` to the client; observability through to clients would require updating the response schema.

## Related

- [[experiments/chinese-leak-test-2026-04-20]] — the validation experiment
- [[concepts/tool_call_codeblock_leak]] — the architectural sibling (also detector + retry + strip)
- [[concepts/bilingual_memory_extraction]] — adjacent multilingual concern (Thai/English keyword tables)
- [[components/hotel_langgraph]] — hosts all three new helpers
- [[components/server]] — hosts the LangChain fallback prompt
- [[Qwen3.5-Opus-9B]], [[Ollama]] — the runtime that exhibits the drift
- [[The Grand Horizon Hotel]] — the canonical hotel name
