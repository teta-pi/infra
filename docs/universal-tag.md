# Universal Tag — technical spec (transcribed)

Source: owner's **Universal Tag Spec** PDF (July 2026, confidential — not
committed; `~/Downloads/TETAPI_Universal_Tag_Spec.pdf`). Extends the Platform
Integration Strategy §03. This is roadmap **12.5** — the install path for the
~29–48% of the web that runs no CMS (static sites, custom-coded pages) and
can't use the WordPress plugin. Install motion = paste one script tag, same as
Google Analytics / Meta Pixel.

**Honest constraint (verbatim intent, non-negotiable in all public copy):** a
client-side script CANNOT create files at `/.well-known/` on a domain root —
that needs server access. The design is deliberately two-part, and Part A alone
must never be sold as full agent-readability.

## Two-part model

| Part | Install effort | What it gives |
|---|---|---|
| **A — script tag only** | paste 1 line in `<head>`, zero config | JSON-LD structured data injected at runtime + one indexing beacon to TETA+PI. Works only for agents/crawlers that execute JS |
| **B — script tag + DNS record** | + 1 CNAME/TXT record (one-time, ~5 min) + a one-line redirect rule at the host | real `/.well-known/agent.json`, `agent-card.json`, `/llms.txt` served from the domain root, reverse-proxied to TETA+PI which generates them dynamically. Works for ALL agents |

Part B is what actually matters for GTM; Part A is the low-friction on-ramp.
The install UI must disclose that A alone is partial.

## Install experience

1. **Script tag** (Part A, works immediately), generated from
   `tetapi.dev/generate` after creating/claiming an entity (same page as the
   WP plugin config; one shared `entity_id` across install methods):
   ```html
   <script async src="https://tetapi.dev/tag.js" data-entity="YOUR_ENTITY_ID"></script>
   ```
2. **DNS record** (Part B): `CNAME _ttpi-agent.yourdomain.com → verify.tetapi.dev`,
   or fallback `TXT yourdomain.com "ttpi-verify=YOUR_ENTITY_ID"`. Detected by a
   scheduled check (same cadence pattern as the WP plugin's domain-ownership
   check; acceptance: within 30 min). Then the owner adds a one-line
   redirect/rewrite rule at their host (per-host docs: Vercel `vercel.json`
   rewrite, Netlify `_redirects`, Cloudflare Page Rule/Worker, Apache
   `.htaccess`, Nginx location block).
3. **Verification**: once DNS is detected, the entity verifies via the existing
   Domain Ownership method (verification rework) — no separate logic.

## tag.js runtime behavior (Part A)

1. Read `data-entity`.
2. Inject schema.org JSON-LD into `<head>` from the entity profile
   (Organization/WebSite, name, url, `sameAs` → entity profile URL).
3. One beacon per page load: `POST https://api.tetapi.dev/v1/tag-ping`
   `{entity_id, page_url, page_title, referrer}` → feeds the entity's
   indexed-pages list on its public profile.
4. **No cookies, no cross-site tracking, no PII, no persistent identifiers** —
   deliberately less than a typical analytics script; state this in public docs.
5. Fails silently, never blocks render (async, GA-standard behavior).

## Well-known proxy (Part B)

```
Agent → GET yourdomain.com/.well-known/agent.json
      → host's redirect rule (owner-controlled)
      → https://verify.tetapi.dev/wk/{entity_id}/agent.json
      → generated dynamically from current entity data
      → Content-Type: application/json, cache ~5 min
```

TETA+PI needs no write access to the site at all — marketed as a lower
trust-ask than the WP plugin ("no plugin, no code changes, one redirect rule").

## Acceptance criteria (from the spec)

1. `tetapi.dev/generate` produces a working snippet keyed to an entity_id.
2. `tag.js` injects valid JSON-LD (verifiable via Google Rich Results Test).
3. Beacon fires once per load, fails silently offline, no render-blocking.
4. DNS record detected within 30 min of being set.
5. With DNS + redirect live, `GET yourdomain.com/.well-known/agent.json`
   returns valid current JSON with the right Content-Type.
6. Per-host install docs for at least Vercel, Netlify, Cloudflare Pages,
   Apache/Nginx.
7. Install UI clearly discloses Part A is partial; no overclaiming.
8. No cookies / persistent client-side identifiers.

## Build phases (manager breakdown, 2026-07-17)

Multi-repo — one session each, in dependency order:

| Phase | Task | Repo / owns | Notes |
|---|---|---|---|
| 12.5a | `tag.js` static file + `/generate` snippet page | `teta-pi/landing` | pure static; JSON-LD needs a public entity-profile fetch (existing public API) |
| 12.5b | `POST /v1/tag-ping` + dynamic wk-file generator (`/wk/{entity_id}/agent.json`, `agent-card.json`, `llms.txt`) | `teta-pi/api` | ✅ **done 2026-07-19, api PR #12**. Storage shape decided: bounded Redis sorted set per entity (200-page cap), not a new Postgres table — see `docs/decisions.md` 2026-07-19. Rate-limited (in-memory, same pattern as 1.10 badge; S-10 tracks the Redis-migration-for-multi-worker follow-up, unchanged). Not yet live-reachable at `verify.tetapi.dev` — needs 12.5c's nginx vhost |
| 12.5c | `verify.tetapi.dev` subdomain + nginx routes + scheduled DNS-record checker | server/devops | **prod-affecting** (new nginx vhost + cert + a periodic job); DNS checker can reuse the WP plugin's domain-check pattern |
| 12.5d | per-host install docs + landing "Universal Tag" section | `teta-pi/landing` | folds into/after 10.5's P2 section |

Sequencing: 12.5a and 12.5b can run in parallel (different repos); 12.5c after
12.5b (needs the wk endpoints to exist); 12.5d last. Nothing here blocks the
6.2 QA gate or GTM Phase 0 — this is the §07 platform-integration arm.
