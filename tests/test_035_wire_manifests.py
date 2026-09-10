#!/usr/bin/env python3
# version: 0.1.0
"""test_035_wire_manifests.py — Behavioural tests for the committed manifest
files under tomo/schemas/shapes/ (spec 035 T1.2).

Separate from test_035_wire_shape.py on purpose: that file tests the pure
describe_shape() walk in isolation (no filesystem); this file tests the
generated-and-committed ARTIFACT — the manifest files on disk, the registry
that decides which schemas get one, and the round-trip against the
committed content. Different subject, different fixture shape (real files
under tomo/schemas/, not inline schema dicts).

Tests cover:
- each of the three published wires has a manifest file on disk (PRD/F1-AC1)
- round-trip: the COMMITTED manifest (loaded from disk, not regenerated
  twice in memory) matches a fresh describe_shape() over the schema file,
  and the committed schema_version matches the schema's declared const
  (PRD/F1-AC5) — see the module docstring's circularity note: a test that
  never opens a file under tomo/schemas/shapes/ would be the wrong test
- no internal (non-published) schema has a manifest — DERIVED from the
  registry, not a hardcoded list, so a schema added tomorrow is covered
  automatically
- a published wire with a missing manifest fails the existence check rather
  than passing silently (MiYo Constitution L1: both a permitted and a
  refused case) — simulated against a name NOT in the real registry, so no
  committed file is touched
- each manifest's `source` field names the schema file it actually describes
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
SHAPES_DIR = SCHEMAS_DIR / "shapes"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.wire_shape import (  # noqa: E402
    PUBLISHED_WIRES,
    build_manifest,
    describe_shape,
    serialize_manifest,
)


def _manifest_path(wire_schema_filename: str) -> Path:
    stem = wire_schema_filename[: -len(".schema.json")]
    return SHAPES_DIR / f"{stem}.shape.json"


def _assert_manifest_exists(wire_schema_filename: str) -> Path:
    """The missing-manifest check (plan T1.2 step 3): a published wire
    without a manifest file must fail loudly. Lives in the test suite, not
    in wire_shape.py — Phase 2 builds the real drift gate on top of this.
    """
    path = _manifest_path(wire_schema_filename)
    assert path.is_file(), f"no manifest committed for published wire {wire_schema_filename!r} (expected {path})"
    return path


# ──────────────────────────────────────────────────────────────────────────────
# PRD/F1-AC1 — every published wire has a manifest
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("wire_schema_filename", PUBLISHED_WIRES)
def test_published_wire_has_manifest_file(wire_schema_filename):
    _assert_manifest_exists(wire_schema_filename)


def test_exactly_three_manifests_exist():
    assert SHAPES_DIR.is_dir()
    manifest_files = sorted(p.name for p in SHAPES_DIR.glob("*.shape.json"))
    assert len(manifest_files) == 3
    assert len(PUBLISHED_WIRES) == 3


# ──────────────────────────────────────────────────────────────────────────────
# PRD/F1-AC5 — regenerating produces identical content on an unchanged schema
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("wire_schema_filename", PUBLISHED_WIRES)
def test_manifest_round_trips_against_committed_file(wire_schema_filename):
    manifest_path = _assert_manifest_exists(wire_schema_filename)
    committed_text = manifest_path.read_text(encoding="utf-8")
    committed = json.loads(committed_text)

    schema_path = SCHEMAS_DIR / wire_schema_filename
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    regenerated_nodes = describe_shape(schema)
    declared_version = schema["properties"]["schema_version"]["const"]

    assert committed["nodes"] == regenerated_nodes
    assert committed["schema_version"] == declared_version

    # PRD/F1-AC5, literally: describing the schema again produces the
    # committed content BYTE-FOR-BYTE. Rebuild the manifest through the same
    # build_manifest + serialize_manifest path the generator used, and
    # compare the resulting text against the file exactly as committed —
    # not just the parsed structure above.
    regenerated = build_manifest(schema, source=committed["source"])
    assert serialize_manifest(regenerated) == committed_text


# ──────────────────────────────────────────────────────────────────────────────
# derived — no non-published schema has a manifest
# ──────────────────────────────────────────────────────────────────────────────

def test_internal_schema_has_no_manifest():
    all_schema_files = sorted(p.name for p in SCHEMAS_DIR.glob("*.schema.json"))
    internal_schema_files = [name for name in all_schema_files if name not in PUBLISHED_WIRES]

    # Sanity: the registry must actually be a strict subset, or this test
    # would vacuously pass by comparing an empty list to itself.
    assert internal_schema_files
    assert len(internal_schema_files) == len(all_schema_files) - len(PUBLISHED_WIRES)

    for schema_filename in internal_schema_files:
        manifest_path = _manifest_path(schema_filename)
        assert not manifest_path.exists(), (
            f"internal schema {schema_filename!r} unexpectedly has a manifest at {manifest_path}"
        )


# ──────────────────────────────────────────────────────────────────────────────
# refused path — missing manifest fails rather than passing silently
# ──────────────────────────────────────────────────────────────────────────────

def test_missing_manifest_fails_the_existence_check():
    # A name deliberately absent from PUBLISHED_WIRES and from disk — never
    # a real committed file, so nothing is deleted or touched as a side
    # effect of this test.
    fake_wire = "not-a-real-published-wire.schema.json"
    assert fake_wire not in PUBLISHED_WIRES
    assert not _manifest_path(fake_wire).exists()

    with pytest.raises(AssertionError):
        _assert_manifest_exists(fake_wire)


# ──────────────────────────────────────────────────────────────────────────────
# source field names the schema it describes
# ──────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("wire_schema_filename", PUBLISHED_WIRES)
def test_manifest_source_names_its_schema(wire_schema_filename):
    manifest_path = _assert_manifest_exists(wire_schema_filename)
    committed = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert wire_schema_filename in committed["source"]
    assert committed["source"] == f"tomo/schemas/{wire_schema_filename}"


# ──────────────────────────────────────────────────────────────────────────────
# build_manifest wraps describe_shape correctly (unit-level, no filesystem)
# ──────────────────────────────────────────────────────────────────────────────

def test_build_manifest_wraps_describe_shape():
    schema = {
        "type": "object",
        "properties": {
            "schema_version": {"const": "7"},
            "id": {"type": "string"},
        },
    }

    manifest = build_manifest(schema, source="tomo/schemas/example.schema.json")

    assert manifest["schema_version"] == "7"
    assert manifest["source"] == "tomo/schemas/example.schema.json"
    assert manifest["nodes"] == describe_shape(schema)
