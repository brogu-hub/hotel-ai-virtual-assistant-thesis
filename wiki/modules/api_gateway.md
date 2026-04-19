---
type: module
path: src/api_gateway/
status: active
language: python
purpose: "HTTP proxy routing external requests to the agent server"
maintainer: Mangakorian
last_updated: 2026-04-19
depends_on: []
used_by: []
linked_issues: []
tags: [module, api_gateway]
created: 2026-04-19
updated: 2026-04-19
---

# api_gateway

## Purpose

A thin HTTP proxy that routes inbound requests from the frontend UI and external clients to the appropriate backend microservice (agent or hotel_guardrails). Provides a unified external API surface.

## Entry points

- Listens on port 9000
- Routes to agent server (8081) and other services

## Notes & gotchas

- Frontend UI (`port 3001`) calls this gateway, not the agent directly
- OpenAPI spec: `docs/api_references/api_gateway_server.json`

## Related

- [[hotel_guardrails]]
- [[agent]]
- [[frontend]]
- [[Chat Request Flow]]
