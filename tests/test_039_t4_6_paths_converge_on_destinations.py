#!/usr/bin/env python3
"""test_039_t4_6_paths_converge_on_destinations.py — spec 039 T4.6.

Backs the folder half of `_strip_provenance` in
`test_038_t4_4_the_two_paths_converge.py` with a destination-level assertion.
That helper reads a `proposed_dir` that is NOT owner-supplied as `None`,
because the markdown spells the untouched default as the rendered folder and
the wire spells it `null`. The equivalence is only true if Pass 2 (K1,
`lib/attachment_plan.py`) lands both spellings on the same `move_asset`
destination — this file is where that is asserted, per folder case:

  - untouched default folder;
  - a typed folder (`Atlas/Other Folder`);
  - the default folder with a trailing `/` — refused `trailing_separator` on
    both paths: no `move_asset` on either, the same `typed_folder_refused`
    record on each;
  - a typed folder equal to `concepts.asset` — the default on both. On the
    markdown it is indistinguishable from the untouched line (it IS the
    rendered text), on the wire it is an owner-supplied string; K1's equality
    rule is what makes them one folder.

Each case drives the real Pass 1 renderers, the real parser `main` down both
the markdown path and the edited-wire path (`_run_both` from the 038 file,
with every anti-tautology guard it carries), and the real Pass 2 move builder
over K1's plan.

The typed-equals-default case cannot use 038's whole-output guard unchanged:
the parser records differ there (markdown: not owner-supplied; wire: the
same text, owner-supplied), and `_strip_provenance` folds only the
not-owner-supplied spelling. That case swaps in a guard that also applies
K1's equality rule; every other field must still agree.

Mechanism falsified: "the two paths reach different folders". Mutations
applied in an isolated `git archive` copy (2026-10-12), each run against this
file:

  - K1's `_typed_folder` reads `name_is_owner_supplied` in place of
    `dir_is_owner_supplied`: the typed-folder and trailing-`/` cases fail
    (the markdown, whose name is untouched, files under the default folder).
    With the per-case `markdown.destinations` pins deleted, the typed-folder
    case still fails on the cross-path `wire.destinations ==
    markdown.destinations`.
  - The parser's markdown join compares `folder_text.rstrip("/")` to the
    rendered folder: the trailing-`/` case fails in `_run_both`'s
    whole-output comparison (markdown: default; wire: owner-supplied).
  - A `check_typed_folder(` line appended to `lib/embed_rewrite.py`: both
    K1-only-decision-site tests fail.

CON-7: fixtures and fakes only.
"""
from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import test_038_t4_4_the_two_paths_converge as C038  # noqa: E402
from pass2_harness import strip_provenance_and_default_folder  # noqa: E402

ASSET_FOLDER = C038.ASSET_FOLDER
DEFAULT_DIR = ASSET_FOLDER.rstrip("/")
OTHER_FOLDER = "Atlas/Other Folder"
FOLDER_LINE = "  - Folder: "


def _run_with_folder(tmp_path: Path, folder: str | None, agree=None):
    """Both paths for one folder decision; `None` leaves the folder untouched
    on both surfaces. The name is Pass 1's computed one throughout."""
    doc = C038._doc(C038.SOURCE, C038.COMPUTED)
    markdown_text = C038._full_md(doc)
    wire_edit = None
    if folder is not None:
        markdown_text = C038._retype(markdown_text, FOLDER_LINE, f"{FOLDER_LINE}`{folder}`")

        def wire_edit(wire: dict) -> None:
            wire["attachment_conflicts"][0]["proposed_dir"] = folder

    return C038._run_both(tmp_path, doc, markdown_text, wire_edit=wire_edit, agree=agree)


def _assert_same_outcome(markdown, wire) -> None:
    assert wire.destinations == markdown.destinations, (markdown.actions, wire.actions)
    assert wire.actions == markdown.actions, (markdown.actions, wire.actions)
    assert wire.skipped == markdown.skipped, (markdown.skipped, wire.skipped)


def test_untouched_default_folder_lands_on_one_destination(tmp_path):
    markdown, wire = _run_with_folder(tmp_path, None)
    assert (markdown.remedy["proposed_dir"], markdown.remedy["dir_is_owner_supplied"]) == (
        DEFAULT_DIR, False)
    assert (wire.remedy["proposed_dir"], wire.remedy["dir_is_owner_supplied"]) == (None, False)
    assert markdown.destinations == [f"{ASSET_FOLDER}{C038.COMPUTED}"], markdown.actions
    _assert_same_outcome(markdown, wire)
    assert markdown.skipped == []


def test_typed_folder_lands_on_one_destination(tmp_path):
    markdown, wire = _run_with_folder(tmp_path, OTHER_FOLDER)
    for side in (markdown, wire):
        assert (side.remedy["proposed_dir"], side.remedy["dir_is_owner_supplied"]) == (
            OTHER_FOLDER, True)
    assert markdown.destinations == [f"{OTHER_FOLDER}/{C038.COMPUTED}"], markdown.actions
    _assert_same_outcome(markdown, wire)
    assert markdown.skipped == []


def test_default_folder_with_trailing_separator_is_refused_on_both(tmp_path):
    markdown, wire = _run_with_folder(tmp_path, f"{DEFAULT_DIR}/")
    for side in (markdown, wire):
        assert (side.remedy["proposed_dir"], side.remedy["dir_is_owner_supplied"]) == (
            f"{DEFAULT_DIR}/", True)
    assert markdown.destinations == [], markdown.actions
    assert [(s["kind"], s["refusal_reason"], s["destination"]) for s in markdown.skipped] == [
        ("typed_folder_refused", "trailing_separator", None)], markdown.skipped
    _assert_same_outcome(markdown, wire)


def test_typed_folder_equal_to_the_asset_folder_is_the_default_on_both(tmp_path):
    # The parser records differ here — markdown (default, not owner-supplied)
    # vs wire (same text, owner-supplied) — and 038's whole-output guard only
    # folds the not-owner-supplied spelling. Every other field must still
    # agree; the folder converges in K1, which the destination below proves.
    def _agree(md_parsed, wire_parsed):
        assert (strip_provenance_and_default_folder(md_parsed)
                == strip_provenance_and_default_folder(wire_parsed)), (md_parsed, wire_parsed)

    markdown, wire = _run_with_folder(tmp_path, DEFAULT_DIR, agree=_agree)
    # The markdown cannot tell this edit from no edit; the wire calls it typed.
    assert (markdown.remedy["proposed_dir"], markdown.remedy["dir_is_owner_supplied"]) == (
        DEFAULT_DIR, False)
    assert (wire.remedy["proposed_dir"], wire.remedy["dir_is_owner_supplied"]) == (
        DEFAULT_DIR, True)
    assert markdown.destinations == [f"{ASSET_FOLDER}{C038.COMPUTED}"], markdown.actions
    _assert_same_outcome(markdown, wire)
    assert markdown.skipped == []


# ── K1 is the only decision site ─────────────────────────────────────────────

SCRIPTS_DIR = TESTS_DIR.parent / "tomo" / "scripts"
DECISION_TOKENS = ("check_typed_name", "check_typed_folder", "remedy ==", "claimed")
GUARD_CALL = re.compile(r"\bcheck_typed_(?:name|folder)\(")


def test_only_the_attachment_plan_calls_the_typed_guards():
    """Every call of either typed guard under tomo/scripts is in K1; the only
    other match is the guards' own definitions."""
    callers = sorted(
        str(path.relative_to(SCRIPTS_DIR))
        for path in SCRIPTS_DIR.rglob("*.py")
        if GUARD_CALL.search(path.read_text(encoding="utf-8"))
    )
    assert callers == ["lib/attachment_plan.py", "lib/typed_name_check.py"], callers


@pytest.mark.parametrize("token", DECISION_TOKENS)
def test_the_two_projections_hold_no_decision_token(token):
    from lib import embed_rewrite, render_actions

    assert token not in inspect.getsource(render_actions._build_move_asset_actions), token
    assert token not in inspect.getsource(embed_rewrite), token
