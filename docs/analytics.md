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

## Open items

- No GoatCounter API token created yet (needed for option 2 above).
- No retention/backup policy set for `/opt/goatcounter/db/` — it's a single
  SQLite file, not currently in the backup rotation
  ([`backups/`](../backups)). Worth adding once real traffic accumulates.
- Public launch (Show HN / r/selfhosted / Product Hunt) is paused pending a
  decision on platform + copy — see [roadmap.md](roadmap.md) for current
  priorities.
