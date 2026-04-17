# 2026-04-17 — Daily Note Workflow Extension (spec 005)

## Summary

Extended the Pass-1 inbox pipeline and Pass-2 instruction builder to handle
daily-note targets: tracker updates, log entries, and log links. Added two
`/tomo-setup` sub-wizards for configuring tracker semantics and daily-log
settings. Spec 005 is now complete.

## Why

Inbox items often belong in the daily log (run notes, mood logs, short
reflections) rather than as standalone atomic notes. The fan-out pipeline
from spec 004 needed three new evaluation dimensions per item — tracker
match, log-entry candidate, and log-link candidate — so the Suggestions
document could propose all three categories in one pass.

The wizard-driven config approach avoids hand-editing YAML for per-field
tracker descriptions and daily-log preferences.

## Changes

### New files

- `tomo/.claude/skills/tomo-trackers-wizard.md` — AskUserQuestion-driven
  flow for adding description + positive/negative keywords per tracker field.
  Edit-tool writes back to vault-config; never rewrites the whole file.
- `tomo/.claude/skills/tomo-daily-log-wizard.md` — Configures `daily_log:`
  section: heading, heading level, time-extraction sources, fallback strategy,
  cutoff days, auto-create flags (MVP-locked to false).
- `scripts/test-005-phase5.sh` — Phase 5 acceptance tests (12 checks).
- `scripts/fixtures/test-005-phase5/` — fixture vault-configs + Python
  assertion scripts for wizard output and instruction-builder handler format.

### Modified files

- `tomo/.claude/commands/tomo-setup.md` → Phase 3b added (detect missing
  tracker descriptions → offer trackers wizard; detect missing daily_log →
  offer daily-log wizard). Mode B gains `trackers` and `daily-log` shortcuts.
- `tomo/.claude/agents/instruction-builder.md` → Step 6.1 (log_entry handler)
  and Step 6.2 (log_link handler) added. Both resolve `daily_log.section` and
  `heading_level` from vault-config; both include the "If daily note doesn't
  exist: Create first" fallback instruction.
- `tomo/.claude/agents/inbox-analyst.md` → Step 8b rewrite: three-way
  classification (tracker / log-entry / log-link), log-format heuristic,
  multi-daily split, cutoff guard.
- `scripts/suggestions-reducer.py` → daily_notes_updates[] block with
  date-sorted entries, per-entry tracker/log_entry/log_link buckets,
  Material-für mirror for log_link items, decision_precedence_note.
- `tomo/config/vault-example.yaml` → added `trackers.*.keywords` fields,
  `daily_log:` section.
- All source files mirrored to `tomo-instance/.claude/`.
- `docs/XDD/specs/005-daily-note-workflow/README.md` → Status: Completed.

## Decisions (locked)

All 7 ADRs from the spec remain confirmed:

1. Three evaluation dimensions per inbox item (tracker, log_entry, log_link)
2. `log_entry` vs `log_link` driven by `atomic_note_worthiness`
3. Polymorphic `updates[]` inside existing `update_daily` action
4. Multi-daily targeting only when content reads as log-format
5. Cutoff default 30 days
6. Daily-note-create surfaced as checkbox only; actual create by plugin
7. Wizard-managed tracker descriptions + daily-log config via `/tomo-setup`

## Validation

- `scripts/test-005-phase5.sh`: 12/12 pass
- `scripts/test-005-phase4.sh`: all pass (regression)
- `scripts/test-005-phase3.sh`: all pass (regression)
- `scripts/test-005-phase1.sh`: all pass (regression)
- `scripts/test-004-phase{2,3,4}.sh`: all pass (spec-004 regression)

Real-vault validation (Task 5.5) requires a live `/inbox` run against the
user's real inbox with items spanning all three categories — pending the
first post-migration session.
