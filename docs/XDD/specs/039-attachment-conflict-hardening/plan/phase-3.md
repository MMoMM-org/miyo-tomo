---
title: "Phase 3: The folder reaches both surfaces"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: The folder reaches both surfaces

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F1]` — F1-AC1, AC2, AC4 (parse side), AC8, AC9
- `[ref: SDD/ADR-4]` — own line; null = configured asset folder
- `[ref: SDD/Runtime View; Primary Flow — Pass 1, Pass 2 markdown path, Pass 2 wire path]`
- `[ref: SDD/Implementation Gotchas]` — two "3"s, retargeted golden, inventory note text
- `[ref: research.md/R2 §1–§4]`

**Key Decisions**:
- The rename line is unchanged; the folder is a **non-checkbox sub-line** `  - Folder: \`…\`` under it, in both rename variants.
- Pass 1 always emits `proposed_dir: null`.
- Order inside the phase: **T3.2 → T3.1 → T3.3**. T3.1 projects the record field T3.2 adds; D26 and the inventory join need the parser literal T3.3 adds, so they move to T3.3.
- The parser records `proposed_dir` verbatim and `dir_is_owner_supplied` (text differs exactly from the folder Pass 1 rendered — same provenance rule as names). It does **not** normalise or decide equality with the default folder — K1 does, against Pass 2's `concepts.asset`, for both paths (SDD Runtime View, wire path step 2).
- After this phase `proposed_dir` is on both surfaces but **nothing in Pass 2 consumes it** — Phase 4 does, behind Phase 2's guard.

**Dependencies**: Phase 1 (T1.3 vendored copy at v3), Phase 2.

---

## Tasks

Delivers the folder as a field on the v4 wire, a line in the markdown, a row in the inventory, and a value in the parser's remedy records.

- [x] **T3.1 Suggestions wire v4** `[activity: integration]`

  1. Prime: `tomo/schemas/suggestions-wire.schema.json:7-10, 175-190`; shape manifest; `suggestions-decision-inventory.json` D24/D25; `test_038_decision_inventory_join.py:56-60, 116, 209-279`; `test_038_inventory_schema_validation.py:372-470` `[ref: SDD/External Interfaces; SDD/ADR-4]`
  2. Test: wire with `proposed_dir: null` validates, wire without it fails (required), a non-string non-null fails; `schema_version` const `"4"`; `test_035_wire_gate` green against the regenerated manifest; vendored copy still `"3"` (it moves in T6.2)
  3. Implement: schema (description starts "Editable — "), `wire-shape.py --regenerate`, `suggestions-render.py` projects `proposed_dir`; triage every suggestions-wire `"3"` literal (R2 §1 list) — leave instructions-wire `"3"`s alone. The inventory's schema-side count goes red here by design and is closed in T3.3
  4. Validate: suite green; `rg '"schema_version": "3"' tests/` reviewed hit by hit
  5. Success: `[ref: PRD/F1-AC1]`

  **Depends on:** T3.2

- [x] **T3.2 Pass 1 renders the folder line** `[activity: backend]`

  1. Prime: `suggestions-reducer.py:690-740, 1438-1535`; `test_038_t4_1_markdown_offers_a_place_to_type.py:76`; `tests/test_037_t2_2_render_conflicts.py`, `test_037_t4_4_rendered_text.py` `[ref: SDD/Primary Flow — Pass 1]`
  2. Test: ordinary conflict renders the Rename line exactly as today followed by `  - Folder: \`<dirname(destination)>\``; the "no free name available" variant renders it too; conflict records carry `proposed_dir: None`; a conflict-free run's markdown is byte-identical to today
  3. Implement: renderer + record field; `suggestions-doc.schema.json` conflict record gains `proposed_dir` (its items are `additionalProperties: false` and `test_037_t2_2_render_conflicts.py:512` validates against it)
  4. Validate: retarget the 038 golden to the new shape (do not delete it); suite green
  5. Success: `[ref: PRD/F1-AC2]`

- [ ] **T3.3 Parser reads the folder line and the wire field** `[activity: backend]`

  1. Prime: `suggestion-parser.py:245-288, 331-521 (esp. 493-517), 2252-2546`; backlog `:1894` (fields declared in three places) `[ref: SDD/Primary Flow — Pass 2 markdown/wire]`
  2. Test: untouched folder line → `proposed_dir` = the rendered text, `dir_is_owner_supplied` False; edited → text verbatim, True; default folder plus a trailing `/` → verbatim, True (refused downstream, both paths alike); deleted line → `None`, False; folder line outside an entry ignored; a folder typed **inside the rename backticks** still yields `separator_present` downstream (`test_a_different_folder_typed_is_refused_separator_present` unchanged — F1-AC8); `build_from_wire` projects `proposed_dir` with `dir_is_owner_supplied: True`; remedy records carry exactly the six keys `{source, remedy, proposed_name, name_is_owner_supplied, proposed_dir, dir_is_owner_supplied}` on both paths; D26 present with `wire_field: attachment_conflicts[].proposed_dir` and `parser_label` carrying the folder-line literal; `EXPECTED_EDITABLE_MARKED_FIELDS` 26 and the test renamed from `…exactly_25…` to `…exactly_26…`, docstring at `test_038_decision_inventory_join.py:79` updated, `FLOOR_SCHEMA_MARKED_FIELDS` left at 25; both directions of the join green
  3. Implement: non-checkbox branch in `_walk_attachment_conflicts`; consolidate its per-entry field declarations into one place while adding the seventh walker field (backlog `:1894` — walker fields, not remedy-record keys); join; wire projection; D26 (note with no bare 3–4 digit number)
  4. Validate: suite green; ruff clean
  5. Success: parse side of `[ref: PRD/F1-AC3]` `[ref: PRD/F1-AC4]`; `[ref: PRD/F1-AC8]` `[ref: PRD/F1-AC9]`

  **Depends on:** T3.1

- [ ] **T3.4 Phase 3 validation** `[activity: validate]`

  - Full suite green; Pass 2 output byte-identical on the 038 baseline and on a conflict fixture with an **edited** folder line (proves nothing consumes it yet); grep shows no reader of `proposed_dir` outside the parser and the renderer.
