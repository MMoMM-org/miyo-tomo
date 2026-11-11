---
title: "Phase 2: Setup and session start"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Setup and session start

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Data Storage Changes; lines: 451-494]`: the `review:` section and the calendar/naming/templates keys.
- `[ref: SDD/Internal API Changes; lines: 495-540]`: `review-session.py start|match|setup-input`, `vault-config-writer.py review`.
- `[ref: SDD/Implementation Examples; lines: 646]`: week-rule inference.
- `[ref: SDD/Architecture Decisions; ADR-5, ADR-7, ADR-8]`

**Key Decisions**:
- Never hand-compose YAML: the writer edits text and keeps comments and other sections byte-identical (ADR-5).
- The week rule comes from the user's weekly notes or the user's answer; the Obsidian plugin configuration is never read (ADR-7).
- A Templater template is recorded with its kind (`templater`); a `template_variant` may be named (ADR-8).

**Dependencies**:
- Phase 1 (T1.1 period). T2.1 and T2.2 may start as soon as T1.1 is done.

---

## Tasks

This phase lets the vault keeper confirm the setup once and lets every `/review` start know what was asked and what is still open.

- [ ] **T2.1 Review config and writer subcommand** `[activity: data-architecture]` `[parallel: true]`

  1. Prime: `tomo/scripts/vault-config-writer.py:9-17, 826, 888, 947-968`; `tomo/schemas/vault-config-templates.schema.json`; `tomo-instance/config/vault-config.yaml:22-27, 439-449, 474-638` (read only); `tomo/profiles/miyo.yaml:48-49` `[ref: SDD/Data Storage Changes; ADR-5]`
  2. Test: `tests/test_vault_config_writer_review.py` and `tests/test_review_config.py` — the writer adds `review:` and sets weekly/monthly granularities, patterns and template mapping, leaves every other byte unchanged, refuses duplicate keys and schema violations, fixes the daily path only when the input says so; `review_config` layers config over profile, validates, reports `place_level` and refuses a level above 6; tracker types read from `trackers.daily_note_trackers`.
  3. Implement: `tomo/schemas/vault-config-review.schema.json`, the `review` subcommand, `tomo/scripts/lib/review_config.py`; WHY docs (`vault-config-writer.md`, `lib/review_config.md`) first; version bumps.
  4. Validate: writer and config tests green; existing writer tests green; ruff clean.
  5. Success: a confirmed setup is saved without touching anything else `[ref: PRD/F1-AC9, F1-AC10]`

- [ ] **T2.2 Setup preview (`match`, `setup-input`)** `[activity: backend-api]` `[parallel: true]`

  1. Prime: `tomo/scripts/note-session.py` (match flow); `skills/note-from-template/SKILL.md:62-76`; `[ref: SDD/Internal API Changes; SDD/Implementation Examples (week-rule inference)]`
  2. Test: `tests/test_review_session.py::match*` on a fake vault — ISO weeklies with `journal-start-date` give `GGGG-[W]WW`, Monday, `week_rule: inferred`; notes without dates or with contradicting starts give `ambiguous`; no notes → ISO and `YYYY-MM` with "no notes to compare"; matched and unmatched names listed; a Sunday rule re-lists the notes it no longer matches; template kinds `plain|templater|missing|unreadable`; the daily-path fix is proposed only when the folder lookup finds the other spelling; `setup-input` writes a schema-valid writer input from a confirmed proposal; the plugin config path is never requested from Kado.
  3. Implement: `tomo/scripts/review-session.py match|setup-input`; WHY doc `docs/tomo/scripts/review-session.md` first.
  4. Validate: tests green; RED proven for the inference by mutation in an isolated copy; ruff clean.
  5. Success: the setup proposal shows what it matches and asks only when it cannot tell `[ref: PRD/F1-AC1, F1-AC3..AC8]`

- [ ] **T2.3 Session start (`start`)** `[activity: backend-api]`

  1. Prime: `note-session.py start`; `lib/note_meta.list_stages` (`note_meta.py:239-257`); `[ref: SDD/Complex Logic; lines: 801-815]`
  2. Test: `tests/test_review_session.py::start*` — every argument form yields the request or an `error` with kind, expectation and one valid example; an `@` note that fits no name format yields `not-periodic-note`; `setup` returns the current values; missing setup per kind reported; open review documents found by `tomo.doc_type=review` in the inbox (also when renamed) and listed by period and state `open`/`failed-delivery` from document and `meta.json` (the delivered/applied states arrive in T4.3); stdout carries no note text.
  3. Implement: `review-session.py start`; doc update first.
  4. Validate: tests green; ruff clean.
  5. Success: `/review` knows the request and every open review before it does anything else `[ref: PRD/F1-AC2, F2-AC1, F2-AC3..AC8]`

- [ ] **T2.4 Phase Validation** `[activity: validate]`

  - Run Phase 1–2 tests, the full suite and ruff. Check the writer leaves a copy of `tomo-instance/config/vault-config.yaml` byte-identical outside the written keys (on a temp copy, never the instance file).
