---
name: suggest-handling
description: Pass 1 suggest sub-flow — classifies fresh inbox sources into a suggestions doc. Load when routing-plan.action is suggest.
user-invocable: false
---
# Suggest Handling
# version: 0.4.0

## When to Activate

Load this skill when:
- `routing-plan.action == "suggest"`

## Suggest Flow

### 1. Read routing plan

```bash
cat tomo-tmp/routing-plan.json
```

Extract `fresh_sources[]` and `inbox_path`.
If `drift_indicators` is non-empty, surface each warning but continue.

### 2. Common setup

# STRICT — run ALL commands below before dispatching ANY subagent.

```bash
rm -rf tomo-tmp/items tomo-tmp/inbox-state.jsonl
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
python3 scripts/read-config-field.py --field tomo.suggestions.parallel --default 5
```

Capture stdout as `BATCH_SIZE`.

```bash
python3 scripts/read-config-field.py --field profile --default miyo
```

Capture stdout as `PROFILE`.

### 3. Fan-out dispatch

# STRICT — BATCH dispatch. Send BATCH_SIZE Agent() calls in a SINGLE message.
# ONE Agent call per message = sequential execution = 5x slower.
# Claude Code runs all Agent calls in the same message concurrently.

Split `fresh_sources[]` into batches of `BATCH_SIZE` items.
For each batch, emit ALL Agent() calls in ONE response.
Wait for the batch to complete before the next.

# STRICT — use this EXACT prompt structure for every dispatch. Do NOT improvise.

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
      force_atomic    = false

    Follow the IO Contract in your agent definition strictly. Write
    tomo-tmp/items/<stem>.result.json and update the state-file.
    Return one confirmation line, no prose.
)
```

### 3b. Tag-handler groups (only when `handled[]` is non-empty)

Check `routing-plan.json` `handled[]`. If it is non-empty, follow the
**tag-handler-interpreter** skill NOW — before Reduce — to produce
`tomo-tmp/tag-handler-groups/`. The reducer picks these up automatically (its
`--tag-handler-groups-dir` default). This MUST run before step 4, or the groups
miss the rendered doc. If `handled[]` is absent or empty, skip this step.

### 4. Reduce

```bash
python3 scripts/suggestions-reducer.py --run-id <RUN_ID> --profile <PROFILE> --output tomo-tmp/suggestions-doc.json
```

### 5. Render

```bash
python3 scripts/suggestions-render.py --input tomo-tmp/suggestions-doc.json --output tomo-tmp/suggestions-rendered.md --json-output tomo-tmp/suggestions-wire.json
```

### 6. Write to vault + tag sources

1. Read `tomo-tmp/suggestions-rendered.md` via the `Read` tool.
2. Write via `mcp__kado__kado-write` with `operation: "note"` at
   `<inbox_path>/<YYYY-MM-DD_HHMM>_suggestions.md`.
3. Publish the structured sibling (a JSON file, not a markdown note — the note op
   would reject it), reusing the SAME `<YYYY-MM-DD_HHMM>` stem as the `.md`:

```bash
python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-wire.json --vault "<inbox_path>/<YYYY-MM-DD_HHMM>_suggestions.json"
```

# STRICT — mark-captured runs immediately after vault write succeeds. Do NOT skip or defer.

```bash
python3 scripts/mark-captured.py --state tomo-tmp/inbox-state.jsonl --run-id <RUN_ID>
```

If mark-captured fails, report the error but still proceed to the report.

### 7. Report

> "Pass 1 complete: {N} items analysed, suggestions written to
> [[<date>_suggestions]]. Review in Obsidian, check the **Approved** box,
> then re-run `/inbox`."
