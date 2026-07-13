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

## 2026-07-13 — Scoped `pk_live_` agent auth (2.2 design)

**Design only — no code in this session.** Written so a future session can
implement without re-deriving the shape. Driven by two waiting consumers:
MCP write tools (2.5 explicitly deferred writes to this design) and the 8.3
metrics notifier, which needs a read-only admin key and was told to reuse
whatever this session lands on (`docs/analytics.md` §4) instead of inventing
a second mechanism.

### Problem with today's `pk_live_`
`api/app/api/deps.py::get_current_user` treats a `pk_live_…` key exactly like
a JWT: `User.api_key` is a single column, one key per user, and once matched
the caller *is* that user — same role, same ownership, no distinction from a
browser session. `require_admin` only checks `user.role in (admin, support)`.
There is no way today to hand out a key that can *only* read admin stats, or
that can *only* write to one entity's blocks. Minting a personal key for the
8.3 notifier today would hand it full admin read+write; minting one for a
future MCP write-tool would hand the calling agent the user's entire
account, not just the one entity it's supposed to act on behalf of.

### Scope model
Scopes are plain strings, checked by prefix/exact match — no RBAC engine,
matches the project's existing "just enough" auth style:
- `admin:read` — read-only back-office endpoints (`/admin/stats`,
  `/admin/analytics`, `/admin/product-metrics`, `/admin/health-check`,
  `/admin/users*`, `/admin/claims`, `/admin/entities`, `/admin/audit-log` —
  every `GET` in `routes/admin.py`).
- `admin:write` — the two mutating admin routes (`POST
  /users/{id}/anonymize`, `POST /entities/{id}/validate`). Implies
  `admin:read` (a key with write doesn't also need read listed).
- `entity:write:<entity_id>` — write access to one business's own
  fields/blocks (`routes/businesses.py`, `routes/blocks.py` mutating routes),
  scoped to a single entity for the future MCP write tools (one verified
  agent, one entity it's authorized for).
- `entity:write:*` — write access to every entity the key's owner currently
  owns. This is the **default when `scopes` is omitted at issuance** — it's
  exactly today's implicit personal-key behavior, so the new mechanism is a
  strict superset, not a parallel system a caller has to opt into.
- No scope string for plain read of public data — that's already
  unauthenticated (`/search`, `/businesses/{id}/preview`, `/proof`, etc.).

Scope checks never widen what the underlying user could already do — a
`entity:write:<id>` key on a user who does not own `<id>` still 403s on the
existing ownership check in `routes/businesses.py`/`blocks.py`. Scopes only
*narrow*.

### Data model — additive, not a replacement
Do **not** touch `User.api_key` or `POST /auth/personal-api-key` — that stays
exactly as-is for humans who want a full-access personal key (e.g. curl
scripting), unaffected by any of this. Add a new table, `agent_api_keys`,
following the project's existing UUID-PK + `func.now()` conventions
(`docs/database.md` Conventions):
- `id` (uuid pk), `user_id` (fk → users), `key_hash` (sha256 of the raw
  token — **hashed, not plaintext**, unlike the legacy `api_key` column; the
  raw `pk_live_…` value is only ever shown once, at creation), `key_prefix`
  (first ~12 chars post-prefix, for display in a future "my agent keys" UI
  without exposing the secret), `label` (human string, e.g.
  `"metrics-notifier"`, `"camera-agent-berlin-bakery"`), `scopes`
  (`ARRAY(Text)`), `created_at`, `last_used_at` (bumped on successful auth,
  best-effort), `revoked_at` (nullable).
- Revocation is a soft `revoked_at` set, never a `DELETE` — same append-only-
  for-audit philosophy already used for `verification_events` /
  `admin_audit_log` (`docs/decisions.md` Trust & crypto). A rotated/replaced
  key's row stays queryable for "what could this key do, and when was it
  killed."
- Keys keep the `pk_live_` prefix so they still route into the existing
  `token.startswith("pk_live_")` branch in `deps.py`; lookup tries
  `agent_api_keys` (by `key_hash`) first, falls back to the legacy
  `User.api_key` exact match if no row matches — old keys keep working
  unchanged, forever, with unrestricted (pre-scope) behavior.

### Issuance, rotation, revocation
New endpoints alongside the existing `/auth/personal-api-key` (not replacing
it):
- `POST /auth/agent-keys` — body `{label, scopes?}`. Validates scopes at
  issuance time, not just at use time: `admin:read`/`admin:write` require the
  issuing user's `role` to already be `admin`/`support`; `entity:write:<id>`
  requires the issuing user to currently own `<id>`. Returns the raw key
  once, same "shown once, store it safely" UX as the personal key.
- `GET /auth/agent-keys` — list the caller's own keys: id, label, prefix,
  scopes, created_at, last_used_at, revoked_at. Never returns the secret.
- `DELETE /auth/agent-keys/{id}` — sets `revoked_at`. "Rotate" is just
  revoke-then-reissue with the same label/scopes — no separate rotate
  endpoint; one extra endpoint to maintain isn't worth it for a two-call
  composition.
- Runtime re-checks ownership on every request in addition to the
  issuance-time check, since ownership can change after a key is minted
  (entity transferred or deleted) — the scope on the key is a ceiling, the
  live ownership check is the floor, narrowest wins.

### Enforcement — extending the `require_admin`-style deps
`get_current_user` becomes (conceptually) `get_current_principal`, returning
`(user, scopes)` where `scopes = None` means *unrestricted* — true for JWT
sessions and legacy `User.api_key` matches, so every existing human/browser
and pre-existing-personal-key caller is unaffected. A new
`require_scope(scope: str)` dependency factory replaces the blanket check
where it's currently too coarse:
- `require_admin` (today's blanket admin gate) becomes
  `require_scope("admin:write")` for the two mutating routes, and
  `require_scope("admin:read")` for every read-only admin route — an
  unrestricted principal (`scopes=None`) always passes both, so this is only
  ever a *new restriction on scoped keys*, never a new restriction on humans.
- Entity-scoped writes can't be a static `Depends()` (the target entity id is
  a path parameter, not known at dependency-resolution time for a
  decorator), so `routes/businesses.py`/`blocks.py` call a small helper —
  `check_entity_scope(principal, entity_id)` — inline, right next to the
  existing owner-check, rather than as FastAPI `Depends`.
- Every scoped-key-authenticated call should log the key's `id`/`label` (not
  just `user_id`) into `admin_audit_log`, so a rogue/compromised agent key's
  actions are distinguishable from the human owner's own JWT actions in the
  audit trail.

### 8.3 reuse (confirms the design is general enough)
The notifier agent gets one `agent_api_keys` row: `label:
"metrics-notifier"`, `scopes: ["admin:read"]`, issued by an admin/support
account. It authenticates with `Authorization: Bearer pk_live_…` exactly as
`docs/analytics.md` §4 already assumed, but now genuinely can't call the two
`admin:write` routes even if the key leaks — today it could, since
`pk_live_` = full account. No new auth system for 8.3, per its own note.

### Backward compatibility (explicit, since this touches shared auth)
- Existing personal keys via `User.api_key`: untouched, unrestricted,
  forever (unless a later session decides to deprecate them — not this one).
- Existing JWT sessions: untouched, unrestricted.
- `require_admin` behavior for humans: unchanged (still just role check via
  the unrestricted-principal fast path).
- Nothing here requires a data migration of existing keys — `agent_api_keys`
  is purely additive.

### Explicitly out of scope for this design
- Rate-limiting per agent key (ties into the existing known-issue that
  rate-limit state is in-process and needs Redis before scaling —
  `docs/known-issues.md`). A leaked write-scoped key spamming requests is a
  real concern but is a separate, later hardening pass.
- Any actual MCP write tools — 2.5 deferred them here on purpose; this
  design only unblocks them, it doesn't design the tools themselves.
- Telegram/push delivery for 8.3 — unrelated to auth, that session's own
  problem.
- Deprecating `User.api_key`/`/auth/personal-api-key` — left as a future
  option, not decided here.
