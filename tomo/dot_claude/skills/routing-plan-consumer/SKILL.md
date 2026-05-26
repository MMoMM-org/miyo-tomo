---
name: routing-plan-consumer
description: Use PROACTIVELY when a conductor needs to read tomo-tmp/routing-plan.json, branch on the action field, or access typed work buckets from triage output.
user-invocable: false
---
# Routing Plan Consumer
# version: 0.1.0

## Reading the Plan

```bash
python3 -c "import json; plan = json.load(open('tomo-tmp/routing-plan.json')); print(json.dumps(plan, indent=2))"
```

## Action Branching

| action | Route to |
|--------|----------|
| suggest | suggestion-conductor: classify new sources into suggestions docs |
| fan-resolve | suggestion-conductor: produce fan companion for force-atomic items |
| synthesize | synthesis-conductor: render instructions from approved inputs |
| transcribe | voice-transcriber: transcribe audio, then stop |
| idle | report status, exit |

## Accessing Typed Buckets

| Field | Contents |
|-------|----------|
| `plan["fresh_sources"]` | unclassified .md files (for suggest action) |
| `plan["approved_suggestions"]` | approved suggestions docs with `cache_path` keys |
| `plan["approved_fan"]` | approved fan companions with `cache_path` keys |
| `plan["approved_moc_proposals"]` | accepted MOC proposals with `cache_path` keys |
| `plan["force_atomic_items"]` | items with Force Atomic Note ticked (`stem`, `source_path`) |
| `plan["pending_approval"]` | docs awaiting user approval (informational only) |
| `plan["drift_indicators"]` | non-blocking drift warnings |
| `plan["skip_stems"]` | stems to exclude from suggestion-conductor |
| `plan["inbox_path"]` | vault-relative inbox folder path |
| `plan["metrics"]` | triage timing data |
