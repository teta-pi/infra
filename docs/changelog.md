# Changelog — development log

Running record of what shipped. The **manager session** reads this to know current
state. Newest first. Every worker session appends an entry when it finishes a task,
using the `Done / Changed / Risk / Next` block (see `CLAUDE.md`).

---

## 2026-07-13 · 13.1 gtm · GTM machine design

Done: transcribed + operationalized the owner's Autonomous GTM Plan PDF
(`~/Downloads/TETAPI_Autonomous_GTM.pdf`) into `docs/gtm.md`. Mapped every
phase item to a session number + owner: Phase 0 (6 registry listings in
exact order → `2.5` preps artifacts, Bob executes; self-verification →
existing claim flow, no new code; `llms.txt` → `10.2`; tool description
rewrite → `2.5`), Phase 1 (tool-call instrumentation = roadmap `2.4`, flagged
🟠 for an owner decision between file-log vs DB-table logging shape;
`proof_url` → new `2.6`; Show HN/Discord = owner-gated, `13.2` drafts copy
only; top-500 dataset script → new `13.3`, off-server), Phase 2
(pre-verification pipeline → new `1.7`, hard-dep claim flow already
satisfied; outreach = Bob, guardrails transcribed verbatim), Phase 3 (badge
loop → new `1.10` badge SVG endpoint, pulled forward since Phase 0's
self-verification badges need it; C2PA loop → folds into direction 14 PI
Camera; cross-verification notifications → unscoped, depends on `2.4`
shipping first). Metrics scorecard mapped into the `8.x` dashboard (new
`8.4` for pre-verified/claimed/badge counts once `1.10`/`1.7` exist). Flagged
§07 (Shopify/Wix/universal snippet) as blocked on reading the companion
`TETAPI_Platform_Integration_Strategy.pdf`, not yet transcribed.
Changed: `docs/gtm.md` (new).
Risk: none — docs only. The doc introduces several new session numbers
(`1.6`, `1.7`, `2.5`, `2.6`, `8.4`, `10.2`, `13.3`) that aren't yet reflected
in `docs/roadmap.md`'s own table — the manager session should reconcile
those into the roadmap before booting them, same as any design doc.
Next: manager adds the new n.m rows to `docs/roadmap.md`; owner decides the
`2.4` logging shape (file vs DB table) before that session boots; owner
reads the Platform Integration Strategy PDF before `12.3`.

## 2026-07-13 · 3.4 frontend · verification methods chooser + brand↔legal UI
Done: new **Verification** section in the owner dashboard (`/profile` EditView).
Registry / Email / Domain are ACTIVE, each wired to its `/verify/*` endpoint:
Registry (`POST /{id}/verify/registry` then polls `businessApi.get` for
`registry_status`), Business Email Control (email → `emailStart`, code →
`emailConfirm`), Domain Ownership (domain → `domainStart` shows DNS TXT +
well-known token with copy buttons → `domainCheck`). **Document Upload** is
visible but DISABLED, labeled "Coming soon" — zero network calls. Below the
methods: brand→verified-legal-entity link UI (`POST`/`DELETE /{id}/legal-entity`),
candidates = the user's own `registry_status="verified"` entities; current link
read from the public by-slug payload since `BusinessOut` omits `legal_entity_id`.
Public disclosure of `legal_entity` added to `/e/[slug]` (name + link, "registry-
verified"), plus email/domain trust chips + accent colors. Fixed the stale
frontend types: `registry_status` now includes `"unverified"`/`"not_found"`,
`VerificationLevel` gains `"email"`/`"domain"` with `LEVEL_ACCENT`/`LABEL`/`HASH`
entries so the search cards keep compiling.
Changed: `web/src/lib/types.ts`, `web/src/lib/api.ts` (append-only: `verifyApi`,
`publicProfileApi`, `DomainVerifyInstructions`, `PublicLegalEntity`),
`web/src/app/profile/page.tsx` (`VerificationSection` + helpers),
`web/src/app/e/[slug]/page.tsx`. `next build` + `tsc --noEmit` clean; verified
render in-browser (methods, disabled Document Upload, email expand).
Risk: link state on the owner dashboard is read from the public payload, so a
just-unpublished/private entity would show no link on load (link/unlink itself
is optimistic and correct). Email-control still accepts any non-free-mailbox
address (backend note, 1.4/1.5). Domain `/check` is a blind GET to the user's
host (mild SSRF, tracked in known-issues).
Next: 1.4 TWIRA `source_weight` per method; 1.5 reset `registry_status` on
rename; landing copy pass (10.x) once methods are public.

## 2026-07-12 · 6.1 manager · system-wide bug audit (read-only)
Done: read-only sweep of `api/`, `web/`, `mcp/`, `landing/` for real defects —
auth/ownership gaps, race conditions, in-memory-state assumptions, stale
types/enums, dead endpoints, error-handling holes. 17 new findings verified
in code (file:line) and appended to `docs/known-issues.md` under "System-wide
bug audit — 2026-07-12 (session 6.1)": 4× 🔴 (unauthenticated path traversal
in `/media/local/{file_id}/{filename}`; MCP `teta_resolve_intent` returns a
slug where every other tool requires a UUID, breaking the flagship
resolve→verify flow; `developers.html`'s REST API docs describe endpoints
that don't exist; `onboarding.html`'s signup form posts to a placeholder
Formspree ID), 8× 🟠 (MCP `verified_only` search filter is a no-op;
`agent_endpoint_verified` not reset on endpoint change — same class as the
already-tracked `registry_status` bug; unauthenticated SSRF-prone
`/verify-endpoint`; GETs on `/businesses` write to the DB via
`onupdate=func.now()`, causing stale level-filtered search until someone
happens to GET; Bitcoin timestamping wired to a no-op stub so proofs are
never submitted (plus a wrong-digest bug in the confirmation check);
`/profile` never reads the session written by `/login`/`/settings`, leaving
that auth path's editor silently unauthenticated with a false "Saved"
indicator; `/claim`'s domain-email proof step is entirely client-side/fakeable;
no UI control ever calls `businessApi.publish`/`setPrivacy`/etc.), 5× 🟡
(Redis check-then-delete race on verification codes; wrong support-email
domain on one landing page; `llms.txt` links the agent manifest at the wrong
subdomain and undercounts MCP tools; `teta_get_profile` renders `undefined`
media fields; MCP `apiFetch` has no timeout).
Changed: `docs/known-issues.md` (append), this changelog entry. No source
files touched — audit only, per task scope.
Risk: none (read-only). All 17 are unfixed and open; several (🔴 #1-4) are
worth prioritizing before any other session touches media serving, the MCP
intent flow, or public-facing landing docs.
Next: turn the 🔴 items into their own numbered tasks first (media path
traversal is the most exposed — unauthenticated, live in prod); 🟠 #6/#8/#9
are backend follow-ups in the same family as the already-queued 1.5
(`registry_status` reset) task.

## 2026-07-12 · 1.4 backend · TWIRA source_weight per verification method
Done: `app/twira/trust.py:SOURCE_W` extended from the registry/self-declared
placeholder to per-method weights read from `verification_events.source` as
actually written by the 1.3 routes: `official_registry` 1.0 (unchanged),
`dns_txt`/`file` 0.75 (Domain Ownership), `business_email` 0.5 (Business
Email Control — weighted down per known-issues.md: the verified mailbox
domain isn't bound to the entity, only a hash is recorded), `document_verified`
0.85 (dormant — no upload endpoint yet, weight decided ahead of the backend
per verification-rework.md §4). Old placeholder keys (`c2pa_camera`,
`linked_account`, `self_declared`) kept for back-compat; none are currently
written by any route.
Changed: `api/app/twira/trust.py`; `docs/architecture.md` (TWIRA T-component
note); `docs/changelog.md`.
Risk: weights are a first-pass ordering call (registry > document > domain >
email), not data-driven — v1 log-based reweighting (see `twira/score.py`
comment) will supersede this.
Next: 3.4 frontend (verification methods chooser UI); 1.5 (reset
`registry_status` on rename — queued, see known-issues.md).

## 2026-07-12 · manager · 14.1 corrected from PI CAM session state
Done: queried the PI CAM session + app dir for the camera's real final state.
Pi CAM is an existing React Native/Expo app (`~/Downloads/PI CAM`, own session):
offline C2PA signing (Secure Enclave/Keystore), watermark/GPS/save-to-Photos
fixes landed 2026-06-28, TS clean; already integrated with the platform via
`modules/account` (QR link, `pk_live_`, entity) → `POST /media/device-upload`;
web `/profile` has a deployed "Connect Pi CAM" + SignInModal. Rewrote roadmap
14.1: not a new web capture UI — finish+verify the app↔platform integration
end-to-end (upload → C2PA/OTS verify → verified block → proof → MCP), fix the
QA finding (Connect no-ops with null token). Flags: PI CAM dir is NOT a git
repo (init + private repo = step 1); a server password was pasted into that
chat on 2026-06-28 — rotate it.
Changed: `docs/roadmap.md` (14.1 rewritten).
Risk: none — docs only.
Next: boot 14.1 in the PI CAM session (app side) + small platform-side task here.

## 2026-07-12 · manager · GTM plan reconciled (PDF) + camera → direction 14
Done: owner delivered the **Autonomous GTM Plan** PDF (zero-budget, 90-day,
agent-network-effect: Phase 0 self-registration on 6 MCP surfaces → Phase 1
agent discovery → Phase 2 top-500 pre-verification with guarded claim outreach
→ Phase 3 self-running loops; WP plugin = parallel site-side arm §07).
Reconciled roadmap 13.x with it — key fix: **GTM activation trigger changed
from "after 12.2 (plugin publish)" to "after 2.5 (MCP listings = Phase 0)"**;
13.1 is now "transcribe+operationalize the PDF into docs/gtm.md". Camera moved
out of frontend into its own **direction 14** (owner: standalone product) —
3.3 → 14.1, same full-product scope, plus the GTM C2PA-loop tie-in.
Changed: `docs/workflow.md` (+14, 13 rewritten), `docs/roadmap.md` (3.3 moved,
14.1 added, 13.1/13.2 rewritten).
Risk: none — docs only. Open decisions flagged for 13.1: lightweight MCP call
logging vs deferred 2.4 (droplet), badge SVG endpoint as a new small backend task.
Next: boot 14.1 + updated 13.1; 2.5 becomes the GTM critical path.

## 2026-07-12 · manager · unfreeze 3.3 camera (full product) + MCP end-goal 2.5
Done: owner set two priorities. (1) **3.3 camera** un-paused and scope upgraded
to a full product: capture → existing C2PA/OTS pipeline → verified block on the
profile/public page, proof visible via `/proof` + MCP. De-coupled from 5.2 (the
split is frozen indefinitely; camera never needed it — one-off request load
only). (2) **2.5 mcp** added — the direction's end goal: fully working, debugged
MCP in the Claude ecosystem and others: e2e testing from real clients, protocol
fixes, then owner-approved registry/directory listings. 2.2 (agent auth design)
marked next in direction 2.
Changed: `docs/roadmap.md` (3.3 unfrozen + rescoped, new 2.5, 2.2 flip).
Risk: none — docs only. Camera signing load is per-request, same as existing
block flow.
Next: boot 3.3 (worktree reset to current main) and 2.2/2.5.

## 2026-07-12 · manager · directions 12 wordpress + 13 gtm
Done: owner added two directions. **12 wordpress** — the TETA+PI WordPress
plugin (new `wordpress-plugin/` folder): free verification tier + $25 premium
pack; this is the first thing we build AND publish (wordpress.org = first
public distribution channel). **13 gtm** — autonomous go-to-market machine,
designed in 13.1 (`docs/gtm.md`), activated immediately after the plugin
publishes (12.2); runs off-server, all public posting owner-gated.
Changed: `docs/workflow.md` (directions table +12/+13),
`docs/roadmap.md` (rows 12.1, 12.2, 13.1, 13.2).
Risk: none — docs only.
Next: boot 12.1 (worktree ready); 13.1 design can run in parallel.

## 2026-07-12 · 11.1 backoffice · dashboard v2 build
Done: implemented the approved 8.1 design as a new "Dashboard" tab in `/admin`
(now the default tab) — health row (api/mcp/stats), growth sparklines +
claim→verified funnel, entity mix + verification level, MCP usage + registry
search health as labeled "not available" placeholders (not hidden), traffic
sparkline + top referrers. Added `GET /admin/health-check` (thin, admin-gated,
audited) because a browser can't reliably CORS-check `mcp.tetapi.dev/health`
from `app.tetapi.dev` — pings mcp + stats.tetapi.dev server-side instead.
Extracted `FunnelChart` so the Dashboard and Analytics tabs share the funnel
render instead of duplicating it.
Changed: `web/src/app/admin/page.tsx` (new `DashboardTab`, `FunnelChart`,
`HealthRow`, `NotAvailable`, `timeAgo`), `web/src/lib/api.ts` (append:
`adminApi.healthCheck`, `AdminHealthCheck`), `api/app/api/routes/admin.py`
(append: `GET /admin/health-check`).
Risk: `health-check` makes two outbound HTTPS calls per request (mcp +
stats.tetapi.dev), 5s timeout each — worst case ~10s if both are unreachable;
acceptable for a manually-viewed dashboard tab, would need caching if polled
by the 8.3 notifier agent. No DB/docker available in this sandbox to run the
full authenticated flow — verified via `tsc --noEmit` + `next build` only, not
a live browser session.
Next: 8.3 notifier agent (off-server) can reuse `/admin/health-check` instead
of pinging `/health` from its own process.

## 2026-07-12 · 1.3 backend · verification rework — methods + decoupled creation
Done: `POST /businesses` no longer calls the registry — any name is creatable
immediately, free, unverified (`registry_status="unverified"`,
`is_published=is_public=true` for every entity_type; L0). Registry match is
now explicit/optional (`POST /{id}/verify/registry`, was automatic at
create/rename). Two new independent methods, each writing its own append-only
`verification_events` row: Business Email Control (`/verify/email/start`
+`/confirm` — 6-digit Resend code to an address on the brand's own domain,
Redis-namespaced `biz_email_code:*`, rejects free-mailbox domains) and Domain
Ownership (`/verify/domain/start`+`/check` — DNS TXT via DNS-over-HTTPS or a
`.well-known` file token, same mechanism as the WordPress plugin; no new DNS
dependency). Brand↔legal-entity link (`POST`/`DELETE /{id}/legal-entity`,
writes `businesses.legal_entity_id`; requires owning both sides + the legal
entity already `registry_status=verified`), publicly disclosed via
`legal_entity` on `GET /businesses/by-slug/{slug}/public`. `/publish` no
longer gates on registry verification. `verification_level` is now computed
on read from `registry_status` + `verification_events` instead of stored.
Document upload: nothing shipped (by design — 3.4/future, UI-only "coming soon").
Changed: `api/app/api/routes/businesses.py`; new
`api/app/services/verification/{email_control,domain_ownership}.py`.
`api/app/api/routes/auth.py` untouched — reused via import
(`send_verification_code`) and pattern only.
Risk: `web/src/lib/types.ts`'s `registry_status`/`VerificationLevel` unions
don't know the new values yet (`unverified`, `email`, `domain`) — cosmetic
frontend gap until 3.4, see `docs/known-issues.md`. `AgentBusinessProfile`/
`BusinessOut` weren't extended with `legal_entity_id` (kept the diff inside
the scoped files) — only the public-by-slug payload discloses the link today.
Next: 1.4 (TWIRA `source_weight` per method), then 3.4 (verification-methods
chooser UI, brand↔legal link UI, public disclosure on the profile page, and
the frontend type/schema follow-ups noted above).

## 2026-07-12 · 4.1 db · verification rework migration (legal_entity_id + event_type)
Done: migration 011 adds `businesses.legal_entity_id` (nullable, self-referencing
FK — brand→verified legal entity link, e.g. "Google"→"Alphabet Inc.") with an
index; asserts the 006 append-only trigger on `verification_events` is still
attached before proceeding. `verification_events.event_type` gains
`email_verified` / `domain_verified` / `document_verified` as documented
allowed values on the `VerificationEvent` model — the column has always been a
plain `String(50)` with no DB-level enum/check constraint, so no schema change
was needed for that part, only the model comment. `document_verified` is
type-only: no backend/upload endpoint until file-upload risk is handled.
Changed: `api/alembic/versions/011_legal_entity_link.py` (new),
`api/app/models/business.py` (`legal_entity_id` column + self-relationship),
`api/app/models/verification_event.py` (comment), `docs/database.md`.
Risk: could not run `alembic upgrade head` locally (no docker/postgres in this
environment) — verified via AST/compile checks and manual review only; CI/next
session against a real DB should confirm the migration applies cleanly.
Next: 1.3 backend — decouple entity creation from registry match, add
email-control + domain-ownership verification methods, brand↔legal link
endpoint (see `docs/verification-rework.md`).

## 2026-07-12 · 8.1 analytics · dashboard v2 design
Done: design doc for the owner's super-dashboard + alerting agent — data source
inventory (what `/admin/stats`, `/admin/analytics`, `/admin/product-metrics` give
vs. the two real gaps: MCP usage and registry search health), ASCII layout mockup,
alert threshold table (severity → channel), and off-server notifier agent
architecture (no new server workers/tables — reuses existing read-only admin
endpoints + `pk_live_` auth).
Changed: `docs/analytics.md` (new "Dashboard v2 design" section, appended).
Risk: none — docs only, zero deploy.
Next: 8.2 implements the approved layout in the admin UI; 8.3 builds the notifier
agent once 2.2 (scoped agent auth) lands, since the agent should reuse that scope
mechanism rather than a bespoke one.

## 2026-07-12 · 3.2 frontend · wire drag-to-reorder + admin badge copy
Done: `/profile` block drag-to-reorder is now live. The grip handle (⠿) in
EditView uses native HTML5 drag (no new deps), live-reordering through the store's
existing `reorderBlocks`; on drop it PATCHes `/blocks/reorder` with the server-side
block ids in their new order, giving `blockApi.reorder` its first caller. Only real
UUIDs are sent (unsaved `block-N` blocks have no row yet); a failed save rolls the
order back to the pre-drag snapshot. Also fixed the admin claims table badge
`$21 LOCKED` → `FOUNDING LOCKED` (claims don't store a locked price, so any amount
misrepresents part of the cohort).
Changed: `web/src/app/profile/page.tsx` (drag handlers on grip + card, module-level
`persistBlockOrder`/snapshot); `web/src/app/admin/page.tsx` (one badge line);
docs/known-issues.md (reorder loose end → wired).
Risk: low — reorder only fires for authed owners with ≥2 server blocks; local-only
and unauthenticated flows unchanged. Not runnable locally (worktree deps absent);
typecheck clean via main-checkout tsc. Verify on prod: drag two saved blocks, reload
`/profile` and `/e/[slug]` to confirm the new order persisted.
Next: consider keyboard-accessible reordering + touch drag for mobile.
## 2026-07-12 · 1.1 backend · close private-block leak on GET blocks
Done: `GET /businesses/{id}/blocks` no longer leaks private blocks. Added an
optional-auth helper `_get_optional_user` (`HTTPBearer(auto_error=False)` wrapping
`get_current_user`, reusing its API-key + token-version logic) so anonymous and
invalid-token callers fall through instead of 401. `list_blocks` now returns every
block to the owner and only `is_public=true` blocks to everyone else.
Changed: `api/app/api/routes/blocks.py` (new helper + owner-aware filter in
`list_blocks`, +1 import); docs/known-issues.md 🟡 → FIXED.
Risk: low — additive/read-only. `/profile` still loads all its own blocks (owner
match); public page `/e/[slug]` untouched (uses `by-slug/{slug}/public`). Agent
readers keep working but no longer see private blocks. Not runnable locally (deps
absent); verify on prod after deploy: owner token → all blocks, anon → public only.
Next: 🟠 move in-memory rate limiters/HR lock to Redis before multi-worker scaling.

## 2026-07-12 · 2.1 mcp · teta_get_proof depth (roadmap #5, MCP 1.3.0)
Done: enriched `teta_get_proof` / `GET /businesses/{id}/proof` with a `proof_depth`
block so agents set their own trust threshold — `ots_status`
(pending/anchored/confirmed, strongest across events), `btc_timestamp_depth`
(deepest Bitcoin confirmation in blocks), `c2pa_chain_length`, `event_count`. All
read straight from `verification_events`; reuses `twira/provenance.current_btc_height()`
(cached mempool.space height). No new tables or workers.
Changed: `api/app/api/routes/businesses.py` (get_proof + 2 imports); `mcp/src/client.ts`
(`VerificationProof.proof_depth`); `mcp/src/index.ts` (Proof Depth section, tool
description, version); version bump 1.2.0→1.3.0 across `mcp/package.json`, MCP
`/health` + `/.well-known/mcp`, and both `.well-known/agent.json`; docs/mcp.md.
Risk: low — additive, read-only. `get_proof` now awaits `current_btc_height()`, so a
cold height cache adds one mempool.space call (≤10s, cached 10 min, shared with TWIRA);
`btc_timestamp_depth` is `null` if that fetch fails. No schema/worker changes.
Next: #6 agent-facing auth for MCP writes (scoped `pk_live_` keys).

## 2026-07-12 · frontend · 3.1 web copy sync (Strategic Foundation v2)
Done: synced `app.tetapi.dev` copy with the landing pricing update (session 2026-07-11
`landing`) — claim checkbox founding price $21→$25 (both form states in
`web/src/app/claim/page.tsx`); `layout.tsx` meta description aligned with
tetapi.dev's positioning copy. The other two audit items were already fixed by a
prior session: `<title>` already read "Digital Entities" and the About link
already pointed to `https://tetapi.dev/about.html` (checked, no change needed).
Changed: `web/src/app/claim/page.tsx`, `web/src/app/layout.tsx`.
Risk: none — static copy only, no logic touched.
Next: admin back office (`web/src/app/admin/page.tsx:612`) still hardcodes a
"$21 LOCKED" badge on the claims table — out of scope here (not "claim flow"),
flagged separately.

## 2026-07-12 · github · 7.1 branch protection on main
Done: enabled branch protection on `main` in `teta-pi/platform` via `gh api`
(`PUT /repos/teta-pi/platform/branches/main/protection`): PRs required (direct
push blocked), `required_approving_review_count: 0` (solo — PR needed, approval
not), `allow_force_pushes: false`, `allow_deletions: false`, `enforce_admins: true`
(agreed with owner — manager session now also goes through PRs, batches doc
changes). No required status checks yet (would block quick doc PRs on the deploy
workflow; can add later as a separate decision).
Changed: repo settings only, no code. Verified: direct push to `main` rejected
(`GH006: Protected branch update failed`); this changelog entry itself lands via
the new PR flow as the first real test.
Risk: none — settings-only change. Note: `enforce_admins: true` means even
manager/admin sessions must use PRs from now on; update `docs/workflow.md` boot
habits if any session still assumes direct-push-to-main is possible.
Next: 7.2 repo descriptions vs landing audit; 7.3 commit attribution audit.

## 2026-07-11 · manager · land orphaned tree work as 3 PRs + status reconcile
Done: the shared `main` working tree held 124 lines of uncommitted work from three
file-disjoint concerns, un-landed. Split into three clean PRs into `main` (all
squash-merged, auto-deployed): **PR #1** landing pricing (see entry below);
**PR #2** `web/src/app/profile/page.tsx` — the Share-page button (roadmap #9);
**PR #3** TWIRA block embeddings (`ai.py` + `routes/blocks.py` +
`workers/tasks/twira.py`) — embed on create/update (no-op without key) +
idempotent `twira_backfill_block_embeddings` task, code half of #3/#7.
⚠️ Drift caught: the 2026-07-06 "Share page button" entry below claimed #9
shipped, but `SharePageButton` was never in git until PR #2 — the changelog ran
ahead of reality. Treat the older entry as "designed", this one as "landed".
Changed: three merges to `main`; roadmap statuses reconciled with git (S4
resolve_intent ✅, `teta_get_proof` depth #5 still open; S6 ✅ deployed; S7
embedding code merged, server `.env`+backfill pending); removed merged s7 worktree.
Risk: three prod deploys, all low-risk. Embeddings dormant until `OPENAI_API_KEY`
is set on the server.
Next: run **S8 (split monorepo)** on the now-clean `main` — unblocked since S4 merged.

## 2026-07-11 · landing · pricing update to Strategic Foundation v2
Done: updated `landing/index.html` pricing to the current model — founding price
$21→$25 (hero CTA, claim checkbox, Module #1 card, final CTA strip); Module #2
$50→$52; "Package #1/#2" renamed "Module #1/#2" (+ intro copy "packages"→"modules");
deleted the discontinued $100 "Package #3" card; pricing grid `repeat(5,1fr)`→
`repeat(4,1fr)` (Free / Module #1 / Module #2 / Enterprise).
Changed: `landing/index.html` only.
Risk: low — static copy/layout; verified in preview (4-card grid, no $21/$100).
Next: app.tetapi.dev (web/) still needs the matching fixes from the audit —
$21→$25 claim checkbox, `localhost:3000` About link → `tetapi.dev/about.html`,
and `<title>`/meta "Agent Economy"→"Digital Entities". Out of scope for this
landing-only session.

## 2026-07-06 · api+web · product metrics on top of /admin/stats + /admin/analytics
Done: added `GET /admin/product-metrics` (require_admin + audit-logged,
read-only) covering what the existing snapshot/traffic endpoints don't: daily
entity growth, daily verification_events, entities by `entity_type`, and a
claim→verified funnel (claims → signed_up → created_entity → verified, joined
by email). Registry search health was requested but skipped — no request
logging exists anywhere in `registry_search.py` / `services/registry/*` to
aggregate from; the endpoint returns `available: false` with a note instead of
faking numbers. Rendered as new sections at the bottom of the existing
Analytics tab in the back office (no new tab).
Changed: `api/app/api/routes/admin.py` (new endpoint), `web/src/lib/api.ts`
(`adminApi.productMetrics`, `AdminProductMetrics` type), `web/src/app/admin/page.tsx`
(`ProductMetricsSection` inside `AnalyticsTab`). Docs: `docs/api.md`,
`docs/analytics.md`.
Risk: none to existing behaviour — additive endpoint, no schema/table changes.
`entities_by_type` and the funnel do full-table scans with no new indexes;
fine at current volume, revisit if `businesses`/`claims` grow large.
Next: build registry search request logging (append-only, entity_id-less since
these are pre-entity lookups) so `registry_search_health` can be filled in.

## 2026-07-06 · mcp · enrich teta_resolve_intent (MCP 1.2.0)
Done: `teta_resolve_intent` now returns a full T/I/P breakdown, `first_verified_at`
and `proof_url` in an agent-parseable format, and takes `entity_types` (multi-type)
+ `min_trust` filters. `min_trust` filters on `Business.t_score` in the TWIRA SQL;
`entity_types` supersedes the old single `entity_type` (kept for back-compat).
Changed: `api/app/api/routes/intent.py`, `api/app/twira/resolver.py` (add `min_trust`
param + t_score filter), `mcp/src/index.ts` (new tool schema + richer text),
`mcp/src/client.ts` (fixed stale `IntentResolution` type, `TwiraBreakdown`), both
`agent.json` (+ `teta_verify_claim` sync), MCP manifest/health/package → 1.2.0.
Risk: `min_trust` only applies on the TWIRA path (no-op on keyword fallback, which
has no t_score); TWIRA I-component still needs OPENAI_API_KEY to be set.
Next: expose `min_trust` in the keyword fallback via LEVEL_WEIGHTS, or surface a
`ranking_mode` flag so agents know whether TWIRA or keyword ranking was used.

## 2026-07-06 · web · "Share page" button on /profile
Done: `/profile` now shows a "Share page" button (roadmap #9) that copies and links
to the public page `app.tetapi.dev/e/<slug>`; visible only once the entity is
published (`is_published`).
Changed: `web/src/app/profile/page.tsx` — new `SharePageButton`; `ProfilePage` now
captures `slug` + `is_published` from the loaded entity; added `APP_ORIGIN` const.
Risk: share link host is hardcoded to production (`https://app.tetapi.dev`), so in
local dev the link points at prod, not localhost.
Next: roadmap #10 (sessions list) or wire a publish toggle into the UI.

## 2026-07-06 · security · remove public `/auth/register` (🟠 FIXED)
Done: deleted the unauthenticated `POST /auth/register` endpoint (created users
with no email verification). Confirmed no caller first — frontend only had an
unused `authApi.register` helper; no server-side or test caller. Removed the route,
the now-dead `UserCreate`/`UserOut` schemas, the `authApi.register` helper, and the
orphaned `User` type import.
Changed: `api/app/api/routes/auth.py`, `api/app/schemas/user.py`,
`web/src/lib/api.ts`; docs (`api.md`, `known-issues.md`). Risk: none — account
creation still flows through verified paths (`/auth/verify-code`, `/auth/magic-link`).
Next: 🟠 gate `GET /businesses/{id}/blocks` (leaks private blocks) or in-memory
rate-limit → Redis before scaling.

## 2026-07-05 · docs · project brain + manager model
Done: added `docs/` (overview, architecture, api, database, mcp, registries,
deployment, decisions, roadmap, known-issues, glossary, workflow, changelog) +
root `CLAUDE.md`; defined the manager/orchestrator session (`docs/manager.md`).
Changed: doc files only. Risk: none. Next: remove /auth/register (🟠).

## 2026-07-05 · backend · profile blocks persistence (🔴 FIXED)
Done: profile page loads entity + blocks from the API on open and persists
add/edit/reorder/remove via `blockApi`; Save PATCHes name/description; auth-gated
with local-only fallback. Fixed `PATCH /blocks/reorder` route shadowing.
Changed: `web/src/app/profile/page.tsx`, `useProfileStore.ts`, `lib/api.ts`,
`api/app/api/routes/blocks.py`. Risk: drag-to-reorder UI not yet wired
(`blockApi.reorder` has no caller). Next: wire reorder UI, then public page shows blocks.

## 2026-07-05 · registry · expansion + working German search
Done: FR (SIRENE), CZ (ARES), FI (PRH), US state registries (NY/CO), premium
NorthData/Opendatabot (key-gated); rewrote German verifier to drive
handelsregister.de JSF portal (validated: WumWam GmbH); no-country fan-out;
similarity ranking; serialized DE access (lock+cache+retry).
Changed: `api/app/services/registry/*`, landing registries, agent.json, llms.txt.
Risk: DE portal scrape can break if the portal changes. Next: UA needs Opendatabot key.

## 2026-07-05 · account · avatar upload + /auth/me
Done: avatar upload (≤2MB), `/auth/me`, avatar in menu + settings.
Changed: `auth.py`, `users.avatar_url` (migration 010), AccountMenu, settings.

## 2026-07-05 · frontend · public entity page /e/[slug]
Done: shareable public page + `GET /businesses/by-slug/{slug}/public` (published,
public blocks only). Risk: shows empty until profile blocks persist (see known-issues).

## 2026-07-05 · account · login + full account management
Done: `/login` (password or email code); change email; delete account (GDPR);
log out everywhere (token_version, migration 009); personal API key.

## 2026-07-04 · account · menu + settings + password sign-in
Done: avatar menu (My Page/Settings/Log out), `/settings`, set-password.

## 2026-07-04 · backoffice · A1–A5
Done: roles + `require_admin`; admin API (stats/users/claims/entities); append-only
`admin_audit_log` (migration 007); PII Fernet encryption (008); GDPR export/anonymize;
registry validation + suspicion flags. Admin UI at `/admin`.

## 2026-07-04 · auth · real email verification codes
Done: Redis-backed 6-digit codes via Resend (`/auth/email-code`, `/verify-code`);
replaced the accept-anything stub in the claim flow.

## 2026-07-03 · systemspec · S1–S4
Done: 12 EntityTypes, segment, block c2pa_manifest/ots_proof/embedding (migration 006);
Temporal Moat `verification_events` (append-only trigger); TWIRA pipeline
(`api/app/twira/`); `/resolve-intent`; MCP 1.1.0 (+teta_resolve_intent, teta_get_profile).
Risk: TWIRA I-component needs OPENAI_API_KEY (still unset).

## 2026-07-03 · landing · claim waitlist
Done: `POST /claim` (201/409 idempotent, rate-limited) + `claim_stats` (migration 005);
landing waitlist form with live counter.

## 2026-07-03 · landing · v2.1 repositioning
Done: pricing ($0/$21/$50/$100/Enterprise), entity-types grid, TWIRA section,
evolution timeline, EU AI Act countdown; "Trust Infrastructure for Digital Entities".

## Earlier
SEO/AEO (sitemap, robots, llms.txt, agent.json), site pages (about, for-agents,
for-businesses, registries, how-it-works, privacy, terms), GitHub org fixes,
self-hosted GoatCounter analytics, under-construction banner.
