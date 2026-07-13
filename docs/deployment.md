# Deployment

## Server
DigitalOcean droplet, Frankfurt, `164.90.235.66` (`ubuntu-s-1vcpu-512mb-10gb-fra1`
— 1 vCPU / 512 MB / 10 GB; this is why sustained-load tasks are deferred, see
roadmap 9.1). SSH:
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
  `tetapi-web` (Next.js standalone), `tetapi-mcp` (node, port 3002).
- **nginx**: serves landing from `/var/www/teta-pi/`, reverse-proxies the subdomains.
- **Python venv**: `/opt/tetapi/venv`. API code at `/opt/tetapi/api`, web at
  `/opt/tetapi/web`, mcp at `/opt/tetapi/mcp`.

## CI/CD — `.github/workflows/deploy.yml`
Trigger: push to `main`. Steps: build Next.js standalone → SSH setup →
rsync API / certs (public only) / Next output / MCP dist / landing → remote script:
patch Next standalone chunks, **patch `app-paths-manifest.json`** (must list every
route — add new pages here!), `pip install` runtime deps, `alembic upgrade head`,
restart `tetapi-api`, `tetapi-web`, `tetapi-mcp` (each health-checked).

⚠ When you add a Next.js page, add its route to the `app-paths-manifest.json` block
in the workflow or it 404s in production.

## Secrets — server `.env` only (`/opt/tetapi/api/.env`), never in git
`SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `RESEND_API_KEY`, `PII_ENCRYPTION_KEY`
(Fernet), `ENVIRONMENT=production`, plus optional `OPENAI_API_KEY`,
`NORTHDATA_API_KEY`, `OPENDATABOT_API_KEY`, `UK_COMPANIES_HOUSE_API_KEY`.
`api/certs/*.key.pem` (C2PA signing key) must **never** be synced/committed — the
rsync excludes it. Agent admin API key is stored at `/root/tetapi-agent-admin.key`.

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
the Next.js layout and every landing page.

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
this audit). Redis is present but currently only used ad hoc.

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
