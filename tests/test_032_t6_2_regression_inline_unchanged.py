#!/usr/bin/env python3
# version: 1.0.0
"""test_032_t6_2_regression_inline_unchanged.py — Phase 6 T6.2 (spec 032).

CON-7: "This is a routing addition, not a rewrite." For an all-inline fixture
(every broken_up finding declared in the body, never in frontmatter), spec 032
must change NOTHING observable: the instruction set (the actions list built by
render_actions.build_garden_audit_actions), the markdown report, and the
remove_up_link / add_relationship emission must all be byte-identical to the
pre-spec baseline.

Technique (same one used three times already in this spec, in
test_garden_audit_render.py's CON-7 tests): load the module as it stood at a
known commit via ``git show <sha>:<path>`` into a tempfile, exec it under a
DISTINCT module name, run it side-by-side with the current module on the SAME
input, and assert equality. Here the baseline is 781aaf2 — the last commit
before this branch's first code change (995e35a) — so the comparison covers
the WHOLE spec's diff in one shot, not just one fix.

Why an all-inline fixture never shifts an action ID (and so gets a genuine
FULL byte-identity assertion, not a narrowed one): the new `edit_frontmatter`
kind is only ever emitted for a frontmatter-declared broken_up finding
(garden-audit-parser._route_broken_up: up_source=="frontmatter" ->
"edit_frontmatter"; up_source=="inline" -> remove_up_link/add_relationship,
exactly as before). An all-inline fixture never takes that branch, so the
action-kind sequence build_garden_audit_actions produces is identical to the
pre-032 sequence, id-for-id.

FOUR DECLARED exceptions on the report side, not defects. Originally one
(spec 032 T5.3); spec 033 sanctioned three more on top of it, all for this
same all-inline fixture:

  1. (032, T5.3/ADR-4) garden-audit-render.py's _render_broken_up_split adds
     a once-per-run summary line — "Broken parents: N findings — B in the
     note body, P in a note property." — suppressed ONLY when body+prop == 0,
     so it's emitted for an all-inline run too (P legitimately 0), not gated
     on any property-resident finding existing.
  2. (033, T4.2/ADR-6) _fix_summary's broken_up branch is reworded to say
     the target was "not found in the audited area" rather than implying it
     is gone — for EVERY broken_up finding, body-resident included. Spec 032
     kept inline Fix-line wording byte-identical through its own whole diff
     (only exception 1 was needed until now); T4.2 is the first change ever
     to touch it, which is why this file's fixture (all findings inline)
     newly diverges here too.
  3. (033, T4.3/ADR-7) the SAME split line from exception 1 gains a trailing
     clause noting it counts broken_up survivors only — parent_not_moc
     findings left that population, and a reader who remembers a bigger N
     needs to know why it dropped.
  4. (033, T4.3/PRD F5) a brand-new "Flagged parents:" line (+ its trailing
     blank) is added to the Summary, stating the per-situation counts. This
     baseline predates the whole per-situation-counts feature, so it never
     had it.

TestReportByteIdenticalCon7 asserts the narrower property these four imply:
every line OTHER than these four declared differences is untouched, and
proves the differences are real (not cover for a bug) by also asserting
full byte-identity holds when there are zero broken_up findings at all — the
case where every one of the four is gated off at once.
"""
from __future__ import annotations

import importlib.util
import pathlib
import subprocess
import sys
import tempfile

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parent
_SCRIPTS_DIR = _ROOT / "tomo" / "scripts"
_PARSER_PATH = _SCRIPTS_DIR / "garden-audit-parser.py"
_RENDER_PATH = _SCRIPTS_DIR / "garden-audit-render.py"

sys.path.insert(0, str(_SCRIPTS_DIR))

_PRE_032_SHA = "781aaf2"  # last commit before this branch's first code change (995e35a)


def _load(name: str, path: pathlib.Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_from_git(name: str, sha: str, repo_relative_path: str):
    """Load `sha:repo_relative_path` as a module under a distinct `name`.

    Written to a fresh tempfile under $TMPDIR — never touches the working
    tree. Returns the executed module.
    """
    content = subprocess.run(
        ["git", "show", f"{sha}:{repo_relative_path}"],
        cwd=_ROOT, capture_output=True, check=True, text=True,
    ).stdout
    with tempfile.TemporaryDirectory() as td:
        old_path = pathlib.Path(td) / f"{name}.py"
        old_path.write_text(content, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, old_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    # The tempdir (and old_path) is gone once the `with` block exits — stash
    # the source's own version line on the module object now, while we still
    # have `content`, so a later sanity check doesn't need to re-read a
    # deleted file via mod.__file__.
    mod._t62_source_version_line = content.splitlines()[1]
    return mod


def _load_render_actions_from_git(name: str, sha: str):
    """Like ``_load_from_git``, but for lib/render_actions.py specifically.

    render_actions.py resolves ``tag-handler-group.py`` at import time via
    ``Path(__file__).resolve().parent.parent`` (scripts/lib/x.py -> scripts/)
    — a bare tempfile breaks that. Mirror the real scripts/lib/ layout inside
    the tempdir instead, using the CURRENT tag-handler-group.py (its
    ``group_id`` helper is untouched by spec 032 and never exercised by
    build_garden_audit_actions; only the import needs to succeed).
    """
    content = subprocess.run(
        ["git", "show", f"{sha}:tomo/scripts/lib/render_actions.py"],
        cwd=_ROOT, capture_output=True, check=True, text=True,
    ).stdout
    thg_content = (_SCRIPTS_DIR / "tag-handler-group.py").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory() as td:
        td_path = pathlib.Path(td)
        (td_path / "lib").mkdir()
        old_path = td_path / "lib" / f"{name}.py"
        old_path.write_text(content, encoding="utf-8")
        (td_path / "tag-handler-group.py").write_text(thg_content, encoding="utf-8")
        spec = importlib.util.spec_from_file_location(name, old_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    mod._t62_source_version_line = content.splitlines()[1]
    return mod


# ---------------------------------------------------------------------------
# NEW (current HEAD) modules
# ---------------------------------------------------------------------------
new_gap = _load("garden_audit_parser_t62_new", _PARSER_PATH)
new_gar = _load("garden_audit_render_t62_new", _RENDER_PATH)
from lib.render_actions import build_garden_audit_actions as new_build_actions  # noqa: E402

# ---------------------------------------------------------------------------
# OLD (pre-032, 781aaf2) modules — DISTINCT names, loaded from git history,
# never from the working tree.
# ---------------------------------------------------------------------------
old_gap = _load_from_git(
    "garden_audit_parser_t62_old", _PRE_032_SHA, "tomo/scripts/garden-audit-parser.py"
)
old_gar = _load_from_git(
    "garden_audit_render_t62_old", _PRE_032_SHA, "tomo/scripts/garden-audit-render.py"
)
old_render_actions = _load_render_actions_from_git("render_actions_t62_old", _PRE_032_SHA)
old_build_actions = old_render_actions.build_garden_audit_actions

# Sanity: the two parser modules really are different objects loaded from
# different sources, at different versions — guards against the "loaded the
# new module twice" trap a reviewer hit earlier in this spec. old_gap's
# version line was stashed from git-show content (its tempfile is gone by
# now); new_gap's is read straight from the working-tree file it was loaded
# from, which is still on disk.
assert old_gap is not new_gap
assert old_gap.__file__ != new_gap.__file__
_new_gap_version_line = _PARSER_PATH.read_text(encoding="utf-8").splitlines()[1]
assert old_gap._t62_source_version_line == "# version: 0.11.0"
assert _new_gap_version_line != old_gap._t62_source_version_line
assert "0.11.0" not in _new_gap_version_line


# ---------------------------------------------------------------------------
# All-inline fixture — every broken_up finding is body-declared (up_source ==
# "inline", up_value is always None for inline per spec 032 ADR-3). Mirrors
# the finding set already proven correct in
# TestEndToEndApprovedReportToActions (test_garden_audit_parser.py): one
# broken_up removal, one broken_up repoint, one dead_link, one unparented,
# one advisory (duplicate_stem) that must never reach the instruction set.
# ---------------------------------------------------------------------------

def _wire_finding(fid, check, tier, fixable, path, stem, detail, decision=None):
    f = {
        "id": fid, "check": check, "tier": tier, "fixable": fixable,
        "target": {"path": path, "stem": stem}, "detail": detail,
    }
    if decision is not None:
        f["decision"] = decision
    return f


def _all_inline_findings():
    # spec 033 T4.4: F02/F03's detail carries up_broken_reason="unresolved"
    # — a real garden-audit.py finding always does once up_source/up_value
    # are populated (a modern, classified cache entry); its absence is
    # T4.4's OWN new "cause-unknown" withhold reason, which would make both
    # findings unroutable here and break every assertion below that this
    # fixture predates. This fixture represents a MODERN cache, not a
    # pre-033 one — T4.4's own tests in test_garden_audit_render.py cover
    # the pre-033 shape.
    return [
        _wire_finding(
            "F01", "dead_link", "integrity", True,
            "Notes/Source Note.md", "Source Note",
            {"dead_target": "Missing Note", "count": 2},
            decision={"selected": True, "action": "edit_note_text", "replace": ""},
        ),
        _wire_finding(
            "F02", "broken_up", "integrity", True,
            "Notes/Broken Note.md", "Broken Note",
            {
                "up_target": "Deleted MOC", "up_source": "inline", "up_value": None,
                "up_broken_reason": "unresolved",
            },
            decision={"selected": True, "action": "edit_note_text", "repoint": ""},
        ),
        _wire_finding(
            "F03", "broken_up", "integrity", True,
            "Notes/Repoint Note.md", "Repoint Note",
            {
                "up_target": "Old MOC", "up_source": "inline", "up_value": None,
                "up_broken_reason": "unresolved",
            },
            decision={
                "selected": True, "action": "add_relationship",
                "repoint": "Correct MOC",
            },
        ),
        _wire_finding(
            "F04", "unparented", "structure", True,
            "Notes/Orphan Note.md", "Orphan Note",
            {"candidate_mocs": [{"target_moc": "MOCs/Writing MOC.md", "score": 0.8}]},
            decision={"selected": True, "action": "link_to_moc", "file_under": ""},
        ),
        _wire_finding(
            "F05", "duplicate_stem", "advisory", False,
            "Notes/Dup.md", "Dup",
            {"dupes": ["Notes/Dup.md", "Archive/Dup.md"]},
        ),
    ]


def _make_wire(findings):
    return {
        "schema_version": "1", "run_id": "run-t62-001",
        "generated": "2026-09-02T12:00:00Z", "profile": "miyo",
        "findings": findings, "emit_digest": "sha256:" + "a" * 64,
    }


def _make_doc(findings):
    return {
        "run_id": "run-t62-001", "generated": "2026-09-02T12:00:00Z", "profile": "miyo",
        "findings": findings, "skipped_checks": [], "skipped_checks_reason": "",
        "reappeared_exclusions": [],
    }


# ---------------------------------------------------------------------------
# T6.2 — instruction set (actions list) byte-identity
# ---------------------------------------------------------------------------

class TestInstructionSetByteIdenticalCon7:
    def test_actions_list_byte_identical_old_vs_new(self):
        wire = _make_wire(_all_inline_findings())

        old_items = old_gap.build_from_wire(wire)["confirmed_items"]
        new_envelope = new_gap.build_from_wire(wire)
        new_items = new_envelope["confirmed_items"]

        # Internal reader envelope, not "the instruction set" itself — the new
        # envelope legitimately grows an "unroutable" key (spec 032 ADR-5).
        # Prove it is empty (every all-inline finding routed cleanly, none
        # withheld) rather than silently dropping it from the comparison.
        assert new_envelope["unroutable"] == []
        assert old_items == new_items

        old_actions = old_build_actions(old_items, [0])
        new_actions = new_build_actions(new_items, [0])

        # THE instruction set. No edit_frontmatter branch is reachable from an
        # all-inline fixture (see module docstring), so the action-kind
        # sequence — and therefore every action id — is identical to the
        # pre-032 sequence. Full list equality, not a narrowed property.
        assert new_actions == old_actions
        assert {a["action"] for a in new_actions} == {
            "resolve_dead_link", "remove_up_link", "add_relationship", "link_to_moc",
        }
        assert "edit_frontmatter" not in {a["action"] for a in new_actions}

    def test_remove_up_link_and_add_relationship_emission_untouched(self):
        # CON-7's third clause, spelled out directly rather than only implied
        # by the byte-identity assertion above.
        wire = _make_wire(_all_inline_findings())
        items = new_gap.build_from_wire(wire)["confirmed_items"]
        actions = new_build_actions(items, [0])

        removes = [a for a in actions if a["action"] == "remove_up_link"]
        assert len(removes) == 1
        assert removes[0]["path"] == "Notes/Broken Note.md"
        assert removes[0]["link"] == "Deleted MOC"

        # Two add_relationship actions are legitimately emitted from this
        # fixture: one from the broken_up repoint (F03) and one from the
        # unparented filing's up-link half (F04, file_note -> link_to_moc +
        # add_relationship). Scope to the broken_up-repoint one by path.
        rels = [a for a in actions if a["action"] == "add_relationship"]
        assert len(rels) == 2
        repoint_rel = next(
            r for r in rels if r["target_moc_path"] == "Notes/Repoint Note.md"
        )
        assert repoint_rel["line"] == "up:: [[Correct MOC]]"
        assert repoint_rel["marker"] == "up::"


# ---------------------------------------------------------------------------
# T6.2 — report byte-identity
# ---------------------------------------------------------------------------

class TestReportByteIdenticalCon7:
    def test_full_report_byte_identical_old_vs_new_except_the_declared_exceptions(self):
        # NOT a full byte-identity assertion — and that is itself a finding,
        # not an oversight. Originally ONE declared exception (spec 032 T5.3):
        # garden-audit-render.py's _render_broken_up_split is a once-per-run
        # summary line, suppressed ONLY when body+prop == 0 — deliberately
        # emitted for an ALL-INLINE run too (0 property-resident, >=1
        # body-resident), not gated on any property-resident finding
        # existing.
        #
        # spec 033 sanctioned three MORE differences for this same all-inline
        # fixture, none of them defects:
        #   (2) T4.2 (ADR-6) rewords the Fix line for EVERY broken_up finding,
        #       body-resident included — this fixture's F02 (removal) and F03
        #       (repoint) are both inline, so both differ now. Spec 032 kept
        #       inline Fix-line wording byte-identical through its own whole
        #       diff (that's why exception (1) alone sufficed until now);
        #       T4.2 is the first change to ever touch it.
        #   (3) T4.3 (ADR-7) appends a clause to the SAME split line from (1),
        #       noting it counts broken_up survivors only.
        #   (4) T4.3 (PRD F5) adds a brand-new "Flagged parents:" line (+ its
        #       trailing blank) to the Summary — this baseline predates the
        #       whole per-situation-counts feature, so it never had it.
        # Assert the narrower property: every OTHER line is untouched, AND
        # the changed/added lines are exactly these four declared, spec-
        # locked differences — nothing else rode in with them.
        doc = _make_doc(_all_inline_findings())

        old_report = (
            "\n".join(old_gar.render_frontmatter(doc)) + "\n" + old_gar.render_report(doc)
        )
        new_report = (
            "\n".join(new_gar.render_frontmatter(doc)) + "\n" + new_gar.render_report(doc)
        )

        old_lines = old_report.splitlines()
        new_lines = new_report.splitlines()

        # Exceptions (1)+(3): the split line's PRESENCE (032) now carries
        # T4.3's clause (033) too — no longer the bare verbatim string, but
        # still starting with it (substring, not equality).
        split_line = next(ln for ln in new_lines if ln.startswith("Broken parents:"))
        assert split_line not in old_lines
        assert split_line.startswith(
            "Broken parents: 2 findings — 2 in the note body, 0 in a note property."
        )
        assert "untagged" in split_line.lower()
        split_idx = new_lines.index(split_line)
        assert new_lines[split_idx + 1] == ""  # its trailing blank

        # Exception (4): the new "Flagged parents:" line + its trailing blank.
        flagged_line = next(ln for ln in new_lines if ln.startswith("Flagged parents:"))
        assert flagged_line not in old_lines
        assert flagged_line == "Flagged parents: 2 findings, not found in the audited area."
        flagged_idx = new_lines.index(flagged_line)
        assert new_lines[flagged_idx + 1] == ""

        # Remove exactly these two line-pairs (4 lines total) from the new
        # report, highest index first so earlier deletions don't shift later
        # ones, and require what remains to be byte-identical, in order, to
        # the true pre-032 report — except for exception (2), handled next.
        added = sorted([split_idx, split_idx + 1, flagged_idx, flagged_idx + 1], reverse=True)
        stripped_new_lines = list(new_lines)
        for i in added:
            del stripped_new_lines[i]

        assert len(stripped_new_lines) == len(old_lines)
        changed = [
            i for i, (o, n) in enumerate(zip(old_lines, stripped_new_lines)) if o != n
        ]
        assert changed, "the fix under test changed nothing — assertion is hollow"

        # Exception (2): F02 and F03's own Fix lines, both inline, both
        # reworded by T4.2. Nothing else may differ.
        assert len(changed) == 2, (
            f"expected exactly F02 and F03's Fix lines to differ, got: "
            f"{[stripped_new_lines[i] for i in changed]}"
        )
        for i in changed:
            assert stripped_new_lines[i].startswith("**Fix:**")
            assert old_lines[i].startswith("**Fix:**")
            assert "not found in the audited area" in stripped_new_lines[i]
            assert "not found in the audited area" not in old_lines[i]

    def test_declared_exceptions_are_gated_off_with_zero_broken_up(self):
        # Falsifies all four exceptions above at once: with NO broken_up
        # findings at all, _render_broken_up_split is suppressed
        # (body+prop == 0), _render_flagged_parent_situations is suppressed
        # (broken_up count == 0, and this fixture has no parent_not_moc
        # findings either), and _fix_summary's broken_up branch is never
        # reached at all — so the report really is fully byte-identical, no
        # exception needed. Proves the four declared differences above are
        # exactly what the two sanctioning specs (032 T5.3, 033 T4.2/T4.3)
        # produce, not a cover for something else riding along.
        doc = _make_doc([f for f in _all_inline_findings() if f["check"] != "broken_up"])

        old_report = (
            "\n".join(old_gar.render_frontmatter(doc)) + "\n" + old_gar.render_report(doc)
        )
        new_report = (
            "\n".join(new_gar.render_frontmatter(doc)) + "\n" + new_gar.render_report(doc)
        )
        assert new_report == old_report
        assert "Broken parents:" not in new_report
        assert "Flagged parents:" not in new_report

    def test_wire_payload_byte_identical_old_vs_new(self):
        # build_wire_payload is untouched by this spec (0-line diff at
        # 781aaf2..HEAD) — confirm the two artifacts stay in lockstep for an
        # all-inline doc, the same way the report does.
        doc = _make_doc(_all_inline_findings())
        old_wire = old_gar.build_wire_payload(doc)
        new_wire = new_gar.build_wire_payload(doc)
        assert new_wire == old_wire
