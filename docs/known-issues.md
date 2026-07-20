# Known Issues

From the full project audit on 2026-07-05. Severity: 🔴 blocker · 🟠 important ·
🟡 minor. Update the status line when you fix one.

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
| 24 | 🟡 | `/profile` has no fixed iOS-style header | **3.12** (extends the existing app-chrome scope) |
| 25 | 🔴 | fake "Verified in registry" + garbage text/wrong registry number appear on FIRST business creation, no user action | **3.14 ✅ fixed 2026-07-20, web PR #13** — root cause was `useRegistryCheck` firing a live external-registry name-search on every keystroke and treating a name match as verification; removed the hook, `registryStatus` now loads from DB (`business.registry_status`/`registry_data`) instead |
| 26 | 🟡 | company description has no visible Edit button | **3.13** |
| 27 | 🟡 | top button defaults to "Save", should default to "Edit" | **3.13** |
| 28 | 🟠 | verifiers take up too much space — need a compact icon menu | **3.13** |
| 29 | 🟠 | blocks (content) should be the primary object on the page, not verifiers | **3.13** |
| 30 | 🟡 | "Connect Camera" should live next to blocks, not in the general verify menu | **3.13** (+ ties to **14.5**) |
| 31 | 🟢 | Publish & Privacy should fold into the compact icon menu too | **3.13** |
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
| 7 | 🔴 | blocks: files don't attach, timestamps are UI-only | **1.20** (with 1.9) |
| 8 | 🟡 | Under-construction banner overlaps UI | **3.12** (app) + **10.6** (landing) |
| 9 | 🟢 | landing menu not sticky | **10.6** |
| 10 | 🟡 | app has no real header/menu bar | **3.12** |
| 11 | 🟠 | onboarding Camera step: dead QR/pairing stub | **3.12** |
| 12 | 🟡 | Share page shows internal link | **3.12** |
| 13 | 🟡 | Registry Match auto-verifies with no UX feedback | **3.10** |
| 14 | 🟡 | persona search card shows registry handle | **3.10** |
| 15 | 🟠 | profile needs full visual redesign | **3.13** (design-first) |
| 16 | 🟡 | no per-block permalink/view | **1.20** |
| 17 | 🟢 | favicon missing everywhere | **3.12** (app) + **10.6** (landing+email) |
| 18 | 🔴 | data leakage between entities of one account | **3.11** (prime suspect: `useProfileStore` localStorage reuse; backend must be ruled out too) |
| 19 | 🔴 | Pi CAM app won't launch | **14.4** (blocks 14.2/14.3) |
| 20 | 🔴 | blocks not indexed/findable | **1.20**; partly explained: `/search` covers entities only, block embeddings blocked on OpenAI billing (5.1) |
| 21 | 🟢 | marketing numbers not clickable/sourced | **10.6** |
| 22 | 🟢 | references block lost its article links | **10.6** |
| 23 | 🟢 | Academic Evidence lacks arXiv links | **10.6** |

## 🟡 `resolve-intent` `verified_only` defaults to `true` — L0 entities invisible to default agent calls (2026-07-16)
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
