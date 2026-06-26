---
name: tag-handler-interpreter
description: Use PROACTIVELY when routing-plan.action is "suggest" AND routing-plan.handled[] is non-empty — handles tag-handler compose and group-result output for the suggestion conductor.
user-invocable: false
---
# Tag Handler Interpreter
# version: 0.2.3

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
python3 scripts/tag-handler-group.py
```

Read `tomo-tmp/tag-handler-group-stubs.json`. Each stub has: `handler`, `target_path`, `marker`, `placement`, `compose`, `source_paths`, and (when configured) `output_format`.

### 2. Read source notes for each group

For each stub in the stubs array:
- For each path in `source_paths`: read the note via `mcp__kado__kado-read` with `operation: "note"`.
- Collect the note's title, frontmatter fields, and body for use in compose (step 3).
- If the stub has `output_format`: ALSO read the TARGET note's marker section — `mcp__kado__kado-read` with `operation: "note"`, `mode: "section"`, `heading:` the marker's HEADING TEXT with its leading `#` run stripped (e.g. marker `"## Captures"` → `heading: "Captures"`; Kado matches heading text, NOT the `##`-prefixed form). Keep the returned section lines (verbatim, unmodified) as `section_lines` for step 3. If Kado returns NOT_FOUND, pass empty `section_lines` (the helper then signals `no_structure_under_marker`).

### 3. Compose one block per group

# STRICT — ONE composed_block per group: every group produces exactly one group-result with one composed_block. A structure-aware group emits its N rows/items INSIDE that single composed_block — N rows are NOT N blocks. Never emit one block per source item.

For each stub, pick the compose path by this PRECEDENCE — first match wins, do NOT fall through:

# STRICT — `output_format` ALWAYS wins. A structure-aware stub ALSO carries a `compose` string, but when `output_format` is present you MUST take path 1 (structure-aware). The `compose` string is NOT a directive here — it is only the wording for the prose fallback inside path 1. NEVER take path 2 or path 3 when the stub has an `output_format` key.

**Path 1 — stub has an `output_format` key → structure-aware compose (MANDATORY when present):**
- For each `synthesize` cell directive: produce a single-line value. Scope by `output_format.granularity`: `per_item` = one value per source capture; `merged` = one value over the whole group. For each `field` cell: read the named frontmatter field from EACH source note (the notes you read in step 2) — `per_item` uses that note's own value; `merged` uses the newest note's value. No synthesis.
- Build `cell_values_per_item` — a list of cell-value lists, one inner list per emitted row/item (for `merged`, exactly one inner list), each inner list ordered to match `output_format.cells`.
- Write `tomo-tmp/compose-payload-<i>.json` with keys: `section_lines` (the raw target section from step 2), `output_format` (from the stub), `cell_values_per_item`, `marker` (from the stub).
- Run:

```bash
python3 scripts/tag-handler-compose.py tomo-tmp/compose-payload-<i>.json
```

- Read the printed JSON:
  - `status: "ok"` → carry its `composed_block` and `resolved_anchor` into step 4 verbatim.
  - `status: "fallback"` → synthesize a plain dated prose status block (using the stub's `compose` string as the wording) for `composed_block`, and carry `fallback.reason` into step 4.

**Path 2 — stub has NO `output_format` and `compose` is a STRING (LLM directive):**
- Synthesize all of this group's source notes (title, frontmatter fields, body) into exactly ONE dated status-update markdown block, following the directive as the synthesis instruction.
- The result is one merged block, regardless of how many source items are in the group.

**Path 3 — stub has NO `output_format` and `compose` is an ARRAY (field-template):**
- Produce a deterministic mechanical join: one bullet line per source item listing the field values named in the array.
- No LLM synthesis.

### 4. Write group-result files

For each stub at index `<i>`:
- Write `tomo-tmp/tag-handler-groups/<i>.json` conforming to `schemas/tag-handler-group.schema.json`.
- Required fields:
  - `schema_version`: `"1"`
  - `handler`: from stub
  - `target_path`: from stub (may be null — do not drop null-target groups)
  - `marker`: from stub
  - `source_paths`: from stub
  - `composed_block`: the merged block from step 3
- Optional (include when the group stub supplies them / when known):
  - `placement`: from stub
  - `compose_mode`: `"llm_directive"` if compose was a string; `"field_template"` if compose was an array
  - `output_format`: from stub, when the stub had one
  - `resolved_anchor`: the `{type, value, placement}` from the compose output, verbatim, when its `status` was `"ok"`
  - `fallback`: `{ "reason": <reason> }`, ONLY when the compose output `status` was `"fallback"`

The reducer reads these files to render suggestion items.
