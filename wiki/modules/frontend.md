---
type: module
path: ""
status: active
language: javascript
purpose: "Sample customer-facing chat UI"
maintainer: ""
last_updated: 2026-04-19
depends_on: [api_gateway]
used_by: []
linked_issues: []
tags: [module, frontend, ui]
created: 2026-04-19
updated: 2026-04-19
---

# frontend

## Purpose

A sample browser-based chat UI for testing the hotel assistant. Connects to the [[api_gateway]] on port 9000. Source code is not included in the repository — it is a pre-built Docker image provided by NVIDIA.

## Key facts

- Port: 3001
- Accessed at `http://<HOST-IP>:3001/`
- Container name: `agent-frontend`
- Calls a single API endpoint on the [[api_gateway]]
- Not intended for production use; for blueprint demos only
- Provides preset customer names and suggested queries

## Notes & gotchas

- Source code not in this repository
- Kubernetes NodePort: 3001 (mapped dynamically)

## Related

- [[api_gateway]]
- [[Chat Request Flow]]
