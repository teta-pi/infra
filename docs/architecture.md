# Architecture

## Request flow
```
                         tetapi.dev (nginx → static HTML)
                         app.tetapi.dev (Next.js 15, SSR/CSR)
   Human / AI agent  ──▶ api.tetapi.dev (FastAPI)  ──▶ PostgreSQL 16 + pgvector
                         mcp.tetapi.dev (MCP TS)   ──▶ (calls the API)
                                                    │
                                          Redis (cache, codes, celery broker)
                                                    │
                                          Celery workers (OTS, probes, TWIRA recompute)
                                                    │
                                          External: OpenAI (embeddings), Resend (email),
                                          OpenTimestamps calendars, official registries
```

## Layer responsibilities
- **Landing (`landing/`)** — pure static HTML, inline CSS/JS, no CDN, no framework.
  SEO/AEO artifacts: `sitemap.xml`, `robots.txt`, `llms.txt`, `.well-known/agent.json`.
  GoatCounter analytics. Served by nginx from `/var/www/teta-pi/`.
- **App (`web/`)** — Next.js 15 App Router, TypeScript, zustand stores. Pages:
  `/` (search), `/claim` (onboarding = waitlist), `/profile` (My Page),
  `/settings`, `/login`, `/admin` (back office), `/e/[slug]` (public entity page),
  `/.well-known/agent.json` (route). API client in `web/src/lib/api.ts`.
- **API (`api/`)** — FastAPI, async SQLAlchemy (asyncpg), Alembic migrations,
  pgvector. Routers under `api/app/api/routes/`, business logic in
  `api/app/services/`, TWIRA in `api/app/twira/`, background jobs in
  `api/app/workers/`. TWIRA's T-component weighs each `verification_events`
  row by `source` (`api/app/twira/trust.py:SOURCE_W`) — one weight per
  verification method (registry / domain / email / document), see
  `docs/verification-rework.md` §4.
- **MCP (`mcp/`)** — TypeScript server exposing `teta_*` tools to agents; it calls
  the API over HTTP (`TETA_PI_API_URL`). Stateless.
- **Workers** — Celery + Redis. Beat schedule: OTS lifecycle (30 min), endpoint
  probes (30 min), TWIRA T/P recompute (nightly), BTC confirmations (hourly).

## Data model (core tables)
`users` · `businesses` (= entities) · `blocks` (+ pgvector embedding) · `media` ·
`devices` · `claims` (waitlist) · `verification_events` (append-only Temporal Moat)
· `endpoint_probes` · `admin_audit_log` (append-only). Full detail in
`docs/database.md`.

## Auth model
- **Email code** (primary): 6-digit code in Redis (15 min), `/auth/email-code` +
  `/auth/verify-code`.
- **Password** (optional): set in Settings, sign in via `/auth/token`.
- **JWT** with a `ver` claim = `users.token_version`; bumping it kills all old
  tokens ("log out everywhere").
- **API keys** `pk_live_…` for agents/integrations; checked directly in
  `get_current_user`.
- **Roles**: `user` | `support` | `admin`; back office gated by `require_admin`.

## Key architectural properties
- **Temporal Moat**: `verification_events` is append-only, enforced by a DB trigger
  (not grants — app and workers share one DB role). Bitcoin-anchored → history
  can't be rewritten.
- **PII encryption**: `users.full_name` stored Fernet-encrypted at rest via the
  `EncryptedString` type; key in server `.env` only.
- **Single uvicorn worker** (`--workers 1`) — in-memory rate limiters and the
  Handelsregister lock/cache rely on this. See `docs/known-issues.md` before scaling.

## Where AI is used
- **Embeddings** (OpenAI `text-embedding-3-small`, 1536-dim) for block vectors and
  the TWIRA **I** component. NOTE: `OPENAI_API_KEY` is not set on the server yet,
  so semantic ranking currently falls back to keyword resolution.
- **AI categories** extraction for entities (`api/app/services/ai.py`).
