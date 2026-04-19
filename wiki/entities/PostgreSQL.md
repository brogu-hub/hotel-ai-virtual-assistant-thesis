---
type: entity
category: product
url: https://www.postgresql.org
tags: [entity, product, database, relational]
created: 2026-04-19
updated: 2026-04-19
---

# PostgreSQL

## What it is

PostgreSQL is an open-source relational database management system.

## Role in this project

PostgreSQL stores structured hotel data: rooms, bookings, and guest records. The `hotel_guardrails` module uses it directly via `src/hotel_guardrails/database.py`.

## Key facts

- Schema: `deploy/compose/init-scripts/init-hotel.sql` (tables: rooms, bookings, guests)
- Connection: `DATABASE_URL` environment variable
- Port: 5432
- Docker Compose: `postgres_container`
- PgAdmin management UI included in full Docker Compose stack
- Railway-hosted for dev/demo deployment
- Structured retriever uses [[Vanna.AI]] for NL-to-SQL queries against this DB

## Related

- [[hotel_guardrails]]
- [[Vanna.AI]]
- [[retrievers]]
- [[Railway]]
