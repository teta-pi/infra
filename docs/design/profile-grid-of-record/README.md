# Handoff: TETA+PI user page — "Grid of record"

## Overview
Redesign of the authenticated user's page (`app.tetapi.dev/profile`) and its public counterpart.
The page presents a verified entity (business, journalist, artist) as a **ledger of signed statement
blocks**. Two things drive the design:

1. **Verification is the top edge of the page.** The three attestation seals
   (`registry:attested`, `c2pa:verified`, `btc:ts:confirmed`) sit in a full-width bar directly under
   the app nav — above the name, avatar and everything else. Trust is read before identity.
2. **Every statement is a strict square.** A block is a claim in any medium (video, photo, text,
   audio). All blocks share one 1:1 tile so the page reads as a register of record, not a feed.

One page, three modes: **Edit** (owner), **Visitor** (public view), **Agent** (machine view / MCP
response). Same data in all three.

## About the design files
The files in this bundle are **design references created in HTML** — prototypes of the intended look
and behaviour, not production code to copy. The task is to **recreate them inside the target
codebase** (React/Next, Vue, etc.) using its existing components, styling approach and data layer.
If no front-end environment exists yet, pick the framework that best fits the project and implement
there. The prototype's internal runtime (`support.js`, the `Component` logic class, `sc-for`/`sc-if`)
is a prototyping runtime — do not port it.

## Fidelity
**High fidelity.** Colors, type sizes, spacing, borders, hover and drag behaviour are final and
should be matched closely. Exact values are listed below and are readable in the HTML source.

## Screens / views

### 1. User page — desktop (1180px board)
Purpose: owner curates their claims; visitor evaluates trust; agent reads structured data.

Vertical order, top to bottom:

| # | Region | Height / padding | Notes |
|---|--------|------------------|-------|
| 1 | App nav | `12px 26px`, bottom border `1px #E2DCF0` | Θ (`#6B3FA0`, 20px/600) `+` (14px/300) π (`#E8640C`, 18px/600) on the left; `Search · My page · Settings` (13.5px `#4A3F6B`) and a `Save` button on the right |
| 2 | **Attestation bar** | 3 equal cells + a 210px status cell, `15px 20px`, bg `#FBFAFD`, bottom border | Per cell: 14px seal glyph, token (11.5px mono `#1A1035`), detail (9.5px mono `#9088B0`), right-aligned `✓ state` in the seal color. Hover: cell bg `#F4F0FB`. Status cell: 6px orange dot pulsing (`tp-pulse` 2.4s) + `re-checked hourly / 12 JUN 2026 · 09:41Z` |
| 3 | Identity | `32px 34px 24px`, flex gap 28px | 104×104 avatar tile (1px border, diagonal stripe placeholder); `h1` 34px/700, `letter-spacing:-1.1px`; handle chip `tetapi.dev/yasna` in a mono outline; description 15.5px `#4A3F6B`, `max-width:640px`; mode switch top-right |
| 4 | Facts strip | 4 equal cells, `16px 34px 17px`, 1px borders top/bottom and between | value 21px/700, label 10px mono uppercase, tracking 1.2px, `#9088B0` |
| 5a | **Verification & publishing** *(Edit mode only)* | `22px 34px 0`, 6-up grid, gap 10px | Section label `VERIFICATION & PUBLISHING` (11px mono, tracking 1.6px, `#6B3FA0`). Six square action tiles: `Registry · Email · Domain · Document · Legal · Publish` |
| 5 | Ledger controls | `22px 34px 15px` | `STATEMENTS` label (11px mono, tracking 1.6px, `#6B3FA0`) + media filter chips; right side: contextual hint (10.5px mono `#9088B0`) |
| 6 | **Square ledger** | `grid-template-columns: repeat(4,1fr)`, gap 10px (tweakable 0–28), padding `0 34px 34px` | Tiles are `aspect-ratio:1`. Last tile in Edit mode is the dashed "ADD BLOCK" tile |
| 7 | Visitor footer *(Visitor mode)* | `22px 34px 24px`, bg `#FBFAFD`, top border | Trust sentence + `Contact farm` (filled) and `Verify all blocks` (outline) buttons |
| 8 | Agent panel *(Agent mode)* | bg `#1A1035`, `26px 34px 30px` | Mono response listing, keys `#9088B0`, values `#ffffff`, status words `#E8640C` |

Regions 7 and 8 replace each other; neither shows in Edit mode.

#### Statement tile (the core component)
Square, `1px solid #E2DCF0`, white, `overflow:hidden`, three stacked rows:

- **Head** — `11px 13px`, bottom border `1px #F1EDF9`. Left: `NN · KIND` (10.5px mono `#9088B0`).
  Right: the tile's own seal glyphs, 8px, gap 4px — only the attestations this block actually has.
- **Media** — fills remaining height. Light blocks: `repeating-linear-gradient(45deg,#F1EDF9 0 6px,#FBFAFD 6px 12px)`.
  Video/stream blocks use the ink variant `(#241847 / #1A1035)` with label color `#C9B8E8`.
  Centered mono label, e.g. `video source`, `plain text · no media`.
- **Foot** — `12px 13px 13px`, top border `1px #F1EDF9`. Title 14px/600, `line-height:1.3`,
  `text-wrap:pretty`; meta 10px mono `#9088B0`.
- **Hover overlay** — absolutely positioned, `rgba(26,16,53,0.93)`, `opacity` 0→1 over `.16s ease`,
  `pointer-events:none`. Top: seal state (`full chain` `#6B3FA0` / `partial` `#E8640C` /
  `unsigned` `#9088B0`, 9.5px mono uppercase tracking 1.4px) then signature + capture line
  (11px mono `#C9B8E8`, `word-break:break-all`). Bottom: the block description, 12.5px `#ffffff`.
- **Border on hover**: `#6B3FA0`.
- **Draggable** only in Edit mode; while dragging the source tile drops to `opacity:.3`.

#### Verification action tile
Low bar, fixed `height:56px`, `1px solid #E2DCF0`, white, horizontal: glyph (12–18px,
1.5px `currentColor` stroke) + stacked label 13px/600 `#1A1035` and status 9.5px mono.
States:
- **verified** — glyph and status in `#6B3FA0`, 6px purple dot at `top:10px; right:10px`.
- **in progress** (selected) — border and glyph `#6B3FA0` (`#E8640C` for Publish), bg `#F4F0FB`, status `in progress` in orange.
- **pending** — glyph and status `#9088B0`, plain border.
Hover: border `#6B3FA0`. Click selects the step; in production each opens its own verification flow
(registry lookup, email code, DNS TXT record, document upload, legal entity check, publish confirm).
Glyphs are CSS shapes, not icons: square (Registry), wide rect (Email), circle (Domain), tall rect
(Document), rotated square (Legal), filled circle (Publish) — swap for the codebase's icon set,
keeping the 18px / 1.5px stroke weight.

#### Add-block tile
Same square, `1px dashed #C9B8E8`, bg `#FBFAFD`, centered: `+` (28px/300 `#6B3FA0`),
`ADD BLOCK` (10.5px mono), `video · photo · text · audio` (9.5px mono `#9088B0`).
Hover: bg `#F4F0FB`, border `#6B3FA0`. Visible in Edit mode only.

#### Block detail modal
Opens on tile click in every mode. Overlay `rgba(26,16,53,0.55)` + `backdrop-filter: blur(3px)`.
Panel 600px, white, `1px solid #C9B8E8`. Header bar (`15px 22px`, bg `#FBFAFD`):
`BLOCK NN · KIND` + `×`. Body: 190px media placeholder (16px stripe), title 21px/700,
description 14.5px, then a 2-column 1px-gap fact grid — `type`, `signature`, `captured`,
`attestations`. Actions: `Verify chain` (filled `#6B3FA0`) and `Replace media` (outline).
Closes on overlay click, `×`, or either action (stub).

### 2. User page — mobile (390px)
- Attestation seals stack **vertically** as three full-width rows (glyph + token + `✓`), still the
  first thing on the page.
- Identity row: 60×60 avatar, name 20px/700, `handle · trust 3` in mono.
- Filter chips scroll horizontally.
- Ledger becomes `repeat(2,1fr)` squares; tile head collapses into the media area
  (kind top-left, seals top-right), title in the foot at 11.5px.
- Add tile is a single square with `+ ADD`.

## Interactions & behavior
- **Mode switch** `Edit | Visitor | Agent` — client state, no navigation. Edit shows drag +
  add tile; Visitor shows the trust footer; Agent shows the MCP panel. Real app should map these
  to `/profile` (owner), the public entity URL, and the agent response respectively.
- **Reorder** — HTML5 drag & drop between tiles in Edit mode; `dragstart` records the index,
  `dragover` calls `preventDefault()`, `drop` splices the moved id into the target index.
  Persist the resulting order server-side.
- **Add block** — appends a `DRAFT` tile (kind `DRAFT`, no attestations, "Untitled claim").
  In production this should open a source picker (video / photo / text / audio) and start the
  signing flow on upload.
- **Filter** — `ALL · video · photo · text · audio`; filters the tile list, indices stay tied to the
  block's real position, not the filtered position.
- **Hover** — the provenance overlay; on touch devices show it on first tap and open the modal on
  the second, or drop the overlay and rely on the modal.
- **No motion beyond**: overlay fade `.16s ease`, the 2.4s status dot pulse, color transitions on
  buttons. Respect `prefers-reduced-motion` by disabling the pulse.

## State management
```
mode        : 'edit' | 'visitor' | 'agent'
order       : string[]           // block ids, source of truth for tile order
filter      : 'ALL'|'VIDEO'|'PHOTO'|'TEXT'|'AUDIO'
hover       : string | null      // block id under the cursor
drag        : number | null      // index being dragged
open        : string | null      // block id shown in the modal
```
Data needed per entity: name, handle, description, avatar, registry record, trust level,
registration year, agent-lookup count, and the block list.
Per block: `id, kind, title, meta, marks[] (registry|c2pa|btc), body, hash/signature, mediaUrl`.
Attestation status for the top bar is derived from the blocks (`c2pa: 4 of 6 blocks signed`) plus the
registry and timestamp records — it is not authored by the user.

## Design tokens
Colors
```
ink / text        #1A1035
body text         #4A3F6B
muted / mono      #9088B0
primary purple    #6B3FA0   hover #5A3488
purple tint bg    #F4F0FB   ·  lilac line #C9B8E8
orange accent     #E8640C
border            #E2DCF0   ·  inner hairline #F1EDF9
surface           #FFFFFF   ·  raised #FBFAFD  ·  canvas #F4F2F8
ink overlay       rgba(26,16,53,0.93)   modal scrim rgba(26,16,53,0.55)
```
Seal glyphs (14px bar / 8–9px on tiles)
```
registry  square  1px radius, filled #6B3FA0
c2pa      circle  50% radius, transparent fill, 1.5px #6B3FA0 border
btc:ts    diamond 1px radius, filled #E8640C, rotate(45deg)
```
Typography
```
UI        'Trebuchet MS', 'Segoe UI', 'Helvetica Neue', sans-serif
Mono      ui-monospace, 'SF Mono', Menlo, monospace
h1 34/700 -1.1px · h2 21/700 -0.6px · stat 21/700 · tile title 14/600 -0.2px
body 15.5/1.55 · secondary 14.5/1.6 · label 10–11.5 mono, tracking 1.2–1.6px, uppercase
```
Spacing: 4px base; section padding `34px` horizontal, grid gap `10px` (0–28 tweakable),
tile inner padding `11–13px`.
Radius: `4px` on buttons only. Everything structural is square — no rounded cards.
Shadows: none. Depth comes from 1px borders and the `#FBFAFD` surface.

## Assets
No bitmap assets. Avatar and all media are diagonal-stripe CSS placeholders — replace with real
media. Seals are CSS shapes (square / circle / rotated square), no icon font or SVG needed.
The Θ+π wordmark is text.

## Files
- `Profile Grid of Record.dc.html` — the chosen design, desktop board + 390px mobile + modal, all
  three modes interactive.
- `support.js` — prototype runtime, required only to open the HTML in a browser. Not for porting.
- Source of the visual language: the existing TETA+PI landing page design file.

## Open questions for the team
- Should a single block support mixed media (photo + text in one square)?
- Who can trigger re-verification, and what does a failed re-check look like on a tile?
- Draft (unsigned) blocks: visible to visitors, or owner-only until signed?
