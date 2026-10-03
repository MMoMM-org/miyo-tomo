#!/usr/bin/env python3
"""spec038-wire-edit.py — set an editable attachment-conflict field on a published
suggestions wire, and PROVE the wire now counts as edited.

For spec 038 T5.3's live runs. Hashi's Suggestions Editor is the surface that will
normally do this, but its vendored schema still pins schema_version "2" and contains
none of the remedy fields (measured 2026-10-03), so today the only way to exercise
the wire path end to end is to set the field here. This script stands in for the
editor and for nothing else.

    spec038-wire-edit.py <suggestions.json> --show
    spec038-wire-edit.py <suggestions.json> --remedy keep_in_inbox
    spec038-wire-edit.py <suggestions.json> --proposed-name "karte-1938.png"
    spec038-wire-edit.py <suggestions.json> --proposed-name "karte*1938.png"

WHY it refuses to touch `emit_digest`: that field IS the change signal. ADR-026 makes
an edited wire the sole authoritative source, and "edited" means a recomputation over
the editable payload no longer matches the stored digest. Rewriting the digest to match
would make the edit invisible and send Pass 2 down the markdown path instead — the run
would look like it passed while testing the wrong path.

WHY it asserts staleness after writing rather than assuming it: the digest is canonical
(sorted keys, no incidental whitespace) and excludes `emit_digest` itself, so it is
invariant to re-serialization. Opening the file in an editor and saving it with different
formatting does NOT stale it. Only a semantic change does. A run staged on the assumption
that "I edited the file, so it is edited" can therefore be wrong, silently, and the three
routes into that mistake all end with Pass 2 reading the markdown twice and passing.

Writes only the file named on the command line. Never touches a vault note, never runs
Tomo, never reaches Kado.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REMEDIES = ("rename", "keep_in_inbox", "ignore")


def _load_digest_fn():
    """Import compute_payload_digest from the repo's own lib — never reimplement it.

    A second copy of the canonical-serialization rule here would agree with the
    producer today and drift the moment either side changed, which is the exact
    failure mode this script exists to detect.
    """
    override = os.environ.get("TOMO_SCRIPTS_DIR")
    lib_root = Path(override) if override else Path(__file__).resolve().parent.parent / "tomo" / "scripts"
    if not (lib_root / "lib" / "render_md.py").exists():
        sys.exit(
            f"spec038-wire-edit: cannot find lib/render_md.py under {lib_root}\n"
            "Run from the repo, or set TOMO_SCRIPTS_DIR to a tomo/scripts directory."
        )
    sys.path.insert(0, str(lib_root))
    from lib.render_md import compute_payload_digest  # noqa: E402

    return compute_payload_digest


def _conflicts(wire: dict, path: Path) -> list[dict]:
    if "attachment_conflicts" not in wire:
        version = wire.get("schema_version")
        hint = (
            "That version predates the field; the instance that published this wire was "
            "not synced. Run scripts/update-tomo.sh --instance tomo-instance --yolo and "
            "re-run Pass 1."
            if version != "3"
            else "The version is current, so the key is missing for some other reason — "
            "read the wire before going further rather than editing around it."
        )
        sys.exit(
            f"spec038-wire-edit: {path} has no 'attachment_conflicts' key "
            f"(schema_version {version!r}).\n{hint}"
        )
    conflicts = wire["attachment_conflicts"]
    if not conflicts:
        sys.exit(
            f"spec038-wire-edit: {path} carries an EMPTY attachment_conflicts list.\n"
            "Pass 1 found no destination collision, so there is nothing to edit and "
            "nothing for the live run to prove. Check the fixture before editing."
        )
    return conflicts


def _show(conflicts: list[dict], wire: dict, digest_fn) -> None:
    stored = wire.get("emit_digest")
    recomputed = digest_fn(wire)
    print(f"schema_version : {wire.get('schema_version')!r}")
    print(f"emit_digest    : {stored}")
    print(f"recomputed     : {recomputed}")
    print(f"counts as      : {'EDITED (wire is authoritative)' if stored != recomputed else 'UNCHANGED (markdown path)'}")
    print(f"\nattachment_conflicts: {len(conflicts)} entry(ies)")
    for i, c in enumerate(conflicts):
        print(f"  [{i}] source        : {c.get('source')}")
        print(f"      destination   : {c.get('destination')}")
        print(f"      same_file     : {c.get('same_file')!r}")
        print(f"      remedy        : {c.get('remedy')!r}      <- editable")
        print(f"      proposed_name : {c.get('proposed_name')!r}   <- editable")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("wire", type=Path, help="the published _suggestions.json")
    ap.add_argument("--index", type=int, default=0, help="which conflict entry (default 0)")
    ap.add_argument("--remedy", choices=REMEDIES, help="set the remedy")
    ap.add_argument("--proposed-name", help="set the rename target basename")
    ap.add_argument("--show", action="store_true", help="print state and exit, writing nothing")
    args = ap.parse_args()

    digest_fn = _load_digest_fn()

    if not args.wire.is_file():
        sys.exit(f"spec038-wire-edit: no such file: {args.wire}")
    try:
        wire = json.loads(args.wire.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        sys.exit(
            f"spec038-wire-edit: {args.wire} is not valid JSON ({exc}).\n"
            "An unparseable wire is one of the three routes to the markdown path, so "
            "fix this rather than running with it."
        )

    conflicts = _conflicts(wire, args.wire)

    if args.show or (args.remedy is None and args.proposed_name is None):
        _show(conflicts, wire, digest_fn)
        if not args.show:
            print("\n(nothing to change — pass --remedy and/or --proposed-name)")
        return 0

    if args.index >= len(conflicts):
        sys.exit(f"spec038-wire-edit: --index {args.index} but only {len(conflicts)} conflict(s)")
    entry = conflicts[args.index]

    stored = wire.get("emit_digest")
    before = digest_fn(wire)
    if stored != before:
        print(
            "spec038-wire-edit: NOTE — this wire was ALREADY edited before this run "
            f"(stored {stored}, recomputed {before}). Proceeding; staleness is still "
            "asserted below.",
            file=sys.stderr,
        )

    changes = []
    if args.remedy is not None:
        changes.append(f"remedy: {entry.get('remedy')!r} -> {args.remedy!r}")
        entry["remedy"] = args.remedy
    if args.proposed_name is not None:
        changes.append(f"proposed_name: {entry.get('proposed_name')!r} -> {args.proposed_name!r}")
        entry["proposed_name"] = args.proposed_name

    after = digest_fn(wire)
    if after == stored:
        sys.exit(
            "spec038-wire-edit: REFUSING TO WRITE — the recomputed digest still matches "
            f"emit_digest ({stored}).\nThe values you asked for are the ones already "
            "there, so this edit would be a no-op and Pass 2 would take the MARKDOWN "
            "path. Pick a different value."
        )

    # emit_digest is deliberately left as the producer wrote it. That mismatch is the
    # whole point: it is what makes load_changed_wire return the wire.
    args.wire.write_text(
        json.dumps(wire, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    for c in changes:
        print(f"  changed  {c}")
    print(f"\n  emit_digest  {stored}   (left untouched, on purpose)")
    print(f"  recomputed   {after}")
    print("\n  ASSERTED: the two differ, so this wire now counts as EDITED and Pass 2")
    print("            must report: suggestions-json: edited wire is authoritative (JSON-only path)")
    print("            If that line is absent from Pass 2's output, the run proved nothing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
