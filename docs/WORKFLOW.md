# Hotel AI Virtual Assistant - Workflow Documentation

## System Overview

The Grand Horizon Hotel AI Virtual Assistant is a chatbot embedded on the hotel website.
Guests interact via text (Thai or English) to get hotel information and make reservations.
No account creation required - guests are identified by email or booking confirmation number only.

## Architecture

```
                          +------------------+
                          |   Hotel Website  |
                          |   (Frontend UI)  |
                          +--------+---------+
                                   |
                              POST /chat
                                   |
                          +--------v---------+
                          |   FastAPI Server  |
                          |   (port 8088)     |
                          +--------+---------+
                                   |
                          +--------v---------+
                          |  Hybrid Router    |
                          |  (safety filter)  |
                          +--------+---------+
                                   |
                          +--------v---------+
                          |  LangGraph Agent  |
                          |  (state machine)  |
                          +--------+---------+
                                   |
              +--------------------+--------------------+
              |                    |                    |
     +--------v-------+  +--------v-------+  +---------v------+
     | Hotel Booking   |  | Hotel Service  |  | Hotel Knowledge|
     | (sub-agent)     |  | (sub-agent)    |  | (RAG search)   |
     +--------+-------+  +--------+-------+  +---------+------+
              |                    |                    |
     +--------v-------+  +--------v-------+  +---------v------+
     | PostgreSQL      |  | PostgreSQL     |  | Qdrant + OpenR.|
     | (reservations)  |  | (svc requests) |  | (embeddings)   |
     +----------------+  +----------------+  +----------------+
```

## LLM Configuration

```
  +-------------------+       PUT /settings/llm       +-------------------+
  |  Ollama (local)   | <---------------------------> |  OpenRouter (cloud)|
  |  qwen3.5-opus:9b  |    switchable at runtime      |  qwen/qwen3-max   |
  |  port 11435       |    no restart needed           |  minimax-m2.7     |
  |  FREE             |                                |  any model        |
  +-------------------+                                +-------------------+
         |                                                     |
         |  Per-model presets auto-applied:                     |
         |  - temperature, max_tokens, thinking                |
         |  - rate limiter (20 req/min) for cloud              |
         +-----------------------------------------------------+
```

## Guest Interaction Workflow

### Flow 1: Hotel Information (Knowledge Q&A)

```
  Guest                          Bot                         Qdrant
    |                             |                            |
    |  "What time is breakfast?"  |                            |
    |---------------------------->|                            |
    |                             |  search_hotel_knowledge()  |
    |                             |--------------------------->|
    |                             |  [dining_services.md]      |
    |                             |<---------------------------|
    |  "Breakfast is served       |                            |
    |   6:30-10:30 AM at the      |                            |
    |   Grand Dining Room,        |                            |
    |   1st floor near lobby"     |                            |
    |<----------------------------|                            |
```

### Flow 2: Room Booking (Multi-Step)

```
  Guest                          Bot                       PostgreSQL
    |                             |                            |
    |  "I want to book a room"    |                            |
    |---------------------------->|                            |
    |  "What dates and room       |                            |
    |   type do you prefer?"      |                            |
    |<----------------------------|                            |
    |                             |                            |
    |  "Deluxe, Apr 15-17,        |                            |
    |   2 guests"                 |                            |
    |---------------------------->|                            |
    |                             |  check_room_availability() |
    |                             |--------------------------->|
    |                             |  [10 Deluxe rooms avail]   |
    |                             |<---------------------------|
    |  "Deluxe rooms available    |                            |
    |   at 4,500 THB/night.       |                            |
    |   Total: 9,000 THB.         |                            |
    |   May I have your email?"   |                            |
    |<----------------------------|                            |
    |                             |                            |
    |  "my.email@gmail.com"       |                            |
    |---------------------------->|                            |
    |                             |  auto-register guest       |
    |                             |  create_reservation()      |
    |                             |--------------------------->|
    |                             |  HTL2604150001 (pending)   |
    |                             |<---------------------------|
    |  "Booked! Confirmation:     |                            |
    |   HTL2604150001             |                            |
    |   Shall I confirm now?"     |                            |
    |<----------------------------|                            |
    |                             |                            |
    |  "Yes, confirm"             |                            |
    |---------------------------->|                            |
    |                             |  confirm_reservation()     |
    |                             |--------------------------->|
    |                             |  status -> confirmed       |
    |                             |<---------------------------|
    |  "Confirmed! Email sent."   |                            |
    |<----------------------------|                            |
```

### Flow 3: Manage Existing Booking

```
  Guest                          Bot                       PostgreSQL
    |                             |                            |
    |  "Check my booking          |                            |
    |   HTL2604150001"            |                            |
    |---------------------------->|                            |
    |                             |  get_reservation_details() |
    |                             |--------------------------->|
    |                             |  [booking details]         |
    |                             |<---------------------------|
    |  "Room 404, Apr 15-17,      |                            |
    |   confirmed, 9,000 THB"     |                            |
    |<----------------------------|                            |
    |                             |                            |
    |  "Cancel my booking,        |                            |
    |   plans changed"            |                            |
    |---------------------------->|                            |
    |                             |  cancel_reservation()      |
    |                             |  (soft delete: status ->   |
    |                             |   'cancelled')             |
    |                             |--------------------------->|
    |  "Booking cancelled.        |                            |
    |   Cancellation email sent." |                            |
    |<----------------------------|                            |
```

### Flow 4: Hotel Arrival (Front Desk)

```
  Guest arrives at hotel
    |
    v
  Front Desk: "May I have your email or confirmation number?"
    |
    |  Guest: "HTL2604150001" or "my.email@gmail.com"
    |
    v
  Staff verifies in system:
    - Reservation status = confirmed
    - Room assignment = 404 (Deluxe, City View)
    - Dates match
    |
    v
  Check-in processed (status -> checked_in)
    |
    v
  Guest pays at front desk (demo: no real transaction)
    |
    v
  Guest receives room key
```

## LangGraph Agent State Machine

```
                            START
                              |
                              v
                    +-------------------+
                    | primary_assistant |
                    | (intent router)   |
                    +---+---+---+---+---+
                        |   |   |   |
           +------------+   |   |   +------------+
           |                |   |                |
           v                v   v                v
  +----------------+ +----------+ +--------------+
  | hotel_booking  | | hotel    | | hotel        |
  | (reservation   | | service  | | knowledge   |
  |  operations)   | | (towels, | | (RAG search)|
  +-------+--------+ | spa...) | +--------------+
          |           +----+----+        |
          v                v             v
  +----------------+ +----------+       END
  | booking_tools  | | service  |
  | - check_avail  | | tools    |
  | - create_res   | +----+----+
  | - confirm      |      |
  | - update       |      v
  | - cancel       |     END
  | - check_in     |
  | - check_out    |
  +-------+--------+
          |
          v (loop back for multi-tool calls)
    hotel_booking
          |
          v
         END
```

## Reservation Status Lifecycle

```
  create_reservation()        confirm_reservation()
         |                           |
         v                           v
     +--------+              +-----------+
     | pending | ----------> | confirmed |
     +--------+              +-----------+
         |                        |    |
         |   cancel_reservation() |    |  check_in_guest()
         |         |              |    |
         v         v              v    v
   +-----------+              +------------+
   | cancelled |              | checked_in |
   +-----------+              +------------+
                                     |
                                     |  check_out_guest()
                                     v
                              +--------------+
                              | checked_out  |
                              +--------------+

  * No hard deletes - all state changes via UPDATE
  * No real payment processing - demo stage
  * payment_status stays 'pending' throughout
```

## Guest Identification

```
  No account creation required.
  Guest identified by:

  +-------------------+     +---------------------------+
  | Email address     |     | Confirmation number       |
  | (primary key)     |     | (HTL + YYMMDD + seq)      |
  |                   |     |                           |
  | Used for:         |     | Used for:                 |
  | - New bookings    |     | - Lookup existing booking |
  | - Lookup history  |     | - Modify / cancel         |
  | - Auto-register   |     | - Check-in at front desk  |
  +-------------------+     +---------------------------+

  When a new email is used for booking:
  -> Guest record auto-created (no registration form)
  -> Loyalty tier = Standard, points = 0
```

## Flow 5: Admin Monitoring & Intervention

```
  Admin Dashboard                    Server                     Guest Chat
       |                               |                            |
       |  GET /admin/sessions           |                            |
       |------------------------------>|                            |
       |  [sessions with previews,     |                            |
       |   status: bot_active]         |                            |
       |<------------------------------|                            |
       |                               |                            |
       |  (sees guest asking about     |                            |
       |   a complex request)          |                            |
       |                               |                            |
       |  POST /admin/sessions/        |                            |
       |       {id}/takeover           |                            |
       |------------------------------>|                            |
       |  status -> admin_controlled   |  [System] Staff joined     |
       |<------------------------------|--------------------------->|
       |                               |                            |
       |                               |  Guest: "I need help"      |
       |                               |<---------------------------|
       |                               |  "Staff is assisting you"  |
       |                               |--------------------------->|
       |                               |  (bot paused, msg saved)   |
       |                               |                            |
       |  GET /admin/sessions/         |                            |
       |       {id}/messages           |                            |
       |------------------------------>|                            |
       |  [full chat history]          |                            |
       |<------------------------------|                            |
       |                               |                            |
       |  POST /admin/chat/override    |                            |
       |  "Let me help you with..."    |                            |
       |------------------------------>|  [Admin] "Let me help..."  |
       |                               |--------------------------->|
       |                               |                            |
       |  POST /admin/sessions/        |                            |
       |       {id}/release            |                            |
       |------------------------------>|                            |
       |  status -> bot_active         |  [System] AI resumed       |
       |<------------------------------|--------------------------->|
       |                               |                            |
       |                               |  Guest: "Thanks!"          |
       |                               |<---------------------------|
       |                               |  Bot responds normally     |
       |                               |--------------------------->|
```

## API Endpoints

### Guest-Facing

| Method | Path | Purpose |
|--------|------|---------|
| POST | /chat | Main chatbot conversation |
| POST | /chat/stream | Streaming chat (SSE) |
| GET | /rooms | Room types with availability |
| GET | /rooms/availability | Calendar availability |
| GET | /rooms/{id} | Room details with pricing |
| POST | /tools/book | Direct booking operations |
| GET | /bookings | List bookings (by email/status) |
| GET | /bookings/{id} | Single booking details |
| GET | /sessions/{id}/messages | Conversation history |

### Admin Operations

| Method | Path | Purpose |
|--------|------|---------|
| PUT | /admin/rooms/{id}/status | Set room status (available/maintenance/cleaning) |
| PUT | /admin/bookings/{id}/status | Override booking status (check-in, no-show, etc.) |
| POST | /admin/chat/override | Send staff message to guest session |
| GET | /admin/sessions | List active sessions with previews |
| GET | /admin/sessions/{id}/messages | View full session chat history |
| POST | /admin/sessions/{id}/takeover | Pause bot, admin takes over conversation |
| POST | /admin/sessions/{id}/release | Resume bot for session |

### Dashboard Monitoring

| Method | Path | Purpose |
|--------|------|---------|
| GET | /dashboard/stats | Overview: occupancy, revenue, check-ins/outs |
| GET | /dashboard/bookings/recent | Live feed of latest bookings |
| GET | /dashboard/sessions | Chatbot session statistics (24h) |
| GET | /dashboard/rooms | Room status breakdown by floor |
| GET | /dashboard/revenue | Revenue by room type, source, daily trend |

### System

| Method | Path | Purpose |
|--------|------|---------|
| GET | /healthz | Load balancer health check |
| GET | /health | Component health status |
| GET | /settings/llm | Current LLM configuration |
| PUT | /settings/llm | Switch model at runtime |
| GET | /settings/models | Available models list |
| POST | /guests | Register guest |
| GET | /guests/{email} | Guest lookup |
| POST | /sessions | Create session |
| POST | /feedback | Submit response feedback |
| GET | /feedback/stats | Feedback statistics |

## Docker Stack

| Container | Port | Service |
|-----------|------|---------|
| hotel-ollama | 11435 | Local LLM (qwen3.5-opus:9b) |
| hotel-db | 5433 | PostgreSQL (hotel database) |
| hotel-redis | 6380 | Redis (session cache) |
| hotel-qdrant | 6334 | Qdrant (knowledge vectors) |
| hotel-api | 8088 | FastAPI server |

```bash
# Start
docker compose -p hoteai -f deploy/compose/docker-compose.hotel.yaml --env-file .env up -d

# Populate data
docker compose -p hoteai ... exec hotel-api python scripts/generate_hotel_dataset.py

# Ingest knowledge
docker compose -p hoteai ... exec hotel-api python scripts/ingest_hotel_knowledge.py

# Run tests
python scripts/test_hotel_workflow.py
```

## Test Results (94% pass rate)

| Part | Tests | Description |
|------|-------|-------------|
| A | 7/7 | Infrastructure, model switching, rooms |
| B | 6/6 | Knowledge/RAG (breakfast, WiFi, spa, pets, transport) |
| C | 9/10 | Full booking lifecycle (create, confirm, update, cancel) |
| D | 4/4 | Advanced scenarios (multi-room, natural dates, Thai) |
| E | 3/4 | Service requests (towels, spa, airport) |
| F | 3/3 | Edge cases (past dates, max guests, off-topic) |
