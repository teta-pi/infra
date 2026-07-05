# TETA+PI — Claude Working Agreement

Read this first, every session. It is the contract for how we build.

## What this project is
Trust Infrastructure for Digital Entities. Verified people, companies, APIs, AI
models, MCP servers and agents, discoverable by AI agents. Operated by **TetaPi
GmbH**, Frankfurt. Live: `tetapi.dev` (landing), `app.tetapi.dev` (Next.js),
`api.tetapi.dev` (FastAPI), `mcp.tetapi.dev` (MCP).

## Language
**Reason in English, reply to the user in Ukrainian.** Internal thinking, plans, and
reasoning happen in English; every message shown to the user is written in Ukrainian.
Code, identifiers, commit messages, and `docs/*` stay in English.

## Documentation is the source of truth
Before touching code, read the docs relevant to your task — not the whole repo.

| You are working on… | Read |
|---|---|
| anything | `docs/overview.md`, `docs/architecture.md` |
| the API / a route / a service | `docs/api.md`, `docs/architecture.md` |
| the database / a migration | `docs/database.md` |
| the MCP server | `docs/mcp.md` |
| registry verifiers | `docs/registries.md` |
| deploy / server / CI | `docs/deployment.md` |
| "why is it done this way" | `docs/decisions.md` |
| what to build next | `docs/roadmap.md` |
| a term you don't know | `docs/glossary.md` |
| a bug / weird behaviour | `docs/known-issues.md` |

## Session discipline (this is how we control token cost)
- **One session = one focused task** (e.g. "MCP: add teta_get_proof depth"). Not
  "backend + UI + docs" in one go.
- **Read only what the task needs.** Name the files. Do not scan the repo.
- **End every task by updating docs**: if behaviour or structure changed, update
  the relevant `docs/*.md`; if a rule changed, update this file; append a line to
  `docs/known-issues.md` if you found or fixed a bug.
- Then `/clear` and start the next task fresh.

## Coding rules
- **Match the surrounding code.** Same style, naming, comment density. No new
  frameworks or patterns without a note in `docs/decisions.md`.
- **Never commit secrets.** Keys live only in server `.env` (see
  `docs/deployment.md`). `api/certs/*.key.pem` must never be synced or committed.
- **Never touch production configs** (`.env` on the server, nginx, systemd)
  without saying so explicitly first.
- **Append-only tables stay append-only** (`verification_events`,
  `admin_audit_log`) — enforced by DB triggers; do not add UPDATE/DELETE paths.
- **Admin/support endpoints go through `require_admin`** and must write an
  `admin_audit_log` entry.
- Commits: end message with `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
  Author email is the GitHub noreply so activity shows on the user's account.
- Deploy is automatic on push to `main` (GitHub Actions). Verify on prod after.

## Changelog format (end of each task, in your final message)
```
Done:    <what shipped>
Changed: <files / behaviour>
Risk:    <what could break>
Next:    <the obvious next step>
```

## Relationship to the memory system
The Claude Code memory (`MEMORY.md` + memory files) is auto-loaded per session and
holds durable facts about the user and project. `docs/` is the deeper, in-repo
brain that any session reads on demand. Keep them consistent; docs are canonical
for anything code-related.
