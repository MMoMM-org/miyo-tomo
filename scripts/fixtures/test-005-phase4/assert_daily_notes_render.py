#!/usr/bin/env python3
"""Assert rendering of daily_notes_updates[] entries.

Usage:
  python assert_daily_notes_render.py <suggestions-doc.json>

Checks:
1. daily_notes_updates has 2 entries, date-sorted.
2. First entry (2026-04-15) has tracker + log_entry + log_link.
3. Second entry (2026-04-16) has log_entry, no trackers.
4. Material für mirror appears in the create_atomic_note section for reading-notes.
5. decision_precedence_note is present.
"""
import json
import sys

doc = json.load(open(sys.argv[1]))

# Test 1: 2 daily_notes_updates entries, date-sorted
dnu = doc.get("daily_notes_updates", [])
assert len(dnu) == 2, f"expected 2 daily_notes_updates, got {len(dnu)}: {[d['daily_note_stem'] for d in dnu]}"
assert dnu[0]["daily_note_stem"] == "2026-04-15", f"first stem={dnu[0]['daily_note_stem']}"
assert dnu[1]["daily_note_stem"] == "2026-04-16", f"second stem={dnu[1]['daily_note_stem']}"

# Test 2: first entry has all three categories
d0 = dnu[0]
assert len(d0["trackers"]) >= 1, "2026-04-15 should have tracker(s)"
assert len(d0["log_entries"]) >= 1, "2026-04-15 should have log_entry"
assert len(d0["log_links"]) >= 1, "2026-04-15 should have log_link"

# Test 3: second entry has log_entry, no trackers
d1 = dnu[1]
assert len(d1["trackers"]) == 0, f"2026-04-16 should have no trackers, got {d1['trackers']}"
assert len(d1["log_entries"]) >= 1, "2026-04-16 should have log_entry"

# Test 4: Material für mirror in create_atomic_note rendered_md for reading-notes
reading_section = next((s for s in doc["sections"] if s["stem"] == "reading-notes"), None)
assert reading_section is not None, "reading-notes section not found"
atomic_action = next((a for a in reading_section["actions"] if a["kind"] == "create_atomic_note"), None)
assert atomic_action is not None, "create_atomic_note action not found in reading-notes"
assert "Material für" in atomic_action["rendered_md"], \
    f"Material für not in reading-notes create_atomic_note rendered_md:\n{atomic_action['rendered_md'][:500]}"

# Test 5: decision_precedence_note present
assert "decision_precedence_note" in doc, "decision_precedence_note missing from doc"
assert len(doc["decision_precedence_note"]) > 10, "decision_precedence_note is empty"

print("OK: all assertions passed")
