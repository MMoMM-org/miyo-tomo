"""Tests for garden-audit-parser.py — Pass-2 rebuild-from-wire.

Covers:
  load_changed_wire:
    - absent path → None
    - file not found → None (warn)
    - invalid JSON → None (warn)
    - schema_version != "1" → None (warn)
    - unchanged wire (digest matches) → None (markdown authoritative)
    - edited wire (digest mismatch) → returns wire dict

  build_from_wire:
    - unparented/orphan (selected=True) → link_to_moc + add_relationship up::
    - broken_up action="add_relationship" (repoint, selected=True) → add_relationship
    - broken_up action="edit_note_text" (removal, selected=True) → edit_note_text
    - dead_link (selected=True) → edit_note_text
    - advisory finding (duplicate_stem, stale_moc) → NO action
    - selected=False → no action (skipped)
    - mixed: only selected fixable findings produce actions
    - action ID counter increments across multiple findings
    - empty findings → empty actions list
"""
# version: 0.1.0
import importlib.util
import json
import pathlib
import sys

# ---------------------------------------------------------------------------
# Load the hyphen-named module under test
# ---------------------------------------------------------------------------
_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS_DIR = _ROOT / "tomo" / "scripts"
_SCRIPT = _SCRIPTS_DIR / "garden-audit-parser.py"

sys.path.insert(0, str(_SCRIPTS_DIR))

spec = importlib.util.spec_from_file_location("garden_audit_parser", _SCRIPT)
gap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gap)

load_changed_wire = gap.load_changed_wire
build_from_wire = gap.build_from_wire

# ---------------------------------------------------------------------------
# Helpers to build minimal valid wire payloads
# ---------------------------------------------------------------------------

def _wire_finding(fid, check, tier, fixable, path, stem, detail, decision=None):
    f = {
        "id": fid,
        "check": check,
        "tier": tier,
        "fixable": fixable,
        "target": {"path": path, "stem": stem},
        "detail": detail,
    }
    if decision is not None:
        f["decision"] = decision
    return f


def _make_wire(findings, schema_version="1", run_id="run-test-001",
               generated="2026-07-20T10:00:00Z", profile="miyo"):
    """Build a wire dict WITHOUT computing emit_digest (for raw shape tests)."""
    return {
        "schema_version": schema_version,
        "run_id": run_id,
        "generated": generated,
        "profile": profile,
        "findings": findings,
        "emit_digest": "sha256:" + "a" * 64,  # placeholder — tests override for digest tests
    }


def _make_real_wire(findings, **kwargs):
    """Build a wire with a correct emit_digest (for digest-based tests)."""
    from lib.render_md import compute_payload_digest
    wire = _make_wire(findings, **kwargs)
    wire["emit_digest"] = compute_payload_digest(wire)
    return wire


def _write_wire(path, wire):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(wire, f, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Convenience finding builders
# ---------------------------------------------------------------------------

def _unparented(fid="F01", selected=True):
    return _wire_finding(
        fid, "unparented", "structure", True,
        "Notes/Orphan.md", "Orphan",
        {"candidate_mocs": [{"target_moc": "MOCs/Writing MOC.md", "score": 0.8}]},
        decision={"selected": selected, "action": "link_to_moc"},
    )


def _orphan(fid="F01", selected=True):
    return _wire_finding(
        fid, "orphan", "structure", True,
        "Notes/Orphan2.md", "Orphan2",
        {"candidate_mocs": [{"target_moc": "MOCs/Code MOC.md", "score": 0.7}]},
        decision={"selected": selected, "action": "link_to_moc"},
    )


def _broken_up_repoint(fid="F01", selected=True):
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Old MOC"},
        decision={"selected": selected, "action": "add_relationship"},
    )


def _broken_up_removal(fid="F01", selected=True):
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Deleted MOC"},
        decision={"selected": selected, "action": "edit_note_text"},
    )


def _dead_link(fid="F01", selected=True, replace=None):
    """Build a dead_link wire finding.

    dead_target is the raw wikilink stem (no brackets) — the scan orchestrator
    stores the graph_audit target verbatim. The parser wraps it as [[stem]] when
    building the edit_note_text match field. decision.replace carries the optional
    replacement target (editable by the user in the wire); absent/empty = remove.
    """
    decision = {"selected": selected, "action": "edit_note_text"}
    if replace is not None:
        decision["replace"] = replace
    return _wire_finding(
        fid, "dead_link", "integrity", True,
        "Notes/Source.md", "Source",
        {"dead_target": "Missing Note", "count": 1},
        decision=decision,
    )


def _duplicate_stem(fid="F01"):
    return _wire_finding(
        fid, "duplicate_stem", "advisory", False,
        "Notes/Dup.md", "Dup",
        {"dupes": ["Notes/Dup.md", "Archive/Dup.md"]},
    )


def _stale_moc(fid="F01"):
    return _wire_finding(
        fid, "stale_moc", "advisory", False,
        "MOCs/Old MOC.md", "Old MOC",
        {"mtime": "2026-01-01T00:00:00Z"},
    )


# ---------------------------------------------------------------------------
# load_changed_wire tests
# ---------------------------------------------------------------------------

class TestLoadChangedWire:
    def test_none_path_returns_none(self):
        assert load_changed_wire(None) is None

    def test_missing_file_returns_none(self, tmp_path):
        assert load_changed_wire(str(tmp_path / "nonexistent.json")) is None

    def test_invalid_json_returns_none(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json", encoding="utf-8")
        assert load_changed_wire(str(p)) is None

    def test_wrong_schema_version_returns_none(self, tmp_path):
        wire = _make_real_wire([])
        wire["schema_version"] = "2"
        wire["emit_digest"] = "sha256:" + "b" * 64  # force "edited"
        p = tmp_path / "wire.json"
        _write_wire(p, wire)
        assert load_changed_wire(str(p)) is None

    def test_unchanged_wire_returns_none(self, tmp_path):
        # Digest matches → markdown is authoritative → None
        wire = _make_real_wire([])
        p = tmp_path / "wire.json"
        _write_wire(p, wire)
        assert load_changed_wire(str(p)) is None

    def test_edited_wire_returns_wire(self, tmp_path):
        # Digest mismatch → user edited → return wire
        wire = _make_real_wire([_unparented()])
        # Simulate user edit: flip selected without updating digest
        wire["findings"][0]["decision"]["selected"] = False
        p = tmp_path / "wire.json"
        _write_wire(p, wire)
        result = load_changed_wire(str(p))
        assert result is not None
        assert result["schema_version"] == "1"


# ---------------------------------------------------------------------------
# build_from_wire tests
# ---------------------------------------------------------------------------

class TestBuildFromWireEmptyFindings:
    def test_empty_findings_empty_actions(self):
        wire = _make_wire([])
        result = build_from_wire(wire)
        assert result["actions"] == []

    def test_returns_run_metadata(self):
        wire = _make_wire([])
        result = build_from_wire(wire)
        assert result["run_id"] == "run-test-001"
        assert result["generated"] == "2026-07-20T10:00:00Z"


class TestBuildFromWireUnparented:
    def test_selected_unparented_emits_link_to_moc(self):
        wire = _make_wire([_unparented(selected=True)])
        result = build_from_wire(wire)
        actions = result["actions"]
        link_actions = [a for a in actions if a["action"] == "link_to_moc"]
        assert len(link_actions) == 1
        assert "Writing MOC" in link_actions[0]["target_moc"]

    def test_selected_unparented_emits_add_relationship_up(self):
        wire = _make_wire([_unparented(selected=True)])
        result = build_from_wire(wire)
        actions = result["actions"]
        rel_actions = [a for a in actions if a["action"] == "add_relationship"]
        assert len(rel_actions) == 1
        assert rel_actions[0]["marker"] == "up::"
        assert "Writing MOC" in rel_actions[0]["line"]

    def test_unselected_unparented_emits_no_action(self):
        wire = _make_wire([_unparented(selected=False)])
        result = build_from_wire(wire)
        assert result["actions"] == []

    def test_selected_unparented_no_candidate_mocs_emits_no_action(self):
        # When orphan_link found no MOC above threshold, candidate_mocs=[] —
        # we cannot file the note, so skip+warn rather than emit a broken action.
        finding = _wire_finding(
            "F01", "unparented", "structure", True,
            "Notes/Orphan.md", "Orphan",
            {"candidate_mocs": []},
            decision={"selected": True, "action": "link_to_moc"},
        )
        wire = _make_wire([finding])
        result = build_from_wire(wire)
        assert result["actions"] == [], (
            "empty candidate_mocs must produce no actions (skip+warn), "
            "not a broken link_to_moc with target_moc=''"
        )


class TestBuildFromWireOrphan:
    def test_selected_orphan_emits_link_to_moc_and_add_rel(self):
        wire = _make_wire([_orphan(selected=True)])
        result = build_from_wire(wire)
        actions = result["actions"]
        assert any(a["action"] == "link_to_moc" for a in actions)
        assert any(a["action"] == "add_relationship" and a["marker"] == "up::" for a in actions)

    def test_unselected_orphan_emits_no_action(self):
        wire = _make_wire([_orphan(selected=False)])
        result = build_from_wire(wire)
        assert result["actions"] == []

    def test_selected_orphan_no_candidate_mocs_emits_no_action(self):
        # Same skip+warn logic as unparented with empty candidate_mocs.
        finding = _wire_finding(
            "F01", "orphan", "structure", True,
            "Notes/Orphan2.md", "Orphan2",
            {"candidate_mocs": []},
            decision={"selected": True, "action": "link_to_moc"},
        )
        wire = _make_wire([finding])
        result = build_from_wire(wire)
        assert result["actions"] == []


class TestBuildFromWireBrokenUp:
    def test_selected_broken_up_repoint_emits_add_relationship(self):
        wire = _make_wire([_broken_up_repoint(selected=True)])
        result = build_from_wire(wire)
        actions = result["actions"]
        assert len(actions) == 1
        assert actions[0]["action"] == "add_relationship"
        assert actions[0]["marker"] == "up::"

    def test_selected_broken_up_removal_emits_edit_note_text(self):
        wire = _make_wire([_broken_up_removal(selected=True)])
        result = build_from_wire(wire)
        actions = result["actions"]
        assert len(actions) == 1
        assert actions[0]["action"] == "edit_note_text"
        assert actions[0]["path"] == "Notes/Broken.md"
        # match should target the up:: line with the broken stem
        assert "up::" in actions[0]["match"]
        assert actions[0]["replace"] == ""

    def test_unselected_broken_up_emits_no_action(self):
        wire = _make_wire([_broken_up_removal(selected=False)])
        result = build_from_wire(wire)
        assert result["actions"] == []


class TestBuildFromWireDeadLink:
    def test_selected_dead_link_emits_edit_note_text(self):
        wire = _make_wire([_dead_link(selected=True)])
        result = build_from_wire(wire)
        actions = result["actions"]
        assert len(actions) == 1
        a = actions[0]
        assert a["action"] == "edit_note_text"
        assert a["path"] == "Notes/Source.md"
        # match wraps dead_target in [[ ]] — dead_target is raw stem from graph_audit
        assert a["match"] == "[[Missing Note]]"
        # default replace="" (remove when decision.replace absent or empty)
        assert a["replace"] == ""

    def test_unselected_dead_link_emits_no_action(self):
        wire = _make_wire([_dead_link(selected=False)])
        result = build_from_wire(wire)
        assert result["actions"] == []

    def test_dead_link_match_wraps_dead_target_in_brackets(self):
        # dead_target is raw stem; parser must wrap in [[]] for wikilink match
        wire = _make_wire([_dead_link(selected=True)])
        result = build_from_wire(wire)
        a = result["actions"][0]
        assert a["match"].startswith("[[") and a["match"].endswith("]]")

    def test_dead_link_occurrence_is_all(self):
        # occurrence="all" removes every instance of the dead wikilink
        wire = _make_wire([_dead_link(selected=True)])
        result = build_from_wire(wire)
        a = result["actions"][0]
        assert a["occurrence"] == "all"

    def test_dead_link_with_replace_target_uses_replace_from_decision(self):
        # User sets decision.replace="[[New Note]]" → fix replaces the dead link
        finding = _dead_link(selected=True, replace="[[New Note]]")
        wire = _make_wire([finding])
        result = build_from_wire(wire)
        a = result["actions"][0]
        assert a["replace"] == "[[New Note]]"

    def test_dead_link_with_empty_replace_removes_link(self):
        # decision.replace="" → replace="" in action (remove intent)
        finding = _dead_link(selected=True, replace="")
        wire = _make_wire([finding])
        result = build_from_wire(wire)
        a = result["actions"][0]
        assert a["replace"] == ""


class TestBuildFromWireAdvisory:
    def test_duplicate_stem_emits_no_action(self):
        wire = _make_wire([_duplicate_stem()])
        result = build_from_wire(wire)
        assert result["actions"] == []

    def test_stale_moc_emits_no_action(self):
        wire = _make_wire([_stale_moc()])
        result = build_from_wire(wire)
        assert result["actions"] == []

    def test_all_advisory_wire_empty_actions(self):
        wire = _make_wire([_duplicate_stem("F01"), _stale_moc("F02")])
        result = build_from_wire(wire)
        assert result["actions"] == []


class TestBuildFromWireMixed:
    def test_mixed_selected_and_skipped(self):
        findings = [
            _unparented("F01", selected=True),
            _dead_link("F02", selected=False),   # skipped by user
            _duplicate_stem("F03"),               # advisory, no action
        ]
        wire = _make_wire(findings)
        result = build_from_wire(wire)
        actions = result["actions"]
        # Only F01 produces actions (link_to_moc + add_relationship)
        assert len(actions) == 2
        assert not any(a.get("action") == "edit_note_text" for a in actions)

    def test_action_ids_increment(self):
        findings = [
            _unparented("F01", selected=True),   # → link_to_moc + add_rel = 2 actions
            _dead_link("F02", selected=True),     # → edit_note_text = 1 action
        ]
        wire = _make_wire(findings)
        result = build_from_wire(wire)
        ids = [a["id"] for a in result["actions"]]
        # IDs must be distinct and monotonically increasing
        assert len(ids) == len(set(ids))
        assert ids == sorted(ids)


class TestAppliedStamping:
    """All action builders must emit applied=False, not None.

    garden-audit-parser bypasses instruction-render's build_actions() which
    stamps applied=False as its final step. The parser must therefore stamp
    applied=False itself on every action it emits (ADR-4 / ADR-026 contract).
    """

    def test_filing_actions_have_applied_false(self):
        wire = _make_wire([_unparented(selected=True)])
        result = build_from_wire(wire)
        for a in result["actions"]:
            assert a["applied"] is False, f"action {a['id']} has applied={a['applied']!r}, expected False"

    def test_broken_up_repoint_has_applied_false(self):
        wire = _make_wire([_broken_up_repoint(selected=True)])
        result = build_from_wire(wire)
        for a in result["actions"]:
            assert a["applied"] is False, f"action {a['id']} has applied={a['applied']!r}, expected False"

    def test_broken_up_removal_has_applied_false(self):
        wire = _make_wire([_broken_up_removal(selected=True)])
        result = build_from_wire(wire)
        for a in result["actions"]:
            assert a["applied"] is False, f"action {a['id']} has applied={a['applied']!r}, expected False"

    def test_dead_link_action_has_applied_false(self):
        wire = _make_wire([_dead_link(selected=True)])
        result = build_from_wire(wire)
        for a in result["actions"]:
            assert a["applied"] is False, f"action {a['id']} has applied={a['applied']!r}, expected False"

    def test_all_actions_in_mixed_wire_have_applied_false(self):
        findings = [
            _unparented("F01", selected=True),
            _broken_up_removal("F02", selected=True),
            _dead_link("F03", selected=True),
        ]
        wire = _make_wire(findings)
        result = build_from_wire(wire)
        assert len(result["actions"]) > 0
        for a in result["actions"]:
            assert a["applied"] is False, f"action {a['id']} has applied={a['applied']!r}, expected False"

    def test_applied_is_not_none(self):
        # Explicit regression: applied=None is wrong (None is falsy but not False)
        wire = _make_wire([_unparented(selected=True)])
        result = build_from_wire(wire)
        for a in result["actions"]:
            assert a["applied"] is not None, f"action {a['id']} has applied=None — must be False"
