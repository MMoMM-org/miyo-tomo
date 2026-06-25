# Structure-Aware Tag-Handler Compose

> Brainstorm output, 2026-06-25. Validated design ready for `/xdd`.
> Extends spec `024-tag-handler-framework` (`miyo-tomo#47`).

## Summary

A tag handler can opt in to making its composed capture **conform to the target section's existing
structure** — emit a Markdown **table row** or **list item** that fits the section, instead of a prose
block. Opt-in **per handler** via a new `output_format` object in the handler config. When absent,
behaviour is byte-identical to today (prose block via `compose`). The motivating case: Tsukai captures
routed to a `## Captures` **table** in `Efforts/Tomo Dev Log.md` should append as table **rows**, newest
on top — not as a prose blob landing above the table header.

## Problem

Today's `insert_under_marker` + prose `compose` produces a free-text block under a heading marker. When
the target section is a **table**, `placement: after` (newest-first) lands the block *above* the table
header (breaks the table), and `placement: inside` appends prose *below* the table (structurally wrong).
There is no way for a handler to say "this section is a table; emit a row."

## Decisions (the forks, as settled in brainstorm)

1. **Scope:** tables **and** lists in v1.
2. **Mechanism:** Hybrid — config declares *intent* (`output_format`), the compose step *reads the target*
   to supply reality (columns, list style, the anchor lines). Target-read is **mandatory**, not optional:
   a correct row needs the target's columns, and newest-first needs the target's header+separator text.
3. **Row ordering:** newest-first supported. For **tables** this needs a new Hashi **multi-line block
   anchor** (see Hashi dependency). For **lists** it needs **no Hashi change**.
4. **Hashi handoff:** request **multi-line block anchor** (live consumer) **+ `replace_section`** (capability
   ask, no Tomo consumer yet, bundled to save a round-trip). One handoff, one Kokoro contract note.
5. **Config shape:** new sibling `output_format` object with **typed cells** (`field` vs `synthesize`).
6. **Granularity:** **per-handler flag** (`per_item | merged`) — a group of N captures becomes N rows or 1
   synthesized row.

## Design

### Config schema (`tomo/schemas/tag-handler.schema.json`)

New optional `output_format` object on a handler config:

```jsonc
"output_format": {
  "structure":   "table_row | list_item",
  "order":       "newest_first | append",
  "granularity": "per_item | merged",
  "cells": [
    { "field": "created" },
    { "field": "category" },
    { "synthesize": "one-line summary of what changed" }
  ],
  "join": " — "   // list_item only; how cells join into one line. Default " — ".
}
```

- **`cells` is the universal content model.** `table_row` renders cells as `| c0 | c1 | c2 |`; `list_item`
  joins them by `join` into a single line.
- **Cell types:** `field` = a raw frontmatter / `read_fields` value from the source capture; `synthesize`
  = an LLM-produced one-line value (the directive string is the instruction).
- **`list_item` bullet style** is inferred from the target list's first item (`-` / `*` / `1.`), default `-`.
- **Backward compatible:** `output_format` absent → status quo (prose block via `compose`).

### Compose step (`tag-handler-interpreter` skill + a deterministic helper)

Clean AI/logic split (Constitution L1 Code Quality — domain logic testable without an AI):

- **Skill (AI glue):** reads source notes **and the target note** via `kado-read`; produces only the
  `synthesize` cell values.
- **New deterministic helper** (`tomo/scripts/lib/target_structure.py`): parses the target section under
  the marker → extracts table columns + the header/separator lines (or the list style); **validates
  cell-count vs column-count**; assembles the row(s)/item(s); selects the anchor. No LLM in this path.
- **Granularity:** `per_item` → one row per source capture (the `composed_block` contains N rows);
  `merged` → one synthesized row. Either way still **one `composed_block` per group** (the existing
  FR-8/AC-3 STRICT invariant holds — the block just has 1 or N lines).

### Placement / anchor matrix

| Structure | Order | Anchor + placement | Hashi change |
|-----------|-------|--------------------|--------------|
| `table_row` | `append` | heading + `inside` (end of section) | none |
| `table_row` | `newest_first` | **block** anchor = header+separator rows + `after` | multi-line block anchor |
| `list_item` | `append` | heading + `inside` | none |
| `list_item` | `newest_first` | heading + `after` (lands above first item) | none |

No new Tomo action — everything reuses `insert_under_marker`. The only new wire is `instruction-render`
emitting the `block` anchor (header+separator) for the table newest-first case.

### Hashi dependency (cross-repo)

Handoff: `_outbox/for-hashi/2026-06-25_tomo-to-hashi_block-anchor-and-replace-section.md`.

1. **Multi-line block anchor** (`anchor.type: "block"`, `value` = consecutive lines joined by `\n`):
   exact-per-line match over N lines; `insertAfter = i + k`. Enables robust newest-first table inserts
   (collision only if two tables share an identical header). **Critical-path dependency.**
2. **`replace_section`** action (heading-scoped overwrite, symmetric with `insert_under_marker`):
   intentionally breaks "append, never replace"; explicit opt-in. **No Tomo consumer yet** — parked for a
   future overwrite-mode handler.

### Failure handling

Validation runs at Pass-1 compose time. On mismatch (cell-count ≠ columns, no table/list under the marker,
marker missing): **never emit a broken row** — surface a clear warning in the suggestions doc and **fall
back to a safe prose-block append** (current behaviour). The user sees it before approving (proposal-first).

### Files touched (Tomo side)

- `tomo/schemas/tag-handler.schema.json` — new `output_format` object.
- `tomo/schemas/tag-handler-group.schema.json` + group-result — carry `output_format`, the multi-row
  `composed_block`, and the resolved anchor.
- `tomo/dot_claude/skills/tag-handler-interpreter/SKILL.md` — read the target note; produce `synthesize`
  cells; call the helper.
- `tomo/scripts/lib/target_structure.py` (new) — parse / validate / assemble (deterministic).
- `tomo/scripts/instruction-render.py` — emit the `block` anchor for table newest-first.
- `tomo/scripts/suggestions-reducer.py` — render the structure-aware suggestion item.
- `docs/tomo/**` — mirrored WHY docs for the runtime changes.
- `_outbox/for-hashi/…` (done) + `_outbox/for-kokoro/…` contract note.

## Approaches considered

- **A — declare format fully in config (deterministic, no target read):** rejected. Can't get the table's
  actual columns or the newest-first anchor without reading the target; config would drift from reality.
- **B — read target, LLM infers everything:** rejected as the *sole* mechanism. Adaptive but
  non-deterministic for structure detection; the row assembly should be deterministic and testable.
- **Hybrid (chosen):** config declares intent + cell mapping; deterministic helper reads the target for
  columns / list style / anchor and validates. Best of both — explicit config, reality-checked output.

Config representation: chose **`output_format` + typed cells** over a positional array (fragile to column
reorder; synthesized cells need a hack) and over folding a third object shape into `compose` (makes
`compose` a heterogeneous 3-way `oneOf`, harder to validate/document).

Row ordering: chose **newest-first via a small Hashi block-anchor extension** over a fragile single-line
separator anchor (first-match collision) and over bottom-only append (doesn't meet the newest-first goal).
Confirmed the extension is a *multi-line anchor*, **not** the `replace` originally feared.

## Out of scope / parking lot

- **Overwrite-mode / per-day row-merge handlers** — the `replace_section` consumer; parked until specced.
- **General structure conformance** — callouts, sub-headings, definition lists.
- **Column-reorder robustness** — v1 maps cells **positionally** (L→R). Reordering target columns silently
  misfills. Named-column mapping deferred.

## Open questions for `/xdd`

- Exact `target_structure.py` parse contract (how it identifies "the table/list under the marker" when the
  section has mixed content).
- Whether `merged`-granularity table rows need an LLM merge directive distinct from the prose `compose`
  string, or reuse it.
- Suggestions-doc rendering of a multi-row block (preview shape the user approves).
