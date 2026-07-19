# Changelog — development log

Running record of what shipped. The **manager session** reads this to know current
state. Newest first. Every worker session appends an entry when it finishes a task,
using the `Done / Changed / Risk / Next` block (see `CLAUDE.md`).

---

## 2026-07-19 · 1 backend · 12.5b tag-ping + wk-generator
Done: `POST /v1/tag-ping` (anonymous beacon for `tag.js`, always 204, never
discloses entity existence, in-memory per-IP rate limit same pattern as the
1.10 badge endpoint) + `GET /wk/{entity_id}/agent.json`\|`agent-card.json`\|
`llms.txt` (public+published entities only, 404 otherwise, 5-min cache) —
Universal Tag Part A/B backend (`docs/universal-tag.md`, security B5). Storage
shape decided: bounded Redis sorted set per entity (`tag_pages:{business_id}`,
200-page cap via `ZREMRANGEBYRANK`) + a plain `INCR` counter, not a new
Postgres table — see `docs/decisions.md` 2026-07-19 for the reasoning
(droplet already at capacity, per-hit DB row ruled out, same call as 1.10).
Changed: `teta-pi/api` — new `app/api/routes/tag.py`, registered in
`app/main.py` without the `/api/v1` prefix (same as `badge.router`, since
`docs/universal-tag.md` spells the beacon URL as `api.tetapi.dev/v1/tag-ping`,
not `/api/v1/tag-ping`); `docs/api.md` (api repo) documents the new routes;
this repo's `docs/universal-tag.md`, `docs/security.md` (B5 built, S-10
refreshed), `docs/roadmap.md`, `docs/decisions.md` updated. PR:
`teta-pi/api#12`.
Risk: entity-id spoofing on `/v1/tag-ping` (inflating another entity's
indexed-pages list) is not prevented — anonymous by design, can't gate without
breaking the zero-friction install; blast radius bounded by the 200-page cap.
The indexed-pages list is not durable (lives only in Redis, capped) — fine for
a best-effort discovery signal, but don't build anything load-bearing on it
without revisiting. `/wk/*` routes exist but aren't reachable from a real
domain yet — needs 12.5c's `verify.tetapi.dev` nginx vhost + redirect rule.
Rate limiter is the same single-worker-only in-memory pattern as elsewhere
(S-10, unchanged, still open).
Next: 12.5c (`verify.tetapi.dev` subdomain + nginx + scheduled DNS-record
checker, devops/prod-affecting) can now build against real `/wk/*` routes;
12.5d (per-host install docs + landing section) after that. JSON-LD from
`agent.json` should get a Google Rich Results Test pass once a real entity is
wired end-to-end.

## 2026-07-19 · 3 frontend · 3.11 entity state isolation
Done: fixed QA #18 (critical) — creating a second entity under the same account,
in the same browser session, showed the previous entity's name/description/blocks
and a false "Verified in registry" badge for a few moments (or indefinitely, for
fields the new entity left empty). Root cause: `useProfileStore` (zustand) is a
module-level singleton, not scoped to a `businessId` — it was never reset when
`store.businessId` changed to a new entity, and `companyName`/`description` were
only overwritten `if (biz.x)` was truthy, so an empty field on the new entity left
the old entity's value in place. Verified isolation is clean at the API layer first
(two entities created via `pk_live_` key, `GET /businesses/{id}` on each — no
cross-contamination server-side) before touching frontend code, confirming this
was 100% a frontend store bug, not backend data leakage.
Changed: `web/src/app/profile/page.tsx` — the entity-load effect now resets
`companyName`/`description`/`blocks`/`nameStatus`/`registryData` to blank the
moment `businessId` changes (before the fetch, not after), and assigns the
fetched `name`/`description` unconditionally instead of only when truthy;
`EditView` is now keyed on `businessId` so `VerificationSection`/`PublishSection`/
`BlockCard`'s own local `useState` (registry status, email/domain verify progress,
publish state) also resets on entity switch instead of leaking.
Risk: none identified — reset-then-fetch only adds a blank frame while the new
entity's data loads, which is strictly more correct than showing stale data.
Next: none from this task.

## 2026-07-18 · wave 2 · 3.9, 15.2, 1.10 (+hotfix), 12.5a, 10.6 — six PRs merged
Done: **3.9** (web PR #10) — centralized 401 handling in `lib/api.ts`, `/profile`
now gates its whole edit surface behind a signed-out panel instead of leaving
a dead session editable; deployed, closes QA #1 (Critical)/#2/#4. **15.2**
(4 repos: api PR #9, web PR #9, mcp PR #4, landing PR #6) — CodeQL +
dependency-audit + secret-scan workflows live, all non-blocking (push+weekly).
**1.10** (api PR #10) — badge SVG endpoint shipped, but PR #10 itself had a
bug: `Business.id.cast("text")` — SQLAlchemy `cast()` needs a type object, not
a string — 500'd on every request. **Caught live within minutes of deploy**
(manager verifies every merge on prod before moving on), hotfixed same-day in
PR #11 (`cast(Business.id, String)`). Re-verified: 200 real entity
(`image/svg+xml`, Cache-Control, ETag), 404 unknown entity. **12.5a** (landing
PR #5) — `tag.js` + `generate.html` shipped; tag-ping beacon is a no-op until
12.5b exists (by design). **10.6** (landing PR #4) — 6 QA items across 11
pages: sticky nav (fixed a real CSS bug along the way), banner z-index/offset,
favicon, clickable sources for stats/citations.
Changed: web `lib/api.ts`/`profile/page.tsx`/`useProfileStore.ts`; 4×
`.github/workflows/*`; api `routes/badge.py` (+hotfix); landing `tag.js`,
`generate.html`, 11 `*.html` pages + favicon assets. `docs/roadmap.md` (1.10
new row, 3.9/15.2/12.5a/10.6 updated), `docs/security.md` §6.
Risk: the badge hotfix is the one real miss this wave — a syntax-valid but
runtime-broken SQLAlchemy call that only surfaces when hit. Everything else
prod-verified clean. Owner follow-ups queued (non-blocking): confirm the MCP
server count stat, arXiv IDs for 2 citations, email-template favicon.
Next: 3.11 (entity-state-leak, Critical, same web files as 3.9 — boot after
this) → 3.10 → 3.12 → 3.13. 12.5b needs the owner's storage-shape call.

---

## 2026-07-18 · 1.21 + S-9 backend · fallback proof_url + domain-check SSRF hardening
Done: api PR #8 merged + deployed (wave 2). **1.21** — the keyword-fallback in
`intent_graph/resolver.py` (the only branch running while OpenAI billing is
unpaid) now sets `proof_url=app.tetapi.dev/e/{slug}` on every result;
prod-verified: `resolve-intent` fallback returns a non-empty proof_url that
opens 200. **S-9** (security seed backlog) — `domain_ownership._check_file`
now resolves the host and rejects private/loopback/link-local/reserved IPs
(incl. the 169.254.169.254 metadata endpoint) and uses `follow_redirects=False`;
prod-verified rejecting a private-resolving domain. Closes the sibling SSRF
that api PR #3 left open (#3 only covered `/verify-endpoint`).
Changed: api `intent_graph/resolver.py`, `services/verification/domain_ownership.py`;
infra roadmap (1.21 ✅), security.md (S-9 CLOSED).
Risk: legit domains behind a CDN edge that resolves to a private range would
be rejected — unlikely for public verification domains. DNS-TXT path untouched
(DoH only, already safe).
Next: wave 2 still in flight — 1.10 badge (api), 12.5a tag.js (landing), 15.2
CI scanning (4 repos); 3.9/10.6 from wave 1. Owner decisions still open:
tag-ping storage (file vs DB), resolve-intent `verified_only` default.

## 2026-07-18 · 14.4 camera · boot failure diagnosed — Expo Go limitation, deps fixed; owner builds dev-client
Done: pi-cam PR #2 merged. `npm install`/Metro/`tsc`/full iOS prod bundle all
clean — the app "not launching" (QA #19) is NOT this repo's code: reanimated 4
+ worklets require the New Architecture, which the Expo Go client crashes on
at startup (known upstream reanimated#8235; `app.json` already enables New
Arch correctly). Fixed the two real version drifts expo-doctor found (expo
54.0.36, react-native-view-shot 4.0.3 → 18/18 checks). README now documents
why Expo Go can't run this app + both dev-client paths (local `expo run:ios`
with full Xcode, or cloud `eas build --profile development` with just an Expo
account). Repo-routing audit: all active session clones push to the correct
repos (3.9→web, 10.6→landing, 14.4→pi-cam); the "platform" label owners see
above chats is the project-folder name, and `teta-pi/platform` is archived
(read-only) so a stray push there fails loudly.
Changed: pi-cam `package.json`/lockfile/README (PR #2); roadmap 14.4 → 🔄
owner-step.
Risk: none to app behavior — no functional code touched. Device boot still
UNVERIFIED (no simulator/Xcode in the session env).
Next: **owner:** `eas build --profile development --platform ios` → confirm
boot on a real device → re-run 14.2 (full capture→upload→proof QA). Then
14.3 (TestFlight needs the Apple Developer account; Android APK is free).

## 2026-07-18 · manager · 6.2 GATE RE-RUN — GREEN (3 caveats); /search page live after a deploy-manifest fix
Done: merged 1.18c (`/search` page, web PR #7) — prod 404'd it despite a green
deploy because `deploy.yml` **overwrites `app-paths-manifest.json` with a
hardcoded route list**; added `/search/page` (web PR #8) — page live (200).
Then ran the FULL 6.2 gate authenticated (owner's test key from the local
key file): create registry-free 201 → block 201 → media upload 200 → search
finds it via API + `/search` page + real MCP `teta_search` session (correct
UUID, working proof link) → `/e/[slug]` 200 with the block → cleanup PATCH
200, entity hidden. **Verdict: 🟢 GREEN — GTM Phase 0 unblocked.** Caveats
filed, non-blocking: (i) block media serialization: empty `media_url`, null
`content_hash` → 1.20(a); (ii) NEW **2.7** — MCP `teta_resolve_intent`
ignores `verified_only:false` (raw API returns the entity, tool returns
empty); (iii) `proof_url: null` in keyword fallback → 1.21 (already filed).
Also note: media upload requires an undocumented `type` form field (422
without) — minor, noted for docs/api.md.
Changed: web `.github/workflows/deploy.yml` (PR #8), `docs/roadmap.md`
(6.2 → GREEN, new 2.7), this entry.
Risk: deploy-manifest hardcoding remains a footgun — every new top-level
route needs a manifest line; consider generating it at build time (small
devops follow-up, not filed as a numbered task yet).
Next: owner decides GTM Phase 0 go (registry submissions are his manual
step) and whether caveats (i)–(iii) ship first; wave-2 boots: 1.20+1.21
(api), 1.10 badge (api), 2.7 (mcp), 3.11 after 3.9 lands (web).

## 2026-07-18 · 15.1 · security threat model + finding triage + 15.2 loop design
Done: wrote `docs/security.md` — the canonical security reference. Threat model:
9 ranked assets (entity data, `pk_live_` keys, admin routes, append-only tables,
C2PA/OTS proofs, media store, `.env` secrets, PII, sessions); 5 trust boundaries
incl. the **new** tag.js↔`/v1/tag-ping` anonymous sustained-write beacon (B5, from
`docs/universal-tag.md`); 7 attacker classes; a per-surface checklist (authn,
authz/IDOR, SSRF, path traversal, injection, rate-limit, secrets). Triaged the
security-relevant findings into a seed backlog (S-1..S-10) mapped to tasks: 6.1
#1 traversal (S-1) + #7 SSRF (S-2) marked **CLOSED** against api PR #3 (verified
via `gh` — merged 2026-07-14; the changelog "PR #3 TWIRA" line is a different
repo); 6.1 #11 fake client verify → 3.9; QA #1 session-not-invalidated → 3.9;
QA #18 cross-entity leak → 3.11. Designed the recurring loop for 15.2 (CodeQL
JS+Python, npm audit, bandit, secret-scan — all runner-side, zero server load —
plus a monthly read-only re-audit cadence).
Changed: `docs/security.md` (new); `docs/roadmap.md` (15.1 ✅); `docs/known-issues.md`
(6.1 #1 + #7 marked CLOSED with api PR #3 ref).
Risk: none — pure docs/design, zero code, zero deploy, no prod contact. Closed-status
of S-1/S-2 depends on api PR #3 being the actual fix (confirmed against the api repo).
Next: **15.2** — implement the CI security workflows (`.github/workflows/*`) and
wire results back into `docs/security.md` §5.

## 2026-07-18 · 1.15 backend · proof_url fixed + update_block guarded; 1.21 spawned
Done: api PR #7 merged + deployed (wave 1 of the parallel plan). `resolve_intent`
proof_url now points at the live public page `app.tetapi.dev/e/{slug}` (session
live-verified: old URL 422 → new 200); `update_block`'s embedding call wrapped
in the same try/except as `add_block` (closes the 1.18 latent duplicate).
Manager prod checks after deploy: health 200; found "Test Reporter" now has
`verification_level: none` (was registry-verified in the 1.13-era tests —
something reset it during QA; explains default resolve-intent returning empty
for it, `verified_only:false` returns it fine — data change, not a regression).
Prod-confirmed the session's own caveat: the keyword fallback (the ONLY branch
running while OpenAI billing is unpaid) returns `proof_url: null` → spawned
**1.21** (tiny: populate proof_url in `intent_graph/resolver.py`).
Changed: api `routes/intent.py`, `routes/blocks.py`; infra roadmap (1.15 ✅,
new 1.21).
Risk: none — minimal fixes, success paths unchanged.
Next: wave 1 still in flight: 1.18c, 3.9 (web), 15.1 (infra), 10.6 (landing),
14.4 (pi-cam). 1.21 slots into the next api session (can bundle with 1.20).

## 2026-07-18 · manager · owner QA report (23 items) decomposed; 14.3 camera release queued
Done: decomposed the owner's 2026-07-17 QA bug report (5 Critical / 5 High /
8 Medium / 5 Low) into session tasks — full mapping table in
`docs/known-issues.md`. New roadmap rows: **3.9** (session/auth integrity —
#1/#2/#4), **3.10** (verifier UX per entity type — #3/#6/#13/#14), **3.11**
(🔴 entity state isolation / data leakage — #18), **3.12** (app chrome —
#8/#10/#11/#12/#17), **3.13** (profile redesign — #15, design-first),
**1.20** (blocks become real: media attach + permalink + indexing —
#7/#16/#20, ties to 1.9/5.1), **10.6** (landing polish — #9/#21/#22/#23 +
banner/favicon), **14.4** (🔴 Pi CAM app won't launch — #19, blocks
14.2/14.3), plus a proper **1.15** row (proof_url dead link + update_block
embed guard, was only in the retired platform repo docs). Also added **14.3**
(TestFlight + free Android release; owner prereq: Apple Developer Program).
Context noted: the QA ran before the 17th's fixes, so #2's 500-half and the
Resend half of #4 are already fixed; #20 is partly by-design (search covers
entities, embeddings blocked on OpenAI billing).
Changed: `docs/roadmap.md` (9 new/updated rows), `docs/known-issues.md`
(mapping table), this entry.
Risk: none — docs only.
Next: owner's priority boots: **1.15** (backend small bundle), **1.18c**
(/search page, last gate blocker), **15.1** (security, parallel). Then 3.9 →
3.11 as the next frontend chain.

## 2026-07-17 · 10.5 landing + 3.8 frontend · Landing Update v3 executed
Done: **10.5** — landing PR #3 merged + deployed: "Prove the claim. Not just
the identity." section (3 example cards: sushi chef/artist/journalist,
"Two checks, one block" diagram, no-legal-entity footer line, single
AI-disclosure sentence with manual-review/appeals wording) AND the P2
"Universal Tag" section (honest two-part disclosure, "Part A alone is a
partial signal"). Verified live on tetapi.dev. **3.8** — closed as a no-op:
all three P0 items from the master prompt were verified ALREADY fixed on live
prod (title/meta "Digital Entities", About → tetapi.dev/about.html, zero
localhost refs on every page) — the prompt's status check was stale; manager
re-verified independently before closing. Also closed stale PR #56 on the
retired platform repo (1.16 docs note, already recorded here).
Changed: landing `index.html` (PR #3); `docs/roadmap.md` (3.8 ✅ no-op,
10.5 ✅).
Risk: none — static HTML only; Universal Tag section shows an illustrative
snippet, 12.5a–c infra not deployed yet, section discloses this honestly.
Re-check its copy when 12.5 ships (noted in the 10.5 row).
Next: 1.18c (/search page) is the ONLY remaining piece before the full 6.2
re-run — corrected boot issued (the first 3.8/1.18c attempt cloned the
retired platform repo by mistake; boots now embed the exact git clone URL).

## 2026-07-17 · 1.18 backend · blocks-create + PATCH 500s fixed and prod-verified; test entities cleaned
Done: api PR #6 merged + deployed. Root causes: (a) `add_block` called
`generate_embedding` unguarded — the server's OpenAI key has unpaid billing, so
every create raised RateLimitError → 500; now try/except + warning log,
embedding is best-effort. (b) `update_business` returned the ORM object
without `db.refresh` after flush (unlike `create_business`) → MissingGreenlet
on `updated_at` serialization → 500 on any PATCH touching the booleans.
Prod-verified with the owner's test `pk_live_` key (stored in a local file,
never in chat): POST block → 201, PATCH `is_public/is_published=false` → 200.
Both leftover QA test entities hidden via the fixed PATCH — `/search` returns
0 for them, public endpoints 404. No direct DB cleanup needed.
Changed: api `routes/blocks.py`, `routes/businesses.py`; infra roadmap 1.18 →
(a)+(b) done, (c) search page in flight.
Risk: low (additive fixes). 🟡 latent duplicate filed in the 1.18 row:
`update_block` has the same unguarded embedding call — small follow-up.
Next: merge 1.18c (/search page PR) when it lands → full 6.2 re-run (now
fully unblocked: email works, key available, all known 500s fixed).

## 2026-07-17 · manager · two new owner tasks: Landing Update v3 + Universal Tag spec
Done: owner delivered (1) the **Landing Update master prompt v3** — pricing
already correct per its own status check, remaining work mapped to **3.8**
(web P0: About→localhost link, stale "Agent Economy" title/meta, doc-upload
"Coming soon" confirm-only) and **10.5** (landing P1: "Prove the claim, not
just identity" section with example cards + two-checks diagram + AI-disclosure
guardrail; P2 optional: Universal Tag section); (2) the **Universal Tag spec
PDF** — transcribed to new `docs/universal-tag.md` (two-part model: tag.js
JSON-LD+beacon; DNS+redirect → wk-proxy via new `verify.tetapi.dev`),
filed as **12.5** with a 4-phase build breakdown (12.5a landing ∥ 12.5b api →
12.5c devops → 12.5d docs). gtm.md §07 row updated (spec no longer "not
transcribed"). Noted in both roadmap rows: landing is static HTML, not the
Next.js the master prompt assumes; and 12.5b tag-ping is a new public
sustained-write endpoint — droplet-load flag + storage-shape owner decision
(file-log vs DB, same as 2.4).
Changed: `docs/universal-tag.md` (new), `docs/roadmap.md` (3.8, 10.5, 12.5),
`docs/gtm.md` (§07 12.5 row), this entry.
Risk: none — docs only.
Next: boot 3.8 + 10.5 (independent, parallel-safe); owner picks 12.5b storage
shape before 12.5 phases boot. 1.18 prod verification still pending owner's
three curl checks.

## 2026-07-17 · 3.6 frontend · auth store unified, publish/privacy controls shipped
Done: audit #10 FIXED — `/profile` (EditView, BlockCard, PiCamSection) now
reads `useAuthStore` first with fallback to `useProfileStore`/`auth_token`
for /claim users; plus a businessId bootstrap via `businessApi.list` so
/login-only users (who never had the claim flow's localStorage) get their
entity resolved instead of silently no-oping on Save/Publish/Verify.
Live-verified on prod with a real /login session: full profile renders, no
duplicate Pi CAM sign-in modal (closes the 14.2 QA finding too). Audit #11
ALREADY-RESOLVED — the fake domain-email step was removed by 3.7's claim
rework, grep confirms no stub remains. Audit #12 FIXED — new "Publish &
Privacy" section wiring `businessApi.publish`/`setPrivacy`; publish verified
live; setPrivacy is frontend-correct but hits the 1.18 PATCH-500 backend bug
(MissingGreenlet) — unblocks automatically when 1.18 lands. Also closed
duplicate web PR #5 (stale re-open of the already-merged 3.7 branch).
Changed: web `src/app/profile/page.tsx` only (PR #6); merged + deployed,
/profile 200 on prod.
Risk: low — token resolution order changed (shared store first); claim-flow
fallback preserved and SignInModal now syncs both stores on success.
Next: 1.18 backend fixes (blocks-create + PATCH 500) — the last backend
blocker; then the frontend /search page; then full 6.2 re-run for GREEN.

## 2026-07-17 · 1.19 backend · verified sender + email-code failures surfaced — email fully live
Done: `FROM_ADDRESS` switched to `TETA+PI <verify@tetapi.dev>` (domain verified
yesterday); `POST /auth/email-code` no longer fire-and-forgets — it awaits the
Resend send and returns 502 with a human detail on failure, clearing the
cooldown + stored code so the user can retry immediately. Manager merged
(api PR #5), deploy green, live-verified on prod: email-code to a NON-owner
address (guesslook@gmail.com) → 200 with no Resend error in logs — with the
new await-semantics that 200 is proof of acceptance, not a silent maybe.
Registration is now testable with any email address.
Changed: api `app/services/email.py` (FROM_ADDRESS, `send_verification_code`
→ bool), `app/api/routes/auth.py` (email-code awaits send; magic-link and
change-email paths untouched).
Risk: email-code response now blocks on Resend (~1s added latency) — intended.
Next: 1.18 (blocks-create + PATCH 500s) and 3.6 report are the remaining
open work; then frontend /search page; then full 6.2 re-run for GREEN.

## 2026-07-17 · manager+owner · Resend incident closed: key rotated, domain verified
Done: (1) **key rotation** — a Resend API key was exposed in a session
transcript during 3.7 diagnostics (2026-07-16); owner created a Full-access
replacement (two failed attempts first: an edited-but-never-restarted service,
then an invalid key — diagnosed via direct Resend API calls from the server),
manager restarted `tetapi-api`, verified the live `/auth/email-code` flow sends
clean (no Resend error in logs). Owner deletes the old exposed key in the
dashboard. (2) **domain verification (backlog #11, was DNS-blocked)** — owner
added `tetapi.dev` in Resend (EU region) and used the Cloudflare auto-config
authorization; DKIM/SPF/MX records propagated in ~4 min; Resend shows Verified;
manager's direct test send from `verify@tetapi.dev` to a **non-owner** address
was accepted — the only-owner-inbox sandbox restriction is gone. Root cause of
the owner's original "no email on registration" report was BOTH: sandbox mode
(only tetakta@gmail.com could receive) AND the in-flight key rotation.
Changed: server `.env` (new key; owner-performed), Cloudflare DNS (3 records,
auto-added by Resend), `docs/roadmap.md` (blocked-table #11 RESOLVED; new 1.19
row). No repo code changed yet — that's 1.19 (from-address swap + surfacing
send failures instead of silent 200), boot issued.
Risk: emails still sent from `onboarding@resend.dev` until 1.19 lands, so
non-owner recipients still fail — 1.19 is the last mile. Old exposed key must
actually be deleted in the dashboard (owner action, confirmed in chat).
Next: 1.19 session; then registration is testable with any email address.

## 2026-07-16 · 1.17 backend · /search + /resolve-intent query filtering fixed, verified on prod
Done: root cause found and fixed (api PR #4): in both endpoints the query text
never reached the SQL WHERE — all other filters (level, country, entity_type,
location) were applied, but `q`/`raw_query` was only used to re-score whichever
rows the LIMIT/OFFSET window happened to fetch. Once entity count exceeded the
window (10 for search, 50 for resolve-intent), true matches fell outside it —
hence identical results for any `q` in search, and empty resolve-intent. Fix:
ILIKE OR-filter (name/slug/description/ai_categories) added to the WHERE before
LIMIT/OFFSET in both paths; keyword fallback confirmed independent of the
OpenAI key. Manager merged + verified live on prod: `/search` correct on all 4
QA repro variants; `/resolve-intent` returns the right UUID on exact match.
Changed: api `app/api/routes/search.py`, `app/intent_graph/resolver.py`;
infra `docs/known-issues.md` (both 🔴 marked FIXED; new 🟡 on the
`verified_only=true` default hiding L0 entities from default agent calls —
product decision for the owner, not a defect), `docs/roadmap.md` (1.17 ✅).
Risk: low — additive WHERE clause, browse mode (empty q) unchanged. The 🟡
default means new L0 entities stay invisible to default `teta_resolve_intent`
calls until they verify — intended trust-first behavior, flagged for review.
Next: 1.18 (blocks-create 500 + PATCH 500) and the frontend `/search` page,
then full 6.2 re-run for GREEN.

## 2026-07-16 · 3.7 frontend + 1.16 backend · registry-free registration shipped
Done: **3.7** — claim flow reworked to type-first (step 0: Business/Organization
vs Person with journalist · actor · creator · other sub-copy) → email → entity
created immediately at L0 (`registry_status=unverified`), no registry step in
the create path; registry match is now optional-later via the 3.4 method
chooser on the profile. Merged as `teta-pi/web` PR #4, auto-deployed, `/claim`
verified 200 on prod. **1.16** — verified, no gap: `BusinessCreate` carries no
registry fields at all, `ClaimCreate` is type+email only, DB registry columns
nullable — no code change needed, no PR.
Changed: web `claim/page.tsx`, `useOnboardingStore`, `useProfileStore`,
`profile/page.tsx`, `lib/types.ts` (EntityKind = single source of truth, 6
values; old localStorage `"artist"` migrated via `normalizeEntityKind()`).
Risk: wider EntityKind surface — migration path covers old stored values; the
3.7 session also hit the `PATCH /businesses/{id}` 500 live and root-caused it:
`MissingGreenlet` serializing `updated_at` post-commit (`businesses.py:232`) —
folded into 1.18 as a root-cause lead. ⚠️ Ops note: a diagnostic grep during
the session exposed a server `.env` secret in a session transcript — owner
advised to rotate the affected key (done outside the repo; no secret committed
anywhere).
Next: 1.17 + 1.18 backend fixes, then frontend `/search` page, then full 6.2
re-run for GREEN.

## 2026-07-16 · manager · 6.2 follow-up — steps 2/3/4(a) now testable, all fail (still RED)
Done: a real owner `pk_live_…` key became available after the entry below was
written, unblocking steps 2/3 (previously untested for lack of auth) and
step 4(a) (previously not re-verified — Browser tool was down). Ran all
three live against prod. Step 2: `POST /businesses/{id}/blocks` 500s on
every payload tried (full body, minimal `{"title":"x"}`, explicit `order`),
across two different entities — the route itself is broken, not a
validation edge case; step 3 is unreachable as a result since
`/media/upload` requires an existing `block_id`. Step 4(a): the homepage
search box (`app.tetapi.dev`) fires a client-side navigation to
`/search?q=...`, which 404s — no such page route exists in the Next app,
and the UI shows no error, the input just clears. Also found, while trying
to clean up the two test entities this session created: `PATCH
/businesses/{id}` 500s whenever `is_public` or `is_published` is in the
body (isolated field-by-field; `name`-only patches work fine) — so the
"unpublish via PATCH" fallback cleanup path (there's no `DELETE`) is itself
broken, leaving `44edb26e-…` (from the first pass) and a second, new
diagnostic-only entity `4cfe5174-…` stuck live/public on prod.
Changed: `docs/known-issues.md` (three new 🔴 entries with isolated repro);
`docs/roadmap.md` new row 1.18 (blocks-create 500, PATCH 500, missing
search page) + row 6.2 status updated to summarize both passes.
Risk: two test entities remain publicly visible/searchable on prod
(`teta-qa-test-entity-62`, `teta-qa-diagnostic-entity`) until 1.18 lands and
someone re-runs the unpublish, or a human does a direct DB cleanup. No
product code was touched this session (read-only QA, docs-only diff).
Next: backend session on 1.18 (blocks-create + PATCH 500s) alongside 1.17
(search/resolve-intent), then a frontend session for the missing search
page; once all three land, re-run 6.2 end-to-end for a real GREEN.

## 2026-07-16 · manager · 6.2 pre-GTM core flow QA — GATE FAILED (RED)
Done: ran the 6.2 live E2E QA sweep against prod (`api.tetapi.dev`,
`app.tetapi.dev`, `mcp.tetapi.dev`) per the owner's gate. Verdict is **RED**,
not green. Confirmed step 1 (create-without-registry, 1.3's decoupling) still
holds via a pre-existing test entity. Confirmed step 5's `/e/[slug]` route
renders (shell only — no blocks on the probed entity). Found two new 🔴
blockers that fail step 4 outright: `GET /search` returns the identical
result set regardless of the `query` param (tested empty/exact-match/slug/
nonsense strings, all identical); `POST /resolve-intent`/`teta_resolve_intent`
(tested both raw curl and a real MCP client session against
`mcp.tetapi.dev/mcp`) returns empty results for every query, including
exact-name matches on entities that exist. Also confirmed a **fix**: the
2.5-era `/businesses/{id}/preview` 500 (blocked `teta_verify_entity`/
`teta_get_profile`/`teta_verify_claim`) is now resolved — clean 200s on both
the raw endpoint and both dependent MCP tools. Steps 2/3 (add a block, upload
a file/image) were **not tested** — they need an authenticated owner session,
and reading a login OTP out of the owner's real inbox on his behalf is out of
scope for an agent (coordinator confirmed this explicitly mid-session); do
not read this as pass or fail, it's simply unverified.
Changed: `docs/known-issues.md` (two new 🔴 entries with exact repro
queries/responses, one 2.5-era entry marked FIXED, an untested-steps note);
`docs/roadmap.md` row 6.2 marked GATE FAILED with the same summary.
Risk: GTM Phase 0 stays blocked until (a) a backend session root-causes and
fixes `/search` + `/resolve-intent`, and (b) someone who can complete an
owner login re-runs steps 2/3 and the media half of step 5. No code was
touched this session (read-only QA, docs-only diff).
Next: spin up a backend session against `/search`'s query-building logic and
`/resolve-intent`'s keyword-fallback path (both look like the same class of
bug — query text not reaching the filter/match step at all); once fixed,
re-run 6.2 with a real login to close steps 2/3/5(media).

## 2026-07-14 · manager · registration flow is still registry-gated in the UI → 3.7 + 1.16
Done: owner reported they couldn't find how to register a business without a
registry. Traced it: backend 1.3 decoupled `create_business` from registry
matching (confirmed — no registry call, `registry_status="unverified"`), BUT
the frontend claim flow (`web/src/app/claim/page.tsx`) never caught up — for
`entityKind === "business"`, step 1 still runs a registry search
(Handelsregister/Companies House) as the path forward. So the UI still feels
registry-first. Added **3.7** (frontend): rework the flow to type-first
(Business/Organization OR Person with journalist/actor/creator/other) →
email → create immediately at L0, registry becomes an optional later action
on the profile, not a creation gate. Added **1.16** (backend): verify the
create/claim endpoints accept the simplified payload with no registry fields
(likely already true post-1.3, small verification task).
Changed: `docs/roadmap.md` (new 3.7, 1.16).
Risk: none — docs only.
Next: boot 3.7 (frontend, `teta-pi/web`) + 1.16 (backend, `teta-pi/api`)
together; they're the fix for the owner's blocker.

## 2026-07-14 · manager · pre-GTM QA gate — 6.2 (core flow) + 14.2 (camera)
Done: owner asked for a full live E2E QA pass before starting GTM Phase 0 —
entity creation, block creation, file/image upload, search (human UI + MCP
agent), and camera sync. Added **6.2** as the blocking gate: create business
→ add block → upload file/image → confirm search finds it both via
`app.tetapi.dev` and a real MCP client (`teta_search`/`teta_resolve_intent`)
→ confirm `/e/[slug]` renders it. Read-only QA session — findings logged to
`known-issues.md`, not silently fixed. **14.2** runs in parallel (owner's own
suggestion) — full device flow QA in `teta-pi/pi-cam` (QR-link → capture →
C2PA sign → device-upload → verified block → proof), plus re-checking the
known "Connect Pi CAM no-ops when token null" finding. Also flipped 14.1 to
reflect reality: platform side already merged (PR #27), app repo already
transferred to `teta-pi/pi-cam`.
Changed: `docs/roadmap.md` (new 6.2, 14.2; 14.1 status corrected).
Risk: none — docs only.
Next: boot 6.2 and 14.2 in parallel.

## 2026-07-14 · github · org-level GitHub Project "TETA+PI Roadmap" created
Done: created an **org-level** GitHub Project v2 (github.com/orgs/teta-pi/projects/1)
that mirrors `docs/roadmap.md` as a visual kanban spanning all repos.
- Two custom single-select fields: **Direction** (15 options, 1 backend → 15
  security, matching `docs/workflow.md`'s direction table) and **Status**
  (collapsed the roadmap's richer emoji legend — ✅🔄⏳🔴🟠🟡⚪🟢 — onto 5
  buckets: Done, In Progress, Ready, Backlog, Blocked).
- Bulk-imported all **48** `n.m` rows from the current `docs/roadmap.md` as
  draft issue items (no repo currently has GitHub Issues open — checked
  `api`/`web`/`mcp`/`landing`/`infra`/`platform`, all empty — so draft items
  are the right default; nothing to link yet). Each item's body carries the
  row's task summary + a pointer back to `docs/roadmap.md` for full detail.
  Status/Direction were set to reflect **current real state**, not the
  roadmap's literal historical text — e.g. 13.2 and 15.2 read "after X" in
  the table but X has since shipped, so both are tagged Ready, not Backlog.
- **Views:** the Projects v2 GraphQL API has no mutation for creating or
  configuring views (layout, grouping) — confirmed by schema introspection,
  not an assumption. Only the default single ungrouped table view exists.
  Both fields are populated so the owner can stand up "Board grouped by
  Status" and "Board/Table grouped by Direction" in a few clicks each; this
  is the one piece of the design that could not be automated.
- Set the Project's `shortDescription` + `readme` (via `updateProjectV2`)
  stating the source-of-truth convention explicitly.
- Added the matching convention note to `docs/workflow.md` (PR #3): the
  board is a generated view, `docs/roadmap.md` stays canonical, sync is
  manual per session for now — automation flagged as a possible future task,
  not built here.
Changed: GitHub org Project settings (new), `docs/workflow.md` (PR #3, this
repo), `docs/changelog.md` (this entry).
Risk: none — no code, no deploy. The one real risk is drift between the
board and `docs/roadmap.md` if a session forgets the manual sync step; the
workflow.md note is the mitigation until automation exists.
Next: owner adds the 2 views manually (Board → group by Status; Board or
Table → group by Direction); consider a future roadmap.md→Project sync
Action if drift becomes a recurring problem.

---
---

## 2026-07-14 · 13.2 gtm · launch materials drafted (Show HN, Discord, outreach template, checklist)
Done: drafted Show HN post ("Show HN: TETA+PI – a verified entity registry
for AI agents", with explicit timing dependency on Phase 0 listings being
live), MCP Discord announcement (shorter, community-appropriate tone),
Phase 2 outreach message template (guardrail language verbatim: "we found
and attested your public data — take control of it", never "we registered
you", instant opt-out/removal, one message only), and a launch checklist
tying the Phase 0 execution checklist to a coordinated Show HN + Discord +
WordPress-plugin announcement.
Changed: new file `docs/gtm-drafts.md`. No code changes, nothing published
or sent — draft copy only, per `gtm.md`'s owner-gating rule.
Risk: none — no droplet load, no external calls, no publish action taken.
Next: Bob reviews `docs/gtm-drafts.md`, edits as needed, and posts Show
HN/Discord himself once the Phase 0 execution checklist in `gtm.md` is
fully checked. Phase 2 outreach template stays unsent until Phase 2 starts
(after `1.7`/bulk pre-verification import and the top-500 dataset, `13.3`).

## 2026-07-13 · manager · 5.3 execution started — MERGE FREEZE declared
Declaring a merge freeze on `teta-pi/platform` main while 5.3 (repo split
execution) runs, per the 5.2 plan's cutover protocol. No PRs will be merged
into this mono until the split's cutover (or an abort) completes and prod is
re-verified. Pre-existing org repos discovered NOT in the 5.2 plan:
`teta-pi/pi-camera`, `teta-pi/mcp-server`, `teta-pi/protocol` — all trivial
placeholders (2 commits, README/LICENSE only, dated 2026-06-26/28, predate the
session-numbered engineering process). Left untouched; not part of 5.3's
critical path; flagged for a separate cleanup decision later.

## 2026-07-13 · 9.1 devops · server resize executed — capacity blocker resolved
Done: owner executed the 9.1 runbook live. Pre-flight snapshot
(`pre-resize-2026-07-13`, 7.19GB, FRA1) → power off → resize `s-1vcpu-512mb-10gb`
→ **`s-1vcpu-2gb`** (2GB RAM / 50GB disk, $12/mo) → power on. Manager declared
a merge freeze for the window (no PRs merged during power-off) and ran full
post-resize verification: RAM 1.9GB total (798MB free, swap 0/2GB — was
swapping 323MB before), disk 6.8/48GB = 15% (was 78%), all services
(nginx/tetapi-api/tetapi-web/tetapi-mcp/docker/fail2ban) `active`, all 4
subdomains 200 (tetapi.dev, app, api/health, mcp/.well-known/mcp v1.4.0).
Merge freeze lifted.
Changed: `docs/roadmap.md` (server-capacity blocker section marked RESOLVED;
5.1, 5.3 unblocked on capacity grounds).
Risk: none — verified clean. 5.1 still separately blocked on unpaid OpenAI
billing (unrelated to capacity). Snapshot retained as rollback safety net.
Next: 5.3 (execute repo split) can be scheduled; 5.1 waits on billing; 2.4
usage analytics and Redis #12 no longer capacity-blocked.

## 2026-07-13 · 5.2 monorepo → separate repos (scope C) split plan
Done: wrote the scope-C split plan into `docs/decisions.md` (design only — zero
code moves, zero repo creation, zero deploy/server changes). Covers: target
layout (5 repos under `teta-pi`: api/web/mcp/landing + an `infra` meta repo for
canonical docs/CLAUDE.md/deploy/compose/unban-ip; wordpress-plugin gets its own
repo in the same cutover); per-folder history via `git filter-repo` (exact
commands) over a clean cutover; cross-repo contracts (web→api & mcp→api already
loose HTTP; the only build coupling is the cosmetic root npm-workspace +
lockfile — no inter-package deps, no shared TS types, so decoupling is a no-op);
per-repo deploy workflows + org-level `DEPLOY_SSH_KEY` + re-applied branch
protection; secrets distribution; cutover order + rollback (both pipelines hit
the same unchanged `/opt/tetapi/*` paths, so rollback = re-enable mono deploy);
and the 512 MB-box risk. Key finding: components are only bound by one CI file +
one lockfile — an ideal split.
Changed: `docs/decisions.md` (+ this entry). No code, no infra.
Risk: none this session (plan only). Execution risk lives in 5.3: four
independent deploy pipelines remove the mono's sequential-restart guarantee —
OOM risk on the 512 MB box.
Next: 5.3 (execute the split) — 🔴 GATED on 9.1 resize (`s-1vcpu-2gb`) landing +
this plan reviewed. Do the cutover deploys sequentially inside a merge freeze.

## 2026-07-13 · manager · 1.13 E2E verified on prod — MCP traction gate CLEAR
Done: after merging/deploying PR #39 (MCP 1.4.0), ran the resolve→verify→profile
E2E against live prod. Confirmed: MCP `/.well-known/mcp` = 1.4.0, 7 tools;
`resolve-intent {query:"reporter",entity_type:"person"}` → real **UUID**
`b75914b9…` (was slug — #2 fixed); `get_proof(UUID)` 200; `preview(UUID)` 200
(was 500 — 1.12 fixed). `verified_only` now sends `level="registry"` (#5, code
verified). **The gate before GTM Phase 0 registry listings is now clear** — the
flagship agent flow (find an entity, then verify it) works end to end.
Changed: `docs/roadmap.md` (1.13 → E2E VERIFIED).
Risk: none — verification only. Note: `resolve-intent` semantic ranking still
needs `OPENAI_API_KEY` (deferred, 5.1); keyword fallback works and returns
UUIDs correctly, which is what the fix targeted.
Next: GTM Phase 0 (2.5 listing metadata is ready) is unblocked; server resize
(9.1 runbook) before turning on 5.1/2.4.

## 2026-07-13 · 9.1 capacity audit + upgrade plan
Done: read-only audit of the prod droplet (no config/service changes).
Measured per-service RAM: TETA+PI stack (api+web+mcp+nginx+postgres+redis)
only ~116 MB; the box swaps (379 MB in swap at idle) because ~170 MB of fixed
non-app overhead (dockerd/containerd, goatcounter, an unrelated btc-robot
trio, multipathd, fail2ban) plus the stack leaves almost no headroom in
458 MB total — RAM-bound, not CPU-bound (load avg <0.2). Disk 78% used
(6.7/8.7 GB), dominated by OS packages + active docker image layers (772 MB,
not reclaimable garbage) + 341 MB Python venv; no large media/upload data yet.
Decided target: `s-1vcpu-2gb` (2 GB RAM / 50 GB disk, $12/mo) over the
literal-2x `s-1vcpu-1gb` ($6/mo) — the cheaper tier only patches today's swap,
not the RAM growth already queued in 5.1 (embeddings) and 5.3. Wrote the full
runbook (pre-flight snapshot, exact DO panel steps, merge-freeze coordination,
post-resize verification, rollback).
Changed: `docs/deployment.md` (new "Server resize runbook" section).
Risk: none — audit was read-only, no server changes made. Confirmed no
automated backup/snapshot exists — the runbook makes a manual pre-resize
snapshot a hard pre-flight step.
Next: owner schedules the resize window; manager declares the merge freeze in
this changelog before it starts; then 5.1/5.3 unblock.

## 2026-07-13 · manager · MCP status audit → task 1.13 (traction-readiness gate)
Done: live-probed prod MCP for a status report (owner priority: MCP is the
traction surface). Working: server up v1.3.1, http+sse, 7 tools registered,
`.well-known/mcp`+`agent.json` consistent, `teta_search`/`teta_get_proof`
return 200, 2.5 hardening + `server.json` listing metadata merged. Broken
(each reproduced live): 🔴 `/businesses/{id}/preview` 500 (breaks 3/7 tools),
🔴 `resolve_intent` returns slug not UUID (flagship resolve→verify dead),
🟠 `verified_only` no-op, 🟡 `get_profile` undefined media. Consolidated all
four into new **1.13 MCP traction-readiness** (folds in 1.12) — the gate that
must land before submitting any MCP registry listing (GTM Phase 0), else
agents' first contact hits 500s.
Changed: `docs/roadmap.md` (1.13 added, 1.12 folded).
Risk: none — docs only. The bugs themselves are live on prod now.
Next: boot 1.13; then server resize; then GTM Phase 0 listings.

## 2026-07-13 · 2.2 agent auth design · scoped pk_live_ design doc
Done: design-only (no code) for scoped `pk_live_` agent auth, written in
`docs/decisions.md`. Scope model (`admin:read`, `admin:write`,
`entity:write:<id>`, `entity:write:*` default), a new additive
`agent_api_keys` table (hashed keys, per-key scopes, soft-revoke — existing
`User.api_key`/`/auth/personal-api-key` untouched for backward compat),
issuance/rotation/revocation endpoints (`POST`/`GET`/`DELETE
/auth/agent-keys`), and how `require_admin`-style deps become a
`require_scope(...)` factory (entity-scoped writes checked inline next to the
existing owner-check, since the target id is a path param, not knowable at
`Depends()` time). Confirmed the design is general enough for 8.3 (metrics
notifier) to reuse as an `admin:read`-only key rather than inventing its own
mechanism, per `docs/analytics.md` §4's explicit ask.
Changed: `docs/decisions.md` only.
Risk: none — no code touched. The design itself flags rate-limiting of agent
keys as explicitly deferred (ties into the existing in-memory-rate-limiter
known-issue).
Next: implementation session for `agent_api_keys` (migration + deps.py +
`/auth/agent-keys` routes) whenever MCP write tools or 8.3 are actually
scheduled to build; 8.3 should wait for that implementation rather than
building its own scope check.

## 2026-07-13 · 10.2 landing · research-lab positioning, no money on hero
Done: removed all "TetaPi GmbH" claims from `landing/*.html` (we are not a
company yet) — repositioned as "TETA+PI research lab" everywhere (nav-adjacent
copy, footers, schema.org JSON-LD `publisher`, meta/og/twitter descriptions).
`about.html` "Company" section reworked into "The lab": dropped the invented
"Handelsregister · Germany" registry-entry claim, "Founded" → "Started ... as
a research lab". `terms.html`/`privacy.html` operator/controller language
reworded to "the TETA+PI research lab" + hello@tetapi.dev contact — legal
page structure and substantive clauses (liability, governing law, retention)
left untouched, no new legal entity invented. Hero CTA "Get verified — lock
$25 founding price" → "Create your page" (now links to app.tetapi.dev/claim
instead of the in-page anchor). Claim form below hero: kept, dropped the "$25
when billing launches" checkbox + its label, button → "Join early access —
be first"; removed `ready_to_pay` from the `POST /claim` payload accordingly
(backend field is optional, defaults `false` — confirmed in
`api/app/schemas/claim.py`, no backend change needed). Pricing section and
final-CTA money mentions further down the page left as-is per scope.
Changed: `landing/index.html`, `about.html`, `terms.html`, `privacy.html`,
`how-it-works.html`, `registries.html`, `for-agents.html`,
`for-businesses.html`.
Risk: none identified — verified all 8 edited pages render correctly via
local static preview; only remaining "GmbH" strings in `landing/` are
unrelated (third-party example entities like "GreenFarm GmbH", registry
category descriptions, form placeholder text).
Next: same GmbH/pricing cleanup for `landing/llms.txt` if the owner wants it
(out of scope here — task was `landing/*.html` only); app.tetapi.dev copy is
a separate task if the owner wants matching positioning there.

## 2026-07-13 · 2.5 mcp ecosystem hardening · E2E-tested + fixed live MCP server
Done: E2E-tested `mcp.tetapi.dev` from real clients — `claude mcp add
--transport http`, official `@modelcontextprotocol/inspector --cli`, and raw
JSON-RPC over curl — exercising all 7 tools with real + edge inputs. Found and
fixed 3 live protocol bugs: (1) **critical** — the server used one shared
`StreamableHTTPServerTransport` for the whole process, so only one client
could ever be connected at a time; every second client (confirmed with
`claude mcp add` and Inspector both failing while another session was open)
got `"Server already initialized"` until a restart. Fixed with a per-session
`Map<sessionId, transport>` (official SDK stateful-HTTP pattern), each with
its own `McpServer`. (2) No CORS — `OPTIONS /mcp` was a bare 405, blocking any
browser-based client. Added CORS headers + preflight handling. (3) Routing
wasn't scoped to `/mcp` — any path fell through to the transport handler; now
a clean 404. Also added a 15s request timeout in `client.ts` (previously
unbounded). Found but **not fixed** (outside `mcp/src/*` scope): `GET
/businesses/{id}/preview` 500s in prod, breaking `teta_verify_entity`,
`teta_get_profile`, `teta_verify_claim` (3/7 tools) — confirmed backend-side
via direct API curl, logged in `docs/known-issues.md` as 🔴, needs a backend
session. Prepared (not submitted) registry listing metadata: `mcp/server.json`
for the official MCP registry, plus a checklist for the Claude connectors
directory and other catalogs in `docs/mcp.md`. Documented client-setup
snippets (Claude Code/Desktop, Cursor, generic HTTP, Inspector) in
`docs/mcp.md`. Version bumped 1.3.0 → 1.3.1 (bootstrap-only fix, no tool
schema change) across `mcp/package.json`, `mcp/src/index.ts`, the
`/.well-known/mcp` manifest, and both `agent.json` files — all confirmed
still in sync.
Changed: `mcp/src/index.ts` (session-per-transport, CORS, routing, version),
`mcp/src/client.ts` (fetch timeout), `mcp/package.json`, `package-lock.json`,
`mcp/server.json` (new), `landing/.well-known/agent.json`,
`web/src/app/.well-known/agent.json/route.ts`, `docs/mcp.md`,
`docs/known-issues.md`.
Risk: bootstrap rewrite touches how every MCP request is routed — typechecked
clean and verified locally (two concurrent sessions, CORS preflight, 404
routing, tool calls) before push, but worth a live re-check against
`mcp.tetapi.dev` after deploy (re-run `claude mcp add --transport http` and
confirm it connects while a second session is also open).
Next: backend session to fix `/businesses/{id}/preview` 500 (🔴 in
known-issues.md, blocks 3/7 tools); owner decides on registry namespace
(`dev.tetapi/mcp` DNS-verified vs `io.github.teta-pi/mcp` GitHub-verified) and
runs the actual registry/connectors-directory submissions.

## 2026-07-13 · 12.1 wordpress · plugin MVP (free tier)
Done: `wordpress-plugin/` — new standalone WP plugin. Plan + $25 Premium Pack
proposal in `wordpress-plugin/README.md`. Free tier built in full: Settings >
TETA+PI page (connect via `pk_live_…` key, `GET /businesses` entity picker);
Domain Ownership verification (rewrite rule serves
`/.well-known/tetapi-verify.txt`, `POST /verify/domain/start` + `/check`,
same mechanism as `docs/verification-rework.md` §2); `[tetapi_badge]`
shortcode + widget pulling `GET /businesses/by-slug/{slug}/public`
(trust_level + legal_entity), 15-min transient cache. Premium pack is
UI-only stubs behind a license-key field, no payment/license-server code.
API key stored AES-256-CBC-encrypted (site's own `AUTH_KEY` salt) in
`wp_options`, never re-rendered. WordPress core APIs only — no Composer, no
build step, PHP 7.4+ compatible; `uninstall.php` cleans up all options.
Changed: new `wordpress-plugin/` tree only (`teta-pi.php`, `uninstall.php`,
`readme.txt`, `includes/`, `assets/`); `docs/architecture.md` (new
"WordPress plugin" section). No changes to `api/`, `web/`, `mcp/`.
Risk: PHP had no local interpreter in this sandbox to run `php -l` /
Plugin Check — files were hand-reviewed for syntax (brace/paren balance,
ABSPATH guards, escaping/sanitization/nonces on every input and output) but
not executed inside a real WordPress install. Verify with Plugin Check
before submitting to wordpress.org.
Next: install on a real WP site (or wp-env) to verify the connect → domain
verify → badge flow end-to-end, then run the official Plugin Check tool;
after that, 12.2 (publish to wordpress.org).

## 2026-07-13 · manager · 5.2 monorepo split — scope decided (C: separate repos)
Done: owner picked **scope C** for the long-deferred monorepo split — full
extraction of `api`/`web`/`mcp`/`landing` into separate `teta-pi` repos.
Reframed roadmap 5.2 as **plan-only** (write the C plan into `docs/decisions.md`:
history carry via `git filter-repo`, per-repo CI/deploy, cross-repo contracts,
secrets distribution, cutover+rollback, how the 512MB deploy model changes) —
zero code, zero deploy, safe to run now. Split execution carved out as new
**5.3**, 🔴 deferred behind the 9.1 server upgrade (it reworks prod deploy +
restarts on a capacity-bound box). Confirmed we are still a single repo
`teta-pi/platform` (npm workspaces web+mcp); split never executed.
Changed: `docs/roadmap.md` (5.2 rescoped, 5.3 added).
Risk: none — docs only.
Next: boot 5.2 plan session (worktree `ttpi-wt/5.2-split` reset to main).

## 2026-07-13 · 9 server + manager · SSH hardened key-only; owner access + docs
Done: resolved the recurring "SSH port 22 refused" incident. Root cause was two
layers: (1) the owner's Mac connected as `ssh root@…` with no `-i`, fell back to
password, and repeated failed passwords got the IP fail2ban-banned (CI kept
deploying fine over its key the whole time — sshd was never down); (2) the
server session then found password auth had *never actually been disabled*
(cloud-init `50-…conf yes` sorted before the old `60-…conf no`; OpenSSH takes
the first value) and fixed it properly with `00-tetapi-hardening.conf`
(`PasswordAuthentication no`), sshd restarted. Manager side: unbanned the
owner's IPs via a new `.github/workflows/unban-ip.yml` (runs over CI key);
confirmed the owner is NOT locked out — `~/.ssh/tetapi_ed25519` works — and
added a `Host tetapi` alias to the owner's `~/.ssh/config` so `ssh tetapi`
always uses the key (prevents the password-fallback that started this).
Documented the whole access model in `docs/deployment.md`.
Changed: `docs/deployment.md` (new SSH access section), `.github/workflows/unban-ip.yml`
(landed earlier as PR #30), owner's local `~/.ssh/config` (not in repo).
Risk: none new — hardening reduces attack surface. Note for future sessions:
password SSH is OFF; use the key; "refused from one machine" = fail2ban, not
sshd down.
Next: none required. Droplet confirmed 1 vCPU/512 MB — reinforces roadmap 9.1
capacity audit before any sustained-load task.

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
