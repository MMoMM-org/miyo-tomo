---
title: "Structure-Aware Tag-Handler Compose"
status: draft
version: "1.0"
---

# Product Requirements Document

> Spec 025. Extends spec `024-tag-handler-framework` (`miyo-tomo#47`). Source brainstorm:
> `docs/XDD/ideas/2026-06-25-structure-aware-tag-handler-compose.md`. FR/AC numbering continues 024
> (which ends at FR-14/AC-6), so this document starts at FR-15 / AC-7.

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (the Tomo Dev Log table case)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Product Overview

### Vision

A tag handler can make its captured note land **in the shape the target section already uses** — a table
row in a table, a list item in a list — so routed captures read as native content, not as prose blobs
bolted under a heading.

### Problem Statement

Spec 024 routes a tagged capture into a target note and inserts an LLM-composed **prose block** beneath a
heading marker. When the target section is a **table** (the real case: the `## Captures` table in
`Efforts/Tomo Dev Log.md`), this breaks down:

- `placement: after` lands the block **above the table header**, corrupting the table.
- `placement: inside` appends a prose paragraph **below the table**, structurally wrong and visually noisy.

There is no way for a handler to say "this section is a table; emit a row." The consequence: the one
producer that exists today (Tsukai) cannot maintain a clean tabular dev log — every capture degrades the
note's structure, defeating the point of routing captures to a structured log.

### Value Proposition

Captures become **first-class rows/items** in the user's own structures, newest-on-top where wanted, with
per-capture or merged granularity — all declared once per handler as data, with the system reading the
target to conform to reality. The user keeps a clean, scannable log instead of an accreting prose dump,
and the vault stays the source of truth (a malformed row is never written; mismatches fall back safely).

## User Personas

> This is internal PKM tooling for a single primary operator, plus the config-author and producer roles
> that operator wears. "Personas" are roles, not market segments.

### Primary Persona: Vault Owner / Reviewer (Marcus)

- **Demographics:** Power user of Obsidian + the MiYo toolchain; high technical expertise; reviews every
  proposed change before it touches the vault (proposal-first model).
- **Goals:** Keep routed captures in clean, native structures (tables/lists); see exactly what will be
  written and where before approving; never have a capture corrupt a note.
- **Pain Points:** Today a tabular dev log is wrecked by prose-block inserts; ordering (newest-first) is
  not expressible; there is no preview of structured output before apply.

### Secondary Personas

- **Tag-Handler Config Author** (same operator, via wizard or hand-edit): wants to declare output shape
  once — structure, order, granularity, cell mapping — as pure data, without knowing the target's current
  columns. Aligns with 024's "handlers are pure data" constraint.
- **Pipeline Maintainer** (same operator, in dev sessions): wants the structure parsing / row assembly to
  be deterministic and unit-testable **without an LLM in the loop** (Constitution L1 Code Quality).
- **Producer tools** (Tsukai today; future `MiYo/<Feature>` tools): unchanged — keep writing prose-bodied
  captures with frontmatter. Structure-awareness is entirely a Tomo-side compose concern.

## User Journey Maps

### Primary User Journey: Tabular dev log, newest on top

1. **Awareness:** The operator notices Tsukai captures arriving under `## Captures` are prose blobs that
   break the table they want to keep.
2. **Consideration:** They decide the section should be a table and that new entries belong at the top.
3. **Adoption:** They add an `output_format` block to the `tsukai` handler config (structure `table_row`,
   order `newest_first`, granularity `per_item`, typed cells) and shape `## Captures` as a table.
4. **Usage:** On the next `/inbox`, the suggestions doc shows the proposed **rows verbatim**, the mode
   (table / newest-first / per-item) and the target+marker; the operator approves; the rows land directly
   under the table header, newest first, table intact.
5. **Retention:** Each subsequent run stacks correctly; the log stays clean and scannable, so the operator
   keeps routing captures there instead of abandoning the log.

### Secondary User Journey: Safe fallback on mismatch

1. The operator edits the target so the section no longer matches the declared format (e.g. removes the
   table, or the column count drifts).
2. On the next run, the suggestions doc shows a **⚠️ warning** naming the handler, target, and mismatch
   reason, and proposes a **prose-block fallback** instead of a broken row.
3. The operator approves the fallback (or fixes the target and re-runs) — fully informed, never surprised
   by a corrupted note.

## Feature Requirements

### Must Have Features

#### Feature 1 — Opt-in structure-aware output (FR-15)

- **User Story:** As a config author, I want to declare that a handler emits a table row or list item via
  an `output_format` block, so routed captures conform to the target section's structure instead of being
  prose blocks.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given a handler config **without** `output_format`, When `/inbox` composes its group, Then the
    output is byte-identical to today's prose block via `compose` (AC-14 backward compatibility).
  - [ ] Given a handler with `output_format.structure = table_row`, When the target section under the
    marker is a well-formed table, Then the composed block is one or more well-formed `| … | … |` rows.
  - [ ] Given a handler with `output_format.structure = list_item`, When the target section is a list,
    Then the composed block is one or more list items in the list's inferred bullet style (`-`/`*`/`1.`,
    default `-`).

#### Feature 2 — Ordering & placement (FR-16)

- **User Story:** As a vault owner, I want to choose whether new rows/items append at the end or insert
  newest-first, so the most recent capture appears where I expect.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given `structure = table_row, order = append`, When composed, Then rows are placed at the **end of
    the section** (beneath the heading, after the last existing row).
  - [ ] Given `structure = table_row, order = newest_first`, When composed, Then the insertion is anchored
    to the target table's **header + separator rows (verbatim)** and placed immediately **after** them, so
    new rows land as the first data row(s).
  - [ ] Given `structure = list_item, order = append`, When composed, Then items are placed at the end of
    the list section.
  - [ ] Given `structure = list_item, order = newest_first`, When composed, Then items are placed **above
    the first existing list item**.
  - [ ] Given any ordering, When composed, Then no new instruction action type is introduced — the
    existing insert-under-marker mechanism is reused. *(Implementation note for SDD; observable as: the
    instruction set contains no new action kind.)*

#### Feature 3 — Granularity: per-item vs merged (FR-17)

- **User Story:** As a config author, I want to choose whether a batch of N captures becomes N rows/items
  or one merged row/item, so the log granularity matches the content.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given `granularity = per_item` and a group of N source captures, When composed, Then the group
    yields **N rows/items**, each derived from one capture.
  - [ ] Given `granularity = merged` and a group of N captures, When composed, Then the group yields
    **exactly one** synthesized row/item, where each `synthesize` cell's directive runs **once over the
    whole batch** (no separate merge-directive field exists).
  - [ ] Given either granularity, When composed, Then the group still produces **exactly one composed
    block** (the 024 FR-8/AC-3 "one update per group" invariant holds; per_item = N lines in one block).

#### Feature 4 — Typed cells, positional mapping & sanitization (FR-18)

- **User Story:** As a config author, I want each cell to be either a raw frontmatter value or an
  LLM-synthesized one-liner, mapped left-to-right onto the target's columns.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given a cell `{field: <name>}`, When composed, Then the cell renders the raw frontmatter /
    `read_fields` value verbatim, with **no LLM** involved.
  - [ ] Given a cell `{synthesize: <directive>}`, When composed, Then the cell renders an LLM one-liner
    produced from the directive.
  - [ ] Given a `synthesize` cell, When its value is rendered into a table row, Then it is guaranteed
    **single-line** and any literal `|` is escaped, so a stray pipe or newline cannot break the row.
  - [ ] Given `structure = table_row`, When the number of declared cells **equals** the target table's
    column count, Then cells map **positionally L→R** onto columns and the row is emitted.
  - [ ] Given `list_item`, When cells are rendered, Then they are joined into one line by `join`
    (default `" — "`).

#### Feature 5 — Safe failure & fallback (FR-19)

- **User Story:** As a vault owner, I want a clear warning and a safe fallback when the target structure
  doesn't match, so a capture is never lost and a note is never corrupted.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given `structure = table_row` and a **cell-count ≠ column-count** mismatch, When composed, Then
    the system emits a **⚠️ warning** in the suggestions doc (naming handler, target, and reason) **and**
    falls back to a safe prose-block append; it does **not** emit a malformed row.
  - [ ] Given the section under the marker is **prose only** (no table/list), When a structure-aware
    handler composes, Then the system warns and falls back to a prose-block append.
  - [ ] Given the **marker is missing**, When a structure-aware handler composes, Then the system warns
    and falls back (it does **not** silently relocate the content).
  - [ ] Given any fallback, When the user reviews the suggestions doc, Then they approve the **fallback**
    knowingly (the warning makes the degradation explicit).

#### Feature 6 — User-review preview (FR-20)

- **User Story:** As a reviewer, I want the suggestions doc to show exactly what will be written and where,
  so I can approve structured output with confidence.
- **Acceptance Criteria (Gherkin):**
  - [ ] Given a structure-aware group, When the suggestions doc is rendered, Then it shows the **target
    note + marker heading**.
  - [ ] Given a structure-aware group, When rendered, Then it shows the **structure mode**: table/list,
    append/newest-first, per-item/merged.
  - [ ] Given a structure-aware group, When rendered, Then it shows a **verbatim preview** of the row(s) /
    item(s) as they will render (all N lines for per_item; the single line for merged).
  - [ ] Given any structure-aware preview or warning, When rendered, Then it **does not name executor
    internals** (no "Hashi", action-type, or script names) — only the user-visible effect.

### Should Have Features

- **FR-21 — Empty-table support:** a target table with a header + separator but zero data rows is a valid
  target; the first row is emitted from the header's column count (happy path, not fallback).
- **FR-22 — Separator-variant tolerance:** the structure parser recognizes common Markdown separator-row
  variants (`|---|`, `| :-- |`, alignment colons, ragged dashes) when locating the header for newest-first.

### Could Have Features

- Mixed-bullet-list warning: when a list mixes `-`/`*`/`1.`, optionally warn (v1 default: first-item style
  is authoritative without a warning — see Open Questions).
- A tag-handler-wizard step that authors `output_format` interactively.

### Won't Have (This Phase)

- **`replace_section` consumer.** Hashi shipped the capability; this spec wires **no** Tomo consumer for it.
- **Overwrite-mode / per-day row-merge handlers** (the future `replace_section` consumer).
- **General structure conformance** beyond tables and lists (callouts, sub-headings, definition lists).
- **Named-column mapping.** v1 is positional; reordering target columns silently misfills (documented
  limitation, see Risks).

## Detailed Feature Specifications

### Feature: Table-row newest-first compose (the most complex path)

**Description:** For a handler with `output_format = {structure: table_row, order: newest_first}`, the
compose step reads the target note, locates the table under the marker, validates that the declared cell
count matches the table's columns, assembles one row per source capture (per_item) or one merged row, and
anchors the insertion to the table's header + separator rows so new rows land directly beneath the header.

**User Flow:**
1. User configures the handler and shapes `## Captures` as a table.
2. System (on `/inbox`) detects the tagged captures, groups them, reads the target table, assembles rows,
   and proposes them in the suggestions doc with a verbatim preview and the mode.
3. User approves.
4. System produces the apply instruction; on apply, the rows land as the first data row(s), newest first,
   table intact.

**Business Rules:**
- A `field` cell never invokes the LLM; only `synthesize` cells do.
- `synthesize` cell values are forced single-line and pipe-escaped before rendering into a row.
- Cells map positionally (L→R) to columns; emission requires cell-count == column-count.
- The newest-first anchor uses the target's **raw** header + separator bytes (read from the note), never a
  re-pretty-printed reconstruction, so the downstream byte-exact match succeeds.
- One composed block per group regardless of granularity.

**Edge Cases:**
- Empty target table (header + separator, 0 rows) → Expected: valid; emit the first data row(s).
- Single-column table (`| x |`) → Expected: cell-count==1 validates; row emitted.
- Prose-only section under the marker → Expected: ⚠️ warn + prose-block fallback.
- Marker missing → Expected: ⚠️ warn + fallback (no silent relocation).
- Cell-count ≠ column-count → Expected: ⚠️ warn + fallback.
- List with mixed bullet styles → Expected: first-item style is authoritative (v1); warning is an open
  question.
- Multiple identical tables under the marker → Expected: the header+separator anchor matches the first;
  collision is only possible if two tables share an identical header **and** separator (documented).
- Table cell containing a literal `|` or newline (from a `synthesize` cell) → Expected: escaped /
  single-lined so the row stays well-formed.
- `field` cell whose source value is missing/empty → Expected: empty cell rendered (row still well-formed);
  not a fallback trigger.
- Markdown separator-row variants → Expected: recognized by the parser (FR-22).

## Success Metrics

> Internal tooling for a single operator — "success" is correctness and sustained use, not market metrics.

### Key Performance Indicators

- **Adoption:** The `tsukai` handler is migrated to `output_format` and the Tomo Dev Log is maintained as a
  table across multiple `/inbox` runs (target: the operator keeps using it rather than reverting to prose).
- **Engagement:** Structure-aware groups compose and apply on real `/inbox` runs without manual row editing.
- **Quality:** **Zero** malformed rows/items written to the vault; every structure mismatch produces a
  warning + fallback (not a corruption). Deterministic assembly covered by unit tests (happy + failure per
  Constitution L1 Testing).
- **Operational impact:** Newest-first table inserts land correctly on the live vault end-to-end
  (Tomo → apply) at least once before the spec is closed.

### Tracking Requirements

| Event | Properties | Purpose |
|-------|------------|---------|
| Structure-aware group composed | handler id, structure, order, granularity, cell count, row count | Confirm the feature path is exercised |
| Structure mismatch fallback | handler id, target, mismatch reason | Detect misconfiguration / drift; verify fallback fires |
| Structure-aware group applied | handler id, structure, order, rows applied | Confirm end-to-end apply on the live vault |

## Constraints and Assumptions

### Constraints

- **Architecture:** No new instruction action — reuse the existing insert-under-marker mechanism (the
  newest-first table path uses Hashi's already-shipped multi-line `block` anchor).
- **Compose boundary:** structure parsing and row/item assembly must be deterministic and testable without
  an LLM (Constitution L1 Code Quality); only `synthesize` cells touch the model.
- **Privacy:** reading the **target** note into the compose step happens **only** for handlers the user
  explicitly configured with `output_format` (Constitution L1 Privacy — no broadened vault access).
- **Proposal-first:** every structure-aware change is reviewed in the suggestions doc before apply; Tomo
  writes only to the inbox/suggestions surface.
- **Runtime layout:** scripts run in the flattened Docker instance — path defaults must be instance-correct
  (cwd-relative), not repo-layout-relative.

### Assumptions

- The user shapes the target section appropriately (creates the table/list) before relying on the handler;
  the system validates and falls back rather than creating structure.
- Hashi's `block` anchor (exact-per-line, trailing-trim) is available and matches the bytes Tomo emits.
- The existing tag-handler chain (detect → resolve → group → compose → reduce → render) is the foundation;
  this feature extends it additively.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Schema↔producer↔consumer 3-way drift silently no-ops new fields | High | Medium | Land schema changes first, then producer (resolver+grouper propagation), then consumer; add/extend parity + round-trip tests (SDD/PLAN) |
| Newest-first anchor mismatch (re-pretty-printed vs raw bytes) → row never inserted | High | Medium | Emit anchor value from the target's raw header/separator bytes; test byte-exact match |
| Positional cell→column mapping misfills after column reorder | Medium | Low | Documented v1 limitation; count validation; named mapping parked for a follow-up |
| `synthesize` cell injects `\|`/newline and breaks a row | Medium | Medium | Mandatory single-line + pipe-escape on synth cells (FR-18); unit tests |
| Multiple identical tables collide on the block anchor | Low | Low | Header+separator anchor; collision only on identical header+separator; documented |
| Producer-chain propagation gap (output_format not carried from resolver→grouper→interpreter) | High | Medium | Explicitly enumerate the propagation path in the SDD/PLAN "files touched" (research found this gap in the brainstorm) |

## Open Questions

> Recorded for the SDD — not PRD blockers. Defaults are stated; the SDD confirms.

- [ ] **Parse contract for mixed-content sections:** when the section under the marker contains prose +
  table + list, which structure is "the" target? (Proposed default: the first structure of the declared
  type encountered under the marker.)
- [ ] **Suggestions-doc preview shape:** exact line-for-line rendering of a multi-row block in the
  suggestions doc (drives FR-20's verbatim preview).
- [ ] **Mixed-bullet-list warning:** is first-item style silently authoritative (v1 default), or does a
  mixed list warrant a ⚠️ warning?
- [ ] **Kokoro ADR landing:** the contract note (`anchor.type: block` + `replace_section`) is pending an
  ADR number — operational follow-up, not a code blocker for this spec.

---

## Supporting Research

### Competitive Analysis

Not applicable — internal PKM tooling. The closest prior art is spec 024's prose-block insert (the thing
being extended) and Hashi's existing `insert_under_marker` placement semantics, which this feature reuses.

### User Research

Grounded in the real motivating case: the `## Captures` section of `Efforts/Tomo Dev Log.md`, where prose
blocks corrupt the intended table. Three research perspectives (Requirements, Technical, Integration) were
run during `/xdd` initialization; their findings are folded into the FRs, edge cases, and risks above.
Key confirmations: Hashi's shipped `block` anchor matches Tomo's handoff byte-for-byte
(`Hashi/src/actions/anchorResolver.ts`); the highest implementation risk is schema/producer/consumer
coordination; the producer chain (`tag-handler-resolve.py` → `tag-handler-group.py` → interpreter) must
propagate `output_format`.

### Market Data

Not applicable — single-operator internal tool.
