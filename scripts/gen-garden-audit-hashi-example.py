#!/usr/bin/env python3
# version: 0.1.0
"""gen-garden-audit-hashi-example.py — generate + validate the real garden-audit
edit_note_text instruction-set example for the Phase-6 Hashi handoff (spec 030).

Example-driven, no hand-authored JSON: builds a representative garden-audit doc
covering every fixable ACTION path, renders BOTH artifacts (report .md + wire
.json) from that one doc (consistent by construction), makes the user decisions in
the report markdown, runs the ACTUAL Pass-2 pipeline
(garden-audit-parser.build_from_report -> render_actions.build_garden_audit_actions),
wraps the envelope exactly as instruction-render.py does for upstream-type=garden-audit,
and VALIDATES it against tomo/schemas/hashi-instructions.schema.json.

Emits three files under --out-dir (default tomo-tmp/hashi-example):
  garden-audit-report.md          (with decisions made)
  garden-audit-wire.json          (the machine structure, unedited)
  garden-audit-instructions.json  (the validated instruction-set)

Run:  ./venv/bin/python scripts/gen-garden-audit-hashi-example.py
Exit 0 iff the generated instruction-set validates.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import jsonschema

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "tomo" / "scripts"
SCHEMA = REPO / "tomo" / "schemas" / "hashi-instructions.schema.json"
sys.path.insert(0, str(SCRIPTS))


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gar = _load("garden_audit_render", "garden-audit-render.py")
gap = _load("garden_audit_parser", "garden-audit-parser.py")
from lib.render_actions import build_garden_audit_actions  # noqa: E402


def _finding(fid, check, tier, path, stem, detail, action):
    return {
        "id": fid, "check": check, "tier": tier, "fixable": True,
        "target": {"path": path, "stem": stem}, "detail": detail,
        "decision": {"selected": True, "action": action},
    }


def _representative_doc() -> dict:
    """A doc covering every fixable garden-audit action path (real-shaped)."""
    return {
        "run_id": "41c6cd18-63b2-4e5b-86b7-da55aa3298e5",
        "generated": "2026-07-21T17:38:48.542300+00:00",
        "profile": "miyo",
        "skipped_checks": [], "skipped_checks_reason": "",
        "reappeared_exclusions": [],
        "findings": [
            # dead_link — user will fill Replace (→ edit_note_text replace).
            _finding("F04", "dead_link", "integrity", "020 Active MOC.md",
                     "020 Active MOC", {"dead_target": "023 Sparks MOC", "count": 1},
                     "edit_note_text"),
            # dead_link — user leaves Replace empty (→ edit_note_text remove).
            _finding("F05", "dead_link", "integrity", "020 Active MOC.md",
                     "020 Active MOC", {"dead_target": "024 Thinking About MOC", "count": 1},
                     "edit_note_text"),
            # broken_up — user fills Repoint (→ add_relationship).
            _finding("F01", "broken_up", "integrity", "021 Fleeting MOC.md",
                     "021 Fleeting MOC", {"up_target": "['020 Active MOC']"},
                     "edit_note_text"),
            # broken_up — user leaves Repoint empty (→ edit_note_text up:: removal).
            _finding("F02", "broken_up", "integrity", "022 Placeholders MOC.md",
                     "022 Placeholders MOC", {"up_target": "['021 Fleeting MOC']"},
                     "edit_note_text"),
            # orphan — user files it under a MOC (→ link_to_moc + add_relationship).
            _finding("F10", "orphan", "structure", "005 Important Links.md",
                     "005 Important Links", {"candidate_mocs": []}, "link_to_moc"),
        ],
    }


# The decisions the user makes in the markdown (F-id -> substitutions).
_REPLACEMENTS = [
    # F04 dead_link: fill Replace → repoint the dead link.
    ("- [x] Apply", "- [x] Apply"),  # (Apply already ticked by default)
]


def _make_decisions(report: str) -> str:
    """Simulate the user's markdown edits: tick Approved, fill some targets."""
    # F04 dead_link — Replace filled. F05 — left empty (removal).
    report = report.replace(
        "**Replace with:** [[]]    ← fill a target to repoint, or leave empty to remove",
        "**Replace with:** [[023 Sparks (MOC)]]",
        1,  # only the FIRST dead_link (F04)
    )
    # F01 broken_up — Repoint filled. F02 — left empty (up:: removal).
    report = report.replace(
        "**Repoint to:** [[]]    ← enter the correct MOC to repoint up::, or leave empty to remove",
        "**Repoint to:** [[020 Active MOC]]",
        1,  # only the FIRST broken_up (F01)
    )
    # F10 orphan — File under a chosen MOC.
    report = report.replace(
        "**File under:** [[]]    ← enter a MOC to file this note under, or pick a suggestion below",
        "**File under:** [[000 Home MOC]]",
        1,
    )
    # Tick the top-level Approved gate.
    report = report.replace("- [ ] Approved", "- [x] Approved", 1)
    return report


def main() -> int:
    out_dir = REPO / "tomo-tmp" / "hashi-example"
    if len(sys.argv) > 1:
        out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    doc = _representative_doc()

    # Render BOTH artifacts from the one doc (consistent by construction).
    report = "\n".join(gar.render_frontmatter(doc)) + "\n" + gar.render_report(doc)
    wire = gar.build_wire_payload(doc)
    report = _make_decisions(report)

    # Run the ACTUAL Pass-2: report decisions + wire structure -> confirmed_items.
    confirmed = gap.build_from_report(report, wire)["confirmed_items"]
    # -> Hashi actions (the same builder instruction-render uses for garden-audit).
    actions = build_garden_audit_actions(confirmed)

    # Wrap the envelope exactly as instruction-render.py does (schema_version "2").
    now = datetime.now(timezone.utc).replace(microsecond=0)
    instructions = {
        "schema_version": "2",
        "type": "tomo-instructions",
        "source_suggestions": "garden-audit-report",
        "generated": now.isoformat().replace("+00:00", "Z"),
        "profile": doc["profile"],
        "tomo_version": None,
        "action_count": len(actions),
        "md_peer": "2026-07-21_1738_garden-audit",
        "actions": actions,
        "tomo": {
            "doc_type": "garden-audit",
            "state": "pending-apply",
            "run_id": doc["run_id"],
        },
    }

    # VALIDATE against the shipped Hashi schema — fail loudly on any gap.
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.validate(instance=instructions, schema=schema)

    (out_dir / "garden-audit-report.md").write_text(report, encoding="utf-8")
    (out_dir / "garden-audit-wire.json").write_text(
        json.dumps(wire, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "garden-audit-instructions.json").write_text(
        json.dumps(instructions, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    kinds = sorted({a["action"] for a in actions})
    print(f"OK — {len(actions)} actions, kinds={kinds}", file=sys.stderr)
    print(f"VALIDATED against {SCHEMA.name}", file=sys.stderr)
    print(f"wrote → {out_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
