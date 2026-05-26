---
name: force-atomic-handling
description: Force Atomic Note sub-flow for fan-resolve action. Load when routing-plan.action is fan-resolve or force_atomic_items is non-empty.
user-invocable: false
---
# Force Atomic Handling
# version: 0.1.0

## When to Activate

Load this skill when:
- `routing-plan.action == "fan-resolve"`
- `routing-plan.force_atomic_items` is non-empty

## Fan-Resolve Flow

### 1. Read force_atomic_items from routing plan

```bash
python3 -c "import json; items = json.load(open('tomo-tmp/routing-plan.json'))['force_atomic_items']; print(json.dumps(items, indent=2))"
```

### 2. Dispatch per-item inbox-analyst subagents

For each force-atomic item, dispatch an inbox-analyst subagent with:
- The source suggestion item's content (from cache)
- `force_atomic=true` flag
- The item's stem and source_path

### 3. Write fan companion document

Collect analyst outputs into a fan companion document:
- Filename: `<date>_suggestions-fan.md`
- Format: mirrors parent suggestions doc structure
- Each item gets expanded atomic-note-level analysis

Write the fan companion to the vault:
```bash
python3 scripts/kado-write-file.py "<inbox_path>/<fan_filename>" "<local_path>"
```

### 4. Tag the fan doc with tomo frontmatter

```bash
python3 -c "
import sys, json
sys.path.insert(0, 'tomo/scripts')
from lib.doc_frontmatter import build_tomo_block
block = build_tomo_block('suggestions-fan', 'pending-approval', '<run_id>')
print(json.dumps({'tomo': block}))
" | python3 scripts/kado-write-file.py --operation frontmatter "<vault_path>"
```

## Force Atomic Items Schema

Each item in `force_atomic_items`:
```json
{"stem": "item-title", "source_path": "100 Inbox/suggestions.md", "section_id": "S03"}
```

- `stem`: the suggestion item title/stem
- `source_path`: vault path of the suggestions doc
- `section_id`: optional section identifier within the doc
