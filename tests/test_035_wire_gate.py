#!/usr/bin/env python3
# version: 0.1.0
"""test_035_wire_gate.py — The gate: diff + classify + version-check, per
published wire (spec 035 T2.3).

Separate from test_035_wire_{shape,diff,classify}.py on purpose, same split
rationale as the rest of the 035 suite: those exercise the pure building
blocks (describe_shape / diff_shapes / classify) in isolation; this file
exercises the thing that DRIVES them — reading a schema and a manifest off
disk, running the SDD/Complex Logic algorithm, and deciding pass or fail.

**Module-split note (docs/tomo/scripts/lib/wire_shape.md has the full WHY):**
the gate function, action-name constants, and message renderer live HERE,
not in `wire_shape.py`. The plan's module-split seam is explicit: if gate or
CLI logic lands inside `wire_shape.py`, `classify` + `CHANGE_KINDS` must be
split out of it at that moment. Keeping the gate beside the module — in its
own file, per the T2.3 plan step 3 — avoids ever reaching that seam.

**The trap this file exists to not fall into:** the committed manifests
match the live schemas today, so "no change -> pass silently" is the
honest, currently-true answer — and a gate that unconditionally passes is
EQUALLY green against that same real tree. Every failure case below is
therefore proven against a scratch copy built by `_make_scratch_wires`,
mutated in memory and written to a pytest tmp_path — never against a
committed schema or manifest file in place.

**The gate's own contract (ADR-3): any shape change fails.** Passing
requires `diff_shapes` to return an empty list. The pass half of "affecting
+ version moved" is realized the way it happens for real: the maintainer
bumps `schema_version` AND regenerates the manifest against the new schema,
so the two sides are byte-identical again and there is nothing left to
diff. A partially-updated pair (version bumped, manifest not regenerated)
still has a diff — the version bump itself shows up as an enum-value change
on the `schema_version` property, per `describe_shape`'s `values` field —
and still fails, per ADR-3.

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

from lib.wire_shape import (  # noqa: E402
    PUBLISHED_WIRES,
    classify,
    describe_shape,
    diff_shapes,
)

# ──────────────────────────────────────────────────────────────────────────────
# The gate — SDD/Complex Logic, one wire at a time
# ──────────────────────────────────────────────────────────────────────────────

# The only two demands the gate ever makes of a maintainer (SDD/Error
# Handling). Named constants, not bare strings at each call/assert site, for
# the same reason CHANGE_KINDS is named in wire_shape.py: a test asserting
# absence needs to check against the SAME token the gate emits.
ACTION_MOVE_VERSION = "move_version"
ACTION_HANDOVER = "handover"
ACTION_REGENERATE_MANIFEST = "regenerate_manifest"


def _manifest_filename(schema_filename: str) -> str:
    stem = schema_filename[: -len(".schema.json")]
    return f"{stem}.shape.json"


def gate_one_wire(document: str, schema_path: Path, manifest_path: Path) -> dict:
    """Gate a single published wire: read its live schema and its committed
    manifest off disk, diff, classify, and decide.

    Returns a structured `WireGateResult` dict, never a rendered string —
    `render_wire_gate_report` below is the only thing that turns this into
    human text, per the plan's "separate the decision from the rendering"
    instruction. Every field here is what a test (or a future `--obligations`
    caller) can assert against without parsing prose:

    - `document`: the schema filename this result is about.
    - `passed`: bool.
    - `error`: set only when the schema could not even be parsed — a
      DIFFERENT failure mode than a real shape diff, so it is never left to
      masquerade as `changes == []` (which means "no change").
    - `changes`: the `ShapeChange` list from `diff_shapes`, each with
      `consumer_affecting` resolved by `classify` (unlike `diff_shapes`'s own
      return value, which always carries `False` there — see
      `wire_shape.py`'s `_change` docstring).
    - `affecting`: `any(...)` over the resolved changes; `None` when `error`
      is set, since there is nothing to classify.
    - `schema_version` / `manifest_version` / `version_moved`.
    - `actions`: the demands this failure makes — `[]` when passed.

    A schema that fails to parse fails LOUD (SDD/Error Handling: "Schema
    unreadable / invalid JSON -> fail loudly; do not treat as 'no change'")
    — caught narrowly (`OSError`, `json.JSONDecodeError`) so a real bug
    inside `describe_shape`/`diff_shapes`/`classify` still raises and fails
    the test run, rather than being swallowed into a gate failure result.
    """
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {
            "document": document,
            "passed": False,
            "error": f"schema unreadable: {exc}",
            "changes": [],
            "affecting": None,
            "schema_version": None,
            "manifest_version": None,
            "version_moved": None,
            "actions": [],
        }

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    recorded = manifest["nodes"]
    observed = describe_shape(schema)
    changes = diff_shapes(recorded, observed)

    schema_version = schema["properties"]["schema_version"]["const"]
    manifest_version = manifest["schema_version"]
    version_moved = schema_version != manifest_version

    if not changes:
        # SDD/Complex Logic step 5: no diff, no failure. This is the ONLY
        # path to passed=True — see the module docstring's ADR-3 note.
        return {
            "document": document,
            "passed": True,
            "error": None,
            "changes": [],
            "affecting": False,
            "schema_version": schema_version,
            "manifest_version": manifest_version,
            "version_moved": version_moved,
            "actions": [],
        }

    resolved_changes = [dict(change, consumer_affecting=classify(change, observed)) for change in changes]
    affecting = any(change["consumer_affecting"] for change in resolved_changes)

    if affecting and not version_moved:
        # SDD/Complex Logic step 7-8: consumer-affecting and the version
        # never moved to signal it — both a version move AND a handover
        # are demanded.
        actions = [ACTION_MOVE_VERSION, ACTION_HANDOVER]
    else:
        # Step 9-10's ELSE covers TWO cases on purpose: a non-affecting
        # change (nothing to hand over, just regenerate), and an affecting
        # change whose version already moved but whose manifest is still
        # stale (the version demand is already satisfied — only
        # regeneration is left). Either way the maintainer's one remaining
        # action is the same.
        actions = [ACTION_REGENERATE_MANIFEST]

    return {
        "document": document,
        "passed": False,
        "error": None,
        "changes": resolved_changes,
        "affecting": affecting,
        "schema_version": schema_version,
        "manifest_version": manifest_version,
        "version_moved": version_moved,
        "actions": actions,
    }


def run_wire_gate(schemas_dir: Path, shapes_dir: Path, wires=PUBLISHED_WIRES) -> list:
    """Gate every published wire, independently. Never stops at the first
    failure (SDD/Complex Logic step 1's FOR, plan T2.3's CON-4 note) — each
    wire's result is computed from its own schema/manifest pair only, so one
    wire's failure cannot suppress or alter another's.
    """
    results = []
    for document in wires:
        schema_path = schemas_dir / document
        manifest_path = shapes_dir / _manifest_filename(document)
        results.append(gate_one_wire(document, schema_path, manifest_path))
    return results


def render_wire_gate_report(results: list) -> str:
    """Human text for a `run_wire_gate` result list. Display-only, same
    contract as `detail` in `wire_shape.py` — nothing parses this back;
    assert against the structured result instead, and reserve this renderer
    for the one or two tests that cover the message itself.

    Passing wires contribute nothing: an all-green run renders to `""`, the
    literal "pass silently" the plan asks for.
    """
    lines = []
    for result in results:
        if result["passed"]:
            continue
        if result["error"]:
            lines.append(f"{result['document']}: {result['error']}")
            continue
        lines.append(
            f"{result['document']}: shape changed "
            f"({result['schema_version']!r} vs manifest {result['manifest_version']!r})",
        )
        for change in result["changes"]:
            marker = "affecting" if change["consumer_affecting"] else "not affecting"
            lines.append(f"  {change['pointer']} {change['kind']} ({marker}): {change['detail']}")
        if ACTION_MOVE_VERSION in result["actions"]:
            lines.append("  -> move schema_version and hand over the obligation to the consumer")
        else:
            lines.append("  -> regenerate the manifest")
    return "\n".join(lines)


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
        manifest_name = _manifest_filename(document)
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

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / _manifest_filename(document))

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
        shapes_dir / _manifest_filename(document),
        lambda manifest: (
            manifest["nodes"][pointer]["properties"].pop("item_key"),
            manifest["nodes"][pointer].__setitem__(
                "required",
                [name for name in manifest["nodes"][pointer]["required"] if name != "item_key"],
            ),
        ),
    )

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / _manifest_filename(document))

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
    manifest_path = shapes_dir / _manifest_filename(document)
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

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / _manifest_filename(document))

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

    result = gate_one_wire(document, schemas_dir / document, shapes_dir / _manifest_filename(document))

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
