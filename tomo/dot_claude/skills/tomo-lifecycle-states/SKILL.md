---
name: tomo-lifecycle-states
description: Tomo lifecycle state machine, valid transitions, and state-promoter invocation patterns. Load when flipping doc states or validating lifecycle consistency.
user-invocable: false
---
# Tomo Lifecycle States
# version: 0.1.0

## State Machine

| doc_type | States | Terminal |
|----------|--------|----------|
| source | captured | captured |
| suggestions | pending-approval → approved | approved |
| suggestions-fan | pending-approval → approved | approved |
| moc-proposal | pending-accept → accepted | accepted |
| instructions | pending-apply → applied | applied |

## Checking Current State

```bash
python3 -c "
import json, sys
sys.path.insert(0, 'tomo/scripts')
from lib.kado_client import KadoClient
client = KadoClient()
hits = client.search_by_frontmatter('tomo.state=pending-approval', path_prefix='100 Inbox/')
for h in hits:
    print(f\"{h['path']}: {h['frontmatter'].get('tomo', {}).get('state', 'unknown')}\")
"
```

## Flipping State

Use state-promoter.py for validated transitions:
```bash
python3 tomo/scripts/state-promoter.py flip --path "<vault_path>" --to "<target_state>"
```

The promoter validates the transition against the state machine and retries once on optimistic-concurrency failure.

## Checking Approval Checkbox

```bash
python3 tomo/scripts/state-promoter.py check_tick --path "<vault_path>" --checkbox "Approved"
```

Returns exit 0 if ticked, exit 1 if not. Check before flipping to approved.

## Frontmatter Validation

```bash
TOMO_SCHEMA_STRICT=1 python3 -c "
import sys
sys.path.insert(0, 'tomo/scripts')
from lib.doc_frontmatter import build_tomo_block
block = build_tomo_block('<doc_type>', '<state>', '<run_id>')
print('Valid' if block else 'Invalid')
"
```
