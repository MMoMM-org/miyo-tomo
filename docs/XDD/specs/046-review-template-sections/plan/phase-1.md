---
title: "Phase 1: Foundations — config, writer, template analysis, quarter period"
status: in_progress
version: "1.0"
phase: 1
---

# Phase 1: Foundations — config, writer, template analysis, quarter period

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Data Storage Changes]` — `review.<g>.sections.<template>`, `off_limits`, `quarterly`, `rows-<kind>.json`
- `[ref: SDD/Implementation Examples/Template analysis]` — rules, line classes, the traced `t_week_privat`
- `[ref: SDD/Runtime View/Complex Logic]` — `landing_off_limits` paragraph after `plan_section`
- `[ref: SDD/Architecture Decisions; ADR-3, ADR-6, ADR-8, ADR-9]`
- `[ref: SDD/Implementation Gotchas]` — `%% fold %%` kept verbatim; `own_sections` vs off-limits rows

**Key Decisions**:
- Never hand-compose YAML; the writer renders lists of mappings block-style, quotes keys, and removes a key on an empty value; every other byte stays (ADR-3, spec 045 ADR-5).
- The analysis is deterministic and conservative: `automatic` only when every body line is automatic; `tp.file.cursor`, callouts and comments are neutral; `mixed` is offered (ADR-9).
- Off-limits: heading only or with sub-sections; a heading is covered when a row names it or a `with_subsections` row names an ancestor; one function `landing_off_limits` (ADR-8).
- The quarter is a period kind with the `Q` token and default `YYYY-[Q]Q`; `KINDS` gains `quarter` (ADR-6).

**Dependencies**: none. T1.1, T1.2 and T1.4 run in parallel; T1.3 needs T1.1 and T1.4 (`GRANULARITY[QUARTER]` needs `period.QUARTER`).

---

## Tasks

Establishes the storage, the template analysis and the quarter as a period, on which setup, reading and delivery build.

- [x] **T1.1 Writer renders lists of mappings and quoted keys** `[activity: data-architecture]` `[parallel: true]`

  1. Prime: `tomo/scripts/lib/vault_config_edit.py` (`render_scalar` 109, `render_leaf` 121, `render_tree` 127, `set_path` 156); `tests/test_vault_config_writer_review.py`; `docs/tomo/scripts/lib/vault_config_edit.md` `[ref: SDD/Data Storage Changes; ADR-3]`
  2. Test: a list of mappings renders block-style and reads back equal; a key with spaces, a colon or non-ASCII (`"t_week privat: v2.md"`, `Übersicht`) is quoted and reads back; `[]` or `null` removes the key; a second template's rows under the same parent stay byte-identical; every other line of a copy of the instance config stays byte-identical; existing writer tests stay green.
  3. Implement: the three rendering capabilities in `vault_config_edit.py`; WHY doc first; version bump.
  4. Validate: writer tests green; ruff clean.
  5. Success: the writer can store per-template rows without touching anything else `[ref: PRD/F2-AC10]`

- [ ] **T1.2 Template analysis and off-limits (`lib/review_mapping.py`)** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `tomo/scripts/lib/review_md.py` (`body` 48, `fence_state` 58, `headings` 69, `QUERY_FENCES`/`EMBED_FENCES` 26); `tomo/scripts/lib/template_syntax.py` (`templater_spans` 256, `_templater_inner_line_indexes` 265 and its callers); `tomo/scripts/lib/review_day.py` (`_EMBED_LINE_RE` 45, `_FIELD_RE` 46); `tests/test_review_sdd_map.py:35-50`; `tomo/scripts/lib/review_actions.py` (`bare` 252); the test vault templates `X/900 Support/930 Templater/t_{week,month,quarter}_privat.md`, `t_{week,month}_work.md` (structure only) `[ref: SDD/Implementation Examples/Template analysis; ADR-8; ADR-9]`
  2. Test: `tests/test_review_mapping.py` with structural fixtures copied from the five templates (headings and body line shapes, no journal text): each rule left-outs its heading with its reason (templater, link, per-period-parent incl. the 3-parent repeat and the container case, off-limits heading-only and with sub-sections, automatic); `mixed`, `container` and `under-own` flags; cursor placeholders count as empty; a heading-looking line inside a `<%* … %>` block or in frontmatter is no heading; `%% fold %%` kept verbatim; duplicates keyed by (text, level, parent, occurrence); `landing_off_limits` for a named row, an ancestor with sub-sections, an ancestor without; the expected offered/left-out sets for all five templates (the SDD's traced `t_week_privat` list, and for the other four the sets written first into the SDD's Template analysis example as part of this task) match; each rule RED-proven by reverting it; `test_review_sdd_map.py` reads spec 045's and spec 046's Directory Maps and stays green with the new lib, its WHY doc and its test.
  3. Implement: `lib/review_mapping.py` (`analyse_template`, heading identity, row id assignment `s<n>` kept per heading key, `landing_off_limits`, `dropped`); `AUTOMATIC_FENCES` and the shared inline-field / embed regexes in `review_md.py`, with `review_day.py` importing them; `_templater_inner_line_indexes` made public in `template_syntax.py` and its callers updated; `test_review_sdd_map.py` taught to read both maps (spec 046's per-file `docs/tomo/` and `tests/` blocks); WHY docs first; version bumps.
  4. Validate: new and existing tests green (`test_review_md*`, `test_template_syntax*`); ruff clean; module ≤ 300 lines.
  5. Success: the setup can offer exactly the headings the rules allow, with reasons `[ref: PRD/F2-AC3, F2-AC5, F2-AC11]`

- [ ] **T1.3 Config schema and reader: sections, off-limits, quarterly** `[activity: data-architecture]`

  1. Prime: `tomo/schemas/vault-config-review.schema.json` (place 57-71, own_sections 72); `tomo/scripts/lib/review_config.py` (`GRANULARITY` 47, `ReviewSetup` ~99-122, `review_setup` 194-266, `input_problems` 319, `writer_edits` 335); `tomo/scripts/vault-config-writer.py` `cmd_review` 950-1000; `tomo/config/vault-example.yaml` ~555-585 `[ref: SDD/Data Storage Changes; ADR-3]`
  2. Test: schema accepts a row with each placement incl. `review`, refuses `habits` in `groups`, an id outside `^s[0-9]{1,3}$`, a cap outside 1..30, an empty description, an unknown field; `off_limits` rows with `with_subsections`; `review.quarterly` keys; `review_setup` selects only the configured template's rows (F2-AC8) and returns pointers for invalid rows; `input_problems` refuses duplicate heading keys and duplicate ids; `writer_edits` touches only `sections.<template>` / `off_limits.<template>`; the writer round-trip saves rows and reads them back; a config without the new keys behaves exactly as before.
  3. Implement: schema, `review_config.py` (`sections`, `off_limits` on `ReviewSetup`; `GRANULARITY[QUARTER]`), writer edits; documented example in `vault-example.yaml`; WHY docs first; version bumps.
  4. Validate: `test_review_config.py`, `test_vault_config_writer_review.py` green; ruff clean.
  5. Success: rows and off-limits marks are stored per template and read back for the configured one `[ref: PRD/F2-AC7, F2-AC8, F2-AC10]`

- [ ] **T1.4 Quarter as a period kind** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `tomo/scripts/lib/period.py` (`KINDS` 28-31, `DEFAULT_FORMATS` 34, `_TOKENS` 36, `Period` 123-176, `weeks_overlapping` 167, `format_kind` 221, `check_format` 301, `parse_args` 384, `_parse_period_word` 425, `_latest_finished_with_number` 460, `_parse_at` 473); `lib/review_templates.py` `KIND_WORDS` 45; `lib/review_state.py` `_infer_kind` 322; `review-session.py:251`; `tests/test_period.py` `[ref: SDD/Architecture Decisions; ADR-6]`
  2. Test: `Period.quarter` bounds and `2026-Q5` → `InvalidPeriod`; `containing`, `previous`, `months()`, `weeks_overlapping` for 2026-Q1 (W01 starts 2025-12-29, W14 ends 2026-04-05); the `Q` token renders and parses `YYYY-[Q]Q`; `format_kind` exactly-one over three kinds; `/review quarter` on 2026-11-14 → 2026-Q3; `2026-Q1`; `Q1` → most recent finished with `year_inferred`; `2026-Q5` → `invalid-period` with example `2026-Q4`; an unfinished quarter → `unfinished-period`; an @-picked `2026-Q1` note; `_infer_kind("2026-Q1")` is quarter; every existing `test_period.py` case stays green.
  3. Implement: the quarter in `period.py` (`_latest_finished_with_number` 459, `_parse_at` 472), `KIND_WORDS`, `_infer_kind`, `review-session.py:251` (`kind != WEEK`); grammar and expected texts; WHY docs first; version bumps. If `period.py` would exceed 500 lines, stop and bring the split (an SDD Technical Debt follow-up) to the owner as a deviation; do not split unasked.
  4. Validate: `test_period.py`, `test_review_state*.py`, `test_review_session.py` green; ruff clean.
  5. Success: every quarter argument resolves or is refused as the PRD says `[ref: PRD/F6-AC2, F6-AC3]`

- [ ] **T1.5 Phase Validation** `[activity: validate]`

  - Run all Phase 1 tests and the full suite once. Check each WHY doc landed before its runtime/code change (git log order). Lint clean. Confirm no eval-gated file changed.
