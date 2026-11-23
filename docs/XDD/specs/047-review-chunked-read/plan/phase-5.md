---
title: "Phase 5: Carried items, their checks and the top lines"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Carried items, their checks and the top lines

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Application Data Models; lines: 654-677]` — `carried` / `carried_ids`, the subset rule, `Sources.previous`, `DocInput`
- `[ref: SDD/Implementation Examples/A carried item checked; lines: 778-860]` — `resolve_sources`, the call-site branch, `review_carried.check`, `overflow`, `coverage`, the trace table
- `[ref: SDD/Implementation Examples/The rendered line; lines: 862-869]`
- `[ref: SDD/Internal API Changes; lines: 628-634]` — the `carried-*` errors, the `carried-moved` notice, the `written` keys
- `[ref: SDD/UI Visualization Guide; lines: 1105-1126]`
- `[ref: SDD/Architecture Decisions; ADR-6, ADR-9, ADR-12; lines: 1194-1199, 1212-1215, 1227-1230]`

**Key Decisions**:
- A separate `carried` field, not new `mark` values; group items gain it as an optional, additive field (every existing fixture stays valid) (ADR-6).
- One source resolver `review_doc.resolve_sources`, used by `check_item` and `review_carried`; every carried failure is an `errors` entry (`proposals-invalid`), never a `rejected` row (ADR-6).
- `overflow` runs before the section checks and moves the last carried items of an over-cap section into the group of their mark; non-carried items keep spec 046's `over-cap` refusal.
- Suffix order: carried label, then the child mark; labels EN/DE, English otherwise. Top lines are callout continuation lines; the parser ignores them (ADR-12).
- Pass 2 code is not touched; `review_doc_parse` gets a regression test only (ADR-9).
- File sizes: `lib/review_doc.py` grows to ≈ 470 lines at most; the rules live in `review_carried.py` (CON-5).

**Dependencies**: Phase 4. T5.1 ∥ T5.2 ∥ T5.5 (disjoint files: T5.1 `tomo/schemas/review-proposals.schema.json`, `tests/test_review_proposals_carried_schema.py`, `docs/tomo/scripts/review-doc.md`; T5.2 `tomo/scripts/lib/review_doc.py`, `tests/test_review_doc.py`, `docs/tomo/scripts/lib/review_doc.md`; T5.5 `tests/test_review_doc_parse.py`) → T5.3 (needs T5.2's `resolve_sources` and `Sources.previous`) → T5.4 (needs T5.1, T5.3).

---

## Tasks

Lets a proposal carry an item from a previous note, proves its mark and sources by script, and shows the previous notes at the top of the document.

- [ ] **T5.1 `carried` and `carried_ids` in the proposals schema** `[activity: data-architecture]` `[parallel: true]`

  1. Prime: `tomo/schemas/review-proposals.schema.json` (group items, `sectionItem.mark` enum), its tests `[ref: SDD/Application Data Models; lines: 654-662]` `[ref: SDD/ADR-6]`
  2. Test: `tests/test_review_proposals_carried_schema.py` (new; validates against the schema file directly, without `review-doc.py`) — a group item and a section item with `carried` and `carried_ids` validate; `carried` without `carried_ids` and the reverse are refused (dependentRequired both ways); a value outside `done | still_open | not_mentioned` and an id outside `^c[0-9]{1,3}$` are refused; every existing proposals fixture of specs 045/046 still validates (glob over the fixtures, untruncated).
  3. Implement: the additive schema change; the WHY note in `docs/tomo/scripts/review-doc.md` (schema section) first; add `tests/test_review_proposals_carried_schema.py` to the Tests block of spec 047's `solution.md` Directory Map in the same commit.
  4. Validate: the new schema test and `test_review_sdd_map.py` green (`test_review_doc.py` is run in T5.6, not edited here); ruff clean.
  5. Success: a proposal can say what it carries and from which carryover ids `[ref: SDD/ADR-6]`

- [ ] **T5.2 Sources, labels and top lines (`lib/review_doc.py`)** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `lib/review_doc.py` (`_LABELS` 100-127, `Sources.of` 203-221, `check_item` 252-278, `_callout` 350-361, `DocInput` 310-327), `docs/tomo/scripts/lib/review_doc.md`, `tests/test_review_doc.py` `[ref: SDD/Implementation Examples; lines: 780-798]` `[ref: SDD/ADR-6, ADR-12]`
  2. Test: `Sources.previous` holds found previous notes only, `previous_of` resolves path or stem; `resolve_sources` returns days, child hits, previous hits and links in source order, and `check_item` built on it gives byte-identical results for every existing case; `_LABELS` carries `carried_done` / `carried_still_open` / `carried_not_mentioned` with the owner's EN and DE wording, English for any other language (F5-AC1); `DocInput` gains `previous`, `not_condensed`, `carry_failed`; `test_one_top_line_per_previous_note` with the states "found, n carried", "found, nothing carried" (F3-AC11), "read in part" appended (F3-AC10), "empty", "no note found for <name>" (no error tone, F3-AC6), "<kind> notes are not set up", the three "not read" causes; one `Not condensed:` line per failed unit; the one carry-failed line; DE wording; the callout's first line unchanged; `review_doc_parse` still reads the document with these lines (no column-0 checkbox above the first `## `).
  3. Implement: WHY doc first; `lib/review_doc.py` 0.5.4 → 0.6.0 (sources, resolver, labels, callout lines; no carried rule here).
  4. Validate: `test_review_doc.py` green; module ≤ ≈ 470 lines; ruff clean.
  5. Success: each previous note gets one plain line at the top, and the carried labels exist in both languages `[ref: PRD/F3-AC6, F3-AC11, F5-AC1]` `[ref: SDD/ADR-12]`

- [ ] **T5.3 Carried rules (`lib/review_carried.py`)** `[activity: domain-modeling]`

  1. Prime: T5.2 resolver; the SDD trace table (12 rows); `lib/review_sections.py` (cap, `_double_placements` 167-180) `[ref: SDD/Implementation Examples; lines: 807-860]` `[ref: SDD/ADR-6]`
  2. Test: `tests/test_review_carried.py` — every row of the SDD trace table as one case (accepted rows and each error: `carried-gone-has-day`, `carried-source-not-its-note (c2)`, `carried-not-allowed (themes)`, `carried-mark-conflict` ×2, `carried-missing (c2)`, `carried-twice (c1)`); plus `carried-without-carryover`, `carried-unknown`, `carried-needs-previous-note`, `carried-needs-day`, `carried-theme-done`; a carried item's previous-note sources must be a subset of its ids' sources and include at least one (F5-AC3); one item with ids from both previous notes and both notes as sources is accepted once (F4-AC7); a carried item that the days also hold is one item with the note and the days as sources (F4-AC6); `test_overflow_moves_to_group_of_mark` (done → done; still_open / not_mentioned → open, or themes when every id is a theme; the child mark dropped; notice rows `{key, to, count}`; never a refusal), and an over-cap section with no carried item still refused `over-cap` (F4-AC10); the two-day theme rule does not apply to a carried item; each rule RED-proven by reverting it.
  3. Implement: WHY doc `docs/tomo/scripts/lib/review_carried.md` first; `lib/review_carried.py` (`check`, `overflow`, `coverage`); `# version: 0.1.0`.
  4. Validate: tests green; module ≤ 300 lines; ruff clean.
  5. Success: a carried item appears once, with one mark, linked to its previous note, and is never dropped `[ref: PRD/F4-AC6, F4-AC7, F4-AC10, F5-AC3]`

- [ ] **T5.4 Call sites: groups, sections and `review-doc.py write`** `[activity: backend-api]`

  1. Prime: `lib/review_doc.check_items`, `lib/review_sections.py` (`check` with mark 95-136, `_double_placements` 167-180, `part_items` suffix 224-231), `lib/review_mapping.py` (off-limits rows), `review-doc.py` `render_and_write` 270-325 `[ref: SDD/Implementation Examples; lines: 800-805, 862-869]` `[ref: SDD/Internal API Changes; lines: 628-634]`
  2. Test: an explicit carried branch at both call sites (groups `in_section=False`, sections `in_section=True` with the item's mark); carried failures appear in `errors` and never in `rejected`; `overflow` runs before `over-cap` is counted; `coverage` runs once over the whole document; the rendered suffix is `" · " + carried label` then `" · " + child mark` (F5-AC2, both SDD example lines byte-exact); a carried item can never land in an off-limits heading, because an off-limits heading is never a mapped section, and the best fit off-limits goes to the next fitting section or its group (F4-AC5); `written` gains `previous [{kind, name, state, carried}]`, `not_condensed`, `carry_failed` and the `carried-moved` notice, counts only; a carried proposal with a non-passed carryover is refused `carried-without-carryover`; the baseline e2e (no carried items in its fixture proposals) is still GREEN.
  3. Implement: WHY docs first; `lib/review_doc.py` (the branch; 0.6.0 → 0.6.1), `lib/review_sections.py` 0.2.2 → 0.3.0, `review-doc.py` version bump, `review-doc.py` (pass previous states, not-condensed units and the carry failure to the renderer; new `written` keys).
  4. Validate: `test_review_doc.py`, `test_review_sections*.py`, `test_review_skill_sections.py` green; full suite green; ruff clean.
  5. Success: carried items are checked and rendered in groups and sections, with both marks in order `[ref: PRD/F4-AC5, F5-AC2]`

  - **Carry-over from the T4.4 review (2026-11-23, orchestrator):** `review-doc.py write` refuses only open UNITS (`condense-incomplete`), not an open carryover. So define `carry_failed` as "at least one previous note was found and the carryover state is not `passed`" (pending, retry and failed all count; `none` stays false). Test: a carryover still `pending` or `retry` at write time renders the carry-failed top line and no carried mark (F6-AC2), making `test_047_t4_4_condense_gate.py::test_an_open_carryover_does_not_hold_the_document_back` consistent with F6-AC2.

- [x] **T5.5 Pass 2 regression: a carried mark is item text** `[activity: testing]` `[parallel: true]`

  1. Prime: `lib/review_doc_parse.py` (`_TRAILING_DONE_MARK` 74, `edited` 94-100), `tests/test_review_doc_parse.py` `[ref: SDD/ADR-9; lines: 1212]` `[ref: SDD/Implementation Examples; lines: 869]`
  2. Test: a ticked carried line is kept with the mark as part of its text; a line whose mark the user edited or deleted is kept as the user left it and is not an edit (link stems unchanged) and not a done tick; an unticked or deleted carried item is absent (F5-AC4, F5-AC5); a line carrying both marks and a trailing ` ✅ YYYY-MM-DD` reads the date only as the done mark it already is; RED proof: a parse mutation that strips text after ` · ` fails the test.
  3. Implement: tests only; `lib/review_doc_parse.py` unchanged (any needed change is a deviation brought to the owner).
  4. Validate: tests green; `git diff --stat` shows no change under `tomo/scripts/lib/review_doc_parse.py`; ruff clean.
  5. Success: Pass 2 treats a carried item exactly like any other item `[ref: PRD/F5-AC4, F5-AC5]`

- [ ] **T5.6 Phase Validation** `[activity: validate]`

  - Full suite in ONE invocation — GREEN; ruff clean; `test_035_wire_gate.py` and `test_035_wire_manifests.py` unchanged and green (wire v4). Trace F3-AC6, F3-AC11, F4-AC5, F4-AC6, F4-AC7, F4-AC10, F5-AC1 … F5-AC5 to node ids. Confirm `review-instructions.py` and the Pass 2 libraries are untouched (`git diff --stat`). WHY docs before code; no eval-gated file changed; CON-5 sizes held.
