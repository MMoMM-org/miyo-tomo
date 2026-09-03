#!/usr/bin/env python3
# version: 0.1.0
"""test_032_t3_3_edit_frontmatter_emission.py — wiring for broken-up frontmatter
fixes (T3.3).

T3.2 delivered the pure transform (_construct_edit_frontmatter_fields). T3.3 is
the wiring: garden-audit-parser.py threads up_value/up_target/choice onto the
edit_frontmatter confirmed_item (the same way add_relationship carries up_line
and remove_up_link carries link), and
lib.render_actions._build_edit_frontmatter_actions assembles the action dict —
deriving `property` via marker_word(parent_marker) (ADR-6), delegating
value/expected to the T3.2 transform, and leaving `applied` to
build_garden_audit_actions' central stamping loop.

Covers the plan's required matrix (phase-3.md T3.3):
  - a routed finding produces one edit_frontmatter with path/property/operation/
    expected and, for set, value
  - property is derived via marker_word(parent_marker) — a different marker
    yields a different property name (PRD/AC-F2.5, ADR-6)
  - additionalProperties are never added (no stem, no title, no provenance)
  - IDs come from the shared counter, monotonic, across a MIXED batch
  - the emitted set validates against tomo/schemas/instructions.schema.json
  - value presence: 'remove' omits the key entirely, 'set' always carries it
  - end-to-end: the parser threads up_value/up_target/choice through both
    build_from_report and build_from_wire
  - the two T3.2 no-match scalar fallbacks are locked as a deliberate no-op
    (carried over from the T3.2 code-quality review)

Spec: docs/XDD/specs/032-up-source-routing/plan/phase-3.md T3.3
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "instructions.schema.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gap = _load("garden_audit_parser", "garden-audit-parser.py")
gar = _load("garden_audit_render", "garden-audit-render.py")

from lib.render_actions import (  # noqa: E402
    _construct_edit_frontmatter_fields,
    build_garden_audit_actions,
)

build_from_report = gap.build_from_report
build_from_wire = gap.build_from_wire


# ---------------------------------------------------------------------------
# Minimal self-contained fixtures (mirroring test_garden_audit_parser.py's
# helpers — not imported cross-file, since tests/ has no __init__.py package).
# ---------------------------------------------------------------------------

def _wire_finding(fid, check, tier, fixable, path, stem, detail, decision=None):
    f = {
        "id": fid, "check": check, "tier": tier, "fixable": fixable,
        "target": {"path": path, "stem": stem}, "detail": detail,
    }
    if decision is not None:
        f["decision"] = decision
    return f


def _make_wire(findings, schema_version="1", run_id="run-test-001",
               generated="2026-07-20T10:00:00Z", profile="miyo"):
    return {
        "schema_version": schema_version, "run_id": run_id, "generated": generated,
        "profile": profile, "findings": findings,
        "emit_digest": "sha256:" + "a" * 64,
    }


def _broken_up_frontmatter_removal(fid="F01", selected=True):
    return _wire_finding(
        fid, "broken_up", "integrity", True,
        "Notes/Broken.md", "Broken",
        {"up_target": "Deleted MOC", "up_source": "frontmatter",
         "up_value": ["[[Deleted MOC]]"]},
        decision={"selected": selected, "action": "edit_note_text"},
    )


def _make_doc(findings):
    return {
        "run_id": "run-rt-001", "generated": "2026-07-20T12:00:00Z", "profile": "miyo",
        "findings": findings, "skipped_checks": [], "skipped_checks_reason": "",
        "reappeared_exclusions": [],
    }


def _full_report(doc):
    return "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)


def _wire(doc):
    return gar.build_wire_payload(doc)


def _doc_finding_broken_up_frontmatter_repoint(fid="F03"):
    return {
        "id": fid, "check": "broken_up", "tier": "integrity", "fixable": True,
        "target": {"path": "Notes/Repoint Note.md", "stem": "Repoint Note"},
        "detail": {"up_target": "Old MOC", "up_source": "frontmatter",
                   "up_value": ["[[Old MOC]]", "[[Reisen (MOC)]]"]},
        "decision": {"selected": True, "action": "add_relationship"},
    }


def _schema_def_wrapper(defname: str) -> dict:
    """Standalone schema validating instances of one $def directly — mirrors
    test_edit_frontmatter_schema.py's _def_wrapper."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    return {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": f"#/$defs/{defname}"}


def _edit_frontmatter_item(
    fid="F01", *, up_value, up_target="Old MOC", choice, new_target=None,
    path="Notes/Broken.md", stem="Broken",
):
    return {
        "id": fid,
        "garden_check": "broken_up",
        "garden_action": "edit_frontmatter",
        "path": path,
        "stem": stem,
        "up_value": up_value,
        "up_target": up_target,
        "choice": choice,
        "new_target": new_target,
    }


# ---------------------------------------------------------------------------
# 1. A routed finding produces one edit_frontmatter with the right fields.
# ---------------------------------------------------------------------------

def test_repoint_emits_edit_frontmatter_with_set_fields():
    item = _edit_frontmatter_item(
        up_value=["[[Old MOC]]", "[[Reisen (MOC)]]"], choice="repoint",
        new_target="New MOC",
    )
    actions = build_garden_audit_actions([item])
    assert len(actions) == 1
    a = actions[0]
    assert a["action"] == "edit_frontmatter"
    assert a["path"] == "Notes/Broken.md"
    assert a["property"] == "up"
    assert a["operation"] == "set"
    assert a["value"] == ["[[New MOC]]", "[[Reisen (MOC)]]"]
    assert a["expected"] == ["[[Old MOC]]", "[[Reisen (MOC)]]"]


def test_remove_sole_entry_emits_edit_frontmatter_with_remove_operation():
    item = _edit_frontmatter_item(up_value=["[[Old MOC]]"], choice="remove")
    actions = build_garden_audit_actions([item])
    assert len(actions) == 1
    a = actions[0]
    assert a["operation"] == "remove"
    assert a["expected"] == ["[[Old MOC]]"]


# ---------------------------------------------------------------------------
# 2. property is derived via marker_word(parent_marker) — never hardcoded.
# ---------------------------------------------------------------------------

def test_property_name_derives_from_default_up_marker():
    item = _edit_frontmatter_item(up_value=["[[Old MOC]]"], choice="remove")
    actions = build_garden_audit_actions([item])
    assert actions[0]["property"] == "up"


def test_property_name_derives_from_a_different_configured_marker():
    item = _edit_frontmatter_item(up_value=["[[Old MOC]]"], choice="remove")
    actions = build_garden_audit_actions([item], parent_marker="parent::")
    assert actions[0]["property"] == "parent"


# ---------------------------------------------------------------------------
# 3. additionalProperties are never added.
# ---------------------------------------------------------------------------

def test_action_carries_no_stray_fields():
    item = _edit_frontmatter_item(
        up_value=["[[Old MOC]]", "[[Reisen (MOC)]]"], choice="repoint",
        new_target="New MOC",
    )
    actions = build_garden_audit_actions([item])
    a = dict(actions[0])
    a.pop("applied")  # stamped centrally, checked separately below
    assert set(a.keys()) == {"id", "action", "path", "property", "operation", "value", "expected"}
    assert "stem" not in a
    assert "title" not in a
    assert "garden_check" not in a
    assert "garden_action" not in a


# ---------------------------------------------------------------------------
# 4. applied stamped False — the assembler's own docstring warns this branch
#    must be covered by the trailing centralised stamping loop.
# ---------------------------------------------------------------------------

def test_all_actions_including_edit_frontmatter_stamped_applied_false():
    items = [
        _edit_frontmatter_item("F01", up_value=["[[Old MOC]]"], choice="remove"),
        {
            "id": "F02", "garden_check": "broken_up", "garden_action": "add_relationship",
            "path": "Notes/Inline.md", "stem": "Inline", "up_line": "up:: [[New MOC]]",
        },
    ]
    actions = build_garden_audit_actions(items)
    assert len(actions) == 2  # both items must actually produce an action
    for a in actions:
        assert a.get("applied") is False


# ---------------------------------------------------------------------------
# 5. ID ordering over a MIXED batch (add_relationship + edit_frontmatter +
#    file_note) — a filtered-to-one-kind suite would not see drift.
# ---------------------------------------------------------------------------

def test_ids_are_monotonic_over_a_mixed_batch():
    items = [
        {
            "id": "F01", "garden_check": "broken_up", "garden_action": "add_relationship",
            "path": "Notes/Inline.md", "stem": "Inline", "up_line": "up:: [[New MOC]]",
        },
        _edit_frontmatter_item("F02", up_value=["[[Old MOC]]"], choice="remove"),
        {
            "id": "F03", "garden_check": "unparented", "garden_action": "file_note",
            "path": "Notes/Orphan.md", "stem": "Orphan",
            "target_moc": "Writing MOC", "target_moc_path": "MOCs/Writing MOC.md",
        },
    ]
    actions = build_garden_audit_actions(items)
    # add_relationship(1) + edit_frontmatter(1) + file_note's link_to_moc +
    # add_relationship(2) = 4 — an item silently dropped would under-count.
    assert len(actions) == 4
    ids = [int(a["id"].lstrip("I")) for a in actions]
    assert ids == sorted(ids)
    assert ids == list(range(1, len(ids) + 1))


# ---------------------------------------------------------------------------
# 6. value presence — the schema will not catch a superfluous `value` on a
#    remove, so this must be a field-by-field assertion.
# ---------------------------------------------------------------------------

def test_remove_operation_omits_value_key_entirely():
    item = _edit_frontmatter_item(up_value=["[[Old MOC]]"], choice="remove")
    a = build_garden_audit_actions([item])[0]
    assert "value" not in a


def test_set_operation_always_carries_value_key():
    item = _edit_frontmatter_item(
        up_value=["[[Old MOC]]", "[[Reisen (MOC)]]"], choice="repoint",
        new_target="New MOC",
    )
    a = build_garden_audit_actions([item])[0]
    assert "value" in a


# ---------------------------------------------------------------------------
# 7. Schema validation — additionalProperties:false catches a stray field a
#    per-field assertion never would.
# ---------------------------------------------------------------------------

def test_emitted_set_action_validates_against_real_schema():
    item = _edit_frontmatter_item(
        up_value=["[[Old MOC]]", "[[Reisen (MOC)]]"], choice="repoint",
        new_target="New MOC",
    )
    a = build_garden_audit_actions([item])[0]
    jsonschema.validate(instance=a, schema=_schema_def_wrapper("edit_frontmatter"))


def test_emitted_remove_action_validates_against_real_schema():
    item = _edit_frontmatter_item(up_value=["[[Old MOC]]"], choice="remove")
    a = build_garden_audit_actions([item])[0]
    jsonschema.validate(instance=a, schema=_schema_def_wrapper("edit_frontmatter"))


# ---------------------------------------------------------------------------
# 8. Data threading — the parser enriches the confirmed_item, both sites.
# ---------------------------------------------------------------------------

def test_build_from_report_threads_up_value_up_target_choice():
    doc = _make_doc([_doc_finding_broken_up_frontmatter_repoint("F03")])
    md = _full_report(doc)
    md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[New MOC]]", 1)
    items = build_from_report(md, _wire(doc))["confirmed_items"]
    assert len(items) == 1
    c = items[0]
    assert c["garden_action"] == "edit_frontmatter"
    assert c["up_value"] == ["[[Old MOC]]", "[[Reisen (MOC)]]"]
    assert c["up_target"] == "Old MOC"
    assert c["choice"] == "repoint"
    assert c["new_target"] == "New MOC"


def test_build_from_wire_threads_up_value_up_target_choice():
    items = build_from_wire(
        _make_wire([_broken_up_frontmatter_removal(selected=True)])
    )["confirmed_items"]
    assert len(items) == 1
    c = items[0]
    assert c["garden_action"] == "edit_frontmatter"
    assert c["up_value"] == ["[[Deleted MOC]]"]
    assert c["up_target"] == "Deleted MOC"
    assert c["choice"] == "remove"


def test_end_to_end_report_to_action_repoints_frontmatter():
    doc = _make_doc([_doc_finding_broken_up_frontmatter_repoint("F03")])
    md = _full_report(doc)
    md = md.replace("**Repoint to:** [[]]", "**Repoint to:** [[New MOC]]", 1)
    items = build_from_report(md, _wire(doc))["confirmed_items"]
    actions = build_garden_audit_actions(items)
    assert len(actions) == 1
    a = actions[0]
    assert a["action"] == "edit_frontmatter"
    assert a["operation"] == "set"
    assert a["value"] == ["[[New MOC]]", "[[Reisen (MOC)]]"]
    assert a["expected"] == ["[[Old MOC]]", "[[Reisen (MOC)]]"]
    assert a["applied"] is False


# ---------------------------------------------------------------------------
# 9. T3.2 code-quality carryover: the two scalar no-match fallbacks are a
#    deliberate no-op edit (fail-safe), not an accident. Locked with a test —
#    a genuine cache/note mismatch must never crash the pipeline, and must
#    never silently transform a value it does not recognise.
# ---------------------------------------------------------------------------

def test_scalar_repoint_no_match_is_a_no_op_not_a_crash():
    fields = _construct_edit_frontmatter_fields(
        "[[Unrelated MOC]]", "Old MOC", "repoint", new_target="New MOC",
    )
    assert fields["operation"] == "set"
    assert fields["value"] == "[[Unrelated MOC]]"  # unchanged — no match, no guess
    assert fields["expected"] == "[[Unrelated MOC]]"


def test_scalar_remove_no_match_is_a_no_op_not_a_crash():
    fields = _construct_edit_frontmatter_fields(
        "[[Unrelated MOC]]", "Old MOC", "remove",
    )
    assert fields["operation"] == "set"
    assert fields["value"] == "[[Unrelated MOC]]"  # unchanged — no match, no guess
    assert fields["expected"] == "[[Unrelated MOC]]"


# ---------------------------------------------------------------------------
# 9. CONTRACT — up_value survives the whole cache→wire path unnormalised.
#
# Hashi's `expected` comparison is deepEqual over the parsed YAML value, and
# for arrays it is element-wise AND ORDER-SENSITIVE ([A,B] does not match
# [B,A]) so the guard cannot pass on a note someone reordered. Confirmed by
# Hashi 2026-09-03 against editFrontmatter.ts. A normalising "cleanup"
# anywhere on our path would therefore fail every guard at APPLY time in a
# user's vault while the suite stayed green.
#
# The pure transform is already covered in test_032_t3_2. These assert the
# END-TO-END path — report/wire → parser → confirmed_item → built action —
# with a list whose observed order differs from sorted order, so a sort
# introduced at ANY hop is caught, not just one inside the transform.
# ---------------------------------------------------------------------------

_UNSORTED = ["[[Zeta MOC]]", "[[Alpha MOC]]", "[[Mid MOC]]"]


def _assert_order_preserved(action, observed):
    assert action["expected"] == observed, (
        "expected must equal the observed value element-wise and in order"
    )
    assert action["expected"] != sorted(observed), (
        "a sorted expected would pass a set-comparison but fail Hashi's "
        "order-sensitive deepEqual at apply time"
    )


def test_wire_path_preserves_up_value_order_end_to_end():
    item = _broken_up_frontmatter_removal(selected=True)
    item["detail"]["up_value"] = list(_UNSORTED)
    item["detail"]["up_target"] = "Zeta MOC"
    items = build_from_wire(_make_wire([item]))["confirmed_items"]
    assert len(items) == 1
    assert items[0]["up_value"] == _UNSORTED

    actions = build_garden_audit_actions(items)
    assert len(actions) == 1
    _assert_order_preserved(actions[0], _UNSORTED)


def test_report_path_preserves_up_value_order_end_to_end():
    finding = _doc_finding_broken_up_frontmatter_repoint("F03")
    finding["detail"]["up_value"] = list(_UNSORTED)
    finding["detail"]["up_target"] = "Zeta MOC"
    doc = _make_doc([finding])
    md = _full_report(doc).replace(
        "**Repoint to:** [[]]", "**Repoint to:** [[New MOC]]", 1
    )
    items = build_from_report(md, _wire(doc))["confirmed_items"]
    assert len(items) == 1
    assert items[0]["up_value"] == _UNSORTED

    actions = build_garden_audit_actions(items)
    assert len(actions) == 1
    a = actions[0]
    _assert_order_preserved(a, _UNSORTED)
    # value is transformed in place at the broken index — the surviving
    # entries keep their positions, they are not rebuilt from a set.
    assert a["value"] == ["[[New MOC]]", "[[Alpha MOC]]", "[[Mid MOC]]"]
