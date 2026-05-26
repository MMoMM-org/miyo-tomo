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

Write a script to `tomo-tmp/check_state.py` then run it:

```python
# tomo-tmp/check_state.py
import json, sys
sys.path.insert(0, 'scripts')
from lib.kado_client import KadoClient
client = KadoClient()
hits = client.search_by_frontmatter('tomo.state=pending-approval', path_prefix='100 Inbox/')
for h in hits:
    print(f"{h['path']}: {h['frontmatter'].get('tomo', {}).get('state', 'unknown')}")
```

```bash
python3 tomo-tmp/check_state.py
```

## Flipping State

Use state-promoter.py for validated transitions:
```bash
python3 scripts/state-promoter.py flip "<vault_path>" <doc_type> <from_state> <to_state> "<run_id>"
```

The promoter validates the transition against the state machine and retries once on optimistic-concurrency failure.

## Checking Approval Checkbox

```bash
python3 scripts/state-promoter.py check-tick "<vault_path>" <doc_type>
```

Returns exit 0 if ticked, exit 10 if not, exit 11 if unreadable. Check before flipping to approved.

## Frontmatter Validation

Frontmatter is built and written exclusively via state-promoter.py — direct calls to build_tomo_block are not needed from agent context.
