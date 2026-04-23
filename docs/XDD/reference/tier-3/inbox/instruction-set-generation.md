# Tier 3: Instruction Set Generation (Pass 2)

> Parent: [Inbox Processing](../../tier-2/workflows/inbox-processing.md)
> Status: Implemented
> Agent: `instruction-builder`
> Related: [Suggestions Document](suggestions-document.md) · [Instruction Set Apply](instruction-set-apply.md)

---

## 1. Purpose

Define how the `instruction-builder` agent converts a **confirmed suggestions document** into a **detailed instruction set** the user can apply. This is Pass 2 of the inbox processing workflow.

## 2. Inputs

| Input | Source |
|-------|--------|
| Confirmed suggestions document | `#MiYo-Tomo/confirmed` file in inbox folder |
| Source inbox items | Referenced by the suggestions document |
| Template files | Read via Kado from `templates.base_path` + mapping |
| vault-config | Frontmatter schema, relationship markers, tag taxonomy |
| Framework profile | Classification data, relationship defaults |
| Discovery cache | Section lookups in target MOCs |

## 3. Trigger

Runs when `/inbox` detects a `#MiYo-Tomo/confirmed` suggestions document. The run-to-run state machine prioritizes this over fresh `captured` items — confirmed work finishes before new work starts.

## 4. Process

```
1. Read confirmed suggestions document via kado-read
   → Parse each S## section
   → Extract checkbox state per suggestion and per sub-action
   → Extract user modifications to field values
   → Build confirmed-action list

2. For each confirmed action, dispatch to the right handler:
   → new_atomic_note → render template, write to inbox
   → new_map_note → render template, write to inbox
   → moc_link → compute exact insertion location, generate instruction
   → daily_note_update → generate tracker or content update
   → note_modification → read target, compute diff, write diff file

3. Render each action's output
   (See §5 Action Handlers)

4. Assemble instruction set document
   → Group by target date if daily note actions present
   → Group by target note for modifications
   → Generate summary stats

5. Write instruction set to inbox folder — two siblings, same timestamp:
   → `YYYY-MM-DD_HHMM_instructions.md` — human-review artifact, tagged
     `#MiYo-Tomo/instructions`
   → `YYYY-MM-DD_HHMM_instructions.json` — machine-readable sibling
     consumed by Tomo Hashi's executor (see §11)

6. Write auxiliary files for new notes and diffs
   → Each gets its own file in the inbox folder
   → Instruction set links to them
```

## 5. Action Handlers

### 5.1 New Atomic Note

> The token list below is illustrative — the actual tokens used depend on the user's template and custom token configuration. See [Token Vocabulary](../templates/token-vocabulary.md) for the full mechanism.

1. Look up template via `templates.mapping.atomic_note`
2. Read template file via Kado
3. Resolve `{{tokens}}` — the template determines which tokens are needed. Common ones:
   - `{{uuid}}`: generated
   - `{{datestamp}}`, `{{updated}}`: current timestamp
   - `{{title}}`: from confirmed suggestion
   - `{{tags}}`: from suggestion + tag taxonomy rules
   - `{{up}}`: MOC link from confirmed suggestion
   - `{{summary}}`: short generated description
   - `{{body}}`: content from source inbox item, cleaned up
   - Plus any user-defined custom tokens per vault-config
4. Validate frontmatter (required fields all set)
5. Write the rendered note to inbox folder as `<date>_<slug>.md`
6. Instruction set entry references this file

### 5.2 New Map Note (New MOC)

Same as atomic note but:
- Template: `templates.mapping.map_note`
- Additional content: initial wikilinks to the notes that triggered the MOC proposal
- Parent MOC link from the cluster's suggested parent
- Classification from the cluster's category

### 5.3 MOC Link

For adding a link to an existing MOC:

1. Read the target MOC via Kado
2. Parse H2 sections
3. Locate the target section (exact match or closest match)
4. Determine the exact insertion point:
   - **Section exists:** append at end of section (before next H2)
   - **Section missing:** note that section must be created
5. Build a direct wikilink: `[[MOC Title#Section Name]]`
6. Generate the exact line to add: `- [[New Note Title]]`
7. Instruction set entry shows:
   - Target: clickable `[[MOC Title#Section]]`
   - Line to add
   - Fallback if section missing: "create section `## Section Name`"

### 5.4 Daily Note Update

For each daily note action:

1. Look up daily note path: `concepts.calendar.granularities.daily.path` + filename pattern (`naming.calendar_patterns.daily`) + target date
2. Check if daily note exists via `kado-read` (best-effort; continue if missing)
3. For each sub-action:
   - **Tracker update:** look up tracker config, generate exact syntax
     - `inline_field`: `Coding:: true`
     - `task_checkbox`: `- [x] Coding`
     - `frontmatter`: set YAML key `coding: true`
   - **Content addition:** target section + markdown snippet to append
4. Instruction set entry shows:
   - Target: clickable `[[2026-04-08#Section]]` or frontmatter update
   - Exact text change
   - Create note first if missing (configurable)

### 5.5 Note Modification

For changes to existing notes:

1. Read current note via Kado
2. Apply the change in memory (add tag, update field, modify section)
3. Compute diff (before/after)
4. Write diff document to inbox folder as `<date>_<slug>-diff.md`:
   ```markdown
   # Diff: oh-my-zsh — Installation & Configuration

   **Target:** [[Atlas/202 Notes/oh-my-zsh — Installation & Configuration]]
   **Change:** Add tag `#topic/applied/tools`

   ## Before
   ```yaml
   tags:
     - type/note/normal
   ```

   ## After
   ```yaml
   tags:
     - type/note/normal
     - topic/applied/tools
   ```
   ```
5. Instruction set entry references the diff file

## 6. Instruction Set Format

### Header

```yaml
---
type: tomo-instructions
generated: 2026-04-08T14:35:00Z
tomo_version: "0.1.0"
source_suggestions: "2026-04-08_1430_suggestions.md"
profile: miyo
action_count: 7
tags:
  - MiYo-Tomo/instructions
---
```

### Body

```markdown
# Tomo Instructions — 2026-04-08 14:35

Generated from: [[2026-04-08_1430_suggestions]]

## Summary
- 3 new atomic notes ready in inbox folder
- 1 new MOC ready in inbox folder
- 3 MOC link additions
- 2 daily note tracker updates
- 1 note modification (diff)

## How to apply

For each action, perform the described change in Obsidian, then tick it off below.
When all actions are applied (or consciously skipped), change this document's tag
from `#MiYo-Tomo/instructions` to `#MiYo-Tomo/applied` and run `/inbox` for cleanup.

---

## Day: 2026-04-08

### I01 — Create new note: oh-my-zsh — Installation & Configuration
- [ ] Applied
- **Rendered file:** [[+/2026-04-08_1430_oh-my-zsh-installation-configuration]]
- **Move to:** `Atlas/202 Notes/`
- **Final filename:** `oh-my-zsh — Installation & Configuration.md`
- **Note:** template contains no Templater syntax, move and you're done

### I02 — Add link to MOC
- [ ] Applied
- **Target:** [[Shell & Terminal (MOC)#Tools]]
- **Add this line at end of section:**
  ```
  - [[oh-my-zsh — Installation & Configuration]]
  ```
- **Fallback:** if `## Tools` section is missing, create it at end of MOC

### I03 — Update daily note tracker
- [ ] Applied
- **Target:** [[Calendar/Days/2026-04-08]]
- **Tracker:** `Coding:: true` (inline field)
- **Reason:** `installed` keyword in source item

### I04 — Create new MOC: Shell & Terminal (MOC)
- [ ] Applied
- **Rendered file:** [[+/2026-04-08_1430_shell-terminal-moc]]
- **Move to:** `Atlas/200 Maps/`
- **Final filename:** `Shell & Terminal (MOC).md`
- **Note:** template contains `<% tp.file.title %>` — after moving, run
  Obsidian command "Templater: Replace Templates in Active File"
- **After moving:** also add to parent MOC [[2600 - Applied Sciences#Sub-MOCs]]

---

## Note modifications

### I05 — Modify: existing note with new tag
- [ ] Applied
- **Target:** [[Atlas/202 Notes/shell-config-notes]]
- **Diff:** [[+/2026-04-08_1430_shell-config-notes-diff]]
- Click the diff file to see before/after, then apply the change manually
```

## 7. Instruction ID Numbering

Each action gets a stable ID (`I01`, `I02`, `I03`, ...). Used by:
- User to reference actions in discussions
- Tomo cleanup step to track which inbox items map to which actions

## 8. Ordering

Actions are ordered for **efficient application**:
1. **New files first** (atomic notes, new MOCs) — so subsequent link actions can target them
2. **MOC links next** — they reference the new notes from step 1
3. **Daily note updates** grouped by date
4. **Modifications** last — riskier, user pays full attention

## 9. Linked Files (Written in Inbox Folder)

Each new note and each diff gets its own file written to the inbox folder during generation:

- `<date>_<slug>.md` — rendered new note (atomic note or MOC)
- `<date>_<slug>-diff.md` — before/after diff document

These files are referenced from the instruction set via wikilinks. They live in the inbox folder until:
- The user applies the action (moves them or applies the diff)
- Cleanup archives them once the instruction set is marked `#MiYo-Tomo/applied`

## 10. Error Handling

- **Confirmed suggestion references missing template:** log error, skip that action, include in instruction set as "ERROR: template X not found, fix vault-config and re-run"
- **Target MOC doesn't exist (was deleted since suggestions generated):** flag for user, skip the link action, suggest re-running from captured
- **Token resolution failure for a required token:** render the note anyway with placeholder `<<MISSING: token_name>>`, include warning in instruction set
- **Diff generation fails (target note changed since suggestions generated):** abort that specific action, user re-runs from captured

## 11. Machine-Readable Sibling (`instructions.json`)

The `.json` sibling is the canonical, machine-readable instruction set consumed
by **Tomo Hashi** (see Kokoro ADR-009). The `.md` remains the source of truth
for human review and approval; the `.json` is decoupled so `.md` wording can
evolve without breaking Hashi's parser.

### Stability contract

- **No LLM prompts, no natural-language instructions.** Those live in the
  `.md`. The JSON carries structured action data only.
- **No conditional logic.** All branches are resolved at generation time and
  emitted as concrete actions.
- **No Kado API references.** Hashi does not call Kado. Any operation
  expressible only as a Kado call is a generation-time failure in Tomo, not a
  runtime error in Hashi.
- **Count parity with `.md` is an invariant.** If the two files disagree on
  action count, that's a Tomo generation bug. Hashi may warn but will not
  reconcile.

### Top-level document shape

```json
{
  "schema_version": "1",
  "type": "tomo-instructions",
  "source_suggestions": "YYYY-MM-DD_HHMM_suggestions",
  "generated": "2026-04-23T14:35:00Z",
  "profile": "miyo",
  "tomo_version": "0.x.y",
  "action_count": 7,
  "actions": [ /* ordered list — see §11.2 */ ]
}
```

- `schema_version` — lets Hashi refuse sets it doesn't understand.
- `source_suggestions` — stem of the confirmed suggestions file (same folder,
  same timestamp as the `.md` peer).
- `generated` — ISO-8601 UTC, seconds precision, `Z` suffix.

### 11.1 Action envelope

Every action in the `actions[]` array has:

- `id` — `I01`, `I02`, … (stable, matches the `.md` heading).
- `action` — discriminator, one of: `create_moc`, `move_note`, `link_to_moc`,
  `update_tracker`, `update_log_entry`, `update_log_link`, `delete_source`,
  `skip`.
- Action-specific fully-resolved fields (see 11.2).

Actions are emitted in the execution order defined in §8.

### 11.2 Action types

#### `create_moc`

New Map-of-Content note. Rendered into the inbox folder; user (or Hashi) moves
it to its final destination and then processes the link_to_moc entries that
reference it.

| Field | Meaning |
|---|---|
| `title` | Final note title (no `.md`, no wikilink brackets). |
| `rendered_file` | Filename inside the inbox folder, e.g. `<date>_<slug>.md`. |
| `source` | Full inbox path to the rendered file. |
| `destination` | Final vault path (folder, trailing slash). |
| `parent_moc` | Parent MOC title, or `null`. |
| `supporting_items` | Optional count of child items; each gets its own `link_to_moc` action below. |
| `tags` | List of tags from the suggestion (includes `MiYo-Tomo/state/...` where applicable). |
| `template` | Template reference used to render the note (informational; Hashi does not re-render). |

#### `move_note`

Move a rendered atomic note from the inbox folder to its destination folder.

| Field | Meaning |
|---|---|
| `title` | Final note title. |
| `rendered_file` | Filename inside the inbox folder. |
| `source` | Full inbox path to the rendered file. |
| `destination` | Final vault path (folder, trailing slash). |
| `origin_inbox_item` | Path to the original inbox source item (for audit trail). |
| `parent_mocs` | List of parent-MOC titles the note links up to (can be empty). |
| `tags` | List of tags from the suggestion. |

#### `link_to_moc`

Add a wikilink to an existing MOC (may be one created earlier in the set — the
`create_moc` ordering guarantees it exists in the instruction order).

| Field | Meaning |
|---|---|
| `target_moc` | MOC title (display form). |
| `target_moc_path` | Resolved vault path to the MOC (populated via Kado; `null` only if target MOC is created in-set and couldn't be pre-resolved). |
| `section_name` | First line of the target callout/section, or `null` when the MOC doesn't yet exist in the vault (Hashi must look up the rendered create_moc's own callout at execute time). |
| `source_note_title` | Title of the note being linked. |
| `line_to_add` | The exact literal line to insert (e.g. `- [[Note Title]]`). |

#### `update_tracker`

Set a dataview inline field in a daily note (e.g. `Coding:: true`).

| Field | Meaning |
|---|---|
| `date` | ISO date of the daily note (`YYYY-MM-DD`). |
| `daily_note_path` | Resolved vault path to the daily note. |
| `field` | Tracker field name (e.g. `Coding`). |
| `value` | Field value (already rendered to its inline-field string form). |
| `syntax` | Literal syntax form to insert (`inline_field` · `task_checkbox` · `frontmatter`). |
| `section` | Section heading under which the tracker lives. |
| `source_stem` | Stem of the source inbox item that triggered the update. |
| `reason` | Short explanation surfaced in the `.md` (e.g. a matched keyword). |

#### `update_log_entry`

Add a content entry to a daily note's log section.

| Field | Meaning |
|---|---|
| `date` | ISO date. |
| `daily_note_path` | Resolved vault path. |
| `section` | Section heading text (e.g. `Daily Log`). |
| `heading_level` | Integer 1–6. |
| `position` | `after_last_line` · `before_first_line` · `at_time`. |
| `time` | `HH:MM` (required when `position=at_time`). |
| `content` | Literal body line to add. |
| `source_stem` | Stem of the source inbox item that triggered the entry. |
| `reason` | Short explanation for the human-facing `.md`. |

#### `update_log_link`

Add a `- [[Target]]` line to a daily note's log section. Same fields as
`update_log_entry` except `content` is replaced by `target_stem` (the wikilink
target stem without brackets). `source_stem` and `reason` behave the same.

#### `delete_source`

Delete an inbox source item after its content has been fully captured elsewhere.

| Field | Meaning |
|---|---|
| `source_path` | Full vault path to the inbox item. |
| `reason` | Short explanation for the human-facing `.md`. |

#### `skip`

Explicit no-op — carries the reason for an intentional skip so the `.md`
surfaces it to the user.

| Field | Meaning |
|---|---|
| `source_path` | Optional vault path to the inbox item being skipped. |
| `reason` | Skip reason. |

### 11.3 Evolution policy

- Additive changes (new optional fields on existing action types, new action
  types) bump no version.
- Breaking changes (removed fields, changed semantics of an existing field,
  renamed action discriminator) bump `schema_version` and are coordinated with
  Kokoro + Hashi via an outbox handoff before shipping.
