---
title: "Phase 2: Setup and session start"
status: completed
version: "1.1"
phase: 2
---

# Phase 2: Setup and session start

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Data Storage Changes]`: the `review:` section and the calendar/naming/templates keys.
- `[ref: SDD/Internal API Changes]`: `review-session.py start|match|setup-input`, `vault-config-writer.py review`, exit codes.
- `[ref: SDD/Implementation Examples/the week rule and ISO week 53 (week-rule inference)]`
- `[ref: SDD/Runtime View/Error Handling]`: rows for `start`, `match`, `setup-input`, writer.
- `[ref: SDD/Architecture Decisions; ADR-5, ADR-7, ADR-8]`

**Key Decisions**:
- Never hand-compose YAML: the writer edits text and keeps comments and other sections byte-identical, including when it inserts absent nested keys (ADR-5).
- The week rule comes from the user's weekly notes or the user's answer; the Obsidian plugin configuration is never read (ADR-7).
- A Templater template is recorded with its kind (`templater`); a `template_variant` may be named (ADR-8).
- Placement is `before` or `inside`; `after` is never offered (ADR-3).

**Dependencies**:
- Phase 1 (T1.1 period). T2.1 and T2.2 may start as soon as T1.1 is done.

---

## Tasks

This phase lets the vault keeper confirm the setup once and lets every `/review` start know what was asked and what is still open.

- [x] **T2.1 Review config and writer subcommand** `[activity: data-architecture]` `[parallel: true]`

  1. Prime: `tomo/scripts/vault-config-writer.py:9-17, 730, 826, 888, 947-968`; `tests/test-vault-config-writer.py`; `tomo/schemas/vault-config-templates.schema.json`; `tomo-instance/config/vault-config.yaml:21-27, 439-449, 474-638` (read only); `tomo/profiles/miyo.yaml:48-49` `[ref: SDD/Data Storage Changes; ADR-5]`
  2. Test: `tests/test_vault_config_writer_review.py` and `tests/test_review_config.py` — on a copy of the instance config the writer inserts absent nested keys (`concepts.calendar.granularities.weekly`, 4 levels deep), creates the missing `naming:` and `review:` sections, sets patterns and template mapping, leaves every other byte unchanged, refuses duplicate keys and schema violations (`status: refused` with pointers), fixes the daily path only when the input says so; `review_config` layers config over profile, validates, owns `place_level` (before → anchor level, inside → +1, refuses `after`; the review heading may not exceed level 5 — its groups stay ≤ 6), and `inbox_path()` refuses `/`, `\`, `..` and any result outside the inbox; tracker types read from `trackers.daily_note_trackers`.
  3. Implement: `tomo/schemas/vault-config-review.schema.json`, the `review` subcommand, `tomo/scripts/lib/review_config.py`; WHY docs (`vault-config-writer.md`, `lib/review_config.md`) first; version bumps.
  4. Validate: writer and config tests green; existing writer tests green; ruff clean.
  5. Success: a confirmed setup is saved without touching anything else; `/review setup` can change it `[ref: PRD/F1-AC2, F1-AC9, F1-AC10]`

- [x] **T2.2 Setup preview (`match`, `setup-input`)** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `tomo/scripts/note-session.py` (match flow); `skills/note-from-template/SKILL.md:62-76`; `[ref: SDD/Internal API Changes; SDD/Implementation Examples (week-rule inference)]`
  2. Test: `tests/test_review_session.py::match*` on the fake vault — ISO weeklies with `journal-start-date` give `GGGG-[W]WW`, Monday, `week_rule: inferred`; notes without dates or with contradicting starts give `ambiguous`; no notes → ISO and `YYYY-MM` with "no notes to compare"; an empty listing of the weekly folder gives `folder_listing: kado-none` (never "no notes"); matched and unmatched names listed; a Sunday rule re-lists the notes it no longer matches; template kinds `plain|templater|missing|unreadable` with the no-access wording for `unreadable`; an unsafe format gives `error.kind = unsafe-format`; Kado unreachable gives `status: stopped`; the daily-path fix is proposed only when the folder lookup finds the other spelling; `setup-input` writes a schema-valid writer input from a confirmed proposal and returns `invalid` with pointers otherwise; the plugin config path is never requested from Kado.
  3. Implement: `tomo/scripts/review-session.py match|setup-input` (top-level exception handler); WHY doc `docs/tomo/scripts/review-session.md` first.
  4. Validate: tests green; RED proven for the inference by mutation in an isolated copy; ruff clean.
  5. Success: the setup proposal shows what it matches and asks only when it cannot tell `[ref: PRD/F1-AC1, F1-AC3, F1-AC4, F1-AC5, F1-AC6, F1-AC7, F1-AC8]`

- [x] **T2.3 Session start (`start`)** `[activity: backend-api]`

  1. Prime: `note-session.py start`; `lib/note_meta.list_stages` (`note_meta.py:239-257`); `[ref: SDD/Complex Logic (review_state)]`
  2. Test: `tests/test_review_session.py::start*` — no argument gives the last finished week under the configured rule, `month` the last finished month; every argument form yields the request or an `error` with kind, expectation and one valid example; an `@` note that fits no name format yields `not-periodic-note`; week 53 and year-spanning weeks resolve under the rule; `setup` returns the current values; missing setup per kind is reported so the skill runs the setup first; open review documents are found by `tomo.doc_type=review` in the inbox plus one `read_frontmatter` per hit (also when renamed) and listed by period with the state from `review_state` (`open`/`failed-delivery` here; the others arrive in T4.3); Kado unreachable gives `status: stopped`; stdout carries no note text.
  3. Implement: `review-session.py start`; a first `lib/review_state.py` with the `open` and `failed-delivery` branches; docs first.
  4. Validate: tests green; ruff clean.
  5. Success: `/review` knows the request and every open review before it does anything else `[ref: PRD/F2-AC1, F2-AC2, F2-AC3, F2-AC4, F2-AC5, F2-AC6, F2-AC7, F2-AC8, F2-AC9]`

- [x] **T2.4 Phase Validation** `[activity: validate]`

  - Run Phase 1–2 tests, the full suite and ruff. Check the writer leaves a copy of `tomo-instance/config/vault-config.yaml` byte-identical outside the written keys (on a temp copy, never the instance file).
