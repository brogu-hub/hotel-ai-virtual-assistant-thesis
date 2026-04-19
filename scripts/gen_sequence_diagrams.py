#!/usr/bin/env python3
"""Generate PNG sequence diagrams from Mermaid for all ASCII diagrams in thesis."""
import subprocess, os, sys
from pathlib import Path

MMDC = os.path.expanduser("~/AppData/Roaming/npm/mmdc.cmd")
OUT_DIR = Path("thesis/figures")
OUT_DIR.mkdir(exist_ok=True)

DIAGRAMS = {
    # CH4 diagrams
    "Fig_4.8_Reservation_Lifecycle": """stateDiagram-v2
    [*] --> pending : create_reservation()
    pending --> confirmed : confirm_reservation()
    pending --> cancelled : cancel_reservation()
    confirmed --> cancelled : cancel_reservation()
    confirmed --> checked_in : check_in_guest()
    checked_in --> checked_out : check_out_guest()

    note right of pending : สร้างจาก email + วันที่
    note right of confirmed : ยืนยันแล้ว รอ check-in
    note right of cancelled : ยกเลิก (soft delete)
    note left of checked_in : แขกเข้าพักแล้ว
    note left of checked_out : ออกจากโรงแรมแล้ว""",

    "Fig_4.9_Guest_Identification": """flowchart LR
    subgraph "Guest Identification (ไม่ต้องสร้างบัญชี)"
        A["Email Address<br/>(primary key)"] --> C["จองห้องใหม่"]
        A --> D["ค้นหาประวัติ"]
        A --> E["Auto-register"]
        B["Confirmation Number<br/>(HTL + YYMMDD + seq)"] --> F["ค้นหาการจอง"]
        B --> G["แก้ไข / ยกเลิก"]
        B --> H["Check-in<br/>ที่ front desk"]
    end""",

    "Fig_4.10_Dual_Identity": """flowchart TB
    subgraph GUESTS["GUESTS table (hotel profile)"]
        G1["guest_id (PK)"]
        G2["email (unique)"]
        G3["first/last name"]
        G4["loyalty_tier / points"]
    end
    subgraph USERS["USERS table (login credentials)"]
        U1["user_id (PK)"]
        U2["username (unique)"]
        U3["password_hash (bcrypt)"]
        U4["role: user | admin"]
    end
    USERS -->|"guest_id FK"| GUESTS
    GUESTS --- GF["Guest Chat Flow<br/>(ไม่ต้อง login)<br/>email-only"]
    USERS --- UF["Registered Users<br/>(JWT bearer token)<br/>Admin operations"]""",

    # CH5 Use Cases
    "Fig_5.13_UC_Booking_Sequence": """sequenceDiagram
    participant G as Guest
    participant B as Bot (LangGraph)
    participant DB as PostgreSQL

    G->>B: "I want to book a room"
    B->>G: "What dates and room type?"
    G->>B: "Deluxe, Apr 15-17, 2 guests"
    B->>DB: check_room_availability()
    DB-->>B: [10 Deluxe rooms available]
    B->>G: "Available at 4,500 THB/night<br/>Total: 9,000 THB. Your email?"
    G->>B: "my@email.com"
    B->>DB: auto-register guest
    B->>DB: create_reservation()
    DB-->>B: HTL2604150001 (pending)
    B->>G: "Booked! HTL2604150001<br/>Shall I confirm?"
    G->>B: "Yes, confirm"
    B->>DB: confirm_reservation()
    DB-->>B: status → confirmed
    B->>G: "Confirmed! Email sent."

    Note over B,DB: Booking agent loops:<br/>check → create → confirm""",

    "Fig_5.14_UC_Knowledge_RAG": """sequenceDiagram
    participant G as Guest
    participant LG as LangGraph
    participant Q as Qdrant
    participant LLM as Ollama/OpenRouter

    G->>LG: "WiFi password?"
    LG->>LG: route → knowledge agent
    LG->>Q: embed query → similarity search
    Q-->>LG: top-3 chunks (faq.md)
    LG->>LLM: prompt + user question + context
    LLM-->>LG: grounded answer
    LG->>G: "WiFi: GrandHorizon_Guest<br/>Password: Welcome2026"

    Note over LG,Q: No tool call —<br/>direct RAG invocation""",

    "Fig_5.15_UC_Auth_Flow": """sequenceDiagram
    participant A as Admin
    participant F as FastAPI
    participant DB as PostgreSQL

    A->>F: POST /auth/login {user, password}
    F->>F: check IP rate limit (100/min)
    F->>F: check user rate limit (5/min)
    F->>F: check account lockout
    F->>DB: SELECT * FROM users
    DB-->>F: user record
    F->>F: bcrypt.verify(password)
    F->>F: JWT {sub, role=admin, iat, exp, jti}
    F-->>A: {access_token, user}

    A->>F: GET /admin/sessions<br/>Authorization: Bearer JWT
    F->>F: decode JWT
    F->>F: check jti blocklist
    F->>F: check password_changed_at
    F->>F: verify role=admin
    F-->>A: [sessions list]""",

    "Fig_5.16_UC_Concurrent_Chat": """sequenceDiagram
    participant A as User A
    participant B as User B
    participant F as FastAPI
    participant S as Scaling
    participant O as Ollama

    par User A and B send simultaneously
        A->>F: POST /chat (session A)
        B->>F: POST /chat (session B)
    end

    F->>S: rate_limit(A) → OK
    F->>S: rate_limit(B) → OK
    F->>S: session_lock(A) → acquired
    F->>S: session_lock(B) → acquired
    F->>S: llm_semaphore slot 1 → A
    F->>S: llm_semaphore slot 2 → B

    par Parallel GPU inference
        S->>O: LLM(A)
        S->>O: LLM(B)
    end

    O-->>F: response A (~9s)
    F-->>A: ChatResponse A
    O-->>F: response B (~9s)
    F-->>B: ChatResponse B

    Note over S,O: NUM_PARALLEL=2<br/>Both finish in ~9s""",

    # CH5 5.8-5.13 WORKFLOW diagrams
    "Fig_5.17_Admin_Takeover": """sequenceDiagram
    participant AD as Admin Dashboard
    participant S as Server
    participant GC as Guest Chat

    AD->>S: GET /admin/sessions
    S-->>AD: [sessions, status: bot_active]
    AD->>S: POST /admin/sessions/{id}/takeover
    S-->>AD: status → admin_controlled
    S->>GC: [System] Staff joined

    GC->>S: Guest: "I need help"
    S->>GC: "Staff is assisting you"
    Note right of S: Bot paused, msg saved

    AD->>S: GET /admin/sessions/{id}/messages
    S-->>AD: [full chat history]

    AD->>S: POST /admin/chat/override<br/>"Let me help you with..."
    S->>GC: [Admin] "Let me help..."

    AD->>S: POST /admin/sessions/{id}/release
    S-->>AD: status → bot_active
    S->>GC: [System] AI resumed

    GC->>S: Guest: "Thanks!"
    S->>GC: Bot responds normally""",

    "Fig_5.18_Timetravel": """sequenceDiagram
    participant AD as Admin
    participant S as Server
    participant DB as PostgreSQL

    AD->>S: GET /admin/sessions/{id}/states
    S->>DB: aget_state_history()
    DB-->>S: checkpoints
    S-->>AD: [Step 0: guest msg]<br/>[Step 1: router]<br/>[Step 3: availability]<br/>[Step 5: booking done]

    AD->>S: POST .../rollback<br/>checkpoint_id=Step3
    S->>DB: aupdate_state()
    DB-->>S: forked from checkpoint
    S-->>AD: "Rolled back to step 3"

    AD->>S: POST .../replay<br/>checkpoint=Step3<br/>message="Try Suite"
    S->>DB: ainvoke(new_msg, config)
    DB-->>S: new branch result
    S-->>AD: "Suite available at..."

    Note over S,DB: Time-travel debugging:<br/>fork & replay from any checkpoint""",

    "Fig_5.19_Payment_Flow": """sequenceDiagram
    participant G as Guest
    participant B as Bot
    participant S as Server
    participant DB as Database

    G->>B: "Confirm booking"
    B->>S: generate_payment_link()
    S->>DB: INSERT payment_link<br/>token=UUID, expires=30min
    DB-->>S: OK
    S-->>B: payment URL
    B->>G: "Pay here: /checkout/{token}"

    G->>S: GET /payment/{token}
    S->>DB: lookup booking details
    DB-->>S: {amount, room, dates}
    S-->>G: Payment page

    G->>S: POST /payment/{token}/complete
    S->>DB: status=paid
    DB-->>S: OK
    S-->>G: "Payment successful"

    Note over S,DB: Mock payment only<br/>Production: Stripe/PromptPay""",

    "Fig_5.20_Audit_Flow": """sequenceDiagram
    participant AD as Admin Dashboard
    participant API as /admin/audit API
    participant DB as Database

    AD->>API: GET /admin/audit?<br/>action_prefix=admin.<br/>&actor_username=john_doe<br/>&limit=50&offset=0
    API->>API: require_admin (JWT check)
    API->>DB: list_audit_entries()<br/>COUNT + LIMIT/OFFSET
    DB-->>API: entries + total
    API-->>AD: {entries, total, has_more}
    API->>DB: audit: AUDIT_VIEWED
    Note right of DB: Meta-audit:<br/>ค้นหา audit log<br/>ถูกบันทึกเอง""",

    "Fig_5.21_Knowledge_Cache": """flowchart TB
    A["search_hotel_knowledge(query)"] --> B["KnowledgeCache.get(query)"]
    B -->|"HIT ~1ms"| C["return cached<br/>(content, sources)"]
    B -->|"MISS"| D["Qdrant vector search<br/>~500ms"]
    D --> E["trim to top_k<br/>(no reranker) ~1ms"]
    E --> F["KnowledgeCache.set(...)"]
    F --> G["return (content, sources)"]

    style C fill:#90EE90
    style D fill:#FFB6C1""",

    "Fig_5.22_Manage_Booking": """sequenceDiagram
    participant G as Guest
    participant B as Bot (LangGraph)
    participant DB as PostgreSQL

    G->>B: "Check my booking HTL2604150001"
    B->>DB: get_reservation_details()
    DB-->>B: [booking details]
    B->>G: "Room 404, Apr 15-17<br/>confirmed, 9,000 THB"

    G->>B: "Cancel my booking, plans changed"
    B->>DB: cancel_reservation()<br/>(soft delete: status → cancelled)
    DB-->>B: cancelled
    B->>G: "Booking cancelled.<br/>Cancellation email sent."

    Note over B,DB: No hard deletes —<br/>all state changes via UPDATE""",

    "Fig_5.23_Dynamic_Pricing": """flowchart LR
    subgraph "Dynamic Pricing Multiplier"
        A["30+ วัน<br/>0.85x<br/>Early Bird -15%"] --> B["14-29 วัน<br/>0.90x<br/>Advance -10%"]
        B --> C["7-13 วัน<br/>1.00x<br/>Standard Rate"]
        C --> D["1-6 วัน<br/>1.20x<br/>Last-Minute +20%"]
        D --> E["วันเดียวกัน<br/>1.30x<br/>Same-Day +30%"]
    end
    style A fill:#90EE90
    style B fill:#B0E0B0
    style C fill:#FFFFCC
    style D fill:#FFD580
    style E fill:#FFB6C1""",

    "Fig_5.24_Escalation": """sequenceDiagram
    participant G as Guest
    participant EM as Escalation Monitor
    participant AD as Admin Dashboard

    G->>EM: "terrible service"
    EM->>EM: check_sentiment: HIT<br/>keyword: "terrible"
    EM->>AD: priority: HIGH<br/>auto-escalation
    EM->>EM: session → admin_controlled

    Note over EM: Also triggers on:<br/>• 3x repeated question<br/>• Booking > 50,000 THB<br/>• Penthouse inquiry""",
}


def main():
    print("Generating sequence diagram PNGs...")
    success = 0
    for name, mermaid in DIAGRAMS.items():
        tmp = OUT_DIR / f"_tmp_{name}.mmd"
        out = OUT_DIR / f"{name}.png"
        tmp.write_text(mermaid, encoding="utf-8")
        cmd = [MMDC, "-i", str(tmp), "-o", str(out),
               "-s", "3", "-w", "1600", "-b", "white"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            sz = out.stat().st_size // 1024
            print(f"  [OK] {name}.png ({sz} KB)")
            success += 1
        else:
            print(f"  [FAIL] {name}: {r.stderr[:200]}")
        tmp.unlink(missing_ok=True)
    print(f"\nDone: {success}/{len(DIAGRAMS)} generated")


if __name__ == "__main__":
    main()
