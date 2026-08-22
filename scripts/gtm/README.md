# GTM scripts (roadmap 13.2)

Off-server tooling for `docs/gtm.md` Phase 1/2. Nothing here touches
`api.tetapi.dev`, the droplet, or prod DB — read-only HTTP to public APIs,
local JSON output only. No script here sends, posts, or publishes anything;
every external action stays owner-gated per `CLAUDE.md`.

Requires Python 3.9+, stdlib only (no `pip install` needed). If you hit
`CERTIFICATE_VERIFY_FAILED` on macOS with a python.org install, run
`/Applications/Python 3.x/Install Certificates.command` once, or export
`SSL_CERT_FILE=$(python3 -m certifi)` (needs `pip install certifi`).

## `pull_top500.py` — top-500 dataset (gtm.md Phase 1 §1.4, roadmap 13.3)

Pulls the official MCP registry (`registry.modelcontextprotocol.io/v0/servers`)
and Glama (`glama.ai/api/mcp/v1/servers`) public APIs, merges by repo URL,
writes a local JSON dataset.

```bash
python3 scripts/gtm/pull_top500.py --limit 500 --out scripts/gtm/dataset/top500.json
```

Output is `.gitignore`d (`scripts/gtm/dataset/`) — it's a working dataset,
not something to commit; re-run any time for a fresh pull.

## `outreach_queue.py` — Phase 2 outreach queue, owner-approval gated

Builds a review queue from the dataset above, using the exact guardrail
template from `docs/gtm-drafts.md` §3 (public data only, instant opt-out,
one message, no follow-up). Every item starts `status: draft`.

```bash
# build
python3 scripts/gtm/outreach_queue.py build \
  --dataset scripts/gtm/dataset/top500.json \
  --out scripts/gtm/dataset/outreach_queue.json

# review
python3 scripts/gtm/outreach_queue.py list --queue scripts/gtm/dataset/outreach_queue.json

# approve one item after manual review (Bob sends it himself — this tool
# never sends anything)
python3 scripts/gtm/outreach_queue.py approve --queue scripts/gtm/dataset/outreach_queue.json --id <id>
```

**Hard gate:** every item's `profile_url` / `opt_out_url` / `badge_url` are
placeholders until roadmap **1.11** (bulk pre-verification import) ships
real entity profiles — `approve` refuses any item still flagged
`links_are_placeholders: true`. Do not hand-edit that flag; fix it by
re-running `build` once 1.11's real links are wired in.
