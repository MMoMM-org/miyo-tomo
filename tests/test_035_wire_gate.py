#!/usr/bin/env python3
# version: 0.3.0
"""test_035_wire_gate.py — Behavioural tests for lib.wire_gate: diff +
classify + version-check, per published wire (spec 035 T2.3).

Separate from test_035_wire_{shape,diff,classify}.py on purpose, same split
rationale as the rest of the 035 suite: those exercise the pure building
blocks (describe_shape / diff_shapes / classify) in isolation; this file
exercises the thing that DRIVES them — reading a schema and a manifest off
disk, running the SDD/Complex Logic algorithm, and deciding pass or fail.

**Production code moved to tomo/scripts/lib/wire_gate.py (code review,
2026-09-10).** It started here, matching the T2.3 plan's literal "put it in
its own file — tests/test_035_wire_gate.py" instruction, but T4.1's CLI
needs the same gate to avoid production code importing from a test module
or reimplementing a second, potentially-drifting drift detector. See
docs/tomo/scripts/lib/wire_gate.md for the full module-split reasoning; this
file now holds only the scratch-copy fixtures and the tests themselves.

**The trap this file exists to not fall into:** the committed manifests
match the live schemas today, so "no change -> pass silently" is the
honest, currently-true answer — and a gate that unconditionally passes is
EQUALLY green against that same real tree. Every failure case below is
therefore proven against a scratch copy built by `_make_scratch_wires`,
mutated in memory and written to a pytest tmp_path — never against a
committed schema or manifest file in place.

Tests cover:
- affecting change + version unmoved -> fail, naming the document, the
  pointer, the property, and demanding BOTH a version move and a handover
- the same shape, replayed as spec 034's actual drift (item_key removed
  from a scratch copy of the suggestions-wire manifest) -> fail the same way
  (this doubles as the T2.3 brief's mandatory counterfactual sanity check)
- affecting change + version moved AND manifest regenerated -> pass
- non-affecting change (open-node addition) -> fail, demanding manifest
  regeneration ONLY — the version-move/handover actions are asserted ABSENT,
  not merely "regeneration present"
- no change, run against the REAL committed tree -> pass silently for all
  three wires (this doubles as the T2.3 brief's mandatory today-is-green
  sanity check)
- an unparseable schema file -> fail with a distinct error marker, never
  collapsed into "no changes therefore pass"
- a MISSING manifest -> fail with a distinct error marker naming it as
  missing, not merely "unreadable" (code review, 2026-09-10: this closes
  T1.2's CON-5 refused-path obligation, which test_035_wire_manifests.py
  explicitly deferred to "Phase 2's T2.3")
- a CORRUPT manifest -> fail with a distinct error marker, same shape as
  the unparseable-schema case
- one wire's manifest broken -> `run_wire_gate` still returns a result for
  ALL wires, the other two gated normally. This is the load-bearing half:
  an uncaught exception from one wire's read would abort the whole loop
  and silently suppress the other wires' obligations — exactly what design
  decision #2 (iterate all, report together, never stop at the first) and
  CON-4's independent counters exist to prevent
- two wires mutated in one edit -> both reported in one `run_wire_gate`
  call, each against its own independent result — the third, untouched wire
  still passes in the same run
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
SHAPES_DIR = SCHEMAS_DIR / "shapes"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.wire_gate import (  # noqa: E402
    ACTION_HANDOVER,
    ACTION_MOVE_VERSION,
    ACTION_REGENERATE_MANIFEST,
    gate_one_wire,
    manifest_filename,
    render_wire_gate_report,
    run_wire_gate,
)
from lib.wire_shape import PUBLISHED_WIRES  # noqa: E402

# ──────────────────────────────────────────────────────────────────────────────
# Scratch-copy fixtures — NEVER mutate a committed schema or manifest in place
# ──────────────────────────────────────────────────────────────────────────────

def _make_scratch_wires(tmp_path: Path) -> tuple[Path, Path]:
    """Copy the three published wires' schemas and committed manifests into
    `tmp_path`, mirroring just enough of the real `tomo/schemas/` layout for
    `gate_one_wire`/`run_wire_gate` to read from. Tests mutate these COPIES;
    the files under `tomo/schemas/` are never touched.
    """
    schemas_dir = tmp_path / "schemas"
    shapes_dir = schemas_dir / "shapes"
    shapes_dir.mkdir(parents=True)
    for document in PUBLISHED_WIRES:
        shutil.copy(SCHEMAS_DIR / document, schemas_dir / document)
        manifest_name = manifest_filename(document)
        shutil.copy(SHAPES_DIR / manifest_name, shapes_dir / manifest_name)
    return schemas_dir, shapes_dir


def _rewrite_json(path: Path, mutate) -> dict:
    """Load, mutate in place via the callback, write back. Returns the
    mutated dict so a test can assert against it without re-reading.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


# ──────────────────────────────────────────────────────────────────────────────
# no change -> pass silently, run against the REAL committed tree
# (T2.3 brief's mandatory sanity check 1: the gate is green on the repo today)
# ──────────────────────────────────────────────────────────────────────────────

def test_gate_passes_silently_on_the_real_committed_tree():
    results = run_wire_gate(SCHEMAS_DIR, SHAPES_DIR)

    assert len(results) == len(PUBLISHED_WIRES) == 3
    for result in results:
        assert result["passed"] is True, result
        assert result["changes"] == []
        assert result["error"] is None
        assert result["actions"] == []

    # "Pass silently": the rendered report for an all-green run is empty.
    assert render_wire_gate_report(results) == ""


# ──────────────────────────────────────────────────────────────────────────────
# affecting change + version unmoved -> fail, naming document/pointer/property,
# demanding BOTH a version move and a handover
# ──────────────────────────────────────────────────────────────────────────────

def test_affecting_change_with_version_unmoved_fails_and_demands_both_actions(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "suggestions-wire.schema.json"

    # /properties/suggestions/items is closed (additionalProperties: false) —
    # an added property there is consumer-affecting (PRD F2-AC1). The
    # manifest copy is left untouched, so it still records the pre-mutation
    # shape and the schema_version is untouched too (version unmoved).
    _rewrite_json(
        schemas_dir / document,
        lambda schema: schema["properties"]["suggestions"]["items"]["properties"].__setitem__(
            "scratch_gate_probe", {"type": "string"},
        ),
    )

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["error"] is None
    assert result["document"] == document
    assert result["affecting"] is True
    assert result["version_moved"] is False
    assert result["actions"] == [ACTION_MOVE_VERSION, ACTION_HANDOVER]

    pointer = "/properties/suggestions/items"
    matching = [c for c in result["changes"] if c["pointer"] == pointer and c["kind"] == "added_property"]
    assert len(matching) == 1
    assert "scratch_gate_probe" in matching[0]["detail"]
    assert matching[0]["consumer_affecting"] is True

    # The rendered message names all of it too — one of the "one or two
    # tests cover the rendering itself" the plan asks for.
    message = render_wire_gate_report([result])
    assert document in message
    assert pointer in message
    assert "scratch_gate_probe" in message
    assert "move" in message.lower()
    assert "hand over" in message.lower() or "handover" in message.lower()


# ──────────────────────────────────────────────────────────────────────────────
# The counterfactual named by the T2.3 brief's mandatory sanity check 2:
# item_key removed from a scratch copy of the suggestions-wire MANIFEST
# (simulating the pre-034 baseline), live schema left untouched.
# ──────────────────────────────────────────────────────────────────────────────

def test_counterfactual_item_key_missing_from_manifest_fails_as_affecting(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "suggestions-wire.schema.json"
    pointer = "/properties/suggestions/items"

    _rewrite_json(
        shapes_dir / manifest_filename(document),
        lambda manifest: (
            manifest["nodes"][pointer]["properties"].pop("item_key"),
            manifest["nodes"][pointer].__setitem__(
                "required",
                [name for name in manifest["nodes"][pointer]["required"] if name != "item_key"],
            ),
        ),
    )

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["affecting"] is True
    assert result["actions"] == [ACTION_MOVE_VERSION, ACTION_HANDOVER]

    matching = [c for c in result["changes"] if c["pointer"] == pointer]
    assert any(c["kind"] == "added_property" and "item_key" in c["detail"] for c in matching)
    assert any(c["consumer_affecting"] for c in matching)


# ──────────────────────────────────────────────────────────────────────────────
# affecting change + version moved (schema bumped AND manifest regenerated
# against it) -> pass
# ──────────────────────────────────────────────────────────────────────────────

def test_affecting_change_with_version_moved_and_manifest_regenerated_passes(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "suggestions-wire.schema.json"

    from lib.wire_shape import build_manifest, serialize_manifest

    schema = _rewrite_json(
        schemas_dir / document,
        lambda schema: (
            schema["properties"]["suggestions"]["items"]["properties"].__setitem__(
                "scratch_gate_probe", {"type": "string"},
            ),
            schema["properties"]["schema_version"].__setitem__("const", "2"),
        ),
    )

    # The maintainer's full procedure: bump the version, THEN regenerate the
    # manifest against the now-current schema. After that, the two sides
    # are identical again and diff_shapes has nothing left to report.
    manifest_path = shapes_dir / manifest_filename(document)
    manifest_path.write_text(
        serialize_manifest(build_manifest(schema, source=f"tomo/schemas/{document}")),
        encoding="utf-8",
    )

    result = gate_one_wire(document, schemas_dir / document, manifest_path)

    assert result["passed"] is True
    assert result["changes"] == []
    assert result["actions"] == []
    assert result["schema_version"] == "2"
    assert result["manifest_version"] == "2"
    assert result["version_moved"] is False  # already moved on BOTH sides — nothing left to compare


# ──────────────────────────────────────────────────────────────────────────────
# non-affecting change -> fail, demanding regeneration ONLY. The version
# demand is asserted ABSENT — PRD F7-AC2 — not merely "regeneration present".
# ──────────────────────────────────────────────────────────────────────────────

def test_non_affecting_change_fails_and_demands_regeneration_only(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "garden-audit-wire.schema.json"

    # findings/items/properties/detail is OPEN (additionalProperties not
    # declared as false) — the live garden-audit case named throughout the
    # spec. An added property there is a subset of what a consumer already
    # accepts, so classify() says not-affecting.
    _rewrite_json(
        schemas_dir / document,
        lambda schema: schema["properties"]["findings"]["items"]["properties"]["detail"][
            "properties"
        ].__setitem__("scratch_gate_probe", {"type": "string"}),
    )

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["affecting"] is False
    assert result["actions"] == [ACTION_REGENERATE_MANIFEST]

    # Structural absence, not just "regeneration is present" — a message
    # asking for both would pass a presence-only test while telling the
    # maintainer to do something the rule says is unnecessary.
    assert ACTION_MOVE_VERSION not in result["actions"]
    assert ACTION_HANDOVER not in result["actions"]

    message = render_wire_gate_report([result])
    assert "regenerate" in message.lower()
    assert "move" not in message.lower()
    assert "hand over" not in message.lower() and "handover" not in message.lower()


# ──────────────────────────────────────────────────────────────────────────────
# unparseable schema -> fail, never treated as "no change"
# ──────────────────────────────────────────────────────────────────────────────

def test_unparseable_schema_fails_and_is_never_treated_as_no_change(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "instructions.schema.json"

    (schemas_dir / document).write_text("{ this is not valid json", encoding="utf-8")

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["error"] is not None
    # Structurally distinct from the "no change" pass shape: a pass ALWAYS
    # carries affecting=False; this carries affecting=None, so the two
    # cannot be confused by a caller checking `affecting is False`.
    assert result["affecting"] is None
    assert result["changes"] == []
    assert result["actions"] == []

    message = render_wire_gate_report([result])
    assert document in message
    assert message != ""


# ──────────────────────────────────────────────────────────────────────────────
# missing manifest -> fail with a distinct error marker (SDD/Error Handling:
# "Manifest missing for a published wire -> fail... silence would reproduce
# it"). This closes T1.2's CON-5 refused-path obligation, which
# test_035_wire_manifests.py deliberately left as intent-documentation for
# "Phase 2's T2.3" to carry (code review, 2026-09-10).
# ──────────────────────────────────────────────────────────────────────────────

def test_missing_manifest_fails_with_a_distinct_error_marker(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "instructions.schema.json"

    (shapes_dir / manifest_filename(document)).unlink()

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["error"] is not None
    assert "missing" in result["error"].lower()
    # Same structural shape as the unparseable-schema case, so a caller
    # branching on `affecting is False` never mistakes this for a pass.
    assert result["affecting"] is None
    assert result["changes"] == []
    assert result["actions"] == []

    message = render_wire_gate_report([result])
    assert document in message
    assert "missing" in message.lower()


# ──────────────────────────────────────────────────────────────────────────────
# corrupt manifest -> fail with a distinct error marker, same shape as the
# unparseable-schema case but naming the manifest, not the schema.
# ──────────────────────────────────────────────────────────────────────────────

def test_corrupt_manifest_fails_with_a_distinct_error_marker(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "instructions.schema.json"

    (shapes_dir / manifest_filename(document)).write_text("{ this is not valid json", encoding="utf-8")

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["error"] is not None
    assert "manifest" in result["error"].lower()
    assert "missing" not in result["error"].lower()  # distinct from the missing-file case above
    assert result["affecting"] is None
    assert result["changes"] == []
    assert result["actions"] == []


# ──────────────────────────────────────────────────────────────────────────────
# The load-bearing half (code review, 2026-09-10): a broken manifest must
# NOT abort run_wire_gate's loop. Before this guard, an uncaught exception
# reading one wire's manifest propagated out of the loop and silently
# suppressed the other two wires' results entirely — the opposite of design
# decision #2 (iterate all, report every failure together, never stop at
# the first) and CON-4's independent-counters requirement.
# ──────────────────────────────────────────────────────────────────────────────

def test_one_broken_manifest_does_not_abort_gating_the_other_wires(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)

    suggestions = "suggestions-wire.schema.json"
    garden_audit = "garden-audit-wire.schema.json"
    instructions = "instructions.schema.json"

    (shapes_dir / manifest_filename(suggestions)).unlink()
    # garden_audit and instructions are left untouched — both should still
    # be gated normally in the same run.

    results = run_wire_gate(schemas_dir, shapes_dir)
    by_document = {result["document"]: result for result in results}

    # The whole point: a result exists for EVERY wire, including the broken
    # one — the loop did not abort partway through.
    assert set(by_document) == {suggestions, garden_audit, instructions}

    assert by_document[suggestions]["passed"] is False
    assert by_document[suggestions]["error"] is not None
    assert "missing" in by_document[suggestions]["error"].lower()

    # The other two wires were never touched, so they gate normally —
    # proving the broken wire did not suppress them.
    assert by_document[garden_audit]["passed"] is True
    assert by_document[garden_audit]["changes"] == []
    assert by_document[instructions]["passed"] is True
    assert by_document[instructions]["changes"] == []


# ──────────────────────────────────────────────────────────────────────────────
# two wires changed in one edit -> both reported, each against its own
# counter, in one run — the untouched third wire still passes
# ──────────────────────────────────────────────────────────────────────────────

def test_two_wires_changed_in_one_edit_are_both_reported_independently(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)

    suggestions = "suggestions-wire.schema.json"
    garden_audit = "garden-audit-wire.schema.json"
    instructions = "instructions.schema.json"

    _rewrite_json(
        schemas_dir / suggestions,
        lambda schema: schema["properties"]["suggestions"]["items"]["properties"].__setitem__(
            "scratch_gate_probe_a", {"type": "string"},
        ),
    )
    _rewrite_json(
        schemas_dir / garden_audit,
        lambda schema: schema["properties"]["findings"]["items"]["properties"]["detail"][
            "properties"
        ].__setitem__("scratch_gate_probe_b", {"type": "string"}),
    )
    # instructions.schema.json is left untouched.

    results = run_wire_gate(schemas_dir, shapes_dir)
    by_document = {result["document"]: result for result in results}

    assert set(by_document) == {suggestions, garden_audit, instructions}

    assert by_document[suggestions]["passed"] is False
    assert by_document[suggestions]["affecting"] is True
    assert by_document[suggestions]["actions"] == [ACTION_MOVE_VERSION, ACTION_HANDOVER]
    assert any(
        "scratch_gate_probe_a" in c["detail"] for c in by_document[suggestions]["changes"]
    )
    # This wire's result names only ITS OWN mutation — the other wire's
    # probe name never leaks in, proving the counters are independent.
    assert not any(
        "scratch_gate_probe_b" in c["detail"] for c in by_document[suggestions]["changes"]
    )

    assert by_document[garden_audit]["passed"] is False
    assert by_document[garden_audit]["affecting"] is False
    assert by_document[garden_audit]["actions"] == [ACTION_REGENERATE_MANIFEST]
    assert any(
        "scratch_gate_probe_b" in c["detail"] for c in by_document[garden_audit]["changes"]
    )
    assert not any(
        "scratch_gate_probe_a" in c["detail"] for c in by_document[garden_audit]["changes"]
    )

    assert by_document[instructions]["passed"] is True
    assert by_document[instructions]["changes"] == []

    # A single rendered report carries both failures and nothing about the
    # untouched wire.
    message = render_wire_gate_report(results)
    assert suggestions in message
    assert garden_audit in message
    # instructions is the bare document name of an untouched, passing wire —
    # it must not appear as a reported failure line.
    assert f"{instructions}:" not in message
