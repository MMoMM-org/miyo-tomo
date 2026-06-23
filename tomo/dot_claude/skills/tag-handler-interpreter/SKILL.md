---
name: tag-handler-interpreter
description: Use PROACTIVELY when routing-plan.action is "suggest" AND routing-plan.handled[] is non-empty — handles tag-handler compose and group-result output for the suggestion conductor.
user-invocable: false
---
# Tag Handler Interpreter
# version: 0.1.0

## When to Activate

Load this skill when:
- `routing-plan.action == "suggest"` AND `routing-plan.handled[]` is non-empty.

If `handled` is absent or an empty array, do NOT load this skill.

## Workflow

### 1. Group handled items

```bash
mkdir -p tomo-tmp/tag-handler-groups
```

```bash
python3 tomo/scripts/tag-handler-group.py --routing-plan tomo-tmp/routing-plan.json --output tomo-tmp/tag-handler-group-stubs.json
```

Read `tomo-tmp/tag-handler-group-stubs.json`. Each stub has: `handler`, `target_path`, `marker`, `placement`, `compose`, `source_paths`.

### 2. Read source notes for each group

For each stub in the stubs array:
- For each path in `source_paths`: read the note via `mcp__kado__kado-read` with `operation: "note"`.
- Collect the note's title, frontmatter fields, and body for use in compose (step 3).

### 3. Compose one block per group

# STRICT — ONE block per group (FR-8/AC-3): never emit one block per source item; the whole group merges into a single dated status update.

For each stub:

**If `compose` is a STRING (LLM directive):**
- Synthesize all of this group's source notes (title, frontmatter fields, body) into exactly ONE dated status-update markdown block, following the directive as the synthesis instruction.
- The result is one merged block, regardless of how many source items are in the group.

**If `compose` is an ARRAY (field-template):**
- Produce a deterministic mechanical join: one bullet line per source item listing the field values named in the array.
- No LLM synthesis.

### 4. Write group-result files

For each stub at index `<i>`:
- Write `tomo-tmp/tag-handler-groups/<i>.json` conforming to `tomo/schemas/tag-handler-group.schema.json`.
- Required fields:
  - `schema_version`: `"1"`
  - `handler`: from stub
  - `target_path`: from stub (may be null — do not drop null-target groups)
  - `marker`: from stub
  - `placement`: from stub
  - `source_paths`: from stub
  - `composed_block`: the merged block from step 3
  - `compose_mode`: `"llm_directive"` if compose was a string; `"field_template"` if compose was an array

The reducer reads these files to render suggestion items.
