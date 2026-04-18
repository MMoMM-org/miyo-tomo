# Tier 3: Daily Note Detection

> Parent: [Daily Note Workflow](../../tier-2/workflows/daily-note.md)
> Status: Draft
> Related: [Tracker Field Handling](tracker-field-handling.md)

---

## 1. Purpose

Define how Tomo detects whether a daily note exists for a target date and what to propose when it doesn't. Daily notes are the user's territory — Tomo augments, never replaces.

## 2. Detection Logic

When an inbox item has a daily-note-relevant action (tracker update, content addition):

```
1. Determine target date from inbox analysis
   → filename date, content date, or fallback to file creation date

2. Compute expected daily note path:
   base_path = vault-config concepts.calendar.granularities.daily.path
   pattern   = vault-config naming.calendar_patterns.daily
   expected  = base_path + format(target_date, pattern) + ".md"
   
   Example: "Calendar/Days/" + "2026-04-09" + ".md"
           → "Calendar/Days/2026-04-09.md"

3. Check existence via kado-read (or kado-search byName):
   → exists → include daily note actions in suggestions
   → does not exist → check config for creation policy
```

## 3. Missing Daily Note Policy

```yaml
# In vault-config.yaml (future, detected during /explore-vault)
calendar:
  daily_creation_policy: "skip" | "suggest" | "create"
```

| Policy | Behavior |
|--------|----------|
| `skip` | Don't propose any daily note actions for missing dates. Log warning. |
| `suggest` | Include in suggestions: "Daily note for 2026-04-09 doesn't exist. Create it?" User approves. |
| `create` | Tomo creates the daily note from template in the inbox folder. User moves it. |

**Default:** `suggest` — Tomo always asks.

**Why not auto-create?** The user likely has a Templater-based daily note flow (with prompts, JS, sub-templates). A Tomo-created daily note would be a simplified version. Better to suggest and let the user decide whether to create via their normal flow or accept Tomo's simplified version.

## 4. Actions on Existing Daily Notes

When the daily note exists, Tomo can propose:

| Action | What changes | How detected |
|--------|-------------|-------------|
| **Tracker update** | Set a tracker field value | Inbox item content matched tracker trigger_keywords |
| **Content addition** | Append text to a section | Inbox item is daily-note-worthy (coding session log, brief mention) |
| **Link addition** | Add wikilink to a section | New note created from same-date inbox item |

All actions appear in the suggestions document (Pass 1) and instruction set (Pass 2) with the daily note as the target.

## 5. Multi-Day Coverage

If the inbox hasn't been processed for multiple days:

```
Items from 2026-04-07:
  → Daily note 2026-04-07.md exists? → add actions
  → Daily note 2026-04-07.md missing? → apply creation policy

Items from 2026-04-08:
  → Same check

Items from 2026-04-09:
  → Same check
```

Each date's actions are grouped in the suggestions document:

```markdown
## Day: 2026-04-07

### S03 — Daily note update: set Coding tracker
...

### S04 — Daily note update: add brief mention of oh-my-zsh setup
...

## Day: 2026-04-08

### S07 — Daily note for 2026-04-08 doesn't exist
- [x] Create from template (in inbox folder, user moves)
- [ ] Skip daily note actions for this date
```

## 6. Content Placement in Daily Notes

When adding content to an existing daily note, Tomo needs to know WHERE:

### Section Targeting

```yaml
# In vault-config.yaml (future)
calendar:
  daily_content_section: "## Notes"    # default section for content additions
  daily_link_section: "## Notes"       # default section for link additions
```

If the configured section exists in the daily note → append there.
If the section doesn't exist → create it at end (before any footer-like content).

### Tracker Targeting

Trackers are found by their field marker (e.g., `Coding::`) anywhere in the daily note body. No section targeting needed — the marker IS the location.

## 7. Daily Note Title

The title of a daily note follows the configured filename pattern:

```
pattern: "YYYY-MM-DD"
date: 2026-04-09
title: "2026-04-09"
```

Some users use more descriptive titles (e.g., "2026-04-09 Wednesday"). The template's `{{title}}` token resolves to the formatted date. User can customize in their template.

## 8. Edge Cases

**User creates daily note between Pass 1 and Pass 2:** Tomo re-checks existence during instruction set generation (Pass 2). If the note now exists, the "create daily note" action becomes a no-op — the instruction set only includes tracker/content actions.

**Daily note exists but has different filename than expected:** If `Calendar/Days/2026-04-09.md` doesn't exist but `Calendar/Days/Wednesday 2026-04-09.md` does, Tomo won't find it. Mitigation: `kado-search byName` with the date pattern as a fallback search.

**Daily note has frontmatter but no content sections:** Tracker fields still work (they're inline fields in the body). Content additions create the first section.

**Multiple daily notes for the same date:** Should not happen. If detected, Tomo uses the first match and warns.
