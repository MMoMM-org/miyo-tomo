---
title: "Phase 1: Extend instruction-render.py"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Extend instruction-render.py

## Phase Context

**Dependencies**: None — this is the first phase.

**Key files**:
- `scripts/instruction-render.py` (main target)
- `scripts/suggestion-parser.py` (input format — read only)
- `tomo/schemas/item-result.schema.json` (action type reference)

---

## Tasks

The script currently renders note files and produces `manifest.json`. Extend it to
also produce `instructions.json` (all actions) and `instructions.md` (human view).

- [ ] **T1.1 Build complete action list from both sources** `[activity: backend]`

  1. Prime: Read current `instruction-render.py` — it only processes items with templates.
     Items without templates (MOC links, daily updates, deletes) are skipped with "instruction-only".
     Read `suggestion-parser.py` output format to understand `confirmed_items[]` and `daily_updates[]`.
  2. Implement: After rendering note files (existing logic), build a unified `actions[]` list:
     - **move_note**: from manifest entries (rendered files that need moving)
     - **link_to_moc**: from `confirmed_items[].parent_mocs[]` — each parent_moc becomes an action
     - **update_tracker**: from `daily_updates[].trackers[]` (accepted only)
     - **update_log_entry**: from `daily_updates[].log_entries[]` (accepted only)
     - **update_log_link**: from `daily_updates[].log_links[]` (accepted only)
     - **create_moc**: from confirmed proposed MOCs (items with `action: "create_moc"`)
     - **delete_source**: from daily-only items (items in daily_updates but not in confirmed_items)
     - **skip**: items explicitly skipped by user
     Each action has: `id` (I01, I02...), `action` type, and type-specific fields.
  3. Validate: Action list covers all items from both sources. Count matches expected.

- [ ] **T1.2 Define instructions.json schema** `[activity: data-architecture]`

  1. Prime: Read `item-result.schema.json` for existing action type definitions.
  2. Implement: Create `tomo/schemas/instructions.schema.json`:
     ```json
     {
       "type": "tomo-instructions",
       "source_suggestions": "<filename>",
       "generated": "<ISO>",
       "profile": "<name>",
       "actions": [
         {
           "id": "I01",
           "action": "move_note",
           "source_path": "100 Inbox/Asahikawa.md",
           "rendered_file": "2026-04-19_1200_asahikawa-....md",
           "title": "Asahikawa — ...",
           "destination": "Atlas/202 Notes/",
           "parent_mocs": ["Japan (MOC)"],
           "tags": ["topic/travel/japan"]
         },
         {
           "id": "I05",
           "action": "link_to_moc",
           "target_moc": "Japan (MOC)",
           "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
           "section_name": "blocks",
           "line_to_add": "- [[Asahikawa — ...]]"
         },
         {
           "id": "I10",
           "action": "update_tracker",
           "daily_note_path": "Calendar/301 Daily/2026-03-26.md",
           "date": "2026-03-26",
           "field": "Sport",
           "value": true,
           "syntax": "inline_field",
           "section": "Tracker"
         },
         {
           "id": "I12",
           "action": "update_log_entry",
           "daily_note_path": "Calendar/301 Daily/2026-03-26.md",
           "date": "2026-03-26",
           "section": "Daily Log",
           "position": "after_last_line",
           "content": "Viel Sport gemacht"
         },
         {
           "id": "I15",
           "action": "delete_source",
           "source_path": "100 Inbox/Sport.md",
           "reason": "Content fully captured in daily note"
         }
       ]
     }
     ```
  3. Validate: Schema covers all 7 action types. Every field Seigyo needs is present.

- [ ] **T1.3 Write instructions.json** `[activity: backend]`

  1. Prime: T1.1 action list + T1.2 schema.
  2. Implement: Write `instructions.json` to output-dir alongside manifest.json.
  3. Validate: JSON is valid, parseable, action count matches.

- [ ] **T1.4 Render instructions.md from JSON** `[activity: backend]`

  1. Prime: Read current instruction-builder.md Step 5 for the expected markdown format.
  2. Implement: Add `render_instructions_md(actions, metadata)` function that produces
     the same markdown the LLM currently assembles:
     - YAML frontmatter (type, source_suggestions, generated, profile, action_count)
     - Section order: New Files → MOC Links → Daily Updates → Source Deletions → Skips
     - Per action: `### I<NN> — <description>` + `- [ ] Applied` + structured fields
     - Wikilinks for all file references (no path prefix, no .md)
  3. Validate: Output matches the format the user is used to. Diff against a known-good
     instruction set to verify structure.

- [ ] **T1.5 Config loading via --fields batch** `[activity: backend]`

  1. Prime: `read-config-field.py` now supports `--fields` + `--format json`.
  2. Implement: `instruction-render.py` loads all needed config in one call:
     `concepts.inbox`, `concepts.calendar.granularities.daily.path`,
     `daily_log.heading`, `daily_log.heading_level`, `profile`.
     Uses these values for path resolution and markdown rendering.
  3. Validate: Config values match vault-config.yaml. No hardcoded paths.

- [ ] **T1.6 Phase Validation** `[activity: validate]`

  - `instructions.json` contains all action types
  - `instructions.md` renders correctly from JSON
  - Both files are in output-dir alongside manifest.json
  - Rendered MD matches expected format (compare structure with known-good output)
