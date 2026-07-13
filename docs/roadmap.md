# Roadmap — TETA+PI development plan

This is our **canonical development plan** and task queue. The manager session keeps
the *status* current; the owner only **adds** to it. Ordered by what unblocks the
most; each backlog item is sized for one focused session.

Status legend: ✅ done · 🔄 in progress · ⏳ queued/blocked · 🔴 blocker · 🟠 important · 🟡 minor.

---

## Current sprint — numbered directions, sub-numbered tasks
Naming: `TTPI · <n> <direction> · <n.m> <task>` (see `docs/workflow.md`). Directions:
**1 backend · 2 mcp · 3 frontend (product UI) · 4 db · 5 devops · 6 manager · 7 github · 8 analytics · 9 server · 10 landing (promo) · 11 backoffice · 12 wordpress (plugin) · 13 gtm (autonomous go-to-market) · 14 camera (PI Camera product) · 15 security (standing red-team)**. Historical ✅ work
(pre-numbering: /auth/register removal, resolve_intent enrich, product metrics,
share button, landing pricing, TWIRA embedding code) lives in `docs/changelog.md`.
File ownership is disjoint so sessions never collide in git.

| n.m | Session (chat title) | Task | Status | Worktree / owns files |
|---|---|---|---|---|
| 1.1 | `1 backend · 1.1 fix private-block leak` | close 🟡 leak in `GET /businesses/{id}/blocks` — owner sees all, others only `is_public` | ✅ done 2026-07-12, PR #10 | `routes/blocks.py` |
| 1.2 | `1 backend · 1.2 registry search logging` | append-only request log in `services/registry/*` → unlocks `registry_search_health` | ⚪ queued | `services/registry/*`, new migration |
| 1.3 | `1 backend · 1.3 verification methods` | **verification rework** (`docs/verification-rework.md`): decouple entity creation from registry (L0 free); registry → optional method; NEW email-control + domain-ownership methods; brand↔legal link endpoint + public disclosure. Document upload: NO backend | ✅ done 2026-07-12, PR #15 | `routes/businesses.py`, `routes/auth.py` (reuse), new `services/verification/*` |
| 1.4 | `1 backend · 1.4 TWIRA source_weight` | per-method trust weights (registry/email/domain/document) feeding T-component; account for the weak email-domain binding noted in known-issues (1.3 review) | ✅ done 2026-07-12, PR #17 (registry 1.0 > document 0.85 dormant > domain 0.75 > email 0.5) | `api/app/twira/*` |
| 1.5 | `1 backend · 1.5 rename resets registry status` | manager-review finding on PR #15: `update_business` keeps `registry_status="verified"` after a rename — reset to `unverified` on name change (see known-issues) | ⚪ queued · small | `routes/businesses.py` |
| 1.6 | `1 backend · 1.6 media path traversal fix` | 🔴 audit #1: `GET /media/local/{file_id}/{filename}` serves files with NO auth and NO path containment — resolve + `is_relative_to(_UPLOAD_DIR)` check. **Most exposed finding, live on prod — fix before anything else touches media** | 🔴 **TOP PRIORITY** · tiny | `routes/media.py` |
| 1.7 | `1 backend · 1.7 verification hygiene bundle` | audit #6 (PATCH keeps `agent_endpoint_verified` after endpoint change → reset), #7 (unauthenticated SSRF-prone `/verify-endpoint` → auth/rate-limit the fetch), #13 (Redis `GETDEL` for code confirm). Same family as 1.5 — can be one session with it | ⚪ queued · small | `routes/businesses.py`, `routes/endpoint_verification.py`, `services/verification/*` |
| 1.8 | `1 backend · 1.8 stop GET-writes; recompute level on write` | audit #8: GETs mutate `updated_at` via `_compute_verification_level` on tracked ORM + unconditional commit; level-filtered search stale until random GET. Persist level reactively on the writes that change it | ⚪ queued | `routes/businesses.py`, `core/database.py` (careful) |
| 1.9 | `1 backend · 1.9 wire bitcoin timestamping` | audit #9: upload routes call a no-op stub, real `submit_bitcoin_timestamp` has zero call sites, confirm-check verifies `sha256("")` (wrong digest). Wire task + fix digest; existing beat/task context only, no new workers | ⚪ queued | `routes/media.py`, `workers/tasks/bitcoin.py` |
| 1.12 | `1 backend · 1.12 fix /businesses/{id}/preview 500` | 🔴 found in 2.5 live E2E: `GET /businesses/{id}/preview` (agent_preview) 500s → breaks 3/7 MCP tools. **Folded into 1.13** (same resolve→verify→profile chain) | ➡ folded into 1.13 | — |
| 1.13 | `1 backend·mcp · 1.13 MCP traction-readiness` | **PRIORITY — the gate before any MCP registry listing (GTM Phase 0).** Close the whole broken resolve→verify→profile chain, all live-confirmed 2026-07-13: (a) 🔴 `GET /businesses/{id}/preview` → 500 (was 1.12) — breaks `get_profile`/`verify_claim`/`verify_endpoint`; (b) 🔴 audit #2 — `resolve_intent` returns **slug** as `entity_id` (`api/app/api/routes/intent.py:65`, `api/app/intent_graph/resolver.py:98`) while every MCP tool + API path wants **UUID** → flagship resolve→verify unusable; return real `biz.id`, keep slug only for `proof_url`; (c) 🟠 audit #5 — `verified_only` no-op (`mcp/src/index.ts:337` sends `undefined`/`"any"`, never filters) → send a real level; (d) 🟡 audit #16 — `get_profile` renders `undefined` media fields. **Exit criterion: all 7 tools pass a real E2E from Claude Code remote MCP / MCP Inspector against prod.** | 🔴 **TOP — blocks GTM Phase 0** | `routes/businesses.py` (preview), `routes/intent.py` + `intent_graph/resolver.py` (#2), `mcp/src/index.ts`+`client.ts` (#5,#16) |
| 2.1 | `2 mcp · 2.1 get_proof depth` | roadmap #5: ots_status, btc_timestamp_depth, C2PA chain → MCP 1.3.0 | ✅ done 2026-07-12, PR #9, live on prod | proof route + `mcp/src/*` |
| 2.2 | `2 mcp · 2.2 agent auth design` | roadmap #6: design doc for scoped `pk_live_` agent auth (no code) | ✅ done 2026-07-13, PR #33 (scoped pk_live_ design in decisions.md; 8.3 reuses admin:read) | `docs/decisions.md` only |
| 2.3 | `2 mcp · 2.3 SSE streaming` | roadmap #7 | 🔴 deferred: server load | — |
| 2.4 | `2 mcp · 2.4 usage analytics` | roadmap #8 | 🔴 deferred: server load | — |
| 2.5 | `2 mcp · 2.5 ecosystem hardening + listing` | **owner's end goal for direction 2: a fully working, debugged MCP in the Claude ecosystem (and others).** End-to-end test mcp.tetapi.dev from real clients (Claude Code/Desktop remote MCP, MCP Inspector), fix every protocol/manifest/tool-schema issue found; verify `/.well-known/mcp` + agent.json; then registry listings — official MCP registry, Claude connectors directory, other catalogs (actual submissions owner-approved). No new server features — hardening + distribution only, no sustained load. **Must absorb audit findings: 🔴 #2 (resolve_intent returns slug, every other tool wants UUID — flagship flow broken), 🟠 #5 (`verified_only` no-op), 🟡 #16 (`get_profile` renders undefined media fields), 🟡 #17 (`apiFetch` no timeout)** | ✅ done 2026-07-13, PR #31 (hardened: per-session transport, CORS, 15s timeout, server.json for listings; found new 🔴 backend /preview 500 → 1.12) | `mcp/src/*` (fixes only) + `routes/intent.py` (#2), `.well-known`, listing metadata, `docs/mcp.md` |
| 3.1 | `3 frontend · 3.1 web copy sync` | claim checkbox $21→$25, meta description (About link + title were already correct) | ✅ done 2026-07-12, PR #8 | `web/src/app/claim/page.tsx`, `layout.tsx` |
| 3.2 | `3 frontend · 3.2 drag-to-reorder` | wire block reorder to `blockApi.reorder` (native HTML5 drag + rollback) + admin badge → "FOUNDING LOCKED" | ✅ done 2026-07-12, PR #11 | `web/…/profile/page.tsx`, `admin/page.tsx` |
| 3.3 | `3 frontend · 3.3 camera capture` | → **moved to direction 14 (owner, 2026-07-12): camera is a standalone product, own session line.** See 14.1 | ➡ moved to 14.1 | — |
| 3.4 | `3 frontend · 3.4 verification methods UI` | rework UI (`docs/verification-rework.md`): method chooser (registry/email/domain active; document visible-DISABLED "Coming soon"); brand↔legal link UI; public disclosure of the link on profile + `/e/[slug]` | ✅ done 2026-07-13, PR #26 | claim/profile verification UI |
| 3.5 | `3 frontend · 3.5 claim page: no money` | mirror of 10.2 on app.tetapi.dev (owner 2026-07-13): remove the "$25 when billing launches — lock my founding price" checkbox from `/claim` (both form states), reframe to early access ("Join early access — be first"); `pay_ready` simply not sent (verify POST /claim tolerates absence — flag, don't fix backend). NOTE: coordinate with 3.4 — if 3.4 touches claim UI, land 3.4 first | 🟢 owner priority · after 3.4 lands if it touches claim | `web/src/app/claim/page.tsx` |
| 3.6 | `3 frontend · 3.6 auth store unification + real controls` | audit #10 (`/profile` never reads `useAuthStore` — login/settings users silently unauthenticated with false "Saved"), #11 (claim "domain email" step fully fake, `onClick={()=>{}}` + any 3 chars pass — wire to real `/verify/email/*` or hide; skip if 3.4 already wired it), #12 (no UI calls `businessApi.publish`/`setPrivacy` — build controls or remove dead surface) | ⚪ queued after 3.4 | `web/…/profile/page.tsx`, `login/settings/claim` auth wiring |
| 4.1 | `4 db · 4.1 verification rework migration` | migration: `entities.legal_entity_id` nullable self-FK + extend `verification_events.event_type` enum (`email_verified`, `domain_verified`, `document_verified`); append-only trigger must survive | ✅ done 2026-07-12, PR #14 (migration ran on prod deploy) | new migration + models |
| 5.1 | `5 devops · 5.1 enable TWIRA embeddings` | key → server `.env`, backfill, verify (code already merged) | 🔴 deferred: OpenAI billing unpaid + server capacity | server `.env` + one-off backfill |
| 5.2 | `5 devops · 5.2 split plan (scope C)` | **owner decided 2026-07-13: scope C — full extraction to separate GitHub repos** (`api` / `web` / `mcp` / `landing` each own repo under `teta-pi`). This task = WRITE the C split plan into `docs/decisions.md` ONLY (zero code, zero deploy): repo layout, how git history is carried per component (`git filter-repo` subtree), per-repo CI/deploy workflow design, cross-repo contracts (web→api URL, mcp→api URL, shared types/agent.json), secrets/`.env` distribution, cutover order + rollback, and how the 512MB droplet deploy model changes. Execution is 5.3+ (gated on server upgrade — do NOT execute here) | 🟢 ready · plan-only, zero deploy | `docs/decisions.md`; worktree `ttpi-wt/5.2-split` (reset to main) |
| 5.3 | `5 devops · 5.3 execute repo split (C)` | execute the approved 5.2 plan: create the repos, carry history, stand up per-repo deploy pipelines, cut over. **Prod-affecting (deploy rework + restarts on a 512MB box)** | 🔴 deferred: needs 9.1 server upgrade + reviewed 5.2 plan | new repos + per-repo `.github/workflows/*` |
| 6.1 | `6 manager · 6.1 system-wide bug audit` | read-only sweep api/web/mcp/landing → 17 verified findings in `docs/known-issues.md`; spawned tasks 1.6-1.9, 3.6, 10.3 + absorbed into 2.5 | ✅ done 2026-07-13, PR #23 | `docs/known-issues.md` only |
| 7.1 | `7 github · 7.1 branch protection` | protect `main`: PRs only, no force-push/delete, enforce_admins | ✅ done 2026-07-12, verified live | GitHub settings only, no code |
| 7.2 | `7 github · 7.2 repo descriptions vs landing` | audit org/repo descriptions + READMEs against current landing copy (Modules, $25, "Digital Entities"); propose diffs, land as one batched PR | ⚪ queued · no deploy until merge | GitHub metadata + `README.md`s |
| 7.3 | `7 github · 7.3 commit attribution audit` | verify commits across branches/repos show on the owner's GitHub account (noreply email policy), incl. worktree branches | ⚪ queued · read-only | none (gh/git read-only) |
| 8.1 | `8 analytics · 8.1 dashboard design` | design the super-dashboard: inventory existing metrics (`/admin/stats`, `/admin/analytics`, `/admin/product-metrics`, GoatCounter), define layout + which metrics matter + alert thresholds; DESIGN DOC first, no code | ✅ done 2026-07-12, PR #12 | `docs/analytics.md` |
| 8.2 | `8 analytics · 8.2 build dashboard` | implement the approved 8.1 design in the admin UI (read-only queries on existing endpoints, no new tables/workers) | ✅ done 2026-07-12 (as session 11.1) | `web/src/app/admin/page.tsx`, `web/src/lib/api.ts`, `routes/admin.py` (append-only) |
| 8.3 | `8 analytics · 8.3 metrics notify agent` | agent that polls key metrics and notifies on thresholds (runs OFF-server — scheduled Claude session / local cron hitting read-only admin API); no server-side workers until upgrade | ⚪ after 8.1 · off-server | new scripts/ or scheduled task, read-only API key |
| 9.1 | `9 server · 9.1 capacity audit + upgrade plan` | measure what's eating the droplet (RAM/CPU/disk per service), pick target droplet size + cost, write the upgrade runbook; unblocks 5.1/5.2/2.3 | ⚪ owner to schedule | server (read-only audit), `docs/deployment.md` |
| 10.1 | `10 landing · 10.1 verification methods copy pass` | after the rework ships: "How it works" + "Verification levels" mention email/domain/document methods | 🟢 ready (3.4 shipped) — bundle with 10.2/10.3 | `landing/index.html` |
| 10.2 | `10 landing · 10.2 positioning: research lab, no money on hero` | owner 2026-07-13: (1) remove ALL "TetaPi GmbH" claims across landing pages (we are not a company yet) → "research lab / startup" positioning; legal pages (terms/privacy) must stop naming a non-existent GmbH — reword to project/lab operator + contact email; (2) hero: remove money — CTA "Get verified — lock $25 founding price" → "Create your page"; (3) hero-adjacent claim form: KEEP (it feeds claim_stats + GTM Phase-2 outreach) but reframe to early access ("Join early access — be first"), drop the $25 checkbox line from it; pricing SECTION further down stays as is | ✅ done 2026-07-13, PR #29 | `landing/*.html` only |
| 10.3 | `10 landing · 10.3 landing truth pass` | audit 🔴 #3 (developers.html documents non-existent endpoints + wrong base URL — every curl 404s), 🔴 #4 (onboarding.html form posts to placeholder Formspree ID — funnel silently dead; point at /claim), 🟡 #14 (wrong support email `hello@teta-pi.io` ×4), 🟡 #15 (llms.txt wrong agent.json subdomain + says 4 MCP tools, real 7). Coordinate with 10.2 (same files family) — can be one session right after it | 🟢 ready · bundle after 10.2 | `landing/developers.html`, `onboarding.html`, `llms.txt`, `for-agents.html` |
| 11.1 | `11 backoffice · 11.1 build dashboard v2` | owner dashboard per the 8.1 design (took over 8.2): Dashboard tab in `/admin` + thin `GET /admin/health-check` | ✅ done 2026-07-12, PR #16 | `web/src/app/admin/page.tsx`, `web/src/lib/api.ts`, `routes/admin.py` (append) |
| 11.2 | `11 backoffice · …` | next backoffice tasks defined by owner/manager (e.g. claims ops tooling) | ⚪ open | `/admin` UI + admin routes |
| 12.1 | `12 wordpress · 12.1 plugin MVP` | **owner priority — first public release.** TETA+PI WordPress plugin, free tier: connect the WP site to a TETA+PI entity (`pk_live_` key), auto domain-ownership verification (plugin serves `/.well-known/tetapi-verify.txt`, calls `/verify/domain/start`+`/check`), verified-badge widget/shortcode. Define the $25 premium pack (aligned with Module #1 pricing) — PLAN the pack contents first, then build free tier fully + premium as licensed stubs. No server-side changes | ✅ done 2026-07-13, PR #28 | new `wordpress-plugin/` only (excluded from deploy.yml) |
| 12.2 | `12 wordpress · 12.2 publish to wordpress.org` | plugin review submission, listing copy (assets/screenshots/readme.txt), $25 pack purchase flow decision (license key via claim/Stripe — owner to pick); landing gets a "WordPress" mention (goes through 10.x) | ⏳ after 12.1 · owner approves the actual publish | `wordpress-plugin/` + listing metadata |
| 13.1 | `13 gtm · 13.1 GTM plan → docs/gtm.md` | transcribe + operationalize the owner's **Autonomous GTM Plan** (July 2026 PDF, confidential) into `docs/gtm.md`: Phase 0 self-registration (6 MCP registry listings — overlaps 2.5, which does the tech side), self-verification dogfooding (TetaPi GmbH L2 + founders as person entities, public proof page), Phase 1 agent discovery (instrument tool calls — needs a lightweight-logging decision vs deferred 2.4; proof_url in every response; Show HN/Discord owner-gated), Phase 2 top-500 pre-verification + claim outreach (guardrails: public data only, instant opt-out, one message, no spam; hard dep: claim flow live), Phase 3 loops (badge SVG endpoint `tetapi.dev/badge/{id}` = new small backend task, C2PA/PI-Camera loop → dir 14, cross-verification notifications). Map each item → session/owner, flag droplet-load items | ✅ done 2026-07-13, PR #25 (spawned: 1.10 badge endpoint, 1.11 bulk import, 2.6 proof_url, 8.4 gtm metrics, 10.4 llms.txt, 13.3 dataset script) | `docs/gtm.md` |
| 13.2 | `13 gtm · 13.2 GTM machine v1` | implement approved 13.1: Phase 0 execution support (listings metadata with 2.5), instrumentation + top-500 dataset script (off-server), badge endpoint task handoff to backend, outreach queue with owner-approval gate | ⏳ after 13.1 + 2.5 | per 13.1, off-server scripts/ |
| 14.1 | `14 camera · 14.1 Pi CAM → full integrated product` | **CORRECTED 2026-07-12 after checking the PI CAM session/app state:** Pi CAM already EXISTS — React Native + Expo app (iOS/Android), offline C2PA signing via Secure Enclave/Keystore, own project at `~/Downloads/PI CAM` (own chat session `PI CAM`), already wired to us: `modules/account` (QR link, `pk_live_`, entity binding) uploads via existing `POST /media/device-upload`. Task = FINISH + VERIFY the integration end-to-end: device-upload → server-side C2PA/OTS verification → verified block on profile + `/e/[slug]` → proof via `/proof` + MCP; fix the QA finding (Pi CAM "Connect" on `/profile` silently no-ops when token is null); GTM C2PA-loop: manifest links the creator's public TETA+PI profile. App-side work runs in the PI CAM session (own codebase, NOT this monorepo); platform-side bits (profile Connect flow, device-upload hardening) run here. ⚠️ Pi CAM dir is NOT a git repo — first step: `git init` + private GitHub repo | 🟢 ready · two-sided (app session + platform) | app: `~/Downloads/PI CAM` (PI CAM session) · platform: `ttpi-wt/14.1-camera` (`routes/media.py`, profile Connect UI) |
| 15.1 | `15 security · 15.1 threat model + red-team harness` | STANDING direction, first task: (1) write `docs/security.md` — threat model (assets: entity data, `pk_live_` keys, admin routes, append-only tables, C2PA/OTS proofs, media store; trust boundaries: agent↔MCP, browser↔API, device↔`/media/device-upload`, WP plugin↔API), attacker classes, per-surface checklist (authn/authz, IDOR, SSRF, path traversal, injection, rate-limit, secrets exposure); (2) triage the 6.1 audit's security findings (🔴 #1 path traversal, 🟠 #7 SSRF, #11 fake client verify) as the seed backlog, mapped to the backend fix tasks (1.6-1.9); (3) design the RECURRING loop — a read-only authorized audit re-run cadence + CI security scanning (CodeQL / `npm audit` / `bandit` — runs on the GitHub runner, ZERO server load) to add in 15.2. **Authorized, our-own-infra only; no destructive/DoS/exfil tests against prod; findings reported, not exploited.** | 🟢 ready · design+audit, zero deploy | `docs/security.md` (new), `docs/known-issues.md` (append) |
| 15.2 | `15 security · 15.2 CI security scanning` | implement the 15.1 loop: add CodeQL (JS+Python) + dependency-audit workflows to `.github/workflows/` (runner-side, no server load); wire results into `docs/security.md` tracking. Recurring after that | ⚪ after 15.1 | `.github/workflows/*`, `docs/security.md` |

## Coordination rules (so parallel sessions don't break each other)
- Each session touches **only its own files** (table above). Never edit another
  session's file.
- Shared-risk files: `web/src/lib/api.ts` (sessions 3 & 6) — **only append new
  functions at the end**, don't touch existing lines → merges cleanly.
- `routes/*` — each session takes its **own** file (auth / blocks / admin), never a
  peer's.
- Claude **commits + pushes automatically**; deploy is automatic on push to `main`.
  After each merge the **manager verifies on prod**.
- Each session ends with the `Done / Changed / Risk / Next` block and updates the
  matching `docs/*.md`.

## Blocked — waiting on keys / DNS / server (don't start until provided)
**Server capacity (2026-07-11):** the prod droplet is at its limit until the owner
upgrades it. Until then: no tasks that add SUSTAINED load (embeddings backfill,
Redis #12, SSE streaming #7, extra workers) and no deploy rework (S8 split
execution). One-off merges are fine (build runs on the GitHub runner; server side
is rsync + brief restarts) — but batch them.

| Item | Needs | Effect when unblocked |
|---|---|---|
| Turn on TWIRA semantics (#3, session 7) | `OPENAI_API_KEY` **billing unpaid (429)** + server upgrade | semantic search + `/resolve-intent` + block embeddings turn on |
| S8 monorepo split (execution) | server upgrade (deploy rework + restarts) | hybrid polyrepo; then S5 camera |
| Resend domain verification (#11) | DNS on `tetapi.dev` (DKIM/SPF) | emails reach everyone, not just the owner inbox |
| Ukraine registry | `OPENDATABOT_API_KEY` | UA registry search works (verifier already written) |

---

## Backlog — ordered by what unblocks the most

### Now — fix what's broken (from known-issues)
1. ✅ **Persist profile blocks to the backend** — load entity+blocks on open, save
   add/edit/remove via the API. *(Done 2026-07-06, `6a022bb`. Reorder UI = session 3.)*
2. ✅ **Remove/gate `/auth/register`** — dead, unauthenticated. *(Done 2026-07-06.)*
3. 🔄 **Turn on TWIRA semantics** — embedding CODE merged 2026-07-11 (PR #3: embed on
   block create/update + `twira_backfill_block_embeddings` task). REMAINING: set
   `OPENAI_API_KEY` on the server `.env` (obtained 2026-07-06) + run the backfill.
   *(Devops session 7 — server-side only now.)*
   - 🟡 also open: `GET /businesses/{id}/blocks` leaks private blocks (session 2);
     in-memory rate-limit/lock assumes single worker → move to Redis before scaling (#12).

### Next — the MCP investment (owner's priority)
The differentiator: make TETA+PI the registry agents actually route through
(see `docs/mcp.md`).
4. ✅ **Enrich `teta_resolve_intent`** — returns `first_verified_at`, proof URLs, and the
   full T/I/P breakdown in a shape agents can rank on; adds `entity_types` +
   `min_trust` filters. *(Done, MCP 1.2.0, merged.)*
5. ⏳ **`teta_get_proof` depth** — include OTS status, btc_timestamp_depth, C2PA chain
   length so agents can set their own trust threshold. *(Not started — was bundled with
   the MCP session but only resolve_intent shipped.)*
6. **Agent-facing auth for MCP writes** — design how a verified agent authenticates
   to the MCP server (scoped `pk_live_` keys) before adding any write tools.
7. **Streaming / batched search** for large result sets over SSE.
8. **MCP usage analytics** — which tools agents call, latency, so we tune TWIRA
   weights from real `(query, clicked_entity)` pairs (the data moat closing).
   *(Bundle with the MCP session — it touches the MCP server; do not run parallel to #4/#5.)*

### Product — account & sharing
9. ✅ **"Share page" button** on `/profile` linking to `/e/[slug]` (+ copy link).
   Shown only when the entity is published. *(Done 2026-07-06.)*
10. **Sessions list with devices** — needs server-side session storage (JWT is
    stateless today); "log out everywhere" already works via token_version.
11. Resend domain verification so emails reach everyone. *(Blocked on DNS.)*
11b. **Camera capture → C2PA + OTS notarization** (session 5) — capture photo/video
     through the camera and run it through the EXISTING C2PA signing + OpenTimestamps
     pipeline (blocks already carry `c2pa_manifest` / `ots_proof`). Three use-cases:
     proof-of-creation (content made by a verified entity), proof-of-process (video
     verification of production / standards compliance), and copyright deposit
     (timestamp as priority evidence). Reuse the proof services — do not build a
     parallel pipeline. Scaffold capture UI as new files under `web/src/app/capture/`;
     plan first, then wire. *(Frontend + Backend.)*

### Back office — internal analytics
15. 🔄 **System metrics dashboard** (session 6) — on top of the existing `/admin/stats`
    (snapshot counters) and `/admin/analytics` (GoatCounter traffic), add: time-series
    trends (entity growth + verification_events per day), entities by `entity_type`,
    a claim → verified funnel, and registry search health (success rate / latency).
    Read-only aggregation, `require_admin` + audit, no new tables. MCP-usage analytics
    stays out of scope here (that is #8).

### Platform — scale readiness
12. 🟠 Move rate limiters + Handelsregister lock to Redis (unblocks multi-worker).
13. More US state registries (CA, TX, DE-state portals) via the `us_states.py` pattern.
14. Learned TWIRA weights (logistic regression on click logs) once MCP analytics exist (#8).

---

## How to pick up an item
New session → read `CLAUDE.md` + the docs named in the item → do just that item →
update docs + append to `known-issues.md` → `changelog.md` → commit + push → `/clear`.
