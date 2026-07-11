# Workflow — how to run development across sessions

The operating procedure for building TETA+PI with Claude. Goal: keep every session's
context small so token cost stays low and work stays focused.

## Core rule: 1 chat = 1 roadmap task
Not a permanent "backend chat". A separate chat per concrete `docs/roadmap.md` item.
When the task is done, close the chat (`/clear` or new). A long-lived chat re-grows
history — the exact problem this avoids. A "direction" is a **tag in the title**, not
a chat.

## Chat naming — numbered directions, sub-numbered tasks
Directions have FIXED numbers; every task gets a sub-number within its direction.
The owner always knows how many session groups exist and where a task lives.

| № | Direction | Covers |
|---|---|---|
| 1 | backend | API, services, auth, TWIRA, registries |
| 2 | mcp | MCP server, tools |
| 3 | frontend | Next.js web app + landing |
| 4 | db | migrations, schema |
| 5 | devops | deploy, server, keys, repo structure |
| 6 | manager | orchestration (this numbering lives in roadmap) |
| 7 | github | GitHub org/repos: Actions, branch protection, PR hygiene, org profile, releases |

```
TTPI · <n> <direction> · <n.m> <what we do>
```
Examples:
- `TTPI · 1 backend · 1.1 fix private-block leak`
- `TTPI · 2 mcp · 2.1 get_proof depth`
- `TTPI · 3 frontend · 3.1 web copy sync`
- `TTPI · 5 devops · 5.1 enable TWIRA embeddings`

The direction tells Claude which `docs/*.md` to read; the task number maps to
`docs/roadmap.md`. Branches: `session/<n.m>-<slug>` (e.g. `session/2.1-get-proof-depth`);
worktrees: `ttpi-wt/<n.m>-<slug>`.

## Isolation: one worktree + one branch per session (PR into main)
`teta-pi/platform` is a **monorepo** (api + web + mcp + landing as folders — there is
only ONE git repo). When several sessions run at once they must NOT share the `main`
working tree, or `git status` mixes everyone's uncommitted files and pushes turn into
rebase soup. So each session gets its **own git worktree on its own branch**, and lands
via a **PR into `main`** (deploy runs on merge to `main`, not on branch pushes).

Manager creates the worktree before launching a session:
```
git worktree add /Users/bobbob/BOB/SERVER/ttpi-wt/<n.m>-<slug> -b session/<n.m>-<slug>
```
The worker session is then launched **with that worktree dir as its project root** and
works only there. Branch naming: `session/<n.m>-<slug>` (e.g. `session/2.1-get-proof-depth`).

Session close (worker):
```
git add <only my scoped files by name>   # never git add -A (shared changelog etc.)
git commit -m "<msg>\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git push -u origin session/<n.m>-<slug>
gh pr create --fill --base main
```
Manager reviews the PR, merges to `main` (→ auto-deploy), then removes the worktree:
```
git worktree remove /Users/bobbob/BOB/SERVER/ttpi-wt/<slug>
git branch -d session/<n.m>-<slug>    # after merge
```

## Session boot message (copy-paste)
```
Work in this worktree only: /Users/bobbob/BOB/SERVER/ttpi-wt/<n.m>-<slug> (branch session/<n.m>-<slug>).
Read CLAUDE.md + docs/<the files this task needs>.
Task: <one sentence>.
Scope: only <files/dirs>. Don't touch anything else.
End: commit ONLY your scoped files by name, push the branch, open a PR into main.
```
Example:
```
Work in this worktree only: /Users/bobbob/BOB/SERVER/ttpi-wt/3.3-camera (branch session/3.3-camera-capture).
Read CLAUDE.md + docs/roadmap.md + docs/architecture.md.
Task: scaffold camera capture → C2PA + OTS (plan first, then wire).
Scope: only new files under web/src/app/capture/. Don't touch anything else.
End: commit your files by name, push session/3.3-camera-capture, open a PR into main.
```
This keeps each session's context small (token saving), isolates its files, and lands
work through review instead of racing on `main`.

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
| github | org, Actions, protection, releases | deployment.md (CI section) |
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
