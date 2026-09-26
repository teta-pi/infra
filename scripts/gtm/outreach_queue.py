#!/usr/bin/env python3
"""GTM 13.2/13.4 — Phase 2 outreach queue, owner-approval gated.

Turns the top-500 dataset (scripts/gtm/pull_top500.py) into a queue of
per-server outreach messages using the exact guardrail template from
docs/gtm-drafts.md §3. This tool never sends anything — it only prepares a
reviewable queue. Every item starts as "draft" and must be flipped to
"approved" one at a time before Bob sends it himself (GitHub issue or
email, per docs/gtm.md Phase 2).

`build` now creates the real pre-verified profiles behind those links, via
POST /admin/entities/bulk-preverify (roadmap 1.11, live since 2026-09-11 —
see docs/known-issues.md). That is a WRITE against prod, so `build` is
dry-run by default: it shows exactly what would be created and writes a
queue with links_are_placeholders=true, but calls nothing. Pass --create to
actually POST the batch and get real profile_url/opt_out_url/badge_url back.

Admin auth: a bearer token for a user with role admin/support (see
api/app/api/deps.py::require_admin — same Authorization: Bearer scheme as
every other endpoint, not a separate admin-key header). Read from the
TETAPI_ADMIN_KEY env var or --key-file; never hardcode or print it.

Usage:
    # see what would be created, without writing anything (default)
    python3 scripts/gtm/outreach_queue.py build \
        --dataset scripts/gtm/dataset/top500.json \
        --out scripts/gtm/dataset/outreach_queue.json

    # actually create the pre-verified profiles and build the queue from
    # the real links the API returns
    TETAPI_ADMIN_KEY=... python3 scripts/gtm/outreach_queue.py build \
        --dataset scripts/gtm/dataset/top500.json \
        --out scripts/gtm/dataset/outreach_queue.json --create

    # list current queue with statuses
    python3 scripts/gtm/outreach_queue.py list --queue scripts/gtm/dataset/outreach_queue.json

    # approve exactly one item after manual review (owner-only step).
    # Refuses if links are still placeholders, or if profile_url/badge_url/
    # opt_out_url don't currently answer 200 (catches domain regressions
    # like 1.23 automatically).
    python3 scripts/gtm/outreach_queue.py approve --queue scripts/gtm/dataset/outreach_queue.json --id <server_id>

    # manual cleanup of a test/mistaken entry — calls the real opt-out
    # endpoint (same one the /e/{slug}/opt-out page's button calls), not
    # the page. Only for undoing our own test writes; a real recipient
    # opts out through the page link, never through this command.
    python3 scripts/gtm/outreach_queue.py optout --business-id <id> --token <opt_out_token>
"""
import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

TEMPLATE = """Subject: Your MCP server has a pre-verified profile on TETA+PI

Hi {author},

We found and attested your public data — take control of it.

TETA+PI (tetapi.dev) is a verification registry for AI agents to check
who/what they're talking to. We pulled {server_name}'s public metadata
(GitHub org, domain, npm package — nothing private, nothing you haven't
already published) and created a pre-verified profile:

  {profile_url}

The page is labeled "Pre-verified · Unclaimed" — we're not claiming to
have verified or registered you, just attesting what's already public,
timestamped. Claiming the profile is free and takes under a minute; once
claimed you get a verified badge for your README ({badge_url}) and basic
analytics on which agents are checking you out.

If you'd rather this didn't exist, one click removes it — no form, no
waiting: {opt_out_url}

This is a one-time message — we won't follow up.

— Bob, TETA+PI"""

API_BASE = os.environ.get("TETAPI_API_BASE", "https://api.tetapi.dev")
BULK_PREVERIFY_URL = f"{API_BASE}/api/v1/admin/entities/bulk-preverify"
OPT_OUT_URL_FMT = f"{API_BASE}/api/v1/businesses/{{business_id}}/opt-out"
UA = "tetapi-gtm-outreach/1.0 (+https://tetapi.dev)"
TIMEOUT = 20.0
# BulkPreverifyRequest.items caps at 200 server-side (api/app/api/routes/admin.py)
BATCH_SIZE = 200


def _slug(name: str) -> str:
    """Local queue-item id only — NOT what the server uses for the entity
    slug (see _server_slugify below, which must match admin.py exactly so
    created[] rows can be matched back to their source dataset row)."""
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "unknown"


def _server_slugify(name: str) -> str:
    """Mirrors api/app/api/routes/businesses.py::_slugify verbatim — the
    server's response doesn't echo back the item's name, only its slug, so
    this is how we re-associate a created/skipped row with its source item."""
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug[:80]


def _admin_key(args) -> str:
    if args.key_file:
        with open(args.key_file) as f:
            key = f.read().strip()
    else:
        key = os.environ.get("TETAPI_ADMIN_KEY", "").strip()
    if not key:
        raise SystemExit(
            "admin key required for --create: set TETAPI_ADMIN_KEY or pass "
            "--key-file (a bearer token for a user with role admin/support — "
            "never hardcode or print it)"
        )
    return key


def _post_json(url: str, body: dict, key: str) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise SystemExit(f"POST {url} -> {e.code}: {detail}")
    except urllib.error.URLError as e:
        raise SystemExit(f"POST {url} -> unreachable: {e}")


def _url_status(url: str, method: str = "GET") -> int | None:
    req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except urllib.error.URLError:
        return None


def _domain_from_website(website: str | None) -> str | None:
    if not website:
        return None
    netloc = urllib.parse.urlparse(website).netloc
    if not netloc:
        netloc = urllib.parse.urlparse("//" + website).netloc
    netloc = netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc or None


def _github_org_from_repo(repo: str | None) -> str | None:
    if not repo or "github.com" not in repo:
        return None
    parts = [p for p in urllib.parse.urlparse(repo).path.split("/") if p]
    return parts[0] if parts else None


def _row_to_item(row: dict) -> dict:
    server_name = row.get("title") or row.get("name") or row.get("repo") or "unknown"
    return {
        "name": server_name[:255],
        "entity_type": "mcp_server",
        "description": row.get("description") or None,
        "domain": _domain_from_website(row.get("website")),
        "github_org": _github_org_from_repo(row.get("repo")),
        # dataset (pull_top500.py) doesn't populate this today; pass through
        # if a future dataset version adds it, so no anchor is left unused.
        "npm_package": row.get("npm_package"),
    }


def _author_for(row: dict) -> str:
    repo = row.get("repo")
    return row.get("namespace") or (repo.split("/")[-2] if repo else None) or "there"


def cmd_build(args):
    with open(args.dataset) as f:
        dataset = json.load(f)
    rows = dataset.get("servers", [])
    if args.limit:
        rows = rows[: args.limit]

    pending, skipped_no_anchor = [], []
    for row in rows:
        item = _row_to_item(row)
        if not (item["domain"] or item["github_org"] or item["npm_package"]):
            skipped_no_anchor.append({"name": item["name"], "repo": row.get("repo")})
            continue
        pending.append((row, item))

    if not args.create:
        print(
            f"[dry-run] would submit {len(pending)} item(s) to {BULK_PREVERIFY_URL} "
            f"in batch(es) of up to {BATCH_SIZE}; {len(skipped_no_anchor)} skipped "
            "locally (no public anchor: domain/github_org/npm_package all empty). "
            "Nothing was written. Re-run with --create to actually create these."
        )
        queue = []
        for row, item in pending:
            sid = _slug(row.get("repo") or item["name"])
            print(f"  would create: {item['name']!r} "
                  f"(domain={item['domain']!r}, github_org={item['github_org']!r}, "
                  f"npm_package={item['npm_package']!r})")
            queue.append({
                "id": sid,
                "server_name": item["name"],
                "repo": row.get("repo"),
                "channel": "github_issue" if row.get("repo") else "email",
                "status": "draft",
                "links_are_placeholders": True,
                "pending_item": item,
                "message": None,
            })
        with open(args.out, "w") as f:
            json.dump({
                "generated_from": args.dataset,
                "dry_run": True,
                "count": len(queue),
                "skipped_no_anchor": skipped_no_anchor,
                "items": queue,
            }, f, indent=2)
        print(f"wrote {len(queue)} draft item(s) to {args.out} (dry run — "
              "links_are_placeholders=true, approve will refuse all of them)")
        return

    key = _admin_key(args)
    slug_to_row = {_server_slugify(item["name"]): (row, item) for row, item in pending}

    created_rows, skipped_rows = [], []
    for i in range(0, len(pending), BATCH_SIZE):
        batch = pending[i : i + BATCH_SIZE]
        resp = _post_json(BULK_PREVERIFY_URL, {"items": [item for _, item in batch]}, key)
        created_rows.extend(resp.get("created", []))
        skipped_rows.extend(resp.get("skipped", []))

    queue = []
    for c in created_rows:
        match = slug_to_row.get(c.get("slug", ""))
        if not match:
            print(f"WARNING: created {c.get('business_id')} (slug={c.get('slug')}) "
                  "didn't match any source row by slug — including with a generic message", file=sys.stderr)
            row, item = {}, {"name": c.get("slug", "unknown")}
        else:
            row, item = match
        server_name, repo = item["name"], row.get("repo")
        message = TEMPLATE.format(
            author=_author_for(row), server_name=server_name,
            profile_url=c["profile_url"], opt_out_url=c["opt_out_url"], badge_url=c["badge_url"],
        )
        sid = _slug(repo or server_name)
        queue.append({
            "id": sid,
            "server_name": server_name,
            "repo": repo,
            "channel": "github_issue" if repo else "email",
            "status": "draft",
            "links_are_placeholders": False,
            "business_id": c["business_id"],
            "links": {
                "profile_url": c["profile_url"],
                "opt_out_url": c["opt_out_url"],
                "badge_url": c["badge_url"],
            },
            "message": message,
        })

    with open(args.out, "w") as f:
        json.dump({
            "generated_from": args.dataset,
            "dry_run": False,
            "count": len(queue),
            "skipped_no_anchor": skipped_no_anchor,
            "skipped_by_api": skipped_rows,
            "items": queue,
        }, f, indent=2)
    print(f"created {len(queue)} real pre-verified profile(s), wrote queue to {args.out}")
    if skipped_rows:
        print(f"{len(skipped_rows)} item(s) skipped by the API (not silent — see "
              f"'skipped_by_api' in {args.out}):")
        for s in skipped_rows:
            print(f"  {s.get('name')!r}: {s.get('reason')}")
    if skipped_no_anchor:
        print(f"{len(skipped_no_anchor)} item(s) skipped locally, no public anchor "
              f"(see 'skipped_no_anchor' in {args.out})")


def cmd_list(args):
    with open(args.queue) as f:
        queue = json.load(f)
    for item in queue["items"]:
        flag = " [PLACEHOLDER LINKS]" if item.get("links_are_placeholders") else ""
        print(f"{item['id']:40s} {item['status']:10s} {item['channel']:12s}{flag}  {item['server_name']}")


def cmd_approve(args):
    with open(args.queue) as f:
        queue = json.load(f)
    for item in queue["items"]:
        if item["id"] != args.id:
            continue
        if item.get("links_are_placeholders"):
            raise SystemExit(
                f"refusing to approve {args.id}: links are still placeholders "
                "(run `build --create` for this dataset first)"
            )
        links = item.get("links") or {}
        profile_url, opt_out_url, badge_url = (
            links.get("profile_url"), links.get("opt_out_url"), links.get("badge_url"),
        )
        if not (profile_url and opt_out_url and badge_url):
            raise SystemExit(f"refusing to approve {args.id}: queue item is missing one or more real links")

        # Live check, not just "were links minted once" — catches a domain
        # regression (like 1.23's original placeholder-domain bug) between
        # build time and approve time. opt_out_url is GET-only: that's the
        # frontend page, never the POST that actually opts the profile out.
        problems = []
        for label, url in (("profile_url", profile_url), ("badge_url", badge_url), ("opt_out_url", opt_out_url)):
            status = _url_status(url, "GET")
            if status != 200:
                problems.append(f"{label} ({url}) -> {status if status is not None else 'unreachable'}")
        if problems:
            raise SystemExit(
                f"refusing to approve {args.id}: link check failed:\n  " + "\n  ".join(problems)
            )

        item["status"] = "approved"
        with open(args.queue, "w") as f:
            json.dump(queue, f, indent=2)
        print(f"approved {args.id} — Bob sends this one manually, no further automation")
        return
    raise SystemExit(f"no item with id {args.id}")


def cmd_optout(args):
    """Manual cleanup only (e.g. removing a test row created while
    verifying this script). A real recipient opts out through the
    /e/{slug}/opt-out page's button, never through this command."""
    url = f"{OPT_OUT_URL_FMT.format(business_id=args.business_id)}?{urllib.parse.urlencode({'token': args.token})}"
    req = urllib.request.Request(url, method="POST", data=b"", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            print(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"POST {url} -> {e.code}: {e.read().decode(errors='replace')}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--dataset", required=True)
    b.add_argument("--out", required=True)
    b.add_argument("--limit", type=int, default=None, help="only process the first N dataset rows (testing)")
    b.add_argument("--create", action="store_true",
                    help="actually POST to bulk-preverify and mint real profiles (default: dry-run)")
    b.add_argument("--key-file", default=None, help="file containing the admin bearer token; else TETAPI_ADMIN_KEY env var")
    b.set_defaults(func=cmd_build)

    l = sub.add_parser("list")
    l.add_argument("--queue", required=True)
    l.set_defaults(func=cmd_list)

    a = sub.add_parser("approve")
    a.add_argument("--queue", required=True)
    a.add_argument("--id", required=True)
    a.set_defaults(func=cmd_approve)

    o = sub.add_parser("optout")
    o.add_argument("--business-id", required=True)
    o.add_argument("--token", required=True)
    o.set_defaults(func=cmd_optout)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
