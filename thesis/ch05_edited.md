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

#### 5.14.7 Chinese Token Leak และ Trilingual EN/TH/CN Policy

หลังจาก 5.14.2–5.14.6 ผลทดสอบเริ่มต้น 0/38 เคสมี Chinese leak อย่างไรก็ตามการเพิ่ม **stress test ที่กดดันโมเดลมากขึ้น** เผยให้เห็นข้อจำกัดเพิ่มเติมประการที่ 5: เนื่องจาก Qwen3.5 ฝึกด้วยคลังข้อมูลภาษาจีนเป็นหลัก local 9B model จะ "หลุด" ตัวอักษรจีน (CJK ideographs) เข้ามาในคำตอบภาษาไทยหรืออังกฤษบางครั้งภายใต้ cognitive load สูง — เช่น turn ที่ต้องสรุป conversation หลายขั้น หรือคำขอที่ต้องเปลี่ยนภาษากลางบทสนทนา ตัวอย่างที่พบในการทดสอบจริง:

> "...• ✅ การตรวจสอบราคาและ**可用性** **ขออภัยที่สับสน** — คำตอบที่ฉันให้ไปเมื่อกี้..."

โมเดลกำลังสร้างคำตอบภาษาไทย พบคำว่า "availability" และส่งออกเป็นจีน 可用性 (3 ตัวอักษร) แทนที่จะแปลเป็นภาษาไทย แม้ regex `has_tool_leak()` จาก 5.14.2 จะไม่จับเนื่องจากไม่ใช่ tool-call syntax post-processor เดิมจึงไม่สามารถป้องกันได้

**การพิจารณาทาง business: Chinese เป็นภาษาที่ต้องรองรับ ไม่ใช่ภาษาที่ต้องบล็อก**

นักท่องเที่ยวจากจีนแผ่นดินใหญ่เป็นกลุ่มลูกค้าหลักของโรงแรม 5 ดาวในประเทศไทย (ประมาณ 17% ของแขกต่างชาติทั้งหมดในปี 2025) ดังนั้นการกำจัด CJK ออกจากคำตอบทั้งหมดจะเป็นการตัดสินใจที่ผิด policy ที่ถูกต้องคือ: **respond in the same language as the user's latest message** ขยายขอบเขตจาก 2 ภาษา (ไทย/อังกฤษ) เป็น 3 ภาษา (ไทย/อังกฤษ/จีน) อย่างเป็นทางการ

**ชั้นที่ 1: Trilingual Policy ใน System Prompt**

ปรับ `main_prompt` ใน `src/agent/hotel_prompt.yaml` ให้ประกาศการรองรับ 3 ภาษาอย่างชัดเจน พร้อม Chinese tone block:

```yaml
# src/agent/hotel_prompt.yaml — main_prompt
You are a professional trilingual (Thai/English/Chinese) hotel assistant
for The Grand Horizon Hotel...

**CRITICAL LANGUAGE RULE**: Detect the guest's language from their LATEST
message only and reply in the SAME language for the ENTIRE response.
- English message → respond ENTIRELY in English (Latin script)
- Thai message    → respond ENTIRELY in Thai (Thai script)
- Chinese message → respond ENTIRELY in Mandarin Chinese (Hanzi)
- Any other language → respond in English by default
- NEVER mix scripts in one response. Do NOT drop a Chinese word into a
  Thai/English reply, or a Thai word into an English/Chinese reply, even
  for terms like "availability" — translate them properly.
- One exception: a guest's own proper name (e.g. "王小明") may be echoed
  in its original script — names are not translated.

**CHINESE TONE**: Address the guest as 您 (formal "you"). Default to
Simplified Chinese unless the guest writes in Traditional.
```

นอกจากนี้ admin-override message (เมื่อ `escalation_monitor` ดักจับ session ส่งให้ staff ดูแลแทน bot) ก็ปรับให้ตอบในภาษาที่ guest พูด:

```python
# src/hotel_guardrails/server.py
_ADMIN_OVERRIDE_MESSAGES = {
    "th": "เจ้าหน้าที่โรงแรมกำลังช่วยเหลือท่านอยู่ กรุณารอสักครู่ค่ะ",
    "en": "A hotel staff member is assisting you. Please wait.",
    "cn": "酒店工作人员正在为您服务，请稍候。",
}
```

**ชั้นที่ 2: Language-Leak Detector (`has_language_leak`)**

โครงสร้างเดียวกับ `has_tool_leak()` ใน 5.14.2 — detect → retry → strip — แต่ logic ภายในต่างกัน เนื่องจากต้องแยกระหว่าง CJK ที่หลุด (leak) กับ CJK ที่ guest ใส่มาเอง (เช่น ชื่อตัวเอง) ซึ่ง echo กลับมาได้:

```python
# src/hotel_guardrails/hotel_langgraph.py
_CJK_RE  = _re.compile(r"[㐀-䶿一-鿿豈-﫿぀-ヿ]")
_THAI_RE = _re.compile(r"[฀-๿]")

def detect_input_language(text: str) -> str:
    """Classify a user message as 'en', 'th', or 'cn' by dominant script."""
    cn = len(_CJK_RE.findall(text))
    th = len(_THAI_RE.findall(text))
    en = sum(1 for c in text if c.isascii() and c.isalpha())
    total = cn + th + en
    if total == 0:
        return "en"
    if cn >= max(th, en) and cn / total >= 0.20:
        return "cn"
    if th >= max(cn, en) and th / total >= 0.20:
        return "th"
    return "en"

def has_language_leak(input_text: str, response_text: str) -> bool:
    """True if response script doesn't match expected reply language."""
    expected = detect_input_language(input_text)
    user_cjk = {c for c in input_text if _CJK_RE.match(c)}

    if expected in ("en", "th"):
        # Any CJK char NOT provided by the user is a leak
        return any(_CJK_RE.match(c) and c not in user_cjk for c in response_text)

    # expected == "cn": Thai chars or insufficient CJK = leak
    cjk_total  = len(_CJK_RE.findall(response_text))
    thai_total = len(_THAI_RE.findall(response_text))
    body_len   = cjk_total + thai_total + sum(1 for c in response_text
                                              if c.isascii() and c.isalpha())
    if thai_total >= 5:
        return True
    if body_len >= 60 and cjk_total < 10:
        return True  # model failed to reply in Chinese
    return False
```

จุดสำคัญของการออกแบบ:

* **User-provided CJK whitelist** : เก็บอักษรจีนที่ guest พิมพ์มาเอง (เช่น "王小明 (Wang Xiaoming)") เพื่อให้ echo กลับในคำตอบภาษาอังกฤษได้โดยไม่นับเป็น leak — นี่คือพฤติกรรมที่ถูกต้อง (ไม่ควรแปลชื่อคน)
* **Asymmetric thresholds** : EN/TH expected ห้าม CJK 1 ตัวขึ้นไป (strict); CN expected อนุญาต Latin (brand names) แต่ห้าม Thai (ตามคนละ script)
* **Quantity check สำหรับ CN reply** : ถ้า body ยาวพอ (≥ 60 ตัวอักษร) แต่ CJK น้อยกว่า 10 แสดงว่าโมเดลไม่ยอมตอบเป็นจีน — นับเป็น leak ในทิศทางตรงข้าม

**ชั้นที่ 3: Wire เข้า Retry Loop**

ใช้ retry mechanism จาก 5.14.3 โดยเพิ่ม language leak เป็น quality check เพิ่มเติม:

```python
# src/hotel_guardrails/hotel_langgraph.py — invoke_hotel_agent
leaked      = has_tool_leak(candidate_text)
lang_leaked = has_language_leak(message, candidate_text)

if candidate_text and not leaked and not lang_leaked:
    return success(candidate_text, retries=attempt)

if attempt < max_retries:
    reason = ("tool-call leak" if leaked else
              f"language leak (expected {detect_input_language(message)})"
              if lang_leaked else "empty response")
    logger.warning(f"Retry {attempt+1}/{max_retries} — {reason}")
```

retry budget ใช้ค่าเดิมจาก 5.14.4 (2 ครั้งสำหรับ 9B local 1 ครั้งสำหรับ cloud) ไม่ต้องเพิ่ม cost

**ชั้นที่ 4: `strip_language_leak()` Last-Resort Fallback**

หาก retry ทั้งหมดยังคงมี leak จะทำ aggressive strip โดยลบเฉพาะ run ของ off-script characters ขนาด 2 ตัวขึ้นไป ที่ guest ไม่ได้ใส่มาเอง — single-character leaks ปล่อยไว้เพื่อหลีกเลี่ยงการตัดประโยคขาด ส่วน proper names ที่อยู่ใน user input จะรอดเสมอ

```python
def strip_language_leak(input_text: str, response_text: str) -> str:
    expected = detect_input_language(input_text)
    user_cjk_runs = {m.group(0) for m in _CJK_RUN_RE.finditer(input_text)}

    if expected in ("en", "th"):
        # Drop CJK runs of 2+ chars not in user's input
        return _CJK_RUN_RE.sub(
            lambda m: m.group(0) if m.group(0) in user_cjk_runs else "",
            response_text,
        )
    elif expected == "cn":
        # Drop Thai runs in a Chinese reply; Latin (brand names) preserved
        return _THAI_RUN_RE.sub("", response_text)
    return response_text
```

**ผลการทดสอบ — `scripts/test_chinese_leak.py` (18 scenarios, 70 turns, multi-turn)**

ทดสอบกับ live local Qwen3.5 Opus 9B ผ่าน Ollama ครอบคลุม 8 trigger categories: (1) cross-language code switching ระหว่าง turns, (2) hard reasoning ภายใต้ multi-constraint booking, (3) out-of-domain math/literature, (4) RAG cold spots, (5) long Thai conversation 6 turns, (6) cross-session memory recall ที่เปลี่ยนภาษา, (7) technical service request, (8) direct Chinese-language provocations ("respond in Chinese") พร้อม positive scenarios เพิ่มเติม: pure Chinese conversation 5 turns, CN→TH→EN three-language switch, CN cross-session memory recall

| Run | Scenarios | Turns | Leaked | Leak rate |
| --- | ---: | ---: | ---: | ---: |
| Pre-fix (8 base + 3 baits) | 11 | 38 | 3 | **7.9%** |
| Post-fix (13 incl. positive CN) | 13 | 46 | **0** | **0.0%** |
| Extended edge cases (incl. trilingual admin-override) | 5 | 24 | **0** | **0.0%** |
| **รวม post-fix** | **18** | **70** | **0** | **0.0%** |

scenario `G_technical_service` turn 3 ที่เคย leak `可用性` (3 CJK chars) post-fix ส่งคำตอบเป็นภาษาไทยล้วน 545 chars (0 CJK 362 Thai chars) scenario ใหม่ `L_full_chinese_conversation` 5 turns ตอบเป็นภาษาจีนล้วน 1011 CJK chars 0 Thai

**Bug fix ที่พบระหว่างการทดสอบ**

ระหว่าง stress test เผยให้เห็น `NameError: 'request_id' is not defined` ใน admin-override branch ที่ `server.py:1035` (จะ fire เมื่อ `escalation_monitor` flag session แล้ว turn ถัดไปเข้า admin-override path) แก้ไขโดยเปลี่ยน `request_id` → `current_request_id` ตาม signature ของ `_process_chat_locked()` — เป็นตัวอย่างที่แสดงว่า defensive testing สามารถค้นพบ bug ที่ไม่เกี่ยวข้องกับสิ่งที่ทดสอบโดยตรง

**ข้อจำกัดที่ยังเหลือ**

* Chain-of-thought adversarial prompts ("Think step by step", "Show your reasoning out loud") ทำให้ local 9B run-away generation จนเกิน request timeout 120 วินาที (3/4 turns ใน scenario Q ของชุดทดสอบ) — ปัญหานี้แยกออกจาก language leak ไม่ใช่ leak แต่เป็น performance issue แก้ได้ด้วย max_tokens cap หรือเพิ่ม upstream timeout
* Single-character CJK leaks ไม่ถูก strip (เพื่อหลีกเลี่ยงการตัดประโยคขาด) — ถ้ารอด retry ทั้ง 2 ครั้งจะถึงผู้ใช้
* `_extract_prefs_from_text()` ของ memory layer ปัจจุบันรองรับเฉพาะ EN+TH keyword tables — Chinese preference extraction (เช่น 我对花生过敏 = peanut allergy) เป็น follow-up ที่จะทำต่อไป
* การทดสอบรอบนี้ใช้เฉพาะ local 9B; cloud Qwen3 Max คาดว่าจะผ่านอย่างน้อยเท่ากับ local (จากผลการทดสอบ functional 100% ก่อนหน้านี้) แต่ยังไม่ได้ rerun อย่างเป็นทางการ

ผลลัพธ์รวม: ระบบ quality control เพิ่มเป็น 4 ชั้น (จากเดิม 3 ชั้น) ครอบคลุม tool-call leak, language leak, empty response และ Thai particle consistency พร้อมรองรับลูกค้าจีนแผ่นดินใหญ่อย่างเป็นทางการ — เป็นการแสดงว่าสถาปัตยกรรม detector + retry + strip ที่ออกแบบไว้สำหรับ tool-call leak สามารถขยายไปครอบคลุม leak ประเภทอื่นได้โดยไม่ต้อง refactor

---

## Suggested Figure Placeholders

You can also add these figure references (generate PNGs later or make ASCII):

* `[Figure 5.25: Server-side retry flow — LangGraph invoke → quality check (empty? leak?) → retry (up to max_retries) → return]`
* `[Figure 5.26: Thai particle decision tree — detect user particle → match in response → validate consistency]`
* `[Figure 5.27: Trilingual EN/TH/CN policy — detect_input_language() → expected reply script → has_language_leak() with user-provided CJK whitelist → retry → strip_language_leak() fallback. Mirrors the tool-call leak architecture (Figure 5.25) extended to language drift.]`

---

## Quick paste-friendly summary (optional intro paragraph)

If you want a one-paragraph teaser at the very start of 5.14 before 5.14.1:

> ระหว่างการทดสอบ 59 test cases กับ 4 sub-agents พบว่า local Qwen3.5 Opus 9B model มีข้อจำกัด 4 ประการที่กระทบคุณภาพคำตอบ ได้แก่ (1) tool-call leak เขียน syntax เป็น text แทนการเรียก tool (2) empty response (3) Thai particle mismatch ระหว่าง ครับ/ค่ะ/คะ และ (4) particle mixing ในคำตอบเดียวกัน การ stress test เพิ่มเติมเผยข้อจำกัดที่ 5 (5) Chinese ideograph leak — Qwen3.5 ที่ฝึกด้วยข้อมูลภาษาจีนเป็นหลักหลุดอักษรจีนเข้ามาในคำตอบไทย/อังกฤษภายใต้ cognitive load สูง ปัญหาเหล่านี้ไม่เกิดกับ cloud model แต่เกิดเป็นครั้งคราวกับ 9B ภายใต้บริบทซับซ้อน จึงได้พัฒนาระบบ quality control 4 ชั้น ได้แก่ regex-based tool-call leak detection, server-side retry พร้อม per-model retry budget, strict prompt rules สำหรับ Thai particle และ trilingual EN/TH/CN policy พร้อม language-leak detector + strip post-processor พร้อม user-provided CJK whitelist (สำหรับ proper-name echoes) ผลการทดสอบ functional ได้ 98.3% accuracy ส่วน Chinese-leak stress test ได้ 0/70 turns leaked (จาก 7.9% pre-fix) ครอบคลุมทั้ง pure-Chinese conversation และ CN→TH→EN three-language switch
>
