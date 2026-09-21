---
name: suggest-handling
description: Pass 1 suggest sub-flow — classifies fresh inbox sources into a suggestions doc. Load when routing-plan.action is suggest.
user-invocable: false
---
# Suggest Handling
# version: 0.11.0

## When to Activate

Load this skill when:
- `routing-plan.action == "suggest"`

## Suggest Flow

### 1. Read routing plan

```bash
cat tomo-tmp/routing-plan.json
```

If `drift_indicators` is non-empty, surface each warning but continue.

# STRICT — read every value the later steps need with `read-routing-plan.py`.
# NEVER derive them from the `cat` output, and NEVER run `python3 -c`.
# Why: inline Python is refused by the Bash validator on its `#` characters,
# and a list retyped from a document drops or invents entries.

```bash
python3 scripts/read-routing-plan.py --field inbox_path
```

Capture stdout as `INBOX_PATH` (no trailing slash).

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

# STRICT — repeat every `WARN:` line this script prints to the user, verbatim,
# before dispatching anything.
# Why: it is the only report of unusable tracker configuration, and a run that
# swallows it looks identical to a healthy one.

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

Get the batch count once:

```bash
python3 scripts/read-routing-plan.py --batch-count --size <BATCH_SIZE>
```

Capture stdout as `BATCH_COUNT`. Then for each `<N>` from 1 to `BATCH_COUNT`:

```bash
python3 scripts/read-routing-plan.py --sources --batch <N> --size <BATCH_SIZE>
```

Each line is one item's `path`. Emit ALL Agent() calls for that batch in ONE
response, then wait for the batch to complete before requesting the next.

# STRICT — use this EXACT prompt structure for every dispatch. Do NOT improvise.
# STRICT — the key is `subagent_type`. `name` only labels the spawned agent.
# Why: a dispatch without `subagent_type` silently runs general-purpose, which
# has none of inbox-analyst's contract, tools or skills.

```
Agent(
  subagent_type: "inbox-analyst"
  prompt: |
    You are processing ONE inbox item under the fan-out pipeline.

    Inputs:
      stem            = "<stem>"
      path            = "<path>"
      shared_ctx_path = "tomo-tmp/shared-ctx.json"
      state_path      = "tomo-tmp/inbox-state.jsonl"
      items_dir       = "tomo-tmp/items"
      run_id          = "<RUN_ID>"
      item_key        = "<path>"
      force_atomic    = false

    Follow your "IO Contract" section strictly.

    Write your result to <items_dir>/<result_filename> (Step 10 derives
    <result_filename> from item_key; never assemble it yourself) and update
    the state-file. Return one confirmation line, no prose.
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

Publish both artefacts with the same script and the SAME `<YYYY-MM-DD_HHMM>` stem.
It routes by extension on its own — `.md` to the note operation, `.json` to the
file operation.

# STRICT — never read the rendered markdown and pass it to `mcp__kado__kado-write`.
# Why: content relayed through your own tokens cannot be checked against the file it came from, and the script reads it from disk.

```bash
python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-rendered.md --vault "<INBOX_PATH>/<YYYY-MM-DD_HHMM>_suggestions.md"
python3 scripts/kado-write-file.py --local tomo-tmp/suggestions-wire.json --vault "<INBOX_PATH>/<YYYY-MM-DD_HHMM>_suggestions.json"
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
