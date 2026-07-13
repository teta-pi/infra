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

## 2026-07-13 — Monorepo → separate repos (scope C) split plan (5.2 design)

**Plan only — zero code moves, zero repo creation, zero deploy/server changes
in this session.** This is the design that becomes execution task **5.3**, which
is 🔴 deferred until the 9.1 server resize lands (see §7 below). Owner decision
2026-07-13: scope **C** — full extraction of `api` / `web` / `mcp` / `landing`
out of the `teta-pi` monorepo into separate GitHub repos under org `teta-pi`.

### Starting state (measured this session, not assumed)
- Monorepo root `teta-pi` (`private`, npm `workspaces: ["web","mcp"]`, one root
  `package-lock.json`). Components: `api/` (FastAPI), `web/` (Next.js 15),
  `mcp/` (TS), `landing/` (static HTML), plus `wordpress-plugin/`, `deploy/`
  (nginx confs + `deploy.sh`), `docker-compose*.yml`, `docs/`, `CLAUDE.md`.
- **No inter-package code coupling.** `web` (`teta-pi-web`) and `mcp`
  (`@teta-pi/mcp`) never import each other; grep for cross-component relative
  imports returns nothing. The root workspace + shared lockfile is a *build
  convenience only*, not a dependency graph. There are **no shared TS types**
  between web / mcp / api.
- Both cross-component runtime contracts are already loose HTTP: `web→api` via
  build-time `NEXT_PUBLIC_API_URL=https://api.tetapi.dev`, `mcp→api` via
  `TETA_PI_API_URL` (systemd env on server). Neither imports the other's code.
- One deploy pipeline (`.github/workflows/deploy.yml`) rsyncs *all four*
  components on push to `main`, using the `DEPLOY_SSH_KEY` secret; a second
  ops workflow (`unban-ip.yml`) uses the same key. Branch protection (7.1) is
  applied on the mono only. Server layout is unchanged by this split:
  `/opt/tetapi/{api,web,mcp}` + `/var/www/teta-pi/` (landing).

This is the ideal case for a split: the only thing binding the components today
is one CI file, one root `package.json`, and one lockfile — all cosmetic.

### 1) Target repo layout
Five repos under **`teta-pi`** (four scope-C components + one meta/infra repo):

| Repo | Contents | Deploys to |
|---|---|---|
| `teta-pi/api` | `api/**` + component doc `docs/api.md`, `docs/database.md`, `docs/registries.md` | `/opt/tetapi/api` |
| `teta-pi/web` | `web/**` + `docs/` web notes | `/opt/tetapi/web` |
| `teta-pi/mcp` | `mcp/**` + `docs/mcp.md` | `/opt/tetapi/mcp` |
| `teta-pi/landing` | `landing/**` | `/var/www/teta-pi/` |
| **`teta-pi/infra`** (meta) | canonical `docs/` (overview, architecture, decisions, roadmap, changelog, glossary, known-issues, deployment, security, gtm, verification-rework), root `CLAUDE.md`, `deploy/nginx/*`, `deploy.sh`, `docker-compose*.yml`, `.env.example`, `unban-ip.yml`, server runbooks | nothing (ops/brain only) |

**`wordpress-plugin/`** is a shippable, independently-distributed artifact (a
plugin users install), not part of the running server — it gets its own repo
`teta-pi/wordpress-plugin`. It is outside the named scope-C four, but should
move in the **same** cutover to avoid a second migration later. Noted, not
gated.

**Where docs / CLAUDE.md / roadmap live post-split — the one real design
tension.** The session model (numbered directions, a manager session, `docs/`
as canonical brain) is inherently *cross-repo*; roadmap/changelog/decisions
describe all components at once and cannot sensibly live inside any single
component repo. So the **canonical `docs/` + roadmap + changelog + decisions
live in `teta-pi/infra`.** But Claude Code auto-loads `CLAUDE.md` from the
working repo's root — a session working in `teta-pi/api` would not see the
infra repo's rules. Resolution:
- Each component repo gets a **thin `CLAUDE.md`** (the coding rules + "canonical
  docs live in `teta-pi/infra`; read `docs/<x>.md` there before touching this
  repo") so per-session auto-load still fires.
- **Component-specific** docs move *with* their component (so a code+doc change
  is one PR): `api.md`/`database.md`/`registries.md` → `teta-pi/api`,
  `mcp.md` → `teta-pi/mcp`.
- **Cross-cutting** docs stay in `teta-pi/infra` (canonical). This keeps the
  "docs are the source of truth" rule intact while respecting the auto-load
  mechanic. Accepted trade-off: two homes for docs, mitigated by the thin
  per-repo pointer.

Rejected: (a) a single "docs live only in infra" model — breaks `CLAUDE.md`
auto-load and forces every code PR to also PR a second repo for its own doc;
(b) duplicating full `docs/` into every repo — guarantees drift, the exact
thing `docs/decisions.md` §2026-07 already rejected for doc folders.

### 2) Git history — per-component extraction with `git filter-repo`
**Recommend: preserve per-folder history via `git filter-repo`, not a clean
cutover.** History has real value here — `git blame` traces every decision back
to its changelog/roadmap entry, and the audit-trail culture of this project
(append-only tables, dated decisions) extends naturally to keeping code
provenance. A squash cutover throws that away permanently for a one-time
convenience; not worth it.

Exact commands (run once **per component**, each on a fresh throwaway clone so
the original mono is never mutated — `filter-repo` rewrites history
destructively in the clone):

```bash
# install once: brew install git-filter-repo   (or pip install git-filter-repo)

# --- api ---
git clone https://github.com/teta-pi/<mono>.git api-extract
cd api-extract
git filter-repo --path api/ --path docs/api.md --path docs/database.md \
                --path docs/registries.md --path-rename api/:
git remote add origin git@github.com:teta-pi/api.git
git push -u origin main --tags
cd ..

# --- web ---   (same pattern)
git clone https://github.com/teta-pi/<mono>.git web-extract
cd web-extract && git filter-repo --path web/ --path-rename web/:
git remote add origin git@github.com:teta-pi/web.git && git push -u origin main --tags && cd ..

# --- mcp ---
git clone https://github.com/teta-pi/<mono>.git mcp-extract
cd mcp-extract && git filter-repo --path mcp/ --path docs/mcp.md --path-rename mcp/:
git remote add origin git@github.com:teta-pi/mcp.git && git push -u origin main --tags && cd ..

# --- landing ---
git clone https://github.com/teta-pi/<mono>.git landing-extract
cd landing-extract && git filter-repo --path landing/ --path-rename landing/:
git remote add origin git@github.com:teta-pi/landing.git && git push -u origin main --tags && cd ..
```

`--path-rename api/:` strips the leading folder so files land at the new repo
root. `teta-pi/infra` is the exception: it keeps the mono's cross-cutting
`docs/`, `CLAUDE.md`, `deploy/`, compose files, and workflows — simplest to
create it by `filter-repo`-ing *out* the four component folders
(`git filter-repo --invert-paths --path api/ --path web/ --path mcp/ --path landing/`)
so it retains everything else with full history, then curating.

### 3) Cross-repo contracts & decoupling
- **web→api / mcp→api**: already HTTP against `api.tetapi.dev`; no code
  coupling. Each keeps its env var (`NEXT_PUBLIC_API_URL`, `TETA_PI_API_URL`).
  Nothing to decouple at runtime — the split is invisible to running services.
- **npm-workspace / lockfile coupling (the only build coupling)**: delete the
  root `package.json` (`workspaces`) and root `package-lock.json`; `web` and
  `mcp` each already have their own `package.json`. Each repo generates its own
  `package-lock.json` on first `npm install`. Because there are **no
  `@teta-pi/*` inter-package deps**, this is a no-op for the dependency graph —
  no `file:`/`link:`/`workspace:` references to rewrite.
- **Shared types**: none exist. The API's OpenAPI schema is the *de facto*
  contract, consumed by hand-written clients (`web/src/lib/api.ts`, mcp's HTTP
  layer). Leave as-is. If typed contracts are ever wanted, generate them from
  `api`'s OpenAPI into web/mcp at build time — explicitly **out of scope** for
  the split; do not introduce a shared package (would re-create the coupling
  we're removing).
- **`agent.json` duplication (latent, pre-existing)**: two independent copies
  today — `landing/.well-known/agent.json` (static) and
  `web/src/app/.well-known/agent.json` (route). They already drift
  independently inside the mono; the split does not worsen this, it just makes
  the drift cross-repo. Flag for a future "single source + generate" task; not
  a blocker for 5.3.

### 4) CI/deploy — per-repo workflows
Replace the one monolithic `deploy.yml` with four component workflows, each
deploying **only its own subdir** to the **unchanged** server paths (server
layout stays `/opt/tetapi/{api,web,mcp}` + `/var/www/teta-pi/`), so no
server-side moves are needed:

- **`teta-pi/api` → `deploy.yml`**: on push `main` → rsync `.` → `/opt/tetapi/api`
  (carry over the existing excludes: `__pycache__`, `.env`, `certs/*.key.pem`),
  sync public certs, `pip install` runtime deps, `alembic upgrade head`,
  `systemctl restart tetapi-api` + health check.
- **`teta-pi/web` → `deploy.yml`**: build Next standalone
  (`NEXT_PUBLIC_API_URL=https://api.tetapi.dev`), rsync standalone/static/server
  → `/opt/tetapi/web`, run the **standalone chunk patch + `app-paths-manifest.json`
  patch** (moves verbatim from today's remote script — this stays a web-repo
  responsibility, and the ⚠ "add new pages to the manifest" rule moves to
  `teta-pi/web`), `systemctl restart tetapi-web` + health check.
- **`teta-pi/mcp` → `deploy.yml`**: `npx tsc`, rsync `dist/` + `package.json` →
  `/opt/tetapi/mcp`, `npm install --omit=dev`, `systemctl restart tetapi-mcp` +
  health check.
- **`teta-pi/landing` → `deploy.yml`**: rsync `.` → `/var/www/teta-pi/`, no
  service restart.
- **`unban-ip.yml`** moves to **`teta-pi/infra`** (its ops home).

Per-repo setup that must be re-applied (was global on the mono):
- **`DEPLOY_SSH_KEY`** — the same key CI already uses. Rather than pasting it
  into 5 repos, add it once as an **org-level secret** in `teta-pi` scoped to
  the selected repos (api/web/mcp/landing/infra). One place to rotate; §5.
- **Branch protection (7.1)** — re-apply per repo: PRs only, no
  force-push/delete, `enforce_admins`. It does not carry over from the mono.
- **`ssh-keyscan` known_hosts** step stays in each workflow (unchanged).

**Cross-repo deploy ordering (new failure mode).** The mono guaranteed
migrate-then-restart-all in one pipeline. Split into 4 independent pushes, a
`web` change that depends on a new `api` field can deploy *before* the `api`
push. Mitigation is the project's existing discipline, not new machinery: API
changes are backward-compatible by convention (see the 2.2 auth design's
"strict superset" stance), and breaking changes deploy **api first, web/mcp
after**. Document this in `teta-pi/infra` deployment notes; no orchestration
layer — that would re-couple the repos.

### 5) Secrets / keys distribution
- **`DEPLOY_SSH_KEY`** (the one CI secret): as **one org-level GitHub secret**
  in `teta-pi`, granted to the five repos. Avoids five copies and five rotation
  points. It is the same `~/.ssh/tetapi_ed25519` that is also the server's
  key-only SSH login (see `docs/deployment.md`) — rotating it is already a
  coordinated operation; org-level keeps it a *single* GitHub-side edit.
- **Server `.env`** (`/opt/tetapi/api/.env`): unchanged, never in git, read only
  by `api`. Not distributed anywhere — belongs conceptually to `teta-pi/api`,
  physically to the server. `.env.example` lives in `teta-pi/infra`.
- **`api/certs/*.key.pem`** (C2PA signing key): stays server-only; the rsync
  exclusion moves into `teta-pi/api`'s workflow. Never synced/committed.
- **Web build env** (`NEXT_PUBLIC_API_URL`): not a secret — a workflow literal
  in `teta-pi/web`. **mcp `TETA_PI_API_URL`**: a systemd env on the server, not
  a GitHub secret.
- **Agent admin key** (`/root/tetapi-agent-admin.key`): server-only, untouched
  by the split.

### 6) Cutover order + rollback → EXECUTION CHECKLIST (this becomes task 5.3)
Execution is **gated on §7** (9.1 resize). During the window, reuse the
existing **merge-freeze convention** (`docs/deployment.md` §Merge-freeze) —
announce in `docs/changelog.md`, hold mono merges.

1. **Pre-flight**: 9.1 resize done + verified (2 GB box); DO snapshot exists;
   no in-flight mono deploy (`gh run list --workflow=deploy.yml`); declare
   merge freeze.
2. Create the 5 (or 6 with wordpress-plugin) empty repos under `teta-pi`.
3. Run the §2 `filter-repo` extractions locally; push each. **Do not add the
   deploy workflows yet** — push *code only* first so no repo auto-deploys mid-
   extraction and stampedes the server.
4. Add org-level `DEPLOY_SSH_KEY` (§5); apply branch protection per repo (§4).
5. In each component repo, add its `deploy.yml` (§4) and the thin `CLAUDE.md`
   (§1); drop the root `package.json`/lockfile in web & mcp, commit per-repo
   lockfiles.
6. Populate `teta-pi/infra` (docs, deploy/nginx, compose, unban-ip, canonical
   CLAUDE.md).
7. **Freeze-and-switch**: run one final deploy from the mono; then **disable the
   mono `deploy.yml`** (rename/remove); trigger each new repo's deploy **one at
   a time** (push a trivial no-op or re-run), verifying prod after each with the
   §Post-resize-style curls (`/health`, `/.well-known/mcp`, landing 200,
   app 200) before triggering the next. Sequential, never all four at once
   (§7).
8. Verify all four subdomains green; lift merge freeze.
9. **Archive** the mono repo read-only (keep issues + history) — **do not
   delete** it (prohibited-action hygiene + it's the rollback anchor).

**Rollback.** Because server paths are unchanged, both pipelines target the same
`/opt/tetapi/*` — rollback is purely "which workflow owns deploy":
- If a new per-repo deploy misbehaves: re-enable the mono `deploy.yml`, push to
  the still-intact mono → the single pipeline redeploys everything to the same
  paths, exactly as today. The new repos are additive until step 9, so this is
  clean.
- If only one service failed to restart (not a pipeline failure):
  `systemctl restart tetapi-<svc>` and re-verify; no repo-level rollback.
- Keep the mono un-archived until a full green cycle from all four new
  pipelines is observed (defer step 9 by a few days).

### 7) Risk: doing this on a 512 MB box — execution is gated on 9.1
The split is *mostly* Git/CI-side (repo creation, history rewrite, workflow
files) — zero server load. **But every per-repo deploy still runs the same
rsync + `systemctl restart` on the droplet**, and the cutover (§6 step 7)
triggers up to four deploys in one window: a Next standalone build-sync, an
`npm install --omit=dev` for mcp, `pip install` + `alembic upgrade` for api,
each followed by a service restart. On the current **512 MB box that already
holds 379 MB in swap at idle** (`docs/deployment.md` 9.1 audit), running those
concurrently risks OOM / a restart that never comes back — the exact failure
the 9.1 runbook warns about. The mono's single sequential pipeline masks this
today; four independent pipelines remove that serialization guarantee.

Therefore **5.3 execution MUST NOT run until 9.1 (resize to `s-1vcpu-2gb`,
2 GB / 50 GB) has landed and verified.** This matches the roadmap's existing
position (5.3 🔴 "deferred: needs 9.1 server upgrade"). Even post-resize, run
the cutover deploys **sequentially** (§6 step 7), not in parallel, and inside a
declared merge freeze. This plan is the input to 5.3; it does not authorize any
server or deploy action itself.
