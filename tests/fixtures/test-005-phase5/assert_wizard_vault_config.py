#!/usr/bin/env python3
"""Assert a wizard-written vault-config YAML has required structure.

Usage:
  python assert_wizard_vault_config.py <vault-config.yaml>

Checks:
1. Parses as valid YAML
2. Has trackers section with today_fields and end_of_day_fields
3. All tracker fields have non-empty description
4. All tracker fields have positive_keywords list (flat form)
5. Has daily_log section
6. daily_log has heading, heading_level, time_extraction, cutoff_days
7. auto_create_if_missing is False (MVP constraint)
"""
import sys
import yaml

def check(condition, msg):
    if not condition:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)

with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f)

check(cfg is not None, "vault-config.yaml is empty or invalid YAML")

# Test 2: trackers structure
check("trackers" in cfg, "missing top-level 'trackers' key")
t = cfg["trackers"]
check("daily_note_trackers" in t, "missing trackers.daily_note_trackers")
check("end_of_day_fields" in t, "missing trackers.end_of_day_fields")
today_fields = t["daily_note_trackers"].get("today_fields", [])
eod_fields = t["end_of_day_fields"].get("fields", [])

# Test 3: all tracker fields have non-empty description
all_fields = today_fields + eod_fields
check(len(all_fields) > 0, "no tracker fields found")
for f in all_fields:
    desc = f.get("description", "")
    check(desc and desc.strip(), f"tracker field '{f.get('name')}' has empty description")

# Test 4: positive_keywords exists (flat form — may be empty list, but key must exist)
for f in all_fields:
    check("positive_keywords" in f, f"tracker field '{f.get('name')}' missing positive_keywords")

# Test 5: daily_log section
check("daily_log" in cfg, "missing top-level 'daily_log' key")
dl = cfg["daily_log"]

# Test 6: required daily_log fields
for required in ["heading", "heading_level", "time_extraction", "cutoff_days"]:
    check(required in dl, f"daily_log missing '{required}' field")

check("sources" in dl["time_extraction"],
      "daily_log.time_extraction missing 'sources' list")
check(len(dl["time_extraction"]["sources"]) > 0,
      "daily_log.time_extraction.sources is empty")
check("fallback" in dl["time_extraction"],
      "daily_log.time_extraction missing 'fallback' field")

# Test 7: auto_create_if_missing is False (MVP constraint)
check("auto_create_if_missing" in dl,
      "daily_log missing 'auto_create_if_missing' field")
check(dl["auto_create_if_missing"] is False,
      f"daily_log.auto_create_if_missing must be false (MVP), got: {dl['auto_create_if_missing']}")

print("OK: all vault-config structure assertions passed")
