# Security probe — regression net (15.6)

`probe.py` is the automated form of `docs/security.md` §6.2. One run = one
report. It re-asserts, against **prod**, that every CLOSED finding in
`docs/security.md` §5 has stayed closed and that no new unauthenticated public
surface appeared unnoticed. This is the class of bug static scanners
(CodeQL/bandit, wired in 15.2) never see: S-15 (agent-key), S-16 (loopback
SSRF), private-block/entity leaks — all found by hand, by luck, over two months.

It replaces the old "monthly manual re-audit" cadence with a daily GitHub
Action (`.github/workflows/security-probe.yml`).

## Rules of engagement (baked in — see `docs/security.md`)

- Our own infra only (`api.` / `mcp.` / `app.` / `tetapi.dev`).
- Read-only: GET/HEAD plus only the POSTs that **by design don't write**
  (`verify-endpoint` persists nothing for an entity the caller doesn't own;
  `agent-key`/`tag-ping` are probed with junk so nothing is stored/created).
  **No entity, user, block, or claim is ever created.**
- Rate limits respected — `verify-endpoint` is 5/min, so the SSRF check uses ≤3
  canaries with pauses.
- Findings are reported, never weaponised. **No auto-fix** — that is the owner's
  call (`docs/decisions.md`, 2026-09-14).

## Running locally

```bash
# full net (uses ~/.tetapi/test_api_key automatically for the auth'd checks)
python3 scripts/security/probe.py

# one group, or machine-readable
python3 scripts/security/probe.py --only auth
python3 scripts/security/probe.py --json

# high-volume rate-limit checks (badge 120/min, tag-ping 240/min) — OFF by
# default because generating >100 req/min against prod is the "load" the rules
# of engagement forbid for a daily run. Run deliberately, not in cron.
python3 scripts/security/probe.py --include-heavy
```

Needs Python 3.12 + `httpx` (the only non-stdlib dep, mirroring
`scripts/gtm/pull_top500.py`). On macOS with a python.org install you may need
`SSL_CERT_FILE=$(python3 -m certifi) …` (same note as `scripts/gtm/README.md`).

Exit code is `1` if any check **FAIL**s (drives the workflow red), `0`
otherwise. **SKIP never fails the run** — it means "could not assert honestly"
(missing fixture, no key, or an unresolved owner decision), not "passed".

## The three files

| File | Role |
|---|---|
| `probe.py` | the checks |
| `public_allowlist.json` | **the contract.** Every route the API may answer 2xx to an *unauthenticated* caller. `auth_surface` fails any live 2xx-to-anonymous route not listed here. `must_not_exist` lists deleted security-fix routes that must stay 404. `pending_owner_decision` records live 2xx surface the docs don't sanction yet (informational; the dedicated check that finds it is what fails). |
| `fixtures.json` | stable prod rows the probe **reads** (never writes) — e.g. the 15.3 entity (public since S-17) with one public + one private block for S-8, and a private entity for S-17. |

## Checks → findings

| Check | Asserts | S-* |
|---|---|---|
| `auth_surface` | every openapi path+method, called unauth with junk, returns 401/403/404/405/422 or is allowlisted; deleted routes stay gone | catches S-15-class regressions |
| `ssrf_canaries` | `verify-endpoint` won't fetch loopback / metadata / RFC1918 (`is_active` stays false) | S-16 |
| `s15_agent_key` | `POST /auth/agent-key` is 404 **and** absent from openapi | S-15 |
| `s1_path_traversal` | `/media/local/…` traversal variants never 200 `/etc/passwd` | S-1 |
| `s8_private_blocks` | anonymous `GET /businesses/{id}/blocks` withholds private blocks | S-8 |
| `private_entity_exposure` | a private (`is_public=false`) entity 404s anonymously on base/`preview`/`proof`/`blocks` and still 200s for the owner (fixture `s17_private_entity`) | S-17 |
| `secrets` | `/.env`, `/.git/config`, `/api/certs/` unreachable; no `pk_live_` in openapi; flags `/docs`+`/redoc` as an owner question | secrets §4 |
| `headers` | HSTS + nosniff + frame-options on all four hosts (fix is devops, §6.3) | headers §4 |
| `mcp` | `teta_search` works anon (by design); `teta_verify_endpoint` won't fetch loopback | S-11/S-16 |
| `rate_limit` | `verify-endpoint` 5/min limiter trips (default); badge/tag-ping under `--include-heavy` | rate-limiting §4 |

## On-box co-tenant asserts (S-18 / S-19 / S-20) live in `cotenant_check.sh`, not here

`probe.py` runs on a **GitHub runner with no SSH to prod** — it can only reach the
public HTTP surface. The co-tenant/shared-host blockers are filesystem- and
loopback-level (`.env` perms, `/opt/tetapi/api` ownership, Redis `AUTH` on
`127.0.0.1:6379`), invisible over HTTP. So they are **not** in the table above;
they are asserted by **`cotenant_check.sh`**, which must be run **on the droplet**
with local sudo (`docs/security.md` §6.2 exception):

```bash
ssh tetapi 'sudo bash -s' < scripts/security/cotenant_check.sh   # exit 0 == all pass
```

| S-* | Assert in `cotenant_check.sh` |
|---|---|
| S-18 | `shos` cannot read `/opt/tetapi/api/.env` (must be `600 root:root`) |
| S-19 | `/opt/tetapi/api` owned by `root:root` (not a co-tenant) |
| S-20 | Redis `127.0.0.1:6379` rejects unauthenticated `PING` (`requirepass`) |

All three are ✅ CLOSED (5.9, 2026-09-19) and PASS. Re-run the script after any
change to `/opt/tetapi` perms/ownership, the redis container, or when onboarding a
new co-tenant. It is read-only (redis: `PING` only).

## Adding a check when a new S-* closes

**Rule (`docs/security.md` §6.2): every closed S-\* gets an assert here, in the
same PR that closes it.** So the fix and its regression test ship together and
the net only ever grows.

1. Add a `check_<name>(rep)` function that makes one or more read-only requests
   and calls `rep.add(name, PASS|FAIL|SKIP, evidence)`. Use `SKIP` — never a
   fake `PASS` — when a fixture or key is missing.
2. Register it in the `CHECKS` dict (its key becomes a `--only` value).
3. If the fix deleted a route, add it to `must_not_exist` in
   `public_allowlist.json`. If it added a legitimately-public route, add it to
   `public` with a `docs/api.md` citation.
4. If it needs a stable prod row, add it to `fixtures.json` (read-only; if it
   ever disappears the check must SKIP, not fail).
5. Run `python3 scripts/security/probe.py --only <name>` against prod and paste
   the result in the PR.

## The GitHub secret

The auth'd checks (SSRF canary, `verify-endpoint` rate limit) need a test
`pk_live_` key. In CI it comes from the repo secret **`SEC_PROBE_API_KEY`**
(owner adds it manually: Settings → Secrets and variables → Actions → New
repository secret, value = the key in `~/.tetapi/test_api_key`). Without it,
those checks SKIP (honestly) rather than fail. The key is **never logged**.
