#!/usr/bin/env python3
# version: 0.3.0
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
turns a result list into human text, and it names an ACTUAL instruction
for every failure branch, error branches included: "a message that says
what to do" is a promise this module keeps on every path, not just the
shape-diff ones. Same contract as `detail` in wire_shape.py: a
human-readable string is for humans, and nothing parses it back — callers
that need to branch on WHY a wire failed read `error_kind`
(code review, 2026-09-10), never the `error` string's prefix.

**Malformed input fails as a gate result; a broken algorithm still
raises.** `_validate_schema_shape`/`_validate_manifest_shape` check the
required keys explicitly, BEFORE describe_shape/diff_shapes/classify ever
run, and return early with a structured error result when a key is
missing. This is deliberately validation, not a `try`/`except KeyError`
wrapped around the processing block — a blanket catch there would also
swallow a genuine `KeyError` bug surfacing from inside
describe_shape/diff_shapes/classify, which this module's error-handling
contract requires to keep raising loudly. See wire_gate.md's note on the
second loop-abort defect this closed.
"""
from __future__ import annotations

import json
from pathlib import Path

from lib.wire_shape import PUBLISHED_WIRES, classify, describe_shape, diff_shapes

# The only three demands the gate ever makes of a maintainer on a real
# shape diff (SDD/Error Handling). A collecting tuple plus an
# identity-checked renderer, same mechanism wire_shape.py's CHANGE_KINDS
# gives classify() — a review already found the alternative (the renderer
# inferring `regenerate_manifest` by ABSENCE of `move_version`) the more
# fragile shape: an unrecognised action would silently render the wrong
# instruction instead of raising. See wire_gate.md.
ACTION_MOVE_VERSION = "move_version"
ACTION_HANDOVER = "handover"
ACTION_REGENERATE_MANIFEST = "regenerate_manifest"

ACTIONS = (ACTION_MOVE_VERSION, ACTION_HANDOVER, ACTION_REGENERATE_MANIFEST)

# One imperative instruction per action — what render_wire_gate_report
# actually prints. Keyed by the SAME constants gate_one_wire assigns into
# `actions`, so a typo or a renamed constant fails loudly (KeyError) rather
# than rendering nothing for a real action.
ACTION_INSTRUCTIONS = {
    ACTION_MOVE_VERSION: "move schema_version to a new value",
    ACTION_HANDOVER: "hand over the schema and the obligation table to the consumer",
    ACTION_REGENERATE_MANIFEST: "regenerate the manifest against the current schema",
}

# Every distinct reason gate_one_wire can fail before it has anything to
# diff — a schema or manifest that could not be read at all, or one that
# parsed as JSON but is missing a key this module requires. Named
# constants for the same reason ACTIONS is one: a caller (T4.1's CLI,
# eventually distinct exit codes) branches on IDENTITY, never on a prefix
# of the human `error` string — prefix-matching a sentence built for
# humans is the exact trap ADR-2 already ruled out for `detail`.
ERROR_SCHEMA_UNREADABLE = "schema_unreadable"
ERROR_SCHEMA_MALFORMED = "schema_malformed"
ERROR_MANIFEST_MISSING = "manifest_missing"
ERROR_MANIFEST_UNREADABLE = "manifest_unreadable"
ERROR_MANIFEST_MALFORMED = "manifest_malformed"

ERROR_KINDS = (
    ERROR_SCHEMA_UNREADABLE,
    ERROR_SCHEMA_MALFORMED,
    ERROR_MANIFEST_MISSING,
    ERROR_MANIFEST_UNREADABLE,
    ERROR_MANIFEST_MALFORMED,
)

# One imperative instruction per error kind. A missing manifest and a
# malformed/unreadable one get DIFFERENT instructions on purpose (code
# review, 2026-09-10): a maintainer who forgot to commit a manifest for a
# new wire needs to be told to create one, not to "regenerate" a file that
# does not exist yet.
ERROR_INSTRUCTIONS = {
    ERROR_SCHEMA_UNREADABLE: "fix the schema file so it parses as JSON",
    ERROR_SCHEMA_MALFORMED: "fix the schema file — it is missing a required key",
    ERROR_MANIFEST_MISSING: "generate and commit a manifest for this wire",
    ERROR_MANIFEST_UNREADABLE: "regenerate the manifest",
    ERROR_MANIFEST_MALFORMED: "regenerate the manifest",
}


def manifest_filename(schema_filename: str) -> str:
    """The committed manifest's filename for a published wire's schema
    filename — `<stem>.shape.json` alongside `<stem>.schema.json`, matching
    the layout `tomo/schemas/shapes/` already uses (T1.2).
    """
    stem = schema_filename[: -len(".schema.json")]
    return f"{stem}.shape.json"


def _validate_schema_shape(schema) -> str | None:
    """The one fragment gate_one_wire needs from a parsed schema:
    `properties.schema_version.const`. Returns a description of what is
    missing, or `None` when the shape is usable. Checked EXPLICITLY, before
    `describe_shape` or the later `schema["properties"]["schema_version"]
    ["const"]` access ever run — a schema that is valid JSON but missing
    this shape (an empty stub, a hand-edit that drops a key) used to raise
    an uncaught KeyError from deep inside gate_one_wire, aborting
    run_wire_gate's loop for every OTHER wire too. See wire_gate.md.
    """
    if not isinstance(schema, dict):
        return "schema is not a JSON object"
    properties = schema.get("properties")
    if not isinstance(properties, dict):
        return "schema is missing required key 'properties'"
    schema_version_node = properties.get("schema_version")
    if not isinstance(schema_version_node, dict) or "const" not in schema_version_node:
        return "schema is missing required key 'properties.schema_version.const'"
    return None


def _validate_manifest_shape(manifest) -> str | None:
    """The two fragments gate_one_wire needs from a parsed manifest:
    `nodes` and `schema_version`. Same contract as
    `_validate_schema_shape` — checked explicitly before either key is
    accessed, so a manifest that is valid JSON but missing one (an empty
    stub, another wire's manifest copy-pasted) fails as a gate result
    instead of an uncaught KeyError aborting the run.
    """
    if not isinstance(manifest, dict):
        return "manifest is not a JSON object"
    if not isinstance(manifest.get("nodes"), dict):
        return "manifest is missing required key 'nodes'"
    if "schema_version" not in manifest:
        return "manifest is missing required key 'schema_version'"
    return None


def _result(
    document: str,
    *,
    passed: bool,
    error: str | None = None,
    error_kind: str | None = None,
    changes: list | None = None,
    affecting: bool | None = None,
    schema_version: str | None = None,
    manifest_version: str | None = None,
    version_moved: bool | None = None,
    actions: list | None = None,
) -> dict:
    """The ONE place a WireGateResult dict is built. `gate_one_wire` used
    to list these same ten keys three times independently (the error
    branch, the pass branch, the fail-with-changes branch) with nothing
    enforcing that the three agreed — this is that enforcement. Every
    caller passes only the fields that differ from the all-`None`/empty
    default, which IS the error-result shape: `_result(document,
    passed=False, error=..., error_kind=...)` needs nothing else.
    """
    return {
        "document": document,
        "passed": passed,
        "error": error,
        "error_kind": error_kind,
        "changes": changes if changes is not None else [],
        "affecting": affecting,
        "schema_version": schema_version,
        "manifest_version": manifest_version,
        "version_moved": version_moved,
        "actions": actions if actions is not None else [],
    }


def _error_result(document: str, error: str, error_kind: str) -> dict:
    """A WireGateResult for a wire that could not even be read or does not
    have the shape this module requires. `affecting` stays `None` (the
    `_result` default): `False` would mean "a real diff was classified and
    found non-affecting", which never happened here — there was nothing to
    classify. `error_kind` is one of `ERROR_KINDS`; a caller branches on
    IT, never on `error`'s prefix (see the module docstring).
    """
    return _result(document, passed=False, error=error, error_kind=error_kind)


def gate_one_wire(document: str, schema_path: Path, manifest_path: Path) -> dict:
    """Gate a single published wire: read its live schema and its committed
    manifest off disk, diff, classify, and decide.

    Returns a structured WireGateResult dict, never a rendered string:

    - `document`: the schema filename this result is about.
    - `passed`: bool.
    - `error`: a human sentence, set only when the schema or manifest could
      not even be read or does not have the required shape — a DIFFERENT
      failure mode than a real shape diff, so it is never left to
      masquerade as `changes == []` (which means "no change").
    - `error_kind`: one of `ERROR_KINDS`, or `None` when `error` is `None`.
      The identity a caller branches on; `error` is display-only.
    - `changes`: the ShapeChange list from diff_shapes, each with
      `consumer_affecting` RESOLVED by classify (unlike diff_shapes's own
      return value, which always carries False there — see wire_shape.py's
      `_change` docstring).
    - `affecting`: `any(...)` over the resolved changes; `None` when `error`
      is set, since there is nothing to classify.
    - `schema_version` / `manifest_version` / `version_moved`.
    - `actions`: the demands this failure makes — `[]` when passed. Each
      entry is one of `ACTIONS`.

    Four ways to fail before there is anything to diff, each a DISTINCT
    `error_kind` (SDD/Error Handling; code review, 2026-09-10 for the
    malformed-shape pair):

    - schema unreadable (OSError / invalid JSON) — caught narrowly so a
      real bug inside describe_shape/diff_shapes/classify still raises and
      fails the run, rather than being swallowed into a gate result.
    - schema malformed (valid JSON, missing `properties.schema_version.
      const`) — validated explicitly by `_validate_schema_shape` BEFORE
      describe_shape runs, never via a blanket `except KeyError`, which
      would also swallow a genuine bug from inside this module's own
      pure functions.
    - manifest missing (`FileNotFoundError`, caught separately from the
      broader OSError/JSONDecodeError pair so the instruction differs: a
      maintainer who forgot to commit a manifest needs to be told to
      create one, not to regenerate a file that does not exist).
    - manifest unreadable (OSError / invalid JSON) or malformed (valid
      JSON, missing `nodes` or `schema_version`, via
      `_validate_manifest_shape`) — both instruct "regenerate the
      manifest".

    ALL FOUR matter more than they look, for the same reason: an uncaught
    exception here does not just fail this wire badly — it propagates out
    of `run_wire_gate`'s loop and aborts gating the other published wires
    entirely, silently suppressing their obligations too. See wire_gate.md.
    """
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return _error_result(document, f"schema unreadable: {exc}", ERROR_SCHEMA_UNREADABLE)

    schema_shape_error = _validate_schema_shape(schema)
    if schema_shape_error is not None:
        return _error_result(document, f"schema malformed: {schema_shape_error}", ERROR_SCHEMA_MALFORMED)

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _error_result(document, f"manifest missing: {manifest_path}", ERROR_MANIFEST_MISSING)
    except (OSError, json.JSONDecodeError) as exc:
        return _error_result(document, f"manifest unreadable: {exc}", ERROR_MANIFEST_UNREADABLE)

    manifest_shape_error = _validate_manifest_shape(manifest)
    if manifest_shape_error is not None:
        return _error_result(document, f"manifest malformed: {manifest_shape_error}", ERROR_MANIFEST_MALFORMED)

    recorded = manifest["nodes"]
    observed = describe_shape(schema)
    changes = diff_shapes(recorded, observed)

    schema_version = schema["properties"]["schema_version"]["const"]
    manifest_version = manifest["schema_version"]
    version_moved = schema_version != manifest_version

    if not changes:
        # SDD/Complex Logic step 5: no diff, no failure. This is the ONLY
        # path to passed=True — see the module docstring's ADR-3 note.
        return _result(
            document,
            passed=True,
            changes=[],
            affecting=False,
            schema_version=schema_version,
            manifest_version=manifest_version,
            version_moved=version_moved,
            actions=[],
        )

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

    return _result(
        document,
        passed=False,
        changes=resolved_changes,
        affecting=affecting,
        schema_version=schema_version,
        manifest_version=manifest_version,
        version_moved=version_moved,
        actions=actions,
    )


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


def _render_action(action: str) -> str:
    """One rendered instruction line for one action. Raises on an action
    not in `ACTION_INSTRUCTIONS` rather than silently rendering nothing or
    the wrong line — the same exhaustiveness discipline `classify` applies
    to `CHANGE_KINDS` in wire_shape.py, applied here to `ACTIONS`. A
    review already found the alternative (inferring `regenerate_manifest`
    by ABSENCE of `move_version`) the more fragile shape.
    """
    if action not in ACTION_INSTRUCTIONS:
        raise ValueError(
            f"render_wire_gate_report: no instruction for action {action!r}. If this is a "
            "legitimate new action, add it to ACTIONS and ACTION_INSTRUCTIONS — do not let "
            "it fall through to a default.",
        )
    return f"  -> {ACTION_INSTRUCTIONS[action]}"


def _render_error(error_kind: str) -> str:
    """One rendered instruction line for one error kind. Same
    exhaustiveness discipline as `_render_action`: raises rather than
    rendering nothing for an `error_kind` that was added to `ERROR_KINDS`
    without a matching entry in `ERROR_INSTRUCTIONS`.
    """
    if error_kind not in ERROR_INSTRUCTIONS:
        raise ValueError(
            f"render_wire_gate_report: no instruction for error_kind {error_kind!r}. If this "
            "is a legitimate new error kind, add it to ERROR_KINDS and ERROR_INSTRUCTIONS.",
        )
    return f"  -> {ERROR_INSTRUCTIONS[error_kind]}"


def render_wire_gate_report(results: list) -> str:
    """Human text for a run_wire_gate result list — "a message that says
    what to do" on EVERY failure branch, error branches included: a
    missing/unreadable/malformed schema or manifest gets its own
    instruction line, not just a diagnosis. Display-only, same contract as
    `detail` in wire_shape.py — nothing parses this back; assert against
    the structured result instead, and reserve this renderer for the
    caller that actually needs to print something.

    Passing wires contribute nothing: an all-green run renders to `""`, the
    literal "pass silently" the plan asks for.
    """
    lines = []
    for result in results:
        if result["passed"]:
            continue
        if result["error"]:
            lines.append(f"{result['document']}: {result['error']}")
            lines.append(_render_error(result["error_kind"]))
            continue
        lines.append(
            f"{result['document']}: shape changed "
            f"({result['schema_version']!r} vs manifest {result['manifest_version']!r})",
        )
        for change in result["changes"]:
            marker = "affecting" if change["consumer_affecting"] else "not affecting"
            lines.append(f"  {change['pointer']} {change['kind']} ({marker}): {change['detail']}")
        for action in result["actions"]:
            lines.append(_render_action(action))
    return "\n".join(lines)
