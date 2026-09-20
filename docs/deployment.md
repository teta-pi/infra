# Deployment

## Server
DigitalOcean droplet, Frankfurt, `164.90.235.66` — resized 2026-07-13 to
`s-1vcpu-2gb` (1 vCPU / 2 GB / 50 GB, $12/mo; was `s-1vcpu-512mb-10gb`, see the
9.1 runbook below for the historical measurements and the resize itself). The
sustained-load restriction from the old 512MB spec is lifted. SSH:
`ssh -i ~/.ssh/tetapi_ed25519 root@164.90.235.66` (owner's Mac has a `Host tetapi`
alias in `~/.ssh/config` → just `ssh tetapi`).

### SSH access — key-only (hardened 2026-07-13)
- **Password auth is OFF.** `/etc/ssh/sshd_config.d/00-tetapi-hardening.conf`
  (`PasswordAuthentication no`) — named `00-` so it sorts before cloud-init's
  `50-cloud-init.conf` (which set `yes`); OpenSSH takes the *first* value per
  Include, read alphabetically, so an earlier `60-…` override silently never
  applied. **Do not add a password back; do not "fix" sshd by restarting into a
  drifted config.**
- **You MUST connect with the key** `~/.ssh/tetapi_ed25519` (same key as CI's
  `DEPLOY_SSH_KEY`). Plain `ssh root@164.90.235.66` (no `-i`) will fall through
  to `Permission denied (publickey)`, NOT a password prompt.
- **fail2ban** guards sshd (default `REJECT` → clients see "Connection refused",
  not a timeout). Repeated failed *password* attempts (e.g. `ssh` falling back to
  password without the key) get the IP banned. Recover via the manual
  `.github/workflows/unban-ip.yml` (runs `fail2ban-client unbanip` + `addignoreip`
  over the CI key) or DigitalOcean Console. A "Connection refused" from one
  machine while CI deploys still succeed = that machine's IP is banned, **not**
  sshd down.

- **Docker**: `tetapi-postgres` (pgvector/pgvector:pg16), `tetapi-redis`.
- **systemd**: `tetapi-api` (uvicorn `--workers 1`, port 8000),
  `tetapi-web` (Next.js standalone), `tetapi-mcp` (node, port 3002),
  `tetapi-celery-worker` + `tetapi-celery-beat` (added 2026-07-25, session 5.4)
  — `celery -A app.workers.celery_app:celery_app worker/beat --concurrency=1`,
  same `WorkingDirectory=/opt/tetapi/api` + `EnvironmentFile=/opt/tetapi/api/.env`
  + `/opt/tetapi/venv` as `tetapi-api`, talks to the same `tetapi-redis` broker.
  The unit files live only at `/etc/systemd/system/*.service` on the server (not
  in this repo), but since 2026-08-05 (session 5.5) `deploy.yml` **does restart
  both celery units on every deploy** (right after `tetapi-api`, each
  health-checked) so a code change to `app/workers/tasks/*.py` picks up without a
  manual `systemctl restart`. Restart is unconditional — no file-change detection
  (cheap: `--concurrency=1`, small RAM). `--concurrency=1` on the worker matches
  the single-uvicorn-worker RAM-budget philosophy (droplet is still 1 vCPU / 2 GB).
- **nginx**: serves landing from `/var/www/teta-pi/`, reverse-proxies the subdomains.
- **Python venv**: `/opt/tetapi/venv`. API code at `/opt/tetapi/api`, web at
  `/opt/tetapi/web`, mcp at `/opt/tetapi/mcp`.

## CI/CD — `.github/workflows/deploy.yml`
Trigger: push to `main`. Steps: build Next.js standalone → SSH setup →
rsync API / certs (public only) / Next output / MCP dist / landing → remote script:
patch Next standalone chunks, **patch `app-paths-manifest.json`** (must list every
route — add new pages here!), `pip install` runtime deps, `alembic upgrade head`,
restart `tetapi-api`, then `tetapi-celery-worker` + `tetapi-celery-beat` (5.5),
`tetapi-web`, `tetapi-mcp` (each health-checked). Celery restarts unconditionally
every deploy so worker/beat never keep running stale task code (regression from
the 1.9 OTS fix, where only the API restarted and the worker crashed for 33 min).

⚠ When you add a Next.js page, add its route to the `app-paths-manifest.json` block
in the workflow or it 404s in production.

## Test CI — `.github/workflows/tests.yml` (api repo, 5.7)
The api repo's other workflows are `bandit.yml`, `codeql.yml`, `pip-audit.yml`
(security/deps) and `deploy.yml` (prod). Since 5.7 there is also **`tests.yml`**,
which runs `pytest`. Trigger: `pull_request` + push to `main` (+ `workflow_dispatch`).
Steps: `actions/setup-python@v6` (3.12) → `pip install ".[dev]"` → `pytest -q`.
Same style as `bandit.yml`/`pip-audit.yml` (`checkout@v7`, `permissions: contents: read`,
`timeout-minutes`).

**No Postgres service, zero droplet load.** It runs entirely on the GitHub runner.
The 1.22 suite (`tests/test_blocks_is_public.py`, the repo's first pytest) is
unit-level: `add_block` is called with a stub `AsyncSession` and the owner check +
embedding patched out, and every `Settings` field has a default with a lazily-created
engine — so imports and the run need no database.

**Not a required status check yet** — whether a red run blocks merge on `main` is an
owner call (see roadmap 5.7 / the api PR). Until the owner adds it under `main`'s
branch protection, the Tests run is advisory (visible on the PR, non-blocking).

## nginx config — applied MANUALLY, not by CI
`deploy/nginx/*.conf` and `deploy/nginx/snippets/*.conf` are **not** touched by
`deploy.yml`. The push-to-`main` pipeline only rsyncs app code — it never writes
`/etc/nginx`. Editing a conf in this repo does nothing on prod until a human
copies it up. Because of that, the repo had silently drifted from the live
configs (reconciled 2026-09-15, 5.6); **before editing a conf, diff it against
the server** (`ssh tetapi "cat /etc/nginx/sites-available/<name>"`).

### Repo file → server path mapping (they are NOT all 1:1 by name)
| repo file | server `/etc/nginx/sites-available/…` |
|---|---|
| `deploy/nginx/api.tetapi.dev.conf` | `api.tetapi.dev` |
| `deploy/nginx/app.tetapi.dev.conf` | `app.tetapi.dev` |
| `deploy/nginx/mcp.tetapi.dev.conf` | `mcp.tetapi.dev` |
| `deploy/nginx/tetapi.dev.conf` | **`teta-pi`** (landing — note the different name) |
| `deploy/nginx/snippets/security-headers.conf` | `/etc/nginx/snippets/security-headers.conf` |

Not tracked in this repo (server-only, out of the 5.6 header rollout):
`stats.tetapi.dev` (GoatCounter), `teta`, `hellfiresol.com`, `default`.

### Applying an nginx change (the manual step)
```bash
# from repo root, for each changed file (snippet FIRST if a conf includes it):
scp deploy/nginx/snippets/security-headers.conf tetapi:/etc/nginx/snippets/security-headers.conf
scp deploy/nginx/api.tetapi.dev.conf  tetapi:/etc/nginx/sites-available/api.tetapi.dev
scp deploy/nginx/app.tetapi.dev.conf  tetapi:/etc/nginx/sites-available/app.tetapi.dev
scp deploy/nginx/mcp.tetapi.dev.conf  tetapi:/etc/nginx/sites-available/mcp.tetapi.dev
scp deploy/nginx/tetapi.dev.conf      tetapi:/etc/nginx/sites-available/teta-pi
ssh tetapi "nginx -t"                 # MUST pass before reloading
ssh tetapi "systemctl reload nginx"   # reload, NOT restart (zero-drop)
```
If `nginx -t` fails: do **not** reload, restore the previous file(s), report.
`reload` re-reads config with no dropped connections; `restart` would blip all
sites — never use it for a config change.

## Security response headers (5.6, 2026-09-15)
TLS terminates at **Cloudflare** (all four hosts answer `server: cloudflare`;
origin nginx is `listen 80` only). Cloudflare passes origin response headers
through unchanged — drift-checked 2026-09-15 by curling origin directly
(`curl -sI -H "Host: <h>" http://164.90.235.66/`) and comparing to the CF-fronted
response. So the headers are set **once, at the origin**, in nginx.

- **app / api / mcp**: `include snippets/security-headers.conf;` at `server{}`
  level → HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy`. All `always` so they appear on 4xx/5xx too (api answers 405
  and mcp 404 to `GET /`).
- **landing (`teta-pi`)**: keeps its own self-contained header set and
  `X-Frame-Options: SAMEORIGIN`; only HSTS was added (inline, not via the
  snippet — the snippet's `DENY` would duplicate/conflict with the landing's
  headers).

### HSTS raise plan (deliberately conservative)
Start value is `max-age=86400` (1 day), **no** `includeSubDomains`, **no**
`preload`. HSTS is browser-cached and hard to walk back, so raise in steps:
1. **Now (5.6):** `max-age=86400` on all four hosts.
2. **After ≥7 days with no TLS/mixed-content incident:** separate PR →
   `max-age=31536000` (1 year).
3. **`includeSubDomains`:** only after confirming **every** `*.tetapi.dev`
   subdomain is HTTPS-only — today that's the 4 hosts **plus `stats.tetapi.dev`**
   (GoatCounter) and any future `verify.tetapi.dev` (12.5c, not deployed yet).
   Adding it before a subdomain is HTTPS-ready would black-hole that subdomain
   in every browser that saw the header.
4. **`preload`:** never without an explicit, separate owner decision — it is a
   browser-baked, effectively irreversible commitment (submits the apex to the
   HSTS preload list). Not planned.

## Secrets — server `.env` only (`/opt/tetapi/api/.env`), never in git
`SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `RESEND_API_KEY`, `PII_ENCRYPTION_KEY`
(Fernet), `ENVIRONMENT=production`, plus optional `OPENAI_API_KEY`,
`NORTHDATA_API_KEY`, `OPENDATABOT_API_KEY`, `UK_COMPANIES_HOUSE_API_KEY`.
`api/certs/*.key.pem` (C2PA signing key) must **never** be synced/committed — the
rsync excludes it. Agent admin API key is stored at `/root/tetapi-agent-admin.key`.

## GitHub Actions secrets (`teta-pi/infra`)
- `DEPLOY_SSH_KEY` — the deploy/unban SSH key (see `unban-ip.yml`).
- **`SEC_PROBE_API_KEY`** — a test `pk_live_` key the daily security probe
  (`security-probe.yml`, 15.6) uses for its authenticated checks (SSRF canary,
  `verify-endpoint` rate limit). **Owner must add this manually** — Claude
  sessions never paste keys into chat or the GitHub UI:
  **Settings → Secrets and variables → Actions → New repository secret**,
  name `SEC_PROBE_API_KEY`, value = the key in your local `~/.tetapi/test_api_key`.
  Until it's set those two checks SKIP (honestly) instead of running; every
  unauthenticated check still runs. The key is never logged by the probe.

## Not yet configured (see known-issues / roadmap)
- `OPENAI_API_KEY` — unset → TWIRA semantic (I) ranking off, keyword fallback used.
- Resend domain `tetapi.dev` not verified → emails deliver only to
  `tetakta@gmail.com`; sender is `onboarding@resend.dev` until DKIM/SPF added.

## Verifying a deploy
```
gh run list --limit 1                 # CI status
curl -s https://api.tetapi.dev/health
curl -s https://mcp.tetapi.dev/.well-known/mcp
```
After any change, verify on prod (curl the affected endpoint / open the page).

## Analytics
Self-hosted GoatCounter at `stats.tetapi.dev` (systemd, SQLite). Tracking snippet in
the Next.js layout and every landing page. GoatCounter listens on `127.0.0.1:8100`.

## Co-tenant: shos (SH.OS) — 5.8, 2026-09-18

The droplet hosts a **second, unrelated project (SH.OS)** alongside TETA+PI. Its
dev agent gets an isolated, unprivileged foothold; TETA+PI keeps full control of
nginx / ports / limits. SH.OS requests changes via the manager session — they
never edit nginx or systemd. This box was *already* multi-tenant before 5.8 (the
`hellfire` / `hellfiresol.com` project, `docs/security.md` B6); shos is the first
one provisioned to the strict model below.

> ✅ **ACCESS ENABLED 2026-09-20 (task 5.10).** `shos` can now SSH in with the
> owner-supplied key. Isolation verified live from a real `shos` session: no sudo,
> no host docker socket, cannot read `/opt/tetapi/api/.env`, redis `-NOAUTH`,
> postgres requires a SCRAM password, and a >512 MB allocation is cleanly
> OOM-killed (TETA+PI api/app stayed 200 throughout). Owner authorized 2026-09-19.
> To revoke in one move, see "Revoking SH.OS access" below.
>
> Enabling surfaced (and 5.10 fixed) a resource-cap gap: `MemoryMax` alone was not
> a hard ceiling because the slice could spill to the 2 GB swapfile — fixed with
> `MemorySwapMax=0` and by dropping `MemoryHigh` (see the limits table). Residual
> notes: postgres `127.0.0.1:5432` is TCP-reachable from `shos` but password-gated
> (SCRAM, not `trust`); and the public `shos.hellfiresol.com` still resolves to the
> hellfire apex site via Cloudflare — the CF SSL mode is Full so CF reaches origin
> `:443` (hellfire's default vhost), not our `:80` shos vhost. That routing is a
> Cloudflare/hellfire-zone fix, not TETA+PI infra.

### The account (done, on prod)
- User `shos`, **uid 1002**, `--disabled-password`, groups **`shos` + `users` only**
  — deliberately **NOT** in `sudo`, **NOT** in `docker` (docker group == root).
- `loginctl enable-linger shos` (user services survive with no live session).
- subuid/subgid `231072:65536` (auto-added; needed for rootless docker).
- Containers, if any, run **rootless** under shos — never the host docker socket.
  Prereqs installed system-wide in 5.8: `uidmap`, `slirp4netns`
  (`dockerd-rootless-setuptool.sh` + `dbus-user-session` were already present;
  `kernel.unprivileged_userns_clone=1`).

### Resource limits (systemd slice — enforced, not honour-system)
Tracked in this repo at `deploy/systemd/user-1002.slice.d/limits.conf`, applied
manually to `/etc/systemd/system/user-1002.slice.d/limits.conf` + `daemon-reload`.

| Limit | Value | Why |
|---|---|---|
| `MemoryMax` | 512M | hard cap; kernel OOM-kills a shos process first. `available` was ~1086 MB at provisioning, so this leaves TETA+PI its usage + headroom |
| `MemorySwapMax` | 0 | **added 5.10.** Without it the slice could spill over `MemoryMax` into the 2 GB swapfile (`memory.swap.max` defaulted to `max`), so `MemoryMax` was only a RAM-residency limit — a 650 MB test allocation *survived* by swapping (`memory.events` `oom_kill=0`). Pinning swap to 0 makes 512M a true ceiling: over-cap → OOM-kill (verified `oom_kill=1`, exit 137) |
| `CPUQuota` | 50% | **one** vCPU shared with TETA+PI (RAM-bound, idle load <0.2) + hellfire; half a core so shos can never starve the API |
| `TasksMax` | 512 | fork-bomb ceiling |

**`MemoryHigh` removed (5.10).** It was `410M` ("throttle-before-kill"), which only
helps *with* swap. With `MemorySwapMax=0` it has no reclaim target, so a runaway
livelocks in throttle between High and Max instead of being killed (observed:
`memory.events` `high` climbed past 23000, process wedged ~451M, never OOM-killed,
and the stall degraded other shos sessions). Dropping High lets `MemoryMax` do a
clean, prompt kill.

Caps bind the whole shos **user manager** (its `systemd --user` units + rootless
dockerd under `user@1002.service`). A `sudo -u shos …` from another login is *not*
capped by this slice — so the live OOM test must run from a real shos SSH session
(the enable-time 5.10 test did, and got a clean OOM-kill).

### Ports — shos may listen ONLY on `127.0.0.1:8200–8299`
`8100` is GoatCounter, `8090` is hellfire — the boot's original `8100–8199` was
dirty; **`8200–8299` is verified free**. SH.OS tells us which port their app binds;
we point a vhost at it. Enforcement is by convention + the perimeter, not systemd
(systemd can't cheaply pin a bind address): nginx only ever `proxy_pass`es to
`127.0.0.1`, and the **only** externally-reachable ports must be 22/80/443 (see
"DigitalOcean firewall" below). A shos process binding `0.0.0.0` is a policy
violation — `scripts/security/cotenant_check.sh` lists shos-owned listeners.

### Rootless docker — SH.OS initialises it themselves (once, in their own session)
```bash
# as shos, after their SSH key is added:
dockerd-rootless-setuptool.sh install
systemctl --user enable --now docker
export DOCKER_HOST=unix:///run/user/1002/docker.sock   # add to ~/.bashrc
docker info      # confirm rootless
```

### Adding an SH.OS vhost (we do this, not them) — DONE 5.10, 2026-09-20
File: `deploy/nginx/shos.hellfiresol.com.conf` (domain-named, matching the other
vhosts; `listen 80`, `server_name shos.hellfiresol.com`, `proxy_pass
http://127.0.0.1:8200`, `proxy_read_timeout 60s`, shared security-headers snippet).
Deployed 2026-09-20:
```bash
scp deploy/nginx/shos.hellfiresol.com.conf tetapi:/tmp/shos.hellfiresol.com.conf
ssh tetapi "sudo mv /tmp/shos.hellfiresol.com.conf /etc/nginx/sites-available/shos.hellfiresol.com && \
  sudo ln -sf /etc/nginx/sites-available/shos.hellfiresol.com /etc/nginx/sites-enabled/shos.hellfiresol.com && \
  sudo nginx -t && sudo systemctl reload nginx"
```
The origin correctly returns **502** until SH.OS's app listens on `127.0.0.1:8200`
(their first port; they tell the manager if they need another in 8200–8299).
⚠ **Public routing caveat:** `https://shos.hellfiresol.com` via Cloudflare currently
serves the hellfire apex site, not this origin — CF SSL mode is Full so CF reaches
origin `:443` (hellfire's default vhost), never our `:80`. Aligning that (Flexible
SSL for the subdomain, or a `:443` origin cert for this host) is a Cloudflare /
hellfire-zone change, outside TETA+PI infra.

### Enabling SSH access (the gated last step) — DONE 5.10, 2026-09-20
1. **Owner generates the key on their OWN machine** (never on the server):
   `ssh-keygen -t ed25519 -f ~/.ssh/shos_ed25519 -C shos@tetapi-droplet`
2. Owner gives us the **public** part (`~/.ssh/shos_ed25519.pub`) — never the
   private key, never pasted into chat as the private half.
3. Install it + a scoped sshd block (does **not** touch the global hardening):
```bash
cat ~/.ssh/shos_ed25519.pub | ssh tetapi "sudo install -d -m700 -o shos -g shos /home/shos/.ssh && \
  sudo tee /home/shos/.ssh/authorized_keys >/dev/null && \
  sudo chmod 600 /home/shos/.ssh/authorized_keys && \
  sudo chown shos:shos /home/shos/.ssh/authorized_keys"
# scoped drop-in — MUST sort LAST (99-), see the Match-leak note below:
ssh tetapi "printf 'Match User shos\n    AllowAgentForwarding no\n    X11Forwarding no\n    PermitTTY yes\n' | \
  sudo tee /etc/ssh/sshd_config.d/99-shos.conf && sudo sshd -t && sudo systemctl reload ssh"
```
⚠ **The drop-in filename must sort AFTER the cloud-init files, hence `99-shos.conf`
(NOT `20-shos.conf`).** `sshd` includes `/etc/ssh/sshd_config.d/*.conf` in lexical
order and a `Match` block stays in effect until the next `Match` **or the end of
the whole config** — it does *not* reset at the end of an included file. The box has
`50-cloud-init.conf` (`PasswordAuthentication yes`) and `60-cloudimg-settings.conf`
after it; a `20-shos.conf` `Match User shos` would swallow those, giving `shos`
`PasswordAuthentication yes`. `99-shos.conf` sorts last so nothing follows it.
Verified after reload with `sudo sshd -T -C user=shos,host=localhost,addr=127.0.0.1`
(→ `passwordauthentication no`, `x11forwarding no`, `allowagentforwarding no`,
`permittty yes`) and the same for a non-shos user (globals intact).
(Reload the `ssh` unit on Ubuntu; `sshd` is an alias. Reload never drops sessions.)

### Revoking SH.OS access — one move
```bash
ssh tetapi "sudo usermod -L shos; \
  sudo truncate -s0 /home/shos/.ssh/authorized_keys; \
  sudo systemctl stop user-1002.slice; \
  sudo loginctl disable-linger shos"
# nginx: drop the vhost + reload:
ssh tetapi "sudo rm -f /etc/nginx/sites-enabled/shos.hellfiresol.com && sudo nginx -t && sudo systemctl reload nginx"
# full teardown also: sudo rm /etc/ssh/sshd_config.d/99-shos.conf && sudo systemctl reload ssh
#   sudo deluser --remove-home shos
```

### Disk — no quota (residual, monitor instead)
Root fs is `ext4` mounted **without** `usrquota`/`grpquota`, so a per-user disk
quota can't be set without remounting `/` + `quotacheck` (intrusive on prod —
out of scope). **Residual risk:** shos can fill the shared 50 GB disk. Mitigation
= monitoring, not enforcement: watch `sudo du -sh /home/shos` and overall `df -h /`
(disk is at 18% today). Revisit if SH.OS's footprint grows.

### Perimeter firewall — confirmed `ufw` (2026-09-19)
The inbound perimeter is an **on-host `ufw`** firewall — active, `default deny
(incoming)`, allowing only **22/80/443** (v4 + v6). Verified two ways: `sudo ufw
status verbose` on the box, and an external TCP probe of `164.90.235.66` from off
the droplet — only 22/80/443 answer; 3001, 3002, 5432, 6379, 8000, 8200 are all
filtered from the internet. So `tetapi-web` (`0.0.0.0:3001`) and `tetapi-mcp`
(`:::3002`) are private today because ufw drops them, and a stray shos bind on
`0.0.0.0:8200–8299` would likewise be blocked externally. Rootless docker (shos)
uses slirp4netns userspace networking and does **not** insert host iptables rules,
so it cannot punch through ufw the way rootful docker's `DOCKER` chain can.
(There is no `do-agent`/`doctl` on the box, so whether a *DigitalOcean Cloud
Firewall* also fronts the droplet isn't readable from the shell — it's optional
defense-in-depth on top of ufw, not required; ufw already enforces the policy.)

### Pre-existing isolation blockers — ✅ FIXED (5.9, 2026-09-19)
5.8's isolation checks surfaced three misconfigurations that predate shos (the
existing `hellfire` co-tenant could already exploit all three). **All three were
remediated in task 5.9 (2026-09-19)** and verified on-box:
`scripts/security/cotenant_check.sh` → **ALL ISOLATION ASSERTS PASS** (exit 0);
api/mcp/app health 200; celery worker reconnected + "ready".

- **S-18** — `/opt/tetapi/api/.env` was `644` (already `root:root`); now `600 root:root`.
  `.env` is rsync-excluded in `deploy.yml`, so the mode survives deploys.
- **S-19** — `/opt/tetapi/api` (+ `certs`) was `hellfire:hellfire`; now `root:root`,
  `certs` dir `700`. Confirmed `deploy.yml` rsyncs as `root@` so ownership survives.
  No `*.key.pem` exists on disk — the C2PA signing key is inline in `.env` (covered
  by S-18). ⚠ rsync `-a` may reset the **certs dir mode** to the repo's on the next
  deploy; the real protection is `.env`/ownership, not the dir bit.
- **S-20** — Redis (standalone `tetapi-redis` container) now requires `AUTH`
  (Option A, `--requirepass`; secret at `/root/tetapi-redis.pass`, `600`; volume /
  loopback publish / restart-policy preserved). `REDIS_URL` updated in `.env`;
  api + celery worker/beat restarted. From `shos`: `PING` → `-NOAUTH`.

The original runbook is kept **below as history**. Fixes were all low-risk —
tetapi-api/web/mcp run as **root**, so tightening perms/ownership doesn't break the
service:

### Pre-existing isolation blockers — TETA+PI-side remediation (NOT this session)
5.8's isolation checks surfaced three misconfigurations that predate shos (the
existing `hellfire` co-tenant can already exploit all three). They live inside
`/opt/tetapi` + TETA+PI service config, which this devops/co-tenant session must
**not** touch — they belong to a TETA+PI backend/devops task. Tracked as **S-18 /
S-19 / S-20** in `docs/security.md`. Verifier: `scripts/security/cotenant_check.sh`
(red now, green after the fixes). Recommended fixes (all low-risk — tetapi-api runs
as **root**, so tightening perms/ownership doesn't break the service):
```bash
# S-18: .env is 644 (world-readable) → every local account reads Fernet/JWT/DB creds
ssh tetapi "sudo chmod 600 /opt/tetapi/api/.env && sudo chown root:root /opt/tetapi/api/.env"
# S-19: /opt/tetapi/api + certs are owned by the hellfire co-tenant (trust inversion)
ssh tetapi "sudo chown -R root:root /opt/tetapi/api && sudo chmod 700 /opt/tetapi/api/certs"
#   ⚠ first confirm the deploy pipeline (deploy.yml) writes /opt/tetapi/api as the
#   same account it uses for web/mcp (already root:root) so rsync keeps working.
# S-20: redis answers unauthenticated on shared loopback 127.0.0.1:6379
#   Option A: set `requirepass` in the redis container + update REDIS_URL in .env.
#   Option B (cleaner, no secret to manage): drop the `127.0.0.1:6379:6379` port
#   publish in docker-compose so redis is reachable only on docker's internal
#   network — do this only if no host process (outside docker) needs redis.
```
**Broader hardening note (not blocking):** `tetapi-api`/`web`/`mcp` run as **root**
(`User=` unset). On a multi-tenant box, moving them to a dedicated non-root service
account would shrink blast radius — own TETA+PI backend task, out of 5.8 scope.

### Observation logged in 5.8 (owner's call, not actioned)
`apt-get install uidmap slirp4netns` surfaced a needrestart notice: an updated
kernel is installed but **not loaded** (pending from prior unattended-upgrades).
A reboot would load it (and blip all four subdomains). Not 5.8's call — flagged
for the owner to schedule if/when desired.

## Server resize runbook (9.1 capacity audit, 2026-07-13)

### Measured state (read-only audit, `ps`/`docker stats`/`du`/`journalctl`)
Current droplet: `s-1vcpu-512mb-10gb` (Frankfurt), ~$4/mo. 458 MB RAM, **379 MB
already in swap** — the box is paging under normal idle load, not just under
deploys.

Per-service RAM (RSS / cgroup, whichever is more accurate for that process):
| Service | RAM |
|---|---|
| `tetapi-api` (uvicorn, 1 worker) | ~45 MB |
| `tetapi-web` (Next.js standalone) | ~31 MB |
| `tetapi-mcp` (node) | ~21 MB |
| `nginx` | ~2 MB |
| `tetapi-postgres` (docker, pgvector/pg16) | ~17 MB (idle; data dir only 65 MB) |
| `tetapi-redis` (docker) | ~1 MB |
| **TETA+PI stack total** | **~116 MB** |
| dockerd + containerd (engine overhead) | ~57 MB |
| `goatcounter` (self-hosted analytics) | ~22 MB |
| `btc-robot` + `btc-funding` + `btc-telegram` (unrelated crypto bot, same box) | ~18 MB |
| `multipathd`, `fail2ban`, `systemd-journald`, misc system.slice | ~70 MB |
| **Non-TETA+PI baseline** | **~170 MB** |

No celery worker/beat is running (not built yet — matches roadmap, not a gap in
this audit). Redis is present but currently only used ad hoc. **Superseded
2026-07-25 (session 5.4): both now run** — see the systemd section above;
~44 MB RSS each, well within the headroom this audit measured.

**Conclusion: the TETA+PI stack itself is small (~116 MB). The box swaps because
~170 MB of fixed OS/tooling/unrelated-service overhead plus the stack leaves
almost no headroom in 458 MB total, before any real request load, embeddings
work, or a second uvicorn worker.** RAM is the binding constraint, not disk, for
day-to-day operation.

Disk — 6.7 GB / 8.7 GB (78%) used:
| Path | Size | What |
|---|---|---|
| `/usr` | 2.7 GB | base OS packages — largely fixed |
| `/var/lib/containerd` | 739 MB | active image layers (matches `docker system df`: pgvector 621 MB + nginx-alpine 94 MB + redis-alpine 58 MB = 772 MB) — not reclaimable garbage, these are the images in use |
| `/var/log/journal` | 268 MB | grows continuously, vacuumed before (9.1 audit did not vacuum — read-only) |
| `/var/lib/apt` + `/var/cache/apt` | 300 MB | apt metadata/cache, regrows after every `apt update` |
| `/opt/tetapi/venv` | 341 MB | Python deps (largest app-owned item) |
| `/opt/tetapi/{web,mcp,api}` | ~78 MB | build output + source |
| `/opt/tetapi/uploads` | 400 KB | media uploads — negligible today, will grow with 14.1 (Pi CAM) traffic |
| postgres data | 65 MB | small today, will grow with 5.1 (TWIRA embeddings — pgvector rows) |

Docker build cache is 0 B (already clean). No dangling images. Disk pressure is
OS/tooling overhead, not user data — but the 78% figure was already 87% once
before this audit period and was manually pruned back down; it will keep
climbing back with routine `apt`/journal growth, and 5.1 (embeddings) +
uploads growth will add real load on top.

### Decision: resize shape + cost
Owner asked for "roughly 2x." Two different DO resize mechanics:

- **RAM/CPU-only resize** (disk unchanged): reversible, ~1-2 min downtime,
  droplet must be powered off. Only available moving between plans that don't
  require a *larger* disk than current, or by explicitly choosing "resize
  without disk change" in the DO panel where offered.
- **Resize with disk growth**: disk can only grow, never shrink — **irreversible**.
  Downtime is longer (DO resizes the underlying volume), typically 5-10 min.

**Given disk is already at 78% and both known growth vectors (5.1 embeddings,
14.1 media uploads) land on this exact box, disk must grow too — a RAM-only
resize would leave the droplet one `apt upgrade` away from the same 87%
near-full state we already hit once.**

Recommended target: **`s-1vcpu-2gb`** (1 vCPU, 2 GB RAM, 50 GB SSD) — **$12/mo**.

Why not the literal cheapest "2x" (`s-1vcpu-1gb`, 1 GB RAM / 25 GB disk, $6/mo):
with ~170 MB fixed non-TETA+PI overhead already eating swap at 458 MB, 1 GB
gives the stack itself only ~800 MB of real headroom once overhead is
subtracted — enough to stop swapping today, but 5.1 (embeddings, model
inference) and any move to `--workers 2` on uvicorn would reopen the same
problem almost immediately. 2 GB gives real slack for both blocked tasks below
without a second resize in a few months. If cost is the deciding factor, 
`s-1vcpu-1gb` ($6/mo) is an acceptable *minimum* fix for the swap problem alone,
but does not durably unblock 5.1/5.3.

| Plan | vCPU | RAM | Disk | $/mo | Fixes swap? | Fixes disk headroom? |
|---|---|---|---|---|---|---|
| current | 1 | 512 MB | 10 GB | $4 | no | no |
| `s-1vcpu-1gb` | 1 | 1 GB | 25 GB | $6 | short-term only | yes, for now |
| **`s-1vcpu-2gb` (recommended)** | 1 | 2 GB | 50 GB | **$12** | yes, durably | yes, with room for 5.1 growth |
| `s-2vcpu-2gb` | 2 | 2 GB | 60 GB | $18 | yes | yes | 

`s-2vcpu-2gb` is not recommended now: nothing measured above is CPU-bound
(load average stays under 0.2 at idle; uvicorn runs 1 worker, single-threaded
bottleneck is RAM not CPU). Revisit CPU if 5.3 (split exec) or a multi-worker
uvicorn config later shows CPU contention in `systemd-cgtop`.

### Pre-flight
1. **Backup/snapshot first — no automated backup exists.** This audit
   confirmed: no `backups/` directory in the repo, no `doctl` on the server, no
   backup cron job. The **only** safety net is a manual DigitalOcean snapshot
   taken right before the resize:
   - DO Dashboard → Droplets → `ubuntu-s-1vcpu-512mb-10gb-fra1` → **Snapshots**
     tab → **Take Snapshot**. Wait for it to complete (few minutes; droplet can
     stay on for a snapshot, does not require power-off).
2. Confirm no in-flight deploy: `gh run list --limit 3 --workflow=deploy.yml`
   — all should show `completed`/`success`, nothing `in_progress`.
3. Pick a low-traffic window (check `stats.tetapi.dev` for the quietest hour;
   no established pattern yet, so default to late-night UTC).

### Merge-freeze coordination
Deploy is automatic on push to `main` (`.github/workflows/deploy.yml`). A
powered-off droplet fails that workflow (SSH step times out). **The manager
session must declare a merge freeze for the resize window** — announce it in
`docs/changelog.md` before starting, and hold any pending PR merges into `main`
until the post-resize verification below passes. This mirrors the existing
[[server-capacity]] convention (no sustained-load tasks / batch merges) already
in memory — resize is the same pattern, just a harder boundary.

### Exact steps (DO panel — owner must do this; not executable from an SSH session)
1. DO Dashboard → Droplets → `ubuntu-s-1vcpu-512mb-10gb-fra1`.
2. **Power off** (More → Power Off) — wait for status `OFF`.
3. Left sidebar → **Resize** → choose **`s-1vcpu-2gb`** ($12/mo, 2 GB RAM /
   50 GB disk). Confirm the disk-grow warning (irreversible).
4. Apply — DO resizes the volume and plan (5-10 min for disk growth).
5. **Power on**.
6. IP stays `164.90.235.66` — no DNS change needed.

Expected downtime for this shape (disk grows): **~5-10 minutes**, all four
subdomains down for the duration.

### Post-resize verification
```bash
ssh -i ~/.ssh/tetapi_ed25519 root@164.90.235.66 "free -h; df -h /; nproc"
curl -s https://tetapi.dev -o /dev/null -w '%{http_code}\n'
curl -s https://api.tetapi.dev/health
curl -s https://mcp.tetapi.dev/.well-known/mcp
curl -s -o /dev/null -w '%{http_code}\n' https://app.tetapi.dev
ssh -i ~/.ssh/tetapi_ed25519 root@164.90.235.66 "systemctl is-active nginx tetapi-api tetapi-web tetapi-mcp docker"
```
Expect: `free -h` shows ~2 GB total, swap near 0 used at idle; `df -h /` shows
~50 GB with usage % dropped roughly in half; all four subdomains 200; all
services `active`. Lift the merge freeze only after this passes.

### Rollback
Disk growth cannot be reverted. If the resize itself fails or the droplet
doesn't come back healthy:
1. Restore from the pre-flight snapshot (DO Dashboard → Snapshots → Restore) —
   recreates the droplet at the **old** 512 MB/10 GB spec with pre-resize state.
2. If only a service failed to restart post-resize (not a DO-level failure),
   no rollback needed — `systemctl restart tetapi-api tetapi-web tetapi-mcp
   nginx` and re-run verification; the underlying resize is unaffected by
   service-level restarts.

### What this unblocks
- **5.1 TWIRA embeddings** — needs headroom for embedding model
  inference/pgvector growth; currently deferred, RAM-constrained.
- **2.4 usage analytics** — deferred pending non-server-load option; a resized
  box removes the RAM reason to keep it off-server-only.
- **5.3 split exec** — roadmap already states explicitly: "🔴 deferred: needs
  9.1 server upgrade" — this resize is the literal blocker.
- **Redis #13** (known-issues, check-then-delete race) — fixing it properly
  means leaning on Redis harder (locks/atomic ops), adding RAM load the
  current box has no room for.
