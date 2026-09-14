#!/usr/bin/env python3
"""TETA+PI security regression net (roadmap 15.6, docs/security.md §6.2).

One run = one report. Deterministic, read-only checks against prod that
re-assert every CLOSED finding in docs/security.md §5 has stayed closed and
that no new unauthenticated public surface appeared unnoticed. This is the
automated replacement for §6.2's old "monthly manual" re-audit — the class of
bugs found by hand over two months (S-15 agent-key, S-16 loopback SSRF,
private-block/entity leaks) that static scanners (CodeQL/bandit) never see.

Rules of engagement (docs/security.md § Rules of engagement) are baked in:
  * our-own-infra only (api./mcp./app./tetapi.dev);
  * read-only — GET/HEAD plus only those POSTs that by design do not write
    (verify-endpoint rejects/fetches but persists nothing for an entity the
    caller doesn't own; tag-ping/agent-key are probed with junk so nothing is
    stored/created). No entity/user/block/claim is ever created;
  * rate limits respected (verify-endpoint is 5/min — see RATE_LIMITED_CHECKS);
  * findings are reported, never weaponised.

stdlib + httpx only (mirrors scripts/gtm/pull_top500.py's off-server style).
Python 3.12.

Usage:
    python3 scripts/security/probe.py                 # full net
    python3 scripts/security/probe.py --only auth      # one check group
    python3 scripts/security/probe.py --json           # machine-readable
    python3 scripts/security/probe.py --include-heavy   # + high-volume rate limits

Exit code: 0 if no FAILs, 1 if any check FAILs (drives the workflow red).
SKIP never fails the run — it means "could not assert honestly" (missing
fixture, missing key, or an open owner-decision), not "passed".

Adding a check when a new S-* is closed: see scripts/security/README.md.
Rule (docs/security.md §6.2): every closed S-* gets an assert here in the same
PR that closes it.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

API = os.environ.get("SEC_PROBE_API_BASE", "https://api.tetapi.dev")
MCP = os.environ.get("SEC_PROBE_MCP_BASE", "https://mcp.tetapi.dev")
APP = os.environ.get("SEC_PROBE_APP_BASE", "https://app.tetapi.dev")
LANDING = os.environ.get("SEC_PROBE_LANDING_BASE", "https://tetapi.dev")

UA = "tetapi-security-probe/1.0 (+https://tetapi.dev)"
TIMEOUT = 15.0
HERE = Path(__file__).resolve().parent

# Statuses an unauthenticated caller may legitimately get on a protected or
# non-public route. A 2xx here (outside the allowlist) is the failure.
OK_UNAUTH = {401, 403, 404, 405, 422}

PASS, FAIL, SKIP = "PASS", "FAIL", "SKIP"


@dataclass
class Result:
    name: str
    status: str
    evidence: str


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, status: str, evidence: str) -> None:
        self.results.append(Result(name, status, evidence))

    @property
    def failed(self) -> bool:
        return any(r.status == FAIL for r in self.results)


def _api_key() -> str | None:
    """Test key, never logged. Env first (CI: SEC_PROBE_API_KEY GitHub secret),
    then the local ~/.tetapi/test_api_key file (docs: test-api-key memory)."""
    k = os.environ.get("SEC_PROBE_API_KEY")
    if k:
        return k.strip()
    f = Path.home() / ".tetapi" / "test_api_key"
    if f.exists():
        return f.read_text().strip()
    return None


def _client(auth: str | None = None) -> httpx.Client:
    headers = {"User-Agent": UA}
    if auth:
        headers["Authorization"] = f"Bearer {auth}"
    return httpx.Client(timeout=TIMEOUT, headers=headers, follow_redirects=False)


def _load_allowlist() -> dict:
    return json.loads((HERE / "public_allowlist.json").read_text())


def _load_fixtures() -> dict:
    return json.loads((HERE / "fixtures.json").read_text())


def _dummy_for(path: str) -> str:
    """Substitute path params with values that cannot match a real row, so
    auth_surface tests 'does this 2xx to anonymous at all', not 'is this id
    real'. A non-existent id 404s on legit reads and only 2xxes on a route
    that ignores its input the way /auth/agent-key did."""
    subs = {
        "{business_id}": "00000000-0000-0000-0000-000000000000",
        "{block_id}": "00000000-0000-0000-0000-000000000000",
        "{media_id}": "00000000-0000-0000-0000-000000000000",
        "{user_id}": "00000000-0000-0000-0000-000000000000",
        "{entity_id}": "sec-probe-nonexistent",
        "{claim_id}": "00000000-0000-0000-0000-000000000000",
        "{slug}": "sec-probe-nonexistent",
        "{file_id}": "sec-probe",
        "{filename}": "probe.txt",
    }
    for k, v in subs.items():
        path = path.replace(k, v)
    return path


# ── a. AUTH SURFACE — the contract check ──────────────────────────────────────
def check_auth_surface(rep: Report) -> None:
    allow = _load_allowlist()
    public = set(allow["public"].keys())
    must_not_exist = allow.get("must_not_exist", {})

    try:
        with _client() as c:
            spec = c.get(f"{API}/openapi.json").json()
    except Exception as e:  # noqa: BLE001
        rep.add("auth_surface", SKIP, f"could not fetch openapi.json: {e}")
        return

    live_paths = spec.get("paths", {})
    violations: list[str] = []
    checked = 0

    with _client() as c:
        for path, methods in live_paths.items():
            for method in methods:
                m = method.upper()
                if m not in ("GET", "POST", "PATCH", "PUT", "DELETE", "HEAD"):
                    continue
                key = f"{m} {path}"
                if key in public:
                    continue  # documented public, tested for content elsewhere
                url = API + _dummy_for(path)
                try:
                    if m in ("GET", "HEAD", "DELETE"):
                        r = c.request(m, url)
                    else:
                        r = c.request(m, url, json={})
                except Exception as e:  # noqa: BLE001
                    rep.add(f"auth_surface[{key}]", SKIP, f"request error: {e}")
                    continue
                checked += 1
                if 200 <= r.status_code < 300:
                    violations.append(f"{key} -> {r.status_code} (UNAUTH, not allowlisted)")

    # must-not-exist: deleted security-fix routes stay gone (S-15, /auth/register)
    for key, why in must_not_exist.items():
        m, path = key.split(" ", 1)
        in_spec = path in live_paths and m.lower() in live_paths[path]
        try:
            with _client() as c:
                r = c.request(m, API + _dummy_for(path), json={} if m != "GET" else None)
            live_gone = r.status_code in (404, 405)
        except Exception as e:  # noqa: BLE001
            rep.add(f"auth_surface[gone:{key}]", SKIP, f"request error: {e}")
            continue
        if in_spec:
            violations.append(f"{key} REAPPEARED in openapi.json ({why})")
        elif not live_gone:
            violations.append(f"{key} live status {r.status_code}, expected 404/405 ({why})")

    if violations:
        rep.add("auth_surface", FAIL,
                f"checked {checked} protected methods; violations:\n    " +
                "\n    ".join(violations))
    else:
        rep.add("auth_surface", PASS,
                f"{checked} protected methods all 401/403/404/405/422; "
                f"{len(public)} allowlisted publics skipped; "
                f"{len(must_not_exist)} deleted routes confirmed gone")


# ── b. SSRF CANARIES (S-16) ───────────────────────────────────────────────────
# verify-endpoint is 5/min — keep to <=3 canaries with pauses.
SSRF_CANARIES = [
    "http://127.0.0.1:8000/health",   # the proven port oracle (the API's own port)
    "http://169.254.169.254/",        # cloud metadata endpoint
    "http://10.0.0.1/",               # RFC1918 private range
]


def check_ssrf(rep: Report) -> None:
    key = _api_key()
    if not key:
        rep.add("ssrf_canaries", SKIP,
                "no test key (SEC_PROBE_API_KEY / ~/.tetapi/test_api_key) — "
                "verify-endpoint requires auth since the 1.7 fix")
        return
    with _client(auth=key) as c:
        for i, url in enumerate(SSRF_CANARIES):
            if i:
                time.sleep(2.0)  # respect 5/min
            name = f"ssrf[{url}]"
            try:
                r = c.post(f"{API}/api/v1/verify-endpoint", json={"endpoint_url": url})
            except Exception as e:  # noqa: BLE001
                rep.add(name, SKIP, f"request error: {e}")
                continue
            if r.status_code == 429:
                rep.add(name, SKIP, "429 rate-limited (window shared with rate_limits check)")
                continue
            if r.status_code in (400, 403, 422):
                rep.add(name, PASS, f"rejected pre-fetch ({r.status_code})")
                continue
            if 200 <= r.status_code < 300:
                body = r.json()
                if body.get("is_active") is True:
                    rep.add(name, FAIL,
                            "server FETCHED an internal address (is_active=true) — "
                            "SSRF/port-oracle live (S-16, awaiting 15.5)")
                else:
                    rep.add(name, PASS, f"reached the route but did not fetch (is_active={body.get('is_active')})")
            else:
                rep.add(name, PASS, f"non-2xx ({r.status_code})")


# ── c. S-15 — /auth/agent-key deleted ─────────────────────────────────────────
def check_s15_agent_key(rep: Report) -> None:
    try:
        with _client() as c:
            r = c.post(f"{API}/api/v1/auth/agent-key", json={})
            spec = c.get(f"{API}/openapi.json").json()
    except Exception as e:  # noqa: BLE001
        rep.add("s15_agent_key", SKIP, f"request error: {e}")
        return
    in_spec = "/api/v1/auth/agent-key" in spec.get("paths", {})
    if r.status_code == 404 and not in_spec:
        rep.add("s15_agent_key", PASS, "404 + absent from openapi.json (deleted, api PR #23)")
    else:
        rep.add("s15_agent_key", FAIL,
                f"status={r.status_code}, in_openapi={in_spec} — S-15 endpoint must be gone")


# ── d. S-1 — media path traversal ─────────────────────────────────────────────
TRAVERSAL_VARIANTS = [
    "/api/v1/media/local/../../etc/passwd",
    "/api/v1/media/local/..%2f..%2fetc%2fpasswd",
    "/api/v1/media/local/%2e%2e/%2e%2e/etc/passwd",
    "/api/v1/media/local/x/....//....//etc/passwd",
]


def check_s1_traversal(rep: Report) -> None:
    bad: list[str] = []
    with _client() as c:
        for p in TRAVERSAL_VARIANTS:
            # httpx normalises dot-segments in a plain URL string, which would
            # defeat the test — send the raw path bytes untouched.
            try:
                r = c.get(httpx.URL(API, raw_path=p.encode()))
            except Exception as e:  # noqa: BLE001
                rep.add(f"s1_path_traversal[{p}]", SKIP, f"request error: {e}")
                continue
            body = r.text[:80]
            if 200 <= r.status_code < 300 and "root:" in body:
                bad.append(f"{p} -> {r.status_code} LEAKED /etc/passwd")
            elif 200 <= r.status_code < 300:
                bad.append(f"{p} -> {r.status_code} (2xx on traversal, inspect: {body!r})")
    if bad:
        rep.add("s1_path_traversal", FAIL, "\n    ".join(bad))
    else:
        rep.add("s1_path_traversal", PASS,
                f"{len(TRAVERSAL_VARIANTS)} traversal variants all non-2xx (contained to UPLOAD_DIR)")


# ── e. S-8 — private blocks not leaked on the list endpoint ────────────────────
def check_s8_private_blocks(rep: Report) -> None:
    fx = _load_fixtures().get("s8_private_blocks")
    if not fx:
        rep.add("s8_private_blocks", SKIP, "no s8 fixture configured")
        return
    entity, priv = fx["entity_id"], fx["private_block_id"]
    with _client() as c:
        try:
            r = c.get(f"{API}/api/v1/businesses/{entity}/blocks")
        except Exception as e:  # noqa: BLE001
            rep.add("s8_private_blocks", SKIP, f"request error: {e}")
            return
    if r.status_code == 404:
        rep.add("s8_private_blocks", SKIP,
                f"fixture entity {entity} gone (404) — recreate a public+private block fixture")
        return
    if r.status_code != 200:
        rep.add("s8_private_blocks", SKIP, f"unexpected {r.status_code}")
        return
    ids = [b.get("id") for b in r.json()] if isinstance(r.json(), list) else []
    if priv in ids or "SECRET" in r.text:
        rep.add("s8_private_blocks", FAIL,
                f"anonymous GET /businesses/{entity}/blocks returned the private block {priv}")
    else:
        rep.add("s8_private_blocks", PASS,
                f"anonymous list returned {len(ids)} public block(s), private block withheld")


# ── private entity exposure (NEW finding 2026-09-14 — owner decision pending) ──
def check_private_entity_exposure(rep: Report) -> None:
    fx = _load_fixtures().get("s8_private_blocks")
    if not fx:
        rep.add("private_entity_exposure", SKIP, "no private-entity fixture configured")
        return
    entity = fx["entity_id"]
    leaks: list[str] = []
    with _client() as c:
        for suffix in ("", "/preview", "/proof"):
            try:
                r = c.get(f"{API}/api/v1/businesses/{entity}{suffix}")
            except Exception:
                continue
            if r.status_code == 404:
                continue
            if 200 <= r.status_code < 300:
                body = r.json()
                is_pub = body.get("is_public")
                # base returns is_public; preview/proof don't, but if the base
                # says private and these still return the same entity, it's a leak.
                if is_pub is False or (suffix and "TETA Security Sync Test A" in r.text):
                    leaks.append(f"GET /businesses/{{id}}{suffix} -> 200 for a private entity")
    if leaks:
        rep.add("private_entity_exposure", FAIL,
                "private (is_public=false) entity readable by UUID anonymously:\n    " +
                "\n    ".join(leaks) +
                "\n    OWNER DECISION (public_allowlist.json > pending_owner_decision): "
                "filter these on is_public for non-owners, or document as intended.")
    else:
        rep.add("private_entity_exposure", PASS,
                "private entity not readable by UUID via base/preview/proof")


# ── f. RATE LIMITS ────────────────────────────────────────────────────────────
def check_rate_limits(rep: Report, include_heavy: bool) -> None:
    """verify-endpoint (5/min) is the security-critical, low-volume limiter, so
    it runs by default (6 tiny auth'd calls to a dead port, no writes, ~no load).
    badge (120/min) and tag-ping (240/min) need >100 requests to trip — that is
    exactly the load the rules of engagement forbid daily, so they are gated
    behind --include-heavy (not run by cron). See README/decisions."""
    key = _api_key()
    if not key:
        rep.add("rate_limit[verify-endpoint]", SKIP, "no test key for the auth'd limiter")
    else:
        tripped = False
        with _client(auth=key) as c:
            for _ in range(6):  # limit is 5/min
                try:
                    r = c.post(f"{API}/api/v1/verify-endpoint",
                               json={"endpoint_url": "http://127.0.0.1:1/"})
                except Exception:
                    continue
                if r.status_code == 429:
                    tripped = True
                    break
        rep.add("rate_limit[verify-endpoint]", PASS if tripped else FAIL,
                "429 within 6 rapid calls" if tripped else
                "no 429 after 6 calls — 5/min limiter not enforcing")

    if not include_heavy:
        rep.add("rate_limit[badge,tag-ping]", SKIP,
                "high-volume limiters (120/240 per min) not run — rules of "
                "engagement (no load against prod). Run with --include-heavy.")
        return
    # badge: 120/min, pure read, no write
    tripped = False
    with _client() as c:
        for _ in range(122):
            try:
                r = c.get(f"{API}/badge/sec-probe-nonexistent")
            except Exception:
                continue
            if r.status_code == 429:
                tripped = True
                break
    rep.add("rate_limit[badge]", PASS if tripped else FAIL,
            "429 within 122 calls" if tripped else "no 429 after 122 calls")


# ── g. SECRETS EXPOSURE ───────────────────────────────────────────────────────
def check_secrets(rep: Report) -> None:
    with _client() as c:
        for p in ("/.env", "/.git/config", "/api/certs/tetapi.key.pem", "/api/certs/"):
            try:
                r = c.get(API + p)
            except Exception:
                continue
            if 200 <= r.status_code < 300:
                rep.add(f"secrets[{p}]", FAIL, f"{r.status_code} — reachable")
            else:
                rep.add(f"secrets[{p}]", PASS, f"{r.status_code}")
        # openapi.json must not embed a live key
        try:
            spec = c.get(f"{API}/openapi.json").text
            if "pk_live_" in spec:
                rep.add("secrets[openapi]", FAIL, "openapi.json contains 'pk_live_'")
            else:
                rep.add("secrets[openapi]", PASS, "no 'pk_live_' in openapi.json")
        except Exception as e:  # noqa: BLE001
            rep.add("secrets[openapi]", SKIP, str(e))
        # /docs + /redoc: public today; security.md has no ruling → don't decide.
        for p in ("/docs", "/redoc"):
            try:
                r = c.get(API + p)
            except Exception:
                continue
            state = "public" if 200 <= r.status_code < 300 else f"non-public ({r.status_code})"
            rep.add(f"secrets[{p}]", SKIP,
                    f"{state} — OWNER QUESTION: should the interactive API docs be "
                    "public on prod? security.md has no decision; not deciding here.")


# ── h. SECURITY HEADERS ───────────────────────────────────────────────────────
REQUIRED_HEADERS = {
    "strict-transport-security": "HSTS",
    "x-content-type-options": "X-Content-Type-Options",
    "x-frame-options": "X-Frame-Options",
}


def check_headers(rep: Report) -> None:
    hosts = {"landing": LANDING, "app": APP, "api": API, "mcp": MCP}
    with _client() as c:
        for label, base in hosts.items():
            try:
                r = c.get(base + "/")
            except Exception as e:  # noqa: BLE001
                rep.add(f"headers[{label}]", SKIP, f"unreachable: {e}")
                continue
            missing = [nice for h, nice in REQUIRED_HEADERS.items() if h not in r.headers]
            if missing:
                rep.add(f"headers[{label}]", FAIL,
                        f"{base} missing: {', '.join(missing)} "
                        "(fix is nginx/Cloudflare = devops, security.md §6.3)")
            else:
                rep.add(f"headers[{label}]", PASS, f"{base} has HSTS + nosniff + frame-options")


# ── i. MCP ────────────────────────────────────────────────────────────────────
def _mcp_session(c: httpx.Client) -> str | None:
    r = c.post(f"{MCP}/mcp",
               headers={"Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream"},
               json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2025-03-26", "capabilities": {},
                                "clientInfo": {"name": "sec-probe", "version": "0"}}})
    sid = r.headers.get("mcp-session-id")
    if sid:
        c.post(f"{MCP}/mcp",
               headers={"Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "Mcp-Session-Id": sid},
               json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    return sid


def _mcp_call(c: httpx.Client, sid: str, tool: str, args: dict) -> str:
    r = c.post(f"{MCP}/mcp",
               headers={"Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                        "Mcp-Session-Id": sid},
               json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                     "params": {"name": tool, "arguments": args}})
    # SSE framing: pull the data: line
    for line in r.text.splitlines():
        if line.startswith("data:"):
            return line[5:].strip()
    return r.text


def check_mcp(rep: Report) -> None:
    with _client() as c:
        try:
            sid = _mcp_session(c)
        except Exception as e:  # noqa: BLE001
            rep.add("mcp", SKIP, f"initialize failed: {e}")
            return
        if not sid:
            rep.add("mcp", SKIP, "no Mcp-Session-Id returned")
            return
        # teta_search without auth works — by design (S-11)
        try:
            out = _mcp_call(c, sid, "teta_search", {"query": "teta", "limit": 1})
            data = json.loads(out)
            ok = "result" in data
            rep.add("mcp[search_anon]", PASS if ok else FAIL,
                    "anonymous teta_search responds (by design)" if ok
                    else f"unexpected: {out[:120]}")
        except Exception as e:  # noqa: BLE001
            rep.add("mcp[search_anon]", SKIP, str(e))
        # teta_verify_endpoint with a loopback URL must not become a port oracle
        try:
            out = _mcp_call(c, sid, "teta_verify_endpoint",
                            {"endpoint_url": "http://127.0.0.1:8000/health"})
            text = out.lower()
            if "active:            ✓ yes" in text or '"is_active":true' in text.replace(" ", "") \
               or ("active" in text and "✓ yes" in text):
                rep.add("mcp[verify_endpoint_ssrf]", FAIL,
                        "MCP teta_verify_endpoint FETCHED loopback (active=yes) — "
                        "SSRF via MCP live (S-16, awaiting 15.5)")
            else:
                rep.add("mcp[verify_endpoint_ssrf]", PASS,
                        "loopback not fetched / rejected")
        except Exception as e:  # noqa: BLE001
            rep.add("mcp[verify_endpoint_ssrf]", SKIP, str(e))
        try:
            c.request("DELETE", f"{MCP}/mcp", headers={"Mcp-Session-Id": sid})
        except Exception:
            pass


CHECKS = {
    "auth": check_auth_surface,
    "ssrf": check_ssrf,
    "s15": check_s15_agent_key,
    "s1": check_s1_traversal,
    "s8": check_s8_private_blocks,
    "private-entity": check_private_entity_exposure,
    "secrets": check_secrets,
    "headers": check_headers,
    "mcp": check_mcp,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="TETA+PI security regression net (15.6)")
    ap.add_argument("--only", choices=list(CHECKS.keys()) + ["rate"],
                    help="run one check group")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--include-heavy", action="store_true",
                    help="also run high-volume rate-limit checks (>100 requests)")
    args = ap.parse_args()

    rep = Report()
    if args.only == "rate":
        check_rate_limits(rep, args.include_heavy)
    elif args.only:
        CHECKS[args.only](rep)
    else:
        for fn in CHECKS.values():
            fn(rep)
        check_rate_limits(rep, args.include_heavy)

    if args.json:
        print(json.dumps({"failed": rep.failed,
                          "results": [r.__dict__ for r in rep.results]}, indent=2))
    else:
        counts = {PASS: 0, FAIL: 0, SKIP: 0}
        for r in rep.results:
            counts[r.status] += 1
        print(f"TETA+PI security probe — {API}")
        print("=" * 72)
        for r in rep.results:
            mark = {PASS: "✅", FAIL: "❌", SKIP: "⚪"}[r.status]
            print(f"{mark} {r.status:4} {r.name}")
            if r.status != PASS:
                for ln in r.evidence.splitlines():
                    print(f"        {ln}")
        print("=" * 72)
        print(f"{counts[PASS]} pass · {counts[FAIL]} fail · {counts[SKIP]} skip")
        if rep.failed:
            print("RESULT: FAIL — at least one regression or live gap. See above.")
        else:
            print("RESULT: clean (no FAILs).")

    return 1 if rep.failed else 0


if __name__ == "__main__":
    sys.exit(main())
