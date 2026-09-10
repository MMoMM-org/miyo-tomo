#!/usr/bin/env python3
# version: 0.2.0
"""wire_gate.py — The drift gate for a published wire: diff + classify +
version-check, and a message that says what to do (spec 035 T2.3).

Sits beside wire_shape.py, not inside it — see
docs/tomo/scripts/lib/wire_gate.md for the module-split seam that put it
here. wire_shape.py stays the pure data model (describe_shape, diff_shapes,
classify, the manifest builder/serializer); this module is the thing that
DRIVES it: reads a schema and a manifest off disk, runs the SDD/Complex
Logic algorithm, and decides pass or fail for one wire, or for all of them
in one run.

**The gate's own contract (ADR-3): any shape change fails.** Passing
requires diff_shapes to return an empty list — regeneration is always an
explicit act, never implied by a version bump alone. See
docs/tomo/scripts/lib/wire_gate.md for the reasoning and the traced
walkthrough of why "affecting + version moved" passes only once the
manifest has actually been regenerated against the new schema.

Structured result, not a string: gate_one_wire/run_wire_gate return a
WireGateResult dict a caller can assert against or build a report from
without parsing prose — render_wire_gate_report is the only thing that
turns a result list into human text. Same contract as `detail` in
wire_shape.py: a human-readable string is for humans, and nothing parses
it back.
"""
from __future__ import annotations

import json
from pathlib import Path

from lib.wire_shape import PUBLISHED_WIRES, classify, describe_shape, diff_shapes

# The only two demands the gate ever makes of a maintainer (SDD/Error
# Handling). Named constants, not bare strings at each call/assert site, so
# a caller asserting absence checks against the SAME token the gate emits.
ACTION_MOVE_VERSION = "move_version"
ACTION_HANDOVER = "handover"
ACTION_REGENERATE_MANIFEST = "regenerate_manifest"


def manifest_filename(schema_filename: str) -> str:
    """The committed manifest's filename for a published wire's schema
    filename — `<stem>.shape.json` alongside `<stem>.schema.json`, matching
    the layout `tomo/schemas/shapes/` already uses (T1.2).
    """
    stem = schema_filename[: -len(".schema.json")]
    return f"{stem}.shape.json"


def _error_result(document: str, error: str) -> dict:
    """A WireGateResult for a wire that could not even be read — a schema
    that fails to parse, or a manifest that is missing or corrupt.
    `affecting` is `None` here, never `False`: `False` means "a real diff
    was classified and found non-affecting", which never happened for this
    result — there was nothing to classify. See gate_one_wire's docstring.
    """
    return {
        "document": document,
        "passed": False,
        "error": error,
        "changes": [],
        "affecting": None,
        "schema_version": None,
        "manifest_version": None,
        "version_moved": None,
        "actions": [],
    }


def gate_one_wire(document: str, schema_path: Path, manifest_path: Path) -> dict:
    """Gate a single published wire: read its live schema and its committed
    manifest off disk, diff, classify, and decide.

    Returns a structured WireGateResult dict, never a rendered string:

    - `document`: the schema filename this result is about.
    - `passed`: bool.
    - `error`: set only when the schema or manifest could not even be read
      — a DIFFERENT failure mode than a real shape diff, so it is never
      left to masquerade as `changes == []` (which means "no change").
    - `changes`: the ShapeChange list from diff_shapes, each with
      `consumer_affecting` RESOLVED by classify (unlike diff_shapes's own
      return value, which always carries False there — see wire_shape.py's
      `_change` docstring).
    - `affecting`: `any(...)` over the resolved changes; `None` when `error`
      is set, since there is nothing to classify.
    - `schema_version` / `manifest_version` / `version_moved`.
    - `actions`: the demands this failure makes — `[]` when passed.

    A schema that fails to parse fails LOUD (SDD/Error Handling: "Schema
    unreadable / invalid JSON -> fail loudly; do not treat as 'no change'")
    — caught narrowly (OSError, json.JSONDecodeError) so a real bug inside
    describe_shape/diff_shapes/classify still raises and fails the run,
    rather than being swallowed into a gate failure result.

    A MISSING or CORRUPT manifest fails the same way (SDD/Error Handling:
    "Manifest missing for a published wire -> fail. A wire added without a
    manifest is exactly the gap this spec closes; silence would reproduce
    it.") — and it matters MORE than the schema guard above: an uncaught
    exception here would propagate out of run_wire_gate's loop and abort
    gating the other published wires entirely, silently suppressing their
    obligations too. `FileNotFoundError` is caught separately from the
    broader `OSError`/`json.JSONDecodeError` pair so the message tells a
    maintainer who forgot to commit a manifest something different from one
    whose manifest got corrupted — see wire_gate.md.
    """
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _error_result(document, f"schema unreadable: {exc}")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _error_result(document, f"manifest missing: {manifest_path}")
    except (OSError, json.JSONDecodeError) as exc:
        return _error_result(document, f"manifest unreadable: {exc}")

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
    """Gate every published wire in `wires`, independently. Never stops at
    the first failure (SDD/Complex Logic step 1's FOR, plan T2.3's CON-4
    note) — each wire's result is computed from its own schema/manifest
    pair only, so one wire's failure cannot suppress or alter another's.
    """
    results = []
    for document in wires:
        schema_path = schemas_dir / document
        manifest_path = shapes_dir / manifest_filename(document)
        results.append(gate_one_wire(document, schema_path, manifest_path))
    return results


def render_wire_gate_report(results: list) -> str:
    """Human text for a run_wire_gate result list. Display-only, same
    contract as `detail` in wire_shape.py — nothing parses this back;
    assert against the structured result instead, and reserve this renderer
    for the caller that actually needs to print something.

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
