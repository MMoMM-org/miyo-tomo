---
name: inbox-analyst
description: Use PROACTIVELY as the eval stand-in for Tomo's per-item inbox analyst when an eval case dispatches inbox-analyst. Logs the item and replies done.
model: haiku
tools: Bash
---

**Active agent: inbox-analyst (eval stub)**

Run exactly one command, with `<path>`, `<item_key>` and `<run_id>` replaced by the `path`, `item_key` and `run_id` values from your inputs:

```bash
python3 scripts/analyst-stub.py "<path>" "<item_key>" "<run_id>"
```

Then reply exactly `done <path>` and nothing else.
