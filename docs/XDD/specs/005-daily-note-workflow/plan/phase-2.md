# Phase 2 — shared-ctx-builder extension

## Goal

shared-ctx.json gains tracker descriptions + keyword lists + the new
`daily_log` block. Budget still ≤ 15 KB.

## Acceptance Gate

- [ ] `daily_notes.tracker_fields[].description` populated when
  vault-config has it; empty string + warning when not.
- [ ] `daily_notes.tracker_fields[].positive_keywords` and
  `negative_keywords` populated from vault-config.
- [ ] `daily_notes.daily_log` block present with all keys, from
  vault-config or Tomo-sane defaults.
- [ ] Output still ≤ 15 KB on the real-instance vault.
- [ ] `calendar.granularities.daily.enabled: false` → no `daily_notes`
  section at all (Spec-004 regression guard).

## Tasks

### 2.1 `build_tracker_fields()` extension

In `scripts/shared-ctx-builder.py`:

- Carry `description`, `positive_keywords`, `negative_keywords` from
  vault-config `trackers.daily_note_trackers.today_fields[]` and
  `trackers.end_of_day_fields.fields[]` into the flat `tracker_fields[]`
  output.
- When description is missing, emit empty string — shared-ctx-builder
  prints a stderr warning listing all fields missing descriptions.

### 2.2 `build_daily_log()` (new)

Read `vault-config.daily_log`:

- If missing: emit defaults
  (`{section: "Daily Log", heading_level: 1, time_extraction:
  {enabled: true, sources: [content, filename], fallback:
  "append_end_of_day"}, link_format: "bullet", cutoff_days: 30,
  auto_create_if_missing: {past: false, today: false, future: false}}`).
- If present: copy fields, force `auto_create_if_missing.{past,today,
  future}` to `false` regardless of vault-config value (MVP constraint
  — log a warning if user set any to `true`).

Attach result to `shared-ctx.daily_notes.daily_log`.

### 2.3 Size budget re-check

After adding tracker descriptions (~500 bytes per field × 22 fields ≈
11 KB addition) the budget will be tight. Implement:

- If total ≥ 15 KB after populating: shorten descriptions by trimming to
  200 characters with ellipsis. Still include keywords (they're short).
- If still over: drop `negative_keywords` first, then `positive_keywords`.
- Never drop `description` itself — that's the most-used field.

### 2.4 Tests

`scripts/test-005-phase2.sh`:

- Fixture vault-config with 3 trackers (some with full descriptions+keywords,
  some partial) → shared-ctx contains all 3 with correct passthrough.
- Fixture with empty `daily_log` section → defaults applied.
- Fixture with `daily_log.auto_create_if_missing.today: true` → forced to
  `false` in output; warning logged.
- Real-instance dry run: size ≤ 15 KB.
- `calendar.granularities.daily.enabled: false` → entire `daily_notes`
  section omitted (Spec-004 regression guard).

## Tests

- [ ] `bash scripts/test-005-phase2.sh` exits 0.
- [ ] `bash scripts/test-004-phase2.sh` still passes (Spec-004 shared-ctx tests).
- [ ] Real-instance dry run: shared-ctx ≤ 15 KB.

## Hand-off to Phase 3

Phase 3 subagent reads the extended shared-ctx to classify three-way.
