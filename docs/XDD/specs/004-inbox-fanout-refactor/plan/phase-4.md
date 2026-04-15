# Phase 4 — Daily-Note Tracker Actions

## Goal

Extend `actions[]` polymorphism from only `create_atomic_note` to also
`update_daily`. An inbox item can produce zero, one, or both in the same
`actions[]`. Zero atomic + one daily is a pure tracker item; one atomic +
one daily is a mixed case (e.g. "morning run note").

## Prerequisites

- Phase 3 complete — `actions[]` is already an array in schema and reducer.
- User has created at least one inbox fixture that implies a tracker entry
  (e.g. `20260415-0700_run.md` with content "5k riverside park").
- `vault-config.yaml` has `calendar.granularities.daily` populated.

## Acceptance Gate (from Requirements Feature 6)

- [ ] Given `vault-config.yaml` has `calendar.granularities.daily`, When
  Phase A builds shared-ctx, Then it includes `daily_notes.tracker_fields[]`
- [ ] Given daily not configured, When Phase A builds shared-ctx, Then
  `daily_notes` section is omitted and subagents emit no `update_daily`
- [ ] Given a subagent detects a date reference AND a tracker keyword, Then
  it appends an `update_daily` action

## Tasks

### 4.1 Tracker-Fields in Shared-Ctx

Extend `shared-ctx-builder.py`:
- Read `vault-config.yaml` `trackers:` section (produced by
  `/explore-vault` Step 7)
- Populate `shared_ctx.daily_notes.tracker_fields[]` with: name, type,
  section, syntax, content-matching keywords
- Budget: tracker_fields[] adds roughly 1-2 KB; re-check the 15 KB cap and
  shorten `mocs[].topics` first if over

### 4.2 Subagent Daily-Detection Logic

Extend `inbox-analyst`:
- Add Step 9b — Detect daily relevance:
  1. Extract date from filename/frontmatter/content (formats from
     `shared-ctx.daily_notes.date_formats`)
  2. If no date → no `update_daily` action
  3. For each tracker_field, compute keyword-match score on content
  4. For fields with score ≥ threshold (e.g. 0.6), add an entry to
     `updates[]` with inferred value (bool tracker → `true` if any keyword
     hit; rating/text tracker → best-matching phrase)
  5. If `updates[]` non-empty, append `{kind: "update_daily", date,
     daily_note_path, updates}` to `actions[]`
- Daily-note path is computed from `shared-ctx.daily_notes.path_pattern`
  substituted with the extracted date

### 4.3 Reducer Rendering for `update_daily`

Extend `suggestions-reducer.py` rendering:

```markdown
### SNN — <suggested title or "Tracker entry for YYYY-MM-DD">

**Source:** [[<stem>]]

...[existing create_atomic_note block if present]...

**Daily update:** [[Calendar/301 Daily/2026-04-15]]
- Add: `Sport:: true` (Habits section)
- Add to Highlights: "5k riverside park"

**Decision (daily update):**
- [x] Approve
- [ ] Skip
```

Each action keeps its own Decision checkboxes. Order: `create_atomic_note`
first, `update_daily` second within a section.

### 4.4 Pass-2 Compatibility Check

Pass-2 (`instruction-builder`) already has a Daily-Note-Update handler
(Step 6). Verify the parser `suggestion-parser.py` correctly extracts
per-action decisions when a section has multiple actions — extend if needed.

### 4.5 Integration Test

Extend `scripts/test-phase3.sh` (or add `test-phase4.sh`):
- Fixture item `20260415-0700_run.md` with "Morning run, 5k, felt energized"
- Expected `result.json`: two actions (create_atomic_note +
  update_daily for 2026-04-15)
- Fixture item `20260415-2200_sleep.md` with "Slept 7h"
- Expected: only update_daily (no atomic note — atomic_note_worthiness < 0.5)

## Tests

- [ ] `bash scripts/test-phase4.sh` exits 0
- [ ] Running `/inbox` on a fixture inbox with tracker-relevant items produces
  a Suggestions doc where each tracker item has a `**Daily update:**` block
  with per-action decision checkboxes
- [ ] Disabling `calendar.granularities.daily` in `vault-config.yaml` causes
  next `/inbox` run to emit zero `update_daily` actions (regression guard)

## Hand-off to Phase 5

Phase 5 runs integration on the user's real inbox (including real tracker
items) and retires `suggestion-builder`.
