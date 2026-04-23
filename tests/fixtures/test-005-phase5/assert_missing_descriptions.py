#!/usr/bin/env python3
"""Assert that a vault-config with incomplete tracker descriptions is detected.

Usage:
  python assert_missing_descriptions.py <vault-config.yaml>

Exits 0 and prints the count of fields missing descriptions.
Exits 1 if all fields have descriptions (fixture is wrong).
"""
import sys
import yaml

with open(sys.argv[1]) as f:
    cfg = yaml.safe_load(f)

t = cfg.get("trackers", {})
today = t.get("daily_note_trackers", {}).get("today_fields", [])
eod = t.get("end_of_day_fields", {}).get("fields", [])
all_fields = today + eod

missing = [f["name"] for f in all_fields if not f.get("description", "").strip()]

if not missing:
    print("FAIL: fixture should have missing descriptions but all fields have them", file=sys.stderr)
    sys.exit(1)

print(f"OK: {len(missing)} tracker field(s) lack descriptions: {missing}")
