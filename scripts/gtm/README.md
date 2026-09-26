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

**`build` creates real pre-verified profiles** (roadmap 1.11,
`POST /admin/entities/bulk-preverify`, live since 2026-09-11) and takes
their real `profile_url`/`opt_out_url`/`badge_url` into the queue — this is
a write against prod, so `build` is **dry-run by default**: it prints and
records what *would* be created, calls nothing, and the queue it writes has
`links_are_placeholders: true` everywhere. Pass `--create` to actually POST
the batch (≤200 items per call, the server's own limit — the script chunks
automatically) and get real links back.

```bash
# see what would be created, writes nothing (default)
python3 scripts/gtm/outreach_queue.py build \
  --dataset scripts/gtm/dataset/top500.json \
  --out scripts/gtm/dataset/outreach_queue.json

# actually create the profiles and build the queue from real links.
# TETAPI_ADMIN_KEY is a bearer token for a user with role admin/support
# (same Authorization: Bearer scheme as everywhere else — not a separate
# admin-key header). --key-file works instead of the env var. Never
# hardcode or paste this key into chat/commits.
TETAPI_ADMIN_KEY=... python3 scripts/gtm/outreach_queue.py build \
  --dataset scripts/gtm/dataset/top500.json \
  --out scripts/gtm/dataset/outreach_queue.json --create

# --limit N restricts to the first N dataset rows — use it to test on a
# handful of records before running against the full dataset.

# review
python3 scripts/gtm/outreach_queue.py list --queue scripts/gtm/dataset/outreach_queue.json

# approve one item after manual review (Bob sends it himself — this tool
# never sends anything). Refuses if links are still placeholders, AND
# live-checks profile_url/badge_url/opt_out_url (GET only, never the
# opt-out POST) return 200 before approving — catches a domain regression
# (like 1.23's original placeholder-domain bug) automatically.
python3 scripts/gtm/outreach_queue.py approve --queue scripts/gtm/dataset/outreach_queue.json --id <id>

# manual cleanup of a test/mistaken row via the real opt-out endpoint
# (not the page — this calls POST /businesses/{id}/opt-out?token=… directly,
# same call the page's button makes). Only for undoing our own test writes.
python3 scripts/gtm/outreach_queue.py optout --business-id <id> --token <opt_out_token>
```

A dataset row needs at least one public anchor (`domain`, parsed from the
registry's `website` field; `github_org`, parsed from the `repo` GitHub URL;
or `npm_package`, not populated by `pull_top500.py` today) — rows without
one are skipped locally and reported in the queue JSON's
`skipped_no_anchor`, never silently dropped. Rows the API itself skips
(mainly: slug already exists — e.g. a previous run already created it) land
in `skipped_by_api` with the server's own reason string.

**Hard gate unchanged:** `approve` refuses any item still flagged
`links_are_placeholders: true`. Do not hand-edit that flag or the `links`
object — re-run `build --create` instead.
