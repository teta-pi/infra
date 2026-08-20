# Security — Threat Model & Standing Audit

Owner: **direction 15 (security)**. This is the canonical security reference for
TETA+PI. It is a *design + audit* document — no code or infra is changed by the
session that maintains it. Implementation of anything here happens in the mapped
backend/frontend/devops tasks.

## Rules of engagement (non-negotiable)
- **Authorized, our-own-infra only.** Every surface named here is operated by
  TetaPi GmbH. No third-party systems are in scope.
- **Read without exploitation.** Findings are verified in code (`file:line`) or by
  read-only requests; they are *reported, not weaponised*.
- **No destructive or DoS tests against prod.** No load tests, no data deletion,
  no exfiltration, no fuzzing that writes. The recurring loop (§7) runs static
  analysis on the GitHub runner — **zero server load** — plus a read-only
  authorized re-audit cadence.
- Anything that would touch prod configs (nginx, systemd, `.env`) is out of scope
  for this direction and must be raised explicitly with the owner.

---

## 1. Assets

Ranked by blast radius. "Where" points at the code/store that guards it.

| # | Asset | Why it matters | Where it lives / is guarded |
|---|---|---|---|
| A1 | **Entity data** (`businesses`, `blocks`, `media`) incl. private (`is_public=false`) rows | The product *is* the trust graph; a leak or forged edit undermines every downstream verification | `api/app/api/routes/{businesses,blocks,media}.py`, owner checks `owner_id == current_user.id` |
| A2 | **`pk_live_…` personal API keys** | Bearer-equivalent to a full account (agents, WP plugin, Universal Tag). Leak = account takeover | `users.api_key`, minted at `/auth/personal-api-key`, checked in `get_current_user` |
| A3 | **Admin / support routes** | Read all users, export GDPR data, anonymize, re-validate registry, audit log | `routes/admin.py`, gated by `require_admin`, every call writes `admin_audit_log` |
| A4 | **Append-only tables** (`verification_events`, `admin_audit_log`) | The Temporal Moat — Bitcoin-anchored history. Silent rewrite destroys the core guarantee | DB triggers block UPDATE/DELETE (migrations 006, 007, re-asserted 011) |
| A5 | **C2PA / OpenTimestamps proofs** (`blocks.ots_proof`, `blocks.c2pa_manifest`, `media.bitcoin_proof`) | Cryptographic evidence surfaced to agents; forgery or swap = fake provenance | `api/app/services/{bitcoin,c2pa}.py`, `workers/tasks/bitcoin.py` |
| A6 | **Media store** (`UPLOAD_DIR`, served at `/media/local/{id}/{name}`) | Filesystem read/write surface; path bugs reach the whole droplet | `routes/media.py`; traversal on the read path was **fixed** (api PR #3, §6) |
| A7 | **Secrets in server `.env`** — Fernet PII key, JWT secret, Resend/OpenAI keys, DB creds, `api/certs/*.key.pem` | Fernet key decrypts every `users.full_name`; JWT secret forges any session | server `.env` **only**; never committed (see `CLAUDE.md`, `docs/deployment.md`) |
| A8 | **PII at rest** (`users.full_name` Fernet-encrypted, `users.email` plaintext for index) | GDPR obligations; encryption depends entirely on A7 | `EncryptedString` type, key in A7 |
| A9 | **Auth sessions** (JWT with `ver` = `token_version`, email codes + `pk_live_` keys in Redis) | Session fixation / non-invalidation = persistent unauthorized access (see QA #1) | `routes/auth.py`, Redis (codes, 15 min), `token_version` bump = logout-all |

---

## 2. Trust boundaries

Each boundary is a place where a less-trusted caller hands data to a more-trusted
component. Untrusted input must be validated/authorized at every crossing.

```
                          ┌───────────────────────── TRUSTED (our infra) ─────────────────────────┐
  UNTRUSTED CALLERS       │                                                                        │
                          │                                                                        │
  AI agent ──(B1)──▶ mcp.tetapi.dev ──(HTTP)──▶ api.tetapi.dev ──▶ PostgreSQL 16 (+ triggers A4)  │
                          │      (stateless TS)      (FastAPI)   └─▶ Redis (codes, rate, celery)    │
  Browser ───(B2)──────────────────────────────▶ │              └─▶ Celery workers (OTS/probes)    │
                          │                        │                                                │
  Camera device ─(B3)──── /media/device-upload ──▶ │                                                │
  WP plugin ────(B4)───── /businesses, /verify ──▶ │              External egress (SSRF surface):   │
  tag.js ───────(B5)───── /v1/tag-ping ──────────▶ │   ─────▶ registries, DNS-over-HTTPS, agent     │
                          │                        │           endpoints, OTS calendars, Resend,    │
                          │                        │           OpenAI                               │
                          └────────────────────────┴────────────────────────────────────────────────┘
```

| ID | Boundary | Trust delta | Primary risks | Enforcement point |
|----|----------|-------------|---------------|-------------------|
| **B1** | agent ↔ MCP | anonymous agent → `teta_*` tools that call the API | over-broad tool output, arg validation drift (zod ↔ API path types), leaking non-public entities via preview/proof | `mcp/src/index.ts` (zod schemas), API auth downstream |
| **B2** | browser ↔ API | anonymous/JWT user → CRUD | IDOR on `/businesses/{id}` & `/blocks`, session non-invalidation (A9), CSRF-style state, XSS via block content rendered in `/e/[slug]` | `get_current_user`, owner checks, Next.js escaping |
| **B3** | device ↔ `/media/device-upload` | camera holding a `pk_live_` key → filesystem write + media row | key theft = write as owner, path/content-type abuse on upload, unbounded file size, missing OTS anchoring | `routes/media.py` (`_save_local` sanitizes), api_key auth |
| **B4** | WP plugin ↔ API | site admin's `pk_live_` key → entity read + domain verify | key stored in WP options (site DB) — leak surface outside our control; over-scoped key | public API + `pk_live_`; key is bearer-equivalent (A2) |
| **B5** | tag.js ↔ `/v1/tag-ping` (`docs/universal-tag.md`) | *fully anonymous, unauthenticated, sustained-write* beacon, one hit per page load on every installed site | spoofed `entity_id` inflating another entity's indexed-pages list, volumetric write abuse (DoS-by-cost), reflected/stored data in `page_url`/`page_title`/`referrer` | ✅ **built 2026-07-19, api PR #12** — in-memory IP rate limit (same pattern as badge, S-10 tracks Redis migration), bounded Redis sorted set (200-page cap, `docs/decisions.md`) instead of a DB row, response always `204` regardless of `entity_id` validity (no existence oracle). Entity-id spoofing (inflating another entity's page list) is **not** prevented — anonymous by design, accepted risk, no auth possible without breaking the zero-friction install; capped list size bounds the blast radius. `page_title`/`referrer`/`page_url` length-capped in the request schema (300/2048/2048 chars); only `page_url` (+ `page_title`) is persisted (in the Redis sorted-set member) — `referrer` is validated but never stored. Persisted fields are not escaped server-side — rendering safety still depends on frontend escaping wherever the indexed-pages list is displayed (see injection checklist below, unchanged) |

---

## 3. Attacker classes

| Class | Capability | Motivation | What they reach |
|-------|-----------|-----------|-----------------|
| **Anonymous internet** | unauthenticated HTTP to api/landing/mcp; can install tag.js on their own site | scrape private data, forge trust signals, cost-DoS | public endpoints, `/verify-endpoint` (SSRF, now auth-gated), `/v1/tag-ping` (B5), `/media/local` (traversal fixed) |
| **Authenticated user (own account)** | valid JWT or `pk_live_` key, owns ≥1 entity | privilege escalation, IDOR into other entities/accounts, keep stale "verified" flags | `/businesses/{id}`, `/blocks`, `/media`, `/verify/*`; QA #18 (cross-entity leak), 6.1 #6 (stale endpoint verify) |
| **Malicious entity owner** | can create any entity name for free (L0), owns content/media/endpoint | impersonation, fake provenance, poison agent search | entity creation (no registry gate by design), `agent_endpoint`, media/C2PA claims |
| **Compromised device / leaked key** | holds a `pk_live_` key (A2) exfiltrated from a WP site DB or camera | act as the owner | everything B3/B4 grants; blast radius = one account |
| **Malicious agent** | drives MCP tools, crafts adversarial queries/intents | extract non-public data, DoS via expensive resolves | B1 tool surface, `resolve-intent` cost |
| **Insider / prod access** | shell or DB on the droplet | read Fernet key (A7) → decrypt all PII, rewrite state | mitigated only by append-only triggers (share one DB role — app & workers) and `.env` hygiene; **key-only SSH** (password off 2026-07-13) |
| **Supply chain** | malicious npm/pip dependency | RCE in api/web/mcp build or runtime | dependency tree — addressed by §7 `npm audit` / `bandit` / CodeQL |

---

## 4. Per-surface security checklist

Standing checklist re-run each audit cycle. `✅ = verified good`, `⚠️ = known gap
(tracked below)`, `☐ = to (re)audit`. Line refs are the audit anchors.

### authn (authentication)
- ✅ JWT carries `ver` = `token_version`; `/auth/logout-all` bumps it (A9).
- ⚠️ **Session not invalidated on expiry/logout** — expired session still shows
  editable profile (QA #1 → **3.9**); "Make private → invalid token" (QA #2, same
  family). Verify `token_version` is actually checked on every mutating route.
- ☐ Email-code brute force: 6-digit code, 15-min TTL, 60s cooldown
  (`/auth/email-code`) — confirm attempt-count lockout, not just cooldown.
- ☐ `pk_live_` keys: confirm rotation (`/auth/personal-api-key`) invalidates the
  old key immediately; no key logging.
- ✅ MCP (B1) still has no auth (that's unchanged and still a real gap), but
  the false `auth: Bearer` README claim is fixed — README now correctly says
  "no auth required yet" (S-11 CLOSED as a docs bug, `2.9`, 2026-08-05).
  Whether MCP needs *real* auth before scaling agent traffic is flagged as an
  open product question in the closing PR, not resolved here.

### authz (authorization) & IDOR
- ✅ Admin surface uniformly behind `require_admin` + `admin_audit_log` (A3).
- ⚠️ **Cross-entity data leak within one account** (QA #18 → **3.11**) — prime
  suspect `useProfileStore` localStorage reuse (frontend), but **backend owner
  scoping must be ruled out too** (does every `/businesses/{id}` and `/blocks`
  read/write check `owner_id`?).
- ⚠️ Stale verified flag: `PATCH /businesses/{id}` keeps
  `agent_endpoint_verified=true` after the endpoint changes (6.1 #6 → **1.5/1.x**).
- ☐ `GET /businesses/{id}/blocks` may return private blocks (known-issues) — audit
  `is_public` filtering on every block read path.
- ☐ MCP preview/proof tools (B1): confirm they never surface `is_public=false`
  entities/blocks to anonymous agents.

### SSRF
- ✅ **`POST /verify-endpoint`** unauthenticated SSRF — **FIXED** (api PR #3, §6).
- ⚠️ `/verify/domain/check` performs a boolean-only fetch to a caller-influenced
  host (mild SSRF, known-issues) — audit for allowlist/timeout/size caps and
  metadata-endpoint (169.254.169.254) blocking.
- ☐ All external egress (registries, DNS-over-HTTPS, agent endpoints, OTS, Resend,
  OpenAI): confirm timeouts, no redirect-following to internal ranges, response
  size caps.

### path traversal
- ✅ **`GET /media/local/{file_id}/{filename}`** — **FIXED** (api PR #3, §6);
  path now contained to `_UPLOAD_DIR`.
- ✅ `_save_local` (upload path) sanitizes via `Path(...).name`.
- ☐ Re-audit any new file-serving route (Universal Tag wk-file generator 12.5b,
  device-upload) for the same containment.

### injection (SQL / XSS / template / header)
- ✅ SQLAlchemy 2 parameterized queries throughout; no raw string SQL observed.
- ☐ Stored XSS: block `title`/`description` and `tag-ping` `page_title`/`referrer`
  rendered on `/e/[slug]` and entity profiles — confirm React escaping + no
  `dangerouslySetInnerHTML`.
- ☐ Email header/template injection via user-controlled fields into Resend.

### rate limiting & cost-DoS
- ⚠️ Rate limiters are **in-memory**, correct only under `uvicorn --workers 1`
  (architecture note) — a scaling hazard, and prod droplet is already maxed
  (memory: server-capacity). Move to Redis before multi-worker.
- ✅ **`/v1/tag-ping` (B5)** — anonymous sustained-write endpoint; in-memory
  rate limit + bounded Redis sorted set (200-page cap), no per-hit DB row —
  same design as the 1.10 badge endpoint. Still single-worker-only (S-10).
- ✅ `/claim` rate-limited 5/min/IP.
- ☐ `resolve-intent` / `search`: confirm per-IP/key limits on expensive ranking.
- ✅ MCP (`mcp.tetapi.dev`) now rate-limits its own ingress — same in-memory
  sliding-window pattern as `/v1/tag-ping`/badge (60 req/min/IP on `/mcp`),
  independent of the API's own limits (S-13 CLOSED, `2.9`, 2026-08-05). Same
  single-worker-only caveat as the API-side limiters above.

### secrets exposure
- ✅ Secrets in server `.env` only; `api/certs/*.key.pem` never synced/committed
  (`CLAUDE.md`, `docs/deployment.md`).
- ☐ Confirm no secret in logs, error responses, or `/docs` schema examples.
- ☐ Repo scan for accidentally committed keys — folds into §7 (CodeQL + a
  secret-scan step).
- ⚠️ Insider blast radius: one DB role for app+workers; Fernet key decrypts all
  PII (A7/A8). Accepted risk, documented; mitigated by key-only SSH + append-only
  triggers.

---

## 5. Seed backlog (triaged findings → tasks)

Consolidated from the 6.1 read-only audit (`known-issues.md` §"System-wide bug
audit — 2026-07-12") and the owner QA report 2026-07-17. Only **security-relevant**
items are tracked here; functional-only bugs stay in `known-issues.md`.

| ID | Finding | Sev | Source | Maps to | Status |
|----|---------|-----|--------|---------|--------|
| S-1 | `GET /media/local/{id}/{name}` unauthenticated path traversal | 🔴 | 6.1 #1 | 1.6 | **CLOSED** — api PR #3 (merged 2026-07-14): path resolved & contained to `_UPLOAD_DIR` |
| S-2 | `POST /verify-endpoint` unauthenticated server-side GET (SSRF) | 🟠 | 6.1 #7 | 1.7 | **CLOSED** — api PR #3 (merged 2026-07-14): auth/rate-limit added on the SSRF-prone fetch |
| S-3 | `/claim` "Registry domain email" verify step is fully client-side fakeable (`onClick={()=>{}}` + `length>=3 → setProven`) | 🟠 | 6.1 #11 | 3.9 (wire to real `/verify/email/*`) | ✅ CLOSED 2026-08-05 (15.3 verification) — not fixed by 3.9; superseded by **web PR #4** (`0a2d700`, "feat(claim): registry-free create flow (3.7)", merged 2026-07-16), which deleted the entire client-side "prove business ownership via registry domain email" step and all its state (`setProven`/prove-method) outright. Confirmed live in current `web/src/app/claim/page.tsx`: no `onClick={()=>{}}`, no `setProven`, no "Registry domain email" step anywhere — the only remaining verify step is account-email (step 2), which calls real `authApi.sendEmailCode`/`authApi.verifyCode`. Registry ownership is now a separate, real backend call from `/profile` (`POST /businesses/{id}/verify/registry`, `lib/api.ts:510`), not client-side fakeable. Security.md's fix-owner column pointed at 3.9; the actual closing commit predates it (3.7) |
| S-4 | Expired session still shows editable profile (session not invalidated) | 🔴 | QA #1 | 3.9 | ✅ CLOSED 2026-08-05 (15.3 verification) — fixed by **web PR #10** (`23fbdbe`, "fix(profile): centralize 401 handling"). `lib/api.ts`'s `handleUnauthorized()` clears both auth stores + `localStorage["auth_token"]` and fires `teta:unauthorized`; `profile/page.tsx` listens for that event (`sessionInvalid` state) and also proactively probes token validity on mount via `businessApi.list(token)`. **Live-verified on prod**: set a garbage token + a real business id in `localStorage`, loaded `app.tetapi.dev/profile` — rendered "Your session expired — sign in again to keep editing." sign-in gate, not the editable grid |
| S-5 | "Make private → invalid token" (stale-token family) | 🟠 | QA #2 | 3.9 | ✅ CLOSED 2026-08-05 (15.3 verification), both sub-parts — **PATCH-500 part**: fixed in **api PR #6** (`56e4ac1`, 1.18) — root cause was a missing `await db.refresh(business)` after `db.flush()` in `update_business`, confirmed present in current `businesses.py:246`. Live re-verified twice on prod: (1) two QA entities that were stuck public since 2026-07-16/17 because of this exact bug (`44edb26e…`, `4cfe5174…`) now show `is_public=false, is_published=false` in prod DB with `updated_at` timestamps after the fix, meaning a PATCH with those booleans has since succeeded; (2) fresh live `PATCH .../is_public,is_published` against two new test entities this session both returned `200`, not `500`. **Stale-token part**: `businessApi.setPrivacy` (`lib/api.ts:374`) routes through the same shared `request()`/`handleUnauthorized()` pipeline verified live for S-4 — a dead token on "Make private" now produces the same sign-in gate instead of a raw "invalid token" error |
| S-6 | Data leakage between entities of one account | 🔴 | QA #18 | 3.11 | ✅ CLOSED 2026-08-05 (15.3 verification) — fixed by **web PR #11** (`abd222e`, "fix(profile): reset entity-scoped store state on businessId switch (QA #18)"). Root cause per commit: `useProfileStore` module-level singleton with no `businessId` scoping, plus the entity-load effect only overwrote `name`/`description` when the new entity's value was truthy — an empty field silently kept the old entity's value. Fix resets entity-scoped store fields before fetching + assigns fetched values unconditionally; `EditView` now keyed on `businessId` so per-entity local state (registry status, verify progress, publish state) resets too. **Backend owner-scoping independently re-verified live** this session: created two fresh test entities under one account via API, fetched each by id — no cross-contamination, each returns its own name/description (matches what the original 3.11 session's commit message says it also confirmed before concluding frontend-only). Full SPA client-side-switch re-test (no page reload) wasn't re-run this session — no in-app multi-entity switcher UI exists yet to drive it through, and it would have required exposing the test credential in a browser tool call, which this session avoided |
| S-7 | `PATCH /businesses/{id}` keeps `agent_endpoint_verified=true` after endpoint change | 🟠 | 6.1 #6 | 1.5/1.x | ✅ **CLOSED 2026-08-20** — fixed by **api PR #17** (1.7, bundled with 1.5/1.8). `update_business` now compares `agent_endpoint` against the current DB value before applying the PATCH and resets `agent_endpoint_verified=false` when it changed (same pattern applied to `registry_status`/`name`, 1.5). Also fixed the previously-undocumented bug that had been blocking this exploit path in practice (`Business.id.cast("text")` 500ing `/verify-endpoint` on every call with `entity_id`, known-issues #18) — S-7 is now closed on a code path that can actually be exercised, not just one that happened to be unreachable. **Live-verified end to end on prod**: created a test business, set `agent_endpoint`, called `/verify-endpoint` (previously always 500'd, now 200) → `agent_endpoint_verified` went `true` (confirmed via a follow-up `GET`, i.e. really persisted, not just in the response body) → PATCHed `agent_endpoint` to a different URL → response and a second `GET` both show it reset to `false` |
| S-8 | `GET /businesses/{id}/blocks` leaks private blocks | 🟡 | known-issues | 1.x (block read authz) | ✅ CLOSED 2026-08-05 (15.3 verification) — fixed by **api PR #10** (`5c46ad8`, "fix(api): close private-block leak on GET /businesses/{id}/blocks (1.1)"). `list_blocks` (`blocks.py:88-113`) now filters `Block.is_public.is_(True)` whenever the caller isn't the resolved owner. **Live-verified on prod**: created one public + one private block on a test entity, then `GET /businesses/{id}/blocks` with no `Authorization` header and separately with a garbage bearer token — both returned only the public block; the same request with the owner's token returned both. Note (unchanged from before): `GET /blocks/{block_id}` permalink (1.20, api PR #13) never shared this bug — it correctly 404s a private block to non-owners; only the list endpoint was ever affected. **New bug found in passing, unrelated to S-8's leak**: `POST /businesses/{id}/blocks` (create) ignores the `is_public` field in `BlockCreate` entirely — new blocks are always created public regardless of payload; a caller must `PATCH` afterward to make one private. Logged in `known-issues.md` |
| S-9 | `/verify/domain/check` mild SSRF (boolean fetch to caller-influenced host) | 🟡 | 6.1 #7 sibling | api PR #8 (1.21 bundle) | ✅ CLOSED 2026-07-18 — `domain_ownership._check_file` now resolves the host and rejects private/loopback/link-local/reserved IPs (incl. 169.254.169.254) + `follow_redirects=False`; prod-verified rejecting a private-resolving domain. DNS-TXT path was already safe (DoH only) |
| S-10 | In-memory rate limiters → single-worker-only; `/v1/tag-ping` now has a limiter (api PR #12) but it's the same in-memory pattern, still not multi-worker-safe | 🟠 | architecture / 12.5b | devops (Redis) | OPEN (design) — rate limiting exists, Redis migration still pending |
| S-11 | `teta-pi/mcp` README claims `auth: Bearer` — not implemented anywhere in `mcp/src/index.ts`; every MCP tool call is fully anonymous. Confirmed live: `POST mcp.tetapi.dev/mcp` `initialize` with zero auth headers succeeds normally | 🟠 | 7.x MCP audit (2026-08-04) | `2 mcp` | **CLOSED** 2026-08-05, `2.9` — `mcp/README.md` false `auth: Bearer` line removed, now correctly states no auth. Real auth remains unimplemented; whether to add it before scaling agent traffic is an **open product decision**, raised explicitly in the `2.9` PR, not resolved by this fix |
| S-12 | `teta-pi/mcp` has zero request logging — no tool/entity/latency/success-fail trail anywhere (`mcp/src/*` grepped in full, only 3 static boot `console.log`s exist) | 🟠 | 7.x MCP audit (2026-08-04) | `2 mcp` | **CLOSED** 2026-08-05, `2.9` — structured JSON stdout logging (tool, entity, latency_ms, ok/error) added around every tool call via a single `server.tool` wrapper in `mcp/src/index.ts`; captured by `journalctl -u tetapi-mcp`, live-verified |
| S-13 | `teta-pi/mcp` has no rate-limiting of its own — every tool call is free, unauthenticated (S-11), and unlimited; MCP is a second anonymous ingress point in front of `api.tetapi.dev` distinct from the API's own limits (S-10) | 🟡 | 7.x MCP audit (2026-08-04) | `2 mcp` | **CLOSED** 2026-08-05, `2.9` — 60 req/min/IP in-memory sliding-window limiter on `/mcp`, same pattern as `/v1/tag-ping`/badge (api PR #12); live-verified tripping to `429` past the limit |
| S-14 | `teta-pi/mcp`'s `sessions` Map (`index.ts:571`) has no expiry beyond `transport.onclose` — a client that never sends a clean session `DELETE` (crash, network drop) leaks its transport for the process lifetime | 🟡 | 7.x MCP audit (2026-08-04) | `2 mcp` | OPEN — invisible under today's traffic, an unbounded slow memory leak under sustained real agent traffic with many imperfectly-closed sessions |

**Closed-item provenance:** S-1 and S-2 both landed in
[`teta-pi/api` PR #3](https://github.com/teta-pi/api/pull/3) —
*"fix(security): media path traversal (1.6) + SSRF-prone /verify-endpoint (1.7)"*,
merged 2026-07-14. (Note: the `docs/changelog.md` line that reads "PR #3 TWIRA
block embeddings" refers to a *different repo's* PR #3, not the api security fix —
verified against the api repo's PR list on 2026-07-18.)

---

## 6. Recurring loop — design for 15.2 (implementation deferred)

Goal: a **standing** security posture that runs itself with **zero server load** —
all heavy analysis on the GitHub runner — plus a light read-only re-audit cadence.
15.1 designs it; **15.2 implements** (`.github/workflows/*`).

### 6.1 CI static analysis (runner-side, no prod impact)

| Tool | Targets | Trigger | Notes |
|------|---------|---------|-------|
| **CodeQL (JavaScript/TypeScript)** | `web/`, `mcp/`, `landing/*.js`, `tag.js` | PR + push to `main` + weekly schedule | GitHub's default `security-extended` query pack; results → Security tab |
| **CodeQL (Python)** | `api/` | same | catches SQLi/SSRF/path-traversal patterns statically |
| **`npm audit`** | `web/`, `mcp/` (per-lockfile) | PR + weekly | fail on `high`+; `--omit=dev` for the runtime picture |
| **`bandit`** | `api/app/` | PR + weekly | Python security linter; baseline-file to suppress accepted findings |
| **secret scan** | whole repo | PR + push | e.g. `gitleaks` or GitHub secret scanning; guards A7 |

Design constraints:
- Runs **only on GitHub-hosted runners** — the maxed prod droplet
  (server-capacity) is never touched.
- One workflow file per concern under `.github/workflows/`; matrix over the two
  CodeQL languages.
- **Non-blocking to start** (report to Security tab), then tighten to
  **fail-the-PR on new `high`/`critical`** once the baseline is clean, so the
  backlog (§5) doesn't wedge merges on day one.
- Findings feed back into §5 of this doc (the tracking table is the single source
  of truth).

### 6.2 Read-only authorized re-audit cadence

- **Cadence:** monthly manual pass (session 15.x) — re-run the §4 checklist
  against current code, refresh `✅/⚠️/☐`, and diff against the last pass.
- **Scope:** read-only, our infra only, no exploitation, no prod writes (§ Rules
  of engagement). Live checks limited to non-destructive GETs against prod.
- **Trigger for an off-cadence pass:** any new public/unauthenticated surface
  (e.g. `/v1/tag-ping`, Universal Tag wk-generator, device-upload changes) gets a
  targeted review *before* it ships.
- **Output:** update §4/§5 here + append to `docs/known-issues.md` for any new
  concrete `file:line` finding + a `docs/changelog.md` entry.

### 6.3 Explicitly out of scope for the loop
- No DAST / active scanning against prod, no fuzzing that writes, no load/DoS
  simulation (server-capacity + rules of engagement).
- No third-party targets.
- Secret rotation, WAF, nginx/systemd hardening = devops direction, raised
  separately with the owner (prod-affecting).

---

*Maintained by direction 15. Keep §4/§5 current; docs are canonical for anything
code-related (`CLAUDE.md`).*
