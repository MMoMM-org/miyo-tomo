---
name: force-atomic-handling
description: Force Atomic Note sub-flow for fan-resolve action. Load when routing-plan.action is fan-resolve or force_atomic_items is non-empty.
user-invocable: false
---
# Force Atomic Handling
# version: 0.2.0

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

For each item in `force_atomic_items[]`, dispatch inbox-analyst:

```
Agent(
  name: "inbox-analyst"
  prompt: |
    You are processing ONE inbox item under the fan-out pipeline.

    Inputs:
      stem            = "<stem>"
      path            = "<path>"
      shared_ctx_path = "tomo-tmp/shared-ctx.json"
      state_path      = "tomo-tmp/inbox-state.jsonl"
      items_dir       = "tomo-tmp/items"
      run_id          = "<RUN_ID>"
      force_atomic    = true

    Follow the IO Contract in your agent definition strictly. Write
    tomo-tmp/items/<stem>.result.json and update the state-file.
    Return one confirmation line, no prose.
)
```

### 4. Reduce

```bash
python3 scripts/suggestions-reducer.py --state tomo-tmp/inbox-state.jsonl --items-dir tomo-tmp/items --run-id <RUN_ID> --profile <PROFILE> --output tomo-tmp/suggestions-fan-doc.json --fan-resolve
```

### 5. Render

```bash
python3 scripts/suggestions-render.py --input tomo-tmp/suggestions-fan-doc.json --output tomo-tmp/suggestions-fan-rendered.md
```

### 6. Write to vault

1. Read `tomo-tmp/suggestions-fan-rendered.md` via the `Read` tool.
2. Write via `mcp__kado__kado-write` with `operation: "note"` at
   `<inbox_path>/<YYYY-MM-DD_HHMM>_suggestions-fan.md`.

### 7. Report

> "FAN resolve complete — {N} items expanded into suggestions-fan doc.
> Review in Obsidian, check the **Approved** box, then re-run `/inbox`."
