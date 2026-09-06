#!/usr/bin/env python3
# version: 0.1.0
"""test_034_t2_3b_wire_item_key.py — spec 034 (recursive inbox discovery), T2.3b.

Three linked obligations, one identity:

  1. EMIT — `suggestions-render.build_wire_payload` must project each section's
     `item_key` (the vault-relative path, verbatim — ADR-1) onto its wire
     suggestion. `stem` stays a bare filename and stays display-only (ADR-2).
  2. CONSUME — `suggestion-parser.build_from_wire` (the ADR-026 wire-edit path)
     must bind proposed-MOC members through `item_key`, not the wire's bare
     `stem`. Two same-named notes in different subfolders otherwise bind a MOC
     member to whichever namesake happened to be written into the join dict last.
  3. AUDIT — `instructions-diff.derive_expected` must prefer the confirmed
     item's `item_key` over its bare `source_path`, so the coverage audit can
     tell two same-named items apart instead of reporting a false full pass.

CON-4 is pinned here too: `confirmed_items` feeds `render_actions.build_actions`,
which emits the instruction set Hashi consumes. Adding `item_key` upstream must
not change a single byte of that emission.

Fixtures only — no live vault, no Kado (CON-7).
"""
from __future__ import annotations

import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import jsonschema

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
WIRE_SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-wire.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


render = _load("suggestions_render_t23b", "suggestions-render.py")
parser = _load("suggestion_parser_t23b", "suggestion-parser.py")
diff = _load("instructions_diff_t23b", "instructions-diff.py")

WIRE_SCHEMA = json.loads(WIRE_SCHEMA_PATH.read_text(encoding="utf-8"))


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

def _section(sid: str, stem: str, item_key: str, title: str) -> dict:
    return {
        "id": sid,
        "stem": stem,
        "item_key": item_key,
        "actions": [
            {
                "kind": "create_atomic_note",
                "suggestion_id": sid,
                "rendered_md": f"**Suggested name:** {title}",
                "item": {
                    "title": title,
                    "template": "t_note_tomo.md",
                    "location": "Atlas/202 Notes/",
                    "tags": [],
                    "audio_peer": None,
                    "attachments": [],
                    "worthiness": 0.8,
                    "suppressed": False,
                    "force_atomic": False,
                },
                "candidate_mocs": [],
            }
        ],
    }


def _doc(sections: list[dict], proposed_mocs: list[dict] | None = None) -> dict:
    return {
        "schema_version": "1",
        "generated": "2026-09-06T10:00:00Z",
        "run_id": "2026-09-06-1000-t23b",
        "profile": "miyo",
        "source_items": len(sections),
        "conventions": {
            "parent_marker": "up::",
            "peer_marker": "related::",
            "moc_suffix": " MOC",
        },
        "sections": sections,
        "proposed_mocs": proposed_mocs or [],
        "needs_attention": [],
    }


def _wire_suggestion(sid: str, stem: str, item_key: str, title: str) -> dict:
    return {
        "id": sid,
        "stem": stem,
        "item_key": item_key,
        "title": title,
        "summary": None,
        "template": "t_note_tomo.md",
        "location": "Atlas/202 Notes/",
        "tags": [],
        "audio_peer": None,
        "attachments": [],
        "decision": "approve",
        "keep_source": True,
        "delete_source": False,
        "force_atomic": False,
        "suppressed": False,
        "worthiness": 0.8,
        "candidate_mocs": [],
    }


def _confirmed(item_id: str, source_path: str, title: str, **extra) -> dict:
    out = {
        "id": item_id,
        "source_path": source_path,
        "action": None,
        "title": title,
        "tags": [],
        "parent_moc": "",
        "parent_mocs": [],
        "keep_source": True,
    }
    out.update(extra)
    return out


def _move_note_action(action_id: str, source_inbox_item: str, title: str) -> dict:
    return {
        "id": action_id,
        "action": "move_note",
        "source": f"tomo-tmp/rendered/{action_id}.md",
        "destination": "Atlas/202 Notes/",
        "title": title,
        "rendered_file": f"{action_id}.md",
        "source_inbox_item": source_inbox_item,
        "audio_peer": None,
        "parent_mocs": [],
        "tags": [],
    }


def _instrs(actions: list[dict]) -> dict:
    return {
        "schema_version": "1",
        "type": "tomo-instructions",
        "action_count": len(actions),
        "actions": actions,
    }


def _run_diff(parsed: dict, instrs: dict) -> tuple[int, list[str], str]:
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc, obs = diff.run_diff(parsed, instrs)
    return rc, obs, buf.getvalue()


# ──────────────────────────────────────────────────────────────────────────────
# OBLIGATION 1 — the wire carries the key
# ──────────────────────────────────────────────────────────────────────────────

def test_wire_suggestion_carries_the_item_key_of_its_section():
    doc = _doc([_section("S01", "Dresden", "100 Inbox/Places/Dresden.md", "Frauenkirche")])
    payload = render.build_wire_payload(doc)

    assert len(payload["suggestions"]) == 1
    assert payload["suggestions"][0]["item_key"] == "100 Inbox/Places/Dresden.md"


def test_two_sections_sharing_a_stem_project_distinct_item_keys():
    """The whole point of ADR-1: `stem` collapses, `item_key` must not."""
    doc = _doc([
        _section("S01", "Dresden", "100 Inbox/Places/Dresden.md", "Frauenkirche"),
        _section("S02", "Dresden", "100 Inbox/Reise/Dresden.md", "A different note"),
    ])
    payload = render.build_wire_payload(doc)

    keys = [s["item_key"] for s in payload["suggestions"]]
    assert len(keys) == 2
    assert keys[0] != keys[1], (
        f"two same-named sections must project DISTINCT item_keys, got {keys!r}"
    )
    assert keys == ["100 Inbox/Places/Dresden.md", "100 Inbox/Reise/Dresden.md"]


def test_wire_with_item_key_validates_against_the_schema():
    doc = _doc([
        _section("S01", "Dresden", "100 Inbox/Places/Dresden.md", "Frauenkirche"),
        _section("S02", "Dresden", "100 Inbox/Reise/Dresden.md", "A different note"),
    ])
    payload = render.build_wire_payload(doc)
    jsonschema.validate(instance=payload, schema=WIRE_SCHEMA)


def test_stem_stays_the_bare_filename_next_to_item_key():
    """ADR-2: `stem` keeps meaning a bare filename and stays display-only."""
    doc = _doc([_section("S01", "Dresden", "100 Inbox/Places/Dresden.md", "Frauenkirche")])
    s = render.build_wire_payload(doc)["suggestions"][0]

    assert s["stem"] == "Dresden"
    assert "/" not in s["stem"]
    assert not s["stem"].endswith(".md")


# ──────────────────────────────────────────────────────────────────────────────
# OBLIGATION 2 — build_from_wire binds MOC members through item_key
# ──────────────────────────────────────────────────────────────────────────────

def test_moc_member_binds_to_the_source_that_justified_it_not_a_namesake():
    """The ADR-026 wire-edit path: a proposed MOC naming S01 as its member must
    down-link S01, not the same-named S02.

    Before this fix, `_stem_lower` collapsed both suggestions to "dresden", so
    `stem_to_id` kept only the LAST writer (S02) and the member bound to it.
    """
    wire = {
        "schema_version": "1",
        "suggestions": [
            _wire_suggestion("S01", "Dresden", "100 Inbox/Places/Dresden.md",
                             "Dresden — Frauenkirche"),
            _wire_suggestion("S02", "Dresden", "100 Inbox/Reise/Dresden.md",
                             "Dresden — a different note"),
        ],
        "proposed_mocs": [
            {
                "id": "M01",
                "topic": "Saxony",
                "name": "Saxony MOC",
                "parent": "",
                "member_ids": ["S01"],
                "tags": [],
                "reason": "cluster",
                "decision": "approve",
            }
        ],
        "daily_updates": [],
        "tag_handler_groups": [],
    }

    out = parser.build_from_wire(wire, moc_template="t_moc_tomo")
    mocs = [c for c in out["confirmed_items"] if c.get("action") == "create_moc"]
    assert len(mocs) == 1
    assert mocs[0]["supporting_items"] == "S01", (
        "the MOC member must bind to S01 — the source that justified it — not to "
        f"its namesake S02; got {mocs[0]['supporting_items']!r}"
    )


def test_build_from_wire_carries_item_key_onto_confirmed_items():
    """`item_key` is a dedicated field. `source_path` stays the display stem
    (ADR-2) — it must NOT be overwritten with the path."""
    wire = {
        "schema_version": "1",
        "suggestions": [
            _wire_suggestion("S01", "Dresden", "100 Inbox/Places/Dresden.md",
                             "Dresden — Frauenkirche"),
        ],
        "proposed_mocs": [],
        "daily_updates": [],
        "tag_handler_groups": [],
    }

    out = parser.build_from_wire(wire, moc_template="t_moc_tomo")
    item = out["confirmed_items"][0]
    assert item["item_key"] == "100 Inbox/Places/Dresden.md"
    assert item["source_path"] == "Dresden", (
        "source_path is display text and must stay the bare stem (ADR-2), got "
        f"{item['source_path']!r}"
    )


# ──────────────────────────────────────────────────────────────────────────────
# OBLIGATION 3 — derive_expected prefers item_key; the false pass closes
# ──────────────────────────────────────────────────────────────────────────────

def test_adversarial_duplicate_render_is_reported_not_a_false_pass():
    """The exact case T2.7's reviewer built and got `RESULT: OK` on.

    Both rendered move_note actions are, in truth, S01 rendered twice. S02 has
    no action anywhere and must be reported [MISSING].
    """
    confirmed = [
        _confirmed("S01", "Dresden", "Dresden — Frauenkirche",
                   item_key="100 Inbox/Places/Dresden.md"),
        _confirmed("S02", "Dresden", "Dresden — a different note",
                   item_key="100 Inbox/Reise/Dresden.md"),
    ]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    instrs = _instrs([
        _move_note_action("a1", "100 Inbox/Places/Dresden.md", "Dresden — Frauenkirche"),
        _move_note_action("a2", "100 Inbox/Places/Dresden.md", "Dresden — Frauenkirche"),
    ])

    rc, _obs, out = _run_diff(parsed, instrs)
    assert rc == 1, f"S02 has no action anywhere and must be reported:\n{out}"

    lines = {ln.strip().split()[0]: ln for ln in out.splitlines()
             if ln.strip().startswith(("S01", "S02"))}
    assert "file=[OK]" in lines["S01"], lines["S01"]
    assert "file=[MISSING]" in lines["S02"], (
        f"S02 must be reported missing, not folded into a false pass: {lines['S02']}"
    )


def test_derive_expected_prefers_item_key_over_source_path():
    confirmed = [
        _confirmed("S01", "Dresden", "Dresden — Frauenkirche",
                   item_key="100 Inbox/Places/Dresden.md"),
    ]
    expected = diff.derive_expected(
        {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    )
    assert expected["by_item"]["S01"]["item_key"] == "100 Inbox/Places/Dresden.md"


def test_derive_expected_falls_back_to_source_path_when_item_key_absent():
    """The markdown path does not mint an item_key. A confirmed item without one
    must keep reconciling exactly as it did before."""
    confirmed = [_confirmed("S01", "A.md", "A")]
    parsed = {"confirmed_items": confirmed, "daily_updates": [], "skipped": []}
    instrs = _instrs([_move_note_action("a1", "100 Inbox/A.md", "A")])

    rc, obs, out = _run_diff(parsed, instrs)
    assert rc == 0, f"a legacy item without item_key must still reconcile:\n{out}"
    assert obs == []
    assert "file=[OK]" in out


# ──────────────────────────────────────────────────────────────────────────────
# CON-4 — what Hashi receives must not change
# ──────────────────────────────────────────────────────────────────────────────

_CFG = {
    "concepts.inbox": "100 Inbox/",
    "concepts.asset": "Atlas/290 Assets/295 Attachments/",
    "concepts.calendar.granularities.daily.path": "Calendar/301 Daily/",
    "daily_log.heading": "Daily Log",
    "daily_log.heading_level": 2,
    "profile": "miyo",
}


def _manifest_entry(source_path: str) -> dict:
    return {
        "id": "S01",
        "action": None,
        "title": "Dresden",
        "source_path": source_path,
        "rendered_file": "2026-09-06_1000_dresden.md",
        "destination": "Atlas/202 Notes/",
        "parent_moc": "Saxony MOC",
        "parent_mocs": ["Saxony MOC"],
        "tags": ["topic/travel"],
        "attachments": [],
    }


def test_instruction_set_is_byte_identical_with_and_without_item_key():
    """CON-4: `item_key` on confirmed_items is internal. The instruction set
    handed to Hashi — source_stem / target_stem and every other field — must be
    unchanged for an input that involves no collision."""
    from lib.render_actions import build_actions  # noqa: PLC0415 — script-dir import

    base = _confirmed("S01", "dresden.md", "Dresden",
                      parent_moc="Saxony MOC", parent_mocs=["Saxony MOC"],
                      keep_source=False, destination="Atlas/202 Notes/",
                      candidate_mocs=[])
    manifest = [_manifest_entry("dresden.md")]

    without, _ = build_actions(manifest, [dict(base)], [], [], dict(_CFG))
    keyed = dict(base, item_key="100 Inbox/dresden.md")
    with_key, _ = build_actions(manifest, [keyed], [], [], dict(_CFG))

    assert json.dumps(with_key, sort_keys=True) == json.dumps(without, sort_keys=True), (
        "adding item_key to confirmed_items changed the emitted instruction set — "
        "that is a cross-repo contract break with Hashi"
    )


def test_emitted_stems_stay_bare_filenames():
    """A path must never leak into an emitted stem field (CON-4)."""
    from lib.render_actions import build_actions  # noqa: PLC0415 — script-dir import

    confirmed = [_confirmed("S01", "dresden.md", "Dresden",
                            parent_moc="Saxony MOC", parent_mocs=["Saxony MOC"],
                            keep_source=False, destination="Atlas/202 Notes/",
                            candidate_mocs=[], item_key="100 Inbox/Places/dresden.md")]
    daily = [{
        "date": "2026-09-06",
        "daily_note_path": "Calendar/301 Daily/2026-09-06.md",
        "trackers": [],
        "log_entries": [{
            "accepted": True, "content": "Wrote about Dresden",
            "source_stem": "100 Inbox/Places/dresden.md",
        }],
        "log_links": [{
            "accepted": True, "target_stem": "100 Inbox/Places/dresden.md",
        }],
    }]

    manifest = [_manifest_entry("dresden.md")]
    actions, _ = build_actions(manifest, confirmed, daily, [], dict(_CFG))

    for a in actions:
        for field in ("source_stem", "target_stem"):
            value = a.get(field)
            if value:
                assert "/" not in value, f"{a['action']}.{field} leaked a path: {value!r}"
