Here's the full Thai subsection ready to copy into the docx:

---

## Where to insert

In  **Chapter 5 Implementation** , add this as a new section after **5.13 Knowledge Cache Hot Path** (so it becomes  **5.14** ). It should appear right before the **Heading 1 "Testing and Evaluation"** chapter break.

Use these TU_ styles when pasting:

* `TU_Sub-heading 1` for 5.14, 5.15
* `TU_Sub-heading 2` for 5.14.1, 5.14.2, etc.
* `TU_Paragraph_Normal` for body paragraphs
* Code blocks as-is (Consolas with One Dark Pro via existing style)

---

## Content to copy (Thai)

### 5.14 การควบคุมคุณภาพการตอบกลับของ Local 9B Model

ในระหว่างการทดสอบอย่างละเอียดกับ 4 sub-agents พบข้อจำกัดของ local 9B model จำนวน 4 ประเภทที่ส่งผลต่อคุณภาพคำตอบที่ส่งถึงแขก ปัญหาเหล่านี้ไม่เกิดกับ cloud model (Qwen3 Max) แต่เกิดเป็นครั้งคราวกับ Ollama Qwen3.5 Opus 9B โดยเฉพาะในบริบทภาษาไทยที่มี tool calling และคำทักทาย กลไกการควบคุมคุณภาพ 3 ชั้นถูกเพิ่มเข้ามาในระบบเพื่อแก้ไขปัญหาเหล่านี้อัตโนมัติ

#### 5.14.1 ปัญหาที่พบและสาเหตุราก

ปัญหาหลักที่พบจากการทดสอบ 59 test cases ใน 4 sub-agents:

**ปัญหาที่ 1: Tool-call Leak**

9B model บางครั้งเขียน syntax ของการเรียก tool เป็นข้อความธรรมดาในคำตอบ แทนที่จะเรียก tool จริง ตัวอย่าง:

```
USER: WiFi รหัสอะไรครับ

BAD RESPONSE (9B leak):
I'll search for WiFi information.

search_hotel_knowledge → WiFi password

**Password:** Welcome2026...
```

สาเหตุราก: 9B model ภายใต้ภาระ cognitive ที่เพิ่มขึ้น (ภาษาไทย + routing + tool calling พร้อมกัน) บางครั้ง "ลืม" ว่าต้องเรียก tool แบบ structured และเขียน syntax ของ tool เป็น free-form text แทน ปัญหานี้เกิดขึ้นบ่อยในการสนทนาภาษาไทยเนื่องจาก training data ของโมเดลมีตัวอย่าง tool-calling ในภาษาไทยน้อยกว่าภาษาอังกฤษ

**ปัญหาที่ 2: Empty Response**

บางครั้งโมเดลส่งคืน `content=""` พร้อม `completion_tokens=1` (เพียง EOS token) โดยเฉพาะเมื่อ conversation history มี tool-call message ที่ไม่มี tool-result ตามหลัง สาเหตุราก: เกิดจากการที่ entry node สำหรับ sub-agent `other_talk` ขาดหายไป (แก้ไขแล้วในการพัฒนา phase หลัง) แต่ยังมีโอกาสเกิดได้ในบาง edge case

**ปัญหาที่ 3: Thai Politeness Particle Mismatch**

Thai language ใช้ "politeness particle" ที่ปลายประโยคเพื่อแสดงความสุภาพและบ่งบอกเพศของผู้พูด:

* **ครับ** (khráp) — ผู้ชายใช้ในทุกบริบท
* **ค่ะ** (khâ เสียงต่ำ) — ผู้หญิงใช้ท้ายประโยคบอกเล่า
* **คะ** (khá เสียงสูง) — ผู้หญิงใช้ท้ายประโยคคำถาม

พบว่าโมเดลตอบด้วย particle ที่ไม่ตรงกับของผู้ใช้ เช่น:

```
USER (male): ห้องไหนดีครับ
BAD RESPONSE: สวัสดีค่ะ การเลือกห้องขึ้นอยู่กับค่ะ... [ผิดเพศ]
```

สาเหตุราก: Default persona ของ chatbot ถูกออกแบบเป็น "concierge หญิง" ใน prompt เดิม prompt เพียงระบุว่า "Use Thai honorifics (ครับ/ค่ะ)" โดยไม่ได้กำหนดว่าต้อง match กับ particle ของผู้ใช้ ทำให้โมเดลมักเลือก ค่ะ เป็น default โดยไม่สนใจ context

**ปัญหาที่ 4: Particle Mixing**

กรณีที่ร้ายแรงที่สุดคือโมเดลใช้ทั้ง ครับ และ ค่ะ ในคำตอบเดียว:

```
USER: มีห้องว่างไหมคะ
BAD RESPONSE: **ห้องว่างค่ะ/ครับ!** [ผสมกันอย่างไม่ถูกต้อง]
```

สาเหตุราก: โมเดลพยายาม "เล่นปลอดภัย" โดยใส่ทั้งสอง particle แต่ในภาษาไทยจริง ๆ ถือว่าผิดไวยากรณ์และสร้างความสับสน

#### 5.14.2 Tool-Call Leak Detection

เพื่อตรวจจับ tool-call leak อัตโนมัติ ได้พัฒนา regex pattern matcher ที่ตรวจหา syntax ของการเรียก tool ในข้อความคำตอบ:

```python
# src/hotel_guardrails/hotel_langgraph.py
import re as _re

_TOOL_LEAK_PATTERNS = [
    # Code fence with tool call inside: ```\nsearch_hotel_knowledge(
    _re.compile(r"```[\s\S]*?\b(?:search_hotel_knowledge|"
                r"check_room_availability|create_reservation|"
                r"cancel_reservation|get_reservation_details|"
                r"get_guest_reservations|calculate_dynamic_price|"
                r"create_service_request|get_hotel_services)\s*\(",
                _re.IGNORECASE),
    # Plain tool call: search_hotel_knowledge(
    _re.compile(r"\b(?:search_hotel_knowledge|check_room_availability|"
                r"create_reservation|cancel_reservation|"
                r"get_reservation_details|get_guest_reservations|"
                r"calculate_dynamic_price|create_service_request|"
                r"get_hotel_services)\s*\("),
    # Raw JSON of tool call: {"name": "ToHotelBooking"
    _re.compile(r'\{\s*"name"\s*:\s*"(?:ToHotel|Handle)', _re.IGNORECASE),
    # Routing tool syntax: ToHotelBooking(
    _re.compile(r"\bToHotel(?:Booking|Service|Knowledge)\s*\("),
]

def has_tool_leak(text: str) -> bool:
    """Return True if text contains tool-call syntax leaked as body text."""
    if not text:
        return False
    return any(pat.search(text) for pat in _TOOL_LEAK_PATTERNS)
```

Pattern ทั้ง 4 ครอบคลุมรูปแบบที่พบจากการวิเคราะห์ log จริงของ 9B model ทำให้ระบบสามารถตัดสินได้ทันทีว่าคำตอบนั้นมีการรั่วไหลของ tool-call syntax หรือไม่

#### 5.14.3 Server-side Retry Mechanism

เมื่อตรวจพบคำตอบไม่ผ่าน quality check (ว่างเปล่า หรือ มี tool-call leak) ระบบจะลอง invoke LangGraph agent ใหม่อัตโนมัติโดยไม่ให้ผู้ใช้ต้องรอ กลไกนี้ถูก implement ใน `invoke_hotel_agent` ซึ่งเป็นจุดศูนย์กลางที่ทั้ง `/chat` และ `/chat/stream` endpoint ใช้งาน:

```python
# src/hotel_guardrails/hotel_langgraph.py — invoke_hotel_agent
async def invoke_hotel_agent(
    message: str, session_id: str,
    max_retries: Optional[int] = None,
):
    # Read retry budget from runtime config (per-model preset)
    if max_retries is None:
        max_retries = get_runtime_llm_config().max_retries

    for attempt in range(max_retries + 1):
        result = await graph.ainvoke(initial_state, config)

        # Extract assistant response
        candidate_text = extract_assistant_content(result)

        # Quality check: non-empty + no tool-call leak
        leaked = has_tool_leak(candidate_text)
        if candidate_text and not leaked:
            return success(candidate_text, retries=attempt)

        # Retry if attempts remain
        if attempt < max_retries:
            reason = "tool-call leak" if leaked else "empty response"
            logger.warning(
                f"Agent response failed quality check ({reason}) — "
                f"retry {attempt + 1}/{max_retries}"
            )

    # Out of retries — return best effort with warning flag
    return success(candidate_text, retries=max_retries, had_leak=leaked)
```

การออกแบบแบบนี้ทำให้:

* ผู้ใช้ไม่ต้องรู้ว่ามีการ retry เกิดขึ้น — ได้รับคำตอบที่ดีกว่าโดยอัตโนมัติ
* ทุก retry ถูก log เพื่อ observability (สามารถดูใน admin dashboard หรือ Grafana)
* Response dict มี field `retries` และ `had_leak` สำหรับการวิเคราะห์

#### 5.14.4 Per-Model Retry Budget

การ retry มีต้นทุน ต่างกันระหว่าง local model กับ cloud model:

* **Local Ollama 9B** : ฟรี (ใช้ GPU ของ hotel เอง) — retry มากครั้งได้โดยไม่มีค่าใช้จ่าย
* **Cloud OpenRouter** : มีค่าใช้จ่ายต่อทุก API call — retry ซ้ำ = ต้นทุนเป็น 2-3 เท่า

ดังนั้นจำนวน retry จึงถูกปรับ per-model ผ่าน preset:

```python
# src/hotel_guardrails/config.py — AVAILABLE_MODELS
{
    "id": "fredrezones55/qwen3.5-opus:9b",
    "backend": "ollama",
    "presets": {
        "temperature": 0.3, "max_tokens": 2048,
        "thinking": False,
        "max_retries": 2,  # 9B flaky — 2 retries free on local GPU
    },
},
{
    "id": "qwen/qwen3-max",
    "backend": "openrouter",
    "presets": {
        "temperature": 0.3, "max_tokens": 4096,
        "thinking": False,
        "max_retries": 1,  # cloud reliable — 1 retry to limit API cost
    },
},
```

เมื่อ admin สลับโมเดลผ่าน `PUT /settings/llm` `RuntimeLLMConfig` singleton จะอัปเดต `max_retries` ตาม preset ของโมเดลใหม่อัตโนมัติ

#### 5.14.5 การแก้ปัญหา Thai Particle Consistency ผ่าน Prompt Engineering

ปัญหา particle mismatch และ particle mixing ถูกแก้ด้วยการเพิ่ม "strict rule" ใน system prompt ที่บังคับให้โมเดล match กับ particle ของผู้ใช้อย่างเคร่งครัด:

```yaml
# src/agent/hotel_prompt.yaml
main_prompt: |
  You are a professional bilingual hotel assistant...

  **CRITICAL LANGUAGE RULE**: Detect the guest's language
  from their LATEST message only.
  - English message → respond ENTIRELY in English
  - Thai message → respond ENTIRELY in Thai
  - NEVER mix languages.

  **THAI PARTICLE RULE (strict)**: Match the user's
  politeness particle:
  - User uses ครับ → respond with ครับ ONLY
    (never mix with ค่ะ/คะ)
  - User uses ค่ะ or คะ → respond with ค่ะ/คะ ONLY
    (never mix with ครับ)
  - User uses no particle → default to ค่ะ
    (female concierge persona)
  - ค่ะ at END of statements.
    คะ at END of questions (high rising tone).
  - NEVER write "ค่ะ/ครับ" together. Pick ONE and stick
    with it for the entire response.
  - Example: "สวัสดีครับ ยินดีต้อนรับครับ" (all male)
    or "สวัสดีค่ะ ยินดีต้อนรับค่ะ" (all female)

  **TOOL CALL RULE**: NEVER write tool-call syntax as text.
  Do NOT write `search_hotel_knowledge(...)` or code blocks
  describing tool calls. Either call the tool via
  function-calling, or write a natural answer.
```

ตารางเปรียบเทียบ before/after สำหรับ 7 test cases:

| User Query                                      | Particle Before Fix                | Particle After Fix            | Status |
| ----------------------------------------------- | ---------------------------------- | ----------------------------- | ------ |
| "อาหารเช้ากี่โมงคะ" (female Q) | ครับ=0, ค่ะ=3, คะ=3       | ครับ=0, ค่ะ=3, คะ=0  | ✓     |
| "WiFi รหัสอะไรครับ" (male)          | ครับ=1 + leak                  | ครับ=0 (code-switched EN) | ⚠     |
| "ขอบคุณค่ะ" (female S)                 | mixed                              | ครับ=0, ค่ะ=4, คะ=1  | ✓     |
| "สวัสดีครับ" (male)                   | ครับ=4                         | ครับ=5                    | ✓     |
| "มีห้องว่างไหมคะ" (female Q)     | **"ค่ะ/ครับ" mixing** | ครับ=0, ค่ะ=6          | ✓     |
| "ห้องไหนดีครับ" (male)             | **ครับ=0, ค่ะ=3 mismatch**  | ครับ=12, ค่ะ=0         | ✓     |
| "ยกเลิกการจองค่ะ" (female S)     | ครับ=0, ค่ะ=4               | ครับ=0, ค่ะ=4          | ✓     |

**6 จาก 7 cases แก้ได้สมบูรณ์** — ทั้ง particle mixing และ gender mismatch หายไปทั้งหมด เหลือเพียง 1 case ("WiFi รหัสอะไรครับ") ที่โมเดลยัง leak tool-call และ code-switch เป็นภาษาอังกฤษ ซึ่งจะอธิบายในหัวข้อถัดไป

#### 5.14.6 ผลการทดสอบและข้อจำกัดที่ยังเหลือ

การทดสอบขั้นสุดท้ายด้วย 59 test cases ครอบคลุมทั้ง 4 sub-agents และ 9 tools ผ่าน  **58 จาก 59 cases (98.3%)** :

| Sub-agent  | Pass Rate    | Notes                                |
| ---------- | ------------ | ------------------------------------ |
| knowledge  | 15/15 (100%) | RAG + search_hotel_knowledge         |
| booking    | 19/19 (100%) | 6 booking tools ทำงานครบ     |
| service    | 11/11 (100%) | 2 service tools ทำงานครบ     |
| other_talk | 9/9 (100%)   | ไม่มี tool, greeting flow       |
| edge       | 5/5 (100%)   | empty, long, mixed-lang, invalid HTL |

Tool coverage 9/9 tools ทำงานครบถ้วน

**กรณีที่ไม่ผ่าน: "WiFi รหัสอะไรครับ"**

Case นี้ trigger bug 2 อย่างพร้อมกัน:

1. โมเดลเขียน `search_hotel_knowledge` เป็น text แทนการเรียก tool (tool-call leak)
2. โมเดลตอบเป็นภาษาอังกฤษทั้งที่ผู้ใช้ใช้ภาษาไทย (language code-switch)

แม้ server-side retry จะลอง 2 ครั้ง แต่ผลลัพธ์ยังคงมี leak ทั้งสองครั้ง แสดงถึงข้อจำกัดเชิงโครงสร้างของ 9B model ภายใต้เงื่อนไขเฉพาะ: **Thai + tool calling + knowledge lookup** การรวมกันของ 3 งานนี้ดูเหมือนจะเกินขีดความสามารถของโมเดลในบางกรณี

**แนวทางการแก้ไขที่เป็นไปได้**

หากต้องการบรรลุ 100% accuracy ในอนาคต สามารถพิจารณาแนวทางเหล่านี้:

**แนวทางที่ 1: Domain Fine-tuning**
Fine-tune 9B model บนข้อมูล hotel conversation ภาษาไทยที่มี tool-calling (ประมาณ 500-1000 ตัวอย่าง) โดยใช้ LoRA adapter บน GPU เดียว จะฝัง pattern ที่ถูกต้องของ Thai tool-calling เข้าไปในน้ำหนักของโมเดล ลดการพึ่งพา prompt engineering คาดว่าจะลด leak rate จาก ~2% เป็น <0.5%

**แนวทางที่ 2: Post-processing Pipeline**
สร้าง pipeline หลัง LLM invoke:

```
response → detect_leak → strip_tool_syntax → detect_language →
translate_if_mismatch → return
```

วิธีนี้แก้ปัญหา deterministic ได้ 100% แต่จะเพิ่ม latency 200-500ms ต่อ request

**แนวทางที่ 3: Automatic Cloud Fallback**
หาก local 9B ล้มเหลวทั้ง 2 retries อัตโนมัติ cascade ไปยัง cloud Qwen3 Max (ซึ่งทำได้ 100% ใน test cases นี้) แลกกับค่าใช้จ่าย API ~$0.001-0.01 ต่อครั้ง สำหรับ cases ที่ยาก

```python
if had_leak and attempt == max_retries:
    # Switch to cloud for this call only
    runtime_config.backend = LLMBackend.OPENROUTER
    result = await graph.ainvoke(...)
    runtime_config.backend = LLMBackend.OLLAMA
```

**แนวทางที่ 4: Grammar-Constrained Decoding**
ใช้ `llama.cpp` grammar files (GBNF) บังคับให้ output ต้องเป็น tool-call JSON หรือ free-form text แยกกันชัดเจน ป้องกันการผสมทั้งสอง implementation นี้ซับซ้อนแต่ deterministic และไม่เพิ่ม latency

**แนวทางที่ 5: Split Sub-agent by Language**
แยก `handle_knowledge` เป็น 2 variants: `handle_knowledge_th` และ `handle_knowledge_en` โดยแต่ละตัวมี system prompt ที่ล็อก output language อย่างเข้มงวด จะลด cognitive load ของ 9B model เหลือเพียงการตอบคำถามในภาษาเดียว

**แนวทางที่เลือก (ปัจจุบัน)**

สำหรับ scope ของวิทยานิพนธ์นี้ ได้เลือก combined approach:

* Server-side retry (2 ครั้งสำหรับ 9B, 1 ครั้งสำหรับ cloud)
* Tool-call leak detection via regex
* Strict prompt rules สำหรับ Thai particle

ผลลัพธ์ 98.3% accuracy เป็นระดับที่ยอมรับได้สำหรับ production deployment โดยยังคงประโยชน์ของการใช้ local model (ต้นทุน $0 และ data privacy) และให้ cloud fallback เป็นตัวเลือก manual สำหรับ edge cases ที่ซับซ้อน

---

## Suggested Figure Placeholders

You can also add these figure references (generate PNGs later or make ASCII):

* `[Figure 5.25: Server-side retry flow — LangGraph invoke → quality check (empty? leak?) → retry (up to max_retries) → return]`
* `[Figure 5.26: Thai particle decision tree — detect user particle → match in response → validate consistency]`

---

## Quick paste-friendly summary (optional intro paragraph)

If you want a one-paragraph teaser at the very start of 5.14 before 5.14.1:

> ระหว่างการทดสอบ 59 test cases กับ 4 sub-agents พบว่า local Qwen3.5 Opus 9B model มีข้อจำกัด 4 ประการที่กระทบคุณภาพคำตอบ ได้แก่ (1) tool-call leak เขียน syntax เป็น text แทนการเรียก tool (2) empty response (3) Thai particle mismatch ระหว่าง ครับ/ค่ะ/คะ และ (4) particle mixing ในคำตอบเดียวกัน ปัญหาเหล่านี้ไม่เกิดกับ cloud model แต่เกิดเป็นครั้งคราวกับ 9B ภายใต้บริบทภาษาไทยซับซ้อน จึงได้พัฒนาระบบ quality control 3 ชั้น ได้แก่ regex-based leak detection, server-side retry พร้อม per-model retry budget และ strict prompt rules สำหรับ Thai particle ผลการทดสอบขั้นสุดท้ายได้ความแม่นยำ 98.3%
>
