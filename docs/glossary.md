# Glossary

- **Entity** — anything TETA+PI verifies (person, company, brand, domain, website,
  API, AI model, MCP server, software, repository, AI agent, autonomous entity).
  Stored in the `businesses` table (historical name).
- **Block** — a unit of content on an entity's profile (text, document, media),
  optionally C2PA-signed and embedded (pgvector) for search.
- **Trust level** — `none | registry | partial | full | live`, computed from what an
  entity has proven. Surfaced as `registry_attested` / `c2pa_verified` /
  `btc_confirmed`.
- **TWIRA** — the ranking algorithm: `α·T + β·I + γ·P` (Trust, Intent alignment,
  Provenance). Query-time ranking for agent search. Code in `api/app/twira/`.
- **Temporal Moat** — the append-only `verification_events` chronology, Bitcoin-
  anchored, that can't be rewritten. `first_verified_at` = earliest confirmed event.
- **C2PA** — Coalition for Content Provenance and Authenticity; the standard used to
  cryptographically sign content so its origin is verifiable.
- **OTS / OpenTimestamps** — the mechanism used to timestamp verification records on
  Bitcoin (calendars, not OP_RETURN).
- **MCP** — Model Context Protocol; how AI agents call our `teta_*` tools.
- **Claim** — a `/claim` submission; doubles as the waitlist entry and, once
  verified, the entity. `ready_to_pay` is the key traction metric.
- **Segment** — `builder | operator | consumer` classification on an entity.
- **Registry verifier** — a class under `api/app/services/registry/` that queries one
  official/commercial company register.
- **Back office** — the `/admin` dashboard (users, claims, entities, audit log) gated
  by `require_admin`.
- **pk_live_…** — a personal/agent API key authenticating directly (not JWT).
- **token_version** — per-user counter in the JWT `ver` claim; bumping it invalidates
  all previously issued tokens.
- **EncryptedString** — SQLAlchemy type that stores PII Fernet-encrypted at rest.
