# Analytics

How traffic to tetapi.dev is measured, what's already running, and what the
future **Analytics** tab in the back-office (`admin/`) needs to expose.

## Why self-hosted, not the built-in dashboard counter

The original "3.57k visitors ↗23.9%" number on the landing dashboard was
counting raw nginx requests, including vulnerability scanners. A 2026-07-03
investigation of `/var/log/nginx/access.log*` on the server found:

- 12,204 requests / 1,405 unique IPs over 7 days, but only **~50 were real
  browsers** (loaded `_next/static` or `.css` assets).
- The "social referrer" traffic (Reddit, Twitter, HN, Facebook — hundreds of
  hits) was **spoofed**. It came from 3 scanner IPs (2x Amsterdam/TECHOFF SRV,
  1x Dallas/DIGI VPS) setting `Referer: https://www.reddit.com/` while
  requesting `/.env`, `/wp-config.php`, `/wp-json/...`. No real mentions of
  tetapi.dev exist yet on Reddit, HN, or Google (checked via web search +
  HN Algolia API on 2026-07-03).
- 63% of all requests were 404s from bot scans (`/wp-admin`, `/.env*`,
  `/.git/config`, `/SDK/webLanguage`, etc).

Conclusion: nginx logs are not a reliable traffic source without heavy
filtering. Real visitor analytics needed a script-based counter that only
fires from an actual browser page load.

## What's running now

**GoatCounter** (self-hosted, v2.7.0, MIT license) — a lightweight
privacy-respecting analytics tool. Chosen over Plausible for lower resource
use (single Go binary + SQLite, fits the 512MB droplet) and no separate DB
service to run.

- **Binary:** `/opt/goatcounter/goatcounter` on the prod server
  (164.90.235.66)
- **DB:** SQLite at `/opt/goatcounter/db/goatcounter.sqlite3`
- **Service:** systemd unit `goatcounter.service`, listens on
  `127.0.0.1:8100`, proxied by nginx
- **Public dashboard:** https://stats.tetapi.dev (DNS: A record via
  Cloudflare, proxied)
- **Login:** tetakta@gmail.com (password set at creation, change on first
  login — not stored in this repo)
- **Real IP passthrough:** `/etc/nginx/conf.d/cf-real-ip.conf` maps
  `$http_cf_connecting_ip` so GoatCounter sees the visitor's real IP instead
  of Cloudflare's edge IP.

**Tracking script** — added to every page that should be measured:
```html
<script data-goatcounter="https://stats.tetapi.dev/count" async
        src="https://stats.tetapi.dev/count.js"></script>
```
Present in:
- [`web/src/app/layout.tsx`](../web/src/app/layout.tsx) (Next.js app —
  covers `/claim`, `/profile`, `/login`, etc.)
- All 11 static pages in [`landing/`](../landing) (`index.html`,
  `about.html`, `for-agents.html`, etc.)

Deployed in commit `c88117b`.

## Known quirks (don't re-debug these)

- **The raw `hits` table empties fast.** GoatCounter buffers pageviews in
  memory and flushes to SQLite every `GOATCOUNTER_STORE_EVERY` seconds
  (default 60), then aggregates into `hit_counts` / `hit_stats` / `paths` /
  `location_stats` / etc. and clears `hits`. Query `hit_counts` joined to
  `paths`, not `hits`, for real totals.
- **`/count` rate-limits per IP** (`x-rate-limit-limit: 4` seen in headers).
  Repeated manual `curl` tests against the same IP will silently succeed
  (200 + valid gif) without recording anything past the limit. Don't trust a
  "no new hits" result from rapid manual testing — it may just be
  rate-limited, not broken.
- **`curl` without full browser headers gets treated as a bot** and silently
  dropped (still 200s the tracking pixel — GoatCounter doesn't reveal
  filtering to the caller). Verify with a real browser (or the
  `read_network_requests` / preview tools), not bare `curl`.
- Cert for `stats.tetapi.dev` is covered by the existing `*.tetapi.dev`
  wildcard (Google Trust Services, via Cloudflare) — no separate certbot
  cert was needed.

## Scanner noise mitigation

Also set up 2026-07-04, since it's the other half of "why did the numbers
look wrong": **fail2ban** jails on the prod server target the exact scanner
patterns found in the nginx logs.

- `nginx-botsearch` (existing filter, was defined but not enabled) —
  wp-login/admin, phpMyAdmin, webmail paths.
- `nginx-scanners` (custom, added) — filter at
  `/etc/fail2ban/filter.d/nginx-scanners.conf`, matches `/.env*`,
  `/.git/`, `/wp-*`, `xmlrpc.php`, `.aws/`, `id_rsa`, `actuator`, `solr/`,
  common backup/shell-upload filenames, etc. Bans for 24h after 3 hits in
  10 minutes.

Both jails run with `backend = auto` (file polling on
`/var/log/nginx/access.log`), added to `/etc/fail2ban/jail.local`.

## Data available for a future Analytics tab

Everything the GoatCounter SQLite DB tracks, queryable directly or via its
JSON API (`stats.tetapi.dev/api/v0/...`, needs an API token — not yet
created):

| Table | What it holds |
|---|---|
| `hit_counts` + `paths` | pageviews per path per hour |
| `ref_counts` + `refs` | referrer domains/URLs per hour |
| `browser_stats` / `system_stats` | browser & OS breakdown |
| `location_stats` | visitor country (from GeoLite2, bundled) |
| `size_stats` | viewport size buckets (mobile/tablet/desktop) |
| `language_stats` | browser `Accept-Language` |
| `campaign_stats` | UTM campaign tracking, if links use `?utm_campaign=` |

For a back-office tab, the simplest path is either:
1. **Embed** the GoatCounter dashboard (iframe or link-out) — zero extra
   work, but not in-brand.
2. **Query GoatCounter's SQLite directly** (read-only) or its JSON API from
   the admin backend, and render with the existing back-office design
   system — matches the "красивий дешборд в нашому стилі" ask. Needs an
   API token created via the GoatCounter admin UI first
   (Settings → API tokens).

Option 2 is the one to build when `admin/` gets its Analytics tab.

## Product metrics (`GET /admin/product-metrics`)

Separate from the GoatCounter traffic bridge above — this is read-only
aggregation over our own tables (`businesses`, `claims`, `verification_events`),
served next to `/admin/stats` and rendered in the same Analytics tab. No new
tables; `?days=` (default 30, max 180) windows the two daily series.

- **`entity_growth`** — entities created per day (`businesses.created_at`).
- **`verification_events_daily`** — Temporal Moat events per day
  (`verification_events.created_at`).
- **`entities_by_type`** — count grouped by `businesses.entity_type` (the
  12-value enum; `/admin/stats` only breaks down by `verification_level`).
- **`funnel`** — claim → verified, joined by email since claims predate
  accounts: `claims` (waitlist total) → `signed_up` (claim email matches a
  `users` row) → `created_entity` (that user owns a `businesses` row) →
  `verified` (that entity's `verification_level != 'none'`).
- **`registry_search_health`** — **not available**. `routes/registry_search.py`
  and `services/registry/*` don't log requests anywhere (no latency, no
  success/fail counter, no `endpoint_probes`-style table for it). The endpoint
  returns `{"available": false, "note": "..."}` instead of guessing. To build
  this: add a lightweight append-only log (table or structured log line) in
  `verify_business_in_registry` capturing registry name, elapsed ms, and
  found/not-found, then aggregate here.

## Open items

- No GoatCounter API token created yet (needed for option 2 above).
- No retention/backup policy set for `/opt/goatcounter/db/` — it's a single
  SQLite file, not currently in the backup rotation
  ([`backups/`](../backups)). Worth adding once real traffic accumulates.
- Public launch (Show HN / r/selfhosted / Product Hunt) is paused pending a
  decision on platform + copy — see [roadmap.md](roadmap.md) for current
  priorities.

## Dashboard v2 design (roadmap 8.1)

Design only — no code in this session. Scope: the owner's single "super
dashboard" screen (admin back-office) plus the alerting agent that watches it.
Implementation is 8.2 (UI) and 8.3 (notifier agent).

Implemented 2026-07-12 (session 11.1) as the "Dashboard" tab in `/admin`
(default tab). Read-only, admin-gated, matches the layout in §2 exactly —
including the two "not available" placeholders (MCP usage, registry search
health), shown labeled rather than hidden. One addition beyond the endpoints
listed in §1: `GET /admin/health-check` (thin server-side aggregation) pings
`mcp.tetapi.dev/health` and `stats.tetapi.dev` from the API instead of the
browser, because `mcp.tetapi.dev`'s `/health` handler sends no CORS headers —
a direct browser fetch from `app.tetapi.dev` would misreport "down". The
notifier agent (8.3) can reuse this endpoint instead of pinging `/health`
itself.

### 1. Data source inventory

| Source | Endpoint | What it gives | Gaps |
|---|---|---|---|
| Snapshot counters | `GET /admin/stats` | users (total/today/week), claims (total, pay_ready %), entities (total, by `verification_level`), verification_events total | Point-in-time only — no trend, no deltas beyond today/week |
| Site traffic | `GET /admin/analytics` | GoatCounter bridge: pageviews, referrers, browser/OS, country, viewport, UTM campaigns | Real-visitor filtering already solved (see above); no alerting today |
| Product metrics | `GET /admin/product-metrics?days=` | `entity_growth` (daily), `verification_events_daily`, `entities_by_type`, `funnel` (claim → signed_up → created_entity → verified) | `registry_search_health` returns `{"available": false}` — not logged yet (roadmap 1.2 unblocks it) |
| Service liveness | `GET /health` (api.tetapi.dev), `GET /health` (mcp.tetapi.dev) | `{"status": "ok"}` process-alive check | No uptime history, no latency, no DB/Redis sub-checks — just "process answered" |
| MCP usage | — | **Does not exist.** No request logging in `mcp/src/*` or MCP-facing routes | Blocked on roadmap #8 / session 2.4 ("MCP usage analytics", currently 🔴 deferred: server load) |
| Registry search health | — | **Does not exist.** `registry_search.py` / `services/registry/*` log nothing (latency, success/fail) | Blocked on roadmap 1.2 (queued) — needs an append-only log table + migration |
| Server resource usage (RAM/CPU/disk) | — | **Not exposed via API.** Only visible via direct server access | Covered by session 9.1 capacity audit, not this dashboard's job — link out, don't duplicate |

Everything already available is read-only, admin-audited, and needs zero new
tables or endpoints. The three gaps (MCP usage, registry search health,
server resources) are explicitly out of scope for 8.2 and tracked as their
own roadmap items — the dashboard should show them as "not yet available"
placeholders rather than block on them.

### 2. Owner's critical metrics + layout

Metrics that matter for a one-person-checks-this-in-30-seconds dashboard,
picked for signal over completeness:

- **Growth** — new entities/day, new users/day (from `product_metrics.entity_growth`)
- **Claim → verified funnel** — conversion rate at each stage, and where it's
  leaking (`product_metrics.funnel`)
- **MCP usage** — placeholder until 2.4 ships; the metric that matters is
  "agents are actually calling `resolve_intent`/`get_proof`", the whole point
  of the product
- **Uptime/health** — API + MCP `/health`, last-checked timestamp, consecutive
  failures (this is what the notifier agent watches, see §4)
- **Traffic sanity** — real vs. bot-filtered pageviews (GoatCounter), so a
  traffic spike/drop is legible without opening `stats.tetapi.dev` separately

```
┌─────────────────────────────────────────────────────────────────────┐
│  TETA+PI · Owner Dashboard                     [last refresh: now]  │
├─────────────────────────────────────────────────────────────────────┤
│  HEALTH                                                              │
│  ● api.tetapi.dev  ok   (checked 2m ago)                             │
│  ● mcp.tetapi.dev  ok   (checked 2m ago)                             │
│  ● stats.tetapi.dev (GoatCounter)  ok                                │
├─────────────────────────────────────────────────────────────────────┤
│  GROWTH (last 30d)                    │  CLAIM → VERIFIED FUNNEL     │
│  entities/day   ▁▂▂▃▅▄▆▇  (sparkline) │  claims        1,204         │
│  users/day      ▁▁▂▂▃▃▄▄  (sparkline) │  → signed_up     412 (34%)   │
│  verification_events/day  (sparkline) │  → created_entity 190 (16%)  │
│                                        │  → verified       88 ( 7%)  │
├─────────────────────────────────────────────────────────────────────┤
│  ENTITY MIX (by entity_type)          │  VERIFICATION LEVEL          │
│  [bar chart, 12-value enum]           │  [bar chart, from /admin/stats]│
├─────────────────────────────────────────────────────────────────────┤
│  MCP USAGE                             │  TRAFFIC (GoatCounter, 14d)  │
│  ⚪ not available — roadmap 2.4         │  real pageviews  ▁▃▄▂▅      │
│                                         │  top referrers   [...]      │
├─────────────────────────────────────────────────────────────────────┤
│  REGISTRY SEARCH HEALTH                                              │
│  ⚪ not available — roadmap 1.2                                       │
└─────────────────────────────────────────────────────────────────────┘
```

Sections map 1:1 to existing endpoints except the two "not available" panels,
which render as a labeled placeholder (not hidden) so the owner knows the
gap exists and which roadmap item closes it.

### 3. Alert thresholds

What wakes the owner up at night vs. waits for the morning check. Severity
`critical` = push/telegram immediately; `warning` = email, batched, checked
each morning; `info` = shown on dashboard only, no notification.

| Metric | Condition | Severity | Channel |
|---|---|---|---|
| `GET /health` (api) | non-200 or unreachable, 2 consecutive checks (~10 min apart) | critical | telegram + push |
| `GET /health` (mcp) | non-200 or unreachable, 2 consecutive checks | critical | telegram + push |
| `stats.tetapi.dev` reachability | unreachable 3 consecutive checks | warning | email |
| Claims → signed_up conversion | drops below 50% of 7-day rolling average | warning | email |
| `entity_growth` (daily) | zero new entities for 3 consecutive days | warning | email |
| `verification_events_daily` | zero for 3 consecutive days (verification pipeline stalled) | critical | telegram + push |
| GoatCounter real pageviews (daily) | drops >80% day-over-day (vs. 7-day avg) | warning | email |
| Bot/404 request ratio (nginx, existing fail2ban data) | new spike pattern not matching known jails | info | dashboard only |
| `registry_search_health` (once it exists, 1.2) | success rate <90% over 1h | warning | email |
| MCP usage (once it exists, 2.4) | zero tool calls for 24h | info | dashboard only (early-stage signal, not urgent) |

Two real endpoints drive `critical`: both `/health` checks and
`verification_events_daily` (the core product working at all). Everything
else is `warning`/`info` — this keeps the "wakes the owner up" list short and
trustworthy; over-alerting trains the owner to ignore it.

### 4. Notifier agent architecture (8.3 scope)

Constraint from `docs/roadmap.md`: **prod droplet is at capacity** — no new
services, workers, or tables on the server. The agent must run entirely
off-server.

**Shape:** a scheduled process (local cron, or a scheduled Claude Code
session via the `schedule` skill) that:
1. Calls the existing read-only admin endpoints over HTTPS with an admin API
   key (`Authorization: Bearer pk_live_…` scoped to an admin/support user —
   reuses the existing `require_admin` + `pk_live_` mechanism, no new auth
   system).
2. Calls `GET /health` on `api.tetapi.dev` and `mcp.tetapi.dev` directly (no
   auth needed, both are public).
3. Diffs current values against the thresholds in §3 and its own last-run
   state (rolling averages, consecutive-failure counts — kept in a small
   local file/SQLite next to the script, **not** on the server).
4. Sends notifications via email (Resend, already integrated) or
   telegram/push (new integration, TBD in 8.3) when a threshold trips.

**What it needs that already exists:** `/admin/stats`, `/admin/analytics`,
`/admin/product-metrics`, `GET /health` (both services), an admin user with a
`pk_live_` key.

**What it needs that does NOT exist yet (scope for later sessions):**
- A way to issue an admin-scoped `pk_live_` key restricted to *read-only*
  admin routes — today `pk_live_` keys and JWTs hit the same `require_admin`
  dependency with no scope distinction. Session 2.2 ("agent auth design") is
  designing scoped keys for MCP; the notifier agent should reuse whatever
  scope mechanism that session lands on rather than inventing a second one.
- `registry_search_health` data (roadmap 1.2) and MCP usage data (roadmap
  2.4) — the two "not available" panels in §2. The agent can't alert on
  metrics that don't exist; those two threshold rows in §3 stay dormant until
  their source sessions ship.
- Telegram/push delivery — email via Resend works today (`services/email.py`),
  but telegram bot + push are net-new integrations, to be picked in 8.3.
- Every admin endpoint call the agent makes writes to `admin_audit_log`
  (existing trigger behavior) — worth confirming in 8.3 that a polling
  cadence (e.g. every 10 min) doesn't spam the audit log in a way that makes
  it harder to read for actual admin actions. Possibly needs a dedicated
  `action` tag like `stats.poll` so it's filterable.
