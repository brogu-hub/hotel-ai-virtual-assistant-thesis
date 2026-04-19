#!/usr/bin/env python3
"""Generate Use Case box diagrams as PNG."""
import subprocess, os
from pathlib import Path

MMDC = os.path.expanduser("~/AppData/Roaming/npm/mmdc.cmd")
OUT_DIR = Path("thesis/figures")

DIAGRAMS = {
    "Fig_5.25_UC_Guest": """flowchart LR
    subgraph "Hotel AI Virtual Assistant"
        UC1["UC1: ถามข้อมูลโรงแรม<br/>(Knowledge Q&A)"]
        UC2["UC2: จองห้องพัก<br/>(Room Booking)"]
        UC3["UC3: แก้ไข/ยกเลิกการจอง<br/>(Modify/Cancel)"]
        UC4["UC4: ขอบริการ<br/>(Service Request)"]
        UC5["UC5: Check-in/Check-out"]
        UC6["UC6: สนทนาทั่วไป<br/>(General Chat)"]
    end
    G["🧑 Guest<br/>(แขก)"] --> UC1
    G --> UC2
    G --> UC3
    G --> UC4
    G --> UC5
    G --> UC6

    style G fill:#4FC3F7,color:#000
    style UC1 fill:#E8F5E9
    style UC2 fill:#E3F2FD
    style UC3 fill:#FFF3E0
    style UC4 fill:#F3E5F5
    style UC5 fill:#E0F7FA
    style UC6 fill:#FFF9C4""",

    "Fig_5.26_UC_Admin": """flowchart LR
    subgraph "Hotel Admin Dashboard"
        UC7["UC7: ดู live chat sessions"]
        UC8["UC8: Take over / release chat"]
        UC9["UC9: จัดการสถานะห้อง"]
        UC10["UC10: จัดการ booking"]
        UC11["UC11: ดู audit logs"]
        UC12["UC12: สลับ LLM model"]
    end
    A["👤 Admin<br/>(พนักงาน)"] --> UC7
    A --> UC8
    A --> UC9
    A --> UC10
    A --> UC11
    A --> UC12

    style A fill:#EF5350,color:#FFF
    style UC7 fill:#E8F5E9
    style UC8 fill:#FFEBEE
    style UC9 fill:#E3F2FD
    style UC10 fill:#FFF3E0
    style UC11 fill:#F3E5F5
    style UC12 fill:#E0F7FA""",

    "Fig_5.27_LangGraph_Loop": """sequenceDiagram
    participant PA as Primary Assistant
    participant R as Router
    participant BA as Booking Agent
    participant BT as Booking Tools
    participant DB as PostgreSQL

    Note over PA: Loop 1: Route
    PA->>R: "I want to book a Deluxe room for Apr 15-17"
    R->>R: emit ToHotelBooking
    R->>BA: enter_booking

    Note over BA: Loop 2: Check availability
    BA->>BT: check_room_availability()
    BT->>DB: SQL query
    DB-->>BT: [10 rooms]
    BT-->>BA: rooms list (cyclic edge)

    Note over BA: Loop 3: Create reservation
    BA->>BT: create_reservation()
    BT->>DB: INSERT
    DB-->>BT: HTL2604150001
    BT-->>BA: confirmation (cyclic edge)

    Note over BA: Loop 4: No more tools → respond
    BA-->>PA: "Booked! HTL2604150001"
    PA-->>PA: END""",

    "Fig_5.28_Auto_Escalation": """flowchart TB
    A["Guest Message"] --> B{"Sentiment Check"}
    B -->|"Keywords: terrible, worst,<br/>แย่มาก, ร้องเรียน"| C["🔴 HIGH Priority<br/>Auto-Escalate"]
    B -->|"Normal"| D{"Repetition Check"}
    D -->|"3+ similar messages<br/>>70% similarity"| C
    D -->|"Normal"| E{"High-Value Check"}
    E -->|"Booking > 50,000 THB<br/>or Penthouse"| C
    E -->|"Normal"| F["✅ Continue with Bot"]
    C --> G["session → admin_controlled<br/>Notify Admin Dashboard"]

    style C fill:#FFCDD2
    style F fill:#C8E6C9
    style G fill:#FFEBEE""",
}

def main():
    print("Generating use case diagram PNGs...")
    for name, mermaid in DIAGRAMS.items():
        tmp = OUT_DIR / f"_tmp_{name}.mmd"
        out = OUT_DIR / f"{name}.png"
        tmp.write_text(mermaid, encoding="utf-8")
        cmd = [MMDC, "-i", str(tmp), "-o", str(out), "-s", "3", "-w", "1600", "-b", "white"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode == 0:
            print(f"  [OK] {name}.png ({out.stat().st_size // 1024} KB)")
        else:
            print(f"  [FAIL] {name}: {r.stderr[:200]}")
        tmp.unlink(missing_ok=True)

if __name__ == "__main__":
    main()
