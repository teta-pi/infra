# TETA+PI Platform

> Verified entity registry for Agent Internet.
> Create a profile. Add blocks. TETA+PI verifies the rest.

## What it does

Any entity — business, journalist, creator, organization — registers a verified profile. TETA+PI automatically structures, categorizes, and verifies it. AI agents discover verified entities through the Intent Graph via MCP.

## Stack

- **Frontend:** Next.js 15 · TypeScript · Tailwind CSS
- **Backend:** FastAPI · PostgreSQL 16 · pgvector
- **Verification:** C2PA · Bitcoin OpenTimestamps
- **Protocol:** MCP server · Intent Graph · `/.well-known/agent.json`
- **Infrastructure:** DigitalOcean · Nginx · Cloudflare · Full (strict) SSL

## Architecture

```
web/              Next.js 15 frontend
api/
  routers/        entity · blocks · verification · mcp · endpoint_verification
  intent_graph/   schema · resolver
  models/         entity · block · verification
mcp/              TypeScript MCP server (HTTP + SSE · port 3002)
```

## Live

tetapi.dev — production deployment

## License

MIT © 2026 TETA+PI · tetapi.dev
