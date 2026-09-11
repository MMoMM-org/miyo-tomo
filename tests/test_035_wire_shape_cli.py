#!/usr/bin/env python3
# version: 0.2.0
"""test_035_wire_shape_cli.py — Behavioural tests for scripts/wire-shape.py,
the maintainer's CLI wrapping describe_shape/diff_shapes/classify via
lib.wire_gate (spec 035 T4.1).

**Test method (plan T4.1's approved test plan — four decisions are gated,
not open to revisit here):**

1. `--check` is proven against SCRATCH trees, not the live repo. The live
   tree already has a Phase 2 gate (lib/wire_gate.py + test_035_wire_gate.py)
   — asserting CLI behaviour against it too would give two tests failing
   for one cause. Exactly one live-tree test exists below
   (`test_check_exits_zero_on_the_real_committed_tree_smoke`) and it is
   deliberately coupled to live repo state: a smoke test proving the CLI's
   exit code agrees with the gate today, not the behavioural proof.
2. `--regenerate` is proven to write AND to not write, in this same file:
   against a drifted scratch tree the manifest bytes change and the
   printed output names the pointer and the change kind; against an
   unchanged scratch tree the bytes AND mtime are unchanged and the CLI
   says nothing changed. Only the second half would be satisfied by a CLI
   that never writes at all.
3. `--obligations` rows are checked against the ACTUAL drift a known
   pointer produced — pointer, change kind, affecting/not-affecting
   verdict, version transition — never merely "a row has four fields",
   which a fixed-row stub would also satisfy.
4. Metadata-only is proven by ENUMERATION, not a hand-picked sample:
   `_all_description_strings()` walks all three published schemas at test
   time and collects every `description` value that exists anywhere in
   them; `test_no_schema_description_leaks_into_any_cli_output` asserts
   none of them appears in any `--check`/`--regenerate`/`--obligations`
   output collected across this file's other tests. A sample would pass
   while the thing it guards is broken; the derived set cannot go stale.

Two published wires anchor every scratch mutation:
- `/properties/suggestions/items` on suggestions-wire.schema.json is
  CLOSED (`additionalProperties: false`) — adding a property there is
  consumer-affecting (classify() reads `closed`).
- `/properties/findings/items/properties/detail` on
  garden-audit-wire.schema.json is OPEN (`additionalProperties: true`) —
  adding a property there is NOT consumer-affecting. Used to prove
  `--obligations`' marker actually varies with the node, not a constant.

Plus the three carry-forwards from T1.2's code-quality review, deliberately
deferred to this task (see plan T4.1):
(a) `build_manifest` raises `ValueError` naming the source document, not a
    bare `KeyError` — covering both "no const at all" and "declared as an
    enum instead of a const".
(b) `--regenerate` writes with `encoding="utf-8"` — proven with a scratch
    property carrying a non-ASCII name, round-tripped byte-for-byte.
(c) The `X.schema.json` -> `X.shape.json` naming convention is importable
    from `lib.wire_shape.manifest_filename` with no duplicate left in
    `tests/test_035_wire_manifests.py` (verified here by identity and by a
    source-text regression check on that file).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
LIB_DIR = REPO_ROOT / "tomo" / "scripts"
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
SHAPES_DIR = SCHEMAS_DIR / "shapes"

sys.path.insert(0, str(LIB_DIR))

from lib.wire_gate import manifest_filename as gate_manifest_filename  # noqa: E402
from lib.wire_shape import PUBLISHED_WIRES, build_manifest  # noqa: E402
from lib.wire_shape import manifest_filename as shape_manifest_filename  # noqa: E402
from lib.wire_shape import serialize_manifest  # noqa: E402

# scripts/wire-shape.py is hyphen-named — load it by path, matching the
# established convention for every other scripts/*.py test in this repo
# (see tests/test_garden_audit_configure.py).
_spec = importlib.util.spec_from_file_location("wire_shape_cli", SCRIPTS_DIR / "wire-shape.py")
wire_shape_cli = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(wire_shape_cli)

SUGGESTIONS_WIRE = "suggestions-wire.schema.json"
GARDEN_AUDIT_WIRE = "garden-audit-wire.schema.json"
AFFECTING_POINTER = "/properties/suggestions/items"
NOT_AFFECTING_POINTER = "/properties/findings/items/properties/detail"


# ──────────────────────────────────────────────────────────────────────────────
# Scratch-copy fixtures — NEVER mutate a committed schema or manifest in place
# ──────────────────────────────────────────────────────────────────────────────

def _make_scratch_wires(tmp_path: Path) -> tuple[Path, Path]:
    """Copy the three published wires' schemas and committed manifests into
    `tmp_path`. Tests mutate these COPIES; tomo/schemas/ is never touched.
    """
    import shutil

    schemas_dir = tmp_path / "schemas"
    shapes_dir = schemas_dir / "shapes"
    shapes_dir.mkdir(parents=True)
    for document in PUBLISHED_WIRES:
        shutil.copy(SCHEMAS_DIR / document, schemas_dir / document)
        name = shape_manifest_filename(document)
        shutil.copy(SHAPES_DIR / name, shapes_dir / name)
    return schemas_dir, shapes_dir


def _rewrite_json(path: Path, mutate) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return data


def _add_property_to_suggestions_items(schema: dict, name: str = "cli_test_field", prop: dict | None = None) -> None:
    """`/properties/suggestions/items` is CLOSED — a genuine,
    consumer-affecting shape change."""
    schema["properties"]["suggestions"]["items"]["properties"][name] = prop or {"type": "string"}


def _add_property_to_garden_audit_detail(schema: dict, name: str = "cli_test_field") -> None:
    """`/properties/findings/items/properties/detail` is OPEN — a shape
    change that does NOT oblige the consumer."""
    schema["properties"]["findings"]["items"]["properties"]["detail"]["properties"][name] = {"type": "string"}


def _all_description_strings() -> set[str]:
    """Every `description` value at any depth across the three PUBLISHED
    schemas, collected at test time (plan T4.1 decision 4) — not a
    hand-picked sample, so this can never go stale relative to the schemas
    it walks.
    """
    found: set[str] = set()

    def walk(node) -> None:
        if isinstance(node, dict):
            description = node.get("description")
            if isinstance(description, str) and description:
                found.add(description)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    for document in PUBLISHED_WIRES:
        walk(json.loads((SCHEMAS_DIR / document).read_text(encoding="utf-8")))
    return found


_captured_outputs: list[str] = []


def _run(argv: list[str], capsys) -> tuple[int, str]:
    """Invoke the CLI's main() with argv, capturing stdout — and stash the
    output for test_no_schema_description_leaks_into_any_cli_output, which
    checks every output any OTHER test in this file produced.
    """
    rc = wire_shape_cli.main(argv)
    out = capsys.readouterr().out
    _captured_outputs.append(out)
    return rc, out


# ──────────────────────────────────────────────────────────────────────────────
# --check (plan decision 1: one live-tree smoke test, scratch trees for behaviour)
# ──────────────────────────────────────────────────────────────────────────────

def test_check_exits_zero_on_the_real_committed_tree_smoke(capsys):
    """Deliberately coupled to live repo state — a SMOKE test, not the
    behavioural assertion. Phase 2's wire_gate already proves the real tree
    gates clean (test_035_wire_gate.py); this only proves the CLI's exit
    code and lib.wire_gate agree on that today.
    """
    rc, out = _run(["--check"], capsys)
    assert rc == 0
    assert out == ""


def test_check_exits_nonzero_on_a_drifted_scratch_tree(tmp_path, capsys):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    _rewrite_json(schemas_dir / SUGGESTIONS_WIRE, _add_property_to_suggestions_items)

    rc, out = _run(["--check", "--schemas-dir", str(schemas_dir), "--shapes-dir", str(shapes_dir)], capsys)

    assert rc != 0
    assert AFFECTING_POINTER in out
    assert "added_property" in out


def test_check_exits_zero_on_a_clean_scratch_tree(tmp_path, capsys):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)

    rc, out = _run(["--check", "--schemas-dir", str(schemas_dir), "--shapes-dir", str(shapes_dir)], capsys)

    assert rc == 0
    assert out == ""


# ──────────────────────────────────────────────────────────────────────────────
# --regenerate: writes AND does-not-write (plan decision 2: both required)
# ──────────────────────────────────────────────────────────────────────────────

def test_regenerate_writes_the_manifest_and_prints_the_diff_it_applied(tmp_path, capsys):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    manifest_path = shapes_dir / shape_manifest_filename(SUGGESTIONS_WIRE)
    before_bytes = manifest_path.read_bytes()

    _rewrite_json(schemas_dir / SUGGESTIONS_WIRE, _add_property_to_suggestions_items)

    rc, out = _run(["--regenerate", "--schemas-dir", str(schemas_dir), "--shapes-dir", str(shapes_dir)], capsys)

    assert rc == 0
    after_bytes = manifest_path.read_bytes()
    assert after_bytes != before_bytes, "a silent rewrite fails this test — ADR-3 requires the diff be printed too"

    # ADR-3: the diff it APPLIED, not merely "something changed".
    assert SUGGESTIONS_WIRE in out
    assert AFFECTING_POINTER in out
    assert "added_property" in out
    assert "cli_test_field" in out
    assert "affecting" in out

    # The write actually landed the new node — not just a printed claim.
    written = json.loads(after_bytes.decode("utf-8"))
    assert "cli_test_field" in written["nodes"][AFFECTING_POINTER]["properties"]


def test_regenerate_on_an_unchanged_tree_writes_nothing_and_says_so(tmp_path, capsys):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    before = {
        document: (
            (shapes_dir / shape_manifest_filename(document)).read_bytes(),
            (shapes_dir / shape_manifest_filename(document)).stat().st_mtime_ns,
        )
        for document in PUBLISHED_WIRES
    }

    rc, out = _run(["--regenerate", "--schemas-dir", str(schemas_dir), "--shapes-dir", str(shapes_dir)], capsys)

    assert rc == 0
    for document in PUBLISHED_WIRES:
        manifest_path = shapes_dir / shape_manifest_filename(document)
        before_bytes, before_mtime = before[document]
        assert manifest_path.read_bytes() == before_bytes
        assert manifest_path.stat().st_mtime_ns == before_mtime

    # A CLI that never writes at all would also pass the loop above — this
    # is the half that closes that gap (plan decision 2).
    assert "nothing" in out.lower()


# ──────────────────────────────────────────────────────────────────────────────
# --obligations: rows match the ACTUAL drift (plan decision 3)
# ──────────────────────────────────────────────────────────────────────────────

def test_obligations_row_names_the_actual_pointer_kind_verdict_and_version(tmp_path, capsys):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    _rewrite_json(schemas_dir / SUGGESTIONS_WIRE, _add_property_to_suggestions_items)
    _rewrite_json(schemas_dir / GARDEN_AUDIT_WIRE, _add_property_to_garden_audit_detail)

    rc, out = _run(["--obligations", "--schemas-dir", str(schemas_dir), "--shapes-dir", str(shapes_dir)], capsys)

    assert rc == 0
    lines = out.splitlines()

    affecting_lines = [line for line in lines if AFFECTING_POINTER in line]
    assert affecting_lines, "no row named the affecting pointer at all"
    assert any("added_property" in line and "not affecting" not in line and "affecting" in line
               for line in affecting_lines)
    assert any("'1' -> '1'" in line for line in affecting_lines), affecting_lines

    not_affecting_lines = [line for line in lines if NOT_AFFECTING_POINTER in line]
    assert not_affecting_lines, "no row named the not-affecting pointer at all"
    assert any("not affecting" in line and "added_property" in line for line in not_affecting_lines)

    # The manifests were only read, never written, by --obligations.
    for document in PUBLISHED_WIRES:
        manifest_path = shapes_dir / shape_manifest_filename(document)
        committed = (SHAPES_DIR / shape_manifest_filename(document)).read_bytes()
        assert manifest_path.read_bytes() == committed


def test_obligations_prints_nothing_extra_on_an_unchanged_tree(tmp_path, capsys):
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)

    rc, out = _run(["--obligations", "--schemas-dir", str(schemas_dir), "--shapes-dir", str(shapes_dir)], capsys)

    assert rc == 0
    assert "no shape drift" in out.lower()


# ──────────────────────────────────────────────────────────────────────────────
# Metadata-only, by ENUMERATION (plan decision 4)
# ──────────────────────────────────────────────────────────────────────────────

def test_no_schema_description_leaks_into_any_cli_output():
    """Runs LAST alphabetically only by accident of pytest's default
    collection order being irrelevant here — this checks every output
    `_run` captured from every OTHER test in this module, not just its own.
    A hand-picked "this one description string is absent" assertion would
    pass while a different description leaked; the derived set (plan
    decision 4) cannot go stale and cannot be dodged by picking the wrong
    sample.
    """
    forbidden = _all_description_strings()
    assert forbidden, "the enumeration itself found nothing — the guard would be vacuous"
    assert _captured_outputs, "no CLI output was captured — run the other tests in this module first"

    combined = "\n".join(_captured_outputs)
    leaked = [description for description in forbidden if description in combined]
    assert leaked == [], f"schema prose leaked into CLI output: {leaked!r}"


# ──────────────────────────────────────────────────────────────────────────────
# Carry-forward (a): build_manifest raises ValueError naming the source
# ──────────────────────────────────────────────────────────────────────────────

def test_build_manifest_raises_value_error_naming_source_when_const_missing():
    schema = {"properties": {"schema_version": {"type": "string"}}}

    with pytest.raises(ValueError) as exc_info:
        build_manifest(schema, source="fake-wire.schema.json")

    message = str(exc_info.value)
    assert "fake-wire.schema.json" in message
    assert "properties.schema_version.const" in message


def test_build_manifest_raises_value_error_when_version_is_enum_not_const():
    schema = {"properties": {"schema_version": {"enum": ["1", "2"]}}}

    with pytest.raises(ValueError) as exc_info:
        build_manifest(schema, source="fake-wire.schema.json")

    message = str(exc_info.value)
    assert "fake-wire.schema.json" in message
    assert "properties.schema_version.const" in message


def test_regenerate_names_the_document_when_a_schema_is_malformed(tmp_path, capsys):
    """The CLI surface for the carry-forward: a person pointing --regenerate
    at a schema missing properties.schema_version.const sees a message
    naming the document, not a bare KeyError.
    """
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    _rewrite_json(schemas_dir / SUGGESTIONS_WIRE, lambda schema: schema["properties"]["schema_version"].pop("const"))

    rc = wire_shape_cli.main(
        ["--regenerate", "--schemas-dir", str(schemas_dir), "--shapes-dir", str(shapes_dir)]
    )
    err = capsys.readouterr().err

    assert rc == 2
    assert SUGGESTIONS_WIRE in err
    assert "properties.schema_version.const" in err


# ──────────────────────────────────────────────────────────────────────────────
# Carry-forward (b): --regenerate writes with encoding="utf-8"
# ──────────────────────────────────────────────────────────────────────────────

def test_regenerate_round_trips_a_non_ascii_property_name_byte_identically(tmp_path):
    """Runs the REAL script as a subprocess under a pinned C locale
    (`LC_ALL=C LANG=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0`), not through
    `wire_shape_cli.main()` in-process.

    On this machine (and most CI), the process's own locale is already
    UTF-8 — `Path.write_text()` with no explicit `encoding=` would use the
    locale's preferred encoding and this test would pass whether or not
    `encoding="utf-8"` is actually present at the write site, which proves
    nothing about carry-forward (b). Pinning the subprocess's locale to C
    (`locale.getpreferredencoding(False)` == "US-ASCII" under it, measured
    directly) makes the two cases actually diverge: `write_text(...,
    encoding="utf-8")` still succeeds and round-trips byte-identically;
    `write_text(...)` with no encoding argument would raise
    `UnicodeEncodeError` on the café_source property name the moment it
    tried to encode as US-ASCII. See the commit body for the revert-proof
    (removing `encoding="utf-8"` from scripts/wire-shape.py and observing
    THIS test fail under this same environment, before restoring it).
    """
    schemas_dir, shapes_dir = _make_scratch_wires(tmp_path)
    non_ascii_name = "café_source"
    mutated = _rewrite_json(
        schemas_dir / SUGGESTIONS_WIRE,
        lambda schema: _add_property_to_suggestions_items(schema, name=non_ascii_name),
    )

    env = dict(os.environ)
    env.update(LC_ALL="C", LANG="C", PYTHONUTF8="0", PYTHONCOERCECLOCALE="0")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "wire-shape.py"),
            "--regenerate",
            "--schemas-dir", str(schemas_dir),
            "--shapes-dir", str(shapes_dir),
        ],
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"stdout={result.stdout!r} stderr={result.stderr!r}"

    manifest_path = shapes_dir / shape_manifest_filename(SUGGESTIONS_WIRE)
    written_bytes = manifest_path.read_bytes()

    # The raw UTF-8 bytes, not a "é" JSON escape — proves
    # ensure_ascii=False survived the write, and that the write used UTF-8
    # rather than the (here, deliberately non-UTF-8) platform default.
    assert non_ascii_name.encode("utf-8") in written_bytes
    assert b"\\u00e9" not in written_bytes

    expected = serialize_manifest(build_manifest(mutated, source=SUGGESTIONS_WIRE)).encode("utf-8")
    assert written_bytes == expected


# ──────────────────────────────────────────────────────────────────────────────
# Carry-forward (c): manifest_filename is the ONE place this convention lives
# ──────────────────────────────────────────────────────────────────────────────

def test_manifest_filename_is_importable_from_wire_shape_and_reexported_by_wire_gate():
    for document in PUBLISHED_WIRES:
        assert shape_manifest_filename(document) == document.replace(".schema.json", ".shape.json")

    # wire_gate.py re-exports the SAME function object rather than defining
    # a second, independently-typed copy of the same convention.
    assert gate_manifest_filename is shape_manifest_filename


def test_wire_manifests_test_module_no_longer_reimplements_the_naming_convention():
    """Regression guard for 'no duplicate left in the test module' — reads
    the actual source of tests/test_035_wire_manifests.py and asserts the
    stem-slicing that used to live in its local `_manifest_path` is gone.
    """
    source = (REPO_ROOT / "tests" / "test_035_wire_manifests.py").read_text(encoding="utf-8")
    assert '[: -len(".schema.json")]' not in source
    assert "manifest_filename" in source
