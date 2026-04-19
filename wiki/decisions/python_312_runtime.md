---
type: decision
status: active
date: 2026-04-19
owner: "Mangakorian"
context: "Python runtime version selection after a full environment rebuild on 2026-04-19"
supersedes: []
superseded_by: []
tags: [decision]
created: 2026-04-19
updated: 2026-04-19
---

# ADR: Python 3.12 as Target Runtime

*Retroactive ADR written 2026-04-19; decision was made as part of the post-rebuild environment standardization on 2026-04-19.*

## Context

Following a full environment rebuild on 2026-04-19, the project needed an explicit Python version target to pin in `requirements.dev.txt`, Docker images, Railway deployment, and CI. The key constraints were:

1. LangGraph (recent versions) requires Python ≥ 3.10.
2. FastAPI + Pydantic v2 are well-tested on 3.11 and 3.12.
3. Psycopg3 (`psycopg[binary]`) and PyJWT have stable 3.12 releases.
4. The Railway builder and the Docker base images used in `deploy/compose/` need a consistent target.
5. Python 3.13 was available at rebuild time but several dependencies (particularly ML-adjacent ones like sentence-transformers) had not yet published stable 3.13 wheels.

## Options considered

- **Option A — Python 3.11**
  - Pros: Very stable; all dependencies have tested 3.11 wheels; slightly more conservative choice
  - Cons: Missing 3.12 performance improvements (faster CPython interpreter, improved asyncio); not the latest stable version

- **Option B — Python 3.12**
  - Pros: Current stable LTS-equivalent; faster `asyncio` event loop; improved error messages; all project dependencies have 3.12 wheels available; Railway's default Python builder supports 3.12
  - Cons: Marginal — some very early 3.12 incompatibilities in obscure packages, but none affecting this project's dependency tree

- **Option C — Python 3.13**
  - Pros: Latest version; further interpreter improvements
  - Cons: sentence-transformers and some other ML dependencies lacked stable 3.13 wheels at rebuild time; higher risk of subtle incompatibilities in a thesis environment where stability matters

## Decision

Target Python 3.12. All `Dockerfile` base images, `railway.toml` runtime config, and local virtual environment use Python 3.12. `requirements.dev.txt` is pinned against 3.12 wheels.

## Consequences

- Positive: Stable, well-supported runtime with full dependency wheel coverage. The asyncio improvements in 3.12 are mildly beneficial given the heavy async usage in `hotel_guardrails/server.py`. Railway deployment uses the same version as local dev, eliminating version-drift surprises.
- Negative / trade-offs: This is a maintenance decision, not an architectural innovation. The Python version constraint is low-salience — it only becomes a problem if a required dependency drops 3.12 support or if a future LangGraph version requires 3.13+. The decision is largely forced by eliminating 3.13 due to wheel availability.
- Revisit if: A required dependency requires 3.13 or drops 3.12; or when Python 3.12 reaches end-of-life (estimated 2028).

## Related

- [[hotel_guardrails]] — primary service affected
- [[common]] — shared libraries affected
- [[Railway]] — deployment environment that must match
