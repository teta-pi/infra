# Known Issues

From the full project audit on 2026-07-05. Severity: 🔴 blocker · 🟠 important ·
🟡 minor. Update the status line when you fix one.

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
Status: OPEN.

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
Status: OPEN.

### 🔴 4. `landing/onboarding.html` "Apply for early access" form posts to a placeholder Formspree ID
`onboarding.html:180-181`: `<!-- TODO: replace YOUR_FORM_ID -->` /
`action="https://formspree.io/f/YOUR_FORM_ID"`. The submit handler
(`onboarding.html:255-279`) posts to this literal placeholder and every
submission fails; the JS catches the error and shows a generic "Something went
wrong" alert, so the whole page's funnel is silently dead. **Fix:** wire a real
Formspree ID (or point it at `/claim`, which is the app's actual working
onboarding endpoint).
Status: OPEN.

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
Status: OPEN.

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

### 🟠 9. Bitcoin timestamping is wired to a no-op stub — proofs are never actually submitted
Both media upload routes (`api/app/api/routes/media.py:130,188`) schedule
`_bitcoin_timestamp_bg` (media.py:38-40), which only logs
`"no-op until OTS integration"`. The real Celery task
`submit_bitcoin_timestamp` (`api/app/workers/tasks/bitcoin.py:10-33`), which
would set `Media.bitcoin_proof`, has zero call sites anywhere in `api/app`. The
hourly beat task `check_bitcoin_confirmations` (`bitcoin.py:36-69`) filters on
`Media.bitcoin_proof != None`, which can never match — so `bitcoin_confirmed`
can never become true through the normal upload flow, and no business can ever
reach `verification_level` `"partial"`/`"full"` via media provenance
(`businesses.py:88-96`). This looks like a believed-live feature (it has a beat
schedule and a real task) that's silently disconnected, not a documented gap.
Separately, even if wired up, `check_bitcoin_confirmations` passes the wrong
digest to verification — `verify_proof(media.bitcoin_proof, b"")`
(`bitcoin.py:58`) always checks against `sha256("")` instead of
`media.original_hash`, so it would always fail (silently, via the broad
`except Exception` at bitcoin.py:91-93). **Fix:** call
`submit_bitcoin_timestamp.delay(...)` from the upload routes instead of the
stub, and fix the digest argument.
Status: OPEN.

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
Status: OPEN.

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
Status: OPEN.

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
Status: OPEN (waiting on key).

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
