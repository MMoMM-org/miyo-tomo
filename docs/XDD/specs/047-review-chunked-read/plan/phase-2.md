---
title: "Phase 2: Stage layout, limits and the loader"
status: in_progress
version: "1.2"
phase: 2
---

# Phase 2: Stage layout, limits and the loader

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Data Storage Changes]` — `manifest.json`, `days/`, `growth/`, `children/`, `context*.json`, `weeks.json`, the line-broken encoding (SDD v1.2; line refs below predate it and run 2–35 lines low — the section names govern)
- `[ref: SDD/Internal API Changes; lines: 588-636]` — `review-read.py` ok (new / continued), `--measure`, removed keys; `review-doc.py` refusals `read-missing`, `read-stale`; `replace --abort`
- `[ref: SDD/Implementation Examples; lines: 697-751]` — the loader, packing a period into units, `takes_part`
- `[ref: SDD/Error Handling; lines: 939-962]` — oversized day, week over budget, child/context over the ceiling, stale stage, sections changed
- `[ref: SDD/Architecture Decisions; ADR-1, ADR-2, ADR-3, ADR-10; lines: 1160-1180, 1217-1220]`
- `[ref: SDD/Implementation Gotchas; lines: 1305-1309]` — `replace --confirm` loads through the stage; a pre-047 stage; the orphan `review_read_parts.py`

**Key Decisions**:
- One cutter: the cap loop of `review_day.py:261-275` becomes the public `cut_at_boundary`; `has_content` becomes public (ADR-2).
- The loader is the single translation from files to today's merged dict; no consumer of `review-doc.py` changes (ADR-1, CON-4).
- `manifest.json` is written last; a stage without it is no read. `--fresh`, a changed `sections_digest`, an invalid manifest or a pre-047 `read*.json` stage → discard and read anew (ADR-3).
- `discard` deletes every content file and keeps `meta.json` and `payloads.json` (ADR-10).
- Deviation 2026-11-23 (owner, T1.4): the per-file ceiling is 32,768 bytes (was 40,960) for every agent-read file, its parts and the re-cuts (SDD ADR-2 v1.3).
- Deviation 2026-11-23 (owner, T1.5): vault growth is staged per creation day in `growth/<date>.json` and counted in its day's unit budget; `context.json` keeps only `growth.created_count`, `mocs_changed`, `mocs_linked_by_new`; the read `report` lives only in `manifest.json` (SDD ADR-1, ADR-2 amended).
- `condensed.json` and `carryover.json` do not exist yet; `load` returns them as `None` until Phase 4 and `review-doc.py write` does not yet refuse `condense-incomplete`.

**Dependencies**: Phase 1 (T1.5 numbers confirmed or a deviation decided; T1.4 Read smoke). T2.1 ∥ T2.2 → T2.3 → T2.4 → T2.5 → T2.6 (T2.4 is the one switch-over commit; T2.5 is owner-gated).

---

## Tasks

Replaces `read.json` with a stage every agent can read in one call, and a loader that hands `review-doc.py` exactly what it consumes today.

- [x] **T2.1 One cutter and a public `has_content` (`lib/review_day.py`)** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `tomo/scripts/lib/review_day.py` (`_has_content` 151, the cap loop 261-275, the entry keys 297-309), `tests/test_review_day.py`, `docs/tomo/scripts/lib/review_day.md` `[ref: SDD/ADR-2; lines: 1168]` `[ref: SDD/Building Block View; lines: 397]`
  2. Test: `cut_at_boundary(units, max_chars)` cuts at a section boundary and reports partly read exactly as `read_day` did (existing cases re-pointed); a single section over the limit is hard-cut as today; `has_content` is importable and equals the old private result for the existing fixtures; `read_day` output byte-identical for every existing `test_review_day.py` case.
  3. Implement: WHY doc first (`review_day.md`: one cutter, its three callers); extract `cut_at_boundary`, rename `has_content`, keep `read_day` calling it; version 0.3.2 → 0.3.3.
  4. Validate: `test_review_day.py`, `test_review_period*.py` green; ruff clean.
  5. Success: a day over the per-day limit is still read to a section boundary and named partly read `[ref: PRD/F1-AC7]`

- [x] **T2.2 Units of a period (`lib/review_weeks.py`)** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: `tomo/scripts/lib/period.py` (`weeks_overlapping` 185-194, `Period.days`, the week rule), `lib/review_config.py` (week rule config); SDD example "Packing a period into units" `[ref: SDD/Implementation Examples; lines: 722-751]` `[ref: SDD/ADR-2; lines: 1168-1173]`
  2. Test: `tests/test_review_weeks.py` — a week review is one unit, not clipped; 2026-03 under ISO gives units W09 [03-01] … W14 [03-30, 03-31] (clipped, F1-AC2); 2026-Q1 gives 14 units with W01 clipped to 01-01 … 01-04 and W14 to 03-30, 03-31; a non-ISO week rule (first day Sunday, 1 min day) clips under that rule; a week over 81,920 bytes splits into `<week>a`, `<week>b` in date order with no day dropped and every day in exactly one unit (F1-AC1); a unit with no taking-part day has `takes_part: false`; a day with only created notes (no content, tasks or links) takes part; a day's weight is its day file plus its growth files, so a week under budget on day files alone but over it with growth splits by the same date-order rule; a single day over the budget is a unit alone and listed as over budget, never dropped; `digest_cap(14) == 8192`, `digest_cap(16) == 7168`, and `test_digest_cap_bounds_the_total` (units × cap ≤ 114,688 for 1…16 units); constants `FILE_CEILING` 32,768 (owner 2026-11-23 after T1.4; was 40,960), `UNIT_BUDGET` 81,920, `DIGEST_TOTAL` 114,688, `DIGEST_MAX` 8,192 as ADR-2 (v1.3).
  3. Implement: WHY doc `docs/tomo/scripts/lib/review_weeks.md` first; `lib/review_weeks.py` (`units` taking day bytes that include growth bytes, `digest_cap`, the constants); `# version: 0.1.0`.
  4. Validate: tests green; module ≤ 300 lines; ruff clean.
  5. Success: every day of a week, month or quarter belongs to exactly one unit inside the period `[ref: PRD/F1-AC1, F1-AC2]`

- [x] **T2.3 The stage (`lib/review_stage.py`)** `[activity: data-architecture]`

  1. Prime: `tomo/scripts/lib/review_read_parts.py` (`files_of`/`write`/`load`/`stage_files` 110-188 — the dict contract to reproduce), `lib/review_period.py` result keys 400-427, `lib/review_children.py` entries 58-106, `lib/run_id.py`, `lib/note_io.atomic_write_text`; T2.1 and T2.2 outputs; SDD loader example `[ref: SDD/Data Storage Changes; lines: 535-587]` `[ref: SDD/Implementation Examples; lines: 697-720]` `[ref: SDD/ADR-1, ADR-3, ADR-10]`
  2. Test: `tests/test_review_stage.py`:
     - `write` produces `days/<date>.json` for every day of the period (empty days too), `growth/<date>.json` for every day with created notes (entries `{path, links}` sorted by path; parts `growth/<date>-<n>.json` at entry boundaries when over 32,768 B, no entry cut or dropped), `children/<label>-<name>[-<n>].json`, `context.json` (+ `context-<n>.json` parts named in `parts`), `weeks.json`, and `manifest.json` last (a crash before it leaves a stage `load` refuses as missing);
     - every agent-read file is `indent=1`, UTF-8, long texts as line arrays; `test_indented_files_stay_under_the_ceiling` on a scaled 2026-Q1 fixture: every file ≤ 32,768 bytes indented and no line > 2,000 characters;
     - an oversized day is re-cut through `review_day.cut_at_boundary` (≤ 3 tries, then the hard cut) and marked `partly_read`; a child note over the ceiling is cut at a heading boundary (`clipped`); context lists overflow into parts each ≤ 32,768 bytes;
     - `load` returns a dict equal to what `review_read_parts.load` returned for the same read (golden comparison on the month and quarter fixtures, lines joined back), with `previous`, `condensed`, `carryover` added (`[]` / `None` / `None` for now); a quarter day file holds the same `read_day` entry as the same day in a week read (F1-AC2); `context.json` carries the whole-period link-difference lists and per-day `fields` (F2-AC3) and growth only as `created_count`, `mocs_changed`, `mocs_linked_by_new` (no per-note list); `load` rebuilds `growth.created` from `growth/` equal to the read's list; `test_growth_goes_to_the_day_it_was_created` (every created note in exactly one growth file, of the local day of its `created`; an entry without `created` on the period's first day); no agent-read file holds the read `report` (only `manifest.json` does);
     - `load` raises stale on any file whose `read_id` differs from the manifest, and missing on a pre-047 stage;
     - `sections_digest` is stable for equal definitions and changes when a mapping row changes; the continue check is true only when layout, period, kind and `sections_digest` match;
     - `test_discard_leaves_only_meta_and_payloads` (every content file and any legacy `read*.json` removed; F7-AC1); a new read discards all earlier material first (F6-AC5).
  3. Implement: WHY doc `docs/tomo/scripts/lib/review_stage.md` first (carrying the history of `review_read_parts.md`); `lib/review_stage.py` (`write` incl. `growth/` and its parts, `load`, `discard`, `can_continue`, `sections_digest`, the encoding and the ceiling measure); `# version: 0.1.0`. `lib/review_period.py` `_growth` keeps each created entry's `day` (local date of Kado's `created`, the `period_bounds_ms` convention) — WHY line in `docs/tomo/scripts/lib/review_period.md` first, version 0.5.1 → 0.5.2, `test_review_period_golden.py` changes by that key only; check `_inbox/from-kado` first that `listNotes` with `fields: ["links"]` still returns `created` (SDD Implementation Gotchas).
  4. Validate: tests green; module ≤ 300 lines (split encoding helpers out if not, as a recorded deviation); ruff clean.
  5. Success: the read rests in files an agent reads in one call, and is loaded back unchanged `[ref: PRD/F2-AC3, F6-AC5, F7-AC1]` `[ref: SDD/ADR-1, ADR-2, ADR-3]`

- [ ] **T2.4 Switch to the stage: `review-read.py` writes it, `review-doc.py` and the walk load it** `[activity: backend-api]`

  One task and one commit (owner 2026-11-23): the read side and the load side change together, so the suite is GREEN before and after the commit and never sees a stage nobody reads or a loader with no stage.

  1. Prime:
     - `tomo/scripts/review-read.py` (one `KadoClient` + one `ReviewPacer` 174-190, stop rules 231-235, `--measure` 200-209 and 242-244, the writes 241 and 247), `docs/tomo/scripts/review-read.md`;
     - `tomo/scripts/review-doc.py` (`_load_read` 208-215, `_drop_stage_content` 218-220, `render_and_write` 270-325, `replace --abort` 359-361), `docs/tomo/scripts/review-doc.md`; `lib/review_habits.py` `habits` 307-313;
     - `tests/test_review_read.py`, `tests/test_046_t4_5_quarter_read.py`, `tests/test_review_read_parts.py`, `tests/test_review_doc.py`, `tests/test_review_e2e*.py`, `tests/review_e2e_walk.py`, `tests/test_047_baseline_e2e.py`, `tests/test_review_privacy.py` (tmp-leak allowlist ~212);
     - `tomo/dot_claude/skills/periodic-review/SKILL.md` step 4 (which output keys it names)
     `[ref: SDD/Internal API Changes; lines: 591-600, 625-636]` `[ref: SDD/Complex Logic (c); lines: 1017-1034]` `[ref: SDD/ADR-1, ADR-3, ADR-10]` `[ref: SDD/Implementation Gotchas; lines: 1305-1308]`
  2. Test:
     - read side: a new read prints `continued: false`, `read_id`, `read_at`, `stage`, `units`, the report as today, and no `read_path` / `read_parts`; `days/` holds only the period's days while the day after contributes only its yesterday fields (F1-AC6); `test_continued_read_makes_no_kado_call` (fake Kado call count 0, stored report, `read_at` of the first read; F6-AC4); `--fresh`, a changed mapping (`discarded: sections-changed`), an invalid manifest (`stage-invalid`) and a pre-047 stage each read anew after discarding; the stops (`kado-unreachable`, `kado-auth`, `setup-*`, `daily-not-configured`, `dailies-not-read`) and `nothing_to_review` write nothing and leave nothing to continue (F2-AC5); missing weekly/monthly notes reported as specs 045/046 define (F2-AC5); `--measure` reports bytes per stage file (growth files included), unit bytes (day files + growth files), `over_ceiling`, `over_budget` and writes no file;
     - load side: `write` and `replace --confirm` load through `review_stage.load`; `read-missing` with no manifest (also a pre-047 stage) and `read-stale` with a mismatched `read_id`; after `write` and after `replace --abort` only `meta.json` and `payloads.json` remain (`growth/` removed too); the not-read and top lines still render from `manifest.json`'s `report`; `review-exists` keeps the stage for `replace --confirm`; habits count or average every day of a quarter that carries a value (F2-AC4, on the quarter fixture);
     - together: the walk (`tests/review_e2e_walk.py`) and every e2e run on the new stage; the tmp-leak allowlist names the new content files (`growth/` included); `test_review_period_golden.py` and the other tests in the SDD's "changed by design" list move with the layout; `grep -rn "review_read_parts\|read_path\|read_parts\|read-index" tomo tests docs/tomo` (untruncated) shows no live reference outside history text and the SKILL.md lines T6.3 rewrites; the baseline e2e (T1.3) is GREEN with its golden files unchanged.
  3. Implement: WHY docs `docs/tomo/scripts/review-read.md` and `docs/tomo/scripts/review-doc.md` first; `review-read.py` 0.3.2 → 0.4.0 through `review_stage` (docstring rewritten for the new output); `review-doc.py` 0.7.2 → 0.8.0 (loader, refusals, `discard` at write and on `replace --abort`); the walk and the e2e tests switched; delete `lib/review_read_parts.py`, `tests/test_review_read_parts.py`, `docs/tomo/scripts/lib/review_read_parts.md` (its history already in `review_stage.md`); move the by-design tests; add any new `tests/test_review_*.py` file to spec 047's `solution.md` Directory Map (Tests block). If a skill contract test fails only because SKILL.md step 4 names `read_path`, rename that key in SKILL.md (WHY line in `docs/tomo/dot_claude/skills/periodic-review.md` first, version bump) and nothing else — the full rewrite is T6.3.
  4. Validate: full suite green in ONE invocation before and after the commit; `test_review_sdd_map.py` green; ruff clean.
  5. Success: a read is stored as a stage, an interrupted Pass 1 continues on it without Kado, and the document is built from it exactly as from `read.json` with no material left after write or abort `[ref: PRD/F1-AC6, F2-AC4, F2-AC5, F6-AC4, F7-AC1]` `[ref: SDD/ADR-1, ADR-3]`

- [ ] **T2.5 Size measurement of 2026-Q1 on the new stage (owner go)** `[activity: validate]`

  1. Prime: T2.4 `--measure` output; T1.5 notes `[ref: SDD/ADR-2; lines: 1172]` `[ref: SDD/Quality Requirements/Performance (hard); lines: 1234]`
  2. Test, owner-gated: announce, wait for the go, run `python3 tomo/scripts/review-read.py --kind quarter --period 2026-Q1 --stem 2026-Q1_review --measure` against the test instance (never `tomo-privat`), report at once.
  3. Implement: record counts only under this task: per-file bytes (max day, max growth file and its parts, max child, context and parts), growth bytes per unit, unit bytes (day files + growth) for all 14 units, `over_ceiling`, `over_budget`. If any limit fails or is far off, bring the change to the owner as a deviation before Phase 4 (constants only).
  4. Validate: `over_budget` empty; no file written; no journal text recorded.
  5. Success: the real quarter fits the limits with no day and no created note left out `[ref: PRD/F1-AC1; SDD/Quality Requirements; SDD/ADR-2 amended]`

- [ ] **T2.6 Phase Validation** `[activity: validate]`

  - Full suite in ONE invocation — GREEN, including the baseline e2e unchanged; ruff clean. Trace F1-AC1, F1-AC2, F1-AC6, F1-AC7, F2-AC3, F2-AC4, F2-AC5, F6-AC4 (script part), F6-AC5, F7-AC1 to node ids. Check every WHY doc landed before its code change (git log order). Confirm no eval-gated file changed and `settings.json` is byte-identical.
