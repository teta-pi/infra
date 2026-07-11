# Roadmap — TETA+PI development plan

This is our **canonical development plan** and task queue. The manager session keeps
the *status* current; the owner only **adds** to it. Ordered by what unblocks the
most; each backlog item is sized for one focused session.

Status legend: ✅ done · 🔄 in progress · ⏳ queued/blocked · 🔴 blocker · 🟠 important · 🟡 minor.

---

## Current sprint — numbered directions, sub-numbered tasks
Naming: `TTPI · <n> <direction> · <n.m> <task>` (see `docs/workflow.md`). Directions:
**1 backend · 2 mcp · 3 frontend · 4 db · 5 devops · 6 manager**. Historical ✅ work
(pre-numbering: /auth/register removal, resolve_intent enrich, product metrics,
share button, landing pricing, TWIRA embedding code) lives in `docs/changelog.md`.
File ownership is disjoint so sessions never collide in git.

| n.m | Session (chat title) | Task | Status | Worktree / owns files |
|---|---|---|---|---|
| 1.1 | `1 backend · 1.1 fix private-block leak` | close 🟡 leak in `GET /businesses/{id}/blocks` | 🟢 ready to start | `routes/blocks.py` |
| 1.2 | `1 backend · 1.2 registry search logging` | append-only request log in `services/registry/*` → unlocks `registry_search_health` | ⚪ queued | `services/registry/*`, new migration |
| 2.1 | `2 mcp · 2.1 get_proof depth` | roadmap #5: ots_status, btc_timestamp_depth, C2PA chain → MCP 1.3.0 | 🟢 ready (worktree stands) | `ttpi-wt/2.1-get-proof` · proof route + `mcp/src/*` |
| 2.2 | `2 mcp · 2.2 agent auth design` | roadmap #6: design doc for scoped `pk_live_` agent auth (no code) | ⚪ after 2.1 · zero deploy | `docs/decisions.md` only |
| 2.3 | `2 mcp · 2.3 SSE streaming` | roadmap #7 | 🔴 deferred: server load | — |
| 2.4 | `2 mcp · 2.4 usage analytics` | roadmap #8 | 🔴 deferred: server load | — |
| 3.1 | `3 frontend · 3.1 web copy sync` | claim checkbox $21→$25, About link, title/meta | 🟢 ready (worktree stands) | `ttpi-wt/3.1-web-copy` · `web/src/` copy only |
| 3.2 | `3 frontend · 3.2 drag-to-reorder` | wire block reorder to `blockApi.reorder` | 🟢 ready to start | `web/…/profile/page.tsx` |
| 3.3 | `3 frontend · 3.3 camera capture` | #11b camera → C2PA + OTS (scaffold first) | ⏸ after 5.2 | `ttpi-wt/3.3-camera` · new files `web/src/app/capture/` |
| 5.1 | `5 devops · 5.1 enable TWIRA embeddings` | key → server `.env`, backfill, verify (code already merged) | 🔴 deferred: OpenAI billing unpaid + server capacity | server `.env` + one-off backfill |
| 5.2 | `5 devops · 5.2 split monorepo` | monorepo → hybrid polyrepo | 🔴 deferred: server upgrade first | `ttpi-wt/5.2-split` |

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
