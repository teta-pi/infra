# Overview

## What it is
**TETA+PI (Θ+π)** — Trust Infrastructure for Digital Entities. A cryptographic
verification registry that lets entities prove who they are so AI agents can find
and trust them.

## The idea in one sentence
Verified entities are visible in agent search; unverified ones don't exist on the
Agent Internet.

## Who it verifies
People, companies, brands, domains, websites, APIs, AI models, MCP servers,
software, repositories, AI agents, autonomous entities. Journalists and artists
are first-class too (C2PA-signed content).

## The three layers of trust
1. **Registry** — cross-check against official government/industry registries.
2. **C2PA** — verified entities sign their content; anyone can verify the signature.
3. **Bitcoin** — each verification record is timestamped on the Bitcoin blockchain
   (OpenTimestamps), giving a permanent, first-verified-at proof.

Agents reach all three via **MCP** (Model Context Protocol).

## Core modules
| Module | Dir | Runtime | URL |
|---|---|---|---|
| Landing | `landing/` | static HTML + nginx | tetapi.dev |
| App | `web/` | Next.js 15 + TypeScript | app.tetapi.dev |
| API | `api/` | FastAPI + PostgreSQL 16 + pgvector | api.tetapi.dev |
| MCP server | `mcp/` | TypeScript (@modelcontextprotocol/sdk) | mcp.tetapi.dev |
| Workers | `api/app/workers/` | Celery + Redis | (background) |

## Signature algorithm — TWIRA
Ranking for agent search is `TWIRA = α·T + β·I + γ·P`:
- **T** Trust: verification level × recency decay × source weight
- **I** Intent: semantic (pgvector) match of query to the entity's public blocks
- **P** Provenance: Bitcoin timestamp depth + C2PA chain length + endpoint uptime

Ranking is earned through verification history, not bought with ads.

## Company
TetaPi GmbH · Frankfurt am Main, Germany · founded 2026.

## Stack at a glance
FastAPI · PostgreSQL 16 + pgvector · Redis · Celery · Next.js 15 · TypeScript ·
MCP TS server · nginx · Docker (Postgres/Redis) + systemd (api/web/mcp) ·
DigitalOcean Frankfurt · GitHub Actions CI/CD.
