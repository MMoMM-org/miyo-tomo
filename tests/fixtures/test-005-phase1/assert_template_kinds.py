#!/usr/bin/env python3
"""Assert that item-result.template.json contains all three update kinds."""
import json
import sys

template_path = sys.argv[1]
with open(template_path, "r", encoding="utf-8") as fh:
    tmpl = json.load(fh)

actions = tmpl.get("actions", [])
update_daily = next((a for a in actions if a.get("kind") == "update_daily"), None)
if update_daily is None:
    print("FAIL: no update_daily action found in template", file=sys.stderr)
    sys.exit(1)

updates = update_daily.get("updates", [])
found_kinds = {u.get("kind") for u in updates if isinstance(u, dict)}
required_kinds = {"tracker", "log_entry", "log_link"}
missing = required_kinds - found_kinds

if missing:
    print(f"FAIL: updates[] missing kinds: {sorted(missing)}", file=sys.stderr)
    sys.exit(1)

print(f"OK: found kinds {sorted(found_kinds)}", file=sys.stderr)
sys.exit(0)
