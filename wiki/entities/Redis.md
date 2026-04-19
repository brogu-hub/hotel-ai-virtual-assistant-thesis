---
type: entity
category: product
url: https://redis.io
tags: [entity, product, cache, database]
created: 2026-04-19
updated: 2026-04-19
---

# Redis

## What it is

Redis is an open-source in-memory data structure store used as a cache, message broker, and session store.

## Role in this project

Redis provides **conversation session caching** for the hotel assistant. Multi-session support (conversation history across turns) is backed by Redis.

## Key facts

- Connection: `APP_CACHE_URL` environment variable (host:port)
- Port: 6379
- Docker Compose: `compose-redis-1`; Redis Commander admin UI also included
- Railway-hosted for dev/demo deployment

## Related

- [[hotel_guardrails]]
- [[Railway]]
