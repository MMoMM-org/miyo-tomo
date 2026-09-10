#!/usr/bin/env python3
# version: 0.5.0
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
- an unparseable schema file -> fail with `error_kind ==
  ERROR_SCHEMA_UNREADABLE`, pinned by identity — never collapsed into "no
  changes therefore pass", and never confused with a MALFORMED (valid
  JSON, wrong shape) schema, which is a different kind entirely
- a MISSING manifest -> fail with `error_kind == ERROR_MANIFEST_MISSING`
  and an instruction to generate and commit one, not merely "unreadable"
  (code review, 2026-09-10: this closes T1.2's CON-5 refused-path
  obligation, which test_035_wire_manifests.py explicitly deferred to
  "Phase 2's T2.3")
- a CORRUPT (invalid JSON) manifest -> fail with `error_kind ==
  ERROR_MANIFEST_UNREADABLE` and an instruction to regenerate it
- a manifest that IS valid JSON but missing `nodes` or `schema_version`,
  and a schema that IS valid JSON but missing `properties.schema_version.
  const` -> each fails as a distinct MALFORMED error_kind, never an
  uncaught KeyError (code review, 2026-09-10: the exact bug `b29a9ac`
  fixed for a missing/unreadable manifest, recurring at the "valid JSON,
  wrong shape" trigger the first fix did not cover)
- one wire's manifest broken, of EITHER kind (missing-file or wrong-shape)
  -> `run_wire_gate` still returns a result for ALL wires, the other two
  gated normally. This is the load-bearing half: an uncaught exception
  from one wire's read would abort the whole loop and silently suppress
  the other wires' obligations — exactly what design decision #2 (iterate
  all, report together, never stop at the first) and CON-4's independent
  counters exist to prevent
- every failure branch's RENDERED message ends in an actual instruction
  line, error branches included — not just a diagnosis (code review,
  2026-09-10: "a message that says what to do" was true on the shape-diff
  branches and false on the error branches)
- render_wire_gate_report RAISES on an action or an error_kind it has no
  instruction for, rather than silently rendering nothing or inferring one
  by absence — the same exhaustiveness discipline CHANGE_KINDS/classify
  already enforce in wire_shape.py, applied here to ACTIONS/ERROR_KINDS
- `_result` ALSO raises at CONSTRUCTION time for an unregistered action or
  error_kind, independent of whether anything ever renders the result —
  closing the half `_render_action`/`_render_error` cannot reach on their
  own (code review, 2026-09-10)
- a THIRD loop-abort trigger (code review, 2026-09-10, after the missing-
  file and missing-top-level-key triggers already closed): valid JSON,
  valid top-level keys, but one node's VALUE inside `nodes` is not a dict,
  or a node's `values` field specifically is a non-dict truthy value —
  each fails as ERROR_MANIFEST_MALFORMED and does not abort gating the
  other wires. The validation set was DERIVED by tracing every
  `manifest`-sourced dereference in wire_shape.py's `_diff_node`, not by
  patching the crash last observed — see wire_gate.md
- two wires mutated in one edit -> both reported in one `run_wire_gate`
  call, each against its own independent result — the third, untouched wire
  still passes in the same run
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
SHAPES_DIR = SCHEMAS_DIR / "shapes"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.wire_gate import (  # noqa: E402
    ACTION_HANDOVER,
    ACTION_MOVE_VERSION,
    ACTION_REGENERATE_MANIFEST,
    ACTIONS,
    ERROR_KINDS,
    ERROR_MANIFEST_MALFORMED,
    ERROR_MANIFEST_MISSING,
    ERROR_MANIFEST_UNREADABLE,
    ERROR_SCHEMA_MALFORMED,
    ERROR_SCHEMA_UNREADABLE,
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
    # Pinned by IDENTITY, not by substring — this is specifically the
    # schema-unreadable kind, never confused with a malformed schema (valid
    # JSON, wrong shape) or any of the manifest error kinds.
    assert result["error_kind"] == ERROR_SCHEMA_UNREADABLE
    # Structurally distinct from the "no change" pass shape: a pass ALWAYS
    # carries affecting=False; this carries affecting=None, so the two
    # cannot be confused by a caller checking `affecting is False`.
    assert result["affecting"] is None
    assert result["changes"] == []
    assert result["actions"] == []

    message = render_wire_gate_report([result])
    assert document in message
    # An actual instruction, not just a diagnosis — the renderer's promise
    # applies to error branches too.
    assert "fix" in message.lower()


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
    assert result["error_kind"] == ERROR_MANIFEST_MISSING
    # Same structural shape as the unparseable-schema case, so a caller
    # branching on `affecting is False` never mistakes this for a pass.
    assert result["affecting"] is None
    assert result["changes"] == []
    assert result["actions"] == []

    message = render_wire_gate_report([result])
    assert document in message
    assert "missing" in message.lower()
    # The instruction for a MISSING manifest is distinct from the
    # instruction for an unreadable/malformed one — "generate and commit",
    # not "regenerate" a file that does not exist yet.
    assert "generate" in message.lower()
    assert "commit" in message.lower()


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
    assert result["error_kind"] == ERROR_MANIFEST_UNREADABLE
    assert result["error_kind"] != ERROR_MANIFEST_MISSING  # distinct kind, not just distinct prose
    assert result["affecting"] is None
    assert result["changes"] == []
    assert result["actions"] == []

    message = render_wire_gate_report([result])
    assert "regenerate" in message.lower()
    assert "commit" not in message.lower()  # the missing-manifest instruction, not this one


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
    assert by_document[suggestions]["error_kind"] == ERROR_MANIFEST_MISSING

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


# ──────────────────────────────────────────────────────────────────────────────
# CRITICAL (code review, 2026-09-10): the same loop-abort bug b29a9ac fixed
# for a missing/unreadable manifest, recurring at a trigger that fix did not
# cover — valid JSON, WRONG SHAPE. `manifest["nodes"]`,
# `manifest["schema_version"]`, and `schema["properties"]["schema_version"]
# ["const"]` were all unguarded; an empty stub, another wire's manifest
# copy-pasted, or a hand-edit that drops a key raised an uncaught KeyError
# from inside gate_one_wire, which — same mechanism as the missing-file
# case — aborted run_wire_gate's loop and silently suppressed the other two
# wires' results. Fixed by explicit shape validation BEFORE
# describe_shape/diff_shapes/classify ever run, never by a blanket
# `except KeyError` (which would also swallow a genuine bug from inside
# those pure functions).
# ──────────────────────────────────────────────────────────────────────────────

def test_manifest_missing_nodes_key_fails_as_malformed_not_an_uncaught_error(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "instructions.schema.json"

    _rewrite_json(shapes_dir / manifest_filename(document), lambda manifest: manifest.pop("nodes"))

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["error"] is not None
    assert "nodes" in result["error"].lower()
    assert result["error_kind"] == ERROR_MANIFEST_MALFORMED
    assert result["affecting"] is None
    assert result["changes"] == []
    assert result["actions"] == []

    message = render_wire_gate_report([result])
    assert "regenerate" in message.lower()


def test_schema_missing_properties_key_fails_as_malformed_not_an_uncaught_error(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "instructions.schema.json"

    _rewrite_json(schemas_dir / document, lambda schema: schema.pop("properties"))

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["error"] is not None
    assert "properties" in result["error"].lower()
    assert result["error_kind"] == ERROR_SCHEMA_MALFORMED
    assert result["error_kind"] != ERROR_SCHEMA_UNREADABLE  # valid JSON — a DIFFERENT kind
    assert result["affecting"] is None
    assert result["changes"] == []
    assert result["actions"] == []

    message = render_wire_gate_report([result])
    assert "fix" in message.lower()


def test_wrong_shape_manifest_and_schema_do_not_abort_gating_the_other_wires(tmp_path):
    # Mirrors test_one_broken_manifest_does_not_abort_gating_the_other_wires,
    # but for the "valid JSON, wrong shape" trigger rather than a missing
    # file — the trigger the first fix (b29a9ac) did not cover. Breaks TWO
    # wires, each a different malformed-shape flavor, in one run.
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)

    suggestions = "suggestions-wire.schema.json"
    garden_audit = "garden-audit-wire.schema.json"
    instructions = "instructions.schema.json"

    _rewrite_json(shapes_dir / manifest_filename(suggestions), lambda manifest: manifest.pop("nodes"))
    _rewrite_json(schemas_dir / garden_audit, lambda schema: schema.pop("properties"))
    # instructions is left untouched — it should still be gated normally.

    results = run_wire_gate(schemas_dir, shapes_dir)
    by_document = {result["document"]: result for result in results}

    # The whole point: a result exists for EVERY wire, including both
    # broken ones — the loop did not abort partway through either trigger.
    assert set(by_document) == {suggestions, garden_audit, instructions}

    assert by_document[suggestions]["passed"] is False
    assert by_document[suggestions]["error_kind"] == ERROR_MANIFEST_MALFORMED

    assert by_document[garden_audit]["passed"] is False
    assert by_document[garden_audit]["error_kind"] == ERROR_SCHEMA_MALFORMED

    # Untouched, so it gates normally — proving neither broken wire
    # suppressed it.
    assert by_document[instructions]["passed"] is True
    assert by_document[instructions]["changes"] == []


# ──────────────────────────────────────────────────────────────────────────────
# CRITICAL, third round (code review, 2026-09-10): the same loop-abort defect
# at a THIRD trigger — valid JSON, valid top-level keys, but one node's
# VALUE inside `nodes` is not a dict. `manifest["nodes"][pointer]` flows
# into wire_shape.py's `_diff_node` as `old`, which calls `.get(...)` on it
# directly — a non-dict node value raised an uncaught AttributeError,
# aborting run_wire_gate's loop exactly like the first two triggers did.
# Derived (not observed-and-patched) alongside it: a node's `values` field
# specifically needs the SAME check, because `_diff_node`'s enum diff calls
# `.get(name, [])` on it a SECOND time — see wire_gate.md's "WHY the
# Validation Set Is Derived From Dereferences" for the full trace and why
# `properties`/`required`/`closed` do NOT need the same treatment.
# ──────────────────────────────────────────────────────────────────────────────

def test_manifest_node_value_not_a_dict_does_not_abort_gating_the_other_wires(tmp_path):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)

    suggestions = "suggestions-wire.schema.json"
    garden_audit = "garden-audit-wire.schema.json"
    instructions = "instructions.schema.json"

    # Corrupt ONE EXISTING node's VALUE (not a top-level manifest key) —
    # the root pointer "" always exists in every published wire's manifest.
    _rewrite_json(
        shapes_dir / manifest_filename(suggestions),
        lambda manifest: manifest["nodes"].__setitem__("", "not-a-dict"),
    )
    # garden_audit and instructions are left untouched — both should still
    # be gated normally in the same run.

    results = run_wire_gate(schemas_dir, shapes_dir)
    by_document = {result["document"]: result for result in results}

    # The whole point: a result exists for EVERY wire, including the
    # corrupted one — the loop did not abort partway through.
    assert set(by_document) == {suggestions, garden_audit, instructions}

    assert by_document[suggestions]["passed"] is False
    assert by_document[suggestions]["error"] is not None
    assert by_document[suggestions]["error_kind"] == ERROR_MANIFEST_MALFORMED
    assert "not a json object" in by_document[suggestions]["error"].lower()
    assert by_document[suggestions]["affecting"] is None
    assert by_document[suggestions]["changes"] == []
    assert by_document[suggestions]["actions"] == []

    # The other two wires were never touched, so they gate normally —
    # proving the corrupted node did not suppress them.
    assert by_document[garden_audit]["passed"] is True
    assert by_document[garden_audit]["changes"] == []
    assert by_document[instructions]["passed"] is True
    assert by_document[instructions]["changes"] == []


def test_manifest_node_values_field_not_a_dict_fails_as_malformed(tmp_path):
    # The SECOND-LEVEL dereference _diff_node makes, distinct from the
    # node-itself check above: a node whose `values` field is a non-empty
    # list (truthy, but has no `.get`) crashes one call deeper inside the
    # enum diff, even though the node ITSELF is a well-formed dict.
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    document = "instructions.schema.json"

    _rewrite_json(
        shapes_dir / manifest_filename(document),
        lambda manifest: manifest["nodes"][""].__setitem__("values", ["not", "a", "dict"]),
    )

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / manifest_filename(document))

    assert result["passed"] is False
    assert result["error"] is not None
    assert result["error_kind"] == ERROR_MANIFEST_MALFORMED
    assert "values" in result["error"].lower()
    assert result["affecting"] is None
    assert result["changes"] == []
    assert result["actions"] == []


# ──────────────────────────────────────────────────────────────────────────────
# ACTIONS/ERROR_KINDS exhaustiveness — same discipline CHANGE_KINDS/classify
# already enforce in wire_shape.py, applied here (code review, 2026-09-10):
# an unrecognised action used to be rendered by ABSENCE-of-move_version
# inference rather than raising, which a review found the more fragile
# shape than wire_shape.py's raise-on-unknown-kind mechanism.
# ──────────────────────────────────────────────────────────────────────────────

def test_actions_has_exactly_the_three_documented_actions():
    assert set(ACTIONS) == {ACTION_MOVE_VERSION, ACTION_HANDOVER, ACTION_REGENERATE_MANIFEST}
    assert len(ACTIONS) == len(set(ACTIONS)), "ACTIONS has a duplicate"


def test_error_kinds_has_exactly_the_five_documented_kinds():
    assert set(ERROR_KINDS) == {
        ERROR_SCHEMA_UNREADABLE,
        ERROR_SCHEMA_MALFORMED,
        ERROR_MANIFEST_MISSING,
        ERROR_MANIFEST_UNREADABLE,
        ERROR_MANIFEST_MALFORMED,
    }
    assert len(ERROR_KINDS) == len(set(ERROR_KINDS)), "ERROR_KINDS has a duplicate"


def test_render_wire_gate_report_raises_on_an_unregistered_action():
    # A hand-built result standing in for a future bug: an action added to
    # a wire's `actions` list without a matching ACTION_INSTRUCTIONS entry.
    # Never reachable through gate_one_wire itself today — this is the
    # exhaustiveness guard for if that ever drifts.
    fake_result = {
        "document": "fake-wire.schema.json",
        "passed": False,
        "error": None,
        "error_kind": None,
        "changes": [],
        "affecting": True,
        "schema_version": "1",
        "manifest_version": "1",
        "version_moved": False,
        "actions": ["moved_to_a_new_planet"],
    }
    with pytest.raises(ValueError):
        render_wire_gate_report([fake_result])


def test_render_wire_gate_report_raises_on_an_unregistered_error_kind():
    fake_result = {
        "document": "fake-wire.schema.json",
        "passed": False,
        "error": "fake error for this test",
        "error_kind": "moved_to_a_new_planet",
        "changes": [],
        "affecting": None,
        "schema_version": None,
        "manifest_version": None,
        "version_moved": None,
        "actions": [],
    }
    with pytest.raises(ValueError):
        render_wire_gate_report([fake_result])


# ──────────────────────────────────────────────────────────────────────────────
# The construction-site half of the SAME exhaustiveness mechanism (code
# review, 2026-09-10): `_render_action`/`_render_error` above only raise
# when something actually RENDERS a result. A caller that reads
# `actions`/`error_kind` directly (T4.1's CLI, potentially, branching on
# `error_kind` identity without ever calling render_wire_gate_report) would
# see an unregistered value sail through unnoticed. `_result` validates at
# the moment every WireGateResult is BUILT — the same moment
# wire_shape.py's `_change` validates `kind` against `CHANGE_KINDS`.
# ──────────────────────────────────────────────────────────────────────────────

def test_result_raises_at_construction_for_an_unregistered_action():
    import lib.wire_gate as wire_gate

    with pytest.raises(ValueError):
        wire_gate._result("fake-wire.schema.json", passed=False, actions=["moved_to_a_new_planet"])


def test_result_raises_at_construction_for_an_unregistered_error_kind():
    import lib.wire_gate as wire_gate

    with pytest.raises(ValueError):
        wire_gate._result(
            "fake-wire.schema.json",
            passed=False,
            error="fake error for this test",
            error_kind="moved_to_a_new_planet",
        )
