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

## Authentication & Authorization

Two identity systems coexist:

```
  +----------------------+              +--------------------------+
  |  GUESTS table        |              |  USERS table             |
  |  (hotel profile)     |              |  (login credentials)     |
  +----------------------+              +--------------------------+
  | guest_id (PK)        |<------+------| guest_id (FK, nullable)  |
  | email (unique)       |       |      | user_id (PK)             |
  | first/last name      |       |      | username (unique)        |
  | phone, nationality   |       |      | email (unique)           |
  | loyalty_tier/points  |       |      | password_hash (bcrypt)   |
  | preferences          |       |      | role ('user' | 'admin')  |
  +----------------------+       |      | is_active, last_login    |
         ^                       |      +--------------------------+
         |                       |              |
         | used by               |              | used by
         |                       |              |
  +-----------------------+      |      +---------------------------+
  | Guest chat flow       |      |      | Registered users          |
  | (no login required)   |      |      | (website login)           |
  | email-only identity   |      |      | JWT bearer token          |
  +-----------------------+      |      +---------------------------+
                                 |              |
                                 |              | when user has booking history
                                 +--------------+ users.guest_id -> guests.guest_id
```

### Auth model

- **Guest chat flow unchanged** — `/chat`, `/rooms`, `/bookings`, `/guests` still use email-only identification. No login needed to chat with the bot or make a reservation.
- **Registered users** log in via `/auth/login` and receive a JWT. Used for website accounts that want booking history across sessions.
- **Admins** are hotel staff. Admin JWT is required for `/admin/*`, `/dashboard/*`, and `PUT /settings/llm`.
- **Default admin** is seeded on first startup from `DEFAULT_ADMIN_USERNAME` / `DEFAULT_ADMIN_PASSWORD` env vars (default: `admin` / `admin123` — **MUST** be changed in production).

### Login / registration flow

```
  Frontend                Server                      DB
     |                      |                         |
     | POST /auth/register  |                         |
     | {username, email,    |                         |
     |  password, full_name}|                         |
     |--------------------->|                         |
     |                      | bcrypt.hashpw(password) |
     |                      | INSERT users (role=user)|
     |                      |------------------------>|
     |                      |<------------------------|
     |                      |                         |
     |                      | jwt.encode({sub, role,  |
     |                      |   user_id, exp, iat})   |
     | 200 {access_token,   |                         |
     |      token_type,     |                         |
     |      expires_in, user}                         |
     |<---------------------|                         |
     |                                                |
     | (store JWT in secure storage)                  |
     |                                                |
     | GET /auth/me                                   |
     | Authorization: Bearer <JWT>                    |
     |--------------------->|                         |
     |                      | decode_access_token()   |
     |                      | get_user_by_username()  |
     |                      |------------------------>|
     |                      |<------------------------|
     |                      | check is_active         |
     | 200 {user profile}   |                         |
     |<---------------------|                         |
```

### Access control matrix

| Scenario              | `/auth/me` | `/admin/*` | `/dashboard/*` | `PUT /settings/llm` | `/chat`, `/rooms`, `/health` |
|-----------------------|:---------:|:---------:|:--------------:|:-------------------:|:----------------------------:|
| No token              | 401       | 401       | 401            | 401                 | 200                          |
| Valid **user** token  | 200       | 403       | 403            | 403                 | 200                          |
| Valid **admin** token | 200       | 200       | 200            | 200                 | 200                          |
| Invalid / expired JWT | 401       | 401       | 401            | 401                 | 200                          |

### Security properties

- **bcrypt 12 rounds** for password hashing (all DB hashes start with `$2b$12$`)
- **JWT HS256** signed with `JWT_SECRET`, 24h lifetime (`JWT_EXPIRE_HOURS`)
- **No `password_hash` ever leaks** in API responses (serialized via `serialize_user()`)
- **Admin-only admin creation** — users cannot self-promote; `/auth/admin/register` requires existing admin JWT
- **Last-login tracking** — `users.last_login` updated on every successful login
- **Login accepts username OR email** as the identifier for ergonomics

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

## Hotel-Grade Features

### PII Redaction

```
  Guest message                    PII Redactor                   LLM
       |                               |                            |
       |  "My card is 4111-1111..."    |                            |
       |------------------------------>|                            |
       |                               |  scrub: [CREDIT_CARD]      |
       |                               |  scrub: [THAI_ID]          |
       |                               |  (preserve email for       |
       |                               |   booking tool args)       |
       |                               |--------------------------->|
       |                               |  "My card is [CREDIT_CARD]"|
       |                               |                            |
       |  Response (clean, no PII)     |                            |
       |<------------------------------|<---------------------------|
```

### Dynamic Pricing

```
  Days before check-in        Multiplier         Label
  ========================    ==========    ==================
  30+ days                      0.85x       Early Bird 15% off
  14-29 days                    0.90x       Advance 10% off
  7-13 days                     1.00x       Standard Rate
  1-6 days                      1.20x       Last-Minute +20%
  Same day                      1.30x       Same-Day +30%
```

Applied automatically in `create_reservation`. The `calculate_dynamic_price` tool
shows guests the actual price before booking.

### Auto-Escalation

```
  Guest message         Escalation Monitor        Admin Dashboard
       |                       |                        |
       |  "terrible service"   |                        |
       |---------------------->|                        |
       |                       |  check_sentiment: HIT  |
       |                       |  priority: HIGH        |
       |                       |----------------------->|
       |                       |  [Auto-escalation]     |
       |                       |  session -> admin_ctrl  |
       |                       |                        |
       |                       |  Also triggers on:     |
       |                       |  - 3x repeated question |
       |                       |  - Booking > 50K THB   |
       |                       |  - Penthouse inquiry    |
```

### Time-Travel / Checkpoint Replay

```
  Admin                          Server                      PostgreSQL
       |                            |                            |
       |  GET /admin/sessions/      |                            |
       |       {id}/states          |                            |
       |--------------------------->|  aget_state_history()      |
       |  [Step 0: guest msg]       |<--------------------------|
       |  [Step 1: router]          |                            |
       |  [Step 3: availability]    |                            |
       |  [Step 5: booking done]    |                            |
       |<---------------------------|                            |
       |                            |                            |
       |  POST .../rollback         |                            |
       |  checkpoint_id=Step3       |  aupdate_state()           |
       |--------------------------->|--------------------------->|
       |  "rolled back to step 3"   |  (fork from checkpoint)    |
       |<---------------------------|<--------------------------|
       |                            |                            |
       |  POST .../replay           |                            |
       |  checkpoint_id=Step3       |  ainvoke(new_msg, config)  |
       |  message="Try Suite"       |--------------------------->|
       |--------------------------->|  (new branch from step 3)  |
       |  "Suite available at..."   |<--------------------------|
       |<---------------------------|                            |
```

### Mock Payment Flow

```
  Guest                     Bot                    Server              DB
    |                        |                        |                 |
    |  "Confirm booking"     |                        |                 |
    |-----------------------+|                        |                 |
    |                        |  generate_payment_link |                 |
    |                        |----------------------->|  INSERT token   |
    |                        |                        |---------------->|
    |  "Pay here:            |                        |  expires 30min  |
    |   pay.grandhorizon     |                        |                 |
    |   .hotel/checkout/     |<-----------------------|                 |
    |   {token}"             |                        |                 |
    |<-----------------------|                        |                 |
    |                        |                        |                 |
    |  GET /payment/{token}  |                        |                 |
    |----------------------------------------------->|  booking details |
    |  {amount, room, dates} |                        |<----------------|
    |<-----------------------------------------------|                 |
    |                        |                        |                 |
    |  POST /payment/        |                        |                 |
    |       {token}/complete |                        |                 |
    |----------------------------------------------->|  status=paid    |
    |  "Payment successful"  |                        |---------------->|
    |<-----------------------------------------------|                 |
```

## API Endpoints (44 total)

Full OpenAPI spec: [docs/api_references/openapi.json](api_references/openapi.json)
Swagger UI: `http://localhost:8088/docs`

Legend: **[Public]** no auth · **[User]** any logged-in user · **[Admin]** admin JWT required

### Authentication [Public/User/Admin]

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| POST | /auth/register | Public | Create `user` account, returns JWT |
| POST | /auth/login | Public | Login by username or email, returns JWT |
| GET | /auth/me | User | Current user profile (from Bearer token) |
| POST | /auth/admin/register | Admin | Create a new admin account |
| GET | /auth/users | Admin | List all users (filter `?role=admin`) |

### Guest-Facing [Public]

| Method | Path | Purpose |
|--------|------|---------|
| POST | /chat | Main chatbot (PII-scrubbed, auto-escalation) |
| POST | /chat/stream | Streaming chat (SSE) |
| GET | /rooms | Room types with availability |
| GET | /rooms/availability | Calendar availability |
| GET | /rooms/{id} | Room details with pricing |
| POST | /tools/book | Direct booking operations |
| GET | /bookings | List bookings (by email/status) |
| GET | /bookings/{id} | Single booking details |
| PATCH | /bookings/{id} | Update booking |
| GET | /sessions/{id}/messages | Conversation history |
| GET | /payment/{token} | Mock payment page (booking details + amount) |
| POST | /payment/{token}/complete | Mock payment completion |

### Admin Operations [Admin]

All routes below require `Authorization: Bearer <admin-JWT>`. Non-admin tokens get 403.

| Method | Path | Purpose |
|--------|------|---------|
| PUT | /admin/rooms/{id}/status | Set room status (available/maintenance/cleaning) |
| PUT | /admin/bookings/{id}/status | Override booking status (check-in, no-show, etc.) |
| POST | /admin/chat/override | Send staff message to guest session |
| GET | /admin/sessions | List active sessions with previews + status |
| GET | /admin/sessions/{id}/messages | Full session chat history |
| POST | /admin/sessions/{id}/takeover | Pause bot, admin takes over |
| POST | /admin/sessions/{id}/release | Resume bot for session |
| GET | /admin/sessions/{id}/states | Checkpoint history (time-travel view) |
| POST | /admin/sessions/{id}/rollback | Rewind to previous checkpoint |
| POST | /admin/sessions/{id}/replay | Branch from checkpoint with new message |
| GET | /admin/escalations | List auto-escalated sessions |

### Dashboard Monitoring [Admin]

| Method | Path | Purpose |
|--------|------|---------|
| GET | /dashboard/stats | Occupancy, revenue, check-ins/outs, guests |
| GET | /dashboard/bookings/recent | Live feed of latest bookings |
| GET | /dashboard/sessions | Chatbot session statistics (24h) |
| GET | /dashboard/rooms | Room status breakdown by floor |
| GET | /dashboard/revenue | Revenue by room type, source, daily trend |

### System

| Method | Path | Auth | Purpose |
|--------|------|------|---------|
| GET | /healthz | Public | Load balancer health check |
| GET | /health | Public | Component health status |
| GET | /settings/llm | Public | Current LLM config (backend, model, thinking) |
| PUT | /settings/llm | Admin | Switch model at runtime (auto-presets) |
| GET | /settings/models | Public | Available models list |
| POST | /guests | Public | Register guest (no account — just profile) |
| GET | /guests/{email} | Public | Guest lookup |
| PATCH | /guests/{id} | Public | Update guest |
| POST | /sessions | Public | Create session |
| DELETE | /sessions/{id} | Public | End session |
| POST | /feedback | Public | Submit response feedback |
| GET | /feedback/stats | Public | Feedback statistics |

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
