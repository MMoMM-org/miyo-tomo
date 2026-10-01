#!/usr/bin/env python3
# version: 0.1.0
"""test_038_suggestions_wire_schema_move.py — T2.1: the suggestions wire's
schema_version move (2 -> 3) and the new attachment_conflicts[] array must
land in the live schema AND the shape manifest together, never one without
the other (spec 038 Phase 2, SDD ADR-1/ADR-2/ADR-3/ADR-8).

A half-finished move — the schema edited but the manifest left stale, or
vice versa — must be observable as a failing assertion here, not discovered
later via scripts/wire-shape.py --check. This file only proves the two
artefacts AGREE with each other; it does not re-derive wire_shape's own
drift-detection logic (that is test_035_wire_shape.py's job).

Spec: docs/XDD/specs/038-every-editable-decision-reaches-the-wire/
Ref: SDD/ADR-1; SDD/ADR-2; SDD/ADR-3; SDD/ADR-8
"""
from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
SHAPES_DIR = SCHEMAS_DIR / "shapes"

SCHEMA_PATH = SCHEMAS_DIR / "suggestions-wire.schema.json"
MANIFEST_PATH = SHAPES_DIR / "suggestions-wire.shape.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_live_schema_and_manifest_agree_on_version_and_attachment_conflicts():
    """The live schema and the shape manifest must agree with each other on
    two things: the wire's schema_version, and whether attachment_conflicts
    exists at all. The manifest also carries the version at TWO internal
    sites (top-level `schema_version` and `nodes[""].values.schema_version`)
    — both must agree with each other, or `--regenerate` was only half run.
    """
    schema = _load(SCHEMA_PATH)
    manifest = _load(MANIFEST_PATH)

    schema_version = schema["properties"]["schema_version"]["const"]
    manifest_top_version = manifest["schema_version"]
    manifest_node_versions = manifest["nodes"][""]["values"]["schema_version"]

    # The manifest's own two version sites must agree with each other.
    assert manifest_node_versions == [manifest_top_version], (
        "the manifest's two version sites disagree with each other: "
        f"top-level={manifest_top_version!r} node-level={manifest_node_versions!r}"
    )

    # The live schema and the manifest must agree with each other.
    assert schema_version == manifest_top_version, (
        "the live schema and the shape manifest disagree on schema_version: "
        f"schema={schema_version!r} manifest={manifest_top_version!r}"
    )

    schema_has_conflicts = "attachment_conflicts" in schema["properties"]
    manifest_has_conflicts = "attachment_conflicts" in manifest["nodes"][""]["properties"]
    assert schema_has_conflicts == manifest_has_conflicts, (
        "the live schema and the shape manifest disagree on whether "
        f"attachment_conflicts exists: schema={schema_has_conflicts} "
        f"manifest={manifest_has_conflicts}"
    )

    # T2.1 moves the version to "3" and adds attachment_conflicts — pin both,
    # not just internal self-consistency, so a move to the wrong version (or
    # a manifest regenerated against the wrong schema) still fails here.
    assert schema_version == "3"
    assert schema_has_conflicts is True
