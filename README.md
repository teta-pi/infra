# TETA+PI Infra

Canonical docs + deploy configuration for **TETA+PI** — Trust Infrastructure
for Digital Entities. This repo holds no application code.

## What lives here
- `docs/` — canonical, cross-cutting docs: overview, architecture, decisions,
  roadmap, changelog, glossary, known-issues, deployment, security, GTM,
  verification rework. (Component-specific docs — API routes, MCP tools —
  live with their component repo.)
- Root `CLAUDE.md` — the coding rules / working agreement referenced by every
  component repo's thin pointer `CLAUDE.md`.
- `deploy/` — nginx configs, `deploy.sh`, server runbooks.
- `docker-compose*.yml`, `.env.example`.

## Where the code is
TETA+PI split from a monorepo into separate repos 2026-07-13 (see
`docs/decisions.md`). The running system:

| Repo | Runtime | Live at |
|---|---|---|
| [`teta-pi/api`](https://github.com/teta-pi/api) | FastAPI · PostgreSQL 16 + pgvector | api.tetapi.dev |
| [`teta-pi/web`](https://github.com/teta-pi/web) | Next.js 15 | app.tetapi.dev |
| [`teta-pi/mcp`](https://github.com/teta-pi/mcp) | TypeScript MCP server | mcp.tetapi.dev |
| [`teta-pi/landing`](https://github.com/teta-pi/landing) | static HTML | tetapi.dev |

`teta-pi/platform` is the retired pre-split monorepo, kept read-only for
history.

## License
MIT © 2026 TETA+PI · tetapi.dev
