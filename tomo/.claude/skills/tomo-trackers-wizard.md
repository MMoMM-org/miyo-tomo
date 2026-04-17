---
name: tomo-trackers-wizard
description: Interactive wizard for configuring tracker field semantics (description, positive/negative keywords) in vault-config.yaml. Invoked via /tomo-setup trackers or directly as /tomo-trackers-wizard.
argument-hint: "no arguments needed"
---
# Tomo Trackers Wizard
# version: 0.1.0

This wizard walks you through giving each tracker field a human-readable description
and keyword lists. Tomo uses these to classify inbox items accurately — a well-described
field with good keywords cuts false positives significantly.

When you're done, run `/inbox` to see the improved classification.

## Workflow

### Step 1 — Load current tracker config

Read `config/vault-config.yaml` via `scripts/read-config-field.py`. Extract all tracker
fields from both sections:

- `trackers.daily_note_trackers.today_fields[]`
- `trackers.end_of_day_fields.fields[]`

Build a working list: for each entry, note its `name`, `type`, existing `description`
(may be absent or empty), existing `keywords.positive[]`, and existing `keywords.negative[]`.

Report to the user:

```
Tracker fields found:

  today_fields:
    - mood (text)
    - energy (scale)
    - focus_task (text)

  end_of_day_fields:
    - wins (text)
    - blockers (text)
```

If vault-config has no tracker sections, say so and offer to skip:

> "No tracker fields found in vault-config.yaml. Nothing to configure."

### Step 2 — Walk each field

For each tracker field (today_fields first, then end_of_day_fields):

1. Show the current state clearly:
   ```
   Field: mood  (type: text)
   Description : <empty>
   Positive kw : <none>
   Negative kw : <none>
   ```

2. Ask via **AskUserQuestion**: "What does `<field>` actually track?"
   - Options:
     - `Keep current` — only if `description` is already non-empty; pre-fill with the
       existing text so the user sees it
     - `Edit` — user provides a free-text description in a follow-up
     - `Skip this field` — leave unchanged

3. If Edit: invite a short free-text description. No AskUserQuestion here — just say:
   > "Describe what `<field>` tracks (one sentence is enough):"
   Then wait for the user's reply.

4. Ask via **AskUserQuestion**: "Positive keywords for `<field>`? (comma-separated or one per line)"
   - Options:
     - `Enter keywords` — user types them in a follow-up
     - `Keep existing` — only if keywords already exist; pre-fill
     - `None` — explicitly empty list

5. Ask via **AskUserQuestion**: "Negative keywords for `<field>`? (suppress false positives)"
   - Options:
     - `Enter keywords`
     - `Keep existing` — only if negative keywords exist
     - `None`

6. Show a confirmation summary:

   ```
   Field `mood`:
     description : "Daily mood score from 1–5"
     positive kw : mood, feeling, energy level, how I feel
     negative kw : productivity, tasks
   ```

   Ask via **AskUserQuestion**: "Accept this configuration?"
   - Options:
     - `Accept` (Recommended)
     - `Re-edit` — loop back to step 2 for this field
     - `Skip` — discard changes for this field, move on

After all fields are processed, show a summary of accepted vs skipped before writing.

### Step 3 — Write back

**IMPORTANT:** Use the Edit tool — NOT a full file rewrite.

For each accepted field, update only its entry in `config/vault-config.yaml`:
- Set `description:` to the new value
- Set `keywords.positive:` list
- Set `keywords.negative:` list

If a field had no `keywords:` block, add one. Preserve all other vault-config content
exactly. Preserve field order within each tracker section.

Do NOT touch any section of vault-config outside the modified tracker field entries.

### Step 4 — Report

```
Tracker semantics configured for N of M fields.

  ✓ mood         — description + 4 positive kw
  ✓ energy       — description + 2 positive kw, 1 negative kw
  ✗ focus_task   — skipped

Run /inbox to see the improved classification.
```

## Constraints

- Always use AskUserQuestion for choices — never plain text prompts.
- Resolve all paths via `scripts/read-config-field.py` — never hardcode vault paths.
- Edit tool only for config writes — preserve the entire file structure.
- Be idempotent — re-running is safe; existing values are shown as defaults.
- Never invent field names or keyword suggestions — always derive from vault-config or user input.
