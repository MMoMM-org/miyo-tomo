---
name: tomo-trackers-wizard
description: Interactive wizard for configuring tracker fields — section, syntax, description, and trigger keywords in vault-config.yaml. Invoked via /tomo-setup trackers or directly as /tomo-trackers-wizard.
argument-hint: "no arguments needed"
---
# Tomo Trackers Wizard
# version: 0.2.0

This wizard walks you through configuring each tracker field with the metadata
Tomo needs for accurate inbox classification and correct daily-note updates:

- **section** — which Daily Note section the tracker lives in (e.g. "Habit")
- **syntax** — how the field is written (`inline_field`, `task_checkbox`, `frontmatter`)
- **description** — what the tracker actually measures
- **positive_keywords** — words that trigger this tracker from inbox content
- **negative_keywords** — words that suppress false positives

## Workflow

### Step 1 — Load current tracker config

Read `config/vault-config.yaml`. Extract all tracker groups and their fields:

- `trackers.daily_note_trackers.yesterday_fields[]`
- `trackers.daily_note_trackers.today_fields[]`
- `trackers.daily_note_trackers.start_of_day_fields[]`
- `trackers.end_of_day_fields.fields[]`

Also read the group-level `section` if present:
- `trackers.daily_note_trackers.section` (default: "Habit")
- `trackers.end_of_day_fields.section` (default: "End of the Day")

For each field note: `name`, `type`, existing `section`, `syntax`, `description`,
`positive_keywords[]`, `negative_keywords[]`. Any may be absent.

Report to the user:

```
Tracker fields found:

  daily_note_trackers (section: Habit):
    yesterday_fields:
      - Entspannung (boolean) — syntax: ?, description: ✓
      - Alcohol (boolean) — syntax: ?, description: ✓
    today_fields:
      - Sport (boolean) — syntax: ?, description: ✓
      - WakeUpEnergy (scale) — syntax: ?, description: ✓

  end_of_day_fields (section: End of the Day):
    - DayJournal (boolean) — syntax: ?, description: ?
```

Use ✓ for present, ? for missing.

### Step 2 — Configure group-level section

For each tracker group, ask via **AskUserQuestion**:

"Which Daily Note section contains the `<group>` trackers?"
- Options:
  - `Habit` (or current value if set)
  - `Enter custom section name`
  - `Keep current` (only if already set)

Set the `section` key on the group.

### Step 3 — Walk each field

For each tracker field:

1. Show current state:
   ```
   Field: Sport  (type: boolean, group: today_fields)
   Section     : Habit (from group)
   Syntax      : <not set>
   Description : "Did I exercise today?"
   Pos keywords: <none>
   Neg keywords: <none>
   ```

2. **Syntax** — Ask via **AskUserQuestion**: "How is `<field>` written in the daily note?"
   - Options:
     - `inline_field` — Dataview-style `Field:: value` (Recommended for most fields)
     - `task_checkbox` — `- [x] Field` checkbox
     - `frontmatter` — YAML property in frontmatter
     - `Keep current` — only if syntax is already set

3. **Description** — Ask via **AskUserQuestion**: "What does `<field>` track?"
   - Options:
     - `Keep current` — only if description exists; show current text
     - `Edit` — user provides free-text description
     - `Skip` — leave unchanged

   If Edit: say "Describe what `<field>` tracks (one sentence is enough):"
   and wait for user reply.

4. **Positive keywords** — Ask via **AskUserQuestion**: "Positive keywords for `<field>`?"
   - Options:
     - `Enter keywords` — user types comma-separated list
     - `Keep existing` — only if keywords exist; show current list
     - `None` — explicitly empty

5. **Negative keywords** — Ask via **AskUserQuestion**: "Negative keywords for `<field>`?"
   - Options:
     - `Enter keywords`
     - `Keep existing` — only if negative keywords exist
     - `None`

6. Show confirmation:
   ```
   Field `Sport`:
     syntax       : inline_field
     description  : "Physical exercise done today"
     positive kw  : ran, workout, gym, yoga, Sport gemacht
     negative kw  : watched, video about
   ```

   Ask via **AskUserQuestion**: "Accept?"
   - `Accept` (Recommended)
   - `Re-edit` — loop back
   - `Skip` — discard changes, move on

### Step 4 — Write back

**IMPORTANT:** Use the Edit tool — NOT a full file rewrite.

For each accepted field, update its entry in `config/vault-config.yaml`:
- Set `syntax:` (if changed or newly set)
- Set `description:` (if changed)
- Set `positive_keywords:` as YAML list (not nested under `keywords:`)
- Set `negative_keywords:` as YAML list (not nested under `keywords:`)

For each group, set the `section:` key if changed.

Preserve all other vault-config content exactly. Preserve field order.

**Schema reference** (per field in vault-config.yaml):
```yaml
- name: Sport
  type: boolean
  syntax: inline_field
  description: "Physical exercise done today"
  positive_keywords: [ran, workout, gym, yoga]
  negative_keywords: [watched, video about]
```

**Schema reference** (group level):
```yaml
trackers:
  daily_note_trackers:
    section: "Habit"
    today_fields:
      - name: Sport
        ...
  end_of_day_fields:
    section: "End of the Day"
    fields:
      - name: DayJournal
        ...
```

### Step 5 — Report

```
Tracker semantics configured for N of M fields.

  ✓ Sport          — inline_field, 5 positive kw, 2 negative kw
  ✓ WakeUpEnergy   — inline_field, 6 positive kw
  ✗ DayJournal     — skipped

Sections: Habit (daily_note_trackers), End of the Day (end_of_day_fields)

Run /inbox to see the improved classification.
```

## Constraints

- Always use AskUserQuestion for choices — never plain text prompts.
- Edit tool only for config writes — preserve the entire file structure.
- Be idempotent — re-running is safe; existing values are shown as defaults.
- Never invent keyword suggestions — only show what exists or what the user types.
- Keywords are flat lists (`positive_keywords: [...]`), NOT nested under `keywords:`.
- `section` lives at the group level, not per field.
