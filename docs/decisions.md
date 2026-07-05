# Decisions

Why the project is built the way it is. Append new decisions at the bottom with a
date; don't rewrite history.

## Stack
- **FastAPI + async SQLAlchemy** — async-first for high-fanout registry lookups and
  agent traffic; Pydantic for typed schemas; OpenAPI docs for free.
- **PostgreSQL 16 + pgvector** — one store for relational data *and* 1536-dim
  embeddings (HNSW) so TWIRA's I-component is a single SQL query, no separate vector DB.
- **Redis** — email codes (TTL), rate-limit/cooldown counters, Celery broker.
- **Celery** — background OTS stamping, endpoint probes, nightly TWIRA recompute.
- **Next.js 15 + TypeScript** — App Router, one app for search + onboarding +
  profile + back office; zustand for client state.
- **MCP TS server** — agents are first-class consumers; MCP is the standard way to
  expose tools to them. Kept stateless, calls the API.
- **Static HTML landing, no CDN/React** — fast, zero build risk, easy to edit; SEO/AEO
  files served directly by nginx.

## Trust & crypto
- **Bitcoin via OpenTimestamps, not OP_RETURN** — OP_RETURN excluded per BIP-177
  (2025-26); OTS calendars give free, standard, verifiable timestamps.
- **Append-only via DB trigger, not REVOKE** — app and workers share one DB role, so
  column-level grants can't express "insert + OTS-only update". A trigger on
  `verification_events` / `admin_audit_log` enforces append-only precisely.
- **first_verified_at = MIN(confirmed event)** — the "first-verified advantage" that
  makes the Temporal Moat visible.
- **PII field encryption (Fernet), email left plaintext** — email is needed for the
  unique index and login; other PII (full_name) is encrypted at rest.

## Auth
- **Email 6-digit code over magic-link** — codes work across devices/clients, no deep
  link handling; Redis TTL + attempt cap is simple and robust.
- **JWT `ver` claim = token_version** — stateless "log out everywhere" without a
  server session store (accepted trade-off: no per-device session list yet).
- **`pk_live_` API keys** checked directly in `get_current_user` for agents.

## Registries
- **German portal JSF scrape** — no free API exists; §9 HGB guarantees free public
  access. Serialized + cached because the portal rejects concurrent sessions.
- **No-country fan-out** — the claim search sends no country, so we query all free
  registries in parallel and rank by name similarity.
- **Commercial providers behind env keys** — NorthData (DE/EU), Opendatabot (UA)
  activate only when licensed; keeps everything legal.

## Ops
- **GitHub Actions on push to main** — single pipeline builds, rsyncs, migrates,
  restarts. `app-paths-manifest.json` patched manually because Next standalone omits it.
- **uvicorn --workers 1** — lets in-memory rate limiters and the DE lock work; must
  move to Redis before scaling out (tracked in known-issues).

## 2026-07 — Documentation & session model
Adopted `docs/` as the in-repo project brain + root `CLAUDE.md` rules; one focused
task per Claude session with `/clear` between; targeted file reads over repo scans.
Rejected: two parallel doc folders (drift) and a standing team of 7 named subagents
(each spawn re-reads context cold — expensive in Claude Code; use subagents only for
parallel read-heavy search).
