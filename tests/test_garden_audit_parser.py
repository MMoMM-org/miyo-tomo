"""Tests for garden-audit-parser.py — Pass-2 reader (markdown authoritative + wire override).

The parser is a pure reader: markdown report (+ optional edited wire) → a
{"confirmed_items": [...]} envelope of SEMANTIC items (garden_check /
garden_action), NOT pre-built actions. render_actions.build_garden_audit_actions
turns confirmed_items into Hashi actions.

Covers:
  load_changed_wire — absent / bad / wrong-version / unchanged → None; edited → wire.
  build_from_wire   — confirmed_items per fixable+selected finding; advisory /
                      deselected → none.
  build_from_markdown — parse the rendered report's structural comments +
                      checkboxes + Replace/Repoint fields → confirmed_items.
  round-trip        — render(doc) → build_from_markdown → confirmed_items match.
  end-to-end        — approved markdown → build_from_markdown →
                      build_garden_audit_actions → correct Hashi actions.
"""
# version: 0.3.0
import importlib.util
import json
import pathlib
import sys

# ---------------------------------------------------------------------------
# Load the hyphen-named modules under test
# ---------------------------------------------------------------------------
_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS_DIR = _ROOT / "tomo" / "scripts"
_PARSER = _SCRIPTS_DIR / "garden-audit-parser.py"
_RENDER = _SCRIPTS_DIR / "garden-audit-render.py"

sys.path.insert(0, str(_SCRIPTS_DIR))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gap = _load("garden_audit_parser", _PARSER)
gar = _load("garden_audit_render", _RENDER)

from lib.render_actions import build_garden_audit_actions  # noqa: E402

load_changed_wire = gap.load_changed_wire
build_from_wire = gap.build_from_wire
build_from_markdown = gap.build_from_markdown

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
        "emit_digest": "sha256:" + "a" * 64,  # placeholder — overridden for digest tests
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
        wire = _make_real_wire([])
        p = tmp_path / "wire.json"
        _write_wire(p, wire)
        assert load_changed_wire(str(p)) is None

    def test_edited_wire_returns_wire(self, tmp_path):
        wire = _make_real_wire([_unparented()])
        wire["findings"][0]["decision"]["selected"] = False
        p = tmp_path / "wire.json"
        _write_wire(p, wire)
        result = load_changed_wire(str(p))
        assert result is not None
        assert result["schema_version"] == "1"


# ---------------------------------------------------------------------------
# build_from_wire tests (now emits confirmed_items)
# ---------------------------------------------------------------------------

class TestBuildFromWireEmptyFindings:
    def test_empty_findings_empty_items(self):
        assert build_from_wire(_make_wire([]))["confirmed_items"] == []

    def test_returns_run_metadata(self):
        result = build_from_wire(_make_wire([]))
        assert result["run_id"] == "run-test-001"
        assert result["generated"] == "2026-07-20T10:00:00Z"


class TestBuildFromWireUnparented:
    def test_selected_unparented_emits_file_note(self):
        items = build_from_wire(_make_wire([_unparented(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        c = items[0]
        assert c["garden_action"] == "file_note"
        assert c["target_moc"] == "Writing MOC"
        assert c["target_moc_path"] == "MOCs/Writing MOC.md"
        assert c["path"] == "Notes/Orphan.md"

    def test_unselected_unparented_emits_no_item(self):
        assert build_from_wire(_make_wire([_unparented(selected=False)]))["confirmed_items"] == []

    def test_selected_unparented_no_candidate_mocs_emits_no_item(self):
        finding = _wire_finding(
            "F01", "unparented", "structure", True,
            "Notes/Orphan.md", "Orphan",
            {"candidate_mocs": []},
            decision={"selected": True, "action": "link_to_moc"},
        )
        assert build_from_wire(_make_wire([finding]))["confirmed_items"] == []


class TestBuildFromWireOrphan:
    def test_selected_orphan_emits_file_note(self):
        items = build_from_wire(_make_wire([_orphan(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        assert items[0]["garden_action"] == "file_note"

    def test_unselected_orphan_emits_no_item(self):
        assert build_from_wire(_make_wire([_orphan(selected=False)]))["confirmed_items"] == []


class TestBuildFromWireBrokenUp:
    def test_selected_broken_up_repoint_emits_add_relationship(self):
        items = build_from_wire(_make_wire([_broken_up_repoint(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        assert items[0]["garden_action"] == "add_relationship"
        assert items[0]["up_line"] == "up:: [[Old MOC]]"

    def test_selected_broken_up_removal_emits_edit_note_text(self):
        items = build_from_wire(_make_wire([_broken_up_removal(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        c = items[0]
        assert c["garden_action"] == "edit_note_text"
        assert c["path"] == "Notes/Broken.md"
        assert "up::" in c["match"]
        assert c["replace"] == ""

    def test_unselected_broken_up_emits_no_item(self):
        assert build_from_wire(_make_wire([_broken_up_removal(selected=False)]))["confirmed_items"] == []


class TestBuildFromWireDeadLink:
    def test_selected_dead_link_emits_edit_note_text(self):
        items = build_from_wire(_make_wire([_dead_link(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        c = items[0]
        assert c["garden_action"] == "edit_note_text"
        assert c["path"] == "Notes/Source.md"
        assert c["match"] == "[[Missing Note]]"
        assert c["replace"] == ""

    def test_unselected_dead_link_emits_no_item(self):
        assert build_from_wire(_make_wire([_dead_link(selected=False)]))["confirmed_items"] == []

    def test_dead_link_occurrence_is_all(self):
        c = build_from_wire(_make_wire([_dead_link(selected=True)]))["confirmed_items"][0]
        assert c["occurrence"] == "all"

    def test_dead_link_with_replace_target_uses_replace_from_decision(self):
        c = build_from_wire(_make_wire([_dead_link(selected=True, replace="[[New Note]]")]))["confirmed_items"][0]
        assert c["replace"] == "[[New Note]]"


class TestBuildFromWireAdvisory:
    def test_duplicate_stem_emits_no_item(self):
        assert build_from_wire(_make_wire([_duplicate_stem()]))["confirmed_items"] == []

    def test_stale_moc_emits_no_item(self):
        assert build_from_wire(_make_wire([_stale_moc()]))["confirmed_items"] == []


class TestBuildFromWireMixed:
    def test_mixed_selected_and_skipped(self):
        findings = [
            _unparented("F01", selected=True),
            _dead_link("F02", selected=False),
            _duplicate_stem("F03"),
        ]
        items = build_from_wire(_make_wire(findings))["confirmed_items"]
        assert [c["id"] for c in items] == ["F01"]


class TestBrokenUpListTarget:
    """Cache up:: is a multi-value list — must reconstruct the real line."""

    def _list_removal(self, fid="F01"):
        return _wire_finding(
            fid, "broken_up", "integrity", True,
            "Notes/Broken.md", "Broken",
            {"up_target": ["020 Active MOC"]},
            decision={"selected": True, "action": "edit_note_text"},
        )

    def test_removal_match_reconstructs_frontmatter_line(self):
        c = build_from_wire(_make_wire([self._list_removal()]))["confirmed_items"][0]
        assert c["match"] == "up:: [[020 Active MOC]]"
        assert "[[[" not in c["match"]

    def test_multi_target_up_list_joins_all(self):
        f = self._list_removal()
        f["detail"]["up_target"] = ["020 Active MOC", "030 Reference MOC"]
        c = build_from_wire(_make_wire([f]))["confirmed_items"][0]
        assert c["match"] == "up:: [[020 Active MOC]], [[030 Reference MOC]]"


# ---------------------------------------------------------------------------
# Markdown render-doc fixtures (drives render → parse round-trip)
# ---------------------------------------------------------------------------

def _doc_finding_unparented(fid="F01"):
    return {
        "id": fid, "check": "unparented", "tier": "structure", "fixable": True,
        "target": {"path": "Notes/Orphan Note.md", "stem": "Orphan Note"},
        "detail": {"candidate_mocs": [{"target_moc": "MOCs/Writing MOC.md", "score": 0.8}]},
        "decision": {"selected": True, "action": "link_to_moc"},
    }


def _doc_finding_broken_up_removal(fid="F02"):
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Broken Note.md", "stem": "Broken Note"},
        "detail": {"up_target": "Deleted MOC"},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _doc_finding_broken_up_repoint(fid="F03"):
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Repoint Note.md", "stem": "Repoint Note"},
        "detail": {"up_target": "Old MOC"},
        "decision": {"selected": True, "action": "add_relationship"},
    }


def _doc_finding_dead_link(fid="F04"):
    return {
        "id": fid, "check": "dead_link", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Source Note.md", "stem": "Source Note"},
        "detail": {"dead_target": "Missing Note", "count": 2},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _doc_finding_duplicate(fid="F05"):
    return {
        "id": fid, "check": "duplicate_stem", "tier": "advisory", "fixable": False,
        "target": {"path": "Notes/Dup.md", "stem": "Dup"},
        "detail": {"dupes": ["Notes/Dup.md", "Archive/Dup.md"]},
    }


def _make_doc(findings):
    return {
        "run_id": "run-rt-001", "generated": "2026-07-20T12:00:00Z", "profile": "miyo",
        "findings": findings, "skipped_checks": [], "skipped_checks_reason": "",
        "reappeared_exclusions": [],
    }


def _full_report(doc):
    """Render the full markdown report (frontmatter + body) as one string."""
    return "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)


# ---------------------------------------------------------------------------
# Round-trip: render(doc) → build_from_markdown → confirmed_items
# ---------------------------------------------------------------------------

class TestMarkdownRoundTrip:
    def test_unparented_round_trips_to_file_note(self):
        md = _full_report(_make_doc([_doc_finding_unparented("F01")]))
        items = build_from_markdown(md)["confirmed_items"]
        assert len(items) == 1
        c = items[0]
        assert c["id"] == "F01"
        assert c["garden_action"] == "file_note"
        assert c["path"] == "Notes/Orphan Note.md"
        assert c["stem"] == "Orphan Note"
        assert c["target_moc"] == "Writing MOC"
        assert c["target_moc_path"] == "MOCs/Writing MOC.md"

    def test_broken_up_removal_round_trips(self):
        md = _full_report(_make_doc([_doc_finding_broken_up_removal("F02")]))
        c = build_from_markdown(md)["confirmed_items"][0]
        assert c["garden_action"] == "edit_note_text"
        assert c["path"] == "Notes/Broken Note.md"
        assert c["match"] == "up:: [[Deleted MOC]]"
        assert c["replace"] == ""
        assert c["occurrence"] == "first"

    def test_broken_up_removal_list_up_target_round_trips(self):
        # Cache up:: is a multi-value list — the markdown path (render → parse)
        # must reconstruct the exact multi-target frontmatter line, never a list
        # repr. Previously only build_from_wire covered the list case.
        f = _doc_finding_broken_up_removal("F02")
        f["detail"]["up_target"] = ["020 Active MOC", "030 Reference MOC"]
        md = _full_report(_make_doc([f]))
        c = build_from_markdown(md)["confirmed_items"][0]
        assert c["garden_action"] == "edit_note_text"
        assert c["match"] == "up:: [[020 Active MOC]], [[030 Reference MOC]]"
        assert "[[[" not in c["match"] and "['" not in c["match"]

    def test_dead_link_removal_round_trips_empty_replace(self):
        # User leaves Replace with: [[]] empty → remove.
        md = _full_report(_make_doc([_doc_finding_dead_link("F04")]))
        c = build_from_markdown(md)["confirmed_items"][0]
        assert c["garden_action"] == "edit_note_text"
        assert c["match"] == "[[Missing Note]]"
        assert c["replace"] == ""
        assert c["occurrence"] == "all"

    def test_advisory_finding_produces_no_item(self):
        md = _full_report(_make_doc([_doc_finding_duplicate("F05")]))
        assert build_from_markdown(md)["confirmed_items"] == []

    def test_frontmatter_run_id_recovered(self):
        md = _full_report(_make_doc([_doc_finding_unparented("F01")]))
        assert build_from_markdown(md)["run_id"] == "run-rt-001"

    def test_unticked_apply_skips_item(self):
        # Simulate the user unticking Apply on a rendered dead_link block.
        md = _full_report(_make_doc([_doc_finding_dead_link("F04")]))
        md = md.replace("- [x] Apply", "- [ ] Apply")
        assert build_from_markdown(md)["confirmed_items"] == []

    def test_user_fills_replace_target_repoints(self):
        md = _full_report(_make_doc([_doc_finding_dead_link("F04")]))
        md = md.replace("**Replace with:** [[]]", "**Replace with:** [[New Target]]")
        c = build_from_markdown(md)["confirmed_items"][0]
        assert c["replace"] == "[[New Target]]"

    def test_user_fills_repoint_target_adds_relationship(self):
        md = _full_report(_make_doc([_doc_finding_broken_up_repoint("F03")]))
        md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[Chosen MOC]]")
        c = build_from_markdown(md)["confirmed_items"][0]
        assert c["garden_action"] == "add_relationship"
        assert c["up_line"] == "up:: [[Chosen MOC]]"

    def test_empty_repoint_falls_back_to_removal(self):
        # Repoint block, user leaves [[]] empty → removal (edit_note_text).
        md = _full_report(_make_doc([_doc_finding_broken_up_repoint("F03")]))
        c = build_from_markdown(md)["confirmed_items"][0]
        assert c["garden_action"] == "edit_note_text"
        assert c["match"] == "up:: [[Old MOC]]"
        assert c["replace"] == ""


# ---------------------------------------------------------------------------
# END-TO-END (F6 fix): approved markdown → confirmed_items → actions
# ---------------------------------------------------------------------------

class TestEndToEndApprovedReportToActions:
    """The full vertical: an approved report renders into Hashi actions.

    This MUST fail against a no-op/empty build_from_markdown or a
    build_garden_audit_actions that drops item kinds.
    """

    def _approved_md(self):
        doc = _make_doc([
            _doc_finding_dead_link("F01"),         # → edit_note_text (remove)
            _doc_finding_broken_up_removal("F02"),  # → edit_note_text (up:: remove)
            _doc_finding_broken_up_repoint("F03"),  # → add_relationship (repoint)
            _doc_finding_unparented("F04"),         # → link_to_moc + add_relationship
            _doc_finding_duplicate("F05"),          # advisory → nothing
        ])
        md = _full_report(doc)
        # User fills the repoint target so F03 becomes a repoint.
        md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[Correct MOC]]")
        return md

    def test_confirmed_items_cover_every_fixable_finding(self):
        items = build_from_markdown(self._approved_md())["confirmed_items"]
        ids = {c["id"] for c in items}
        assert ids == {"F01", "F02", "F03", "F04"}  # F05 advisory excluded

    def test_actions_contain_edit_note_text_for_dead_link_and_broken_up(self):
        items = build_from_markdown(self._approved_md())["confirmed_items"]
        actions = build_garden_audit_actions(items)
        edits = [a for a in actions if a["action"] == "edit_note_text"]
        # dead_link removal + broken_up removal = 2 edit_note_text
        assert len(edits) == 2
        matches = {a["match"] for a in edits}
        assert "[[Missing Note]]" in matches
        assert "up:: [[Deleted MOC]]" in matches
        for a in edits:
            assert a["replace"] == ""

    def test_actions_contain_add_relationship_for_repoint_and_filing(self):
        items = build_from_markdown(self._approved_md())["confirmed_items"]
        actions = build_garden_audit_actions(items)
        rels = [a for a in actions if a["action"] == "add_relationship"]
        # repoint (F03) + filing up:: (F04) = 2 add_relationship
        assert len(rels) == 2
        lines = {a["line"] for a in rels}
        assert "up:: [[Correct MOC]]" in lines
        assert "up:: [[Writing MOC]]" in lines
        for a in rels:
            assert a["marker"] == "up::"

    def test_actions_contain_link_to_moc_for_filing(self):
        items = build_from_markdown(self._approved_md())["confirmed_items"]
        actions = build_garden_audit_actions(items)
        links = [a for a in actions if a["action"] == "link_to_moc"]
        assert len(links) == 1
        assert links[0]["target_moc"] == "Writing MOC"
        assert links[0]["line_to_add"] == "- [[Orphan Note]]"

    def test_all_actions_stamped_applied_false(self):
        items = build_from_markdown(self._approved_md())["confirmed_items"]
        actions = build_garden_audit_actions(items)
        # F01 edit + F02 edit + F03 add_rel + F04 (link_to_moc + add_rel) = 5.
        # Exact count keeps the applied-flag loop reachable-by-contract.
        assert len(actions) == 5
        for a in actions:
            assert a["applied"] is False

    def test_edit_note_text_path_is_the_note_path(self):
        items = build_from_markdown(self._approved_md())["confirmed_items"]
        actions = build_garden_audit_actions(items)
        paths = {a["path"] for a in actions if a["action"] == "edit_note_text"}
        assert paths == {"Notes/Source Note.md", "Notes/Broken Note.md"}

    def test_empty_confirmed_items_yields_no_actions(self):
        # Falsifies a no-op impl that always returns actions.
        assert build_garden_audit_actions([]) == []


# ---------------------------------------------------------------------------
# W1: build_garden_audit_actions preserves confirmed[] input order
# ---------------------------------------------------------------------------

class TestActionOrderPreserved:
    """Action IDs must track confirmed[] input order. A file_note BEFORE an
    edit_note_text must yield link_to_moc(1), add_relationship(2), edit(3) —
    ascending IDs matching input order. A two-pass impl (edits first) would
    reorder and fail this."""

    def test_file_note_before_edit_note_text_keeps_input_order(self):
        confirmed = [
            {
                "id": "F01", "garden_check": "unparented", "garden_action": "file_note",
                "path": "Notes/Orphan.md", "stem": "Orphan",
                "target_moc": "Writing MOC", "target_moc_path": "MOCs/Writing MOC.md",
            },
            {
                "id": "F02", "garden_check": "dead_link", "garden_action": "edit_note_text",
                "path": "Notes/Source.md", "stem": "Source",
                "match": "[[Missing]]", "replace": "", "occurrence": "all",
            },
        ]
        actions = build_garden_audit_actions(confirmed)
        kinds = [a["action"] for a in actions]
        assert kinds == ["link_to_moc", "add_relationship", "edit_note_text"]
        # IDs ascend in emission order (F01's two actions before F02's edit).
        ids = [a["id"] for a in actions]
        assert ids == sorted(ids)
        # The edit_note_text (F02, last input) carries the highest id.
        assert actions[-1]["action"] == "edit_note_text"
        assert actions[-1]["id"] == max(ids)
