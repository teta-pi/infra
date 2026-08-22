#!/usr/bin/env python3
"""GTM 13.2 / roadmap 13.1 §1.4 — top-500 MCP server dataset.

Pulls public server listings from the official MCP registry and Glama,
merges them by repository URL, and writes a local JSON dataset for Phase 2
pre-verification. Read-only HTTP calls to public APIs only — does not touch
api.tetapi.dev or any TETA+PI infrastructure. Safe to run from a laptop.

Usage:
    python3 scripts/gtm/pull_top500.py [--limit 500] [--out dataset.json]
"""
import argparse
import json
import time
import urllib.error
import urllib.parse
import urllib.request

REGISTRY_URL = "https://registry.modelcontextprotocol.io/v0/servers"
GLAMA_URL = "https://glama.ai/api/mcp/v1/servers"
UA = "tetapi-gtm-dataset/1.0 (+https://tetapi.dev)"


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read())


def pull_registry(limit: int) -> dict[str, dict]:
    """Official MCP registry, keyed by repo URL. Paginates via cursor."""
    out: dict[str, dict] = {}
    cursor = None
    while len(out) < limit:
        url = f"{REGISTRY_URL}?limit=100"
        if cursor:
            url += f"&cursor={urllib.parse.quote(cursor)}"
        try:
            data = _get(url)
        except urllib.error.URLError as e:
            print(f"registry: fetch failed ({e}), stopping pagination")
            break
        for entry in data.get("servers", []):
            server = entry.get("server", {})
            repo = (server.get("repository") or {}).get("url")
            key = repo or server.get("name")
            if not key or key in out:
                continue
            out[key] = {
                "source": "official_registry",
                "name": server.get("name"),
                "title": server.get("title"),
                "description": server.get("description"),
                "repo": repo,
                "website": server.get("websiteUrl"),
            }
        cursor = data.get("metadata", {}).get("nextCursor")
        if not cursor or not data.get("servers"):
            break
        time.sleep(0.2)
    return out


def pull_glama(limit: int) -> dict[str, dict]:
    """Glama public listing, keyed by repo URL. Paginates via GraphQL-style cursor."""
    out: dict[str, dict] = {}
    after = None
    while len(out) < limit:
        url = f"{GLAMA_URL}?first=100"
        if after:
            url += f"&after={after}"
        try:
            data = _get(url)
        except urllib.error.URLError as e:
            print(f"glama: fetch failed ({e}), stopping pagination")
            break
        for server in data.get("servers", []):
            repo = (server.get("repository") or {}).get("url")
            key = repo or server.get("slug")
            if not key or key in out:
                continue
            out[key] = {
                "source": "glama",
                "name": server.get("name"),
                "namespace": server.get("namespace"),
                "description": server.get("description"),
                "repo": repo,
                "glama_url": server.get("url"),
                "license": (server.get("spdxLicense") or {}).get("name"),
            }
        page = data.get("pageInfo", {})
        after = page.get("endCursor")
        if not page.get("hasNextPage") or not after:
            break
        time.sleep(0.2)
    return out


def merge(registry: dict, glama: dict) -> list[dict]:
    keys = list(dict.fromkeys(list(registry.keys()) + list(glama.keys())))
    merged = []
    for k in keys:
        r, g = registry.get(k), glama.get(k)
        row = {**(g or {}), **(r or {})}
        row["repo"] = k if k.startswith("http") else row.get("repo")
        row["in_official_registry"] = r is not None
        row["in_glama"] = g is not None
        merged.append(row)
    return merged


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--out", default="scripts/gtm/dataset/top500.json")
    args = ap.parse_args()

    print(f"pulling official registry (limit {args.limit})...")
    registry = pull_registry(args.limit)
    print(f"  {len(registry)} servers")

    print(f"pulling glama (limit {args.limit})...")
    glama = pull_glama(args.limit)
    print(f"  {len(glama)} servers")

    merged = merge(registry, glama)[: args.limit]
    print(f"merged: {len(merged)} unique servers "
          f"({sum(1 for r in merged if r['in_official_registry'] and r['in_glama'])} in both)")

    import os
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump({"pulled_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "count": len(merged), "servers": merged}, f, indent=2)
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
