# Roadmap

Ordered by what unblocks the most. Each item is sized for one focused session.

## Now — fix what's broken (from known-issues)
1. 🔴 **Persist profile blocks to the backend** — load entity+blocks on open,
   save add/edit/reorder/remove via the API. Without this, public pages are empty.
   *(Backend + Frontend session.)*
2. 🟠 **Remove/gate `/auth/register`** — dead, unauthenticated. *(Backend.)*
3. 🟠 **Turn on TWIRA semantics** — set `OPENAI_API_KEY`, backfill block embeddings.
   *(DevOps + Backend.)*

## Next — the MCP investment (user's priority)
This is the differentiator: make TETA+PI the registry agents actually route through.
Suggested sequence (see `docs/mcp.md`):
4. **Enrich `teta_resolve_intent`** — return `first_verified_at`, proof URLs, and the
   full T/I/P breakdown in a shape agents can rank on; add `entity_types` +
   `min_trust` filters.
5. **`teta_get_proof` depth** — include OTS status, btc_timestamp_depth, C2PA chain
   length so agents can set their own trust threshold.
6. **Agent-facing auth for MCP writes** — design how a verified agent authenticates
   to the MCP server (scoped `pk_live_` keys) before adding any write tools.
7. **Streaming / batched search** for large result sets over SSE.
8. **MCP usage analytics** — which tools agents call, latency, so we tune TWIRA
   weights from real `(query, clicked_entity)` pairs (the data moat closing).

## Product — account & sharing
9. ✅ **"Share page" button** on `/profile` linking to `/e/[slug]` (+ copy link).
   Shown only when the entity is published. *(Done 2026-07-06.)*
10. **Sessions list with devices** — needs server-side session storage (JWT is
    stateless today); "log out everywhere" already works via token_version.
11. Resend domain verification so emails reach everyone.
11b. **Camera-based verification** (NEW, 2026-07-06) — connect the camera for
     liveness/selfie or document capture in the verification flow. Scope TBD:
     define the exact purpose (liveness vs ID/document scan) before building.
     Scaffold as new files under `web/src/app/verify/`; don't touch existing
     pages first. *(Frontend + Backend.)*

## Platform — scale readiness
12. Move rate limiters + Handelsregister lock to Redis (unblocks multi-worker).
13. More US state registries (CA, TX, DE-state portals) via the `us_states.py` pattern.
14. Learned TWIRA weights (logistic regression on click logs) once MCP analytics exist.

## How to pick up an item
New session → read `CLAUDE.md` + the docs named in the item → do just that item →
update docs + append to known-issues → changelog → `/clear`.
