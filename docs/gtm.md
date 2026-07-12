# GTM — Autonomous Go-To-Market Machine

Source of truth: the owner's **Autonomous GTM Plan** PDF
(`~/Downloads/TETAPI_Autonomous_GTM.pdf`, July 2026, confidential — not
committed to the repo). This doc transcribes it and maps every item to a
session number + owner so it can be executed the same way the rest of the
roadmap is. Companion doc `TETAPI_Platform_Integration_Strategy.pdf` (§07,
Shopify/Wix/universal snippet) has **not** been transcribed yet — read it
before starting 12.3.

**Core principle (verbatim):** classic GTM pushes a product to people. Ours
makes agents discover TETA+PI on their own, use it, and leave traces that
bring the next agents. Every mechanism is a loop, not a channel.

**Sequencing rule (verbatim):** first we are everywhere and self-verified —
THEN we pre-verify others. Legitimacy before outreach. Pre-verifying
strangers before we're visible ourselves would look suspicious ("who are you
to verify me?").

**Budget $0, horizon 90 days, owner Bob V.** All public posting/outreach
stays owner-gated per [[gtm-plan]] — sessions never post publicly on their
own.

Owner column below means: **Bob** = the human owner must perform the action
himself (external accounts, DNS, public posting, judgment calls) — a session
can prepare the artifact but not execute the step. **Session n.m** = a Claude
Code session does the work end-to-end.

---

## Plan at a glance

| Phase | Window | Objective | Exit criterion |
|---|---|---|---|
| 0 — Self-Registration | Week 1–2 | Listed on every MCP surface + verified in our own registry | 6+ listings live, self-proof public |
| 1 — Agent Discovery | Week 2–4 | Agents find and call `teta_search` organically | 50 organic tool calls/week |
| 2 — Pre-Verification | Month 2 | Top-500 MCP servers get pre-verified L1 profiles + claim outreach | 25+ claimed profiles (5%) |
| 3 — Self-Running Loops | Month 2–3 | Badges, C2PA links, cross-verification notifications compound | 100+ tool calls/week, 50+ badges live |

---

## Phase 0 — Self-Registration Everywhere (Week 1–2)

### 0.1 Registry listings — exact order (verbatim)

| # | Surface | Mechanics | Effort | Owner |
|---|---|---|---|---|
| 1 | **Official MCP Registry** (`registry.modelcontextprotocol.io`) | Publish `server.json` under namespace `dev.tetapi` via `mcp-publisher` CLI. **DNS TXT record proves domain ownership.** | 0.5 d | Bob (DNS + CLI auth) |
| 2 | Smithery | `smithery mcp publish <url> -n teta-pi/mcp-server`. Clean owned listing, not an auto-stub. | 0.5 d | Bob |
| 3 | Glama | Crawls the official registry — entry appears automatically. Then claim ownership to moderate it. | 0.5 d | Bob (claim only, after #1) |
| 4 | mcp.so + PulseMCP | Submit/claim. 20K+ servers on mcp.so — Claude Desktop users browse here. | 0.5 d | Bob |
| 5 | awesome-mcp-servers (GitHub) | PR to `punkpeye/awesome-mcp-servers`. Security/verification category is nearly empty — we start it. | 0.5 d | Bob |
| 6 | GitHub MCP Registry (`github.com/mcp`) | Submit — integrates into Copilot + VS Code one-click install. | 0.5 d | Bob |

**One metadata pack, reused everywhere:** name, one-line agent-query-optimized
description, transport (Streamable HTTP), auth method, one copy-paste Claude
Desktop config, homepage `tetapi.dev`, repo URL, MIT license, contact.

**Session mapping:** `2.5 mcp · MCP ecosystem listings prep` — session builds
the reusable artifacts Bob needs to actually submit: `server.json` for the
official registry, the metadata pack (above), the rewritten tool descriptions
(§0.3), and drafts the `awesome-mcp-servers` PR body. **No droplet load** —
`server.json` ships in the `mcp/` repo, doesn't touch the running server.
Bob then executes all 6 submissions himself (external accounts, DNS TXT, PR
from his own GitHub identity) — these are not things a session can do on his
behalf (Explicit-permission-required territory: publishing/posting).

### 0.2 Self-verification — dogfooding as proof (verbatim)

- TETA+PI becomes the **first verified entity in its own registry**: TetaPi
  GmbH, L2, with public C2PA + Bitcoin OTS proof page.
- Verified badge (SVG served from `tetapi.dev/badge/{entity_id}`) on all 4
  GitHub repos — the badge endpoint doubles as a free impression counter.
- Verify **Bob V.** and **Mykhailo M.** as person entities — founders eat
  their own dog food.
- Public proof URL linked from every registry listing: "This MCP server is
  itself a verified entity — see the proof."

**Session mapping:** no new code needed for the verification itself — the
claim flow, L2 method chooser, and public proof page all shipped in
`1.3`/`3.4`/`4.1` (verification rework, merged 2026-07-12). This is an
**owner action**: Bob runs TetaPi GmbH + himself + Mykhailo through the
existing `/claim` flow. The **badge SVG endpoint** it depends on does not
exist yet — new task **`1.10 backend · badge SVG endpoint`** (see §Phase 3
below, pulled forward since 0.2 needs it). Public GitHub repo README edits
(pasting the badge) are Bob's own repos — owner action, zero droplet load.

### 0.3 Agent-readable surfaces (verbatim)

- `tetapi.dev/llms.txt` — agent crawler guide (like robots.txt for LLMs).
- `tetapi.dev/.well-known/agent.json` — already live; bump to v1.1.0.
- Tool descriptions rewritten for agent queries. NOT "TETA+PI verification
  protocol server". YES "Verify if a business, person, or MCP server is real
  before your agent transacts with it".

**Session mapping:**
- `10.2 landing · llms.txt` — new static file in `landing/`, no droplet load
  (static asset, same as the 11 existing HTML pages).
- `2.5 mcp · MCP ecosystem listings prep` (same task as §0.1) — rewrite the
  7 `teta_*` tool descriptions in `mcp/src/index.ts` + bump both
  `.well-known/agent.json` files to v1.1.0 per the existing sync rule in
  `docs/mcp.md`. No droplet load — description strings only, no new tools.

---

## Phase 1 — Agent Discovery (Week 2–4)

No outreach yet — the listings work, we instrument.

### 1.1 Instrument tool calls (verbatim)
Log every MCP tool invocation: tool name, timestamp, anonymized client
fingerprint. "100 agent calls/week" is the traction metric.

**This is roadmap `2.4 · usage analytics`, currently 🔴 deferred: server
load.** GTM needs it for the Phase 1 exit criterion, so it can't stay
deferred indefinitely — **owner decision needed**: two shapes to pick
between before a session builds it:
- (a) **Lightweight append-only log line** written to a local file on the
  MCP server (rotated, rsynced off periodically) instead of a DB table — no
  new DB writes, minimal droplet load, but not queryable live for the
  dashboard without an aggregation step.
- (b) **DB table** (`mcp_usage_events`, append-only like
  `verification_events`) — queryable immediately by `8.x`, but adds writes
  per tool call on the already-at-capacity droplet (see `docs/roadmap.md`
  "Blocked" section).
Flag for Bob: pick (a) or (b) before booting this as `2.4`. Either way it's
the MCP session's file (`mcp/src/index.ts` + possibly a new backend log
route), not a new direction.

### 1.2 `proof_url` in every response (verbatim)
Every `teta_search` / `teta_verify_entity` response carries a proof link, so
when an agent cites the answer, the user sees `tetapi.dev`.

**Status check:** `teta_resolve_intent` already returns `proof_url` (shipped
in `2.1`). The other 6 tools (`teta_search`, `teta_verify_entity`,
`teta_verify_endpoint`, `teta_get_proof`, `teta_get_profile`,
`teta_verify_claim`) need it added. **Session mapping: `2.6 mcp · proof_url
everywhere`** — small, no new backend endpoint (the proof URL is
`tetapi.dev/e/{slug}`, derivable from data each tool already fetches). No
droplet load.

### 1.3 Show HN + MCP Discord (verbatim)
One honest "Show HN: verified entity registry for AI agents" post +
announcement in the official MCP Discord. Free, one-shot, timed after
listings are live.

**Owner-gated, no exceptions** — public posting is Explicit-permission
territory even before GTM's own rule. **Owner: Bob.** Session `13.2` can
draft the post copy for Bob to review, but Bob publishes it.

### 1.4 Collect top-500 dataset, quietly (verbatim)
Script pulls the official registry API + Glama public data: server name,
GitHub org, domain, npm package. Prep for Phase 2, no outreach yet.

**Session mapping: `13.3 gtm · top-500 dataset script`** — new off-server
script under `scripts/`, read-only HTTP calls to public APIs (registry +
Glama), writes to a local file/SQLite, not the prod DB. **Zero droplet
load** — doesn't touch `api.tetapi.dev` or the server at all.

---

## Phase 2 — Pre-Verification of Top-500 (Month 2)

**Hard dependency (verbatim): the claim flow must work before outreach — a
broken claim form kills the loop at step 2.** Claim flow shipped in
`3.4`/`1.3` — dependency is already satisfied.

| Step | Action |
|---|---|
| 1 | From the Phase-1 dataset, create pre-verified L1 profiles for top-500 MCP servers: public data only (GitHub org, domain, npm package). |
| 2 | Author outreach — GitHub issue or email, one per server: "Your MCP server has a pre-verified profile on TETA+PI. Claim it to…" |
| 3 | Claimed profile unlocks: verified badge SVG for README + agent-search analytics ("X agents verified you this week"). |
| 4 | Badge in README = permanent backlink + social proof — the next author sees it and claims theirs. Loop closes. |

**Tone guardrails (verbatim, non-negotiable):**
> Public data only. Instant claim AND instant opt-out/removal. Message tone:
> "we found and attested your public data — take control of it", never "we
> registered you". One message per author, no follow-up spam. A community
> backlash would invert the loop — these guardrails are not optional.

**Session mapping:**
- **`1.7 backend · bulk pre-verification import`** (new) — step 1 needs a
  way to create L1 entity profiles programmatically from the Phase-1
  dataset without going through the human claim UI per-entity. Check first
  whether the existing entity-creation API (used by `3.4`'s claim flow)
  already supports this via a script hitting it 500 times, or whether it
  needs a dedicated admin bulk-import endpoint (`require_admin` +
  `admin_audit_log`, same pattern as everything else in `routes/admin.py`).
  Scope this properly before building — likely a small new endpoint, not a
  big one.
- Step 2 (outreach) — **owner: Bob**, one message per author, using the
  guardrail language above verbatim. Not automatable without owner review
  of every message (this is exactly the kind of "acting on the plan"
  distinct from "sending messages on the user's behalf" — Explicit
  permission per message, or Bob sends them himself).
- Step 3 (claimed-profile unlocks) — reuses `1.10` badge endpoint (§Phase 3)
  + needs "agents verified you this week" analytics, which depends on `1.1`
  instrumentation existing first. Sequencing: `2.4`/`2.6` → `1.10` → this.
- Step 4 — passive, no work.

---

## Phase 3 — Self-Running Loops (Month 2–3)

| Loop (verbatim) | Session mapping | Droplet load |
|---|---|---|
| **Badge loop** — verified badge in READMEs → developers see it → claim → add badge. SVG endpoint counts impressions for free. | **`1.10 backend · badge SVG endpoint`** (new) — `GET /badge/{entity_id}` returns an SVG, increments an impression counter. Pulled forward: `0.2` (self-verification badges on our own 4 repos) needs this first. | 🟡 **flag**: new public, unauthenticated, high-fanout endpoint (every README render hits it). Needs response caching / a cheap counter write (not a full `admin_audit_log`-style row per hit) — note for the session to design around, not a reason to defer. |
| **C2PA loop** — every PI Camera asset carries a manifest linking to the creator's TETA+PI profile. Every signed photo shared = an ad. | **Direction 14 (PI Camera)** — per [[pi-cam]], dir 14 is "finish + verify platform integration"; this loop is the product reason that integration matters. No new session number, folds into 14.x. | None beyond existing C2PA/OTS pipeline (`3.3`/`11b`), already scoped as reuse-only. |
| **Cross-verification loop** — Agent A verifies entity B → B gets notified ("3 agents verified you this week") → B claims to see analytics → richer endpoint → more agents route to B. | **New, later** — depends on `1.1`/`2.4` instrumentation existing (can't notify on calls we don't log) + an email trigger (reuses `services/email.py`/Resend, already integrated). Not numbered yet — propose as a Phase-2/3 backend task once `2.4` ships. | 🟡 **flag**: adds notification logic + email sends triggered by MCP traffic — low per-event cost but is new sustained background work; sequence after the server-capacity upgrade (`9.1`) if volume is meaningful. |
| **Registry crawl loop** — directories crawl the official registry continuously; our listing propagates without action from us. | None — passive, no session needed. | None. |

---

## §07 — Parallel Arm: Platform Integrations (verbatim summary)

A second, equally important arm targets site owners directly (not just
agents), detailed fully in the **companion doc**
`TETAPI_Platform_Integration_Strategy.pdf` — not yet transcribed into this
repo. Same zero-budget, self-serve principle as Phase 0, applied to every
major CMS/website builder: WordPress/WooCommerce (specified, building now),
then Shopify and Wix, then a universal snippet for the 29–48% of the web
with no detectable CMS.

| Item | Session mapping | Owner |
|---|---|---|
| WordPress plugin (free + $25 pack) | `12.1` (in progress), `12.2` (publish) | Session builds, Bob approves the wordpress.org publish (owner-gated) |
| Shopify app | New — **`12.3 wordpress · Shopify app`** (misnamed direction, keep numbering; or split into a new direction if scope is large — Bob to decide) | Read companion PDF first |
| Wix app | New — **`12.4`** | Read companion PDF first |
| Universal snippet (non-CMS sites) | New — **`12.5`** | Read companion PDF first |

Combined Month-3 target (verbatim): **250+ organic MCP calls/week AND 300+
Tier-0 platform installs** — two independent, non-correlated traction
signals for the same registry. No droplet load from any of these — plugins
run on the site owner's infrastructure and call our existing public API at
normal traffic rates.

---

## §08 — Strategic context: Agentic Commerce Standards (verbatim, no action item)

Stripe's Agentic Commerce Protocol (ACP, with OpenAI) and Shopify's Universal
Commerce Protocol (UCP, with Google, backed by Amazon/Mastercard/Visa/
Meta/Microsoft/Walmart) went live across 1M+ Shopify merchants in
2025–2026, auto-enabled with no merchant opt-in. They solve discovery and
payment, **not** verification of who operates the merchant — no independent
cryptographic confirmation. This is unprompted external validation of the
exact gap TETA+PI fills. Not a competitive threat to route around — a talking
point. Once registry density + platform installs reach scale, a direct
partnership conversation with Stripe/Shopify becomes a realistic **Phase 4**
business-development target — unscheduled, owner-only, no session mapping
today.

---

## Metrics & Investor Scorecard (verbatim)

| Metric | Week 2 | Month 1 | Month 2 | Month 3 |
|---|---|---|---|---|
| Registry listings live | 4 | 6+ | 6+ | 6+ |
| Organic MCP tool calls / week | — | 50 | 100 | 250 |
| Pre-verified profiles | — | — | 500 | 500+ |
| Claimed profiles | — | — | 15 | 25+ (5%) |
| Verified badges in the wild | 4 (own) | 4 | 20 | 50+ |
| Registered entities (claim flow) | 5 | 50 | 200 | 500 |

### Feeding this into the `8.x` dashboard

| Metric | Dashboard status | Session to close the gap |
|---|---|---|
| Registered entities (claim flow) | ✅ already shown — `product_metrics.funnel` "verified" stage | none |
| Organic MCP tool calls/week | ⚪ placeholder in `8.2` labeled "not available — roadmap 2.4" | closed automatically once `2.4`/`1.1` ships |
| Pre-verified / claimed profiles | ❌ no metric source yet | new `8.4` once `1.7` (bulk import) exists — needs an L1-source flag on `businesses` or a query against the claim table |
| Verified badges in the wild (impressions) | ❌ no metric source yet | new `8.4`/extend `1.10` — the badge endpoint's own counter, surfaced via `product-metrics` |
| Registry listings live | not a DB metric — external state | tracked in this doc's checklist (below), not the dashboard |

---

## Ownership & Dependencies (verbatim, mapped to sessions)

| Workstream | PDF owner | Session / owner here | Depends on |
|---|---|---|---|
| Registry submissions (all 6) | Bob | Bob executes; `2.5` preps artifacts | MCP server publicly reachable + `server.json` |
| Self-verification + proof page | Mykhailo | Bob runs via existing `/claim` UI; no new session | `1.3`/`3.4`/`4.1` (done) |
| Badge SVG endpoint + counter | Mykhailo | **`1.10`** (new) | — |
| `llms.txt` + tool description rewrite | Bob + Mykhailo | `10.2` (llms.txt) + `2.5` (tool descriptions) | — |
| Top-500 dataset script | Mykhailo | **`13.3`** (new) | — |
| Claim outreach (Phase 2) | Bob | Bob, guardrails verbatim above | Phase 0 complete + claim flow live (already true) |
| Show HN + Discord post | Bob | Bob; `13.2` drafts copy only | Listings live |

---

## Execution checklist (Phase 0 exit criterion tracking)

Update this list as items land — it's the "registry listings live" metric,
which isn't a DB row anywhere else.

- [ ] Official MCP Registry (`registry.modelcontextprotocol.io`)
- [ ] Smithery
- [ ] Glama (auto after #1, then claim)
- [ ] mcp.so + PulseMCP
- [ ] awesome-mcp-servers PR merged
- [ ] GitHub MCP Registry
- [ ] TetaPi GmbH self-verified L2 + public proof page live
- [ ] Bob V. + Mykhailo M. verified as person entities
- [ ] `llms.txt` live
- [ ] `agent.json` bumped to v1.1.0 (both landing + app)
- [ ] Tool descriptions rewritten (agent-query-optimized)

---

## Session numbers introduced by this doc

| n.m | Task | Status | Files |
|---|---|---|---|
| 1.10 | backend · badge SVG endpoint + impression counter | ⚪ queued, needed before 0.2 | new route, likely `routes/badge.py` |
| 1.11 | backend · bulk pre-verification import | ⚪ queued, after 1.10/2.6, before Phase 2 outreach | new admin endpoint or script against existing API |
| 2.5 | mcp · MCP ecosystem listings prep (server.json, metadata pack, tool description rewrite, agent.json bump) | ⚪ queued, unblocks Phase 0 submissions | `mcp/src/index.ts`, `mcp/server.json` (new), both `agent.json` files |
| 2.6 | mcp · proof_url in every tool response | ⚪ queued, small | `mcp/src/index.ts` |
| 8.4 | analytics · pre-verified/claimed profile + badge impression metrics | ⚪ after 1.10 + 1.11 exist | `routes/admin.py` product-metrics, `admin/page.tsx` |
| 10.4 | landing · llms.txt | ⚪ queued, no deploy risk | `landing/llms.txt` (new) |
| 12.3–12.5 | wordpress · Shopify app / Wix app / universal snippet | ⏳ after companion PDF is transcribed | new dirs, TBD |
| 13.3 | gtm · top-500 dataset script | ⚪ after 2.5 (needs registry to be listed to pull from it) | new `scripts/` |

`13.2` (already in roadmap: "GTM machine v1") absorbs the remaining
owner-facing pieces that aren't standalone code tasks: drafting the Show HN
/ Discord copy, the outreach message template (guardrails verbatim), and the
launch checklist tying Phase 0 completion to the plugin release.

---

## Droplet-load summary (for the owner's capacity call, see `docs/roadmap.md`)

| Item | Load | Verdict |
|---|---|---|
| 1.1 instrumentation (Phase 1) | New DB writes per MCP call, or file-based if (a) chosen | 🟠 **owner decision required** before booting — pick (a) file log or (b) DB table |
| 1.10 badge SVG endpoint | New public high-fanout endpoint | 🟡 build with caching/cheap counter from day one, not a concern that blocks building |
| 1.7 bulk pre-verification import | One-off/batch writes, not sustained | 🟢 fine, batch it like other one-off merges |
| Cross-verification notifications (Phase 3) | New sustained background trigger + emails | 🟡 sequence after `9.1` server upgrade if volume is real |
| Everything else (registry submissions, llms.txt, tool descriptions, dataset script, WordPress/Shopify/Wix plugins) | Off-server, static, or client-side | 🟢 no droplet impact |
