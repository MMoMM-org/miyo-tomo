#!/usr/bin/env python3
# wire-shape.py — The maintainer's CLI for the wire-shape manifests (spec 035 T4.1).
# version: 0.1.0
"""Check, regenerate, or explain the shape manifests under tomo/schemas/shapes/
— the committed baseline `pytest` gates every published wire schema against
(lib/wire_gate.py). Wraps describe_shape / diff_shapes / classify
(lib/wire_shape.py) and the gate built on top of them (lib/wire_gate.py); it
adds no detection logic of its own.

Usage:
  python3 scripts/wire-shape.py --check
      Same pass/fail decision the test suite makes. Exits non-zero and
      prints the failure report when a published wire's schema has drifted
      from its committed manifest; silent and exits zero when nothing has.

  python3 scripts/wire-shape.py --regenerate
      Rewrites the manifest for every wire whose schema no longer matches
      its committed manifest, and prints the diff it applied — pointer,
      change kind, whether it obliges the consumer, and the version
      transition — for every wire it touches. ADR-3: regeneration is always
      an explicit, printed act; a silent rewrite would make a deliberate
      shape change indistinguishable from a maintainer running this
      reflexively. Writes nothing, and says so, when no wire has drifted.

  python3 scripts/wire-shape.py --obligations
      Prints the same per-change rows --regenerate would print, without
      writing anything — a preview, for deciding whether a handoff is
      needed before committing to move a schema_version.

  --schemas-dir / --shapes-dir override the default tomo/schemas and
  tomo/schemas/shapes (real repo paths) — mainly so tests can point this at
  a scratch tree.

Every printed line is pointer, change kind, a short structural detail
(property/type/enum-value name — never a schema's own prose), document
filename, and version — the same metadata-only contract lib/wire_gate.py's
`render_wire_gate_report` already keeps (MiYo Constitution L1: reports never
carry schema descriptions, vault content, or credentials).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts"
sys.path.insert(0, str(LIB_DIR))

from lib.wire_gate import (  # noqa: E402
    manifest_filename,
    render_wire_gate_report,
    run_wire_gate,
)
from lib.wire_shape import (  # noqa: E402
    PUBLISHED_WIRES,
    build_manifest,
    classify,
    diff_shapes,
    serialize_manifest,
)

DEFAULT_SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
DEFAULT_SHAPES_DIR = DEFAULT_SCHEMAS_DIR / "shapes"


def _read_manifest(manifest_path: Path) -> dict | None:
    """The committed manifest at `manifest_path`, or `None` when it doesn't
    exist yet — a wire with no manifest regenerates from an empty baseline
    (every node reads as newly added) rather than raising, so `--regenerate`
    can also be the thing that creates a first manifest for a new wire.
    """
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None


def _render_change_row(document: str, change: dict, observed_nodes: dict, transition: str) -> str:
    """One line: document, pointer, change kind, whether it obliges the
    consumer, the change detail, and the version transition — the four
    facts plan T4.1 asks `--obligations`' rows to carry. `detail` is
    display-only structural text (a property/type/enum-value name — see
    wire_shape.py's `_change` docstring); it never carries schema prose.
    """
    affecting = classify(change, observed_nodes)
    marker = "affecting" if affecting else "not affecting"
    return (
        f"{document}: {change['pointer']} {change['kind']} ({marker}): "
        f"{change['detail']} [version {transition}]"
    )


def cmd_check(schemas_dir: Path, shapes_dir: Path) -> int:
    """The same pass/fail decision `pytest` makes (lib/wire_gate.py's
    ADR-3 gate): any shape change fails, regardless of whether it obliges
    the consumer. Silent on a clean tree — `render_wire_gate_report`
    already renders an all-green run as `""` (the SDD's "pass silently").
    """
    results = run_wire_gate(schemas_dir, shapes_dir)
    report = render_wire_gate_report(results)
    if report:
        print(report)
        return 1
    return 0


def cmd_regenerate(schemas_dir: Path, shapes_dir: Path) -> int:
    """Rewrite the manifest for every wire whose schema no longer matches
    its committed manifest, printing the diff it applied as it goes
    (ADR-3). A wire with no diff is left untouched — bytes AND mtime
    unchanged — and contributes nothing to the printed output. If nothing
    anywhere changed, says so explicitly rather than exiting silent, so a
    maintainer who ran this reflexively still sees that it did nothing.
    """
    touched: list[str] = []

    for document in PUBLISHED_WIRES:
        schema_path = schemas_dir / document
        manifest_path = shapes_dir / manifest_filename(document)

        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        new_manifest = build_manifest(schema, source=document)

        old_manifest = _read_manifest(manifest_path)
        old_nodes = old_manifest["nodes"] if old_manifest else {}
        old_version = old_manifest["schema_version"] if old_manifest else None

        changes = diff_shapes(old_nodes, new_manifest["nodes"])
        if not changes:
            continue

        shapes_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(serialize_manifest(new_manifest), encoding="utf-8")
        touched.append(document)

        transition = f"{old_version!r} -> {new_manifest['schema_version']!r}"
        print(f"{document}: manifest regenerated ({transition})")
        for change in changes:
            print("  " + _render_change_row(document, change, new_manifest["nodes"], transition))

    if not touched:
        print("wire-shape --regenerate: no shape drift against any committed manifest; nothing written.")
    return 0


def cmd_obligations(schemas_dir: Path, shapes_dir: Path) -> int:
    """Print the obligation table `--regenerate` would apply, without
    writing anything — one row per changed field, naming the pointer, the
    change, whether it obliges the consumer, and the version transition
    (PRD/F4-AC2: this is the handoff's raw material). Reuses
    `run_wire_gate` directly, so a row here and a `--check` failure line
    can never disagree about what changed or how it classifies.
    """
    results = run_wire_gate(schemas_dir, shapes_dir)
    printed = False

    for result in results:
        if result["error"]:
            print(f"{result['document']}: {result['error']}")
            printed = True
            continue
        if not result["changes"]:
            continue
        printed = True
        transition = f"{result['manifest_version']!r} -> {result['schema_version']!r}"
        # gate_one_wire already resolved consumer_affecting via classify();
        # reuse that instead of a second describe_shape pass here.
        for change in result["changes"]:
            marker = "affecting" if change["consumer_affecting"] else "not affecting"
            print(
                f"{result['document']}: {change['pointer']} {change['kind']} "
                f"({marker}): {change['detail']} [version {transition}]"
            )

    if not printed:
        print("wire-shape --obligations: no shape drift against any committed manifest.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check, regenerate, or explain the wire-shape manifests under "
        "tomo/schemas/shapes/ (spec 035).",
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="pass/fail against the committed manifests")
    mode.add_argument("--regenerate", action="store_true", help="rewrite drifted manifests, printing the diff")
    mode.add_argument("--obligations", action="store_true", help="print the obligation table without writing")
    parser.add_argument("--schemas-dir", type=Path, default=DEFAULT_SCHEMAS_DIR)
    parser.add_argument("--shapes-dir", type=Path, default=DEFAULT_SHAPES_DIR)
    args = parser.parse_args(argv)

    try:
        if args.check:
            return cmd_check(args.schemas_dir, args.shapes_dir)
        if args.regenerate:
            return cmd_regenerate(args.schemas_dir, args.shapes_dir)
        return cmd_obligations(args.schemas_dir, args.shapes_dir)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"wire-shape: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
