# GTM Phase 0 — submission packet (roadmap 13.2)

Companion to [`gtm.md`](gtm.md) (plan) and [`gtm-drafts.md`](gtm-drafts.md)
(launch copy). This file is the copy-paste packet for the **six registry
submissions** in `gtm.md` §0.1 — everything a session could prepare without
external accounts is here; Bob executes each submission himself (owner-gated:
publishing/posting, external-account creation).

Status: all technical prep (`2.5`) is done and prod-verified. Nothing below
has been submitted yet — see the checklist in `gtm.md` and `gtm-drafts.md`
§4 for the "when to post" gate.

---

## Reusable metadata pack

| Field | Value |
|---|---|
| Name | TETA+PI |
| One-line description (agent-query-optimized) | "Verify if a business, person, or MCP server is real before your agent transacts with it." |
| Longer description | Trust infrastructure for AI agents: search and verify people, businesses, journalists, artists and organizations via official registries, C2PA media provenance, and Bitcoin OpenTimestamps proof. |
| Homepage | `https://tetapi.dev` |
| Repo | `https://github.com/teta-pi/mcp` |
| Remote endpoint | `https://mcp.tetapi.dev/mcp` (Streamable HTTP) |
| Auth | none |
| License | MIT |
| Contact | tetakta@gmail.com |
| Claude Desktop config | `{"mcpServers":{"tetapi":{"url":"https://mcp.tetapi.dev/mcp"}}}` |

**Gap:** no square logo/icon asset exists yet (needed for the Claude
connectors directory and helps other catalog listings). Design task, not
code — flag for Bob/Mykhailo before those submissions.

---

## 1. Official MCP Registry (`registry.modelcontextprotocol.io`)

Manifest ready: [`mcp/server.json`](https://github.com/teta-pi/mcp/blob/main/server.json)
(namespace `dev.tetapi/mcp`). Needs a one-time DNS TXT record on `tetapi.dev`
to prove domain ownership, then `mcp-publisher publish` from `mcp/` — see
`docs/mcp.md` "Listings" section for the exact steps. Owner-run (DNS + CLI
auth are not things a session can do).

## 2. Smithery

`smithery mcp publish https://mcp.tetapi.dev -n teta-pi/mcp-server` — use
the metadata pack above verbatim for name/description if prompted.

## 3. Glama

Crawls the official registry automatically once #1 is live — verified live
2026-08-21, Glama's public API (`glama.ai/api/mcp/v1/servers`) is real and
queryable (used by `scripts/gtm/pull_top500.py`). After it appears, claim
ownership via Glama's dashboard to moderate the listing.

## 4. mcp.so + PulseMCP

Submit/claim via each site's own form, metadata pack above.

## 5. awesome-mcp-servers (GitHub PR to `punkpeye/awesome-mcp-servers`)

**Reality check (2026-08-21):** `gtm.md` describes the Security category as
"nearly empty" — that was true 2026-07-13 but is stale now; the section has
grown to 20+ entries, several from adjacent trust/verification-for-agents
projects. Still worth submitting, just not "starting" the category — drop
that framing if referencing this PR anywhere else.

**PR body draft:**

```
Title: Add TETA+PI to Security

Adds TETA+PI, a trust/verification registry MCP server for AI agents
(verify people, businesses, and other MCP servers before an agent
transacts with them — C2PA + Bitcoin OpenTimestamps proof, not just a
claim). Remote server, no API key required.

- [x] Read the contribution guidelines
- [x] Verified the server works (tested with MCP Inspector against
      https://mcp.tetapi.dev/mcp, streamable-http transport)
- [x] Added to the correct category (Security)
- [x] Follows the existing entry format
```

**Entry line to insert** (alphabetical by repo owner within the Security
section — `github.com/teta-pi/mcp` sorts after `t`-prefixed entries, check
current file for exact neighbor at PR time):

```
- [teta-pi/mcp](https://github.com/teta-pi/mcp) 🎖️ 📇 ☁️ - Verify people, businesses, journalists, artists, and other MCP servers before your agent transacts with them — public proof pages backed by official registries, C2PA media provenance, and Bitcoin OpenTimestamps, not just a claim. No API key. Remote streamable-http at `https://mcp.tetapi.dev/mcp`.
```

## 6. GitHub MCP Registry (`github.com/mcp`)

Submit via GitHub's own registry submission flow once #1 (official registry)
is live — same metadata pack.

---

## Badge handoff (roadmap 1.10, done — prod-verified 2026-07-18)

`GET https://tetapi.dev/badge/{entity_id}` is live: cached SVG,
`Cache-Control`/`ETag` present, cheap counter, graceful "unknown" 404. Ready
to use as-is for:
- README badges on our own 4 repos (`gtm.md` §0.2, owner action)
- the badge line in `scripts/gtm/outreach_queue.py`'s message template
  (already wired — see `badge_url` in that script)

No further backend work needed for the badge loop itself; `1.11` (bulk
pre-verification import) is the remaining gap before badges can point at
real pre-verified entities instead of placeholders.

---

## What this packet does NOT cover

- Actual submissions — owner-executed, see `gtm.md` Ownership & Dependencies.
- Show HN / Discord posts / outreach messages — see `gtm-drafts.md`.
- Top-500 dataset + outreach queue tooling — see `scripts/gtm/README.md`.
- Claude connectors directory icon asset — design gap, not scripted here.
