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
| A2 | **`pk_live_…` personal API keys** | Bearer-equivalent to a full account (agents, WP plugin, Universal Tag). Leak = account takeover | `users.api_key`, minted at `/auth/personal-api-key`, checked in `get_current_user`. Sibling: **Pi CAM device keys** (`devices.api_key`, `X-Device-Api-Key`, bearer-equivalent for `/media/device-upload`) — revocable since 1.25 (owner/device/admin paths, S-21) |
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
| **B6** | co-tenant ↔ shared host | an **unrelated project** (`hellfire`/`hellfiresol.com`, and `shos`/SH.OS from 5.8) holding a local unprivileged account on the same droplet → the TETA+PI stack, its secrets, its data stores | read TETA+PI secrets off disk (`.env`, C2PA keys), reach TETA+PI's Postgres/Redis over the shared loopback, own/modify TETA+PI's app tree, exhaust shared RAM/CPU/disk | filesystem perms + ownership on `/opt/tetapi`, DB/Redis auth, systemd resource slices, ufw perimeter. **Controls in place (5.9, 2026-09-19)** — S-18/S-19/S-20 all CLOSED: `.env` is `600 root:root`, `/opt/tetapi/api` (+ certs) is `root:root`, Redis requires `AUTH`. Combined with the deliberately-unprivileged `shos` account (no sudo, no docker group, systemd-capped) and the on-host ufw perimeter, the shared-host controls B6 depends on are now enforced. **Re-audited 15.7 (2026-09-20), verdict per co-tenant:** `shos` isolation **holds** — deliberately unprivileged (no sudo, no docker group, systemd-capped incl. `MemorySwapMax=0`), rootless docker only, cannot read `.env`, redis `-NOAUTH`, postgres `:5432` from the host demands **SCRAM** (auth code 10, not `trust` — the pg_hba `127.0.0.1/32 trust` line is unreachable from the host because docker-proxy rewrites the source to the bridge gateway), cannot read `/var/log`/other-user journals, ports loopback-only (`127.0.0.1:8200`), perimeter `ufw` blocks it externally (confirmed 8200 filtered from off-box). `hellfire` isolation is **broken**: root-equivalent via the `docker` group (**S-21**) and, live again, owns `/opt/tetapi/api` which the root-run api service executes (**S-19 regressed**). Residuals: no per-user disk quota (monitor), pg_hba loopback `trust` is safe only incidentally (topology, not auth), `hellfire` uncapped by any systemd slice. `docs/deployment.md` "Co-tenant: shos (SH.OS)" |

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
- ⏳ **`POST /verify-endpoint`** — **FIX READY (S-16 → 15.5, api PR #31, CI-green;
  closes on merge+deploy)**. All caller-supplied URLs pass
  `app/core/ssrf.py::assert_safe_url` before any fetch
  (http/https, no literal IPs, public-resolving host, port 80/443), and both
  fetches use `follow_redirects=False`. `assert_safe_url` is the shared guard for
  any future caller-URL route. Residual: DNS-rebinding (resolve≠fetch), tracked.
- ✅ `/verify/domain/check` — `domain_ownership._check_file` resolves the host and
  rejects private/loopback/link-local/reserved IPs (incl. 169.254.169.254) +
  `follow_redirects=False` (S-9, api PR #8). DNS-TXT path is DoH-only.
- ☐ All external egress (registries, DNS-over-HTTPS, agent endpoints, OTS, Resend,
  OpenAI): registry verifiers + Resend + OpenAI use **fixed** hosts (params only,
  not caller-host) — not SSRF; confirm timeouts + response size caps as hygiene.

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
| S-2 | `POST /verify-endpoint` unauthenticated server-side GET (SSRF) | 🟠 | 6.1 #7 | 1.7 | **CLOSED** — api PR #3 (merged 2026-07-14): auth/rate-limit added. **Correction (15.5, 2026-09-21):** auth + rate-limit was never an actual SSRF *mitigation* — it only narrowed *who* could trigger the fetch, and even that regressed to "anyone" once the MCP service key made the tool anonymous again (mcp #9). The server still fetched arbitrary caller URLs. The real SSRF control (URL validation / private-IP block) landed only in **S-16 → 15.5** (api PR #31). This row stays CLOSED for the *original* narrow finding; S-16 is the SSRF fix of record |
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
| S-15 | `POST /auth/agent-key` unauthenticated, unrate-limited account+`pk_live_` key mint — live exploited on prod (2 probe accounts found) | 🔴 | 6.6 UI/backend sync audit (2026-09-11) | `15.4` | ✅ **CLOSED 2026-09-11** — endpoint deleted outright, [api PR #23](https://github.com/teta-pi/api/pull/23). Zero call-sites in `web`/`mcp`/`pi-cam`/WP plugin (grepped fresh checkouts independently of the audit), present unchanged since the repo's first commit (`83d5fba`), never documented in `docs/api.md`'s Auth table, and `is_agent` (the flag it set) has no admin-provisioning flow to gate behind — nothing to gate, so removal (not `require_admin`) was the clean fix. **Two prod accounts created by live probing** (`agent-e4f27342559dced1@teta-pi.agent` 2026-09-11 15:06, `agent-df2830672772c722@teta-pi.agent` 15:14) deactivated via `is_active=false` (rows kept, append-only discipline — A4) after explicit owner confirmation; `get_current_user` (`app/api/deps.py:15-41`) checks `is_active` on both the JWT and `pk_live_` paths, so this alone revokes both. Checked for other `is_agent` rows of unknown origin: one pre-existing row, `agent@tetapi.dev` (2026-07-04, `role=admin`) — legitimate, seeded in migration `007_roles_admin_audit.py:18` as a founder-designated "operations agent" admin account, unrelated to this exploit, left untouched. **Live-verify after deploy:** re-curl `POST /auth/agent-key` with empty body, expect `404` (route gone), not `200`. |

| S-16 | `POST /verify-endpoint` still performs a server-side GET to any caller-supplied URL with **no host validation** — S-2's "fix" only added auth (`get_current_user`), not an allowlist/private-IP block. A caller with any active-account `pk_live_` key (a free signup, or the MCP service key) makes the prod server fetch `http://127.0.0.1:8000/…`, `169.254.169.254`, RFC1918 — `is_active:true` when the target responds = a loopback **port oracle**. `_verify_active`/`_verify_consistency` in `endpoint_verification.py` do `client.get(url, follow_redirects=True)` with no `_resolves_to_public_ip` guard (contrast `domain_ownership._check_file`, which has one since S-9) | ✅ **CLOSED 2026-09-21 (15.5, api PR #31)** — `app/core/ssrf.py::assert_safe_url` at route entry + `follow_redirects=False`; manager live-verified post-deploy: `127.0.0.1:8000`→400 (port), `169.254.169.254`/`[::1]`→400 (IP literal), `localhost`→400 (resolves private), public https→200 `is_active:true`; probe run 35620078993 = 21 PASS / 0 FAIL (`ssrf[*]`, `mcp[verify_endpoint_ssrf]` green). Residual: DNS-rebinding (resolve≠fetch) — pin resolved IP on httpx transport is a separate owner-decision task. Orig:  | 15.6 probe (2026-09-14) | `15.5` | ⏳ **FIX READY — CLOSES on merge+deploy (15.5, 2026-09-21)** — [api PR #31](https://github.com/teta-pi/api/pull/31), CI (pytest 5.7) **green**; merge is the manager's gate (worker cannot merge/deploy). New `app/core/ssrf.py::assert_safe_url` validates `endpoint_url` **before any fetch**: http/https only, **literal IPs rejected outright** (agent endpoints are domains — this collapses the IPv4/IPv6/IPv4-mapped-literal bypass class in one rule), host resolved via `getaddrinfo` with **every** A/AAAA rejected on `is_private/loopback/link_local/reserved/multicast/unspecified` (IPv4-mapped `::ffff:` unwrapped first — its own `is_loopback` is False), port **80/443 only** (kills the internal-port scan even against a public host) → HTTP 400. Both `_verify_active`/`_verify_consistency` now use `follow_redirects=False` (3xx→not-active) so a public URL can't 302 to an internal address. `get_current_user` kept (NOT reverted to auth-only — that killed the MCP tool for 2mo). 30-case `tests/test_ssrf_guard.py` (pytest, 5.7 CI). **Residual (documented, tracked): DNS-rebinding** — the host is resolved in the guard and re-resolved by httpx at fetch; a TTL-0 record could answer public-then-private. Full fix = pin the resolved IP onto the httpx transport (separate task, owner's call). Probe `ssrf_canaries`+`mcp[verify_endpoint_ssrf]` go green on deploy; live-verify: `127.0.0.1:8000/health` → **400** (was `is_active:true`), real public https → `200 is_active:true` |
| S-17 | Private (`is_public=false` / `is_published=false`) entity is fully readable by anyone who knows its UUID via `GET /businesses/{id}`, `GET /businesses/{id}/preview` and `/proof` (name, description, blocks) — only private *blocks* were ever scoped (S-8); the entity row and the agent preview/proof were not. `get_business`/`agent_preview`/`get_proof` have no `is_public` filter for non-owners. `by-slug/{slug}/public` is correctly scoped, which is why this went unnoticed | 🟡 | 15.6 probe (2026-09-14) | owner decision (backend) | ✅ **CLOSED 2026-09-14** — owner decision: filter (a UUID-readable private entity contradicts `is_public` itself; same rule as S-8). Fixed by [api PR #26](https://github.com/teta-pi/api/pull/26) (1.25): `_get_visible_business` in `businesses.py` — owner always sees, everyone else gets **404** (not 403, a guessed UUID confirms nothing) when `is_public=false` OR `is_published=false`; applied to `GET /businesses/{id}`, `/preview`, `/proof`, plus the two block reads (`/businesses/{id}/blocks`, `/blocks/{block_id}`) which S-8 had left listing a private entity's public blocks. Bonus: `/preview` and `/proof` also stopped emitting non-public blocks/media ids of *public* entities (they iterated `business.blocks` unfiltered; `by-slug/public` already filtered). `get_optional_user` promoted to `api/deps.py`. Companion [web PR #47](https://github.com/teta-pi/web/pull/47): `/profile` now sends the owner token on the two reads it did anonymously (else a private entity's own profile would render empty). Live-verified post-deploy (see changelog). Probe: `private_entity_exposure` rewritten to assert 404 on all four reads for anon + 200 for the owner against a dedicated private fixture (`s17_private_entity`); `pending_owner_decision` entry removed from `public_allowlist.json` |
| S-18 | **`/opt/tetapi/api/.env` is `644` (world-readable)** — any local account (the `hellfire` co-tenant, the new `shos`, anyone) reads the Fernet PII key (A7/A8 → decrypt all PII), JWT secret (forge any session), `DATABASE_URL`, `REDIS_URL`, `RESEND_API_KEY`. Live-confirmed 2026-09-18: `sudo -u shos cat /opt/tetapi/api/.env` succeeded. Not web-exposed (the probe's `secrets` HTTP check is green) — this is a **local co-tenant** vector (B6) invisible to the runner probe | ✅ | 5.8 co-tenant provisioning (2026-09-18) | TETA+PI backend/devops | **CLOSED (5.9, 2026-09-19)** — `chmod 600` applied (was already `root:root`, only mode was 644); after: `stat` = `600 root:root`, api health 200. `cotenant_check.sh` → "shos cannot read /opt/tetapi/api/.env". Note: `.env` is rsync-excluded in `deploy.yml`, so the mode survives deploys. C2PA signing key is stored inline in `.env` (`C2PA_SIGNING_KEY_PEM`), so this fix also protects it |
| S-19 | **`/opt/tetapi/api` and `/opt/tetapi/api/certs` are owned by `hellfire:hellfire`** — a *different co-tenant* owns TETA+PI's production API tree and can rewrite our prod code or swap the C2PA signing key (A5). Trust inversion: hellfire is effectively more privileged over TETA+PI's own files than TETA+PI is. `/opt/tetapi/{web,mcp,venv}` are correctly `root:root`; only `api` drifted | 🔴 | 5.8 co-tenant provisioning (2026-09-18) | TETA+PI devops (CI deploy) | **REOPENED — REGRESSED (15.7, 2026-09-20).** 5.9's `chown -R root:root` was undone by the very next `api` deploy: on 2026-09-20 `/opt/tetapi/api` **and** `certs` are `755 hellfire:hellfire` again (`web/mcp/venv` still `root:root`, `.env` still `600 root:root` — S-18 held because `.env` is rsync-excluded). **Root cause (found this pass, not a mystery this time):** `api` repo `.github/workflows/deploy.yml` rsyncs with `rsync -az … root@…:/opt/tetapi/api/`. `-a` implies `-o -g`, so as root on the receiving side rsync **preserves the SOURCE's numeric uid/gid** — the GitHub-hosted runner checkout is uid **1001**, which on the droplet is **hellfire**. Every api deploy re-stamps the tree 1001:1001. The 5.9 note "deploy.yml rsyncs as root@ (so ownership survives)" was wrong: sshing *as* root is not enough; `-a` copies the runner's ownership. **Blast radius is now 🔴, not the earlier ✅:** `tetapi-api` runs as **root** (`systemctl show tetapi-api` → `User=` empty; uvicorn proc owner root) and executes the code in `/opt/tetapi/api`, which hellfire owns and can write → **hellfire can drop code into the API and have it run as root** (a second hellfire→root path independent of S-21's docker group). **Fix (devops, prod-CI — out of scope for dir 15):** add `--chown=root:root` (or `--no-owner --no-group`) to *both* api rsyncs in `api/.github/workflows/deploy.yml`, then a one-time `chown -R root:root /opt/tetapi/api && chmod 700 /opt/tetapi/api/certs`; re-run `cotenant_check.sh` (its S-19 assert already catches this — it is what re-found the regression). Reopened, not a new S-number, per §5 "one row per S". |

| S-19 | **`/opt/tetapi/api` and `/opt/tetapi/api/certs` are owned by `hellfire:hellfire`** — a *different co-tenant* owns TETA+PI's production API tree and can rewrite our prod code or swap the C2PA signing key (A5). Trust inversion: hellfire is effectively more privileged over TETA+PI's own files than TETA+PI is. `/opt/tetapi/{web,mcp,venv}` are correctly `root:root`; only `api` drifted | ✅ | 5.8 co-tenant provisioning (2026-09-18) | TETA+PI backend/devops | **CLOSED (5.9, 2026-09-19)** — `chown -R root:root /opt/tetapi/api` + `chmod 700 certs` applied; after: `/opt/tetapi/api` + `certs` = `root:root`, certs dir `700`, api health 200, service active. Confirmed `deploy.yml` rsyncs as `root@` (so ownership survives). No `*.key.pem` on disk (the signing key is inline in `.env`, covered by S-18). `cotenant_check.sh` → "/opt/tetapi/api owned by root:root". Risk: rsync `-a` may reset the **certs dir mode** to the repo's on next deploy — the key protection is `.env`/ownership, not the dir bit; next `main` push confirms. **⚠ REGRESSED on first deploy 2026-09-20 (run `35539343701`, `1f5967c`) — the whole tree reverted to `hellfire:hellfire`. Cause: `rsync -az` preserves the runner's numeric uid/gid (`runner` = uid 1001 = `hellfire` on the droplet) even under root — the "rsyncs as root@ so ownership survives" assumption was wrong. FIXED (5.11, 2026-09-21):** `deploy.yml` both rsync steps now pass `--chown=root:root`, and the deploy re-asserts `chmod 700 certs`. Verified after: `find /opt/tetapi/api ! -user root` → 0, certs `700 root:root`, health 200, `cotenant_check.sh` S-19 assert green |
| S-20 | **Redis answers unauthenticated on the shared loopback `127.0.0.1:6379`** — a co-tenant (shos/hellfire) can read/write/flush TETA+PI's Redis: email codes (A9), rate-limit state, celery broker, tag-ping data. Live-confirmed 2026-09-18: `PING` from `shos` returned `+PONG` with no `AUTH`. Same shared-loopback exposure applies to Postgres `:5432` (reachable, auth status unverified) | ✅ | 5.8 co-tenant provisioning (2026-09-18) | TETA+PI backend/devops | **CLOSED (5.9, 2026-09-19)** — Option A: standalone `tetapi-redis` container recreated with `--requirepass` (32-byte secret at `/root/tetapi-redis.pass`, `600`; volume/publish/restart preserved; loopback publish kept for host services), `REDIS_URL` updated in `.env`, `tetapi-api`/`celery-worker`/`celery-beat` restarted (all active, worker reconnected + "ready"). From `shos`: `PING` → `-NOAUTH Authentication required.`. `cotenant_check.sh` → "redis rejects unauthenticated access". **Residual — resolved 5.10 (2026-09-20):** Postgres `127.0.0.1:5432` is TCP-reachable from `shos` but **password-gated** — a raw startup packet as `tetapi`/`postgres` returns `AuthenticationSASL` (SCRAM), not `trust`, so no unauthenticated DB access; residual is only the reachable port (behind a strong password). Separately, 5.10 (SH.OS access-enable) found the systemd RAM cap was not a hard ceiling (swap spill) and fixed it — `MemorySwapMax=0`, drop `MemoryHigh` (`docs/deployment.md` limits table) |
| S-21 | **Pi CAM device key (`devices.api_key`, `X-Device-Api-Key`) could never be revoked** — once paired, the upload credential was valid forever: `devices_router` had no revoke route, the pi-cam "Unlink" button only wiped local SecureStore, rotating the personal `pk_live_` key didn't touch it, and `routes/admin.py` had no kill switch. A lost/stolen/sold camera (or anyone who extracts the key) could upload media to the profile indefinitely — same asset class as A2, but with *no* rotation path at all (`known-issues.md` 6.6b) | 🔴 | 6.6 UI/backend sync audit addendum (2026-09-11) | `1.25` (api) + `14.11` (pi-cam) + `3.25` (web) | ✅ **CLOSED 2026-09-20** — [api PR #29](https://github.com/teta-pi/api/pull/29): migration 015 (`devices.revoked_at`, `api_key` nullable); revocation **erases** the secret (`api_key=NULL`, `is_active=false`, `revoked_at=now`) and `_get_device` rejects revoked/inactive/keyless rows in Python → 401 on `/media/device-upload`. Three paths: owner `DELETE /devices/{id}` (owner-checked, foreign → 404), device `POST /devices/self-revoke` (auth = its own key, so it can only kill itself — what pi-cam "Unlink" now calls, [pi-cam PR #11](https://github.com/teta-pi/pi-cam/pull/11)), admin `DELETE /admin/devices/{id}` (`require_admin` + `admin_audit_log` `devices.revoke`). `GET /devices` exposes `revoked_at`; web `/profile` got a per-device Revoke button ([web PR #48](https://github.com/teta-pi/web/pull/48)). Append-only trail: `verification_events` `device_revoked` (level 0, source owner/device/admin). Regression: `tests/test_device_revoke.py` in api CI + `probe.py` `check_s21_device_revoked` (fixture `s21_revoked_device`, the one justified prod write — see `scripts/security/README.md`) |

| S-21 | **`hellfire` is in the `docker` group → root-equivalent over the whole droplet, incl. TETA+PI** — `getent group docker` = `bob,hellfire`. Membership in `docker` is membership over the root-owned `/var/run/docker.sock` (`srw-rw---- root:docker`); `docker run -v /:/host …` (or `--privileged`) mounts the host root as root, so hellfire can read `.env` (Fernet key A7 → decrypt all PII; JWT secret → forge sessions), read the Postgres data volume directly, and rewrite `/opt/tetapi`. This is the strongest standing B6 vector and it is **unconditional** — independent of what hellfire's containers currently mount. Live-checked 2026-09-20: hellfire's two current containers (`gtm-agent-inbox-1` :8090, `internal-db-db-1` :5433) are themselves benign (no bind mounts of the host, `Privileged=false`, no `CapAdd`, loopback-only ports) — but that constrains today's containers, not hellfire's capability. Contrast `shos`, which is deliberately **not** in `docker` and runs **rootless** docker (verified: `shos docker ps` hits its *own* rootless daemon; forcing `DOCKER_HOST=unix:///var/run/docker.sock` → `permission denied`). | 🔴 | 15.7 co-tenancy re-audit (2026-09-20) | TETA+PI devops + HF coordination | **OPEN** — the fix is to migrate hellfire off the host docker daemon to **rootless docker** (the model shos already uses) and remove hellfire from the `docker` group; a prod-config + cross-tenant change, so it is a manager/devops boot, not dir 15. `cotenant_check.sh` now asserts hellfire ∉ docker group (honestly RED until fixed, same pattern S-18/19/20 used). Not runner-visible → no `probe.py` assert |
| S-22 | **Pre-verified-entity takeover: `POST /businesses/{id}/claim/domain/check` never binds the *proven* domain to the entity's real anchor** — the claim flow (roadmap 1.11, the GTM Phase 2 gate) calls `domain_ownership.check_domain_verification(business_id, payload.domain)` with a **caller-supplied** `payload.domain` and, on success, does `business.owner_id = current_user.id; claim_status = "claimed"`. There is **no check anywhere** that `payload.domain` equals the entity's imported anchor (`pre_verified_source.domain`, set in `admin.py::bulk_preverify_entities`). So any signed-up (free email-code) user can claim any `pre_verified_unclaimed` entity — e.g. a bulk-imported "Coca-Cola" — by proving they control a **throwaway domain they own** (place `_tetapi-verify.<theirdomain>` TXT / well-known file), not the business's real domain. `_get_claimable_business`'s `claim_status == "pre_verified_unclaimed"` gate holds (you can't claim a `self_registered`/`claimed` entity) — the hole is purely the missing anchor match. Same root (`check_domain_verification` accepts an arbitrary domain) mildly affects the owner-side `verify/domain/check` too (an owner can mark their own entity "domain_verified" against an unrelated domain they hold — trust-inflation, lower sev since they already own the entity). | 🔴 | 15.7 (2026-09-20), code review of 1.11 | backend (1.11 follow-up) | **OPEN — currently LATENT.** Prod has **0** `pre_verified_unclaimed` rows (`self_registered`=17, `opted_out`=6), so nothing is claimable *today*; the takeover goes live the instant GTM Phase 2 runs `bulk-preverify` to import real businesses. Must fix **before** that import. **Fix:** in `check_claim_domain_verification` (`businesses.py:508`) require `normalize_domain(payload.domain) == normalize_domain(business.pre_verified_source["domain"])` before transferring ownership (reject otherwise). Not cleanly runner-assertable without a prod fixture (creating one is a write, forbidden) + a controlled domain — its regression test ships **with** the fix per §6.2, ideally as a `cotenant_check`-style or fixtured check |
| S-23 | **Redis password is written in cleartext to the systemd journal** — `journalctl -u tetapi-celery-worker` contains 3 lines (Sep 19 15:20, right after the S-20 `requirepass` fix) of celery's startup banner printing the full broker URL `redis://:<PASSWORD>@127.0.0.1:6379//` (`transport:`, `results:`, and "Connected to …"). The very secret S-20 introduced to gate Redis is now persisted in plaintext in the journal. | 🟡 | 15.7 (2026-09-20) | devops | **OPEN.** Mitigated: the journal is readable only by root / `adm` / `systemd-journal` — `shos` is denied (`journalctl` → "not seeing messages from other users"); hellfire is root-equiv via S-21 anyway, so no *new* reader gains it today. But it defeats S-20 defense-in-depth and leaks on any journal export/backup or a future lower-priv admin reader. **Fix (devops):** stop celery printing the broker URL (set the password via a redis ACL/`CELERY_BROKER_URL` masked, or feed the pass from `/root/tetapi-redis.pass` at runtime and rotate the leaked one), then `journalctl --rotate --vacuum-time=1s` the old entries. `cotenant_check.sh` now asserts the journal is clean (RED until fixed). Not runner-visible |


**Closed-item provenance:** S-1 and S-2 both landed in
[`teta-pi/api` PR #3](https://github.com/teta-pi/api/pull/3) —
*"fix(security): media path traversal (1.6) + SSRF-prone /verify-endpoint (1.7)"*,
merged 2026-07-14. (Note: the `docs/changelog.md` line that reads "PR #3 TWIRA
block embeddings" refers to a *different repo's* PR #3, not the api security fix —
verified against the api repo's PR list on 2026-07-18.)

### 5.1 Co-tenancy hardening backlog (15.7, 2026-09-20 — lower severity)

Not full S-numbers (defense-in-depth / latent), but tracked so a devops boot can
sweep them together. None are dir-15 fixes (all touch prod config).

- **H-1 `sshd`: `PermitRootLogin yes` for every user** (`sshd -T -C user=…` for bob/hellfire/shos all show `permitrootlogin yes`). Root SSH is key-only in practice (`passwordauthentication no` globally, root has a populated `authorized_keys`), but the policy should be `prohibit-password` (or `no`). 🟡
- **H-2 `hellfire` (uid 1001) has NO systemd resource slice** — only `user-1002.slice.d/limits.conf` (shos) exists. hellfire is uncapped on RAM/swap/CPU/tasks and can exhaust the shared 2 GB swap + thrash disk (the exact failure mode 5.10 fixed for shos). Subsumed by S-21 for *compromise*, but a standalone availability risk. 🟡
- **H-3 `/proc` has no `hidepid`** (`proc /proc … rw,nosuid,nodev,noexec` — no `hidepid=2`), so any local account reads every process's `argv` (`/proc/<pid>/cmdline`) — confirmed shos reading the api's uvicorn cmdline. `/proc/<pid>/environ` is correctly `0400 owner` (shos denied), so env-borne secrets are safe; TETA+PI passes no secrets on argv today, so this is info-leak only. 🟢
- **H-4 tetapi-postgres pg_hba `host all all 127.0.0.1/32 trust` + `::1/128 trust`** inside the container. Safe *today* only incidentally: docker-proxy rewrites host→container source to the bridge gateway (`172.19.0.1`), so a host caller matches the `host all all all scram-sha-256` catch-all, not `trust` (verified: shos startup packet → SCRAM/code 10). Unlike Redis (which got `requirepass` in S-20), Postgres loopback safety rests on network topology, not auth — remove the loopback `trust` lines and rely on SCRAM. 🟡
- **H-5 `tetapi-web` binds `0.0.0.0:3001` and `tetapi-mcp` binds `*:3002`** (not `127.0.0.1`), so a co-tenant can reach them directly on the host; external privacy rests solely on `ufw`. Content served is public anyway, so low — but bind them to loopback (nginx proxies from `127.0.0.1`). 🟢
- **H-6 `cotenant_check.sh` docker assertion false-positived** (fixed this pass): it ran `sudo -u shos docker ps` and flagged success as "host socket access", but shos's default context is now `rootless` (enabled 5.10) so `docker ps` legitimately hits shos's own daemon. The check now forces `DOCKER_HOST=unix:///var/run/docker.sock` to test the real property, and separately asserts hellfire ∉ docker (S-21). ✅ fixed in `scripts/security/cotenant_check.sh`.
- **Observation (not ours — for HF):** hellfire's `internal-db` on `127.0.0.1:5433` **is** password-gated (startup packet → SCRAM). No action for TETA+PI; logged because it shares our host.

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

### 6.2 Read-only authorized re-audit — now an automaton (15.6)

**Last full authorized pass: 15.7, 2026-09-20** (co-tenancy re-audit). Runner probe
18 pass / 2 fail / 3 skip — the 2 fails are both S-16 (`ssrf`, `mcp[verify_endpoint_ssrf]`),
expected-red until 15.5; the 3 skips are the `/docs`+`/redoc` owner question and the
opt-in heavy rate-limit checks. (The 2026-09-20 cron run's extra SKIPs on
`private_entity_exposure`/`headers[mcp]` were a transient `Connection reset by peer`,
not a regression — both re-verified PASS this pass.) On-box `cotenant_check.sh` found
S-19 **regressed** and S-21 (hellfire∈docker); see §5.


Replaced the old "monthly manual pass" with a **daily deterministic probe** —
`scripts/security/probe.py`, run by `.github/workflows/security-probe.yml`
(cron `17 6 * * *`, plus `workflow_dispatch`). It exists because the manual
cadence missed things for months: S-15 (agent-key), S-16 (loopback SSRF) and
the private-block/entity leaks were all found by hand, by luck — never by a
static scanner (§6.1's CodeQL/bandit can't see them).

- **What it asserts:** every CLOSED §5 finding has a matching read-only assert
  (walk the table — each `S-*` maps to a check in `scripts/security/README.md`),
  plus one contract check (`auth_surface`) that fails if any live openapi
  path+method answers 2xx to an unauthenticated caller and isn't in
  `scripts/security/public_allowlist.json`. That allowlist is the contract that
  would have caught S-15 on day one.
- **Scope:** read-only, our infra only, no exploitation, no prod writes (§ Rules
  of engagement). Only GET/HEAD and the POSTs that by design don't write; the
  `verify-endpoint` limiter (5/min) is respected (≤3 SSRF canaries per run);
  high-volume rate-limit tests (badge/tag-ping, >100 req/min) are opt-in
  (`--include-heavy`), never run by cron, since sustained load is out of scope
  (§6.3).
- **On FAIL:** the workflow goes red and opens/updates **one** GitHub issue
  (label `security`) — it comments on the existing open issue rather than
  spawning a new one per run. On PASS it is silent.
- **Report-only — no auto-fix** (owner's call, `docs/decisions.md` 2026-09-14).
  A FAIL that maps to a not-yet-merged fix (e.g. S-16 → 15.5) is *expected* red
  until that fix lands; that's the probe proving it still bites.
- **Trigger for an off-cadence pass:** any new public/unauthenticated surface
  still gets a targeted human review *before* it ships — and lands in the
  allowlist as part of that.
- **Output when a human finds something new:** update §4/§5 here + append to
  `docs/known-issues.md` + a `docs/changelog.md` entry.

**Rule (enforced by convention, not code):** every closed `S-*` gets an assert
in `probe.py` **in the same PR that closes it** — fix and regression test ship
together, so the net only ever grows. New-check mechanics:
`scripts/security/README.md`.

### 6.3 Explicitly out of scope for the loop
- No DAST / active scanning against prod, no fuzzing that writes, no load/DoS
  simulation (server-capacity + rules of engagement).
- No third-party targets.
- Secret rotation, WAF, nginx/systemd hardening = devops direction, raised
  separately with the owner (prod-affecting).

**Security response headers — DONE (5.6, 2026-09-15, devops).** The probe's
`headers[*]` gaps (no HSTS / nosniff / X-Frame-Options on app/api/mcp; landing
missing HSTS) are closed at the nginx origin — see `docs/deployment.md`
"Security response headers". `probe.py::check_headers` re-asserts all four hosts
carry HSTS + `X-Content-Type-Options` + `X-Frame-Options`.

Residuals still open (tracked, not blocking):
- **CSP** — deliberately **not** shipped in 5.6; needs an audit of inline
  scripts/styles on landing + app before a non-breaking policy can be written.
  Own devops task.
- **HSTS strength** — currently `max-age=86400`, no `includeSubDomains`, no
  `preload`. Raise plan (1y → includeSubDomains once every subdomain incl.
  `stats.tetapi.dev` is HTTPS-only → preload only by explicit owner decision) in
  `deployment.md`. Until `max-age` is a year and includeSubDomains is set, HSTS
  coverage is partial by design.
- **Cloudflare SSL mode = residual on the CF→origin hop.** Origin is `listen 80`
  only (no per-tetapi 443 vhost), so Cloudflare reaches the origin over plain
  HTTP (Flexible-mode behaviour). HSTS is still correct and enforced for the
  browser↔Cloudflare hop (where a real user's TLS lives); the CF→origin hop is
  inside DigitalOcean's network but is not itself TLS. Moving CF to Full(-strict)
  + a 443 origin vhost would close it — separate devops decision, **owner to
  confirm the current CF SSL mode** (inferred Flexible from the origin config,
  not read from the CF dashboard this session).

---

*Maintained by direction 15. Keep §4/§5 current; docs are canonical for anything
code-related (`CLAUDE.md`).*
