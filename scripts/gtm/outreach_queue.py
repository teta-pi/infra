#!/usr/bin/env python3
"""GTM 13.2 — Phase 2 outreach queue, owner-approval gated.

Turns the top-500 dataset (scripts/gtm/pull_top500.py) into a queue of
per-server outreach messages using the exact guardrail template from
docs/gtm-drafts.md §3. This tool never sends anything — it only prepares a
reviewable queue. Every item starts as "draft" and must be flipped to
"approved" one at a time before Bob sends it himself (GitHub issue or
email, per docs/gtm.md Phase 2).

Hard dependency: real profile_url / opt_out_url links require roadmap 1.11
(bulk pre-verification import) to exist first — until then this queue is
built with placeholder links and status stays "draft" (never "approved").

Usage:
    # build the queue from a dataset pulled by pull_top500.py
    python3 scripts/gtm/outreach_queue.py build \
        --dataset scripts/gtm/dataset/top500.json \
        --out scripts/gtm/dataset/outreach_queue.json

    # list current queue with statuses
    python3 scripts/gtm/outreach_queue.py list --queue scripts/gtm/dataset/outreach_queue.json

    # approve exactly one item after manual review (owner-only step)
    python3 scripts/gtm/outreach_queue.py approve --queue scripts/gtm/dataset/outreach_queue.json --id <server_id>
"""
import argparse
import json
import re

TEMPLATE = """Subject: Your MCP server has a pre-verified profile on TETA+PI

Hi {author},

We found and attested your public data — take control of it.

TETA+PI (tetapi.dev) is a verification registry for AI agents to check
who/what they're talking to. We pulled {server_name}'s public metadata
(GitHub org, domain, npm package — nothing private, nothing you haven't
already published) and created a pre-verified profile:

  {profile_url}

This is not us claiming to have registered you or speak for you — it's a
snapshot of what's already public, timestamped and attested. Claiming the
profile is free and takes under a minute; once claimed you get a verified
badge for your README ({badge_url}) and basic analytics on which agents
are checking you out.

If you'd rather this didn't exist, one click removes it — no form, no
waiting: {opt_out_url}

This is a one-time message — we won't follow up.

— Bob, TETA+PI"""


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-") or "unknown"


def cmd_build(args):
    with open(args.dataset) as f:
        dataset = json.load(f)

    queue = []
    for row in dataset.get("servers", []):
        server_name = row.get("title") or row.get("name") or row.get("repo") or "your server"
        repo = row.get("repo")
        author = (row.get("namespace") or (repo.split("/")[-2] if repo else None)
                  or "there")
        sid = _slug(row.get("repo") or row.get("name") or server_name)
        # placeholders — real values need 1.11 (bulk pre-verification import)
        profile_url = f"https://tetapi.dev/e/PLACEHOLDER-{sid}"
        opt_out_url = f"https://tetapi.dev/e/PLACEHOLDER-{sid}/opt-out"
        badge_url = f"https://tetapi.dev/badge/PLACEHOLDER-{sid}"
        message = TEMPLATE.format(
            author=author, server_name=server_name, profile_url=profile_url,
            opt_out_url=opt_out_url, badge_url=badge_url,
        )
        queue.append({
            "id": sid,
            "server_name": server_name,
            "repo": repo,
            "channel": "github_issue" if repo else "email",
            "status": "draft",  # draft -> approved -> sent (sent is set manually by Bob, out of scope here)
            "links_are_placeholders": True,  # flips to False once 1.11 exists and links are real
            "message": message,
        })

    with open(args.out, "w") as f:
        json.dump({"generated_from": args.dataset, "count": len(queue), "items": queue}, f, indent=2)
    print(f"wrote {len(queue)} draft outreach items to {args.out}")
    print("NOTE: profile_url/opt_out_url/badge_url are placeholders until roadmap "
          "1.11 (bulk pre-verification import) ships real entity profiles. "
          "Do not approve or send any item with links_are_placeholders=true.")


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
        if item["id"] == args.id:
            if item.get("links_are_placeholders"):
                raise SystemExit(
                    f"refusing to approve {args.id}: links are still placeholders "
                    "(needs roadmap 1.11 bulk pre-verification import first)"
                )
            item["status"] = "approved"
            with open(args.queue, "w") as f:
                json.dump(queue, f, indent=2)
            print(f"approved {args.id} — Bob sends this one manually, no further automation")
            return
    raise SystemExit(f"no item with id {args.id}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    b = sub.add_parser("build")
    b.add_argument("--dataset", required=True)
    b.add_argument("--out", required=True)
    b.set_defaults(func=cmd_build)

    l = sub.add_parser("list")
    l.add_argument("--queue", required=True)
    l.set_defaults(func=cmd_list)

    a = sub.add_parser("approve")
    a.add_argument("--queue", required=True)
    a.add_argument("--id", required=True)
    a.set_defaults(func=cmd_approve)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
