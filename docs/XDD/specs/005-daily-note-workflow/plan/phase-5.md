---
phase: 5
title: "Wizards + Pass-2 + validation"
status: in_progress
depends_on: [1, 2, 3, 4]
---

# Phase 5 — Wizards + Pass-2 handlers + validation

## Goal

User can configure tracker semantics and daily-log settings via
`/tomo-setup` sub-wizards. Pass-2 handles `log_entry` and `log_link`
update kinds. End-to-end real-vault run produces a correct Suggestions
document.

## Acceptance Gate

- [ ] `/tomo-setup trackers` walks every tracker field, collects
  description + keywords, writes to vault-config.
- [ ] `/tomo-setup daily-log` collects daily-log config, writes to
  vault-config.
- [ ] `/tomo-setup` (full flow) runs the two sub-wizards after Phase 3
  when respective config sections are missing/incomplete.
- [ ] Pass-2 `instruction-builder` emits usable instructions for
  `log_entry` and `log_link`.
- [ ] A real-vault `/inbox` run produces a document matching all the
  format rules of this spec.
- [ ] Sub-wizard skill names use `tomo-*` prefix.

## Tasks

### 5.1 `tomo-trackers-wizard` skill

New file `tomo/.claude/skills/tomo-trackers-wizard.md`. Skill-format
walkthrough:

- Read vault-config tracker fields.
- For each field, AskUserQuestion:
  - "What does `<field>` track?" (free text → description)
  - "Keywords that should trigger a match? (comma-separated)" → positive_keywords
  - "Keywords that should SUPPRESS a match even if positives hit?" → negative_keywords
- After each field: confirm + move on, or skip this field, or abort.
- End of flow: write back to `vault-config.yaml`. Preserve other config
  sections verbatim; only touch `trackers.*.today_fields[]` and
  `end_of_day_fields.fields[]` entries.

### 5.2 `tomo-daily-log-wizard` skill

New file `tomo/.claude/skills/tomo-daily-log-wizard.md`. AskUserQuestion
flow:

- Section name (default "Daily Log")
- Heading level (1 or 2)
- Time-extraction sources (multi-select: content, filename, frontmatter, mtime)
- Fallback (append_end_of_day / append_start_of_day / skip_time)
- Cutoff days (number, default 30)
- (Future-flagged) auto_create_if_missing — MVP: inform user these are
  locked to false; offer to set the flags for future use with a clear
  "not active yet" note.
- Write back to vault-config `daily_log:`.

### 5.3 `/tomo-setup` integration

Update `tomo/.claude/commands/tomo-setup.md`:

- Add Phase 3b between existing Phase 3 (user-rules) and Phase 4
  (template verification).
- Phase 3b flow:
  - Detect missing/incomplete tracker descriptions (empty
    `description` for any tracker field) → offer `tomo-trackers-wizard`.
  - Detect missing `daily_log` section → offer `tomo-daily-log-wizard`.
  - Each offered via AskUserQuestion ("Run wizard now / Skip").
- Mode-B direct entries:
  - `/tomo-setup trackers` → sub-wizard directly
  - `/tomo-setup daily-log` → sub-wizard directly

### 5.4 Pass-2 handlers

`tomo/.claude/agents/instruction-builder.md`:

- New Step 6.1 — Daily Log Entry handler:
  - For each `log_entry` in confirmed suggestions:
    - Instruction: "Open `[[<daily-note-stem>]]`. Find (or create) section
      `## <daily_log.section>`. Insert at time slot `<time>` or append at
      end per `time_extraction.fallback`. Content: `<content>`."
  - If daily note doesn't exist: precede with "Create `[[<daily-note-stem>]]`
    first (your create plugin or manual)."
- New Step 6.2 — Daily Log Link handler:
  - "Under `## <daily_log.section>`, add `- [[<target_stem>]]` bullet at
    `<time>` slot or append."
  - Same create-first prefix when missing.

Both steps re-use the `daily_log.section` + `heading_level` from
vault-config at instruction-generation time.

### 5.5 Real-vault validation

Document procedure in `phase-5.md`:

1. User updates vault-config via wizards.
2. Runs `/inbox` on a real inbox with:
   - At least one short run-log item (for tracker + log_entry).
   - At least one substantive article note (for atomic + log_link).
   - At least one multi-date log file (for multi-daily split).
   - At least one year-old item (for cutoff).
3. User inspects:
   - Top-of-doc Daily Notes Updates block present.
   - Render order matches spec.
   - Checkboxes usable.
   - Year-old item has no update_daily actions.
4. User approves, runs Pass 2, verifies instruction set references correct sections.
5. User applies one log_entry + one log_link manually.
6. Cleanup phase completes without error.

### 5.6 Tests

`scripts/test-005-phase5.sh`:

- Wizard-written vault-config passes validate.
- Pass-2 handlers produce expected instruction text for log_entry +
  log_link fixtures.
- Regression: `bash scripts/test-004-phase{2,3,4}.sh` still pass.
- Regression: `bash scripts/test-005-phase{1,2,3,4}.sh` still pass.

## Close

This spec (005) moves to `Completed`. Update
`docs/XDD/specs/005-daily-note-workflow/README.md` Status. Write an
evolution note at `docs/evolution/<YYYY-MM>/` mirroring the one from
Spec 004.
