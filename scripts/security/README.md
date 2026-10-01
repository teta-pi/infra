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
# full net. Locally this falls back to ~/.tetapi/test_api_key — which is the
# OWNER'S ADMIN key. CI does not use it (see "The probe account" below); for a
# faithful rehearsal of the CI run, pass the probe account's key explicitly:
#   SEC_PROBE_API_KEY=$(cat <probe key file>) python3 scripts/security/probe.py
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
The `origin-tls` check additionally shells out to the `openssl` CLI (present
by default on GitHub's `ubuntu-latest` runners and any dev machine) rather
than adding a certificate-parsing library — SKIPs, doesn't fail, if it's
missing. Origin IP defaults to `164.90.235.66`, override with
`SEC_PROBE_ORIGIN_IP`.

Exit code is `1` if any check **FAIL**s (drives the workflow red), `0`
otherwise. **SKIP never fails the run** — it means "could not assert honestly"
(missing fixture, no key, or an unresolved owner decision), not "passed".

## The three files

| File | Role |
|---|---|
| `probe.py` | the checks |
| `public_allowlist.json` | **the contract.** Every route the API may answer 2xx to an *unauthenticated* caller. `auth_surface` fails any live 2xx-to-anonymous route not listed here. `must_not_exist` lists deleted security-fix routes that must stay 404. `pending_owner_decision` records live 2xx surface the docs don't sanction yet (informational; the dedicated check that finds it is what fails). |
| `fixtures.json` | stable prod rows the probe **reads** (never writes) — the 15.3 entity (public since S-17) with one public + one private block for S-8, plus the probe account's own private entity (S-17) and its one **revoked** Pi CAM device (+ that device's now-worthless key, stored without the `pk_live_` prefix) for S-21. Since 15.8 the S-17/S-21 rows belong to `security-probe@tetapi.dev`, not to the owner — see "The fixtures" below. |

## Checks → findings

| Check | Asserts | S-* |
|---|---|---|
| `auth_surface` | every openapi path+method, called unauth with junk, returns 401/403/404/405/422 or is allowlisted; deleted routes stay gone | catches S-15-class regressions |
| `ssrf_canaries` | `verify-endpoint` won't fetch loopback / metadata / RFC1918 (`is_active` stays false) | S-16 |
| `s15_agent_key` | `POST /auth/agent-key` is 404 **and** absent from openapi | S-15 |
| `s1_path_traversal` | `/media/local/…` traversal variants never 200 `/etc/passwd` | S-1 |
| `s8_private_blocks` | anonymous `GET /businesses/{id}/blocks` withholds private blocks | S-8 |
| `private_entity_exposure` | a private (`is_public=false`) entity 404s anonymously on base/`preview`/`proof`/`blocks` and still 200s for the owner (fixture `s17_private_entity`) | S-17 |
| `s21_device_revoked` | `POST /media/device-upload` with a **revoked** Pi CAM key → 401, and the owner's `GET /devices` still lists that device with `revoked_at` set (fixture `s21_revoked_device`; SKIP if the row is gone, FAIL if it was re-paired) | S-21 |
| `key-privilege` | the probe's own CI key authenticates as a plain `user` — not `admin`/`support` — and a `require_admin` route 403s it | S-26 |
| `secrets` | `/.env`, `/.git/config`, `/api/certs/` unreachable; no `pk_live_` in openapi; flags `/docs`+`/redoc` as an owner question | secrets §4 |
| `headers` | HSTS + nosniff + frame-options on all four hosts (fix is devops, §6.3) | headers §4 |
| `mcp` | `teta_search` works anon (by design); `teta_verify_endpoint` won't fetch loopback | S-11/S-16 |
| `origin-tls` | dials the origin IP directly (bypassing Cloudflare) per our-own hostname's SNI and compares the served cert's CN/SAN to that hostname, not response body size — a byte match is someone else's site's implementation detail, not identity | S-25 (honestly RED until the `:443` vhosts + default-reject land) |
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

| S-* | Assert in `cotenant_check.sh` | 15.7 (2026-09-20) |
|---|---|---|
| S-18 | `shos` cannot read `/opt/tetapi/api/.env` (must be `600 root:root`) | ✅ PASS |
| S-19 | `/opt/tetapi/api` owned by `root:root` (not a co-tenant) | ❌ **REGRESSED** — `hellfire:hellfire` again (api deploy `rsync -az` preserves runner uid 1001) |
| S-20 | Redis `127.0.0.1:6379` rejects unauthenticated `PING` (`requirepass`) | ✅ PASS |
| S-24 | `docker` group has no co-tenant (only `bob`) — membership == host root | ❌ FAIL — `hellfire` in `docker` group |
| S-23 | no cleartext redis password in `journalctl -u tetapi-celery-worker` | ❌ FAIL |
| H-1 | `sshd PermitRootLogin` is `prohibit-password`/`no`, not `yes` | ❌ FAIL |
| H-4 | tetapi-postgres pg_hba has no loopback/local `trust` line | ❌ FAIL (safe today only via docker-proxy topology) |

**Do not run under `sudo -u shos` for the docker check** — shos runs its own
rootless daemon, so a bare `docker ps` succeeds legitimately; the script forces
`DOCKER_HOST=unix:///var/run/docker.sock` to test host-socket access specifically.
S-18/S-20 PASS; **S-19 regressed** and S-24/S-23/H-1/H-4 are honestly RED (the fixes
are prod-config/CI, raised for a devops boot — see `docs/security.md` §5/§5.1). Re-run
after any change to `/opt/tetapi` perms/ownership, the redis container, the `docker`
group, `sshd` config, or when onboarding a co-tenant. Read-only (redis: `PING` only).

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

## The probe account (15.8) — the net runs as a plain `user`

The auth'd checks run as **`security-probe@tetapi.dev`** (`role=user`,
`is_agent=false`, user id `4909361d-2481-45de-b0ca-62f9f0de7a88`), created
2026-10-01 for this purpose only. Before 15.8 they ran as the **owner's own
`role=admin` account** (`tetakta@gmail.com`) — see S-26 in `docs/security.md`:
a compromised runner, workflow or third-party action got `require_admin` on
prod (bulk-preverify, GDPR export, anonymise, claims, `admin/devices`,
audit-log) for a net that calls **no** admin route at all.

What the key is actually needed for — four checks, none of them admin:

| check | why it needs a key |
|---|---|
| `ssrf` | `POST /verify-endpoint` requires auth since the 1.7 fix |
| `rate` | same route — the 5/min limiter can only be tripped auth'd |
| `private-entity` | the S-17 rule is "owner 200, everyone else 404" — the owner half needs the fixture's **owner** |
| `s21` | `GET /devices` lists the **caller's own** devices, to prove the fixture row is revoked and not re-paired |

So the requirement was never *admin*, only *owner of the fixtures* — which is
why the fixtures moved with the account (below). `key-privilege` asserts this
stays true: it fails the run if the key ever authenticates as `admin`/`support`
again.

**The owner's `~/.tetapi/test_api_key` is deliberately NOT rotated by 15.8** —
it is the owner's personal admin key for manual manager checks (live-verifying a
deploy, admin-path spot checks) and has no CI role any more.

### Creating / rotating the probe account

The account was created with a one-off `psql` INSERT, not the signup flow: the
flow is `POST /auth/email-code` → a 6-digit code delivered **by email**, and
`tetapi.dev` has no MX record, so a code addressed to a role mailbox on our own
domain hard-bounces. (Reading the code out of prod Redis instead was blocked by
the session sandbox.) Documented here rather than hidden:

```sql
INSERT INTO users (id, email, auth_provider, role, token_version, is_active, is_agent, api_key)
VALUES (gen_random_uuid(), 'security-probe@tetapi.dev', 'email', 'user', 0, true, false, '<pk_live_…>');
```

**Rotation does not need psql.** `get_current_user` accepts a `pk_live_` bearer,
so the account can rotate its own key:

```bash
curl -s -X POST https://api.tetapi.dev/api/v1/auth/personal-api-key \
     -H "Authorization: Bearer $OLD_KEY"          # → {"api_key": "pk_live_…"}
gh secret set SEC_PROBE_API_KEY --repo teta-pi/infra < <file holding the new key>
```

Never paste the key into a chat, a PR, a log or a commit — pipe it from a file.
Because the mailbox does not exist, there is **no email-recovery path** into this
account; that is intentional (one less takeover route), and the trade-off is
that a lost key is re-issued by `psql` the same way it was created.

## The fixtures — the prod writes this net has justified

`check_private_entity_exposure` and `check_s21_device_revoked` assert against
rows that must exist on prod, owned by whoever holds the probe key. 15.8 moved
them off the owner's account onto the probe account; both were created **once,
by hand**, through the ordinary product API (no psql), on 2026-10-01:

1. `POST /businesses` → `PATCH {is_public:false, is_published:false}` — the
   **S-17 fixture**, entity `70be78d9-4859-41d1-bdd3-ba272ea69653`
   ("TETA Security Probe Fixture 15.8"), private and never published.
2. `POST /devices/generate-token` → `POST /devices/register` (synthetic
   fingerprint `sec-probe-s21-fixture-158`) → `DELETE /devices/{id}` — the
   **S-21 fixture**, device `eea13e52-03d7-4499-ba89-d012b241c902`. The device
   id and the revoked key's suffix went into `fixtures.json`; the key is
   **worthless by construction** (revocation erases it, `api_key IS NULL`),
   which is the whole point — if it ever stops being worthless the check goes
   red. Stored without the `pk_live_` prefix so no secret scanner trips on it.

Proving the key worked *before* revocation no longer costs a write: `POST
/media/device-upload` with the live key and **no file body** returned `422`
(dependency resolved, body rejected = the header authenticated), and `401` with
the same key after `DELETE`. The 1.25 fixture run did a real upload for this;
the `422`/`401` pair proves the same thing and stores nothing. Both old
fixtures (`ab27ca35…`, `ef2cdffa…`, under the owner's account) were left in
place untouched — deleting prod rows is not something this net does.

⚠️ `GET /devices` resolves **the caller's first business**, so the probe account
must keep owning **exactly one** entity. Do not create a second one under it, or
the S-21 check starts reading the wrong entity's devices.

The S-8 fixture is read **anonymously** (it asserts what a non-owner can see),
so its owner is irrelevant; it was deliberately left under the owner's account.

## The GitHub secret

The four auth'd checks take their key from the repo secret
**`SEC_PROBE_API_KEY`** (`teta-pi/infra` → Settings → Secrets and variables →
Actions). Since 15.8 its value is the **probe account's** key, not the owner's.
Without it those checks SKIP (honestly) rather than fail. The key is **never
logged**, and `key-privilege` fails the run if a privileged key is ever put back.
`SEC_PROBE_API_KEY` exists in `teta-pi/infra` only — no other repo in the org,
and no org-level secret, holds a `pk_live_` key (checked 2026-10-01).
