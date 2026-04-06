#!/usr/bin/env python3
"""
Generate all thesis figures as high-resolution PNGs using Mermaid CLI.
Each file is named after its figure reference in the thesis.

Usage:
    python scripts/generate_figures.py
"""
import os
import sys
import subprocess
import json
from pathlib import Path

FIGURES_DIR = Path(__file__).parent.parent / "thesis" / "figures"
FIGURES_DIR.mkdir(exist_ok=True)

# Mermaid config for high-res vertical-aligned diagrams
MERMAID_CONFIG = {
    "theme": "default",
    "themeVariables": {
        "fontSize": "16px",
        "fontFamily": "Segoe UI, Arial, sans-serif"
    }
}

CONFIG_PATH = FIGURES_DIR / "mermaid-config.json"
with open(CONFIG_PATH, "w") as f:
    json.dump(MERMAID_CONFIG, f)


def render(filename: str, mermaid_code: str, width: int = 1600, scale: int = 3):
    """Render a mermaid diagram to PNG."""
    mmd_path = FIGURES_DIR / f"{filename}.mmd"
    png_path = FIGURES_DIR / f"{filename}.png"

    with open(mmd_path, "w", encoding="utf-8") as f:
        f.write(mermaid_code)

    mmdc_path = os.path.expanduser("~/AppData/Roaming/npm/mmdc.cmd")
    if not os.path.exists(mmdc_path):
        mmdc_path = "mmdc"  # fallback to PATH
    cmd = [
        mmdc_path,
        "-i", str(mmd_path),
        "-o", str(png_path),
        "-s", str(scale),
        "-w", str(width),
        "-b", "white",
        "-c", str(CONFIG_PATH),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if result.returncode == 0:
        size_kb = os.path.getsize(png_path) / 1024
        print(f"  [OK] {filename}.png ({size_kb:.0f} KB)")
    else:
        print(f"  [FAIL] {filename}: {result.stderr[:200]}")

    # Clean up .mmd file
    mmd_path.unlink(missing_ok=True)


# =============================================================================
# All 24 figures
# =============================================================================

print("Generating thesis figures...\n")

# --- Chapter 1 ---

render("Fig_1.1_System_Context", """
graph TB
    Guest["🧑 Hotel Guest<br/>(Thai / English)"]
    Staff["👨‍💼 Hotel Staff<br/>(Admin Dashboard)"]
    Frontend["🖥️ Frontend<br/>Next.js 15 + Ant Design"]

    subgraph Backend["FastAPI Server (hotel-api:8088)"]
        Router["HybridRouter<br/>Safety Check"]
        LG["LangGraph Agent<br/>Multi-Agent State Machine"]
        Auth["JWT Auth<br/>+ Rate Limiting"]
        Scaling["Chat Scaling<br/>Semaphore + Cache"]
        Audit["Audit Log"]
    end

    subgraph Services["Docker Services"]
        Ollama["🤖 Ollama<br/>Qwen3.5 Opus 9B<br/>(GPU)"]
        Cloud["☁️ OpenRouter<br/>Qwen3 Max<br/>(Cloud API)"]
        DB["🗄️ PostgreSQL<br/>Rooms, Bookings,<br/>Users, Audit"]
        Qdrant["🔍 Qdrant<br/>Hotel Knowledge<br/>Vectors"]
        Redis["⚡ Redis<br/>Session Cache"]
    end

    Guest -->|"Chat"| Frontend
    Staff -->|"Monitor"| Frontend
    Frontend -->|"HTTP/SSE"| Router
    Router --> LG
    LG -->|"Local LLM"| Ollama
    LG -->|"Cloud LLM"| Cloud
    LG --> DB
    LG --> Qdrant
    Auth --> DB
    Backend --> Redis

    style Backend fill:#e8f4fd,stroke:#1890ff
    style Services fill:#f6ffed,stroke:#52c41a
""")

# --- Chapter 2 ---

render("Fig_2.1_Chatbot_Taxonomy", """
graph LR
    subgraph Gen1["Generation 1<br/>Rule-Based"]
        R1["Keyword Matching"]
        R2["Decision Trees"]
        R3["Fixed Responses"]
    end

    subgraph Gen2["Generation 2<br/>Retrieval-Based"]
        R4["Intent Classification"]
        R5["FAQ Lookup"]
        R6["Template Responses"]
    end

    subgraph Gen3["Generation 3<br/>Generative"]
        R7["LLM-Powered"]
        R8["Free-Form Text"]
        R9["Context-Aware"]
    end

    subgraph Gen4["Generation 4<br/>Agentic ✅"]
        R10["Multi-Agent"]
        R11["Tool Calling"]
        R12["Memory + RAG"]
        R13["Database Integration"]
    end

    Gen1 -->|"Evolution"| Gen2
    Gen2 -->|"Evolution"| Gen3
    Gen3 -->|"Evolution"| Gen4

    style Gen4 fill:#d4edda,stroke:#28a745,stroke-width:3px
""")

render("Fig_2.2_LangGraph_Concept", """
graph TD
    START((START)) --> PA["Primary Assistant<br/>(Router LLM)"]

    PA -->|"ToHotelBooking"| EB["Enter Booking"]
    PA -->|"ToHotelService"| ES["Enter Service"]
    PA -->|"ToHotelKnowledge"| EK["Enter Knowledge"]
    PA -->|"HandleOtherTalk"| OT["Other Talk"]

    EB --> HB["Hotel Booking<br/>Sub-Agent"]
    ES --> HS["Hotel Service<br/>Sub-Agent"]
    EK --> HK["Hotel Knowledge<br/>RAG Search"]
    OT --> HOT["General<br/>Conversation"]

    HB -->|"Tool Call"| BT["Booking Tools<br/>12 tools"]
    BT -->|"Result"| HB
    HB --> END1((END))

    HS -->|"Tool Call"| ST["Service Tools<br/>2 tools"]
    ST -->|"Result"| HS
    HS --> END2((END))

    HK --> END3((END))
    HOT --> END4((END))

    style PA fill:#1890ff,color:#fff
    style HB fill:#52c41a,color:#fff
    style HS fill:#faad14,color:#fff
    style HK fill:#722ed1,color:#fff
    style HOT fill:#eb2f96,color:#fff
""")

render("Fig_2.3_RAG_Pipeline", """
graph TB
    subgraph Ingestion["Offline: Knowledge Ingestion"]
        MD["📄 Hotel Markdown<br/>10 documents"]
        Chunk["✂️ Chunking<br/>Auto-calculated size"]
        Embed["🔢 Embedding<br/>qwen3-embedding-8b<br/>4096 dims"]
        Store["💾 Qdrant<br/>Vector Store"]
        MD --> Chunk --> Embed --> Store
    end

    subgraph Query["Online: Query Pipeline"]
        User["👤 User Question"]
        QEmbed["🔢 Query Embedding"]
        Search["🔍 Vector Search<br/>Top-k Similar"]
        Cache["⚡ Knowledge Cache<br/>500 entries, 5min TTL"]
        Context["📋 Context Assembly"]
        LLM["🤖 LLM Generation"]
        Response["💬 Response"]

        User --> Cache
        Cache -->|"HIT"| Response
        Cache -->|"MISS"| QEmbed
        QEmbed --> Search
        Search --> Context
        Context --> LLM
        LLM --> Response
    end

    Store -.->|"Retrieval"| Search

    style Ingestion fill:#f0f5ff,stroke:#1890ff
    style Query fill:#f6ffed,stroke:#52c41a
""")

# --- Chapter 3 ---

render("Fig_3.1_Framework_Comparison", """
graph TB
    subgraph Comparison["LLM Orchestration Framework Comparison"]
        direction TB
        LG["✅ LangGraph<br/>• State persistence ✓<br/>• Cyclic tool loops ✓<br/>• Time-travel debug ✓<br/>• Production maturity ✓"]
        CR["CrewAI<br/>• Role-based agents<br/>• Growing ecosystem<br/>• No native persistence"]
        AG["AutoGen<br/>• Conversation-based<br/>• Research-focused<br/>• No persistence"]
        LC["LangChain (plain)<br/>• Sequential chains<br/>• Mature ecosystem<br/>• No cyclic loops"]
    end

    style LG fill:#d4edda,stroke:#28a745,stroke-width:3px
    style CR fill:#fff3cd,stroke:#ffc107
    style AG fill:#fff3cd,stroke:#ffc107
    style LC fill:#f8d7da,stroke:#dc3545
""")

# --- Chapter 4 (System Design, numbered as Fig 3.x in thesis) ---

render("Fig_4.1_System_Architecture", """
graph TB
    subgraph Frontend["Frontend (Next.js 15)"]
        Chat["💬 Chat UI<br/>SSE Streaming"]
        Admin["📊 Admin Dashboard"]
        Rooms["🏨 Room Catalog"]
    end

    subgraph API["FastAPI Server :8088"]
        direction TB
        CORS["CORS Middleware"]
        AuthMW["JWT Auth"]
        PII["PII Redactor"]
        RateLimit["Rate Limiter"]
        Router["Hybrid Router"]
        LGA["LangGraph Adapter"]

        subgraph Agents["LangGraph State Machine"]
            PA2["Primary<br/>Router"]
            Booking["Booking<br/>Agent"]
            Service["Service<br/>Agent"]
            Knowledge["Knowledge<br/>Agent"]
            General["General<br/>Talk"]
        end

        ScalingBlock["Scaling Primitives<br/>LLM Semaphore<br/>Session Locks<br/>Knowledge Cache"]
        AuditBlock["Audit Logger"]
    end

    subgraph Infra["Infrastructure"]
        Ollama2["Ollama :11435<br/>RTX 5080 GPU"]
        OR["OpenRouter API<br/>(Cloud Fallback)"]
        PG["PostgreSQL :5433<br/>10 tables"]
        QD["Qdrant :6334<br/>Vector Store"]
        RD["Redis :6380<br/>Session Cache"]
    end

    Frontend -->|"HTTP"| API
    Router --> LGA --> Agents
    PA2 --> Booking
    PA2 --> Service
    PA2 --> Knowledge
    PA2 --> General
    Agents --> Ollama2
    Agents -.->|"Runtime Switch"| OR
    Agents --> PG
    Knowledge --> QD
    API --> RD

    style Frontend fill:#e6f7ff,stroke:#1890ff
    style API fill:#f0f5ff,stroke:#2f54eb
    style Infra fill:#f6ffed,stroke:#52c41a
    style Agents fill:#f9f0ff,stroke:#722ed1
""")

render("Fig_4.2_LangGraph_State_Machine", """
stateDiagram-v2
    [*] --> primary_assistant

    primary_assistant --> enter_booking: ToHotelBooking
    primary_assistant --> enter_service: ToHotelService
    primary_assistant --> enter_knowledge: ToHotelKnowledge
    primary_assistant --> other_talk: HandleOtherTalk
    primary_assistant --> [*]: No tool call

    enter_booking --> hotel_booking
    hotel_booking --> booking_tools: Tool call
    booking_tools --> hotel_booking: Tool result
    hotel_booking --> [*]: Done

    enter_service --> hotel_service
    hotel_service --> service_tools: Tool call
    service_tools --> hotel_service: Tool result
    hotel_service --> [*]: Done

    enter_knowledge --> hotel_knowledge
    hotel_knowledge --> [*]: RAG response

    other_talk --> handle_other
    handle_other --> [*]: Direct response
""")

render("Fig_4.3_ER_Diagram", """
erDiagram
    ROOM_TYPES ||--o{ ROOMS : contains
    ROOMS ||--o{ RESERVATIONS : booked_as
    GUESTS ||--o{ RESERVATIONS : makes
    GUESTS ||--o| USERS : has_account
    RESERVATIONS ||--o{ SERVICE_REQUESTS : generates
    RESERVATIONS ||--o{ PAYMENT_LINKS : has
    USERS ||--o{ AUDIT_LOG : performs
    ROOMS ||--o{ HOUSEKEEPING : scheduled

    ROOM_TYPES {
        int room_type_id PK
        string name
        decimal base_price
        int max_occupancy
    }
    ROOMS {
        int room_id PK
        string room_number
        int floor
        string status
    }
    GUESTS {
        int guest_id PK
        string email UK
        string first_name
        string last_name
    }
    RESERVATIONS {
        int reservation_id PK
        string confirmation_number UK
        date check_in_date
        date check_out_date
        string status
        decimal total_amount
    }
    USERS {
        int user_id PK
        string username UK
        string password_hash
        string role
    }
    AUDIT_LOG {
        bigint audit_id PK
        string action
        jsonb details
        timestamp created_at
    }
""")

render("Fig_4.4_RAG_Pipeline_Detail", """
graph TB
    subgraph Docs["Hotel Knowledge Base"]
        D1["🍽️ dining.md"]
        D2["🧖 spa.md"]
        D3["🏊 facilities.md"]
        D4["📋 policies.md"]
        D5["❓ FAQ.md"]
        D6["🚗 transport.md"]
        D7["🛏️ rooms.md"]
        D8["+ 3 more..."]
    end

    Chunk["✂️ Auto Chunk<br/>~3,200 chars<br/>20% overlap"]
    EmbedModel["🔢 qwen3-embedding-8b<br/>4096 dimensions"]
    QdrantStore["💾 Qdrant Collection<br/>hotel_knowledge"]

    subgraph QueryTime["Query Time"]
        QInput["User: 'What time is breakfast?'"]
        QEmbed2["🔢 Query Embedding"]
        VSearch["🔍 Vector Search<br/>Top-30 candidates"]
        TopK["📊 Top-3 Results<br/>(No reranker)"]
        CtxInject["📋 Context Injection<br/>max 2,000 chars"]
        LLMCall["🤖 LLM Call<br/>(with context)"]
        Answer["💬 'Breakfast is served<br/>6:30-10:30 AM at<br/>The Grand Dining Room'"]
    end

    Docs --> Chunk --> EmbedModel --> QdrantStore
    QInput --> QEmbed2 --> VSearch
    QdrantStore -.-> VSearch
    VSearch --> TopK --> CtxInject --> LLMCall --> Answer

    style Docs fill:#fff7e6,stroke:#fa8c16
    style QueryTime fill:#f0f5ff,stroke:#1890ff
""")

render("Fig_4.5_JWT_Auth_Flow", """
sequenceDiagram
    participant F as Frontend
    participant S as FastAPI Server
    participant DB as PostgreSQL

    F->>S: POST /auth/login<br/>{username, password}
    S->>DB: get_user_by_username()
    DB-->>S: user row (password_hash)
    S->>S: bcrypt.checkpw(password, hash)
    S->>S: create_access_token()<br/>{sub, role, user_id, iat, exp, jti}
    S-->>F: {access_token, token_type, user}

    Note over F: Store JWT

    F->>S: GET /admin/sessions<br/>Authorization: Bearer <token>
    S->>S: decode_access_token()
    S->>S: check jti blocklist
    S->>S: check password_changed_at vs iat
    S->>DB: get_user_by_username() [cached]
    S->>S: require_admin (role check)
    S-->>F: 200 {sessions data}

    Note over F,S: 401 if token invalid/expired/revoked<br/>403 if role != admin
""")

render("Fig_4.7_Docker_Topology", """
graph TB
    subgraph Network["hotel-ai-network (Docker Bridge)"]
        direction TB
        OL["🤖 hotel-ollama:11434<br/>Ollama LLM Server<br/>GPU: RTX 5080<br/>NUM_PARALLEL=2"]
        API["⚙️ hotel-api:8088<br/>FastAPI + LangGraph<br/>depends_on: all<br/>--reload"]
        PG["🗄️ hotel-db:5432<br/>PostgreSQL 16<br/>init-hotel.sql<br/>10 tables"]
        QD["🔍 hotel-qdrant:6333<br/>Qdrant Vector DB<br/>hotel_knowledge"]
        RD["⚡ hotel-redis:6379<br/>Redis 7<br/>Session Cache"]
    end

    Host["🖥️ Host Machine"]
    Host -->|":11435"| OL
    Host -->|":8088"| API
    Host -->|":5433"| PG
    Host -->|":6334"| QD
    Host -->|":6380"| RD

    API --> OL
    API --> PG
    API --> QD
    API --> RD

    style Network fill:#f0f5ff,stroke:#1890ff
""")

# --- Chapter 5 (Implementation, numbered as Fig 4.x) ---

render("Fig_5.1_Runtime_Model_Switch", """
sequenceDiagram
    participant Admin
    participant API as FastAPI Server
    participant Config as RuntimeLLMConfig
    participant Ollama
    participant Cloud as OpenRouter

    Admin->>API: PUT /settings/llm<br/>{backend: "openrouter"}
    API->>Config: update(backend="openrouter")
    Config-->>API: {changes: {backend: ollama→openrouter}}
    API-->>Admin: 200 OK

    Note over Config: Thread-safe singleton update

    participant Guest
    Guest->>API: POST /chat {message}
    API->>Config: get_runtime_llm_config()
    Config-->>API: backend=openrouter
    API->>Cloud: Chat completion
    Cloud-->>API: Response
    API-->>Guest: ChatResponse

    Admin->>API: PUT /settings/llm<br/>{backend: "ollama"}
    API->>Config: update(backend="ollama")

    Guest->>API: POST /chat {message}
    API->>Ollama: Chat completion
    Ollama-->>API: Response
    API-->>Guest: ChatResponse
""")

render("Fig_5.2_Prompt_Structure", """
graph TB
    subgraph MainPrompt["main_prompt (~2,800 chars)"]
        Lang["🌐 Language Detection<br/>CRITICAL RULE:<br/>EN→EN, TH→TH, never mix"]
        Date["📅 Date Handling<br/>Current: {date} {time}<br/>Partial dates → current/next month"]
        Tools["🔧 Tool Catalog<br/>search_hotel_knowledge<br/>check_room_availability<br/>create_reservation<br/>...7 more tools"]
        Rules["📏 Response Rules<br/>Complete answers<br/>Use tools, never memory<br/>Thai honorifics"]
    end

    subgraph BookingFlow["booking_flow"]
        BF["Multi-step guide:<br/>1. Dates → 2. Room type →<br/>3. Guests → 4. Email →<br/>calculate_dynamic_price →<br/>create_reservation →<br/>check_upsell_opportunity"]
    end

    subgraph ServicePrompt["service_prompt"]
        SP["1. Acknowledge request<br/>2. Identify reservation<br/>3. Create service request<br/>4. Estimated response time"]
    end

    MainPrompt -->|"+ booking"| BookingAgent["Booking Sub-Agent"]
    MainPrompt -->|"+ service"| ServiceAgent["Service Sub-Agent"]
    MainPrompt -->|"alone"| KnowledgeAgent["Knowledge Sub-Agent"]

    BookingFlow --> BookingAgent
    ServicePrompt --> ServiceAgent

    style MainPrompt fill:#e6f7ff,stroke:#1890ff
""")

render("Fig_5.3_PII_Redaction", """
graph LR
    Input["👤 Guest Input<br/>'My card is<br/>4111-1111-1111-1111'"]
    Regex["🔍 PII Regex<br/>6 Patterns:<br/>• CREDIT_CARD<br/>• THAI_NATIONAL_ID<br/>• PASSPORT<br/>• PHONE_TH<br/>• PHONE_INTL<br/>• EMAIL"]
    Redacted["🛡️ Redacted Text<br/>'My card is<br/>[CREDIT_CARD]'"]
    LLM["🤖 LLM<br/>Never sees<br/>real card number"]
    Response["💬 Response<br/>Does not echo<br/>the card number"]

    Input --> Regex --> Redacted --> LLM --> Response

    style Regex fill:#fff2e8,stroke:#fa541c
    style Redacted fill:#f6ffed,stroke:#52c41a
""")

render("Fig_5.4_Scaling_Pipeline", """
graph TB
    Request["POST /chat<br/>{message, session_id}"]
    RL["🚦 Chat Rate Limiter<br/>30 msgs/min per session<br/>→ 429 if exceeded"]
    SL["🔒 Session Lock<br/>asyncio.Lock per session_id<br/>Serializes same-session requests"]
    Safety["🛡️ Safety Check<br/>+ PII Redaction"]
    Sem["⏳ LLM Semaphore<br/>2 concurrent slots<br/>45s queue timeout<br/>→ 503 if saturated"]
    Cache["⚡ Knowledge Cache<br/>500 entries, 5min TTL<br/>→ Skip Qdrant if cached"]
    LG2["🤖 LangGraph Agent<br/>Route → Sub-Agent → Tools"]
    Ollama3["🖥️ Ollama GPU<br/>NUM_PARALLEL=2"]
    Resp["💬 Response"]

    Request --> RL --> SL --> Safety --> Sem --> LG2
    LG2 --> Cache
    Cache -->|"HIT"| Resp
    Cache -->|"MISS → Qdrant"| LG2
    LG2 --> Ollama3 --> Resp

    style RL fill:#fff2e8,stroke:#fa541c
    style SL fill:#e6f7ff,stroke:#1890ff
    style Sem fill:#fff7e6,stroke:#fa8c16
    style Cache fill:#f6ffed,stroke:#52c41a
""")

# --- Chapter 6 (Testing, numbered as Fig 5.x) ---

render("Fig_6.1_Accuracy_Comparison", """
xychart-beta
    title "Model Accuracy Comparison (25 Test Cases)"
    x-axis ["Knowledge<br/>(8)", "Booking<br/>(6)", "Greeting<br/>(4)", "Language<br/>(3)", "Edge<br/>(4)", "Overall<br/>(25)"]
    y-axis "Accuracy (%)" 0 --> 100
    bar [100, 100, 75, 100, 75, 92]
    bar [100, 100, 100, 100, 100, 100]
""")

render("Fig_6.2_Test_Coverage_Pie", """
pie title "Infrastructure Test Coverage (193 tests)"
    "Auth Baseline (72)" : 72
    "Auth Hardening (38)" : 38
    "Audit + DB Scaling (46)" : 46
    "Chat Scaling (37)" : 37
""")

render("Fig_6.3_Before_After_Optimization", """
xychart-beta
    title "Performance Optimization Results"
    x-axis ["Warm Chat<br/>Latency", "5 Concurrent<br/>Chats", "RAG Query<br/>(cached)", "Prompt<br/>Size"]
    y-axis "Value (relative)" 0 --> 100
    bar [100, 100, 100, 100]
    bar [28, 3, 0.2, 51]
""")

render("Fig_6.4_Kappa_Matrix", """
graph TB
    subgraph Matrix["Cohen's Kappa Confusion Matrix (κ = 0.000)"]
        direction TB
        subgraph Row1[" "]
            direction LR
            H0[" "]
            H1["Cloud PASS"]
            H2["Cloud FAIL"]
        end
        subgraph Row2[" "]
            direction LR
            L1["Local PASS"]
            C11["✅ 23<br/>Both Pass"]
            C12["0<br/>Local Pass<br/>Cloud Fail"]
        end
        subgraph Row3[" "]
            direction LR
            L2["Local FAIL"]
            C21["❌ 2<br/>Local Fail<br/>Cloud Pass<br/>(G03, E03)"]
            C22["0<br/>Both Fail"]
        end
    end

    style C11 fill:#d4edda,stroke:#28a745,stroke-width:3px
    style C21 fill:#f8d7da,stroke:#dc3545,stroke-width:2px
    style C12 fill:#f0f0f0,stroke:#ccc
    style C22 fill:#f0f0f0,stroke:#ccc
""")

# --- Chapter 7 (Discussion, numbered as Fig 6.x) ---

render("Fig_7.1_Cost_Accuracy_Latency", """
graph TB
    subgraph Triangle["Cost — Accuracy — Latency Trade-off"]
        Local["🏠 Local 9B<br/>Cost: $0/query<br/>Accuracy: 92%<br/>p50 Latency: 9.0s<br/>Privacy: ✅ On-premise<br/>Concurrent: 2 users"]
        Cloud["☁️ Cloud (Qwen3 Max)<br/>Cost: ~$0.005/query<br/>Accuracy: 100%<br/>p50 Latency: 6.7s<br/>Privacy: ❌ API<br/>Concurrent: Unlimited"]
        Hybrid["🔄 Hybrid Strategy<br/>Local for routine (92%)<br/>Cloud for complex (8%)<br/>Runtime switchable"]
    end

    Local -->|"Fallback for<br/>complex queries"| Cloud
    Cloud -->|"Switch back<br/>when traffic drops"| Local
    Local --> Hybrid
    Cloud --> Hybrid

    style Local fill:#d4edda,stroke:#28a745
    style Cloud fill:#cce5ff,stroke:#004085
    style Hybrid fill:#fff3cd,stroke:#856404
""")

render("Fig_7.2_Orchestrator_Comparison", """
graph TB
    subgraph Matrix["Orchestrator Decision Matrix"]
        direction TB
        LGW["✅ LangGraph (Selected)<br/>+ State persistence (PostgreSQL)<br/>+ Cyclic tool loops<br/>+ Time-travel debugging<br/>+ Checkpoint replay<br/>+ Production-grade"]
        CRW["⚠️ CrewAI<br/>+ Role-based agents<br/>- No native persistence<br/>- Limited debugging<br/>- Growing ecosystem"]
        AGW["⚠️ AutoGen<br/>+ Conversation-based<br/>- Research-focused<br/>- No persistence<br/>- Complex setup"]
    end

    style LGW fill:#d4edda,stroke:#28a745,stroke-width:3px
    style CRW fill:#fff3cd,stroke:#ffc107
    style AGW fill:#fff3cd,stroke:#ffc107
""")

# --- Access control matrix (Fig 3.6 equivalent) ---
render("Fig_4.6_Access_Control_Matrix", """
graph TB
    subgraph ACL["Access Control Matrix"]
        direction TB
        H1["Endpoint Category"]
        H2["No Token → 401"]
        H3["User Token → varies"]
        H4["Admin Token → 200"]
    end

    subgraph Public["Public Endpoints (200 for all)"]
        P1["/chat, /chat/stream"]
        P2["/rooms, /rooms/availability"]
        P3["/health, /healthz"]
        P4["GET /settings/llm"]
    end

    subgraph UserOnly["User Endpoints (401 without token)"]
        U1["/auth/me → 200"]
        U2["/auth/logout → 200"]
        U3["/auth/me/password → 200"]
    end

    subgraph AdminOnly["Admin Endpoints (401/403 without admin)"]
        A1["/admin/* (15 endpoints) → 403 for user"]
        A2["/dashboard/* (5 endpoints) → 403 for user"]
        A3["PUT /settings/llm → 403 for user"]
    end

    style Public fill:#d4edda,stroke:#28a745
    style UserOnly fill:#e6f7ff,stroke:#1890ff
    style AdminOnly fill:#fff2e8,stroke:#fa541c
""")

# Summary
print(f"\nAll figures generated in: {FIGURES_DIR}")
print(f"Total: {len(list(FIGURES_DIR.glob('*.png')))} PNG files")
