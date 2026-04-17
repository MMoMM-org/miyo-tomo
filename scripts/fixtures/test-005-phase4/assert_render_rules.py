#!/usr/bin/env python3
"""Assert render rules for daily_notes_updates block.

Usage:
  python assert_render_rules.py <reducer_script_path>

Builds synthetic daily_notes_updates[] entries and calls
render_daily_notes_updates_block() directly to check:

1. exists=false → "Create daily note ... first" checkbox present.
2. empty trackers → "Possible Trackers" header omitted.
3. non-empty log_entries → "Possible Log Entries" header present.
4. log_links → "Possible Log Links" header present.
5. time=null → "end of day" appears.
"""
import importlib.util
import sys

reducer_path = sys.argv[1]
spec = importlib.util.spec_from_file_location("suggestions_reducer", reducer_path)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

render = mod.render_daily_notes_updates_block

# Case 1: exists=false → Create-first checkbox
entry_missing = {
    "daily_note_stem": "2026-04-20",
    "exists": False,
    "trackers": [],
    "log_entries": [
        {"time": "08:00", "content": "morning jog", "reason": "short note", "source_stem": "jog", "source_section": "S01"}
    ],
    "log_links": [],
}
rendered = render([entry_missing])
assert "Create daily note [[2026-04-20]] first" in rendered, \
    f"Create-first checkbox missing for exists=false:\n{rendered[:500]}"

# Case 2: empty trackers → no "Possible Trackers" header
assert "Possible Trackers" not in rendered, \
    f"Possible Trackers header should be omitted when trackers empty:\n{rendered[:500]}"

# Case 3: non-empty log_entries → Log Entries header present
assert "Possible Log Entries" in rendered, \
    f"Possible Log Entries header missing:\n{rendered[:500]}"

# Case 4: time=null → "end of day"
entry_null_time = {
    "daily_note_stem": "2026-04-21",
    "exists": True,
    "trackers": [],
    "log_entries": [],
    "log_links": [
        {"target_stem": "some-note", "time": None, "reason": "substantive note", "source_stem": "some-note", "source_section": "S02"}
    ],
}
rendered2 = render([entry_null_time])
assert "end of day" in rendered2, \
    f"'end of day' missing for null time:\n{rendered2[:500]}"

# Case 5: log_links → Possible Log Links header present
assert "Possible Log Links" in rendered2, \
    f"Possible Log Links header missing:\n{rendered2[:500]}"

# Case 6: exists=true → NO Create-first checkbox
entry_exists = {
    "daily_note_stem": "2026-04-22",
    "exists": True,
    "trackers": [{"field": "Sport", "value": True, "reason": "ran", "source_stem": "run", "source_section": "S01"}],
    "log_entries": [],
    "log_links": [],
}
rendered3 = render([entry_exists])
assert "Create daily note" not in rendered3, \
    f"Create-first checkbox should NOT appear when exists=true:\n{rendered3[:500]}"

print("OK: all render-rule assertions passed")
