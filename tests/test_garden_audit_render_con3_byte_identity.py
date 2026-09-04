#!/usr/bin/env python3
# version: 0.1.0
"""test_garden_audit_render_con3_byte_identity.py — spec 033 T5.2 (CON-3).

Spec 033 split the old `broken_up` check into two: `broken_up` (still
fixable, reworded per T4.2) and the new `parent_not_moc` (advisory, not
fixable). CON-3 says every OTHER check's rendered report block must be
untouched by this split. This is proven by loading the pre-spec
garden-audit-render.py from git — commit 8d866bb, the last commit before
Phase 1 of this branch — under a distinct module name, and diffing its
output against the current module's output for the same mixed document.

Deliberately NOT a line-count proxy (`git diff 8d866bb -- ... | wc -l`, or
asserting "exactly N lines differ" in the rendered report): spec 032's own
CON-7 guard used a changed-line count and went hollow the moment a second,
legitimate property-side change landed — a count that happened to be right
for one PR silently stopped meaning anything for the next. This guard scopes
to a named set of finding BLOCKS (split on `### F<id>` headings, the same
split `_split_report_blocks` already uses for --suggest enrichment) and
diffs each one by its finding id — so it survives every future PR that adds
another broken_up/parent_not_moc-only change without ever being re-tuned.

Handling the old module's ignorance of `parent_not_moc` (spec 033 T2.1 ADR-1
splits it out of `broken_up`; the pre-spec module has never heard of it):
the old renderer neither raises nor drops the finding — `_CHECK_LABEL.get`
falls back to the literal check string as the heading label, no per-check
detail-line branch matches so no detail line is added, and the missing
`decision` key routes it into the generic advisory fallback ("_Advisory —
no automated fix. Review and handle manually._"). It renders SOMETHING, just
not what the new module renders — which is fine, because `parent_not_moc`
is itself one of the broken-parent checks this guard exists to exempt, not
one it needs to protect.
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS_DIR = _ROOT / "tomo" / "scripts"
_SCRIPT = _SCRIPTS_DIR / "garden-audit-render.py"
_PRE_SPEC_SHA = "8d866bb"  # last commit before spec 033 Phase 1 (plan/phase-5.md T5.2)

sys.path.insert(0, str(_SCRIPTS_DIR))

# ---------------------------------------------------------------------------
# Load both the current module and the pre-spec-033 module from git, under
# distinct names — mirrors the pattern already established in
# test_garden_audit_render.py (test_mixed_doc_body_resident_output_byte_identical_con7).
# ---------------------------------------------------------------------------

_spec = importlib.util.spec_from_file_location("garden_audit_render_con3_new", _SCRIPT)
new_gar = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(new_gar)


def _load_pre_spec_module():
    content = subprocess.run(
        ["git", "show", f"{_PRE_SPEC_SHA}:tomo/scripts/garden-audit-render.py"],
        cwd=_ROOT, capture_output=True, check=True, text=True,
    ).stdout
    with tempfile.TemporaryDirectory() as td:
        old_path = Path(td) / "garden_audit_render_pre_spec033.py"
        old_path.write_text(content, encoding="utf-8")
        old_spec = importlib.util.spec_from_file_location(
            "garden_audit_render_con3_pre_spec033", old_path
        )
        old_mod = importlib.util.module_from_spec(old_spec)
        old_spec.loader.exec_module(old_mod)
        return old_mod


old_gar = _load_pre_spec_module()

_GENERATED = "2026-09-04T12:00:00Z"
_RUN_ID = "run-con3-test-001"
_PROFILE = "miyo"

# ---------------------------------------------------------------------------
# One finding per check, covering the full set garden-audit.py emits —
# including both spec 033 outputs (broken_up, parent_not_moc) so the guard
# proves the split's OWN blocks legitimately differ while everything else
# does not.
# ---------------------------------------------------------------------------


def _make_mixed_findings() -> list[dict]:
    return [
        {
            "id": "F01",
            "check": "unparented",
            "tier": "structure",
            "fixable": True,
            "target": {"path": "Notes/Orphan Note.md", "stem": "Orphan Note"},
            "detail": {
                "candidate_mocs": [{"target_moc": "MOCs/Writing MOC.md", "score": 0.8}],
            },
            "decision": {"selected": True, "action": "link_to_moc"},
        },
        {
            "id": "F02",
            "check": "orphan",
            "tier": "structure",
            "fixable": True,
            "target": {"path": "Notes/Graph Orphan.md", "stem": "Graph Orphan"},
            "detail": {
                "candidate_mocs": [{"target_moc": "MOCs/Reading MOC.md", "score": 0.6}],
            },
            "decision": {"selected": False, "action": "link_to_moc"},
        },
        {
            "id": "F03",
            "check": "broken_up",
            "tier": "integrity",
            "fixable": True,
            "target": {"path": "Notes/Broken Note.md", "stem": "Broken Note"},
            "detail": {
                "up_target": "Deleted MOC",
                "up_source": "inline",
                "up_value": None,
                "up_broken_reason": "unresolved",
            },
            "decision": {"selected": True, "action": "edit_note_text"},
        },
        {
            "id": "F04",
            "check": "dead_link",
            "tier": "integrity",
            "fixable": True,
            "target": {"path": "Notes/Source Note.md", "stem": "Source Note"},
            "detail": {"dead_target": "Missing Note", "count": 2},
            "decision": {"selected": True, "action": "edit_note_text"},
        },
        {
            "id": "F05",
            "check": "duplicate_stem",
            "tier": "advisory",
            "fixable": False,
            "target": {"path": "Notes/Dup.md", "stem": "Dup"},
            "detail": {"dupes": ["Notes/Dup.md", "Archive/Dup.md"]},
        },
        {
            "id": "F06",
            "check": "stale_moc",
            "tier": "advisory",
            "fixable": False,
            "target": {"path": "MOCs/Old MOC.md", "stem": "Old MOC"},
            "detail": {"mtime": "2026-01-01T00:00:00Z"},
        },
        {
            "id": "F07",
            "check": "parent_not_moc",
            "tier": "advisory",
            "fixable": False,
            "target": {"path": "Notes/Untagged Parent Child.md", "stem": "Untagged Parent Child"},
            "detail": {
                "up_target": "Real Note",
                "up_source": "inline",
                "up_value": None,
                "up_broken_reason": "not-a-moc",
            },
        },
    ]


# Checks whose rendered block is EXPECTED to change under spec 033 — the
# split this guard exists to fence around, not to protect.
_BROKEN_PARENT_CHECKS = {"broken_up", "parent_not_moc"}

_RE_FINDING_HEADER = re.compile(r"^###\s+(F\d+)\b")


def _make_doc() -> dict:
    return {
        "run_id": _RUN_ID,
        "generated": _GENERATED,
        "profile": _PROFILE,
        "findings": _make_mixed_findings(),
        "skipped_checks": [],
        "skipped_checks_reason": "",
        "reappeared_exclusions": [],
    }


def _blocks_by_fid(report_md: str, split_fn) -> dict[str, list[str]]:
    """{fid: block lines} using the module's OWN `_split_report_blocks` —
    block 0 (everything before the first `### F<id>` heading) is dropped:
    it necessarily differs between old and new (the Summary's new "Flagged
    parents:" line and the new "Untagged parents" block are both aggregate
    content ABOUT broken-parent findings, not about any of the other checks
    this guard protects)."""
    blocks = split_fn(report_md)
    out: dict[str, list[str]] = {}
    for block in blocks[1:]:
        m = _RE_FINDING_HEADER.match(block[0])
        assert m, f"block does not start with a finding heading: {block[0]!r}"
        out[m.group(1)] = block
    return out


class TestUnrelatedChecksByteIdenticalToPreSpec:
    def test_every_non_broken_parent_block_is_byte_identical(self):
        doc = _make_doc()
        old_report = old_gar.render_report(doc)
        new_report = new_gar.render_report(doc)

        old_blocks = _blocks_by_fid(old_report, old_gar._split_report_blocks)
        new_blocks = _blocks_by_fid(new_report, new_gar._split_report_blocks)

        findings_by_id = {f["id"]: f for f in doc["findings"]}
        assert set(old_blocks) == set(new_blocks) == set(findings_by_id)

        unrelated_ids = [
            fid for fid, f in findings_by_id.items()
            if f["check"] not in _BROKEN_PARENT_CHECKS
        ]
        # Sanity: the mixed doc actually exercises every unrelated check —
        # a shrunk fixture would make this guard pass vacuously.
        unrelated_checks = {findings_by_id[fid]["check"] for fid in unrelated_ids}
        assert unrelated_checks == {
            "unparented", "orphan", "dead_link", "duplicate_stem", "stale_moc",
        }

        mismatches = {
            fid: (old_blocks[fid], new_blocks[fid])
            for fid in unrelated_ids
            if old_blocks[fid] != new_blocks[fid]
        }
        assert mismatches == {}, (
            f"CON-3 violated — non-broken-parent block(s) changed: "
            f"{sorted(mismatches)}"
        )

    def test_broken_parent_blocks_do_in_fact_differ(self):
        # Negative-control: F03 (broken_up) and F07 (parent_not_moc) are
        # EXPECTED to differ — proves the fixture and the split both
        # actually exercise the changed path, so the byte-identity result
        # above isn't just "nothing rendered differently at all".
        doc = _make_doc()
        old_report = old_gar.render_report(doc)
        new_report = new_gar.render_report(doc)
        old_blocks = _blocks_by_fid(old_report, old_gar._split_report_blocks)
        new_blocks = _blocks_by_fid(new_report, new_gar._split_report_blocks)
        assert old_blocks["F03"] != new_blocks["F03"]
        # F07 didn't exist as "parent_not_moc" pre-spec at all — the old
        # module renders SOMETHING (see module docstring) but never the
        # target-naming advisory message T4.1 adds.
        assert "not yet tagged as a MOC" not in "\n".join(old_blocks["F07"])
        assert "not yet tagged as a MOC" in "\n".join(new_blocks["F07"])
