# Known Issues

From the full project audit on 2026-07-05. Severity: 🔴 blocker · 🟠 important ·
🟡 minor. Update the status line when you fix one.

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
