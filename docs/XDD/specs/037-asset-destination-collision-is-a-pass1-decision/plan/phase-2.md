---
title: "Phase 2: The decision in the document"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: The decision in the document

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-4]` — rename pre-ticked, cleared means ignore
- `[ref: SDD/Interface Specifications; attachment_conflicts[]]`
- `[ref: PRD/F2]`, `[ref: PRD/S1]`, `[ref: PRD/S2]`, `[ref: PRD/C1]`
- `[ref: PRD/Detailed Feature Specifications; Business Rules 1-6]`

**Key Decisions**:
- Rename ships **ticked**. This reverses the repo's usual habit deliberately:
  a safe obvious answer exists, and charging attention for the common case is
  the cost this spec exists to avoid.
- A **cleared** default resolves to `ignore`, not to `keep_in_inbox`. Clearing
  the box is itself a signal that the owner wants to handle it, so the outcome
  is the loudest of the three, not the quietest.
- The parser resolves `remedy` fully — empty and contradictory entries become
  `ignore` here, so no downstream consumer re-derives it.
- The section is rendered only when non-empty. A run without conflicts must
  produce an unchanged document.

**Dependencies**: Phase 1 (conflicts must exist before they can be rendered).

---

## Named risk carried in from Phase 1 — read before designing the render

**A conflict entry's `owner_source_items` may name a note whose attachment is not the entry's
`source`.** Recorded 2026-09-22 from T1.2's compliance review; T1.2 itself is correct and passed.

`detect_attachment_conflicts` groups by case-folded **destination**. That is the right key — it is
what makes one attachment embedded by three notes a single conflict with three owners. But when two
*different* inbox attachments share a basename (`100 Inbox/A/karte.png` and `100 Inbox/B/karte.png`)
and the vault already holds that name, both land in the **same** entry: `source` keeps whichever
path was seen first, and `owner_source_items` accumulates the owners of both.

For detection this is harmless — the destination genuinely is occupied, which is all Phase 1 claims.
It stops being harmless here. If this phase renders `owner_source_items` as "the notes that embed
this file", and Phase 3 applies a rename with an embed rewrite, **the second file's owning note is
told its embed was retargeted to a file it never owned.** The user approves a remedy for one file
and a different note is modified.

The intra-run half of this is deliberately Pass 2's (`_build_move_asset_actions`' `claimed` dict,
`render_actions.py:761-774`), and that boundary stands — this is not a request to detect it here.
What this phase owes is that its rendering and its remedies cannot mislead when an entry carries
owners of more than one source. Decide it explicitly: render per-source rather than per-destination,
split the entry, or state why the shape cannot reach a user.

**Decided 2026-09-22 — in the data, not the display. This phase owes nothing further.**
The third option was checked and refuted rather than assumed: `_asset_dest_join`
(`render_actions.py:571-575`) builds the destination from the asset folder plus the source's
basename, and spec 034 shipped recursive inbox discovery, so two attachments sharing a filename in
different inbox subfolders genuinely reach one entry. The owner chose to fix the key rather than
teach the renderer a special case — **Phase 1 T1.5** groups by exact source path, keeping the
case-folded destination only as the occupancy test. An entry therefore describes exactly one file
by the time this phase reads it, and `owner_source_items` names only notes embedding that file.

## Tasks

Establishes the surface the owner reads and the tick the pipeline reads back.

- [ ] **T2.1 The conflict renders as a decision with three remedies** `[activity: frontend-ui]`

  1. Prime: Read `render_attachments_preamble` `[ref: suggestions-reducer.py:1452]` for the document's existing attachment voice, and a rendered suggestions document for how other decisions present their checkboxes
  2. Test: one conflict renders an entry naming source, destination and every owning note `[ref: PRD/F2-AC1]`; exactly three remedies appear — rename, keep in inbox, ignore — with rename ticked `[ref: PRD/F2-AC2]`; an attachment embedded by three notes renders **one** entry `[ref: PRD/F2-AC3]`; a run with no conflicts renders **no section at all** `[ref: PRD/F2-AC4]`; the rename remedy names the destination it would use `[ref: PRD/C1]`
  3. Implement: render the section from `attachment_conflicts[]`, including `proposed_name`
  4. Validate: full suite; `ruff`; byte-compare a zero-conflict document against the pre-change render
  5. Success: every F2 rendering criterion has a named test; the owner can act without opening JSON `[ref: PRD/Personas, primary]`

- [ ] **T2.2 The entry says whether it is the same file** `[activity: frontend-ui]` `[parallel: true]`

  1. Prime: Read `same_file` in `[ref: SDD/Interface Specifications]` and the three S1 criteria
  2. Test: `same_file: true` renders the sentence saying so **and** the warning that renaming creates a second copy `[ref: PRD/S1-AC1]`; `false` renders that a different file holds the name `[ref: PRD/S1-AC2]`; `null` renders that the files could not be compared, with the remedies unchanged `[ref: PRD/S1-AC3]`
  3. Implement: branch the entry's wording on `same_file`; never render a digest `[ref: SDD/Security and privacy]`
  4. Validate: full suite; `ruff`; grep the rendered fixture output for any hex digest and assert none
  5. Success: the wording changes, the remedies and the default do not `[ref: SDD/Complex Logic]`

- [ ] **T2.3 The parser reads the tick back, and resolves the awkward cases** `[activity: domain-modeling]`

  1. Prime: Read `tomo/scripts/suggestion-parser.py` checkbox parsing for an existing decision block; read Business Rules 3 and 4 `[ref: PRD/Detailed Feature Specifications]`
  2. Test: rename left ticked yields `rename`; keep-in-inbox ticked alone yields `keep_in_inbox`; ignore ticked alone yields `ignore`; **rename cleared with nothing else ticked yields `ignore`** `[ref: PRD/F2-AC5, ADR-4]`; **two remedies ticked yields `ignore`** `[ref: PRD/Rule 4]`; `remedy` is never null after parsing `[ref: SDD/Interface Specifications]`; an entry where rename stays ticked and the owner also ticks ignore is a contradiction, not a rename
  3. Implement: parse the three boxes into `remedy`, applying Rules 3 and 4 in the parser
  4. Validate: full suite; `ruff`; prove the cleared-default test RED by inverting the resolution to `keep_in_inbox`
  5. Success: an unresolved entry is loud, not quiet `[ref: SDD/ADR-4 rationale]`; S2's statement in the entry names what will happen `[ref: PRD/S2-AC1]`
