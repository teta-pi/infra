# Entity Verification Rework — business ≠ registry

Owner-approved spec, 2026-07-12. Source of truth for tasks 4.1 → 1.3 → 1.4 / 3.4
(see `docs/roadmap.md`). Business entity creation is decoupled from official-registry
matching; registry match becomes one of several optional verification methods.

---

## SYSTEM (app.tetapi.dev — product UI, frontend + backend logic)

### 1. Entity creation — decouple from registry
Creating a business entity must NOT require or attempt a registry name-match. Any
brand name is creatable immediately, free, unverified (L0). Example this fixes:
"Google" the brand vs. "Alphabet Inc." the legal entity — currently a
registry-name-match at creation would fail or misfire for cases like this.

### 2. Verification — multiple independent optional methods
Replace the single "registry match" verification path with a choice of methods,
each an independent event with its own trust weight (feeds TWIRA's T-component
`source_weight`):

| Method | Mechanism | Status |
|---|---|---|
| Official Registry Match | Match legal name against Handelsregister / GLEIF / EU VAT | Existing — keep, becomes one option, not the only one |
| Business Email Control | Magic link to an email on the brand's own domain | Build now |
| Domain Ownership | DNS TXT or file-based check (same mechanism as the WordPress plugin) | Build now — already exists for the plugin, extend to all entities |
| Document Upload | Registration certificate / license / tax ID | **UI only for now** — visible, disabled, labeled "Coming soon." No backend/upload endpoint yet — wait until file-upload risk (validation, storage, review flow) is handled. |

### 3. Brand ↔ Legal Entity linking (the Google/Alphabet case)
Add the ability to link a brand entity to a verified legal entity instead of
forcing a name match:

```
Entity "Google" (type=brand)
  legal_entity_id → Entity "Alphabet Inc." (type=business, registry-verified)
```

The brand entity can inherit trust from the linked, verified legal entity. The
link is publicly disclosed on the profile (not hidden).

### 4. Data model changes
- `entities.legal_entity_id` — nullable, self-referencing FK
- `verification_events.event_type` — extend enum to cover the new methods
  (`email_verified`, `domain_verified`, `document_verified` — document type added
  now, not activated until backend ships)
- TWIRA `source_weight` — extend from the current registry/self-declared
  placeholder to cover all methods above, each with its own weight

---

## LANDING (tetapi.dev — public marketing / "about the project")
No changes needed from today's discussion. This is a backend/product-logic change,
not a positioning or messaging change — the existing landing copy ("Registry
attested," verification levels L1/L2/L3, etc.) still describes the concept
accurately. If/when the new verification methods ship in the product, the
landing's "How it works" and "Verification levels" sections may need a copy pass
to mention the additional methods (email/domain/document) — but that is a
separate, future task (10.x), not part of this change.

---

## Task breakdown & dependency order (manager)
1. **4.1 db** — migration: `legal_entity_id` FK + `event_type` enum extension.
   Append-only trigger on `verification_events` must stay intact.
2. **1.3 backend** — decouple creation (L0, no registry call); registry match
   becomes optional method; NEW: email-control (magic link on brand domain, reuse
   Resend/code infra) + domain ownership (reuse the WordPress-plugin DNS TXT/file
   check); brand↔legal link endpoint (+ public disclosure in profile payloads).
   Document upload: NOTHING in backend.
3. **1.4 backend** — TWIRA `source_weight` per method (small, after 1.3).
4. **3.4 frontend** — verification methods chooser UI (registry / email / domain
   active; document visible-disabled "Coming soon"), brand↔legal link UI, public
   disclosure on profile/public page.
Constraint: no new sustained server load (no new workers); all checks run in
request/existing task context.
