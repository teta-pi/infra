# TETA+PI docs — the project brain

Read these instead of scanning the repo. Any Claude session should be able to
recover full context from these files alone.

## Start here
- **[overview.md](overview.md)** — what the project is, in one page.
- **[architecture.md](architecture.md)** — how the pieces fit together.

## Reference (read the one your task touches)
- **[api.md](api.md)** — FastAPI routes, auth, services.
- **[database.md](database.md)** — tables, migrations, conventions.
- **[mcp.md](mcp.md)** — the MCP server and its tools.
- **[registries.md](registries.md)** — registry verifiers and routing.
- **[deployment.md](deployment.md)** — server, CI/CD, secrets, ops.
- **[analytics.md](analytics.md)** — GoatCounter setup, traffic data, plans for the back-office Analytics tab.

## Direction & memory
- **[roadmap.md](roadmap.md)** — what to build next, sized per session.
- **[changelog.md](changelog.md)** — running log of what shipped (manager reads this).
- **[decisions.md](decisions.md)** — why things are the way they are.
- **[known-issues.md](known-issues.md)** — bugs & constraints found in audit.
- **[glossary.md](glossary.md)** — project vocabulary.

## Running the project
- **[manager.md](manager.md)** — the orchestrator session that knows state + plan
  and generates tasks for worker sessions.

## Rules & workflow
Working rules live in the repo-root **[CLAUDE.md](../CLAUDE.md)** (auto-loaded each
session). The day-to-day operating procedure — chat naming, boot/close messages,
one-task-per-session — is in **[workflow.md](workflow.md)**.

## Keeping docs honest
When code changes, update the matching doc in the same session. If overview or
architecture shifts, note it in `decisions.md` with a date. Docs are canonical for
anything code-related; the Claude memory system holds user/project facts.
