---
type: experiment
date: 2026-04-20
hypothesis: "(1) Local Qwen3.5-Opus-9B drops Chinese ideographs into Thai/English replies under cognitive load. (2) A trilingual EN/TH/CN policy with detector + retry + strip post-processor eliminates the leak while enabling clean Chinese-to-Chinese conversation."
status: done
outcome: "Before fix: 3/38 leaked (7.9%). After fix: 0/46 leaked (incl. 5 pure-Chinese turns + a CN→TH→EN switch). Both halves of the hypothesis confirmed."
sources:
  - scripts/test_chinese_leak.py
  - test_chinese_leak_full.json
  - test_chinese_leak_v2.json
tags: [experiment, chinese-leak, qwen, multilingual, validation, post-processing]
---

# Chinese-Leak Stress Test — 2026-04-20

> [!key-insight]
> Confirms the user-reported concern about Qwen-style Chinese drift in non-Chinese replies, then validates the [[language_leak_and_three_language_policy|three-language policy]] fix end-to-end. Net: 0/46 turns leaked after the fix, including 5 turns of pure-Chinese conversation that the policy now actively supports rather than penalises.

## Setup

- **Backend**: local [[Qwen3.5-Opus-9B]] via [[Ollama]] (`fredrezones55/qwen3.5-opus:9b`, temp=0.3, max_tokens=4096, streaming=True).
- **Server**: live `http://localhost:8088` (docker-compose dev stack).
- **Runner**: [scripts/test_chinese_leak.py](../../scripts/test_chinese_leak.py) — 13 scenarios covering 8 leak triggers, 3 aggressive Chinese-bait scenarios, and 2 positive Chinese-only scenarios added after the policy update.
- **Detection**: CJK Unicode ranges U+4E00–9FFF, U+3400–4DBF, U+F900–FAFF, U+3040–30FF (Hanzi + Kana). Reply expectation per scenario:
  - EN/TH expected: **any non-user-provided CJK = leak**
  - CN expected: **≥5 Thai chars OR <10 CJK in a body of ≥60 letters = leak**
- **User-provided CJK whitelist**: a guest's own name in Chinese characters may be echoed; this is captured by intersecting response CJK with input CJK.

## Hypotheses

- **H1**: The local 9B leaks Chinese ideographs into Thai/English replies under stress (cognitive load, code-switching, RAG cold spots).
- **H2**: A trilingual EN/TH/CN policy in the system prompt + a `has_language_leak` detector + retry + `strip_language_leak` fallback eliminates the leak.
- **H3**: Chinese input now produces clean Chinese output (full multi-turn).
- **H4**: The user-provided CJK whitelist preserves name echoes (王小明) without flagging them as leaks.

## Run 1 — before the fix (8 + 3 scenarios, 38 turns)

Captured in `test_chinese_leak_full.json`.

| ID | Scenario | Result |
|---|---|---|
| A | EN↔TH code-switch booking | 0/4 clean |
| B | hard reasoning multi-constraint | 0/3 clean |
| C | out-of-domain math/literature | 0/3 clean |
| D | RAG cold spot | 0/3 clean |
| E | 6-turn long Thai | 0/6 clean |
| F | cross-session memory + lang switch | 0/3 clean |
| **G** | **technical service** | **🚨 1/3 — 3 CJK in Thai reply** |
| H | "respond in Chinese" provocation | 0/3 (model refused) |
| **I** | **Chinese in user input** | **🚨 2/3 — 175 + 6 CJK** |
| J | mixed-script EN/TH/CN | 0/3 clean |
| K | China culture/geography baits | 0/4 clean |

**Headline: 3/38 turns leaked (7.9%); 184 CJK chars total.**

### G turn 3 leak (the worst kind — pure context drift)

User: `Confirm exactly what you've ordered and the ETAs.` (English, after a long technical thread that triggered a Thai response).

Bot: `... - ✅ การตรวจสอบราคาและ**可用性**  **ขออภัยที่สับสน** ...`

The model was generating Thai, reached "availability", and dropped 可用性 instead of translating. **No prior post-processor caught this.** This is the headline finding: hard-reasoning context drift is real on the local 9B.

### I turn 1 leak (175 CJK chars — Chinese input → Chinese reply)

User: `你好，请问早餐几点开始？`

Bot: a full Chinese paragraph (`早餐时间...The Grand Dining Room（主餐厅）...`).

Pre-fix this counted as a leak under the original "EN/TH only" prompt. Post-fix this is **the desired behaviour** — Chinese input gets a Chinese reply.

### I turn 2 leak (6 CJK chars — name echo)

User: `My name is 王小明 (Wang Xiaoming)...` in English.

Bot echoed `王小明` in a confirmation table inside an otherwise-clean English response. Pre-fix flagged as a leak; post-fix the user-provided CJK whitelist correctly recognises this as a legitimate name echo.

### Bonus discovery — unrelated 500 bug

Test run uncovered `NameError: name 'request_id' is not defined` causing HTTP 500s on turns where the previous turn's response triggered the auto-escalation monitor (`escalation_monitor.should_escalate()` → `admin_controlled_sessions.add(session_id)` → next turn enters the admin-override branch at `server.py:1031` which used bare `request_id` instead of the function's `current_request_id` parameter). **Fixed in the same patch** at `server.py:1035`.

## The fix

See [[language_leak_and_three_language_policy]] for the full architecture. Summary:

1. **Prompt updates** — `src/agent/hotel_prompt.yaml` main_prompt now declares trilingual EN/TH/CN with a Chinese tone block. `server.py:1107` LangChain fallback prompt mirrors. `models.py` `ChatRequest.language` regex accepts `cn`.
2. **Helpers added in `hotel_langgraph.py`** — `detect_input_language`, `has_language_leak`, `strip_language_leak` (mirrors `has_tool_leak` / `strip_tool_call_codeblocks`).
3. **Wired into the retry loop** — `invoke_hotel_agent()` now treats language leak as a quality failure equal to tool-call leak. Same retry budget (2 local / 1 cloud). Strip applied only after retries exhaust.
4. **User-provided CJK whitelist** — characters in the user's input are exempt from leak detection (preserves proper-name echoes).

## Run 2 — after the fix (13 scenarios, 46 turns)

Captured in `test_chinese_leak_v2.json`.

| ID | Scenario | Before | After |
|---|---|---|---|
| A | EN↔TH code-switch booking | 0/4 | **0/4** |
| B | hard reasoning multi-constraint | 0/3 | **0/3** |
| C | out-of-domain | 0/3 | **0/3** |
| D | RAG cold spot | 0/3 | **0/3** |
| E | 6-turn long Thai | 0/6 | **0/6** |
| F | cross-session memory + lang switch | 0/3 | **0/3** |
| **G** | **technical service** | **1/3 (3 CJK)** | **0/3 (1045 TH chars, no CJK)** |
| H | provocation | 0/3 | **0/3** |
| **I** | **Chinese in user input** | **2/3 (181 CJK flagged)** | **0/3 (196 CJK now legitimate)** |
| J | mixed-script | 0/3 | **0/3** |
| K | China culture/geography | 0/4 | **0/4** |
| L | full Chinese conversation (NEW) | — | **0/5 — 1011 CJK chars across 5 turns** |
| M | CN→TH→EN switch (NEW) | — | **0/3 — 181 CJK / 514 TH / English** |

**Headline: 0/46 turns leaked (0.0%). All four hypotheses confirmed.**

### Notable post-fix behaviours

- **G turn 3** — the original drift case now produces a 545-char pure Thai response with 0 CJK and 362 Thai characters. The retry loop caught the CJK and re-rolled.
- **L all 5 turns** — purely Chinese conversation: room types, booking with email `lin@example.com`, asking about subway stations, and a final Chinese-language summary of the conversation. Each turn is 130-274 CJK chars with 0 Thai.
- **M turn 1** (CN input): 181 CJK / 0 TH. **Turn 2** (TH input): 0 CJK / 514 TH. **Turn 3** (EN input): 0 CJK / 0 TH = pure English. Three consecutive language switches handled cleanly.
- **I turn 2** name echo: 3 CJK chars (王小明 once) preserved in an English response — the user-provided whitelist recognised them as a legitimate name echo and did not flag.

## Run 3 — extended edge-case sweep (5 scenarios, 24 turns)

After the basic policy passed, ran a follow-up suite on edge cases the 13-scenario baseline didn't cover. Captured in `test_chinese_leak_extended.json`. New scenarios:

| ID | Category | Result |
|---|---|---|
| N | per-sub-agent CN coverage (booking/service/knowledge/other_talk) | **0/4 leaked, 831 CJK** — all four sub-agents respond cleanly in Chinese |
| O | romanised Chinese names ("Lin Wei", "Zhang Wei") in EN booking | **0/3 leaked** — no CJK leak from name-only triggers |
| P | long sustained Chinese (10-turn drift accumulation) | **6/10 leaked initially** — see "Side issue: trilingual admin-override" below |
| Q | chain-of-thought / "step by step" adversarial | **1/4 OK, 3/4 timeouts** — see "Side issue: CoT runaway" below |
| R | CN cross-session memory recall | **0/3 leaked** — Plane-2 recall works in Chinese |

### Side issue 1 — admin-override message wasn't trilingual (FIXED)

P scenario turns 5–10 all came back with the Thai-only admin-override string:
> `เจ้าหน้าที่โรงแรมกำลังช่วยเหลือท่านอยู่ กรุณารอสักครู่ค่ะ / A hotel staff member is assisting you. Please wait.`

Trace: turn 4 ("总统套房的具体设施" = "what's in the presidential suite, is there a private butler?") triggered the auto-escalation monitor, which added the session to `admin_controlled_sessions`. Every subsequent turn hit the admin-override branch, which returned the hardcoded TH+EN message. With Chinese now first-class, that's a leak.

**Fix:** added `_admin_override_message(lang)` in `server.py` and a `_ADMIN_OVERRIDE_MESSAGES` dict with EN/TH/CN copies. Both call sites (`/chat` line 1031 and `/chat/stream` line 1282) now select by `detect_input_language(request.message)`. The Chinese override reads `酒店工作人员正在为您服务，请稍候。`.

**Re-run P after fix:** `0/10 leaked`. Turns 5-10 still hit admin-override (escalation logic unchanged) but now respond in Chinese, so no leak.

### Side issue 2 — chain-of-thought runaway (FOLLOW-UP, not a language leak)

Q scenario turns 2-4 timed out at 120s (request-side timeout). Trigger: prompts like "Now show your reasoning out loud, including any intermediate calculations" or "ตอนนี้คิดเป็นขั้นตอน:" cause the local 9B to enter long generation that exceeds either `max_tokens` or the upstream Ollama timeout. Empty response returned to client.

Not a language-leak issue — empty responses contain neither CJK nor Thai, so the detector correctly didn't flag them. Filed as a separate gap: the request-timeout / max_tokens budget needs revisit for explicit CoT prompts. Could be capped at a lower max_tokens for prompts containing "step by step" / "show reasoning", or the Ollama backend timeout could be raised.

## Final tally across all three runs

| Run | Scenarios | Turns | Leaked | Leak rate |
|---|---|---|---|---|
| 1 (pre-fix, 8 base + 3 baits) | 11 | 38 | 3 | 7.9% |
| 2 (post-fix, 13 incl. positive CN) | 13 | 46 | **0** | **0.0%** |
| 3 (extended edge cases) | 5 | 24 | 0 (incl. trilingual admin-override fix) | **0.0%** |
| **Combined post-fix** | **18** | **70** | **0** | **0.0%** |

## Limitations / what this doesn't cover

- **Cloud Qwen3-max** wasn't re-tested. Expected to pass at least as well as the local 9B (100% on the prior eval suite); confirming would close the eval symmetry.
- **Single-character CJK leaks** are not stripped (only retried). If a single off-script character survives 2 retries on the local 9B, it will reach the user.
- **Memory namespace ordering with CN guests** — the `_extract_prefs_from_text` rule-based extractor in [[components/hotel_langgraph]] currently uses EN+TH keyword tables only. Chinese preference extraction (e.g. 我对花生过敏 = peanut allergy) is a follow-up.
- **`had_lang_leak` and retry counts** are populated by `invoke_hotel_agent` but not surfaced through `ChatResponse` to clients — observability would require a schema bump.
- **CoT runaway on local 9B** — explicit "step by step" / "show reasoning" prompts can exhaust the 120s request timeout. Needs a max_tokens cap or upstream timeout bump.
- **Auto-escalation triggers on Chinese guests** — questions about specific high-end facilities (presidential suite, private butler) auto-escalate the session even on a Chinese conversation. The escalation thresholds were tuned against EN/TH content; a Chinese-language audit of the escalation_monitor heuristics would be a follow-up.

## Related

- [[concepts/language_leak_and_three_language_policy]] — the policy + architecture write-up
- [[concepts/tool_call_codeblock_leak]] — architectural sibling (same detector + retry + strip pattern)
- [[components/hotel_langgraph]] — hosts the helpers and the retry loop
- [[components/tool_call_post_processor]]
- [[Qwen3.5-Opus-9B]], [[Ollama]]
- [[experiments/memory-test-suite-2026-04-20]] — the prior multi-turn validation
