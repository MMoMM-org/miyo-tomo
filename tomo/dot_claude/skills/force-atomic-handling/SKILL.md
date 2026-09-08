---
name: force-atomic-handling
description: Force Atomic Note sub-flow for fan-resolve action. Load when routing-plan.action is fan-resolve or force_atomic_items is non-empty.
user-invocable: false
---
# Force Atomic Handling
# version: 0.7.0

## When to Activate

Load this skill when:
- `routing-plan.action == "fan-resolve"`
- `routing-plan.force_atomic_items` is non-empty

## Fan-Resolve Flow

### 1. Read routing plan

```bash
cat tomo-tmp/routing-plan.json
```

Extract `force_atomic_items[]`, `approved_suggestions[0].cache_path`,
and `inbox_path`.

### 2. Common setup

# STRICT — run ALL commands below before dispatching ANY subagent.

```bash
mkdir -p tomo-tmp/items
```

```bash
python3 scripts/run-id.py --out tomo-tmp/.run_id
```

Capture stdout as `RUN_ID`.

```bash
python3 scripts/shared-ctx-builder.py --cache config/discovery-cache.yaml --vault-config config/vault-config.yaml --profiles-dir profiles --run-id <RUN_ID> --output tomo-tmp/shared-ctx.json
```

If this fails, abort and surface the error.

```bash
python3 scripts/read-config-field.py --field profile --default miyo
```

Capture stdout as `PROFILE`.

### 3. Fan-out dispatch

# STRICT — use this EXACT prompt structure for every dispatch. Do NOT improvise.
# STRICT — path MUST be the item's own `item_key` from the routing plan, verbatim.
# NEVER build a path from `inbox_path` and `stem`.
# `source_path` in the routing plan is the suggestions doc — NEVER use it as path.
# Why: the analyst reads the note at `path` via Kado — `source_path` makes it classify the suggestions doc, and a path built from `inbox_path` + `stem` names a file that does not exist for a note in a subfolder.

For each item in `force_atomic_items[]`, dispatch inbox-analyst.

```
Agent(
  name: "inbox-analyst"
  prompt: |
    You are processing ONE inbox item under the fan-out pipeline.

    Inputs:
      stem            = "<stem>"
      path            = "<item_key>"
      shared_ctx_path = "tomo-tmp/shared-ctx.json"
      state_path      = "tomo-tmp/inbox-state.jsonl"
      items_dir       = "tomo-tmp/items"
      run_id          = "<RUN_ID>"
      item_key        = "<item_key>"
      force_atomic    = true

    Follow the IO Contract in your agent definition strictly. Write your
    result to <items_dir>/<result_filename> (Step 10 derives <result_filename>
    from item_key; never assemble it yourself) and update the state-file.
    Return one confirmation line, no prose.
)
```

### 4. Reduce

```bash
python3 scripts/suggestions-reducer.py --state tomo-tmp/inbox-state.jsonl --items-dir tomo-tmp/items --run-id <RUN_ID> --profile <PROFILE> --output tomo-tmp/suggestions-fan-doc.json --fan-resolve
```

### 5. Render

```bash
python3 scripts/suggestions-render.py --input tomo-tmp/suggestions-fan-doc.json --output tomo-tmp/suggestions-fan-rendered.md --json-output tomo-tmp/suggestions-fan-wire.json
```

### 6. Write to vault

Publish BOTH siblings at the same stem so the ADR-026 editor + Pass-2 pair them:

1. Read `tomo-tmp/suggestions-fan-rendered.md` via the `Read` tool.
2. Write via `mcp__kado__kado-write` with `operation: "note"` at
   `<inbox_path>/<YYYY-MM-DD_HHMM>_suggestions-fan.md`.
3. Publish the wire sibling (JSON needs the file op, not note):

```bash
python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-fan-wire.json --vault "<inbox_path>/<YYYY-MM-DD_HHMM>_suggestions-fan.json"
```

### 7. Record the run cost

# STRICT — run this before the report. Do NOT skip it.
# Why: this is the ONLY step that records what a `fan-resolve` run cost — triage
# deliberately writes no entry for this action, and a skipped step loses the
# run's cost silently.

```bash
python3 scripts/record-run-cost.py --run-id <RUN_ID> --suggestions-doc tomo-tmp/suggestions-fan-doc.json
```

### 8. Report

> "FAN resolve complete — {N} items expanded into suggestions-fan doc.
> Review + resolve in Hashi (or Obsidian), check the **Approved** box, then re-run `/inbox`."
