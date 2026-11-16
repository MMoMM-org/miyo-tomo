---
title: "Phase 4: Pass 1 — proposals and the review document by section"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: Pass 1 — proposals and the review document by section

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Application Data Models]` — Proposals, SectionPart, ParsedDoc
- `[ref: SDD/Implementation Examples/One section part in the review document]` — divider, analysis part, mark suffix
- `[ref: SDD/Runtime View/Complex Logic]` — "Double placement"
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2, ADR-11]`

**Key Decisions**:
- `sections: [{key, items}]` beside unchanged `groups`; keys only, never heading text (ADR-1).
- Caps refused (`over-cap`), never truncated; double placement refused only with a mapping (ADR-2).
- Every part stays at `##`; the section heading and checkbox carry `%%sN%%`; expected keys in `meta.json` `pass1_sections` (ADR-11).
- Without a mapping the document is spec 045's (F1-AC10, CON-2).

**Dependencies**: Phase 2 and T3.3 (`read.json` with `sections`, which itself needs T3.1–T3.2). T4.1–T4.4 may run while T3.4 waits for the owner; T4.5 needs T3.4.

---

## Tasks

Turns the model's per-section proposals into a review document laid out like the user's note, with one checkbox per section.

- [x] **T4.1 Proposals schema and section checks (`lib/review_sections.py`)** `[activity: domain-modeling]`

  1. Prime: `tomo/schemas/review-proposals.schema.json`; `lib/review_doc.py` (`load_proposals` 132, `Sources` 165, `_group_reason` 201, `_check_item` 209, `check_items` 236, `MONTH_GROUPS` 65-70) `[ref: SDD/Application Data Models; ADR-1; ADR-2]`
  2. Test: `sections` with `key` pattern and items; `mark` defined only on section items (group item schema unchanged); quarter groups `monthly_only` / `not_in_monthly`; checks: `unknown-section`, `over-cap`, `double-placement` (normalised text; sources + first line; only with a mapping), `mark-not-allowed` per kind, `NO_SOURCE` for section items (daily of the period, or a weekly/monthly note for a review-only finding); the per-kind group tables keep the week and month order; spec 045 proposals without `sections` pass and fail exactly as before; each check RED-proven.
  3. Implement: schema; `lib/review_sections.py` (definitions, checks); per-kind group tables in `review_doc.py`; WHY docs first; version bumps. Notes from Phase 3: a quarter's read carries `monthly` entries (keyed `month`, text in `month_text`; weekly entries keep `week_text`) — `review_doc.Sources` must accept `monthly` paths as sources for a `monthly_only` finding, and `_group_reason` / `has_weeklies` (today `kind != MONTH → MONTH_ONLY`) need the quarter's equivalents, incl. a refusal reason when a quarter read no monthly notes.
  4. Validate: `test_review_doc.py`, new `test_review_sections.py` green; ruff clean.
  5. Success: no over-cap, sourceless or twice-placed item reaches the document `[ref: PRD/F1-AC3, F1-AC4, F1-AC5, F1-AC6, F1-AC9; Rules 5, 6]`

- [x] **T4.2 Rendering the document by section and the write path** `[activity: backend-api]`

  1. Prime: `lib/review_doc.py` (`DocInput` 265, `item_lines` 296, `neutralised` 289, `_callout` 303, `render_document` 324, `_LABELS` 82, `group_labels` 108); `review-doc.py` (`render_and_write` 220-265, `_write_meta` 193, `replace`); `lib/review_doc_read.py:55` `[ref: SDD/Implementation Examples/One section part; ADR-11]`
  2. Test: parts in template order, then the `## Tomo Review %%review%%` divider with its landing line, analysis parts, then groups; empty groups omitted only with a mapping; an empty section shows `- nothing found` and an unticked checkbox; the landing line per part names heading and placement (and "Tomo Review" for a routed or analysis section); the mark suffix from `_LABELS` (de, en); global `%%tN%%` numbering; the section checkbox label is the positive wording per review language (de `Abschnitt übernehmen`, en); with a mapping and no group left the whole "Tomo Review" part and its divider are absent; the habits stay in the "Tomo Review" part with a mapping; `meta.json` `pass1_sections` keys and counts only (privacy test); `pass1_counts` with section keys read by `review_doc_read`; `write` and `replace` both run the checks; **an unmapped document is byte-identical to spec 045's** for the week and month fixtures. (The quarter's read parts are T4.5.)
  3. Implement: `review_sections` rendering, `review_doc.render_document` assembly, `review-doc.py`, `review_doc_read.py`; WHY docs first; version bumps. Notes from T4.1: `review_sections.check(proposals, read)` returns `SectionCheck(accepted, rejected, errors)` and is not yet called by `review-doc.py` — wire it into `write` and `replace` here (errors are `"<pointer>: <error>"` strings, section rejections `{section, index, reason}`); `review-doc.py` still sets `month_groups=rd.WEEKLY_ONLY in accepted`, so quarter groups render only once that flag covers the quarter (T4.5 for the read parts, but the flag belongs to rendering); advisory review nit: the double-placement normaliser removes `%%` before the trailing link list, so an echoed rendered line `x ([[a]]) %%t1%%` keeps its list — strip `%%tN%%` first, with a test, and fix the WHY doc's wording on `%%` marks.
  4. Validate: `test_review_doc*.py`, `test_review_e2e*.py`, `test_review_privacy*.py` (amended closed-key assertion for sections, as decided for amended CON-3) green; `review_doc.py` ≤ 450 lines; ruff clean.
  5. Success: the document mirrors the user's note `[ref: PRD/F1-AC7, F1-AC8, F1-AC10, F3-AC1, F3-AC2, F3-AC3]`

- [x] **T4.3 Parsing sections back** `[activity: backend-api]`

  1. Prime: `lib/review_doc_parse.py` (`_ITEM` 53, `_HEADING` 54, `_APPROVED` 55, `_item_of` 165, `_parse_body` 182, `counts` 109, `approved_review` 124) `[ref: SDD/Application Data Models ParsedDoc; ADR-11]`
  2. Test: a section heading with `%%sN%%` and its checkbox matched before `_ITEM`; ticked / unticked / missing per expected key from `meta.json` → `section-checkbox-missing` names the section and the line to restore; the divider is a boundary with no items; a user section named "Done" is never read as group `done`; per-section counts incl. the user's own items (for `section-dropped`) and empty ticked sections (`section-empty`); the landing line is ignored; an edited heading keeps its section; spec 045 documents parse exactly as before (`unknown-group`, `duplicate-group`, `item-outside-group` unchanged).
  3. Implement: parser changes; WHY doc first; version bump. Notes from T4.2: section and review headings, landing lines and the mapped callout's anchor pass through `review_sections.display_heading` (display only), so no config text forms a `%%sN%%` / `%%review%%` / `%%tN%%` id in a mapped document; the unmapped callout keeps the raw anchor (CON-2, pinned); the callout's target stem and not-read / partly-read paths are still raw (pre-existing, path-derived, low risk). Section ids on heading and checkbox are the row key (`%%s1%%`); `pass1_sections` in meta.json is `[{key, count, empty}]` in document order (non-analysis, then analysis parts), written only with a mapping; `SectionPart.routed` has no producer until Phase 5. New refusal `sections-changed` (read's section keys differ from the config rows) — the skill (T4.4) answers it by reading the period again.
  4. Validate: `test_review_doc_parse.py`, `test_review_instructions.py` green; ruff clean.
  5. Success: an unticked section drops everything in it, a broken checkbox stops delivery `[ref: PRD/F3-AC4, F3-AC5, F3-AC6; Rule 7]`

- [ ] **T4.4 Skill steps 5 and 6: proposing by section** `[activity: prompt-authoring]`

  1. Prime: SKILL.md steps 5-6 (117-161); `docs/tomo/dot_claude/skills/periodic-review.md`; `tests/test_review_skill.py:164, 478-492, 538`, `test_review_skill_contract.py:51`, `test_review_skill_pass2.py:43-46` `[ref: SDD/Components SKILL.md row; ADR-1]`
  2. Test: pins for: items per `read.json` `sections` entry from its description and keywords, reminders not finished text, at most `cap`, one place per item, the rest in the groups, analysis rows as overviews, counts per section in the report, the new refusals in the rewrite-once loop, the `section-checkbox-missing` stop.
  3. Implement: WHY first; SKILL.md through `tcs-helper:skill-author`; version bump; record the character growth. Note from T3.3: `read.json` `sections` carries no `placement` (SDD SectionDefinition), so the model cannot tell an analysis row from its fields alone; if "analysis rows as overviews" needs a marker, add `placement` (or an `analysis` flag) to `review-read.py` `section_definitions` and the SDD data model in this task, with a pin. Notes from T4.3 (orchestrator moved the Pass 2 stop wiring here, because the refusing-set test needs a matching skill stop branch): (a) add `review_doc_parse.SECTION_CHECKBOX_MISSING` to `review_actions._gate` after `APPROVED_MISSING` and to `review_delivery.REFUSING` (update the pin in `test_review_deliver.py:130`); `review_actions.py` is already 463 lines (over 450, pre-existing) — keep the edit line-neutral or split along a seam; (b) `review-doc.py parse` stdout carries `section_problems` (`SectionProblem.public()`: key, restore line — never heading text) and `section_counts` (`{ticked, kept, unticked, added, empty}` per key) for the skill's stop line and the later `section-dropped` / `section-empty` notices; (c) the skill's Pass 2 step gets a `section-checkbox-missing` stop branch naming the section (heading from the config row by key) and its restore line; (d) a test that a document whose s1 heading carries `%%s3%% %%s1%%` with s3 ticked delivers nothing (the parser files t1/t2 under s3; only the gate stops it); (e) the skill answers `sections-changed` (from `review-doc.py write`, T4.2) by reading the period again.
  4. Validate: skill tests green.
  5. Success: the model gathers what each section asks for `[ref: PRD/F1-AC2; F1-AC3 model part]`

- [ ] **T4.5 Quarter: reading the split parts in Pass 1** `[activity: backend-api]`

  1. Prime: T3.4's `read-index.json` / `read-<YYYY-MM>.json` and its measurement; SKILL.md step 5 `[ref: SDD/Architecture Decisions; ADR-7]`
  2. Test: `review-doc.py write` loads all parts through T3.4's loader and checks sources across them; skill pins for the quarter branch: read the index, then each month part in turn, then write one `proposals.json`; a quarter document renders with the quarter groups and marks; the interim step 1 line that stops a set-up quarter request ("cannot review a quarter yet", T2.3) is removed together with its pin `test_a_quarter_request_sets_up_and_reads_nothing` and the routing goes on to step 3; `/review setup` walks the quarter like week and month (the "only when `setup.quarter` is present" gate goes); the interim wording also goes from the skill's description ("weekly or monthly"), docs/tomo/dot_claude/skills/periodic-review.md ("The quarter in the same flow") and docs/tomo/dot_claude/commands/review.md ("Why the Shim Carries argument-hint").
  3. Implement: WHY first; the loader call in `review-doc.py`; the skill's quarter branch through `tcs-helper:skill-author`; version bumps. Notes from T3.4: the loader is `lib/review_read_parts.load` (raises `ReadFilesMissing` / `ReadFilesInvalid` → map to `read-missing` / `read-invalid`); `review-doc.py`'s abort, success and failure clean-up paths delete only `read.json` today and must remove a quarter's files through `review_read_parts.stage_files`; `review-read.py` stdout gives `read_path` (the index for a quarter) and `read_parts` — the skill reads those, and the SDD Internal API line for `review-read.py` gains `read_parts`; reject a duplicated part name in `_part_names` and use `fullmatch` for part names (T3.4 review nits); the skill's quarter branch names the quarter keys it reads (`monthly`, `month_text`, `only_in_monthly_links`, `dailies_not_in_monthly`, `report.monthly_status` / `monthly_notes`) the way step 5 names the month's; `docs/tomo/scripts/review-doc.md` (its read.json clean-up WHY) joins the WHY-first list.
  4. Validate: tests green.
  5. Success: a quarter's Pass 1 reads within the Read limit `[ref: PRD/F6-AC6; SDD/Quality Requirements]`

- [ ] **T4.6 Phase Validation** `[activity: validate]`

  - Run all Phase 4 tests and the full suite (GREEN). The unmapped-document byte-identity test green. Drift check against ADR-1/2/11. WHY-first order (git log) and no eval-gated file changed. Lint clean.
