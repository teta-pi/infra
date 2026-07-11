# Changelog — development log

Running record of what shipped. The **manager session** reads this to know current
state. Newest first. Every worker session appends an entry when it finishes a task,
using the `Done / Changed / Risk / Next` block (see `CLAUDE.md`).

---

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
