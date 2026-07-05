# Deployment

## Server
DigitalOcean droplet, Frankfurt, `164.90.235.66`. SSH:
`ssh -i ~/.ssh/tetapi_ed25519 root@164.90.235.66`.

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
