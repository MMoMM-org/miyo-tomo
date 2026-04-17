---
name: tomo-daily-log-wizard
description: Interactive wizard for configuring the daily_log section in vault-config.yaml. Sets heading, heading level, time-extraction sources, fallback strategy, cutoff days, and auto-create flags. Invoked via /tomo-setup daily-log.
argument-hint: "no arguments needed"
---
# Tomo Daily Log Wizard
# version: 0.1.0

This wizard configures how Tomo finds and updates your daily log entries. It writes the
`daily_log:` section of `config/vault-config.yaml`. Re-running is safe — existing values
are shown as defaults.

## Workflow

### Step 1 — Load current state

Read `config/vault-config.yaml`. Check whether a `daily_log:` section exists.

If it exists, show current values:

```
Current daily_log config:
  heading              : "Daily Log"
  heading_level        : 2
  time_extraction      : [content, filename]
  time_fallback        : append_end_of_day
  cutoff_days          : 30
  auto_create_if_missing: false
```

If missing, note it and proceed through each question with defaults pre-selected.

### Step 2 — Heading

Ask via **AskUserQuestion**: "What heading does your daily log section use?"

- Options:
  - `Daily Log` (default) — use as-is
  - `Journal` — common alternative
  - `Log` — short form
  - `Custom` — user types it in a follow-up

If Custom: invite input — "Type your daily log heading:"

### Step 3 — Heading level

Ask via **AskUserQuestion**: "What heading level is it?"

- Options:
  - `## (level 2)` (Recommended — most common in daily notes)
  - `# (level 1)`
  - `### (level 3)`

### Step 4 — Time extraction sources

Ask via **AskUserQuestion** (multiSelect: true): "Where should Tomo look for timestamps when
filing entries to your daily log?"

- Options (multiSelect):
  - `content` — parse timestamps from note body text (Recommended)
  - `filename` — infer date from the inbox note's filename

At least one must be selected. If the user selects none, re-ask.

### Step 5 — Time fallback

Ask via **AskUserQuestion**: "What should Tomo do when no timestamp is found in an inbox item?"

- Options:
  - `append_end_of_day` (Recommended) — add entry at end of today's daily log section
  - `append_start_of_day` — add entry at top of today's daily log section
  - `skip_time` — file to daily log without a specific time anchor

### Step 6 — Cutoff days

Ask via **AskUserQuestion**: "How many days back should Tomo update daily logs? (Items older
than this get no daily-note updates.)"

- Options:
  - `30 days` (Recommended)
  - `7 days`
  - `14 days`
  - `60 days`
  - `Custom` — user types a number in a follow-up

If Custom: "Enter the cutoff in days (a whole number):"

### Step 7 — Auto-create flags

**Note to Claude:** Do NOT ask the user to toggle these — they are locked to `false` in MVP.
Display them as informational only:

```
Auto-create flags (locked to false in MVP):
  auto_create_if_missing: false  — Tomo won't create daily notes yet.

When Tomo gains daily-note creation support (post-MVP), these will activate.
```

Ask via **AskUserQuestion**: "Pre-set auto_create_if_missing for when the feature ships?"

- Options:
  - `Pre-set to true` — stored as false now, but will enable automatically when supported
  - `Keep false` (Recommended) — explicit opt-in later

Store the user's intent as `auto_create_if_missing: false` regardless — this is an
informational choice only. Record the preference as a comment if the user chose
pre-set, so they remember their intent.

### Step 8 — Write config

Construct the `daily_log:` block from collected values:

```yaml
daily_log:
  heading: "<heading>"
  heading_level: <1|2|3>
  time_extraction:
    sources: [<content|filename>]
    fallback: <append_end_of_day|append_start_of_day|skip_time>
  cutoff_days: <N>
  auto_create_if_missing: false
```

If `daily_log:` already exists in vault-config, use the Edit tool to update it in place.
If it is missing, use the Edit tool to append the block after the last top-level key.

**IMPORTANT:** Never rewrite the entire file — use Edit for surgical updates only.

### Step 9 — Confirm

Show the final written config:

```
daily_log configuration saved:

  heading         : "Daily Log"
  heading_level   : 2
  time_extraction : [content, filename]  fallback: append_end_of_day
  cutoff_days     : 30
  auto_create     : false (locked until post-MVP)

Run /inbox to use the updated daily-log settings.
```

## Constraints

- Always use AskUserQuestion for all user choices — never plain-text prompts.
- Resolve paths via `scripts/read-config-field.py` — never hardcode vault paths.
- Edit tool only for config writes — preserve entire file structure.
- auto_create_if_missing is ALWAYS written as `false` regardless of user intent.
- Be idempotent — re-running is safe; existing values are pre-selected as defaults.
