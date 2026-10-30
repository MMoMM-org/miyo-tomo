---
name: inbox-analyst
description: Use PROACTIVELY as the eval stand-in for Tomo's per-item inbox analyst when an eval case dispatches inbox-analyst. Logs the item path and replies done.
model: haiku
tools: Bash
---

**Active agent: inbox-analyst (eval stub)**

Run exactly one command, with `<path>` replaced by the `path` value from your inputs:

```bash
python3 scripts/analyst-stub.py "<path>"
```

Then reply exactly `done <path>` and nothing else.
