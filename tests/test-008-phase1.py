#!/usr/bin/env python3
# version: 0.3.3
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

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import importlib.util

_spec = importlib.util.spec_from_file_location(
    "instruction_render", SCRIPTS_DIR / "instruction-render.py"
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
    # Dedup: after backfill, parent_mocs and supporting_items paths both produce
    # the same (target, source) key — must emit exactly once.
    sport_catan_count = sum(
        1 for l in links
        if l["target_moc"] == "Sport (MOC)" and l["source_note_title"] == "Catan Strategy"
    )
    _must(sport_catan_count == 1,
          f"Sport (MOC) ← Catan must appear exactly once, got {sport_catan_count}")

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

    # Every action carries applied=False on emission — consumer (Tomo Hashi)
    # flips to True after successful execution. See docs/instructions-json.md.
    for a in actions:
        _must("applied" in a, f"{a['id']} ({a['action']}) missing applied field")
        _must(a["applied"] is False,
              f"{a['id']} ({a['action']}) applied must be False on emission, got {a['applied']!r}")

    print(f"[PASS] action_building — {len(actions)} actions, {len(set(kinds))} types, "
          f"ordered correctly, supporting_items expanded, applied=False stamped")
    return actions


def test_schema_validity(actions):
    """Validate instructions.json against instructions.schema.json."""
    schema_path = REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"
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


def test_backfill_supporting_items_parents():
    """Supporting items inherit the new MOC as their primary parent so the
    rendering loop writes `up:: [[<new MOC>]]` into the atomic note."""
    # Case 1: item with no existing parents → new MOC becomes primary
    confirmed = [
        {"id": "A1", "source_path": "Catan.md", "action": None,
         "title": "Catan Strategy", "parent_moc": "",
         "parent_mocs": []},
        {"id": "MOC01", "action": "create_moc", "title": "Brettspiele (MOC)",
         "parent_moc": "2700", "parent_mocs": ["2700"],
         "supporting_items": "A1"},
    ]
    ir.backfill_supporting_items_parents(confirmed)
    a1 = next(it for it in confirmed if it["id"] == "A1")
    _must(a1["parent_moc"] == "Brettspiele (MOC)",
          f"primary parent_moc must be set to new MOC, got {a1['parent_moc']!r}")
    _must(a1["parent_mocs"] == ["Brettspiele (MOC)"],
          f"parent_mocs must contain new MOC, got {a1['parent_mocs']}")

    # Case 2: item with existing parent → new MOC prepended, existing preserved
    confirmed = [
        {"id": "A1", "source_path": "Catan.md", "action": None,
         "title": "Catan Strategy", "parent_moc": "Games (MOC)",
         "parent_mocs": ["Games (MOC)"]},
        {"id": "MOC01", "action": "create_moc", "title": "Brettspiele (MOC)",
         "parent_moc": "2700", "parent_mocs": ["2700"],
         "supporting_items": "A1"},
    ]
    ir.backfill_supporting_items_parents(confirmed)
    a1 = next(it for it in confirmed if it["id"] == "A1")
    _must(a1["parent_mocs"][0] == "Brettspiele (MOC)",
          f"new MOC must be prepended, got {a1['parent_mocs']}")
    _must("Games (MOC)" in a1["parent_mocs"],
          f"existing parent must be preserved, got {a1['parent_mocs']}")
    # parent_moc was already set → NOT overwritten (existing primary wins)
    _must(a1["parent_moc"] == "Games (MOC)",
          f"existing parent_moc must not be overwritten, got {a1['parent_moc']!r}")

    # Case 3: idempotence — calling twice shouldn't re-prepend
    ir.backfill_supporting_items_parents(confirmed)
    a1 = next(it for it in confirmed if it["id"] == "A1")
    _must(a1["parent_mocs"].count("Brettspiele (MOC)") == 1,
          f"idempotence broken: Brettspiele appears twice in {a1['parent_mocs']}")
    print("[PASS] backfill_supporting_items_parents — prepend, preserve, idempotent")


def test_backfill_plus_build_actions_no_duplicate_links():
    """Real pipeline flow: backfill mutates confirmed → build_actions sees the
    up-link via parent_mocs AND the down-link via supporting_items, and must
    dedupe to exactly one action per (target_moc, source_title) pair."""
    confirmed = [
        {"id": "A1", "source_path": "Catan.md", "action": None,
         "title": "Catan Strategy", "tags": [],
         "parent_moc": "", "parent_mocs": []},
        {"id": "MOC01", "action": "create_moc", "title": "Brettspiele (MOC)",
         "tags": [], "parent_moc": "2700", "parent_mocs": ["2700"],
         "supporting_items": "A1"},
    ]
    manifest = [
        {"id": "A1", "action": None, "title": "Catan Strategy",
         "source_path": "Catan.md",
         "rendered_file": "2026-04-21_1200_catan.md",
         "destination": "Atlas/202 Notes/",
         "parent_moc": "", "parent_mocs": [], "tags": []},
        {"id": "MOC01", "action": "create_moc", "title": "Brettspiele (MOC)",
         "source_path": None,
         "rendered_file": "2026-04-21_1200_brettspiele-moc.md",
         "destination": "Atlas/200 Maps/",
         "parent_moc": "2700", "parent_mocs": ["2700"],
         "supporting_items": "A1", "tags": []},
    ]

    # Mimic main(): backfill mutates the confirmed list BEFORE building actions.
    # Also update the manifest entry for A1 to reflect the new parent — the
    # rendering loop would do this naturally (it re-reads from confirmed_items
    # after backfill), so for this integration test we sync it manually.
    ir.backfill_supporting_items_parents(confirmed)
    for m in manifest:
        if m["id"] == "A1":
            a1 = next(c for c in confirmed if c["id"] == "A1")
            m["parent_moc"] = a1["parent_moc"]
            m["parent_mocs"] = list(a1["parent_mocs"])

    actions = ir.build_actions(manifest, confirmed, [], [], CFG)
    links = [a for a in actions if a["action"] == "link_to_moc"]
    # Expected:
    #   1. Brettspiele ← Catan  (from A1's newly-backfilled parent_mocs)
    #   2. Brettspiele → 2700   (MOC01's own parent_mocs up-link)
    # Deduped: exactly 2 link_to_moc actions.
    _must(len(links) == 2,
          f"expected 2 link_to_moc actions after dedup, got {len(links)}: "
          f"{[(l['target_moc'], l['source_note_title']) for l in links]}")
    keys = {(l["target_moc"], l["source_note_title"]) for l in links}
    _must(("Brettspiele (MOC)", "Catan Strategy") in keys,
          f"down-link Brettspiele ← Catan missing: {keys}")
    _must(("2700", "Brettspiele (MOC)") in keys,
          f"up-link Brettspiele → 2700 missing: {keys}")

    # Also verify the atomic note's manifest entry got the up:: target.
    a1_mf = next(m for m in manifest if m["id"] == "A1")
    _must(a1_mf["parent_moc"] == "Brettspiele (MOC)",
          f"atomic note's parent_moc must be the new MOC: {a1_mf['parent_moc']}")
    print("[PASS] backfill + build_actions — no duplicate links, up:: target back-filled")


def test_resolve_section_names():
    """resolve_section_names reads each target MOC and captures the first
    editable callout's full line."""
    actions = [
        {"id": "I01", "action": "link_to_moc", "target_moc": "Japan (MOC)",
         "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
         "section_name": None, "source_note_title": "Asahikawa",
         "line_to_add": "- [[Asahikawa]]"},
        {"id": "I02", "action": "link_to_moc", "target_moc": "Japan (MOC)",
         "target_moc_path": "Atlas/200 Maps/Japan (MOC).md",
         "section_name": None, "source_note_title": "Sapporo",
         "line_to_add": "- [[Sapporo]]"},
        # No resolved path → stays null
        {"id": "I03", "action": "link_to_moc", "target_moc": "Brettspiele (MOC)",
         "target_moc_path": None,
         "section_name": None, "source_note_title": "Catan",
         "line_to_add": "- [[Catan]]"},
        # Unrelated action → untouched
        {"id": "I04", "action": "move_note", "source": "x", "destination": "y", "title": "z"},
    ]

    japan_moc_body = """---
tags: [type/others/moc]
---

# Japan (MOC)

> [!weather]- Current Weather
> (auto-generated)

> [!blocks]- Key Concepts
> - [[Tokyo]]
> - [[Kyoto]]

> [!shell]
> ```dataviewjs
> // query
> ```
"""

    class FakeClient:
        def __init__(self):
            self.reads = []
        def read_note(self, path):
            self.reads.append(path)
            if path == "Atlas/200 Maps/Japan (MOC).md":
                return {"content": japan_moc_body}
            return {"content": ""}

    client = FakeClient()
    resolved = ir.resolve_section_names(actions, client, ["connect", "blocks", "anchor"])
    _must(resolved == 2, f"expected 2 resolved, got {resolved}")
    _must(actions[0]["section_name"] == "[!blocks]- Key Concepts",
          f"I01 section_name wrong: {actions[0]['section_name']!r}")
    _must(actions[1]["section_name"] == "[!blocks]- Key Concepts",
          f"I02 section_name wrong: {actions[1]['section_name']!r}")
    _must(actions[2]["section_name"] is None, "I03 has no path → stays null")
    _must(len(client.reads) == 1, f"read caching broken — expected 1 read, got {len(client.reads)}")

    # `weather` is NOT in editable → skipped. First MATCHING callout (`blocks`)
    # is what we pick, even though `weather` appears earlier in the file.

    # Skips when editable list is empty
    for a in actions:
        a["section_name"] = None
    resolved_empty = ir.resolve_section_names(actions, client, [])
    _must(resolved_empty == 0, "empty editable list → 0 resolutions")

    # Degrades gracefully with None client
    resolved_no_client = ir.resolve_section_names(actions, None, ["blocks"])
    _must(resolved_no_client == 0, "no client → 0 resolutions")

    # Degrades gracefully when read_note raises
    class RaisingClient:
        def read_note(self, path):
            raise RuntimeError("kado down")
    actions_r = [{"id": "I01", "action": "link_to_moc", "target_moc": "X",
                  "target_moc_path": "Atlas/X.md", "section_name": None,
                  "source_note_title": "Y", "line_to_add": "- [[Y]]"}]
    resolved_raise = ir.resolve_section_names(actions_r, RaisingClient(), ["blocks"])
    _must(resolved_raise == 0, "raising client → 0 resolutions")
    _must(actions_r[0]["section_name"] is None, "raising client → stays null")

    # Priority regression: `connect` appears FIRST in the MOC but is the
    # navigation callout — content bullets should prefer `blocks` or any
    # non-connect editable. Picking `connect` would put atomic-note links
    # in the up::/related:: area (observed in the live Japan (MOC) output
    # before this fix).
    moc_connect_first = """---
---
# MOC

> [!connect] Your way around
> up:: [[Parent]]

> [!blocks]- Key Concepts
> - [[Existing]]
"""
    class PriorityClient:
        def read_note(self, path):
            return {"content": moc_connect_first}
    actions_p = [{"id": "I01", "action": "link_to_moc",
                  "target_moc": "M", "target_moc_path": "Atlas/M.md",
                  "section_name": None, "source_note_title": "N",
                  "line_to_add": "- [[N]]"}]
    ir.resolve_section_names(actions_p, PriorityClient(), ["connect", "blocks"])
    _must(actions_p[0]["section_name"] == "[!blocks]- Key Concepts",
          f"blocks must outrank connect even when connect is first in file "
          f"and first in editable list; got {actions_p[0]['section_name']!r}")
    # Fallback: if ONLY connect is editable, connect still wins
    actions_c = [{"id": "I01", "action": "link_to_moc",
                  "target_moc": "M", "target_moc_path": "Atlas/M.md",
                  "section_name": None, "source_note_title": "N",
                  "line_to_add": "- [[N]]"}]
    ir.resolve_section_names(actions_c, PriorityClient(), ["connect"])
    _must(actions_c[0]["section_name"] == "[!connect] Your way around",
          f"connect is the only editable → should be used as last resort")
    print("[PASS] resolve_section_names — editable match, caching, graceful degrade, connect-deprioritized")


def test_resolve_target_moc_paths():
    """resolve_target_moc_paths populates link_to_moc.target_moc_path via Kado."""
    actions = [
        {"id": "I01", "action": "link_to_moc", "target_moc": "Japan (MOC)",
         "target_moc_path": None, "source_note_title": "Asahikawa",
         "line_to_add": "- [[Asahikawa]]"},
        {"id": "I02", "action": "link_to_moc", "target_moc": "Japan (MOC)",
         "target_moc_path": None, "source_note_title": "Sapporo",
         "line_to_add": "- [[Sapporo]]"},
        {"id": "I03", "action": "move_note", "source": "x", "destination": "y", "title": "z"},
    ]

    class FakeClient:
        def __init__(self):
            self.calls = []
        def search_by_name(self, name):
            self.calls.append(name)
            if name == "Japan (MOC)":
                return [{"path": "Atlas/200 Maps/Japan (MOC).md"}]
            return []

    client = FakeClient()
    resolved = ir.resolve_target_moc_paths(actions, client)
    _must(resolved == 2, f"expected 2 resolved, got {resolved}")
    _must(actions[0]["target_moc_path"] == "Atlas/200 Maps/Japan (MOC).md",
          f"I01 target_moc_path wrong: {actions[0]['target_moc_path']}")
    _must(actions[1]["target_moc_path"] == "Atlas/200 Maps/Japan (MOC).md",
          f"I02 target_moc_path wrong: {actions[1]['target_moc_path']}")
    _must(len(client.calls) == 1, f"caching broken — expected 1 call, got {len(client.calls)}")
    # move_note untouched
    _must("target_moc_path" not in actions[2], "non-link_to_moc actions must stay untouched")

    # Degrades gracefully with None client
    actions2 = [{"id": "I01", "action": "link_to_moc", "target_moc": "X",
                 "target_moc_path": None, "source_note_title": "Y",
                 "line_to_add": "- [[Y]]"}]
    resolved2 = ir.resolve_target_moc_paths(actions2, None)
    _must(resolved2 == 0, "no client → 0 resolutions")
    _must(actions2[0]["target_moc_path"] is None,
          "no client → target_moc_path stays null")

    # Degrades gracefully when search raises
    class RaisingClient:
        def search_by_name(self, name):
            raise RuntimeError("kado down")

    actions3 = [{"id": "I01", "action": "link_to_moc", "target_moc": "X",
                 "target_moc_path": None, "source_note_title": "Y",
                 "line_to_add": "- [[Y]]"}]
    resolved3 = ir.resolve_target_moc_paths(actions3, RaisingClient())
    _must(resolved3 == 0, "raising client → 0 resolutions")
    _must(actions3[0]["target_moc_path"] is None,
          "raising client → target_moc_path stays null")

    # Tier-1: target_moc matches a create_moc in the SAME instruction set —
    # resolve from the create_moc.destination without needing Kado. Critical
    # for new MOCs that don't exist in the vault yet.
    actions4 = [
        {"id": "I01", "action": "create_moc",
         "title": "Brettspiele (MOC)",
         "source": "100 Inbox/2026-04-21_1200_brettspiele-moc.md",
         "destination": "Atlas/200 Maps/Brettspiele (MOC).md"},
        {"id": "I02", "action": "link_to_moc",
         "target_moc": "Brettspiele (MOC)", "target_moc_path": None,
         "source_note_title": "Catan", "line_to_add": "- [[Catan]]"},
    ]

    class NeverCalledClient:
        def search_by_name(self, name):
            raise AssertionError("in-set lookup must not fall through to Kado")

    resolved4 = ir.resolve_target_moc_paths(actions4, NeverCalledClient())
    _must(resolved4 == 1, f"in-set resolve → 1 resolved, got {resolved4}")
    _must(actions4[1]["target_moc_path"] == "Atlas/200 Maps/Brettspiele (MOC).md",
          f"in-set target_moc_path wrong: {actions4[1]['target_moc_path']}")

    # Tier-1 also works with client=None (no Kado at all)
    actions5 = [
        {"id": "I01", "action": "create_moc",
         "title": "New (MOC)",
         "source": "100 Inbox/x.md",
         "destination": "Atlas/200 Maps/New (MOC).md"},
        {"id": "I02", "action": "link_to_moc",
         "target_moc": "New (MOC)", "target_moc_path": None,
         "source_note_title": "Y", "line_to_add": "- [[Y]]"},
    ]
    resolved5 = ir.resolve_target_moc_paths(actions5, None)
    _must(resolved5 == 1, f"in-set resolve without client → 1, got {resolved5}")
    _must(actions5[1]["target_moc_path"] == "Atlas/200 Maps/New (MOC).md",
          "in-set resolve works without Kado")

    print("[PASS] resolve_target_moc_paths — happy, cached, graceful-degrade, in-set tier-1")


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
    test_backfill_supporting_items_parents()
    test_backfill_plus_build_actions_no_duplicate_links()
    test_resolve_target_moc_paths()
    test_resolve_section_names()

    print("\n✓ All XDD-008 Phase 1 tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
