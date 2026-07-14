# GTM Launch Materials — Draft Copy (owner reviews and posts)

Companion to [`gtm.md`](gtm.md) (the operational plan). This file holds the
actual copy for `13.2` §1.3 and §Phase 2 outreach. **Nothing here is posted,
sent, or published by a session — Bob reviews and executes every item
himself**, per the owner-gating rule in `gtm.md`.

Status: DRAFT ONLY.

---

## 1. Show HN post

**Timing dependency — do not post before this is true:** Phase 0 exit
criterion met — 6+ registry listings live (see the execution checklist in
`gtm.md`) and TetaPi GmbH self-verified with a public proof page. Posting
before listings are live undercuts the post itself (an agent reading it
would find nothing to point at yet).

**Title:**
```
Show HN: TETA+PI – a verified entity registry for AI agents
```

**Body draft:**
```
Hi HN — I'm Bob, one of the founders of TETA+PI.

AI agents are starting to call APIs, hire other agents, and transact with
businesses they've never seen a human vet. Right now there's no cheap way
for an agent to answer "is this real?" before it acts on something — a
merchant, an MCP server, a person, an API.

TETA+PI is a registry that answers that question. Anyone — a person, a
company, an API operator, an MCP server, an AI model — can get verified at
one of three levels (basic claim, documented ownership, cryptographically
proven) and the result is a public, checkable proof page: what was
verified, how, and when. We use C2PA content credentials and Bitcoin
OpenTimestamps so the proof doesn't depend on trusting us after the fact —
you can verify the timestamp independently.

We built an MCP server (`mcp.tetapi.dev`) so agents can query this
directly instead of scraping a webpage: `teta_verify_entity`,
`teta_search`, `teta_verify_endpoint`, and a few others. We also
self-verified — TetaPi GmbH, and both founders, are themselves the first
verified entries in our own registry. Proof page: [link to our L2 proof
page].

This is early. No funding, no ad spend — the plan is to be useful enough
that agents route to it on their own. Feedback, especially "here's where
this breaks," is very welcome.

Repo: [github link] · MCP server: mcp.tetapi.dev · tetapi.dev
```

**Tone notes:** factual, first-person, no hype adjectives ("revolutionary",
"game-changing"). Leads with the problem an agent actually has, not with
the company. Matches the "honest, factual" instruction in `gtm.md` §1.3.

---

## 2. MCP Discord announcement

Shorter, community-appropriate register for the official MCP Discord
(assume a `#show-and-tell` or equivalent channel — Bob to confirm channel
name before posting). Same timing dependency as the Show HN post: after
Phase 0 listings are live.

**Draft:**
```
Hey all — sharing something we've been building: TETA+PI
(mcp.tetapi.dev), an MCP server for verifying who/what you're talking to
before an agent acts on it. Businesses, people, APIs, other MCP servers —
each gets a public proof page (C2PA + Bitcoin OTS timestamping, so the
proof doesn't rely on trusting us after the fact).

Tools: teta_search, teta_verify_entity, teta_verify_endpoint,
teta_get_proof, teta_get_profile, teta_verify_claim, teta_resolve_intent.

We're the first verified entity in our own registry (dogfooding), and
we're listed on [registry.modelcontextprotocol.io / Smithery / Glama —
whichever are live at post time]. Happy to answer questions or take
feedback on the tool descriptions — trying to make them agent-query
friendly rather than marketing copy.

tetapi.dev if you want the human-facing version.
```

**Tone notes:** no pitch-deck language, leads with what it does and the
tool names (this is a technical audience that will judge by the tool
schema), ends with an invitation for feedback rather than a call to action.

---

## 3. Phase 2 outreach message — TEMPLATE ONLY (not sent to anyone)

Per `gtm.md` §Phase 2, this is the exact guardrail language, verbatim,
turned into a fillable template. **One message per author, no follow-up.**
Not automatable — Bob sends each one himself after reviewing the specific
claimed entity, or explicit per-message permission is required if a
session ever drafts one for a specific target.

**Channel:** GitHub issue on the server's repo, or email if no repo/issue
tracker.

**Template:**
```
Subject: Your MCP server has a pre-verified profile on TETA+PI

Hi [author/maintainer name],

We found and attested your public data — take control of it.

TETA+PI (tetapi.dev) is a verification registry for AI agents to check
who/what they're talking to. We pulled [server name]'s public metadata
(GitHub org, domain, npm package — nothing private, nothing you haven't
already published) and created a pre-verified profile:

  [link to profile]

This is not us claiming to have registered you or speak for you — it's a
snapshot of what's already public, timestamped and attested. Claiming the
profile is free and takes under a minute; once claimed you get a verified
badge for your README and basic analytics on which agents are checking
you out.

If you'd rather this didn't exist, one click removes it — no form, no
waiting: [instant opt-out/removal link].

This is a one-time message — we won't follow up.

— Bob, TETA+PI
```

**Guardrails this template must never drift from** (verbatim from
`gtm.md`, restated here so the template stays correct if edited later):
- Public data only.
- Instant claim AND instant opt-out/removal — both links must work before
  any message goes out.
- Tone: "we found and attested your public data — take control of it."
  Never "we registered you."
- One message per author. No follow-up spam.

---

## 4. Launch checklist — Phase 0 → public announcement

Ties Phase 0 completion (execution checklist in `gtm.md`) to when the
Show HN/Discord posts (§1 and §2 above) and the WordPress plugin + MCP
registry submissions should be announced **together**, so the launch reads
as one coordinated moment instead of a trickle.

**Gate — do not post §1/§2 until all of these are checked** (mirrors the
Phase 0 exit criterion in `gtm.md`, repeated here for convenience — update
both places if either changes):

- [ ] Official MCP Registry listing live (`registry.modelcontextprotocol.io`)
- [ ] Smithery listing live
- [ ] Glama listing claimed
- [ ] mcp.so + PulseMCP listed/claimed
- [ ] awesome-mcp-servers PR merged
- [ ] GitHub MCP Registry submission live
- [ ] TetaPi GmbH self-verified L2, public proof page reachable
- [ ] Bob V. + Mykhailo M. verified as person entities
- [ ] `llms.txt` live
- [ ] `agent.json` bumped to v1.1.0 (landing + app)
- [ ] Tool descriptions rewritten (agent-query-optimized)

**Then, same-week bundle (verbatim intent from `gtm.md`: "everywhere and
self-verified" before outreach — launch as one signal, not a drip):**

1. WordPress plugin published to wordpress.org (`12.2`) — confirm live and
   installable before announcing.
2. Post Show HN (§1 above).
3. Post MCP Discord announcement (§2 above), same day or next.
4. Mention the WordPress plugin in both posts as "also available for
   WordPress/WooCommerce sites" — one launch narrative covering both the
   agent-facing (MCP) and site-owner-facing (plugin) arms, per the
   dual-arm structure in `gtm.md` §07.
5. Do NOT start Phase 2 outreach (§3 above) the same week — `gtm.md`'s
   sequencing rule is legitimacy before outreach; give the listings/posts
   at least a few days to settle before touching the top-500 dataset.

**Explicitly out of scope for this checklist:** the top-500 dataset script
(`13.3`) and the bulk pre-verification import (`1.11`) — those are
separate session tasks per `gtm.md`, not part of the announcement itself.
