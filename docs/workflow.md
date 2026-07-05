# Workflow — how to run development across sessions

The operating procedure for building TETA+PI with Claude. Goal: keep every session's
context small so token cost stays low and work stays focused.

## Core rule: 1 chat = 1 roadmap task
Not a permanent "backend chat". A separate chat per concrete `docs/roadmap.md` item.
When the task is done, close the chat (`/clear` or new). A long-lived chat re-grows
history — the exact problem this avoids. A "direction" is a **tag in the title**, not
a chat.

## Chat naming
```
TTPI · <direction> · <what we do>
```
Examples:
- `TTPI · backend · profile blocks persistence`
- `TTPI · backend · remove /auth/register`
- `TTPI · mcp · enrich resolve_intent`
- `TTPI · devops · enable TWIRA embeddings`
- `TTPI · frontend · share page button`

The direction (`backend / frontend / mcp / db / devops / docs`) tells Claude which
`docs/*.md` to read.

## Session boot message (copy-paste)
```
Read CLAUDE.md + docs/<the files this task needs>.
Task: <one sentence>.
Scope: only <files/dirs>. Don't touch anything else.
```
Example:
```
Read CLAUDE.md + docs/known-issues.md + docs/api.md + docs/database.md.
Task: profile page must persist blocks to the DB and load them on open.
Scope: web/src/app/profile/page.tsx, web/src/lib/api.ts, api/app/api/routes/blocks.py.
```
This makes Claude read only what's needed (token saving) and not sprawl across the repo.

## Session close
Claude ends with the `CLAUDE.md` changelog (`Done / Changed / Risk / Next`) and
updates the matching `docs/*.md`. Your move: if good → `/clear`, next task. If the
task is big → split it across two sessions; don't drag one out.

## Directions that actually apply (not 7 generic agents)
| Direction | Covers | Docs Claude reads |
|---|---|---|
| backend | API, services, auth, TWIRA | api.md, database.md |
| frontend | Next.js pages, UI | architecture.md |
| mcp | MCP server, tools | mcp.md |
| db | migrations, schema | database.md |
| devops | deploy, server, keys | deployment.md |
| docs | doc updates | README.md |
Registries and workers are backend sub-topics — no separate direction.

## Subagents — when yes / no
- **Yes** — parallel read/search across code ("find every use of token_version").
- **No** — don't stand up a permanent "team of 6 agents". In Claude Code each
  subagent spawn starts cold and re-reads context — more expensive than a clean chat
  with targeted reads. The "PM orchestrating agents" model is an API pattern, not a
  Claude Code one. ~90% of tasks: clean chat + docs is enough.

## The archive chat
The original build chat: don't delete, don't code in it anymore. Rename it
`TTPI · MASTER (archive)`. Everything important now lives in `docs/` and the memory
system; open it only to look up a specific old decision.

## Task queue = docs/roadmap.md
Pick the top open item, run it in one session per the boot template, update docs,
`/clear`. The roadmap is ordered so the top item unblocks the most.
