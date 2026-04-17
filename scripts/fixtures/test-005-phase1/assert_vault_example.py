#!/usr/bin/env python3
"""Assert vault-example.yaml structure for Spec 005 Phase 1."""
import sys

try:
    import yaml
except ImportError:
    print("FAIL: PyYAML not available", file=sys.stderr)
    sys.exit(2)

vault_yaml_path = sys.argv[1]
with open(vault_yaml_path, "r", encoding="utf-8") as fh:
    cfg = yaml.safe_load(fh)

errors = []

# today_fields checks
trackers = cfg.get("trackers", {})
daily_trackers = trackers.get("daily_note_trackers", {})
today_fields = daily_trackers.get("today_fields", [])

if not today_fields:
    errors.append("trackers.daily_note_trackers.today_fields is empty or missing")

for i, field in enumerate(today_fields):
    label = field.get("name", f"today_fields[{i}]")
    if not field.get("description", "").strip():
        errors.append(f"today_fields[{i}] ({label}): description is empty")
    if "positive_keywords" not in field:
        errors.append(f"today_fields[{i}] ({label}): missing positive_keywords")
    elif not isinstance(field["positive_keywords"], list):
        errors.append(f"today_fields[{i}] ({label}): positive_keywords must be a list")
    if "negative_keywords" not in field:
        errors.append(f"today_fields[{i}] ({label}): missing negative_keywords")
    elif not isinstance(field["negative_keywords"], list):
        errors.append(f"today_fields[{i}] ({label}): negative_keywords must be a list")

# end_of_day_fields checks
eod = daily_trackers.get("end_of_day_fields", {})
eod_fields = eod.get("fields", [])

if not eod_fields:
    errors.append("trackers.daily_note_trackers.end_of_day_fields.fields is empty or missing")

for i, field in enumerate(eod_fields):
    label = field.get("name", f"eod_fields[{i}]")
    if not field.get("description", "").strip():
        errors.append(f"end_of_day_fields.fields[{i}] ({label}): description is empty")
    if "positive_keywords" not in field:
        errors.append(f"end_of_day_fields.fields[{i}] ({label}): missing positive_keywords")
    elif not isinstance(field["positive_keywords"], list):
        errors.append(f"end_of_day_fields.fields[{i}] ({label}): positive_keywords must be a list")
    if "negative_keywords" not in field:
        errors.append(f"end_of_day_fields.fields[{i}] ({label}): missing negative_keywords")
    elif not isinstance(field["negative_keywords"], list):
        errors.append(f"end_of_day_fields.fields[{i}] ({label}): negative_keywords must be a list")

# daily_log checks
daily_log = cfg.get("daily_log")
if daily_log is None:
    errors.append("top-level daily_log: key is missing")
else:
    required_keys = {"enabled", "section", "heading_level", "time_extraction", "link_format", "cutoff_days", "auto_create_if_missing"}
    missing_keys = required_keys - set(daily_log.keys())
    if missing_keys:
        errors.append(f"daily_log: missing keys: {sorted(missing_keys)}")

    time_extraction = daily_log.get("time_extraction", {})
    sources = time_extraction.get("sources")
    if not isinstance(sources, list):
        errors.append(f"daily_log.time_extraction.sources must be a list, got {type(sources).__name__}")

    auto_create = daily_log.get("auto_create_if_missing", {})
    for sub_key in ("past", "today", "future"):
        val = auto_create.get(sub_key)
        if val is not False:
            errors.append(f"daily_log.auto_create_if_missing.{sub_key} must be false, got {val!r}")

if errors:
    for e in errors:
        print(f"FAIL: {e}", file=sys.stderr)
    sys.exit(1)

print("OK: vault-example.yaml structure valid", file=sys.stderr)
sys.exit(0)
