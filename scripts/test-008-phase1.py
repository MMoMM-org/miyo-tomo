#!/usr/bin/env python3
# version: 0.2.0
"""test-008-phase1.py — Unit coverage for instruction-render action-building.

Exercises `build_actions()` + `render_instructions_md()` with a handcrafted
manifest + parsed-suggestions payload. No Kado, no vault — pure function tests
that verify the XDD 008 Phase 1 contract:

  - action IDs are monotonic I01..INN
  - every action type the plan lists is emitted
  - instructions.json is valid per instructions.schema.json
  - instructions.md renders deterministically with the right section order
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "instruction_render", SCRIPT_DIR / "instruction-render.py"
)
ir = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(ir)


CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}

MANIFEST = [
    {
        "id": "A1",
        "action": None,  # regular atomic note
        "title": "Asahikawa — Snow city notes",
        "source_path": "Asahikawa.md",
        "template": "t_note_tomo",
        "rendered_file": "2026-04-21_1200_asahikawa-snow-city-notes.md",
        "rendered_path": "/tmp/rendered/2026-04-21_1200_asahikawa-snow-city-notes.md",
        "destination": "Atlas/202 Notes/",
        "parent_moc": "Japan (MOC)",
        "parent_mocs": ["Japan (MOC)", "Travel (MOC)"],
        "tags": ["topic/travel/japan"],
    },
    {
        "id": "A2",
        "action": None,
        "title": "Catan Strategy",
        "source_path": "Catan.md",
        "template": "t_note_tomo",
        "rendered_file": "2026-04-21_1200_catan-strategy.md",
        "rendered_path": "/tmp/rendered/2026-04-21_1200_catan-strategy.md",
        "destination": "Atlas/202 Notes/",
        "parent_moc": "",
        "parent_mocs": [],
        "tags": [],
    },
    {
        "id": "MOC01",
        "action": "create_moc",
        "title": "Sport (MOC)",
        "source_path": None,
        "template": "t_moc",
        "rendered_file": "2026-04-21_1200_sport-moc.md",
        "rendered_path": "/tmp/rendered/2026-04-21_1200_sport-moc.md",
        "destination": "Atlas/200 Maps/",
        "parent_moc": "2100 - Health",
        "parent_mocs": ["2100 - Health"],
        "supporting_items": "A2",
        "tags": ["type/others/moc"],
    },
]

CONFIRMED = [
    {
        "id": "A1",
        "source_path": "Asahikawa.md",
        "action": None,
        "title": "Asahikawa — Snow city notes",
        "tags": ["topic/travel/japan"],
        "parent_moc": "Japan (MOC)",
        "parent_mocs": ["Japan (MOC)", "Travel (MOC)"],
    },
    {
        "id": "A2",
        "source_path": "Catan.md",
        "action": None,
        "title": "Catan Strategy",
        "tags": [],
        "parent_moc": "",
        "parent_mocs": [],
    },
    {
        "id": "MOC01",
        "action": "create_moc",
        "title": "Sport (MOC)",
        "parent_moc": "2100 - Health",
        "parent_mocs": ["2100 - Health"],
        "supporting_items": "A2",  # pulls Catan in as a child link
    },
]

DAILY_UPDATES = [
    {
        "date": "2026-03-26",
        "daily_note_path": "Calendar/301 Daily/2026-03-26.md",
        "trackers": [
            {
                "field": "Sport",
                "value": "true",
                "syntax": "inline_field",
                "section": "Tracker",
                "source_stem": "Sport",
                "reason": "Went running",
                "accepted": True,
            },
        ],
        "log_entries": [
            {
                "time": None,
                "position": "after_last_line",
                "content": "Viel Sport gemacht",
                "reason": "notable",
                "source_stem": "Sport",
                "accepted": True,
            },
            {
                "time": "10:00",
                "position": "at_time",
                "content": "Ignored — unaccepted",
                "accepted": False,
            },
        ],
        "log_links": [
            {
                "target_stem": "Asahikawa",
                "time": None,
                "position": "after_last_line",
                "accepted": True,
            },
        ],
    },
]

SKIPPED = [
    {"id": "B1", "source_path": "Trash.md", "disposition": "delete_source"},
    {"id": "B2", "source_path": "Keep.md", "disposition": "skip"},
]


def _must(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        sys.exit(1)


def test_action_building():
    actions = ir.build_actions(MANIFEST, CONFIRMED, DAILY_UPDATES, SKIPPED, CFG)

    kinds = [a["action"] for a in actions]
    ids = [a["id"] for a in actions]

    # IDs must be monotonic I01..INN
    _must(ids == [f"I{i+1:02d}" for i in range(len(ids))],
          f"IDs must be I01..INN, got {ids}")

    # Expected action mix:
    # A1 atomic (move_note) + A2 atomic (move_note) + MOC01 (create_moc)
    # = 2 move_note, 1 create_moc.
    # Links: A1 parent_mocs × 2 (Japan, Travel) + MOC01 parent_mocs × 1 (2100)
    #        + supporting_items down-link (MOC01 → A2) = 4 links.
    counts = {k: kinds.count(k) for k in set(kinds)}
    _must(counts.get("move_note") == 2, f"expected 2 move_note, got {counts}")
    _must(counts.get("create_moc") == 1, f"expected 1 create_moc, got {counts}")
    _must(counts.get("link_to_moc") == 4,
          f"expected 4 link_to_moc (2 A1 parent + 1 MOC01 parent + 1 supporting_items), got {counts}")
    _must(counts.get("update_tracker") == 1, f"expected 1 update_tracker, got {counts}")
    _must(counts.get("update_log_entry") == 1, f"expected 1 update_log_entry, got {counts}")
    _must(counts.get("update_log_link") == 1, f"expected 1 update_log_link, got {counts}")
    # Sport source_stem is daily-only (not in confirmed) → 1 daily-only delete
    # Plus 1 from skipped disposition=delete_source = 2
    _must(counts.get("delete_source") == 2, f"expected 2 delete_source, got {counts}")
    _must(counts.get("skip") == 1, f"expected 1 skip, got {counts}")

    # Ordering: create_moc before move_note before link_to_moc.
    def _first_idx(kind: str) -> int:
        for i, k in enumerate(kinds):
            if k == kind:
                return i
        return -1
    _must(_first_idx("create_moc") >= 0, "create_moc must be emitted")
    _must(_first_idx("create_moc") < _first_idx("move_note"),
          f"create_moc must come before move_note, got kinds={kinds}")
    _must(_first_idx("move_note") < _first_idx("link_to_moc"),
          f"move_note must come before link_to_moc, got kinds={kinds}")
    _must(_first_idx("link_to_moc") < _first_idx("update_tracker"),
          f"link_to_moc must come before daily updates, got kinds={kinds}")

    # move_note now carries source + destination full paths + origin_inbox_item
    moves = [a for a in actions if a["action"] == "move_note"]
    a1_move = next(m for m in moves if m["title"] == "Asahikawa — Snow city notes")
    _must(a1_move["source"] == "100 Inbox/2026-04-21_1200_asahikawa-snow-city-notes.md",
          f"move_note.source mismatch: {a1_move['source']}")
    _must(a1_move["destination"] == "Atlas/202 Notes/Asahikawa — Snow city notes.md",
          f"move_note.destination mismatch: {a1_move['destination']}")
    _must(a1_move["origin_inbox_item"] == "100 Inbox/Asahikawa.md",
          f"move_note.origin_inbox_item mismatch: {a1_move['origin_inbox_item']}")
    # delete_source boolean must not leak into move_note
    _must("delete_source" not in a1_move, "move_note must not carry a delete_source boolean")
    # source_path (old field) must be gone
    _must("source_path" not in a1_move, "move_note must not carry legacy source_path")

    # create_moc also carries source + destination full paths
    cm = next(a for a in actions if a["action"] == "create_moc")
    _must(cm["source"] == "100 Inbox/2026-04-21_1200_sport-moc.md",
          f"create_moc.source mismatch: {cm['source']}")
    _must(cm["destination"] == "Atlas/200 Maps/Sport (MOC).md",
          f"create_moc.destination mismatch: {cm['destination']}")
    _must(cm["supporting_items"] == "A2", "create_moc.supporting_items preserved")

    # link_to_moc uses bare stems + dedupes. The supporting_items expansion
    # pulls A2 (Catan) into MOC01 (Sport (MOC)).
    links = [a for a in actions if a["action"] == "link_to_moc"]
    supporting_link = next(
        (l for l in links if l["target_moc"] == "Sport (MOC)"
         and l["source_note_title"] == "Catan Strategy"),
        None,
    )
    _must(supporting_link is not None,
          f"supporting_items expansion must emit Sport (MOC) ← Catan Strategy link, got {links}")
    _must(supporting_link["line_to_add"] == "- [[Catan Strategy]]",
          f"supporting_items link_to_add wrong: {supporting_link['line_to_add']}")

    # MOC up-link (Sport (MOC) → 2100) must still exist
    up_link = next(
        (l for l in links if l["target_moc"] == "2100 - Health"
         and l["source_note_title"] == "Sport (MOC)"),
        None,
    )
    _must(up_link is not None, f"Sport (MOC) → 2100 up-link missing, got {links}")

    # Tracker action carries date + field + syntax
    tr = next(a for a in actions if a["action"] == "update_tracker")
    _must(tr["date"] == "2026-03-26", "tracker date wrong")
    _must(tr["field"] == "Sport", "tracker field wrong")
    _must(tr["syntax"] == "inline_field", "tracker syntax wrong")

    # delete_source reasons are populated, paths are vault-relative with .md
    dels = [a for a in actions if a["action"] == "delete_source"]
    for d in dels:
        _must(d["source_path"].endswith(".md"), f"delete path missing .md: {d}")
        _must(d["reason"], f"delete reason empty: {d}")

    print(f"[PASS] action_building — {len(actions)} actions, {len(set(kinds))} types, "
          f"ordered correctly, supporting_items expanded")
    return actions


def test_schema_validity(actions):
    """Validate instructions.json against instructions.schema.json."""
    schema_path = SCRIPT_DIR.parent / "tomo" / "schemas" / "instructions.schema.json"
    schema = json.loads(schema_path.read_text())

    doc = {
        "schema_version": "1",
        "type": "tomo-instructions",
        "source_suggestions": "test.json",
        "generated": "2026-04-21T12:00:00Z",
        "profile": "miyo",
        "tomo_version": None,
        "action_count": len(actions),
        "actions": actions,
    }

    # Required top-level fields
    for field in schema["required"]:
        _must(field in doc, f"instructions.json missing required field: {field}")

    # Per-action: required fields present + no unexpected fields
    action_defs = schema["$defs"]
    action_def_by_kind = {
        "move_note": action_defs["move_note"],
        "link_to_moc": action_defs["link_to_moc"],
        "update_tracker": action_defs["update_tracker"],
        "update_log_entry": action_defs["update_log_entry"],
        "update_log_link": action_defs["update_log_link"],
        "create_moc": action_defs["create_moc"],
        "delete_source": action_defs["delete_source"],
        "skip": action_defs["skip"],
    }
    for action in actions:
        kind = action["action"]
        action_schema = action_def_by_kind.get(kind)
        _must(action_schema is not None, f"unknown action kind: {kind}")
        # Required fields present
        for req in action_schema["required"]:
            _must(req in action, f"{action['id']} ({kind}) missing required field: {req}")
        # No unknown fields (schema has additionalProperties:false)
        allowed = set(action_schema["properties"])
        for field in action:
            _must(field in allowed, f"{action['id']} ({kind}) has unexpected field: {field}")

    # Try real jsonschema validation if installed (stricter)
    try:
        import jsonschema
        jsonschema.validate(doc, schema)
        print(f"[PASS] schema_validity — {len(actions)} actions valid per jsonschema.validate")
    except ImportError:
        print(f"[PASS] schema_validity — {len(actions)} actions pass structural check "
              f"(jsonschema not installed for full validation)")


def test_md_rendering(actions):
    md = ir.render_instructions_md(
        actions,
        {
            "source_suggestions": "test_suggestions",
            "generated": "2026-04-21T12:00:00Z",
            "profile": "miyo",
            "tomo_version": "0.2.0",
        },
        CFG,
    )

    # Frontmatter
    _must(md.startswith("---\n"), "MD must start with frontmatter")
    _must("type: tomo-instructions" in md, "MD missing type field")
    _must(f"action_count: {len(actions)}" in md, "MD action_count wrong")
    _must("profile: miyo" in md, "MD profile missing")

    # Section order
    sections = ["## New Files", "## MOC Links", "## Daily Updates", "## Source Deletions", "## Skips"]
    positions = [md.find(s) for s in sections]
    _must(all(p > 0 for p in positions), f"missing sections: {list(zip(sections, positions))}")
    _must(positions == sorted(positions), f"sections out of order: {positions}")

    # Every action ID is present
    for a in actions:
        _must(f"### {a['id']} —" in md, f"MD missing heading for {a['id']}")

    # Wikilink hygiene — no .md inside double brackets
    import re
    for match in re.finditer(r"\[\[([^\]]+)\]\]", md):
        inner = match.group(1)
        _must(not inner.endswith(".md"), f"wikilink still has .md: {inner}")

    # Checkboxes
    _must(md.count("- [ ] Applied") == len(actions),
          f"expected {len(actions)} checkboxes, got {md.count('- [ ] Applied')}")

    print(f"[PASS] md_rendering — {len(md)} chars, all {len(actions)} actions rendered")


def test_config_loading(tmp_config_yaml: Path):
    cfg = ir.load_config(str(tmp_config_yaml))
    _must(cfg["profile"] == "miyo", f"profile mismatch: {cfg['profile']}")
    _must(cfg["concepts.inbox"] == "100 Inbox/", f"inbox mismatch")
    # Daily path should be trimmed of trailing space
    _must(cfg["concepts.calendar.granularities.daily.path"] == "Calendar/301 Daily/",
          f"daily path not trimmed: {cfg['concepts.calendar.granularities.daily.path']!r}")
    _must(cfg["daily_log.heading_level"] == 2, f"heading_level not int")
    print("[PASS] config_loading — all fields resolved")


def main() -> int:
    import tempfile
    sample_yaml = """
schema_version: 1
profile: "miyo"
concepts:
  inbox: "100 Inbox/"
  calendar:
    granularities:
      daily:
        path: "Calendar/301 Daily/ "
daily_log:
  heading: "Daily Log"
  heading_level: 2
"""
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as tf:
        tf.write(sample_yaml)
        cfg_path = Path(tf.name)
    try:
        test_config_loading(cfg_path)
    finally:
        cfg_path.unlink(missing_ok=True)

    actions = test_action_building()
    test_schema_validity(actions)
    test_md_rendering(actions)

    print("\n✓ All XDD-008 Phase 1 tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
