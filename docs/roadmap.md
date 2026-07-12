# Roadmap — TETA+PI development plan

This is our **canonical development plan** and task queue. The manager session keeps
the *status* current; the owner only **adds** to it. Ordered by what unblocks the
most; each backlog item is sized for one focused session.

Status legend: ✅ done · 🔄 in progress · ⏳ queued/blocked · 🔴 blocker · 🟠 important · 🟡 minor.

---

## Current sprint — numbered directions, sub-numbered tasks
Naming: `TTPI · <n> <direction> · <n.m> <task>` (see `docs/workflow.md`). Directions:
**1 backend · 2 mcp · 3 frontend (product UI) · 4 db · 5 devops · 6 manager · 7 github · 8 analytics · 9 server · 10 landing (promo) · 11 backoffice**. Historical ✅ work
(pre-numbering: /auth/register removal, resolve_intent enrich, product metrics,
share button, landing pricing, TWIRA embedding code) lives in `docs/changelog.md`.
File ownership is disjoint so sessions never collide in git.

| n.m | Session (chat title) | Task | Status | Worktree / owns files |
|---|---|---|---|---|
| 1.1 | `1 backend · 1.1 fix private-block leak` | close 🟡 leak in `GET /businesses/{id}/blocks` — owner sees all, others only `is_public` | ✅ done 2026-07-12, PR #10 | `routes/blocks.py` |
| 1.2 | `1 backend · 1.2 registry search logging` | append-only request log in `services/registry/*` → unlocks `registry_search_health` | ⚪ queued | `services/registry/*`, new migration |
| 1.3 | `1 backend · 1.3 verification methods` | **verification rework** (`docs/verification-rework.md`): decouple entity creation from registry (L0 free); registry → optional method; NEW email-control + domain-ownership methods; brand↔legal link endpoint + public disclosure. Document upload: NO backend | 🟢 ready (4.1 merged) | `routes/businesses.py`, `routes/auth.py` (reuse), new `services/verification/*` |
| 1.4 | `1 backend · 1.4 TWIRA source_weight` | per-method trust weights (registry/email/domain/document) feeding T-component | ⏳ after 1.3 · small | `api/app/twira/*` |
| 2.1 | `2 mcp · 2.1 get_proof depth` | roadmap #5: ots_status, btc_timestamp_depth, C2PA chain → MCP 1.3.0 | ✅ done 2026-07-12, PR #9, live on prod | proof route + `mcp/src/*` |
| 2.2 | `2 mcp · 2.2 agent auth design` | roadmap #6: design doc for scoped `pk_live_` agent auth (no code) | ⚪ after 2.1 · zero deploy | `docs/decisions.md` only |
| 2.3 | `2 mcp · 2.3 SSE streaming` | roadmap #7 | 🔴 deferred: server load | — |
| 2.4 | `2 mcp · 2.4 usage analytics` | roadmap #8 | 🔴 deferred: server load | — |
| 3.1 | `3 frontend · 3.1 web copy sync` | claim checkbox $21→$25, meta description (About link + title were already correct) | ✅ done 2026-07-12, PR #8 | `web/src/app/claim/page.tsx`, `layout.tsx` |
| 3.2 | `3 frontend · 3.2 drag-to-reorder` | wire block reorder to `blockApi.reorder` (native HTML5 drag + rollback) + admin badge → "FOUNDING LOCKED" | ✅ done 2026-07-12, PR #11 | `web/…/profile/page.tsx`, `admin/page.tsx` |
| 3.3 | `3 frontend · 3.3 camera capture` | #11b camera → C2PA + OTS (scaffold first) | ⏸ after 5.2 | `ttpi-wt/3.3-camera` · new files `web/src/app/capture/` |
| 3.4 | `3 frontend · 3.4 verification methods UI` | rework UI (`docs/verification-rework.md`): method chooser (registry/email/domain active; document visible-DISABLED "Coming soon"); brand↔legal link UI; public disclosure of the link on profile + `/e/[slug]` | ⏳ after 1.3 | claim/profile verification UI |
| 4.1 | `4 db · 4.1 verification rework migration` | migration: `entities.legal_entity_id` nullable self-FK + extend `verification_events.event_type` enum (`email_verified`, `domain_verified`, `document_verified`); append-only trigger must survive | ✅ done 2026-07-12, PR #14 (migration ran on prod deploy) | new migration + models |
| 5.1 | `5 devops · 5.1 enable TWIRA embeddings` | key → server `.env`, backfill, verify (code already merged) | 🔴 deferred: OpenAI billing unpaid + server capacity | server `.env` + one-off backfill |
| 5.2 | `5 devops · 5.2 split monorepo` | monorepo → hybrid polyrepo. Session findings (2026-07-12, plan phase only, no code): (1) `decisions.md` has NO split plan — it must be designed and written first; (2) scope undecided, owner must pick: (a) split npm workspace + per-component deploy workflows (prod-affecting), (b) JS/structural decoupling keeping one deploy.yml, or (c) full extraction to separate repos. Restart as: pick scope → write plan to `decisions.md` → execute | 🔴 deferred: server upgrade first + owner scope decision (a/b/c) | `ttpi-wt/5.2-split` (clean, rebased) |
| 7.1 | `7 github · 7.1 branch protection` | protect `main`: PRs only, no force-push/delete, enforce_admins | ✅ done 2026-07-12, verified live | GitHub settings only, no code |
| 7.2 | `7 github · 7.2 repo descriptions vs landing` | audit org/repo descriptions + READMEs against current landing copy (Modules, $25, "Digital Entities"); propose diffs, land as one batched PR | ⚪ queued · no deploy until merge | GitHub metadata + `README.md`s |
| 7.3 | `7 github · 7.3 commit attribution audit` | verify commits across branches/repos show on the owner's GitHub account (noreply email policy), incl. worktree branches | ⚪ queued · read-only | none (gh/git read-only) |
| 8.1 | `8 analytics · 8.1 dashboard design` | design the super-dashboard: inventory existing metrics (`/admin/stats`, `/admin/analytics`, `/admin/product-metrics`, GoatCounter), define layout + which metrics matter + alert thresholds; DESIGN DOC first, no code | ✅ done 2026-07-12, PR #12 | `docs/analytics.md` |
| 8.2 | `8 analytics · 8.2 build dashboard` | implement the approved 8.1 design in the admin UI (read-only queries on existing endpoints, no new tables/workers) | 🟢 ready (8.1 merged) | admin UI + `routes/admin.py` (append-only) |
| 8.3 | `8 analytics · 8.3 metrics notify agent` | agent that polls key metrics and notifies on thresholds (runs OFF-server — scheduled Claude session / local cron hitting read-only admin API); no server-side workers until upgrade | ⚪ after 8.1 · off-server | new scripts/ or scheduled task, read-only API key |
| 9.1 | `9 server · 9.1 capacity audit + upgrade plan` | measure what's eating the droplet (RAM/CPU/disk per service), pick target droplet size + cost, write the upgrade runbook; unblocks 5.1/5.2/2.3 | ⚪ owner to schedule | server (read-only audit), `docs/deployment.md` |
| 10.1 | `10 landing · 10.1 verification methods copy pass` | after the rework ships: "How it works" + "Verification levels" mention email/domain/document methods | ⏸ after 3.4 ships | `landing/index.html` |
| 11.x | `11 backoffice · …` | back office gets its own direction; first tasks defined after 8.1 design lands (dashboard build 8.2 may move here) | 🟢 unblocked (8.1 merged) — manager to write boot | `/admin` UI + admin routes |

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
