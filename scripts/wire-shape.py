#!/usr/bin/env python3
# wire-shape.py — The maintainer's CLI for the wire-shape manifests (spec 035 T4.1).
# version: 0.4.0
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

WARNING — --regenerate is destructive and unrecoverable by this tool:
  It overwrites each drifted manifest with a plain truncating write — no
  backup, no temp file, no atomic swap. The instant the write returns, the
  PRIOR bytes at that path are gone. This tool keeps no copy. Git is the
  only recovery path, and only if the manifest was committed (or at least
  staged/stashed) before you ran this — an uncommitted manifest edit, or
  one left over from an earlier --regenerate you never committed, is lost
  with no trace once a later run touches the same file.

  The printed diff is NOT a recovery format — it is display text, built to
  be read, not parsed back into a manifest. What it preserves varies by
  change kind:
    - type_changed / openness_changed: old -> new is printed inline, so
      that one field IS reconstructable from the diff alone.
    - added_enum_value / removed_enum_value: the specific value is named,
      so a removed enum member's value IS reconstructable.
    - enum_constraint_added / enum_constraint_removed: the constraint's
      full value set at the surviving side is named (see
      lib/wire_shape.py's _diff_node), so a removed constraint's prior
      enum IS reconstructable from the diff alone.
    - added_property / removed_property: only the property's NAME is
      printed — its prior type, required-ness and enum values are not.
    - node_added / node_removed: only the POINTER is printed — nothing
      about what the removed subtree contained.
  If you need the prior manifest, `git show HEAD:<path>` before running
  this, not the terminal scrollback afterward.
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


def _format_change_row(document: str, change: dict, marker: str, transition: str) -> str:
    """One line: document, pointer, change kind, the already-resolved
    affecting/not-affecting marker, the change detail, and the version
    transition — the single row shape both `--regenerate`'s printed diff
    and `--obligations`' preview use (plan T4.1: "one row per changed
    field"). `detail` is display-only structural text (a property/type/
    enum-value name — see wire_shape.py's `_change` docstring); it never
    carries schema prose.

    Takes `marker` pre-resolved rather than resolving it itself, so this is
    the ONE place the row format is written down — `_render_change_row`
    (which classifies fresh) and `cmd_obligations` (which reuses
    `gate_one_wire`'s already-resolved verdict) both format through this,
    instead of each hand-writing the same f-string.
    """
    return (
        f"{document}: {change['pointer']} {change['kind']} ({marker}): "
        f"{change['detail']} [version {transition}]"
    )


def _render_change_row(document: str, change: dict, observed_nodes: dict, transition: str) -> str:
    """`_format_change_row`, with the marker resolved via `classify()`
    against a freshly-built node map. `--regenerate` has no `gate_one_wire`
    result to reuse — it diffs against its own just-built `new_manifest`
    directly — so this is where it classifies before formatting.
    """
    affecting = classify(change, observed_nodes)
    marker = "affecting" if affecting else "not affecting"
    return _format_change_row(document, change, marker, transition)


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

    Prints EACH wire's diff before writing that wire's manifest, never
    after. Nothing about the diff depends on the write having happened —
    `document`, `changes`, `transition` and `new_manifest["nodes"]` are all
    known beforehand — so there is no ordering reason to write first. The
    reverse order (write, then print) leaves a rewritten baseline with no
    printed record if the print step fails for ANY reason after the write
    — a broken pipe, a full disk on redirected stdout, a future formatting
    bug — which is exactly the "silent rewrite" ADR-3 exists to prevent,
    just moved from "the write is skipped" to "the write already landed
    and nothing says so." Print-first means that failure mode aborts the
    command having changed nothing for that wire instead.
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

        transition = f"{old_version!r} -> {new_manifest['schema_version']!r}"
        print(f"{document}: manifest regenerated ({transition})")
        for change in changes:
            print("  " + _render_change_row(document, change, new_manifest["nodes"], transition))

        shapes_dir.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(serialize_manifest(new_manifest), encoding="utf-8")
        touched.append(document)

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
        # format through the SAME row-builder --regenerate uses
        # (_format_change_row) instead of a second hand-written f-string,
        # rather than re-running classify() on data that's already
        # classified.
        for change in result["changes"]:
            marker = "affecting" if change["consumer_affecting"] else "not affecting"
            print(_format_change_row(result["document"], change, marker, transition))

    if not printed:
        print("wire-shape --obligations: no shape drift against any committed manifest.")
    return 0


def main(argv: list[str] | None = None) -> int:
    # Any of the three subcommands can print a non-ASCII property/type/
    # enum-value name — `detail` is schema-derived, not just --regenerate's
    # diff — so this applies to all three, not only the write path (the
    # manifest FILE write is already pinned to UTF-8 separately — see
    # build_manifest/serialize_manifest). Without this, sys.stdout/
    # sys.stderr encode with the platform default, which is not UTF-8
    # everywhere (LC_ALL=C and friends) — found the hard way: under that
    # locale, printing such a name after --regenerate had ALREADY written
    # the manifest raised UnicodeEncodeError mid-print, breaking ADR-3's
    # "regeneration always prints the diff" precisely in the one locale
    # where the write side's own UTF-8 pin mattered.
    #
    # Deliberately global (mutates sys.stdout/sys.stderr for the calling
    # process, not just this function's own output), not scoped narrower —
    # weighed and kept: this script's only in-process caller is its own
    # test suite (`wire_shape_cli.main(argv)`); every real invocation runs
    # as a subprocess, where "the calling process" IS this script, so there
    # is nothing else to leak into. Reconfiguring to UTF-8 is also
    # idempotent and one-directional (widens acceptance, narrows nothing),
    # so even the in-process test-suite case has no observed downside — the
    # full suite passes with it applied on every main() call.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

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
