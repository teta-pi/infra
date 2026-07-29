# Handoff: TETA+PI search — home and result set

## Overview
Two pages of the search flow, in the same visual language as the approved user page
("Grid of record"): verification lives on the **top edge**, evidence is always a **square tile**,
and every machine-readable value is set in mono.

1. **Home** — the query line *is* the page. No hero, no feature grid, no marketing. Nav, ~520px of
   air, one input on a hairline rule, one mono line of registry state. That restraint is the point:
   the product's promise is signed evidence, not persuasion.
2. **Results** — entities ranked by the evidence they published. Each row shows its attestation
   seals, a trust badge, a short answer paragraph, and expandable square evidence blocks. Entities
   whose claims are text-only declarations rank last and say so. Unverified open-source mentions are
   withheld behind an explicit action.

## About the design files
`Search.dc.html` is a **design reference written in HTML** — a prototype of the intended look and
behaviour, not production code to copy. Recreate it inside the target codebase with its own
components, styling approach and data layer. `support.js` is the prototyping runtime needed only to
open the file in a browser (`sc-for`, `sc-if`, the `Component` logic class) — do not port it.

## Fidelity
**High fidelity.** Colors, type sizes, spacing and states are final; exact values below and in the
HTML source. Both pages ship with a 390px mobile board.

## Screens

### 1. Home — desktop (1180px board)

| # | Region | Spec |
|---|--------|------|
| 1 | Nav | `12px 26px`, bottom border `1px #E2DCF0`. Θ (`#6B3FA0`, 20px/600) `+` (14px/300) π (`#E8640C`, 18px/600); right: `Search · My page · Settings` 13.5px `#4A3F6B` + `Claim your page` button (`#6B3FA0`, radius 4px) |
| 2 | Query field | Centered block, container `height:520px`, field `max-width:720px`. **No box** — a single `border-bottom:1.5px solid #1A1035`. Left: 14px circle outline `#9088B0` (the query marker), then the query in mono 19px `letter-spacing:-0.3px`, then a 2×23px caret `#6B3FA0` blinking 1s `step-end`. Right, baseline-aligned: `SEARCH ↵` in mono 11px, tracking 1.4px, uppercase, `#6B3FA0` |
| 3 | Under-rule line | `margin-top:14px`, mono 10.5px `#9088B0`: `signed evidence only · 48,201 entities · 1,204,776 blocks`; right side a link to an example result set |

That is the entire page. Nothing below the fold.

The prototype types the demo query out at 42ms/char and stops (`clearInterval`); in production this
is a real `<input>` — keep the caret, the hairline rule and the mono face, drop the animation.

### 2. Home — mobile (390px)
Nav collapses to the wordmark + a mono `claim page` link. Field block `height:420px`, same hairline
rule, query 14px mono, `SEARCH ↵` 10px. Registry line wraps to two mono lines.

### 3. Results — desktop (1180px board)

| # | Region | Spec |
|---|--------|------|
| 1 | Nav with inline search | `12px 26px`. Wordmark, then the query field as a `1px #E2DCF0` box with a filled `Search` button; `My page` on the right |
| 2 | **Evidence filter bar** (top edge) | 4 equal cells + a 200px count cell, `14px 20px`, bg `#FBFAFD`, bottom border. Each cell: seal glyph 12px + mono 11.5px label + count right-aligned `#9088B0`. Selected: bg `#F4F0FB`, `box-shadow: inset 0 -2px 0 0 #6B3FA0`. Filters: `all results · full chain · partial chain · declared only` |
| 3 | Result rows | `24px 34px 26px`, bottom border; hover bg `#FBFAFD`, expanded row bg `#FBFAFD` |
| 4 | Unverified tail | `22px 34px 24px`, bg `#FBFAFD`. Dashed 11px circle + `4 UNVERIFIED MENTIONS WITHHELD`, explanation, `Show unverified` outline button |

#### Result row
- 72×72 avatar tile (1px border, diagonal stripe placeholder).
- Name 22px/700 `-0.7px` (hover `#6B3FA0`), handle chip in mono outline, entity type in mono 10px
  uppercase `#9088B0`.
- Attestation line: each seal as glyph + mono label (`registry`, `c2pa`, `btc:ts`), then the trust
  badge — outlined mono 10px whose color encodes strength: 3 seals `#6B3FA0` (`L3 media-backed`),
  2 seals `#E8640C` (`L2 partial chain`), 1 seal `#9088B0` (`L1 declared only`) — then meta
  (`6 blocks · 318 agent lookups / 30d`).
- Answer paragraph 14.5px `#4A3F6B`, `max-width:660px`, `text-wrap:pretty` — a factual summary of
  *which blocks matched*, never a generated opinion.
- Actions, stacked right: `Open page` (filled) and `Show N blocks` / `Hide evidence` (outline).
- Evidence grid, revealed on toggle: `repeat(4,1fr)`, gap 10px, `padding-left:92px` so it aligns
  under the name, not the avatar.

#### Evidence tile (same component as on the profile, one size down)
Square, `1px solid #E2DCF0`, three rows: head `9px 11px` with `KIND` mono 10px + the block's own
seal glyphs (7px); media area with the diagonal stripe (`#241847/#1A1035` ink variant for
video/stream, label `#C9B8E8`); foot `10px 11px 11px` with title 12.5px/600 and meta mono 9.5px.
Hover border `#6B3FA0`. Click opens the block modal.

#### Block modal
Identical to the profile's: 600px panel, scrim `rgba(26,16,53,0.55)` + `blur(3px)`, header
`ENTITY NAME · KIND`, 190px media placeholder, title 21px/700, description, then a 2-column fact
grid — `type`, `signature`, `captured`, `attestations` — and `Verify chain` / `Open entity page`.

### 4. Results — mobile (390px)
Search field in the header with a compact `Go` button; filter bar scrolls horizontally; each result
is avatar + name + seal glyphs + trust label, a short answer, and a 2-up square evidence grid
(first two blocks).

## Interactions & behavior
- **Filter** — client-side in the prototype; server-side facet in production. Counts must come from
  the same query, not be recomputed on the client.
- **Expand / collapse evidence** — per row, first result expanded by default.
- **Block modal** — opens from any evidence tile on either page.
- **Ranking rule (product logic, not decoration):** entities with a full signature chain outrank
  partial chains, which outrank declaration-only records. The trust badge must always state the
  reason. Never reorder by engagement or payment.
- **Withheld results** — unsigned open-source mentions are never mixed into the ranked list; they
  appear only after an explicit `Show unverified`, and must stay visually separated.
- Motion: caret blink 1s `step-end` only. Respect `prefers-reduced-motion`.

## State
```
query     : string
trust     : 'ALL' | 'FULL' | 'PARTIAL' | 'DECLARED'
expanded  : Record<entityId, boolean>
open      : { block, ownerName } | null
```
Per entity: `id, name, handle, type, marks[] (registry|c2pa|btc), trustLevel, blockCount,
agentLookups30d, answer, blocks[]`.
Per block: `id, kind (VIDEO|PHOTO|TEXT|AUDIO), title, meta, marks[], body, signature, mediaUrl`.
`trustLevel` and the filter facets are **derived from `marks`** server-side — never author them.

## Design tokens
Colors
```
ink / text        #1A1035        body text  #4A3F6B        muted / mono  #9088B0
primary purple    #6B3FA0  hover #5A3488   tint bg #F4F0FB   lilac line #C9B8E8
orange accent     #E8640C
border            #E2DCF0        inner hairline #F1EDF9
surface           #FFFFFF        raised #FBFAFD             canvas #F4F2F8
ink stripe        repeating-linear-gradient(45deg,#241847 0 6px,#1A1035 6px 12px)
light stripe      repeating-linear-gradient(45deg,#F1EDF9 0 6px,#FBFAFD 6px 12px)
modal scrim       rgba(26,16,53,0.55) + backdrop-filter: blur(3px)
```
Seal glyphs — CSS shapes, no icons
```
registry  square  radius 1px, filled #6B3FA0
c2pa      circle  radius 50%, transparent, 1.5px #6B3FA0
btc:ts    diamond radius 1px, filled #E8640C, rotate(45deg)
query marker      circle outline 1.5px #9088B0
```
Typography
```
UI    'Trebuchet MS','Segoe UI','Helvetica Neue',sans-serif
Mono  ui-monospace,'SF Mono',Menlo,monospace
query 19px mono -0.3px · entity name 22/700 -0.7px · modal h2 21/700 -0.6px
tile title 12.5/600 · answer 14.5/1.55 · labels 9.5–11.5 mono, tracking 0.3–1.6px
```
Spacing 4px base; section padding `34px` horizontal; grid gap `10px`; radius `4px` on buttons only —
everything structural is square. No shadows; depth is 1px borders plus `#FBFAFD`.

## Implementation notes
- The mono query spans must be **block-level flex children** (`display:block; flex:1; min-width:0;
  overflow:hidden; text-overflow:ellipsis`) — `text-overflow` does not apply to inline elements, and
  a long query will otherwise spill past a 390px viewport.
- Keep `SEARCH ↵` on one line (`white-space:nowrap`).
- All square tiles use `aspect-ratio:1` — do not substitute fixed heights.

## Assets
None. Avatars and media are diagonal-stripe CSS placeholders; seals are CSS shapes; the Θ+π
wordmark is text.

## Open questions
- Does the answer paragraph come from a template over matched blocks, or from a model? If a model,
  it needs its own provenance marker.
- Should `declared only` entities be excluded from the default result set instead of ranked last?
- Pagination or infinite scroll for large result sets — and how the filter counts behave across pages.
