# Known Issues

From the full project audit on 2026-07-05. Severity: 🔴 blocker · 🟠 important ·
🟡 minor. Update the status line when you fix one.

## 7.x CI/CD + MCP production-readiness audit (2026-08-04, read-only — see docs/security.md for the security-relevant subset)

Boot 7.x (`teta-pi/infra`). Three parts: CI/CD audit across all repos, MCP
production-readiness audit (9-point), org showcase correction. This section
covers the functional/CI findings; auth/observability/rate-limit findings
that are security-relevant are also filed in `docs/security.md` §5 as
S-11..S-14 (same findings, cross-referenced, not duplicated in full here).

### 🟡 `teta-pi/api` CI: Bandit + pip-audit both red (new findings)
Neither blocks merge/deploy — no repo in the org has `required_status_checks`
set on `main` (verified across all 6 public repos), so every CI check
everywhere is advisory-only, matching 15.2's original "non-blocking to
start" design.
- **Bandit** (`bandit -r app -ll`, high-severity-only reporting): 1 High
  finding — `app/api/routes/badge.py:79`, `hashlib.md5(svg.encode()).hexdigest()`
  used to build an `ETag` cache-control header. Not a real security use of
  MD5 (collision resistance is irrelevant for a cache key) — bandit flags any
  MD5 use by default. Quick fix: `hashlib.md5(svg.encode(), usedforsecurity=False)`
  (Python ≥3.9), one line. The scan also found 6 Low findings not printed
  (the `-ll` flag only reports High+) — not inspected this session, low
  priority given the one High is itself borderline.
- **pip-audit**: 1 vuln — `ecdsa==0.19.2`, `PYSEC-2026-1325` / `CVE-2024-23342`
  (Minerva timing side-channel on P-256 ECDSA). **No fix will ever land**:
  upstream `python-ecdsa` explicitly declined to fix it (side-channel attacks
  are out of scope per their own security policy) — pip-audit will report
  this forever regardless of how current the lockfile is. `ecdsa` is not a
  direct dependency (`pyproject.toml` has no `ecdsa` line) — it's pulled in
  transitively, likely via `opentimestamps-client` or `python-jose`'s
  dependency tree, not confirmed which this session. Real exploitability is
  low: confirmed `app/core/auth.py` signs JWTs with `ALGORITHM = "HS256"`
  (symmetric HMAC), so the API's own JWT code path never calls into `ecdsa`'s
  signing/ECDH functions at all. **Not a quick win** (no upstream fix
  exists) — needs a small session to (a) find the actual pulling package via
  `pip show -f` / dependency tree, (b) decide accept-with-suppression
  (pip-audit `--ignore-vuln PYSEC-2026-1325` + a comment) vs. removing
  whatever pulls it in if it's dead weight.
Status: OPEN, both non-blocking. Next: `7 github` or `1 backend` session, small.

### 🟡 `teta-pi/web` CI: `npm audit` still red — same finding as 2026-07-28, unchanged
Re-confirmed this session, no new information: 3 vulns (2 high, 1 critical),
all rooted in pinned `next@15.0.3`. See the existing entry below
("`teta-pi/web` CI: `npm audit` job red (found 2026-07-28...)") for the full
detail — not duplicated here. `npm audit fix --force` still resolves it by
bumping to `next@15.5.22`, still needs a deliberate upgrade + regression
session, not a blind `--force`.

### ✅ `teta-pi/pi-cam` had zero CI — fixed this session (partial)
`.github/workflows` 404'd on this repo before this session — none of 15.2's
CodeQL/npm-audit rollout (api/web/mcp/landing, PRs #9/#9/#4/#6) had touched
it. **Fixed:** added `npm-audit.yml` (`teta-pi/pi-cam` PR #3, merged,
matches the web/mcp pattern exactly). **CodeQL intentionally NOT added** —
pi-cam is a **private** repo on the org's **Free** plan, and GitHub Advanced
Security (required for code-scanning uploads on private repos) isn't
available on Free; the workflow would just 403 on every run. Confirmed the
same root cause blocks branch protection on this repo too:
`gh api repos/teta-pi/pi-cam/branches/main/protection` → `403 "Upgrade to
GitHub Pro or make this repository public"`. **This makes pi-cam the only
repo in the org where `main` isn't protected at all** (no PR-only
enforcement, no force-push/delete protection) — not a policy inconsistency,
a platform-tier constraint. Fix requires an owner decision: (a) make pi-cam
public — unlocks both branch protection and CodeQL, matches all 6 other
repos, and the app has no baked-in secrets to expose (client-side RN/Expo
app, keys are per-device via `pk_live_` + Secure Enclave, not in source); or
(b) upgrade the org to GitHub Team/Enterprise for GHAS on private repos.
**First real run (post-merge) is red**: several high/moderate vulns, all in
build/CLI tooling (`brace-expansion`, `js-yaml`, `postcss`, `shell-quote`,
`node-tar`, `undici`, `uuid` — Expo/Metro toolchain transitives, not app
runtime code), most with a non-force `npm audit fix` available. Not
triaged/fixed this session (same "audit, don't fix" scope as everywhere
else in 7.x) — flagged for whoever picks up the pi-cam dependency bump.
Status: OPEN (owner decision on public/GHAS + a dependency-bump session
needed), npm-audit workflow itself done+merged.

### MCP (`teta-pi/mcp`) production-readiness audit — 9-point, read-only
Full findings, evidence, and the "minimum for production" list live in
`docs/security.md` §5 (S-11..S-14) for the security-relevant items (auth,
CORS, rate-limiting, session-map memory growth) and here for the rest:

- **Observability: zero.** Grepped `mcp/src/client.ts` + `mcp/src/index.ts`
  in full (891 lines) — no logging anywhere except 3 static `console.log`
  lines at process boot. No per-call log of which tool, which entity,
  latency, or success/fail; no request-id/correlation-id generated or
  forwarded to the API. If an agent operator reports a bad result for a
  specific call, there is currently no way to reconstruct it after the fact.
  **Single highest-leverage fix**: structured stdout logging (tool name,
  entity id, latency ms, ok/error) — captured by `journalctl -u tetapi-mcp`
  already, no new infra needed.
- **Graceful degradation: reasonable but raw.** `client.ts::apiFetch`
  (lines 82-105) has a 15s `AbortController` timeout, single-shot, no
  retry/fallback/cache. On any failure it throws `Error("API {status}:
  {body}")`; the MCP SDK's `server.tool()` wrapper catches this and returns
  `{isError:true, content:[...]}` — **confirmed live**:
  `teta_verify_entity` on a nonexistent UUID → `"API 404:
  {\"detail\":\"Business not found\"}"`. Never hangs, never crashes the
  process, but the agent always sees the raw upstream error text verbatim —
  no domain-specific fallback, no "try again" guidance. A real backend 500
  would surface FastAPI's raw error body the same way (not checked here
  whether that body ever contains a stack trace in prod — separate,
  backend-side question).
- **No retry / no circuit breaker.** One failing call costs one 15s wait,
  no retry loop (so no self-inflicted flood if `api.tetapi.dev` is down),
  but also no fast-fail — a chained `teta_search`→`teta_verify_entity`→
  `teta_get_proof` sequence during an outage burns up to 45s before the
  agent sees three raw errors. Acceptable for occasional traffic, not for
  sustained real load during an incident.
- **Guardrails: solid shape validation, zero independent integrity check.**
  Every tool's zod schema (uuid/url/length/enum/numeric bounds) is real and
  correctly wired — no injection surface found (no raw SQL/shell built from
  tool args; `client.ts` only builds `URLSearchParams`/JSON bodies). But
  `teta_get_proof` (`index.ts:196-265`) is a pure pass-through formatter —
  the MCP layer never recomputes a C2PA manifest hash or an OTS merkle proof
  itself, it fully trusts whatever `/businesses/{id}/proof` returns. That's
  architecturally fine (verification logic belongs in
  `api/app/services/{bitcoin,c2pa}.py`, not duplicated here) but is worth
  stating plainly since tool descriptions ("so your agent can set its own
  trust threshold") could be read as MCP doing independent verification —
  it doesn't; the API is the sole source of truth.
- **Testing: zero.** `mcp/package.json` has no test framework (no
  jest/vitest/mocha/tap) and no `test` script; `mcp/src/` is exactly
  `client.ts` + `index.ts`, no `__tests__`/`*.test.ts` anywhere. None of the
  7 tools have coverage, happy-path or error-path (not-found, invalid input,
  timeout — all unverified except by hand/live curl, as done in this
  audit). CI's only gate is `npx tsc` inside `deploy.yml` (typecheck, not
  tests).
- **CI/CD**: 3 workflows, all green — `codeql.yml` (JS/TS),
  `npm-audit.yml` (`--omit=dev --audit-level=high`), `deploy.yml` (push to
  main: `npm install && npx tsc` → rsync `dist/` → restart
  `tetapi-mcp`). Deploy is gated only by `tsc` succeeding (a real compile
  error blocks it); no test gate exists since there are no tests. No
  `required_status_checks` on `main`, same as every other repo — advisory
  only.
- **Docs consistency — 2 real bugs found:**
  - `docs/mcp.md` (infra, canonical) says "Version 1.3.1"; the live server
    (confirmed via a real `initialize` JSON-RPC call — `serverInfo.version`)
    and `package.json` both say **1.5.1**. The 2.7/2.8 sessions (merged
    2026-07-27/28) touched `mcp/src/index.ts` but never updated this doc.
    The 7-tool table itself is accurate (names/backends/purposes all match
    live code) — just the version line and the missing changelog of what
    2.7/2.8 shipped.
  - `mcp/README.md` (the repo's own) has two real bugs, found while cross-
    checking auth: `auth: Bearer` in the connect snippet is **false** — no
    auth is enforced anywhere in `mcp/src/index.ts` (see security.md S-11),
    and `url: https://mcp.tetapi.dev/sse` is a **wrong path** — only
    `/health`, `/.well-known/mcp`, `/mcp` are routed (`index.ts:600-632`),
    everything else 404s (confirmed the same bug existed in the **org-level**
    README, `teta-pi/.github/profile/README.md` — fixed there this session
    since Part 3 explicitly scoped org-README updates, PR merged; the mcp
    repo's own README bug is left as this documented finding, not fixed
    silently, per the audit-not-fix instruction).
- **Technical debt**: no `TODO`/`FIXME`/`XXX`/`HACK` anywhere in `mcp/src/*`
  (grepped, zero matches) — clean of debt markers, partly because so little
  operational/defensive code exists yet (see observability/testing above).
  One real structural finding: the `sessions` Map (`index.ts:571`,
  `Map<string, StreamableHTTPServerTransport>`) has no expiry beyond
  `transport.onclose` — a client that opens a session and never sends a
  clean `DELETE` (crash, network drop, an agent that just stops calling)
  leaves its transport in memory for the process lifetime. Invisible under
  today's occasional/demo traffic; an unbounded slow leak under sustained
  real agent traffic with many imperfectly-closed sessions. Not urgent, but
  exactly the class of bug that only shows up after real load.

**Minimum for production with real AI-agent clients as load, ranked:**
1. Structured logging (tool/entity/latency/ok-or-error) — smallest, highest
   leverage, unblocks postfactum debugging.
2. Resolve the auth desync — either implement real Bearer auth, or if the
   product decision is genuinely "stay open for now," remove the false
   claim from `mcp/README.md` (actively misleading integrators today).
3. Rate-limit the MCP ingress itself, not just the API behind it — MCP is a
   second anonymous entry point with no limits of its own (see security.md
   S-13).
4. A minimal test suite — one happy-path + one error-path (not-found) test
   per tool, so the next `mcp/src/*` change has a safety net (this audit
   found zero regressions, but nothing would have caught one).
5. `sessions` Map expiry/cleanup — low urgency, known unbounded-growth risk.
6. `docs/mcp.md` version bump + 2.7/2.8 changelog; `mcp/README.md` auth+path
   fix (trivial, both — org README already fixed this session).

Status: OPEN — all findings above, filed for future `2 mcp`/`15 security`
sessions. No code touched in `teta-pi/mcp` this session (audit only, per
instruction).

## 🟡 No backend endpoint for a manual per-block "Verify chain" re-check (found 2026-08-02, roadmap 3.15d)
The block detail modal spec (`docs/design/profile-grid-of-record/README.md`,
"Block detail modal") gives every block a `Verify chain` action. Grepped
`teta-pi/web`'s `verifyApi`/`blockApi` (`lib/api.ts`) — every existing verify
endpoint is entity-level (registry/email/domain start+confirm); nothing
triggers a re-check of one block's own c2pa/bitcoin attestation state on
demand. `BlockDetailModal` (`web/src/app/profile/page.tsx`) mirrors the
design prototype's own stub behavior (the button just closes the modal, same
as the mock's `closeModal` handler) and adds a caption underneath saying a
manual trigger isn't wired to a backend endpoint yet — not a fabricated call.
**Fix (if ever wanted):** a backend session would need a per-block
`POST /blocks/{id}/verify` (or similar) that re-runs the c2pa/bitcoin checks
outside the existing hourly automatic recheck.
Status: OPEN, no fix planned — documented stub, not blocking 3.15e/f.

## 🟡 No public "total entities / total blocks" count endpoint (found 2026-07-31, roadmap 3.16a)
The new minimal home page (`docs/design/search-home-results/README.md` region 3)
wants a real registry-scale line: `signed evidence only · N entities · N blocks`.
Grepped `teta-pi/web`'s API client and `teta-pi/infra`'s `docs/api.md` — no public
endpoint returns these totals; only `GET /claim/stats` (waitlist-specific) and
`require_admin`-gated `/admin/stats`/`/admin/product-metrics` exist. `page.tsx`
(`useEvidenceCounts`) renders "—"/"—" rather than fabricate numbers — same choice
as 3.15a's "agent lookups / 30d" gap.
**Fix:** needs a backend session — a lightweight public `GET /stats` (or similar)
exposing `entities_count`/`blocks_count`, likely a cheap aggregate query or a
cached counter, not `require_admin`.
Status: OPEN (backend work not started).

## 🟡 Block data model has no "audio" media type or per-block registry mark (found 2026-07-31, roadmap 3.15b)
The Grid of Record square ledger spec (`docs/design/profile-grid-of-record/README.md`
region 6) wants filter chips `ALL·video·photo·text·audio` and per-block seals that
can include `registry` (max 3 marks = "full chain"). The real data model doesn't
support either: `MediaItem.type` (`teta-pi/web` `src/lib/types.ts`) is only
`video`\|`photo`\|`file` — no audio — and registry verification is entity-level
only, never per-block. `StatementLedger`/`StatementTile` (`web/src/app/profile/page.tsx`)
adapted rather than faked this: filter chips are `ALL·video·photo·text·file`, and
"full chain" now means 2 marks (c2pa+btc), not 3. Not a bug — a product/data-model
gap. **Fix (if ever wanted):** backend would need an `audio` `MediaItem.type` (or a
generic upload-classification pass) and a way to associate a specific registry
check with an individual block, not just the entity.
Status: OPEN, no fix planned — documented adaptation, not blocking 3.15c-f.

## 🟡 No per-entity "agent lookups" analytics (found 2026-07-29, roadmap 3.15a)
The Grid of Record facts strip (`docs/design/profile-grid-of-record/README.md`
region 4) wants a real "agent lookups / 30d" stat per entity. Grepped
`teta-pi/web`'s API client and `teta-pi/infra`'s `docs/api.md`/`docs/database.md`
— no such field or endpoint exists anywhere; only admin-level aggregates
(`/admin/product-metrics`) exist, and those are `require_admin`-gated, not
usable from a regular owner's `/profile`. `FactsStrip` (`web/src/app/profile/page.tsx`)
renders "—" for this stat rather than fabricate a number.
**Fix:** needs a backend session — track per-entity MCP/API read-access counts
(likely `verification_events`-adjacent, or a new lightweight counter table) and
expose it on `GET /businesses/{id}` or a dedicated endpoint.
Status: OPEN (backend work not started).

## 2.8 fix — TWIRA path now enforces `verified_only` (2026-07-28)

**Repo:** `teta-pi/api` PR #15 (merged, deployed).

**Fixed:** `app/twira/resolver.py::twira_resolve` never filtered candidates by
`verification_level` — `verified_only` had zero effect whenever the
TWIRA-ranked path ran (almost always since 5.1 made embeddings live), and only
took effect on the keyword-fallback path (`IntentResolver.resolve`). Added a
`verified_only: bool = True` parameter to `twira_resolve`, threaded from
`payload.verified_only` in `app/api/routes/intent.py::resolve_intent`, and
filters `Business.verification_level != "none"` when set.

**Semantics decision:** "verified" = any level above `"none"`, matching
`IntentResolver.resolve`'s existing filter (`LEVEL_WEIGHTS` in
`intent_graph/resolver.py` treats `registry`/`partial`/`full`/`live` all as
non-zero) — not a `registry`+ threshold. This keeps `teta_search` and
`teta_resolve_intent` consistent, per the 2.7/2.8 requirement. (Note: audit
finding 🟠 5 below, about `teta_search`'s `level` mapping in `mcp/index.ts`,
is a separate, still-open bug in a different repo/layer — not touched here.)

Verified live: `POST /api/v1/resolve-intent` with `"artificial intelligence
consulting services"` + `verified_only:true` now returns an empty result set
(HELLFIRE Solutions, `verification_level: "none"`, no longer appears);
`verified_only:false` on the same query still returns it, unchanged from
before the fix.

## 🟡 `teta-pi/web` CI: `npm audit` job red (found 2026-07-28, while in the repo for 3.5)

Not a runtime bug — deploy still succeeds (separate job), just a CI signal
nobody's acted on. `Dependency audit (npm audit)` reports 3 vulnerabilities (2
high, 1 critical) rooted in the pinned `next` version: unbounded Server Action
payload in Edge runtime, SSRF via rewrites, unauthenticated Server Function
endpoint disclosure, plus transitive `postcss`/`sharp` CVEs. `npm audit fix
--force` resolves it but bumps `next` to `15.5.22`, outside the current stated
range — needs a deliberate upgrade + regression pass, not a blind `--force` in
an unrelated session. Not fixed here (out of scope for 3.5); flagging for
whoever owns dependency upgrades.

## 2.7 fix — MCP `teta_resolve_intent` `verified_only` (2026-07-27), 🟡 2.8 caveat now fixed (see above)

**Repo:** `teta-pi/mcp` PR #5 (merged, deployed, v1.5.1).

**Fixed:** `teta_resolve_intent`'s zod schema never declared `verified_only`
at all (not a `true`/`false` branch bug — the parameter didn't exist), so any
value a caller passed was silently stripped by MCP's schema validation and
the REST call always used the API's default (`true`). Now exposes
`verified_only` (default `true`, same semantics as `teta_search`, see the
now-superseded 🟡 note below) and threads it into the `resolveIntent()` REST
call. Verified live via a real MCP client (raw JSON-RPC/curl session against
`mcp.tetapi.dev`, not just typecheck): `teta_resolve_intent(query:
"artificial intelligence consulting services", verified_only: false)` returns
HELLFIRE Solutions (TWIRA `I=0.3153`, `verification_level: "none"`), matching
a direct `POST /resolve-intent` call with the same payload.

**🟡 New, found while verifying (not fixed here) — filed as roadmap 2.8:**
`app/twira/resolver.py::twira_resolve` (`teta-pi/api`) never filters
candidates by verification level — `verified_only` has zero effect whenever
the TWIRA-ranked path runs (i.e. almost always, since 5.1 made embeddings
live). It only takes effect on the keyword-fallback path
(`IntentResolver.resolve` in `intent_graph/`). So `verified_only:true` today
still surfaces unverified (`none`) entities through `teta_resolve_intent`
whenever TWIRA has a semantic match — the flag is now correctly *plumbed*
end to end but not *enforced* for the common case. Product/API call for a
future `2 mcp`/api session.

## 1.20 backend scoping session (2026-07-24) — traced QA #7/#16/#20, fixed 3 of 4 root causes

**Repo:** `teta-pi/api` PR #13 (merged, deployed). Read-only trace into `teta-pi/web`
for (a) — no React changes made.

**Fixed:**
- **(b)/1.9** Bitcoin timestamping was wired to a no-op stub, plus a double-hash
  bug in the confirm-check (`sha256("")` instead of the real digest) — both
  fixed. See known-issues entry "🟠 9" below for the full writeup, including
  the **still-open** part: no celery worker/beat process runs on prod at all
  (confirmed via `docker ps`/`systemctl` right after this deploy), so the fix
  is necessary-but-not-sufficient until a worker ships (devops, likely 5.x).
- **(4)/caveat (i) from 6.2** `MediaOut` schema was missing `original_hash`
  entirely, and `public_profile_by_slug`/`agent_preview` (`businesses.py`)
  hand-built media dicts that omitted the file URL and hash outright. Verified
  via prod psql that the underlying DB rows were always correct
  (`storage_url`/`original_hash` populated) — this was a pure serialization
  gap on every public read path, not a data problem. Fixed: both now emit
  `media_url`/`content_hash` (public shape) or `original_hash` (authenticated
  `BlockOut`/`MediaOut` shape). Verified live post-deploy on
  `hellfire-solutions`'s public profile.
- **(c)** New public `GET /api/v1/blocks/{block_id}` permalink, independent of
  parent entity, respects `is_public`/ownership (404s a private block to
  non-owners, same information-leak posture as the rest of the API). Verified
  live.

**(a) — traced, NOT fixed here; scoped precisely for 1.20-web:**
The backend chain already works correctly end-to-end: `BlockCard.handleFileUpload`
(`teta-pi/web` `src/app/profile/page.tsx:1310-1336`) calls
`mediaApi.upload(block.id, file, ...)` with the real block id, and the backend
writes the `Media` row with the correct `block_id`/`storage_url`/`original_hash`
(confirmed via prod psql — e.g. `media_id ac5f455a-...` from this session's own
test upload landed correctly). The break is entirely client-side:
  - `ProfileBlock`/`BlockMedia` (`src/stores/useProfileStore.ts:9-18`) only
    stores `{source, phase}` — no id, url, or hash field exists on the type at
    all, so there is nowhere to put the server's response even if it were read.
  - `handleFileUpload` calls `mediaApi.upload(...)` but discards its return
    value entirely, then fakes "done" via a bare `setTimeout` (`page.tsx:1330-1333`).
  - `mapServerBlock` (`page.tsx:42-52`), used when loading a business's
    existing blocks, reads only `b.media[0].c2pa_verified` to guess a `source`
    — the real media id/url/hash from the server response is thrown away here
    too.
  - `MediaDisplay` (`page.tsx:1461-1477`) never renders the actual file: it
    draws a static striped placeholder `<div>` and a **hardcoded fake hash
    string** (`"#c2pa:verified · btc:ts:confirmed"` / `"#btc:ts:confirmed"`),
    regardless of what really happened.

  **Fix for 1.20-web:** extend `BlockMedia` to carry `{id, media_url,
  content_hash, c2pa_verified, bitcoin_confirmed}` (or just embed the server's
  `MediaItem` directly), populate it from `mediaApi.upload`'s response and from
  `mapServerBlock`, and make `MediaDisplay` render the real `media_url` (proxy
  through `/media/local/...` same-origin) and the real hash instead of the
  fake string.

**(a) fixed 2026-07-27, session 1.20-web (`teta-pi/web` PR #17, merged+deployed).**
`BlockMedia` now carries `{id, storage_url, original_hash, c2pa_verified,
bitcoin_confirmed}`. One wrinkle found while wiring it up: `mediaApi.upload`'s
own response doesn't actually carry `storage_url`/`original_hash` — the route
computes them but `MediaUploadResponse` (the `response_model`) only declares
`media_id`/`c2pa_verified`/`c2pa_signer`/`bitcoin_status`, so FastAPI strips
the rest before it reaches the client. `handleFileUpload` now follows the
upload with `blockApi.get(block.id)` (the new `/blocks/{id}` permalink) and
matches the freshly uploaded item by `media_id` to read back the real
`MediaOut`. `mapServerBlock` fills the same fields on initial load.
`MediaDisplay` renders the real file via `mediaUrl()` (same-origin
`/media/local/...` proxy, file-link fallback for non-images) and a real
truncated hash + verification state, replacing the two hardcoded fake hash
strings. Also added the public block-permalink page,
`/e/[slug]/blocks/[blockId]`, and found `MediaItem` (`web/src/lib/types.ts`)
was still missing `original_hash` even though the API's public/authenticated
payloads have carried it since the earlier fix above — added.
Verified: full upload→refetch chain replicated via curl against a disposable
QA test block (`media_id` from `/media/upload` == `media.id` from the
follow-up `GET /blocks/{id}`); new permalink page checked in-browser against
`hellfire-solutions`'s live 3-media block (real image + hashes render, 404
case handled) both locally and on prod post-deploy. **Not verified**: a full
interactive upload through the signed-in `/profile` editor UI — the harness's
safety classifier blocks injecting a live API key into a browser session, and
the account holding real edit rights wasn't available; covered instead by the
curl-replicated chain above plus a clean `npm run build`.
**New deploy-pipeline bug caught immediately after this PR's own deploy**: the
new `/e/[slug]/blocks/[blockId]` route 404'd live even though the build was
clean — `deploy.yml` hand-writes `.next/server/app-paths-manifest.json` on
the server (same root cause as the 3.12 icon-routes bug) instead of syncing
the manifest `next build` actually produces, so it silently drops any route
not in its hardcoded list. Fixed in a same-day follow-up, PR #18 — added the
missing entry, redeployed, confirmed 200 live. **This is now the second time
this exact mechanism has caused a silent prod 404 after a clean deploy**
(3.12 icon routes, now this) — worth fixing at the root (sync the real
manifest instead of hand-maintaining a copy) rather than patching entry by
entry each time a new route ships; flagged as a roadmap follow-up.
Status: CLOSED.

## Found + fixed 2026-07-21 (3.12) — `overflow:hidden` page shells become invisible scroll containers

**🟡 found while manually verifying the 3.12 app-chrome fix in-browser, not from a QA
report.** Three page wrappers (`web/src/app/page.tsx` home, `profile/page.tsx`,
and claim's `PageShell`) use `minHeight:"100vh"` + `overflow:"hidden"` purely
to clip two decorative blurred circles that extend past their own bounds.
`overflow:hidden` still makes an element scrollable *by script or focus*, it
just hides the scrollbar — so once actual content briefly exceeds 100vh (e.g.
the claim wizard's Step-0 sub-kind picker expanding the page past the
viewport height), a focus/layout-shift event scrolled that wrapper ~180px
**internally**, independent of `window.scrollY` (which stayed 0 — this is
what made it confusing to diagnose: `getBoundingClientRect()` on the rail
showed a negative Y with no scroll to explain it, and `element.scrollTop` on
the wrapper itself was the actual culprit). The offset then persisted across
the wizard's client-side step transitions, permanently hiding the fixed
banner/header's neighboring content above the fold with no visible
scrollbar to reveal why. Fixed: `overflow:"hidden"` → `overflow:"clip"` on
those three wrappers (clips visually, never becomes a scroll container);
also added `window.scrollTo(0, 0)` on claim step change as a defensive habit
for step wizards in general. **Watch for**: any other `overflow:hidden` +
`minHeight:100vh` combo added later for the same decorative-clipping reason
should default to `overflow:"clip"` instead.

## Infra incident — 2026-07-20, deploy broken by a droplet user-account reset

**🔴 found + fixed same session, manager-executed, no dev session needed.**
While merging/deploying 3.14's web PR #13, the deploy failed with `Permission
denied (publickey)` on the rsync-as-root step. Root cause: `bob` (UID 1000)
and `hellfire` (UID 1001) were both created at the **exact same second**
(2026-07-19 17:39:01, per `auth.log`) — evidence the droplet's user accounts
were reset/reprovisioned (DigitalOcean rebuild or similar), while `/opt/tetapi/*`
data on the persistent disk survived from before the reset. Two side effects:
(1) `/opt/tetapi/api` and `/opt/tetapi/web` appeared owned by the newly-created
`hellfire` user — not because HELLFIRE's processes touched them, but because
the pre-reset owner UID (1001) got reassigned to the new `hellfire` account by
coincidence; (2) a `00-hellfire-hardening.conf` sshd drop-in set `PermitRootLogin
no`, overriding the base `sshd_config`'s `PermitRootLogin yes` — likely
provisioning-script debris from the same event, not a deliberate HELLFIRE
security decision. Fixed: `chown -R root:root /opt/tetapi/api /opt/tetapi/web`
+ removed `00-hellfire-hardening.conf` + `sshd` reload (not restart, to avoid
dropping live sessions). Confirmed HELLFIRE's own services (`btc-robot`,
`btc-funding`, `btc-telegram`) unaffected throughout. Re-ran the failed deploy
— green, prod verified (`/profile`, `/`, `/search` all 200). **Watch for**: if
the droplet gets reset again, this exact failure mode (root SSH denied,
`/opt/tetapi/*` ownership drifting to whatever UID 1001 becomes) will recur —
worth a periodic check rather than assuming it's permanent.

## Owner QA Bug Report — Session 2, 2026-07-19 (10 items, #24–#33, decomposed same day)

Continues the numbering from the session-1 report below. 2 Critical / 2 High /
5 Medium / 1 Low; 10 APP, 0 LANDING, 1 CAMERA.

| QA# | Sev | Item | Where it went |
|---|---|---|---|
| 24 | 🟡 | `/profile` has no fixed iOS-style header | **3.12 ✅ fixed 2026-07-21** — `/profile` renders `<AppHeader/>` directly (not only inherited from a shared shell), same translucent fixed bar as the rest of the app |
| 25 | 🔴 | fake "Verified in registry" + garbage text/wrong registry number appear on FIRST business creation, no user action | **3.14 ✅ fixed 2026-07-20, web PR #13** — root cause was `useRegistryCheck` firing a live external-registry name-search on every keystroke and treating a name match as verification; removed the hook, `registryStatus` now loads from DB (`business.registry_status`/`registry_data`) instead |
| 26 | 🟡 | company description has no visible Edit button | **3.13 ✅ fixed 2026-07-24, web PR #16** — name+description now default read-only with an explicit Edit button (`fieldsEditing` state) |
| 27 | 🟡 | top button defaults to "Save", should default to "Edit" | **3.13 ✅ fixed 2026-07-24, web PR #16** — same toggle; button reads "Edit" until entered, "Save" only while editing |
| 28 | 🟠 | verifiers take up too much space — need a compact icon menu | **3.13 ✅ fixed 2026-07-24, web PR #16** — `VerificationSection`+`PublishSection` merged into `VerifyMenu`, an icon-row accordion (one `MethodCard` panel open at a time) |
| 29 | 🟠 | blocks (content) should be the primary object on the page, not verifiers | **3.13 ✅ fixed 2026-07-24, web PR #16** — blocks render right after name/description, `VerifyMenu` moved below |
| 30 | 🟡 | "Connect Camera" should live next to blocks, not in the general verify menu | **3.13 ✅ fixed 2026-07-24, web PR #16** — `PiCamButton` (slimmed from `PiCamSection`) sits in the "Your blocks" header row (+ ties to **14.5**) |
| 31 | 🟢 | Publish & Privacy should fold into the compact icon menu too | **3.13 ✅ fixed 2026-07-24, web PR #16** — "Publish" is the sixth icon in `VerifyMenu` |
| 32 | 🔴 | ~~seed/test entities pollute real search~~ → **NOT real data**, manager confirmed via direct psql: 0 rows in `businesses` for any of those names — frontend fabricates fake entity cards | **3.14 ✅ fixed 2026-07-20, web PR #13** — home `page.tsx` fell back to hardcoded `SEED_RESULTS` on any empty/failed API search and rendered them as real results; now returns `[]` on empty/failed search, seed pool shown only in the pre-search hero |
| 33 | 🔴 | Pi CAM needs a new build + camera sync reachable from BOTH onboarding AND the block-creation step | **14.5** — blocked on owner confirming 14.4's dev-client boots on a real device |

## Owner QA Bug Report — 2026-07-17 (23 items, decomposed 2026-07-18)

Full report: owner's `TETAPI_QA_Bug_Report_2026-07-17.docx` (5 Critical / 5
High / 8 Medium / 5 Low; 18 APP, 6 LANDING, 1 CAMERA). **QA ran BEFORE the
2026-07-17 evening fixes** (1.18 blocks/PATCH 500s, 3.6 auth stores), so some
items are already addressed. Mapping to sessions:

| QA# | Sev | Item | Where it went |
|---|---|---|---|
| 1 | 🔴 | expired session still shows editable profile | **3.9** |
| 2 | 🟠 | Make private → "invalid token" | **3.9** (stale-token family; PATCH-500 part already fixed in 1.18) |
| 3 | 🟠 | persona sees business verifier set | **3.10** |
| 4 | 🟠 | Business Email "Send Code" dead | **3.9** re-test (Resend was also broken during QA — key rotation + sandbox; may already work) |
| 5 | 🟡 | Domain Ownership untested | folded into **6.2 re-run** checklist |
| 6 | 🟡 | "Legal Entity" link unclear/inert | **3.10** |
| 7 | 🔴 | blocks: files don't attach, timestamps are UI-only | **1.20 ✅ backend fixed 2026-07-24 (api PR #13, with 1.9), web part OPEN** — backend was already correct end-to-end (block_id, hash, storage_url all write correctly; verified via prod psql + live upload); the actual break is `teta-pi/web`'s `ProfileBlock`/`BlockMedia` client state, which never persists the server's media_id/url/hash — see full writeup below. Timestamps: bitcoin wiring now real (was a no-op stub), see known-issues #9 |
| 8 | 🟡 | Under-construction banner overlaps UI | **3.12 ✅ fixed 2026-07-21 (app)** + **10.6** (landing) — banner is `position:fixed` with height in CSS var `--banner-h`, wraps to 2 lines on mobile instead of clipping; every page offsets below it via that var |
| 9 | 🟢 | landing menu not sticky | **10.6** |
| 10 | 🟡 | app has no real header/menu bar | **3.12 ✅ fixed 2026-07-21** — new shared `AppHeader` (Wordmark + AccountMenu, translucent/blurred bar) on `/`, `/search`, `/profile`, `/settings`, `/e/[slug]`, replacing each page's separately-fixed logo + menu |
| 11 | 🟠 | onboarding Camera step: dead QR/pairing stub | **3.12 ✅ fixed 2026-07-21** — step deleted outright (not hidden-in-place): wizard is now Identify → Verify → Publish (3 steps); real device-link wiring is 14.5's job once 14.4's dev-client is confirmed |
| 12 | 🟡 | Share page shows internal link | **3.12 investigated 2026-07-21 — could not reproduce, already correct since `aef2e4f` (2026-07-11)**: `SharePageButton` has always built `https://app.tetapi.dev/e/{slug}`; live slugs confirmed human-readable via psql (`hellfire-solutions`, `shosho`…), not UUIDs. No other share surface found with an internal-link bug — likely a stale observation from before that commit, or a surface not yet identified |
| 13 | 🟡 | Registry Match auto-verifies with no UX feedback | **3.10** |
| 14 | 🟡 | persona search card shows registry handle | **3.10** |
| 15 | 🟠 | profile needs full visual redesign | **3.13** (design-first) |
| 16 | 🟡 | no per-block permalink/view | **1.20 ✅ backend fixed 2026-07-24** — public `GET /api/v1/blocks/{block_id}` (api PR #13), respects `is_public`/ownership, 404s for private blocks to non-owners. Web route to it still needed (1.20-web) |
| 17 | 🟢 | favicon missing everywhere | **3.12 ✅ fixed 2026-07-21 (app)** + **10.6** (landing+email) — reused 10.6's `favicon.svg`/`apple-touch-icon.png` as Next's `src/app/icon.svg` + `apple-icon.png` (auto-wired) |
| 18 | 🔴 | data leakage between entities of one account | **3.11** (prime suspect: `useProfileStore` localStorage reuse; backend must be ruled out too) |
| 19 | 🔴 | Pi CAM app won't launch | **14.4** (blocks 14.2/14.3) |
| 20 | 🔴 | blocks not indexed/findable | **1.20**; partly explained: `/search` covers entities only, block embeddings blocked on OpenAI billing (5.1) |
| 21 | 🟢 | marketing numbers not clickable/sourced | **10.6** |
| 22 | 🟢 | references block lost its article links | **10.6** |
| 23 | 🟢 | Academic Evidence lacks arXiv links | **10.6** |

## 🟡 `resolve-intent` `verified_only` defaults to `true` — L0 entities invisible to default agent calls (2026-07-16)
> **UPDATE 2026-07-27 (2.7):** the API-level default described here was
> never the actual MCP-layer bug — `teta_resolve_intent` didn't expose
> `verified_only` as a tool parameter at all until 2.7, so an agent had no
> way to pass `false` through MCP regardless of this default. That's now
> fixed (see the 2.7 section at the top of this file), which also surfaced a
> new caveat: the TWIRA path ignored `verified_only` entirely, making this
> default moot for TWIRA-live queries. **UPDATE 2026-07-28 (2.8):** fixed —
> see the 2.8 section at the top of this file — the TWIRA path now enforces
> `verified_only` with the same semantics as this default.

Found while verifying the 1.17 fix on prod. `POST /resolve-intent` with only a
`query` returns empty for any L0 (`verification_level="none"`) entity even on
an exact name match, because `verified_only: bool = True` is the default in
both `app/intent_graph/schema.py:13` and `routes/intent.py:20` — the filter
`verification_level != "none"` excludes every unverified entity. With
`"verified_only": false` the same query returns the correct UUID (score
0.585). **By design, not a bug** — but it means a freshly registered entity is
unfindable via default MCP `teta_resolve_intent` calls until it verifies via at
least one method. Product call for the owner: keep the trust-first default, or
flip to `false` (include L0, let `relevance_score`/`verification_level` speak).
Status: OPEN as a product decision, not a defect. `/search` is unaffected
(`level` param defaults to `any`).

## 🔴 6.2 pre-GTM QA sweep (2026-07-16) — GATE FAILED, two new blockers, search/intent both broken on prod
> **UPDATE 2026-07-16: both blockers below are FIXED by 1.17 (api PR #4) and
> re-verified live on prod** — `/search` returns correct, query-dependent
> results on all 4 repro variants (empty→browse-all, exact→1, slug→1,
> nonsense→0); `/resolve-intent` filters by query text correctly (see the 🟡
> `verified_only` note above for why L0 matches still need
> `"verified_only": false`). Root cause: the query text never reached the SQL
> WHERE — it only re-scored whichever rows the LIMIT/OFFSET happened to fetch.
> The section is kept for the repro record.

Live E2E QA against prod for the 6.2 gate (must be green before GTM Phase 0).
**Verdict: RED.** Two new 🔴 blockers found; step 4 of 6.2's own exit criteria
(search finds the new entity) fails outright regardless of what gets created.
Steps 2/3 (add block, upload media) were **not tested** — see note below.

### 🔴 `GET /search` ignores the `query` parameter entirely — returns the same result set for every query
Confirmed live against `api.tetapi.dev`. The exact same 4 entities, in the
exact same order, with the exact same `relevance_score` values (`0.44, 0.35,
0.35, 0.35`), came back for all of the following:
- `GET /api/v1/search?query=&level=any&limit=5`
- `GET /api/v1/search?query=bakery&level=any&limit=5`
- `GET /api/v1/search?query=TETA%20QA%20Test%20Entity&level=any&limit=5` (a
  substring of an entity that actually exists, `TETA QA Test Entity 6.2`)
- `GET /api/v1/search?query=teta-qa-test-entity-62&level=any&limit=5` (the
  entity's own slug)
- `GET /api/v1/search?query=zzz-nonexistent-xyz-123&level=any&limit=5` (a
  string matching nothing)
All five requests returned the identical 4-entity array (`Test Reporter`,
`tetakta`, `TETA QA Test Entity 6.2`, `TETA QA Diagnostic Entity`) — the
endpoint appears to just return all entities in the DB, unfiltered and
unranked by query content. This upgrades the older, unconfirmed entry below
("`/search` relevance looks off for unrelated queries") from low-priority to
a confirmed blocker: search does not work at all on prod right now, for any
query. This also means the `app.tetapi.dev` search UI (same backend) cannot
find anything meaningfully either, though it wasn't separately re-verified
visually this session (Claude Browser tool was temporarily unavailable
throughout this session). **Fix:** needs a backend session — check
`/search`'s query-building logic for a dropped/short-circuited filter clause.
Status: OPEN (🔴, confirmed 2026-07-16, blocks 6.2).

### 🔴 `POST /resolve-intent` (`teta_resolve_intent`) returns empty results for every query tested, including exact name matches
Confirmed both via raw `curl POST https://api.tetapi.dev/api/v1/resolve-intent`
and via a real MCP client call (`teta_resolve_intent` over
`https://mcp.tetapi.dev/mcp`, JSON-RPC `tools/call`). All of the following
returned `{"query": "...", "results": []}` / "No entities resolved for
intent...":
- `{"query":"TETA QA Test Entity 6.2"}` — exact name of an entity that exists.
- `{"query":"Test Reporter"}` — exact name of a `registry`-level verified
  entity that exists and that `teta_search`/`teta_verify_entity` can both
  resolve fine when called directly by id.
The flagship resolve→verify agent workflow (`docs/mcp.md`'s "Roadmap for
MCP") cannot currently route a natural-language query to any entity on prod,
even a trivial exact-match one. Not yet root-caused this session (read-only
QA) — could be the same underlying query-matching bug as `/search` above, or
a separate TWIRA/embedding-path issue (recall `OPENAI_API_KEY` is unset on
the server per the existing "TWIRA semantic ranking is off" entry below, so
`/resolve-intent` was already known to fall back to keyword matching — but
keyword matching returning literally nothing for an exact-name query is a
distinct, new failure, not just "no semantic boost"). **Fix:** needs a
backend session to trace `/resolve-intent`'s keyword-fallback path.
Status: OPEN (🔴, confirmed 2026-07-16, blocks 6.2).

### ✅ `GET /businesses/{id}/preview` 500 (see entry below, found 2026-07-13) — CONFIRMED FIXED
Re-tested live 2026-07-16 against the same entity id used in the original
report (`b75914b9-b0a9-4170-a3c2-7df87ba26633`, "Test Reporter") both via raw
`curl GET https://api.tetapi.dev/api/v1/businesses/{id}/preview` (200, clean
JSON) and via a real MCP client call to `teta_verify_entity` and
`teta_get_profile` (both 200, clean tool output, no `isError`). Whatever
broke this between 2.5's testing and now is fixed; all 7 MCP tools are
reachable again. Not re-tested: `teta_verify_claim` (same endpoint, should
follow, but wasn't separately exercised this session).
Status: FIXED (confirmed 2026-07-16).

### Steps 2/3 of 6.2 (add a block; upload a file/image to it) — UNTESTED, blocked
These require an authenticated owner session (JWT via
`/auth/email-code`+`/auth/verify-code`, or password sign-in). The QA agent
sent the email-code request successfully (`POST /auth/email-code` for
`tetakta@gmail.com` → 200, "Verification code sent"), but reading the code out
of the owner's real inbox, or otherwise entering a login OTP on the owner's
behalf, is out of scope for an agent — not attempted. **Do not read this as a
pass or a fail; it is simply not verified.** A human (or a session with a
disposable/inbox-accessible test account) needs to run steps 2/3 by hand:
create a block on an owned entity, upload an image, and confirm
`media_url`/`hash` populate and (if applicable) C2PA fields populate on the
resulting block.

**What *did* pass:** step 1 (create-without-registry, 1.3's decoupling) is
confirmed still holding — pre-existing entity `TETA QA Test Entity 6.2`
(`44edb26e-bfab-4c25-bbb0-f251b0a1cf5a`, created 2026-07-14) has
`registry_status: "unverified"`, `registry_id: null`, `is_published: true`,
and `GET /businesses/by-slug/teta-qa-test-entity-62/public` confirms the
public payload requires no registry data (`registry.status: "unverified"`,
`registry_id: null`). Step 5 (`/e/[slug]` renders) is partially confirmed —
the route returns 200 and the correct shell — but this entity has no blocks
(`block_count: 0`), so the "renders a block + media" half of step 5 is
untested for the same auth reason as steps 2/3.

Status: OPEN — session verdict is **RED**, not green. This gate does not
clear until (a) the search/resolve-intent blockers above are fixed and
re-verified, and (b) steps 2/3/5(media) are run end-to-end by someone who can
complete the login.

## 🔴 6.2 follow-up (2026-07-16) — steps 2/3/4(a) now testable, all three fail

A real `pk_live_…` personal API key became available after the section
above was written, unblocking steps 2/3 (previously "untested, blocked" on
auth) and step 4(a) (previously not re-verified because the Browser tool was
down). All three now fail with new, distinct defects — the gate stays RED.

### 🔴 `POST /businesses/{id}/blocks` always 500s — step 2 cannot be completed at all
Confirmed live with a real owner API key against two different entities
(`44edb26e-bfab-4c25-bbb0-f251b0a1cf5a` and a second freshly-created one,
`4cfe5174-f767-46b3-b5fb-e1593c28924d`). Every payload variation 500s —
full `{"title","description","is_public"}`, minimal `{"title":"x"}`, and
with `order` explicit — so this isn't a payload-shape issue, the route
itself is broken for every caller. `GET` on the same
`/businesses/{id}/blocks` path works fine (200, `[]`), confirming auth and
routing are otherwise sound; only the `POST` handler is broken. This means
step 3 (upload a file to a block) is also unreachable, since
`POST /media/upload` requires an existing `block_id`. **Fix:** needs a
backend session to trace `routes/blocks.py`'s `create_block` handler —
likely an unhandled exception on every insert (ORM/schema mismatch?), not a
validation edge case.
Status: OPEN (🔴, confirmed 2026-07-16, blocks 6.2 steps 2 and 3).

### 🔴 `PATCH /businesses/{id}` 500s whenever `is_public` or `is_published` is in the payload
Isolated field-by-field on `44edb26e-bfab-4c25-bbb0-f251b0a1cf5a`:
`{"name":"..."}` alone → 200 clean; `{"is_public":false}` alone → 500;
`{"is_published":false}` alone → 500; both together → 500. This is a
different bug from the already-tracked #6 below (which is about a stale
`agent_endpoint_verified` flag surviving an endpoint change, not a crash) —
this one 500s on *any* write to either boolean, full stop. Practical impact
for this QA sweep: there is no `DELETE /businesses/{id}` endpoint, so
"unpublish via PATCH" was supposed to be the fallback cleanup path per the
6.2 task brief — that fallback is itself broken, so **the two test entities
created this session cannot be unpublished or hidden through any API call**
and remain live/public/findable on prod:
- `TETA QA Test Entity 6.2` — `44edb26e-bfab-4c25-bbb0-f251b0a1cf5a` /
  `/e/teta-qa-test-entity-62`
- `TETA QA Diagnostic Entity` — `4cfe5174-f767-46b3-b5fb-e1593c28924d` /
  `/e/teta-qa-diagnostic-entity` (created solely to confirm the blocks-500
  bug wasn't specific to one entity; pure test junk, safe to hard-delete)
Needs a manual DB cleanup (or a fix to this PATCH bug followed by a
proper unpublish) by someone with direct database access. **Fix:** needs a
backend session to trace `update_business`'s handling of the two boolean
fields — likely a truthy/falsy check treating `False` as "not provided" and
then hitting a code path that assumes the field is always set.
Status: OPEN (🔴, confirmed 2026-07-16, blocks cleanup + reopens #6 below).

### 🔴 Homepage search box (`app.tetapi.dev`) routes to a nonexistent `/search` page — step 4(a) fails for a human, not just for `GET /search`'s query bug
Confirmed live with the Claude Browser tool (unavailable in the original
6.2 run, now working): typing a query into the homepage's "Search verified
entities…" box and pressing Enter fires `GET
https://app.tetapi.dev/search?q=...`, which the app itself returns as a
**404** (`/search`, `/explore`, `/entities`, `/browse`, `/discover` were all
probed — none exist as a page route in the Next.js app). No error is shown
to the user; the input box just goes quietly blank and nothing happens. So
step 4(a) doesn't merely inherit the already-tracked `/search` API bug above
— there is no working search page in the frontend for a human to land on at
all, even once the API bug is fixed. **Fix:** needs a frontend session —
either the search box should call the API directly (client-side fetch to
`/api/v1/search`) and render results inline/in a modal, or a real
`/search` (or similarly-named) page route needs to exist in `web/src/app/`.
Status: OPEN (🔴, confirmed 2026-07-16, blocks 6.2 step 4(a) independently of
the `/search` API bug).

## System-wide bug audit — 2026-07-12 (session 6.1, read-only)
Numbered so they can become individual roadmap tasks. All verified in code
(file:line); nothing here has been fixed yet.

### 🔴 1. `GET /media/local/{file_id}/{filename}` has no path sanitization (unauthenticated)
`api/app/api/routes/media.py:200-206` builds `_UPLOAD_DIR / file_id / filename`
straight from the URL and serves it with `FileResponse` — no auth, no
`Path(...).name` containment check, unlike `_save_local` (media.py:23-35) which
does sanitize. Either segment can be `".."`, so a request can walk at least two
directories above `UPLOAD_DIR` (e.g. `file_id=".."`, `filename=".."` plus a
known filename) with zero authentication. **Fix:** resolve the path and verify
it's still inside `_UPLOAD_DIR` (`path.resolve().is_relative_to(_UPLOAD_DIR.resolve())`),
reject otherwise.
Status: **CLOSED** — fixed in api PR #3 (merged 2026-07-14, "fix(security): media
path traversal (1.6) + SSRF-prone /verify-endpoint (1.7)"). Triaged by 15.1 as
S-1 in `docs/security.md` §5.

### 🔴 2. MCP `teta_resolve_intent` returns a slug as `entity_id`, but every other tool requires a UUID
`api/app/api/routes/intent.py:65` and `api/app/intent_graph/resolver.py:98` both
set `entity_id=biz.slug` (also used to build `proof_url` at `intent.py:76`
against a UUID-only path). But `teta_verify_entity`, `teta_get_proof`,
`teta_verify_claim`, `teta_get_profile` all validate `id: z.string().uuid()`
(`mcp/src/index.ts:25,98,171,461`) and the API path params are typed
`uuid.UUID`. An agent following the documented flow — resolve intent, then
verify the top result — gets its call rejected by MCP's own zod validation
("Invalid uuid"). This breaks the flagship resolve→verify workflow end-to-end.
**Fix:** have intent resolution return the entity's real UUID (`biz.id`), keep
slug only for building URLs.
Status: OPEN.

### 🔴 3. `landing/developers.html` REST API docs describe endpoints that don't exist
`developers.html:219-235` documents base URL `https://api.tetapi.dev/v1`
(missing `/api`; real base per `docs/api.md:3` is `.../api/v1`) and lists
`GET /entities/search`, `GET /entities/{id}`, `GET /entities/{id}/proof`,
`POST /entities/{id}/verify-claim`, `POST /endpoints/verify` — none of these
routes exist. Real routes are `/search`, `/businesses/{id}`,
`/businesses/{id}/proof`, `/verify-endpoint` (`api/app/api/routes/*.py`). The
`curl` example at line 235 uses the same wrong base+paths. Every copy-pasted
example 404s. **Fix:** rewrite the section against the actual routers.
Status: **CLOSED** — fixed 2026-07-27 (10.3, landing PR). Base URL corrected
to `.../api/v1`; endpoint table + curl example rewritten against the real
`/search`, `/businesses/{id}`, `/businesses/{id}/proof` routes (verified live:
both example requests return 200). Also refreshed developers.html's own
MCP-tools grid (was missing `teta_resolve_intent`/`teta_get_profile`, same gap
as #15 below).

### 🔴 4. `landing/onboarding.html` "Apply for early access" form posts to a placeholder Formspree ID
`onboarding.html:180-181`: `<!-- TODO: replace YOUR_FORM_ID -->` /
`action="https://formspree.io/f/YOUR_FORM_ID"`. The submit handler
(`onboarding.html:255-279`) posts to this literal placeholder and every
submission fails; the JS catches the error and shows a generic "Something went
wrong" alert, so the whole page's funnel is silently dead. **Fix:** wire a real
Formspree ID (or point it at `/claim`, which is the app's actual working
onboarding endpoint).
Status: **CLOSED** — fixed 2026-07-27 (10.3, landing PR). Dropped the dead
Formspree form entirely; the page now sends people straight to
`app.tetapi.dev/claim` (verified live, 200), the app's real self-serve claim
flow. Removed the now-unused multi-field form CSS/JS along with it.

### 🟠 5. MCP `teta_search`'s `verified_only` filter is a no-op
`mcp/src/index.ts:324` passes `level: verified_only ? undefined : "any"` to
`searchBusinesses`, but `mcp/src/client.ts:103` only forwards `level` to the
API `if (params.level && params.level !== "any")` — both `undefined` and
`"any"` fail that check, so `level` is *never* sent regardless of
`verified_only`. The API defaults `level` to `"any"`
(`api/app/api/routes/search.py:34`), which includes never-verified (`"none"`)
entities. An agent calling `teta_search(verified_only: true)` — the tool's
default and stated behavior — gets unverified results mixed in. **Fix:** send
`level: verified_only ? "registry" : "any"` (or similar) instead of `undefined`.
Status: OPEN.

### 🟠 6. `PATCH /businesses/{id}` lets an owner keep `agent_endpoint_verified=true` after changing the endpoint
`api/app/schemas/business.py:14-21` (`BusinessUpdate`) includes
`agent_endpoint`, and `update_business` (`api/app/api/routes/businesses.py:232-247`)
applies any field from the payload with no side effects — it never resets
`agent_endpoint_verified`. An owner can verify one endpoint via
`POST /verify-endpoint`, then `PATCH` `agent_endpoint` to a different,
unverified URL while the "verified" flag (surfaced in search/intent/public
payloads) stays true. Same class of bug as the already-tracked
`registry_status`-survives-rename issue (queued as 1.5), different field.
**Fix:** reset `agent_endpoint_verified = False` in `update_business` whenever
`agent_endpoint` is in the payload and differs from the current value.
Status: OPEN.

### 🟠 7. `POST /verify-endpoint` is fully unauthenticated and performs a server-side GET to any caller-supplied URL
`api/app/api/routes/endpoint_verification.py:73-113` has no
`Depends(get_current_user)`/`require_admin` at all. Anyone can supply an
arbitrary `endpoint_url` and the server fetches it unconditionally
(`_verify_active`/`_verify_consistency`, lines 91-97) — a blind,
unauthenticated SSRF probe, separate from the already-documented
`/verify/domain/check` one. (The one mitigating factor: it can only flip
`agent_endpoint_verified=True` on a business, line 100-103, if the submitted
URL matches that business's *already-declared* `agent_endpoint` — it can't
redirect someone else's business to an attacker URL.) **Fix:** at minimum rate
limit / require auth for the SSRF-prone fetch even if the flip-to-verified path
stays open.
Status: **CLOSED** — fixed in api PR #3 (merged 2026-07-14, "fix(security): media
path traversal (1.6) + SSRF-prone /verify-endpoint (1.7)"). Triaged by 15.1 as
S-2 in `docs/security.md` §5. (Sibling `/verify/domain/check` mild SSRF stays
OPEN — tracked as S-9.)

### 🟠 8. `GET /businesses/{id}` and `GET /businesses` (list) write to the DB on every read
`_compute_verification_level` is called and assigned onto the ORM object in
both `get_business` (`api/app/api/routes/businesses.py:228`) and
`list_businesses` (`businesses.py:193`), and `get_db`
(`api/app/core/database.py:19-28`) unconditionally commits at the end of
*every* request including GETs. `Business.updated_at` has
`onupdate=func.now()` (`api/app/models/business.py:78-80`), so a plain,
unauthenticated `GET /businesses/{id}` mutates and writes the row. Because
`verification_level` is otherwise never recomputed proactively, and
`routes/search.py:55` / `routes/intent.py` filter on the *stored* column, an
entity that newly qualifies for a higher level won't appear in level-filtered
search until someone happens to hit one of these GET endpoints. **Fix:**
either persist `verification_level` reactively (on the events/media writes
that change it) instead of on read, or don't assign it onto the tracked ORM
instance in a read-only endpoint (compute into the response schema instead).
Status: OPEN.

### 🟠 9. Bitcoin timestamping wired to a no-op stub — proofs never actually submitted
**Fixed in code 2026-07-24 (1.20/1.9, api PR #13, merged+deployed).** Both
upload routes now call `submit_bitcoin_timestamp.delay(media_id, original_hash)`
directly (`api/app/api/routes/media.py`) instead of the old `_bitcoin_timestamp_bg`
no-op stub (removed). Also fixed a double-hash bug: `submit_hash`/`verify_proof`
(`api/app/services/bitcoin.py`) were re-hashing an already-computed digest on
submit, and `check_bitcoin_confirmations` (`bitcoin.py`) checked
`verify_proof(media.bitcoin_proof, b"")` — always `sha256("")` — instead of
`media.original_hash`. Both now pass the real digest through.

**Worker/beat deployed 2026-07-25 (session 5.4).** `tetapi-celery-worker` +
`tetapi-celery-beat` systemd units now run on prod (same venv/`.env`/
`WorkingDirectory` as `tetapi-api`, `--concurrency=1`). Verified live: a fresh
test upload's `submit_bitcoin_timestamp` task is picked up and run within
~10s (previously stuck in Redis indefinitely), and all 4 beat tasks fire on
schedule. Plan was shared with the owner and confirmed before touching prod
systemd, per the working agreement.

**New finding, surfaced only now that the code path is actually reachable:**
the task runs but the real OTS submission still fails —
`app/services/bitcoin.py`'s `submit_hash()` calls `cal.submit(ts)` (passing a
`Timestamp` object) where the installed `opentimestamps-client`'s
`RemoteCalendar.submit(self, digest, timeout=None)` expects the raw digest
bytes and *returns* a `Timestamp` to merge in. Confirmed via
`journalctl -u tetapi-celery-worker`: all 3 calendar URLs reject the call with
`message_body should be a bytes-like object..., got <class
'opentimestamps.core.timestamp.Timestamp'>`, then serialization fails with
"An empty timestamp can't be serialized" (caught by the broad `except
Exception`, so it fails silently as `{"status": "failed"}` rather than
crashing). `media.bitcoin_proof` will stay `NULL` until this is fixed —
flagged as its own follow-up task, not fixed in this devops session (wrong
repo/scope: this was `teta-pi/infra`, the fix belongs in `teta-pi/api`).

**Fixed 2026-07-26 (1.9, api PR #14, merged+deployed).** `submit_hash()` now
calls `cal.submit(content_hash)` (the raw digest) and merges the returned
`Timestamp` into the local one (`ts.merge(remote_ts)`) before serializing,
instead of passing the local `Timestamp` object into `submit()`. Verified
against the real `alice.btc.calendar.opentimestamps.org` endpoint directly
(submit+merge+serialize succeeded, 137 bytes) and live via
`journalctl -u tetapi-celery-worker`: the 20:32 UTC `ots_lifecycle` run
stamped 1 pending event with zero calendar warnings, vs. every run before it
failing with the `message_body should be a bytes-like object` /
`An empty timestamp can't be serialized` pair.

**Gotcha found during verification: the deploy pipeline doesn't restart the
celery worker.** The fix was live on disk and CI was green right after
merge, but `tetapi-celery-worker` kept failing with the *exact same* old
error for two more beat cycles (19:46 deploy → still broken at 20:02).
Cause: `tetapi-api`'s systemd unit gets restarted on deploy, but
`tetapi-celery-worker`/`tetapi-celery-beat` don't — and since Python caches
imported modules for the lifetime of the process, the long-running worker
(up since 2026-07-25, session 5.4) kept executing the old in-memory
`app.services.bitcoin` code regardless of what was on disk. Fixed by
`sudo systemctl restart tetapi-celery-worker`; confirmed clean on the next
cycle. **Any change to worker/task code needs a manual
`systemctl restart tetapi-celery-worker` (and `tetapi-celery-beat` if the
schedule itself changed) after deploy** until the pipeline restarts them
automatically — see `docs/deployment.md`.
Status: CLOSED — worker/beat deployment FIXED, OTS calendar submission bug FIXED.

### 🟠 10. `/profile` never reads the session created by `/login` or `/settings` — those flows leave the editor unauthenticated
`web/src/app/login/page.tsx:54` and `web/src/app/settings/page.tsx:216` (plus
two spots in `claim/page.tsx`) write the session only into the persisted
`useAuthStore` zustand store. `ProfilePage` (`web/src/app/profile/page.tsx`)
never imports `useAuthStore` — it only restores auth from the raw
`localStorage["auth_token"]` key (page.tsx:143-152), which is set solely by the
claim flow (`claim/page.tsx:1109`) or the in-page `SignInModal`
(`profile/page.tsx:925`). A user who signs in via the normal `/login` page and
then opens `/profile` has no token there: Save, block edit/reorder/delete, and
device "Connect" all silently no-op (`profile/page.tsx:335-350` shows a
"Saved" toast even though `businessApi.update` was never called, because the
`if (store.businessId && token)` guard is skipped and the code falls straight
to `setSavedAt`). **Fix:** have `/profile` read from `useAuthStore` (or unify
the two auth stores) instead of a separate `localStorage` key.
Status: OPEN.

### 🟠 11. `/claim`'s "Registry domain email" verification step is entirely fake
`web/src/app/claim/page.tsx:748`: the "Send code" button is `onClick={() => {}}`
— no request is ever sent. The adjacent "Verify" button
(`claim/page.tsx:769`) does `if (verifyCode.length >= 3) store.setProven(true)`
— any 3+ character string typed into the code field marks the claim's
"business ownership" proof as satisfied, with no backend call at all. This is
the step that's supposed to gate creating an account as an authorized
representative of an entity, and it's fully client-side and fakeable. **Fix:**
wire it to the real `/verify/email/*` endpoints (already implemented per
`docs/api.md`), or hide the method until it is.
Status: OPEN.

### 🟠 12. No web UI control ever calls `businessApi.publish`
`grep` across `web/src/**` finds zero call sites for `businessApi.publish`
(`web/src/lib/api.ts:353`). `SharePageButton` only renders when `published &&
slug` (`profile/page.tsx:219`), and `published` is set purely from
`biz.is_published` on load — there is no button anywhere that flips an
unpublished entity to published. Since entities are `is_published=true` by
default at creation (per the 1.3 rework), this mostly matters for anyone who
unpublished and now can't re-publish from the UI. Same pattern for
`businessApi.setPrivacy`/`setAgentEndpoint`/`agentPreview` and
`endpointApi.verify`/`intentApi.resolve` (`lib/api.ts:356-391`) — all defined,
zero callers; `web/src/components/ui/PrivacyToggle.tsx` is similarly unused
anywhere. **Fix:** either build the missing publish/privacy controls into
`/profile` or `/settings`, or remove the dead client surface.
Status: OPEN.

### 🟡 13. Business-email/domain confirm endpoints have a check-then-delete race on the Redis code
`api/app/services/verification/email_control.py:71-76` (and the equivalent in
`domain_ownership.py`) does `GET` the stored code, compares, then `DELETE`s it
as a separate awaited call — not an atomic compare-and-delete. Two concurrent
confirm requests with the same still-valid code can both pass the comparison
before either delete lands, each writing its own `verification_events` row
(`businesses.py:295-307`). Impact is a duplicate append-only event, not an auth
bypass (the code still has to be correct). **Fix:** use a Lua script or
`GETDEL` for atomic check-and-consume.
Status: OPEN.

### 🟡 14. `landing/onboarding.html` uses the wrong support-email domain
Four places (`onboarding.html:236,240,272,277`) use `hello@teta-pi.io`, while
every other page (`privacy.html`, `terms.html`, `index.html`,
`developers.html`, `registries.html`, `llms.txt:49`) consistently uses
`hello@tetapi.dev`. Misdirected contact address on an error-path CTA.
Status: **CLOSED** — fixed 2026-07-27 (10.3, landing PR). All 4 occurrences in
`onboarding.html` corrected to `hello@tetapi.dev`. **Note:** the same wrong
address also exists in `generate.html` (×2) — out of scope for 10.3's file
list, flagged separately as a follow-up task.

### 🟡 15. `landing/llms.txt` points the agent manifest at the wrong subdomain and understates the MCP tool count
`llms.txt:22` links `https://app.tetapi.dev/.well-known/agent.json`, but
`landing/nginx.conf:11-15` serves `/.well-known/` from the landing site itself
(`tetapi.dev`) and the file physically lives at
`landing/.well-known/agent.json` — the correct link is
`https://tetapi.dev/.well-known/agent.json`. Separately, `llms.txt:25-32` and
`for-agents.html` list only 4 MCP tools ("4 MCP tools, ready to use"); the
server actually exposes 7 (`mcp/src/index.ts`), missing
`teta_resolve_intent`, `teta_get_profile`, `teta_verify_claim` from the
agent-facing docs (`landing/.well-known/agent.json` itself is correct and
lists all 7). **Fix:** correct the manifest link and refresh the tool list/count.
Status: **CLOSED** — fixed 2026-07-27 (10.3, landing PR). `llms.txt` manifest
link corrected to `https://tetapi.dev/.well-known/agent.json`; tool list
expanded from 4 to all 7 (`teta_resolve_intent`, `teta_get_profile`,
`teta_verify_claim` added), matching `agent.json`. `for-agents.html`'s "4 MCP
tools" header and tool grid updated to 7 as well.

### 🟡 16. MCP `teta_get_profile` renders `undefined` for every media item
`mcp/src/index.ts:465-471` reads `m.media_type ?? "media"` and `m.url ?? m.id`,
but neither field exists on the API's actual media payload — `agent_preview`
(`api/app/api/routes/businesses.py:487-494`) only returns `type`,
`c2pa_verified`, `c2pa_signer`, `captured_at`, `bitcoin_confirmed`,
`bitcoin_block`, and `mcp/src/client.ts`'s own `AgentMedia` interface has no
`url`/`id`/`media_type` fields either. Every block with media renders a line
like `- media: undefined` in the tool output shown to the calling agent.
**Fix:** use the real field (`type`) instead.
Status: OPEN.

### 🟡 17. MCP `apiFetch` has no timeout — a hung or unreachable API hangs every tool call indefinitely
`mcp/src/client.ts:80-91`'s `fetch(url, {...})` has no `AbortController`/
timeout. If `TETA_PI_API_URL` is unreachable or slow, the calling agent gets no
error, just an indefinite hang. **Fix:** add a timeout (e.g. `AbortSignal.timeout(10_000)`)
and surface a clear error on expiry.
Status: OPEN.

## 🔴 Profile "My Page" does not persist blocks to the backend
`web/src/app/profile/page.tsx` uses `useProfileStore` (zustand) which had **no
persist middleware and made no API calls to save blocks**. Consequences (past):
- Blocks a user creates are lost on refresh and never reach the DB.
- The public page `/e/[slug]` reads blocks from the DB, so it always showed
  "No public blocks yet" even for entities that added blocks in the UI.
- Media upload (`mediaApi.upload`) hit the backend, but the block it attaches to
  only existed client-side (fake `block-N` id).
Status: FIXED (2026-07-05). The profile page now loads the entity + blocks from
the API on open (`businessApi.get` + `blockApi.list`, mapped into the store) and
persists changes via `blockApi`: **Add** creates the block up front so it has a
real UUID (needed for media upload); **edit** PATCHes title/desc debounced 600ms
(flushing the latest store state so title/desc edits don't clobber each other);
**remove** DELETEs; the top **Save** button now PATCHes name/description via
`businessApi.update`. All calls are auth-gated and fall back to local-only when
unauthenticated (offline UX preserved). Also fixed: `PATCH /blocks/reorder` was
shadowed by `/blocks/{block_id}` (matched `block_id="reorder"` → 422); reorder is
now declared first. Drag-to-reorder is now wired (2026-07-12): the block
grip handle in `/profile` (EditView) uses native HTML5 drag, live-reordering via
the store's existing `reorderBlocks`; on drop it PATCHes `/blocks/reorder` with
the server-side block ids in their new order. Only real UUIDs are sent (unsaved
`block-N` blocks have no row yet); a failed save rolls the order back to the
pre-drag snapshot. `blockApi.reorder` now has a caller.

## 🔴 `GET /businesses/{id}/preview` 500s for real entities in production
Found during 2.5 MCP live E2E testing (2026-07-13): `teta_verify_entity`,
`teta_get_profile`, and `teta_verify_claim` — 3 of the MCP server's 7 tools —
all call this endpoint and all three fail with `API 500: Internal Server
Error` against real entities on `mcp.tetapi.dev`. Reproduced directly against
`api.tetapi.dev` with `curl`, so it's a backend bug, not the MCP layer (which
surfaces the failure cleanly as `isError: true` rather than crashing).
`GET /businesses/{id}/proof` on the same entity ids returns 200 fine, so it's
specific to the `/preview` handler/schema. **Fix:** needs a backend session —
reproduce locally with a real entity id (e.g. `b75914b9-b0a9-4170-a3c2-7df87ba26633`
on prod) and get the actual traceback (prod only returns "Internal Server
Error" with no detail).
Status: OPEN (blocks 3/7 MCP tools; not fixed in 2.5 since it's outside
`mcp/src/*` scope).

## 🟡 `/search` relevance looks off for unrelated queries
Found during 2.5 MCP live E2E testing (2026-07-13): `teta_search` (backend
`/search`) returned the same two unrelated people ("Test Reporter", "tetakta")
for both `query="bakery"` and `query=""`. Might be intentional fallback
behavior for a near-empty dev dataset, or a relevance bug — not investigated
further (out of scope for 2.5, and could just be sparse seed data in prod).
**Fix:** check with more entities in the DB / a non-trivial query before
concluding it's a real bug.
Status: OPEN (unconfirmed, low priority).

## 🟠 `/auth/register` is public, unauthenticated, and unused
`routes/auth.py::register` creates a user with no email verification. The frontend
no longer calls it (onboarding uses email-code). It's dead code + attack surface
(lets anyone create accounts / squat emails). **Fix:** remove it, or gate it behind
an admin/API-key and require verification. Confirm no server-side caller first.
Status: FIXED (2026-07-06). Removed the endpoint entirely — confirmed no caller
(frontend only had an unused `authApi.register` helper; no server-side or test
caller). Deleted the route, the now-dead `UserCreate`/`UserOut` schemas, the
`authApi.register` helper, and the orphaned `User` type import in `web/src/lib/api.ts`.
Account creation now happens only via verified paths (`/auth/verify-code`,
`/auth/magic-link`).

## 🟠 Frontend `registry_status`/`verification_level` types are now stale
`web/src/lib/types.ts` still types `registry_status` as `"pending" | "verified"
| "failed" | "multiple_matches"` and `VerificationLevel` without `"email"` /
`"domain"`. Backend (1.3, verification rework) now returns `registry_status:
"unverified"` by default and `verification_level: "email" | "domain"` when
those new methods succeed — values the current frontend types/labels
(`LEVEL_ACCENT`/`LEVEL_LABEL`/`LEVEL_HASH` in `page.tsx`/`seedData.ts`) don't
know about yet. Also new: `AgentBusinessProfile`/`BusinessOut` schemas were
deliberately **not** extended with `legal_entity_id` (out of 1.3's scoped
files); only the public-by-slug payload discloses `legal_entity` today.
**Fix (3.4):** add the new enum values + a "coming soon" style for them, wire
up the `/verify/*` + `/legal-entity` endpoints, and add `legal_entity_id` to
`BusinessOut`/`AgentBusinessProfile` if the owner dashboard needs it.
Status: FIXED (2026-07-13). `web/src/lib/types.ts`: `VerificationLevel` now has
`"email"`/`"domain"` (with `LEVEL_ACCENT`/`LEVEL_LABEL`/`LEVEL_HASH` entries, so
the search cards in `page.tsx`/`seedData.ts` still compile); `registry_status`
now includes `"unverified"` and `"not_found"`. `web/src/lib/api.ts` (append-only)
gained `verifyApi` (registry/email/domain + link/unlink legal-entity) and
`publicProfileApi.bySlug`. The `/profile` owner dashboard has a Verification
methods chooser (registry/email/domain active, Document Upload disabled "Coming
soon" with zero network calls) + brand↔legal link UI; `/e/[slug]` publicly
discloses `legal_entity`. `BusinessOut` was **not** extended with
`legal_entity_id` (still out of scope / a backend change) — the dashboard reads
the current link from the public by-slug payload instead, and `Business.legal_entity_id`
is typed optional to reflect that it isn't returned by `GET /businesses/{id}`.

## 🟠 Renaming a registry-verified entity keeps `registry_status="verified"`
Found in manager review of PR #15 (1.3). Before the rework, renaming a business
re-triggered registry verification; now `update_business` applies the new name
and the old `registry_status` survives — so an owner can registry-verify a real
legal name, rename the entity to anything, and keep the verified badge. Fix
(small backend task 1.5): on a name change, reset `registry_status` to
`"unverified"` (history stays in `verification_events`; the owner can re-run
`POST /{id}/verify/registry` for the new name). Related, lower-severity notes
for 1.4's weight design: (a) email-control accepts ANY non-free-mailbox
address — nothing ties the verified mailbox domain to the entity, and only a
hash of it is recorded, so weight it accordingly; (b) `/verify/domain/check`
issues a blind GET to `https://<user-domain>/.well-known/tetapi-verify.txt` —
boolean-only result, but still a request to an arbitrary host (mild SSRF
surface; consider blocking private-range hosts later).
Status: OPEN (queued as 1.5).

## 🟠 In-memory state assumes a single uvicorn worker
Rate limiters (claims, email-code) and the Handelsregister lock/cache live in
process memory. Correct only under `uvicorn --workers 1` (current prod). Scaling to
multiple workers or hosts silently breaks rate limiting and duplicates DE portal
sessions. **Fix before scaling:** move counters + lock to Redis.
Status: OPEN (documented constraint).

## 🟠 TWIRA semantic ranking is off in production
`OPENAI_API_KEY` is unset on the server, so `generate_embedding` returns empty and
`/resolve-intent` + the I-component fall back to keyword matching. Blocks also get
no embeddings, so pgvector search is empty. **Fix:** set `OPENAI_API_KEY`, backfill
embeddings for existing public blocks, then TWIRA I turns on automatically.
Status: **FIXED (2026-07-27, 5.1).** OpenAI billing paid, key live in server `.env`.
`twira_backfill_block_embeddings` run via the Celery worker — 6/10 public blocks
embedded (4 skipped: media-only, no title/description). Embed-on-write verified
(create → 1536-dim vector immediately; update → re-embeds). Semantic `/resolve-intent`
confirmed running through the TWIRA vector branch (query "artificial intelligence
consulting services" → HELLFIRE Solutions via its "AI solutions for everyone" block,
I=0.315), `proof_url` non-null (`app.tetapi.dev/e/{slug}`), REST + MCP. This also
closes the 1.21 keyword-fallback `proof_url: null` caveat — prod no longer defaults
to the fallback path. NOTE: block-level findability (1.20c) still needs public blocks
on a public+published business; the QA test bakery holding sourdough blocks is
unpublished, so those blocks stay out of results by design.

## 🟡 `GET /businesses/{id}/blocks` leaks private blocks
`routes/blocks.py::list_blocks` is unauthenticated and returns **all** blocks for
a business, including `is_public=false`. Anyone with a business UUID can enumerate
private blocks. The profile edit page (owner) relies on getting every block, so a
fix must add ownership/auth there (and route non-owner reads through the public
`by-slug/{slug}/public` path, which already filters). Left as-is during the block
persistence work to avoid breaking agent readers. **Fix:** require `get_current_user`
+ owner check on `list_blocks`, or split owner vs public listing.
Status: FIXED (2026-07-12). `list_blocks` now takes an optional bearer
(`_get_optional_user` in `routes/blocks.py`, `HTTPBearer(auto_error=False)` wrapping
`get_current_user` so anonymous/invalid-token callers fall through to the public
view instead of 401). The owner sees every block; non-owners and anonymous callers
get `is_public=true` blocks only. `/profile` still gets all its own blocks (owner
match), and `/e/[slug]` is untouched (it uses `by-slug/{slug}/public`). Agent
readers keep working — they just no longer see private blocks.

## 🟡 Email delivery limited to one address
Resend domain `tetapi.dev` not verified; sender `onboarding@resend.dev` only
delivers to `tetakta@gmail.com`. **Fix:** verify the domain in Resend (DKIM/SPF),
switch sender to `hello@tetapi.dev` in `api/app/services/email.py`.
Status: OPEN (needs DNS).

## 🟡 Ukraine registry has no working backend
`ukraine_edr.py` targets `usr.minjust.gov.ua`, whose API is dead; UA searches return
nothing. **Fix:** set `OPENDATABOT_API_KEY` (verifier already implemented in
`premium.py`).
Status: OPEN (needs licence key).

## Audit — things that are FINE (checked, no action)
- `ENVIRONMENT=production` set; `dev_token` not exposed by `/auth/magic-link`.
- No secrets in git history (only placeholder SECRET_KEY / minio defaults in
  `.env.example`); C2PA signing key not tracked.
- Ownership checks present on business/block update (no IDOR).
- Append-only triggers verified live (DELETE/illegal UPDATE rejected).
- Admin endpoints gated by `require_admin` and audited.
- Registry search stable (WumWam 5/5, ranking by similarity correct).

### 🔴 `/profile` leaked one entity's state onto another, same account/session
Found 2026-07-17 (QA #18). Creating a second entity under the same account —
without a full re-login — immediately showed the *previous* entity's name,
description, and blocks on the new entity's edit page, plus a false "Verified in
registry" badge. `web/src/stores/useProfileStore.ts` is a module-level zustand
singleton with no `businessId` scoping; `web/src/app/profile/page.tsx`'s
entity-load effect (~line 202) never reset it when `store.businessId` changed,
and only overwrote `companyName`/`description` `if (biz.x)` was truthy — an
empty field on the new entity silently kept the old entity's value.
`VerificationSection`/`PublishSection`/`BlockCard` (same file) compounded it with
their own `useState` (registry/email/domain verify progress, publish state) that
also had no reset trigger on entity switch. Verified server-side isolation was
clean first (two entities created via API key, fetched independently, no
cross-contamination) before concluding this was frontend-only.
Status: **FIXED 2026-07-19** (roadmap 3.11, `teta-pi/web` PR #11) — entity-load
effect now resets the store's entity-scoped fields before fetching and assigns
fetched values unconditionally; `EditView` is keyed on `businessId` so the child
components' local state resets too.
