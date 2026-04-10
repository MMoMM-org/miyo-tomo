# Tier 3: Tracker Field Handling

> Parent: [Daily Note Workflow](../../tier-2/workflows/daily-note.md)
> Status: Draft
> Related: [Daily Note Detection](daily-note-detection.md) · [Inbox Analysis](../inbox/inbox-analysis.md)

---

## 1. Purpose

Define how Tomo reads, proposes, and (via user) updates tracker fields in daily notes. Tracker fields are structured data points the user tracks over time — coding sessions, exercise, energy levels, etc.

## 2. Tracker Definition

Trackers are declared in vault-config.yaml (detected during `/explore-vault` or manually configured):

```yaml
trackers:
  - name: "coding-session"
    syntax: "inline_field"
    field: "Coding"
    type: "boolean"
    trigger_keywords: ["coded", "programming", "installed", "configured"]
  
  - name: "sport"
    syntax: "task_checkbox"
    label: "Sport"
    type: "boolean"
    trigger_keywords: ["sport", "gym", "run", "workout"]
  
  - name: "energie"
    syntax: "inline_field"
    field: "Energie"
    type: "scale"
    range: [1, 10]
    trigger_keywords: []
  
  - name: "gratitude"
    syntax: "frontmatter"
    field: "gratitude"
    type: "text"
    trigger_keywords: []
```

## 3. Supported Syntaxes

### 3.1 Inline Field (`inline_field`)

Dataview-style inline fields in the note body:

```markdown
Coding:: true
Energie:: 7
```

**Read:** Pattern match `^<field>::\s*(.+)$`
**Write:** Replace the value after `:: ` or append if field doesn't exist
**Location:** Anywhere in note body (typically in a Tracker section)

### 3.2 Task Checkbox (`task_checkbox`)

Standard markdown task list:

```markdown
- [ ] Sport
- [x] Meditation
```

**Read:** Pattern match `^- \[([ x])\]\s*<label>$`
**Write:** Toggle `[ ]` ↔ `[x]`
**Location:** Anywhere in note body (typically in a Tracker section)

### 3.3 Frontmatter (`frontmatter`)

YAML properties in the note's frontmatter:

```yaml
---
gratitude: "Had a great coffee"
sleep_hours: 7
---
```

**Read:** Parse YAML, get value by key
**Write:** Update YAML key-value via Kado frontmatter operation
**Location:** In the YAML frontmatter block

## 4. Value Types

| Type | Valid values | Default for new | Example |
|------|-------------|-----------------|---------|
| `boolean` | `true`, `false` (inline); `[x]`, `[ ]` (checkbox) | `false` / `[ ]` | `Coding:: true` |
| `scale` | Integer within `range` (e.g., 1-10) | empty | `Energie:: 7` |
| `count` | Integer ≥ 0 | `0` | `Coffees:: 3` |
| `text` | Free string | empty | `Gratitude:: Had a great coffee` |
| `choice` | One of configured labels | empty | `Mood:: 😊` |

## 5. Trigger Keywords

During inbox analysis, Tomo matches content against trigger keywords:

```
Inbox item: "Installed oh-my-zsh on the new Mac, took about an hour"
Trigger keywords for "coding-session": ["installed", "configured"]
Match: "installed" → propose Coding:: true
```

**Matching rules:**
- Case-insensitive
- Word boundary match (not substring — "install" doesn't match "reinstallation")
- First keyword match wins (no need to find all matches)
- Empty trigger_keywords = never auto-triggered (user must mention explicitly or set manually)

**Confidence:** Trigger matches are heuristic — the suggestions document shows the match reason:

```markdown
**Daily note update (2026-04-09):**
- Set tracker: `Coding:: true`
- Reason: keyword "installed" matched in source content
```

## 6. Reading Current Values

Before proposing a tracker update, Tomo reads the current value:

```
1. Determine daily note path (see daily-note-detection.md)
2. Read daily note via kado-read
3. For each tracker in config:
   - inline_field: regex search body for "^<field>::\s*(.+)$"
   - task_checkbox: regex search body for "^- \[([ x])\]\s*<label>$"
   - frontmatter: parse YAML, lookup key
4. Return current values
```

**Why read first?** To avoid proposing a redundant update (e.g., "set Coding:: true" when it's already true).

## 7. Update Proposals in Suggestions

Tracker updates appear in the suggestions document (Pass 1):

```markdown
### S05 — Daily note tracker: Coding → true (2026-04-09)
- [x] Approve
- Tracker: Coding (inline_field)
- Current value: (not set)
- Proposed value: true
- Reason: "installed" keyword in [[+/2026-04-09_1430_oh-my-zsh]]
```

For scale/count types, Tomo may suggest a value based on content:

```markdown
### S06 — Daily note tracker: Energie (2026-04-09)
- [ ] Approve (skipped by default — no auto-trigger for this tracker)
- Tracker: Energie (inline_field, scale 1-10)
- Current value: (not set)
- Proposed value: ___ (user fills in)
```

## 8. Instruction Set Actions

In Pass 2, tracker updates become concrete instructions:

```markdown
### I03 — Update daily note tracker
- [ ] Applied
- **Target:** [[Calendar/Days/2026-04-09]]
- **Tracker:** Coding (inline_field)
- **Change:** Set `Coding:: true`
- **Location:** Find `Coding::` line or add in Tracker section
```

For task checkboxes:

```markdown
### I04 — Update daily note tracker
- [ ] Applied
- **Target:** [[Calendar/Days/2026-04-09]]
- **Tracker:** Sport (task_checkbox)
- **Change:** Check `- [x] Sport`
- **Location:** Find `- [ ] Sport` line
```

## 9. Tracker Detection During /explore-vault

vault-explorer detects trackers from the daily note template:

```
1. Find the daily note template:
   vault-config templates.mapping.daily → read via Kado

2. Scan for tracker patterns:
   - Inline fields: lines matching ^<word>::\s*$  (empty value = tracker slot)
   - Task checkboxes: lines matching ^- \[ \]\s*<word>$
   - Frontmatter keys with empty/default values

3. For each detected tracker:
   - Infer type from default value:
     empty boolean → boolean
     empty number → count or scale (ask user)
     empty string → text
   - Suggest trigger_keywords (empty by default — user adds them)

4. Present findings to user for confirmation
5. Write to vault-config trackers section
```

**If no daily template exists:** skip tracker detection. User can configure manually.

## 10. Edge Cases

**Tracker field doesn't exist in daily note:** For inline_field and task_checkbox, the instruction says "add this line in the Tracker section (or at end of note)." For frontmatter, the instruction says "add this YAML key."

**Tracker value already matches proposed value:** Skip the action. Don't clutter the suggestions with no-ops.

**Multiple inbox items trigger the same tracker for the same day:** First wins. Second is redundant (value already proposed as true/set). Don't duplicate.

**Scale tracker without explicit value in content:** Don't propose a value. Include in suggestions as "manual fill" with the input field blank. User sets the value or skips.

**Tracker field syntax changed by user (was inline_field, now task_checkbox):** Tomo uses the config as source of truth. If the actual note uses a different syntax, the instruction may not work. `/explore-vault --confirm` re-detects and updates config.
