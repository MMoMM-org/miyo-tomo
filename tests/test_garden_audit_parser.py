"""Tests for garden-audit-parser.py — Pass-2 reader (two-artifact split, spec 030).

The parser joins the markdown report's DECISIONS to the wire's STRUCTURE by F-id
→ a {"confirmed_items": [...]} envelope of SEMANTIC items (garden_check /
garden_action). render_actions.build_garden_audit_actions turns confirmed_items
into Hashi actions.

Covers:
  load_changed_wire — absent / bad / wrong-version / unchanged → None; edited → wire.
  build_from_wire   — confirmed_items per fixable+selected finding (Hashi-edited
                      path); advisory / deselected → none.
  build_from_report — join wire structure (path/detail/candidate_mocs) to markdown
                      decisions (Apply ticks + Repoint/Replace) by F-id.
  round-trip        — render(doc)+build_wire_payload(doc) → build_from_report →
                      confirmed_items have wire PATH + markdown decisions.
  end-to-end        — approved report + wire → build_from_report →
                      build_garden_audit_actions → correct Hashi actions.
  NO HTML comment   — the rendered report contains no `<!-- garden-audit` string.
  CLI main()        — argv dispatch: missing-wire degrade + edited/unedited routing.
  _is_wire_edited   — single-load digest gate (no second file read).
"""
# version: 0.12.0
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
build_from_report = gap.build_from_report
parse_decision_map = gap.parse_decision_map

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
    from lib.render_md import compute_garden_audit_digest
    wire = _make_wire(findings, **kwargs)
    wire["emit_digest"] = compute_garden_audit_digest(wire)
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
    # spec 032: up_source/up_value are always present on a fresh (post-032)
    # cache entry. Inline declarations carry up_value=None (there is no
    # frontmatter property to read) — this is the routing branch's normal
    # inline shape, not a stale cache.
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Old MOC", "up_source": "inline", "up_value": None},
        decision={"selected": selected, "action": "add_relationship"},
    )


def _broken_up_removal(fid="F01", selected=True):
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Deleted MOC", "up_source": "inline", "up_value": None},
        decision={"selected": selected, "action": "edit_note_text"},
    )


def _broken_up_frontmatter_repoint(fid="F01", selected=True):
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Old MOC", "up_source": "frontmatter",
         "up_value": ["[[Old MOC]]", "[[Reisen (MOC)]]"]},
        decision={"selected": selected, "action": "add_relationship"},
    )


def _broken_up_frontmatter_removal(fid="F01", selected=True):
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Deleted MOC", "up_source": "frontmatter",
         "up_value": ["[[Deleted MOC]]"]},
        decision={"selected": selected, "action": "edit_note_text"},
    )


def _broken_up_stale_cache(fid="F01", selected=True, action="edit_note_text"):
    """A broken_up finding whose cache predates spec 032 — up_value key absent."""
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Old MOC", "up_source": "inline"},  # no up_value key at all
        decision={"selected": selected, "action": action},
    )


def _broken_up_no_declaration_site(fid="F01", selected=True, action="edit_note_text"):
    """up_source absent/None on a broken finding — the impossible case, unroutable."""
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Old MOC", "up_source": None, "up_value": "[[Old MOC]]"},
        decision={"selected": selected, "action": action},
    )


def _broken_up_map_shaped_value(fid="F01", selected=True, action="edit_note_text"):
    """A map-shaped up_value (spec 032 T3.2) — no defined transform, unroutable
    with its own reason (NOT stale-cache: the cache is healthy here)."""
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Old MOC", "up_source": "frontmatter", "up_value": {"a": 1}},
        decision={"selected": selected, "action": action},
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


def _parent_not_moc(fid="F01", up_target="Real Note"):
    """spec 033 T2.1/ADR-1: the up:: target exists and is in scope, but isn't a
    MOC — the link works, so this is advisory/unfixable, matching exactly the
    shape garden-audit.py's _check_broken_up emits (no decision key at all)."""
    return _wire_finding(
        fid, "parent_not_moc", "advisory", False,
        "Notes/Broken.md", "Broken",
        {"up_target": up_target, "up_source": "inline", "up_value": None,
         "up_broken_reason": "not-a-moc"},
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

    def test_selected_broken_up_removal_emits_remove_up_link(self):
        # Link-only removal (user decision 2026-07-23): the broken link is
        # removed from the up:: line — no whole-line literal match anymore.
        items = build_from_wire(_make_wire([_broken_up_removal(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        c = items[0]
        assert c["garden_action"] == "remove_up_link"
        assert c["path"] == "Notes/Broken.md"
        assert c["link"] == "Deleted MOC"
        assert "match" not in c and "replace" not in c

    def test_unselected_broken_up_emits_no_item(self):
        assert build_from_wire(_make_wire([_broken_up_removal(selected=False)]))["confirmed_items"] == []

    def test_wire_repoint_targets_user_chosen_moc_not_original(self):
        # W1: a wire-edited decision.repoint must point up:: at the user's chosen
        # MOC, NOT the broken original up_target ("Old MOC").
        f = _broken_up_repoint(selected=True)
        f["decision"]["repoint"] = "Custom MOC"
        c = build_from_wire(_make_wire([f]))["confirmed_items"][0]
        assert c["garden_action"] == "add_relationship"
        assert c["up_line"] == "up:: [[Custom MOC]]"
        assert "Old MOC" not in c["up_line"]

    def test_wire_empty_repoint_falls_back_to_up_target(self):
        # Empty repoint slot → up_line falls back to the original up_target.
        f = _broken_up_repoint(selected=True)
        f["decision"]["repoint"] = ""
        c = build_from_wire(_make_wire([f]))["confirmed_items"][0]
        assert c["up_line"] == "up:: [[Old MOC]]"

    def test_wire_repoint_wikilinked_value_normalizes(self):
        # A wire repoint value wrapped in [[ ]] normalizes to a clean up:: line.
        f = _broken_up_repoint(selected=True)
        f["decision"]["repoint"] = "[[Custom MOC]]"
        c = build_from_wire(_make_wire([f]))["confirmed_items"][0]
        assert c["up_line"] == "up:: [[Custom MOC]]"


class TestBuildFromWireDeadLink:
    def test_selected_dead_link_emits_resolve_dead_link(self):
        # Semantic resolution (2026-07-24): dead_link → resolve_dead_link with the
        # BARE target (Hashi resolves alias/embed + display). No literal match.
        items = build_from_wire(_make_wire([_dead_link(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        c = items[0]
        assert c["garden_action"] == "resolve_dead_link"
        assert c["path"] == "Notes/Source.md"
        assert c["target"] == "Missing Note"
        # Empty replace = unlink intent (Hashi keeps the display text).
        assert c["replace"] == ""
        assert "match" not in c and "occurrence" not in c

    def test_unselected_dead_link_emits_no_item(self):
        assert build_from_wire(_make_wire([_dead_link(selected=False)]))["confirmed_items"] == []

    def test_dead_link_with_replace_target_repoints(self):
        # Wire decision.replace is a '[[New]]' wikilink → normalised repoint.
        c = build_from_wire(_make_wire([_dead_link(selected=True, replace="[[New Note]]")]))["confirmed_items"][0]
        assert c["garden_action"] == "resolve_dead_link"
        assert c["replace"] == "[[New Note]]"

    def test_dead_link_empty_replace_is_unlink(self):
        # Remove intent (empty replace) → unlink: the parser passes replace='';
        # Hashi drops the [[ ]] keeping the display (not Tomo's concern anymore).
        c = build_from_wire(_make_wire([_dead_link(selected=True, replace="")]))["confirmed_items"][0]
        assert c["target"] == "Missing Note"
        assert c["replace"] == ""


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


class TestBuildFromWireParentNotMocCon2:
    """spec 033 T2.2 / PRD F2 criterion 5, CON-2: parent_not_moc must never
    reach build_from_wire's broken_up elif (garden-audit-parser.py:603) —
    driving the REAL function over a mixed batch, not inspecting the finding
    dict. CON-2 holds because the code path is structurally absent (the outer
    `if not finding.get("fixable")` gate fires first), not because nothing
    happens to take it.
    """

    def _mixed_findings(self):
        return [
            _broken_up_repoint("F01"),
            _broken_up_removal("F02"),
            _parent_not_moc("F03", up_target="Real A"),
            _parent_not_moc("F04", up_target="Real B"),
            _parent_not_moc("F05", up_target="Real C"),
        ]

    def test_no_confirmed_item_and_no_action_for_any_parent_not_moc(self):
        result = build_from_wire(_make_wire(self._mixed_findings()))
        confirmed = result["confirmed_items"]
        assert not any(c["garden_check"] == "parent_not_moc" for c in confirmed), (
            "parent_not_moc must never produce a confirmed_item/action"
        )
        assert not any(c["id"] in ("F03", "F04", "F05") for c in confirmed)
        acked_checks = [a["check"] for a in result["acked_advisories"]]
        assert acked_checks.count("parent_not_moc") == 3, (
            "all three parent_not_moc findings must land in acked_advisories"
        )

    def test_broken_up_still_routes_exactly_as_spec_032_adr7(self):
        # ADR-7 regression guard: the split must not perturb spec 032's
        # broken_up routing for the findings that DO stay broken_up, even
        # when they share a batch with parent_not_moc findings.
        confirmed = build_from_wire(_make_wire(self._mixed_findings()))["confirmed_items"]
        assert len(confirmed) == 2, "only the two broken_up findings may confirm"
        repoint = next(c for c in confirmed if c["id"] == "F01")
        removal = next(c for c in confirmed if c["id"] == "F02")
        assert repoint["garden_action"] == "add_relationship"
        assert repoint["up_line"] == "up:: [[Old MOC]]"
        assert removal["garden_action"] == "remove_up_link"
        assert removal["path"] == "Notes/Broken.md"
        assert removal["link"] == "Deleted MOC"


class TestBrokenUpListTarget:
    """Cache up:: is a multi-value list — must reconstruct the real line."""

    def _list_removal(self, fid="F01"):
        return _wire_finding(
            fid, "broken_up", "integrity", True,
            "Notes/Broken.md", "Broken",
            {"up_target": ["020 Active MOC"], "up_source": "inline", "up_value": None},
            decision={"selected": True, "action": "edit_note_text"},
        )

    def test_removal_link_from_list_up_target(self):
        # Legacy list-shaped up_target → bare first stem, never a list-repr.
        c = build_from_wire(_make_wire([self._list_removal()]))["confirmed_items"][0]
        assert c["garden_action"] == "remove_up_link"
        assert c["link"] == "020 Active MOC"
        assert "[" not in c["link"]

    def test_multi_target_up_list_takes_first(self):
        # Defensive: a multi-value up_target list yields the FIRST stem as the
        # link to remove (the scan emits singular broken stems; list shape is a
        # legacy-cache artifact).
        f = self._list_removal()
        f["detail"]["up_target"] = ["020 Active MOC", "030 Reference MOC"]
        c = build_from_wire(_make_wire([f]))["confirmed_items"][0]
        assert c["link"] == "020 Active MOC"


# ---------------------------------------------------------------------------
# spec 032 T3.1: garden_action depends on WHERE up:: is declared (up_source),
# not just the user's remove/repoint choice. ADR-5: never a body-oriented
# fallback for a frontmatter-sourced finding.
# ---------------------------------------------------------------------------

class TestBuildFromWireBrokenUpRouting:
    def test_inline_repoint_emits_add_relationship_byte_identical(self):
        items = build_from_wire(_make_wire([_broken_up_repoint(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        assert items[0]["garden_action"] == "add_relationship"
        assert items[0]["up_line"] == "up:: [[Old MOC]]"

    def test_inline_remove_emits_remove_up_link_byte_identical(self):
        items = build_from_wire(_make_wire([_broken_up_removal(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        c = items[0]
        assert c["garden_action"] == "remove_up_link"
        assert c["link"] == "Deleted MOC"

    def test_frontmatter_repoint_emits_edit_frontmatter(self):
        items = build_from_wire(
            _make_wire([_broken_up_frontmatter_repoint(selected=True)])
        )["confirmed_items"]
        assert len(items) == 1
        assert items[0]["garden_action"] == "edit_frontmatter"

    def test_frontmatter_remove_emits_edit_frontmatter(self):
        items = build_from_wire(
            _make_wire([_broken_up_frontmatter_removal(selected=True)])
        )["confirmed_items"]
        assert len(items) == 1
        assert items[0]["garden_action"] == "edit_frontmatter"

    def test_mixed_batch_routes_each_by_its_own_note(self):
        findings = [
            _broken_up_repoint("F01", selected=True),               # inline repoint
            _broken_up_frontmatter_removal("F02", selected=True),   # frontmatter remove
        ]
        items = build_from_wire(_make_wire(findings))["confirmed_items"]
        by_id = {c["id"]: c["garden_action"] for c in items}
        assert by_id == {"F01": "add_relationship", "F02": "edit_frontmatter"}

    def test_up_value_key_absent_is_unroutable_stale_cache(self):
        result = build_from_wire(_make_wire([_broken_up_stale_cache(selected=True)]))
        assert result["confirmed_items"] == []
        assert result["unroutable"] == [
            {"id": "F01", "path": "Notes/Broken.md", "reason": "stale-cache"}
        ]

    def test_stale_cache_finding_does_not_suppress_other_findings_in_batch(self):
        # spec 032 T3.4 (PRD AC-F6.3): withholding one finding must not swallow
        # the rest of the run. A parser that returned an empty confirmed_items
        # for any reason would pass a batch of purely stale-cache findings — so
        # this batch pairs the stale one with a finding that DOES route, and
        # asserts the count as well as the shape.
        findings = [
            _broken_up_stale_cache("F01"),
            _broken_up_frontmatter_removal("F02"),
        ]
        result = build_from_wire(_make_wire(findings))
        items = result["confirmed_items"]
        assert len(items) == 1
        assert items[0]["id"] == "F02"
        assert items[0]["garden_action"] == "edit_frontmatter"
        assert result["unroutable"] == [
            {"id": "F01", "path": "Notes/Broken.md", "reason": "stale-cache"}
        ]

    def test_stale_cache_finding_routes_normally_once_up_value_recovers(self):
        # spec 032 T3.4, PRD AC-F6.4: withholding is temporary, not terminal. A
        # cache rebuild adds the up_value key for the same note/target; the next
        # audit run must route it like any other finding.
        stale = build_from_wire(_make_wire([_broken_up_stale_cache(selected=True)]))
        assert stale["confirmed_items"] == []
        assert stale["unroutable"] == [
            {"id": "F01", "path": "Notes/Broken.md", "reason": "stale-cache"}
        ]

        # Same note, same up_target ("Old MOC"), same inline source — the only
        # difference is that up_value is now present (a refreshed cache entry).
        recovered = build_from_wire(_make_wire([_broken_up_repoint(selected=True)]))
        items = recovered["confirmed_items"]
        assert len(items) == 1
        assert items[0]["garden_action"] == "add_relationship"
        assert recovered["unroutable"] == []

    def test_up_value_present_none_is_not_treated_as_stale(self):
        # Inline sources legitimately carry up_value=None (ADR-3) — the sentinel
        # must distinguish this from a genuinely absent key.
        items = build_from_wire(_make_wire([_broken_up_removal(selected=True)]))["confirmed_items"]
        assert len(items) == 1
        assert items[0]["garden_action"] == "remove_up_link"

    def test_up_source_none_is_unroutable_no_declaration_site(self):
        result = build_from_wire(
            _make_wire([_broken_up_no_declaration_site(selected=True)])
        )
        assert result["confirmed_items"] == []
        assert result["unroutable"] == [
            {"id": "F01", "path": "Notes/Broken.md", "reason": "no-declaration-site"}
        ]

    def test_map_shaped_up_value_is_unroutable_unsupported_shape(self):
        result = build_from_wire(
            _make_wire([_broken_up_map_shaped_value(selected=True)])
        )
        assert result["confirmed_items"] == []
        assert result["unroutable"] == [
            {"id": "F01", "path": "Notes/Broken.md", "reason": "unsupported-shape"}
        ]

    def test_no_frontmatter_finding_ever_emits_body_oriented_action(self):
        # ADR-5: assert directly across the whole emitted set, not by inspection
        # of a single happy-path case.
        findings = [
            _broken_up_frontmatter_repoint("F01", selected=True),
            _broken_up_frontmatter_removal("F02", selected=True),
            _broken_up_repoint("F03", selected=True),
            _broken_up_removal("F04", selected=True),
        ]
        items = build_from_wire(_make_wire(findings))["confirmed_items"]
        assert len(items) == 4
        frontmatter_ids = {"F01", "F02"}
        for c in items:
            if c["id"] in frontmatter_ids:
                assert c["garden_action"] == "edit_frontmatter"
            assert not (
                c["id"] in frontmatter_ids
                and c["garden_action"] in ("remove_up_link", "add_relationship")
            )


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
    # spec 032: up_source/up_value present, matching a fresh (post-032) cache.
    # Inline declarations carry up_value=None (no frontmatter property to read).
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Broken Note.md", "stem": "Broken Note"},
        "detail": {"up_target": "Deleted MOC", "up_source": "inline", "up_value": None},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _doc_finding_broken_up_repoint(fid="F03"):
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Repoint Note.md", "stem": "Repoint Note"},
        "detail": {"up_target": "Old MOC", "up_source": "inline", "up_value": None},
        "decision": {"selected": True, "action": "add_relationship"},
    }


def _doc_finding_broken_up_frontmatter_repoint(fid="F03"):
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Repoint Note.md", "stem": "Repoint Note"},
        "detail": {"up_target": "Old MOC", "up_source": "frontmatter",
                   "up_value": ["[[Old MOC]]", "[[Reisen (MOC)]]"]},
        "decision": {"selected": True, "action": "add_relationship"},
    }


def _doc_finding_broken_up_frontmatter_removal(fid="F02"):
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Broken Note.md", "stem": "Broken Note"},
        "detail": {"up_target": "Deleted MOC", "up_source": "frontmatter",
                   "up_value": ["[[Deleted MOC]]"]},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _doc_finding_broken_up_stale_cache(fid="F02"):
    """A broken_up finding whose cache predates spec 032 — up_value key absent."""
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Broken Note.md", "stem": "Broken Note"},
        "detail": {"up_target": "Deleted MOC", "up_source": "inline"},
        "decision": {"selected": True, "action": "edit_note_text"},
    }


def _doc_finding_broken_up_no_declaration_site(fid="F02"):
    """up_source absent/None on a broken finding — the impossible case, unroutable."""
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Broken Note.md", "stem": "Broken Note"},
        "detail": {"up_target": "Deleted MOC", "up_source": None, "up_value": "[[Deleted MOC]]"},
        "decision": {"selected": True, "action": "edit_note_text"},
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


def _wire(doc):
    """Build the wire payload (STRUCTURE source) for a doc."""
    return gar.build_wire_payload(doc)


def _report_and_wire(doc):
    """Render BOTH artifacts from one doc — the two-artifact split."""
    return _full_report(doc), _wire(doc)


# ---------------------------------------------------------------------------
# No HTML comment in the rendered report (spec 030 two-artifact split)
# ---------------------------------------------------------------------------

class TestNoHtmlComment:
    def test_report_contains_no_garden_audit_comment(self):
        doc = _make_doc([
            _doc_finding_dead_link("F01"),
            _doc_finding_broken_up_removal("F02"),
            _doc_finding_unparented("F03"),
            _doc_finding_duplicate("F04"),
        ])
        report = _full_report(doc)
        assert "<!-- garden-audit" not in report
        assert "<!--" not in report  # no HTML comment of any kind


# ---------------------------------------------------------------------------
# parse_decision_map: markdown → {F-id → {apply, repoint, replace}}
# ---------------------------------------------------------------------------

class TestParseDecisionMap:
    def test_ticked_apply_maps_to_apply_true(self):
        md = _full_report(_make_doc([_doc_finding_dead_link("F01")]))
        dm = parse_decision_map(md)
        assert dm["F01"]["apply"] is True

    def test_unticked_apply_maps_to_apply_false(self):
        md = _full_report(_make_doc([_doc_finding_dead_link("F01")]))
        md = md.replace("- [x] Apply", "- [ ] Apply")
        assert parse_decision_map(md)["F01"]["apply"] is False

    def test_typed_repoint_captured(self):
        md = _full_report(_make_doc([_doc_finding_broken_up_repoint("F01")]))
        md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[Chosen MOC]]")
        assert parse_decision_map(md)["F01"]["repoint"] == "Chosen MOC"

    def test_typed_replace_captured(self):
        md = _full_report(_make_doc([_doc_finding_dead_link("F01")]))
        md = md.replace("**Replace with:** [[]]", "**Replace with:** [[New Target]]")
        assert parse_decision_map(md)["F01"]["replace"] == "New Target"


# ---------------------------------------------------------------------------
# Phase 7 (T7.3): Suggest opt-in + ticked pick sub-checkbox
# ---------------------------------------------------------------------------

def _dead_link_cache():
    return [
        {"stem": "Missing Notes", "kind": "note", "path": "N/Missing Notes.md", "topics": []},
    ]


def _broken_up_cache():
    return [
        {"stem": "Writing MOC", "kind": "moc", "path": "MOCs/Writing MOC.md", "topics": ["writing"]},
    ]


def _enriched_dead_link_report(fid="F01"):
    """Render a dead_link report, opt into Suggest, run --suggest enrichment."""
    doc = _make_doc([_doc_finding_dead_link(fid)])
    md = _full_report(doc)
    wire = _wire(doc)
    md = md.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
    return gar.enrich_report_with_suggestions(md, wire, _dead_link_cache()), wire


def _enriched_broken_up_report(fid="F01"):
    f = _doc_finding_broken_up_repoint(fid)
    f["detail"]["up_target"] = "Writng MOC"  # typo → "Writing MOC" candidate
    doc = _make_doc([f])
    md = _full_report(doc)
    wire = _wire(doc)
    md = md.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
    return gar.enrich_report_with_suggestions(md, wire, _broken_up_cache()), wire


class TestParseDecisionMapSuggest:
    def test_suggest_opt_in_read(self):
        md, _ = _enriched_dead_link_report("F01")
        assert parse_decision_map(md)["F01"]["suggest"] is True

    def test_suggest_unticked_is_false(self):
        md = _full_report(_make_doc([_doc_finding_dead_link("F01")]))
        assert parse_decision_map(md)["F01"]["suggest"] is False

    def test_ticked_pick_becomes_replace_value(self):
        md, _ = _enriched_dead_link_report("F01")
        md = md.replace("- [ ] [[Missing Notes]]", "- [x] [[Missing Notes]]", 1)
        assert parse_decision_map(md)["F01"]["replace"] == "Missing Notes"

    def test_ticked_pick_becomes_repoint_value(self):
        md, _ = _enriched_broken_up_report("F01")
        md = md.replace("- [ ] [[Writing MOC]]", "- [x] [[Writing MOC]]", 1)
        assert parse_decision_map(md)["F01"]["repoint"] == "Writing MOC"

    def test_typed_value_wins_over_ticked_pick(self):
        # D4 precedence: a value typed into the field OVERRIDES a ticked pick.
        md, _ = _enriched_dead_link_report("F01")
        md = md.replace("- [ ] [[Missing Notes]]", "- [x] [[Missing Notes]]", 1)
        md = md.replace("**Replace with:** [[]]", "**Replace with:** [[Typed Wins]]")
        assert parse_decision_map(md)["F01"]["replace"] == "Typed Wins"

    def test_no_tick_no_type_is_empty(self):
        md, _ = _enriched_dead_link_report("F01")
        # Picks present but none ticked, field empty → removal (empty replace).
        assert parse_decision_map(md)["F01"]["replace"] == ""

    def test_multiple_ticked_picks_uses_first_and_warns(self, capsys):
        # S1: "Pick one" is the contract. If the user ticks two candidates, the
        # first is used and a warning is emitted (the extras are dropped).
        doc = _make_doc([_doc_finding_dead_link("F01")])
        md = _full_report(doc)
        wire = _wire(doc)
        md = md.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
        # Two candidates both clear the cutoff vs "Missing Note".
        cache = [
            {"stem": "Missing Notes", "kind": "note", "path": "N/a.md", "topics": []},
            {"stem": "Missing Noted", "kind": "note", "path": "N/b.md", "topics": []},
        ]
        md = gar.enrich_report_with_suggestions(md, wire, cache)
        assert "- [ ] [[Missing Notes]]" in md and "- [ ] [[Missing Noted]]" in md
        # The FIRST candidate line in the block (both score 0.96; ties sort by
        # target ASC → "Missing Noted" renders before "Missing Notes").
        import re as _re
        first_pick = _re.search(r"- \[ \] \[\[([^\]]+)\]\]", md).group(1)
        md = md.replace("- [ ] [[Missing Notes]]", "- [x] [[Missing Notes]]", 1)
        md = md.replace("- [ ] [[Missing Noted]]", "- [x] [[Missing Noted]]", 1)
        dm = parse_decision_map(md)
        assert dm["F01"]["replace"] == first_pick  # the first ticked pick wins
        assert "ticked pick" in capsys.readouterr().err


class TestBuildFromReportWithPick:
    def test_ticked_dead_link_pick_flows_to_confirmed_item(self):
        md, wire = _enriched_dead_link_report("F01")
        md = md.replace("- [ ] [[Missing Notes]]", "- [x] [[Missing Notes]]", 1)
        items = build_from_report(md, wire)["confirmed_items"]
        assert len(items) == 1
        assert items[0]["replace"] == "[[Missing Notes]]"

    def test_ticked_broken_up_pick_becomes_add_relationship(self):
        md, wire = _enriched_broken_up_report("F01")
        md = md.replace("- [ ] [[Writing MOC]]", "- [x] [[Writing MOC]]", 1)
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "add_relationship"
        assert c["up_line"] == "up:: [[Writing MOC]]"

    def test_no_pick_no_type_broken_up_is_removal(self):
        md, wire = _enriched_broken_up_report("F01")
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "remove_up_link"
        assert c["link"]


class TestBuildFromReportParentNotMocCon2:
    """spec 033 T2.2 / PRD F2 criterion 5, CON-2: parent_not_moc must never
    reach _confirmed_item_from_wire_finding's `if check == "broken_up":`
    branch (garden-audit-parser.py:403) — driving the REAL build_from_report
    over a mixed batch. The markdown carries F-id blocks for the two broken_up
    findings only; the three parent_not_moc findings have NO markdown block at
    all, proving build_from_report doesn't need one — the outer
    `if not finding.get("fixable")` gate (:516) fires before any decision-map
    lookup would matter for them.
    """

    def _mixed_wire(self):
        doc = _make_doc([
            _doc_finding_broken_up_repoint("F01"),
            _doc_finding_broken_up_removal("F02"),
        ])
        md = _full_report(doc)
        # The report path resolves repoint-vs-remove from the MARKDOWN's typed
        # "Repoint to:" field, not from the doc's decision.action — fill it in
        # for F01 so the ADR-7 regression test exercises both outcomes, same
        # as test_user_fills_repoint_target_adds_relationship above.
        md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[Chosen MOC]]", 1)
        wire = _wire(doc)
        wire["findings"] = wire["findings"] + [
            _parent_not_moc("F03", up_target="Real A"),
            _parent_not_moc("F04", up_target="Real B"),
            _parent_not_moc("F05", up_target="Real C"),
        ]
        return md, wire

    def test_no_confirmed_item_and_no_action_for_any_parent_not_moc(self):
        md, wire = self._mixed_wire()
        result = build_from_report(md, wire)
        confirmed = result["confirmed_items"]
        assert not any(c["garden_check"] == "parent_not_moc" for c in confirmed), (
            "parent_not_moc must never produce a confirmed_item/action"
        )
        assert not any(c["id"] in ("F03", "F04", "F05") for c in confirmed)
        acked_checks = [a["check"] for a in result["acked_advisories"]]
        assert acked_checks.count("parent_not_moc") == 3, (
            "all three parent_not_moc findings must land in acked_advisories"
        )

    def test_broken_up_still_routes_exactly_as_spec_032_adr7(self):
        # ADR-7 regression guard: the split must not perturb spec 032's
        # broken_up routing for the findings that DO stay broken_up.
        md, wire = self._mixed_wire()
        confirmed = build_from_report(md, wire)["confirmed_items"]
        assert len(confirmed) == 2, "only the two broken_up findings may confirm"
        repoint = next(c for c in confirmed if c["id"] == "F01")
        removal = next(c for c in confirmed if c["id"] == "F02")
        assert repoint["garden_action"] == "add_relationship"
        assert repoint["up_line"] == "up:: [[Chosen MOC]]"
        assert removal["garden_action"] == "remove_up_link"
        assert removal["path"] == "Notes/Broken Note.md"
        assert removal["link"] == "Deleted MOC"


# ---------------------------------------------------------------------------
# Change 2: structure File-under field + file_note target precedence
# ---------------------------------------------------------------------------

def _doc_finding_unparented_no_candidate(fid="F01"):
    """An unparented finding the scan found NO candidate MOC for (topics only)."""
    return {
        "id": fid, "check": "unparented", "tier": "structure", "fixable": True,
        "target": {"path": "Notes/Orphan Note.md", "stem": "Orphan Note"},
        "detail": {"candidate_mocs": [], "topics": ["writing", "misc", "notes"]},
        "decision": {"selected": True, "action": "link_to_moc"},
    }


def _enriched_unparented_report(fid="F01"):
    """Render an unparented (no scan candidate) report, opt into Suggest, enrich."""
    doc = _make_doc([_doc_finding_unparented_no_candidate(fid)])
    md = _full_report(doc)
    wire = _wire(doc)
    md = md.replace("- [ ] Suggest targets", "- [x] Suggest targets", 1)
    cache = [{"stem": "Writing MOC", "kind": "moc", "path": "MOCs/Writing MOC.md",
              "topics": ["writing"]}]
    return gar.enrich_report_with_suggestions(md, wire, cache), wire


class TestParseDecisionMapFileUnder:
    def test_file_under_field_read(self):
        md = _full_report(_make_doc([_doc_finding_unparented("F01")]))
        md = md.replace("**File under:** [[]]", "**File under:** [[Chosen MOC]]")
        assert parse_decision_map(md)["F01"]["file_under"] == "Chosen MOC"

    def test_file_under_empty_by_default(self):
        md = _full_report(_make_doc([_doc_finding_unparented("F01")]))
        assert parse_decision_map(md)["F01"]["file_under"] == ""

    def test_ticked_pick_becomes_file_under(self):
        md, _ = _enriched_unparented_report("F01")
        md = md.replace("- [ ] [[Writing MOC]]", "- [x] [[Writing MOC]]", 1)
        assert parse_decision_map(md)["F01"]["file_under"] == "Writing MOC"


class TestFileNotePrecedence:
    """file_note target precedence: typed File-under > ticked pick > scan
    candidate_mocs[0] > none (skip). The resolved MOC threads into link_to_moc +
    add_relationship via build_garden_audit_actions."""

    def test_scan_candidate_used_when_no_user_input(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_unparented("F01")]))
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "file_note"
        assert c["target_moc"] == "Writing MOC"  # scan candidate

    def test_typed_file_under_wins_over_scan_candidate(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_unparented("F01")]))
        md = md.replace("**File under:** [[]]", "**File under:** [[User MOC]]")
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["target_moc"] == "User MOC"

    def test_ticked_pick_wins_over_scan_candidate(self):
        md, wire = _enriched_unparented_report("F01")
        md = md.replace("- [ ] [[Writing MOC]]", "- [x] [[Writing MOC]]", 1)
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "file_note"
        assert c["target_moc"] == "Writing MOC"

    def test_typed_wins_over_ticked_pick(self):
        md, wire = _enriched_unparented_report("F01")
        md = md.replace("- [ ] [[Writing MOC]]", "- [x] [[Writing MOC]]", 1)
        md = md.replace("**File under:** [[]]", "**File under:** [[Typed MOC]]")
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["target_moc"] == "Typed MOC"

    def test_no_candidate_no_input_skips_item(self, capsys):
        # No scan candidate, no typed value, no pick → can't file → skip + warn.
        md, wire = _report_and_wire(_make_doc([_doc_finding_unparented_no_candidate("F01")]))
        items = build_from_report(md, wire)["confirmed_items"]
        assert items == []
        err = capsys.readouterr().err.lower()  # single read — capsys clears each call
        assert "skipping" in err and "no moc" in err

    def test_resolved_moc_flows_into_link_and_relationship(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_unparented("F01")]))
        md = md.replace("**File under:** [[]]", "**File under:** [[User MOC]]")
        items = build_from_report(md, wire)["confirmed_items"]
        actions = build_garden_audit_actions(items)
        link = next(a for a in actions if a["action"] == "link_to_moc")
        rel = next(a for a in actions if a["action"] == "add_relationship")
        assert link["target_moc"] == "User MOC"
        assert rel["line"] == "up:: [[User MOC]]"


# ---------------------------------------------------------------------------
# build_from_report: join wire STRUCTURE + markdown DECISIONS by F-id
# ---------------------------------------------------------------------------

class TestBuildFromReport:
    def test_unparented_uses_wire_path_and_candidate_moc(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_unparented("F01")]))
        items = build_from_report(md, wire)["confirmed_items"]
        assert len(items) == 1
        c = items[0]
        assert c["id"] == "F01"
        assert c["garden_action"] == "file_note"
        assert c["path"] == "Notes/Orphan Note.md"     # from wire
        assert c["stem"] == "Orphan Note"              # from wire
        assert c["target_moc"] == "Writing MOC"         # from wire candidate_mocs
        assert c["target_moc_path"] == "MOCs/Writing MOC.md"

    def test_broken_up_removal_link_from_wire_up_target(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_broken_up_removal("F02")]))
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "remove_up_link"
        assert c["path"] == "Notes/Broken Note.md"      # from wire
        assert c["link"] == "Deleted MOC"               # from wire up_target
        assert "match" not in c and "replace" not in c

    def test_broken_up_list_up_target_from_wire(self):
        f = _doc_finding_broken_up_removal("F02")
        f["detail"]["up_target"] = ["020 Active MOC", "030 Reference MOC"]
        md, wire = _report_and_wire(_make_doc([f]))
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["link"] == "020 Active MOC"            # first stem, bare
        assert "[" not in c["link"] and "'" not in c["link"]

    def test_dead_link_target_from_wire_empty_replace(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_dead_link("F04")]))
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "resolve_dead_link"
        assert c["target"] == "Missing Note"             # from wire dead_target
        assert c["replace"] == ""                        # unlink intent
        assert "match" not in c

    def test_dead_link_typed_replace_repoints(self):
        # A typed Replace target → repoint to the new wikilink.
        md, wire = _report_and_wire(_make_doc([_doc_finding_dead_link("F04")]))
        md = md.replace("**Replace with:** [[]]", "**Replace with:** [[New Target]]")
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "resolve_dead_link"
        assert c["target"] == "Missing Note"
        assert c["replace"] == "[[New Target]]"

    def test_advisory_finding_produces_no_item(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_duplicate("F05")]))
        assert build_from_report(md, wire)["confirmed_items"] == []

    def test_run_id_from_wire(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_unparented("F01")]))
        assert build_from_report(md, wire)["run_id"] == "run-rt-001"

    def test_unticked_apply_skips_item(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_dead_link("F04")]))
        md = md.replace("- [x] Apply", "- [ ] Apply")
        assert build_from_report(md, wire)["confirmed_items"] == []

    def test_id_in_wire_but_absent_from_markdown_is_skipped(self):
        # The wire carries F01; the markdown decision map does not (no ### F01
        # heading) → the finding is not confirmed. Join key is the F-id.
        md, wire = _report_and_wire(_make_doc([_doc_finding_dead_link("F01")]))
        # Strip the whole finding block from the markdown (remove its heading).
        md_no_f01 = md.replace("### F01", "### ZZ99")
        assert build_from_report(md_no_f01, wire)["confirmed_items"] == []

    def test_user_fills_replace_target(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_dead_link("F04")]))
        md = md.replace("**Replace with:** [[]]", "**Replace with:** [[New Target]]")
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["replace"] == "[[New Target]]"

    def test_user_fills_repoint_target_adds_relationship(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_broken_up_repoint("F03")]))
        md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[Chosen MOC]]")
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "add_relationship"
        assert c["up_line"] == "up:: [[Chosen MOC]]"

    def test_empty_repoint_falls_back_to_removal(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_broken_up_repoint("F03")]))
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "remove_up_link"
        assert c["link"] == "Old MOC"                    # from wire up_target

    def test_removal_finding_offers_repoint_field_and_fills_to_add_rel(self):
        # A broken_up finding (action=edit_note_text) renders the Repoint field;
        # filling it makes the fix a repoint (add_relationship), not a removal.
        md, wire = _report_and_wire(_make_doc([_doc_finding_broken_up_removal("F02")]))
        assert "**Repoint to:**" in md
        md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[New Home MOC]]")
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "add_relationship"
        assert c["up_line"] == "up:: [[New Home MOC]]"

    def test_empty_wire_dict_produces_no_items(self):
        # An empty wire dict (no findings) → no confirmed items (graceful). This
        # is the unit-level empty-dict case; the file-not-found CLI degrade is
        # covered by TestCliMainDispatch.test_missing_wire_degrades_to_empty.
        md = _full_report(_make_doc([_doc_finding_dead_link("F01")]))
        assert build_from_report(md, {})["confirmed_items"] == []


# ---------------------------------------------------------------------------
# spec 032 T3.1: same routing contract as build_from_wire, joined through the
# markdown decision map instead of the wire's decision block.
# ---------------------------------------------------------------------------

class TestBuildFromReportBrokenUpRouting:
    def test_inline_repoint_emits_add_relationship(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_broken_up_repoint("F03")]))
        md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[Chosen MOC]]")
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "add_relationship"

    def test_inline_remove_emits_remove_up_link(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_broken_up_removal("F02")]))
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "remove_up_link"

    def test_frontmatter_repoint_emits_edit_frontmatter(self):
        md, wire = _report_and_wire(
            _make_doc([_doc_finding_broken_up_frontmatter_repoint("F03")])
        )
        md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[Chosen MOC]]")
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "edit_frontmatter"

    def test_frontmatter_remove_emits_edit_frontmatter(self):
        md, wire = _report_and_wire(
            _make_doc([_doc_finding_broken_up_frontmatter_removal("F02")])
        )
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "edit_frontmatter"

    def test_mixed_batch_routes_each_by_its_own_note(self):
        doc = _make_doc([
            _doc_finding_broken_up_removal("F02"),                  # inline remove
            _doc_finding_broken_up_frontmatter_removal("F03"),      # frontmatter remove
        ])
        md, wire = _report_and_wire(doc)
        items = build_from_report(md, wire)["confirmed_items"]
        by_id = {c["id"]: c["garden_action"] for c in items}
        assert by_id == {"F02": "remove_up_link", "F03": "edit_frontmatter"}

    def test_up_value_key_absent_is_unroutable_stale_cache(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_broken_up_stale_cache("F02")]))
        result = build_from_report(md, wire)
        assert result["confirmed_items"] == []
        assert result["unroutable"] == [
            {"id": "F02", "path": "Notes/Broken Note.md", "reason": "stale-cache"}
        ]

    def test_stale_cache_finding_does_not_suppress_other_findings_in_batch(self):
        # spec 032 T3.4 (PRD AC-F6.3): pair the stale finding with one that DOES
        # route, and assert the count — a parser returning an empty
        # confirmed_items for any reason would pass a batch of only stale
        # findings.
        doc = _make_doc([
            _doc_finding_broken_up_stale_cache("F02"),
            _doc_finding_broken_up_frontmatter_removal("F03"),
        ])
        md, wire = _report_and_wire(doc)
        result = build_from_report(md, wire)
        items = result["confirmed_items"]
        assert len(items) == 1
        assert items[0]["id"] == "F03"
        assert items[0]["garden_action"] == "edit_frontmatter"
        assert result["unroutable"] == [
            {"id": "F02", "path": "Notes/Broken Note.md", "reason": "stale-cache"}
        ]

    def test_stale_cache_finding_routes_normally_once_up_value_recovers(self):
        # spec 032 T3.4, PRD AC-F6.4: withholding is temporary. Same note/target
        # ("Deleted MOC", inline source) — the second run's cache carries
        # up_value, so the finding must route rather than stay withheld.
        stale_md, stale_wire = _report_and_wire(
            _make_doc([_doc_finding_broken_up_stale_cache("F02")])
        )
        stale = build_from_report(stale_md, stale_wire)
        assert stale["confirmed_items"] == []
        assert stale["unroutable"] == [
            {"id": "F02", "path": "Notes/Broken Note.md", "reason": "stale-cache"}
        ]

        fresh_md, fresh_wire = _report_and_wire(
            _make_doc([_doc_finding_broken_up_removal("F02")])
        )
        fresh = build_from_report(fresh_md, fresh_wire)
        items = fresh["confirmed_items"]
        assert len(items) == 1
        assert items[0]["garden_action"] == "remove_up_link"
        assert fresh["unroutable"] == []

    def test_up_value_present_none_is_not_treated_as_stale(self):
        md, wire = _report_and_wire(_make_doc([_doc_finding_broken_up_removal("F02")]))
        c = build_from_report(md, wire)["confirmed_items"][0]
        assert c["garden_action"] == "remove_up_link"

    def test_up_source_none_is_unroutable_no_declaration_site(self):
        md, wire = _report_and_wire(
            _make_doc([_doc_finding_broken_up_no_declaration_site("F02")])
        )
        result = build_from_report(md, wire)
        assert result["confirmed_items"] == []
        assert result["unroutable"] == [
            {"id": "F02", "path": "Notes/Broken Note.md", "reason": "no-declaration-site"}
        ]

    def test_no_frontmatter_finding_ever_emits_body_oriented_action(self):
        doc = _make_doc([
            _doc_finding_broken_up_frontmatter_repoint("F01"),
            _doc_finding_broken_up_frontmatter_removal("F02"),
            _doc_finding_broken_up_repoint("F03"),
            _doc_finding_broken_up_removal("F04"),
        ])
        md, wire = _report_and_wire(doc)
        items = build_from_report(md, wire)["confirmed_items"]
        assert len(items) == 4
        frontmatter_ids = {"F01", "F02"}
        for c in items:
            if c["id"] in frontmatter_ids:
                assert c["garden_action"] == "edit_frontmatter"
            assert not (
                c["id"] in frontmatter_ids
                and c["garden_action"] in ("remove_up_link", "add_relationship")
            )


# ---------------------------------------------------------------------------
# END-TO-END: approved report + wire → confirmed_items → Hashi actions
# ---------------------------------------------------------------------------

class TestEndToEndApprovedReportToActions:
    """The full vertical: an approved report + its wire render into Hashi actions.

    Structure comes from the wire, decisions from the markdown, joined by F-id.
    This MUST fail against a no-op/empty build_from_report or a
    build_garden_audit_actions that drops item kinds.
    """

    def _approved(self):
        doc = _make_doc([
            _doc_finding_dead_link("F01"),         # → edit_note_text (remove)
            _doc_finding_broken_up_removal("F02"),  # → edit_note_text (up:: remove)
            _doc_finding_broken_up_repoint("F03"),  # → add_relationship (repoint)
            _doc_finding_unparented("F04"),         # → link_to_moc + add_relationship
            _doc_finding_duplicate("F05"),          # advisory → nothing
        ])
        md = _full_report(doc)
        # The user fills ONLY F03's Repoint field → F03 repoints; F02 stays a
        # removal. Scope the fill to F03's block (split on its heading).
        head, _, f03_onward = md.partition("### F03")
        f03_onward = f03_onward.replace(
            "**Repoint to:** [[]]", "**Repoint to:** [[Correct MOC]]", 1
        )
        return head + "### F03" + f03_onward, _wire(doc)

    def _items(self):
        md, wire = self._approved()
        return build_from_report(md, wire)["confirmed_items"]

    def test_confirmed_items_cover_every_fixable_finding(self):
        ids = {c["id"] for c in self._items()}
        assert ids == {"F01", "F02", "F03", "F04"}  # F05 advisory excluded

    def test_actions_for_dead_link_and_broken_up_removals(self):
        actions = build_garden_audit_actions(self._items())
        # dead_link → resolve_dead_link (semantic; Hashi handles alias/embed).
        resolves = [a for a in actions if a["action"] == "resolve_dead_link"]
        assert len(resolves) == 1
        assert resolves[0]["target"] == "Missing Note"
        assert resolves[0]["replace"] == ""              # unlink intent
        assert resolves[0]["path"] == "Notes/Source Note.md"
        # broken_up removal is LINK-ONLY: a remove_up_link action.
        removes = [a for a in actions if a["action"] == "remove_up_link"]
        assert len(removes) == 1
        assert removes[0]["link"] == "Deleted MOC"
        assert removes[0]["path"] == "Notes/Broken Note.md"

    def test_actions_contain_add_relationship_for_repoint_and_filing(self):
        actions = build_garden_audit_actions(self._items())
        rels = [a for a in actions if a["action"] == "add_relationship"]
        assert len(rels) == 2
        lines = {a["line"] for a in rels}
        assert "up:: [[Correct MOC]]" in lines
        assert "up:: [[Writing MOC]]" in lines
        for a in rels:
            assert a["marker"] == "up::"

    def test_actions_contain_link_to_moc_for_filing(self):
        actions = build_garden_audit_actions(self._items())
        links = [a for a in actions if a["action"] == "link_to_moc"]
        assert len(links) == 1
        assert links[0]["target_moc"] == "Writing MOC"
        assert links[0]["line_to_add"] == "- [[Orphan Note]]"

    def test_all_actions_stamped_applied_false(self):
        actions = build_garden_audit_actions(self._items())
        assert len(actions) == 5
        for a in actions:
            assert a["applied"] is False

    def test_edit_actions_carry_the_note_path(self):
        actions = build_garden_audit_actions(self._items())
        paths = {
            a["path"] for a in actions
            if a["action"] in ("resolve_dead_link", "remove_up_link")
        }
        assert paths == {"Notes/Source Note.md", "Notes/Broken Note.md"}

    def test_empty_confirmed_items_yields_no_actions(self):
        assert build_garden_audit_actions([]) == []


# ---------------------------------------------------------------------------
# Hashi-edited-wire path still works (digest mismatch → build_from_wire)
# ---------------------------------------------------------------------------

class TestEditedWirePathStillWorks:
    """When the wire is Hashi-edited (digest mismatch), the wire is fully
    authoritative — build_from_wire runs, markdown decisions are not consulted."""

    def test_edited_wire_repoint_authoritative(self):
        f = _broken_up_repoint(selected=True)
        f["decision"]["repoint"] = "Custom MOC"
        c = build_from_wire(_make_wire([f]))["confirmed_items"][0]
        assert c["garden_action"] == "add_relationship"
        assert c["up_line"] == "up:: [[Custom MOC]]"


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


# ---------------------------------------------------------------------------
# CLI main() dispatch — the real entry point the conductor invokes. Unit tests
# exercise build_from_report / build_from_wire directly; these drive main()'s
# argv → _load_raw_wire → routing so the degrade + edited-wire branches are
# covered (mock at the orchestrator, not the helper).
# ---------------------------------------------------------------------------

class TestCliMainDispatch:
    def test_missing_wire_degrades_to_empty(self, tmp_path, monkeypatch, capsys):
        # TEST 1: --wire points at a nonexistent file → _load_raw_wire returns
        # None → main() prints the degrade envelope and exits 0 (no crash). This
        # covers the empty-output branch, not the build_from_report(md, {}) unit.
        report = _full_report(_make_doc([_doc_finding_dead_link("F01")]))
        report_path = tmp_path / "report.md"
        report_path.write_text(report, encoding="utf-8")
        missing_wire = tmp_path / "does-not-exist.json"

        monkeypatch.setattr(sys, "argv", [
            "garden-audit-parser.py",
            "--file", str(report_path),
            "--wire", str(missing_wire),
        ])
        rc = gap.main()
        assert rc == 0
        out = json.loads(capsys.readouterr().out)
        assert out["confirmed_items"] == []

    def test_edited_wire_routes_to_build_from_wire(self, tmp_path, monkeypatch, capsys):
        # TEST 2: a real wire with a DIGEST MISMATCH (a fixable finding flipped
        # to selected=False after the digest was computed) → main() must route to
        # build_from_wire (wire fully authoritative), NOT build_from_report. With
        # the item deselected in the wire, the output is empty — proving main()
        # honoured the wire's decision, not the markdown's Apply tick.
        wire = _make_real_wire([_unparented(selected=True)])
        # Simulate a Hashi edit: deselect the finding without recomputing the
        # digest → _is_wire_edited sees the mismatch on the single-loaded dict.
        wire["findings"][0]["decision"]["selected"] = False
        wire_path = tmp_path / "wire.json"
        _write_wire(wire_path, wire)

        # The markdown, by contrast, has the finding present-and-ticked. If main()
        # wrongly used build_from_report it would emit a confirmed_item; the wire
        # path must win and emit none.
        doc = _make_doc([_doc_finding_unparented("F01")])
        report_path = tmp_path / "report.md"
        report_path.write_text(_full_report(doc), encoding="utf-8")

        monkeypatch.setattr(sys, "argv", [
            "garden-audit-parser.py",
            "--file", str(report_path),
            "--wire", str(wire_path),
        ])
        rc = gap.main()
        assert rc == 0
        captured = capsys.readouterr()  # single read — capsys clears on each call
        out = json.loads(captured.out)
        # Wire is authoritative and the item is deselected → no confirmed items.
        assert out["confirmed_items"] == []
        # stderr announces the JSON-only path (build_from_wire routing).
        assert "edited wire is authoritative" in captured.err

    def test_unedited_wire_routes_to_build_from_report(self, tmp_path, monkeypatch, capsys):
        # W1 complement: a DIGEST-MATCHING wire (unedited) → main() must route to
        # build_from_report (wire structure + markdown decisions), NOT
        # build_from_wire. The markdown ticks Apply on F01 → the joined result
        # has a confirmed_item, proving the unedited/report path was taken.
        doc = _make_doc([_doc_finding_unparented("F01")])
        wire = _wire(doc)  # build_wire_payload → correct emit_digest (unedited)
        wire_path = tmp_path / "wire.json"
        _write_wire(wire_path, wire)
        report_path = tmp_path / "report.md"
        report_path.write_text(_full_report(doc), encoding="utf-8")

        monkeypatch.setattr(sys, "argv", [
            "garden-audit-parser.py",
            "--file", str(report_path),
            "--wire", str(wire_path),
        ])
        rc = gap.main()
        assert rc == 0
        captured = capsys.readouterr()
        out = json.loads(captured.out)
        # build_from_report joined wire structure + the ticked markdown decision.
        assert [c["id"] for c in out["confirmed_items"]] == ["F01"]
        assert out["confirmed_items"][0]["garden_action"] == "file_note"
        # The build_from_wire announcement must NOT appear (report path taken).
        assert "edited wire is authoritative" not in captured.err


# ---------------------------------------------------------------------------
# _is_wire_edited — the single-load digest gate main() routes on (W1). No file
# read; operates on an already-loaded dict.
# ---------------------------------------------------------------------------

class TestIsWireEdited:
    def test_digest_matching_wire_is_not_edited(self):
        wire = _make_real_wire([_unparented(selected=True)])  # correct digest
        assert gap._is_wire_edited(wire) is False

    def test_digest_mismatch_is_edited(self):
        wire = _make_real_wire([_unparented(selected=True)])
        wire["findings"][0]["decision"]["selected"] = False  # digest now stale
        assert gap._is_wire_edited(wire) is True

    def test_wrong_schema_version_is_not_edited(self):
        wire = _make_real_wire([_unparented(selected=True)])
        wire["schema_version"] = "2"
        assert gap._is_wire_edited(wire) is False

    def test_missing_digest_is_edited(self):
        # No stored emit_digest → treat as edited (cannot prove unchanged).
        wire = _make_wire([_unparented(selected=True)])
        wire.pop("emit_digest", None)
        assert gap._is_wire_edited(wire) is True
