#!/usr/bin/env python3
# version: 0.1.0
"""test_034_feature_coverage_map.py — spec 034's PRD features, mapped to tests.

WHAT THIS GUARDS: that every feature in
`docs/XDD/specs/034-recursive-inbox-discovery/requirements.md` has a named test
behind it, and that the named test still runs and still passes. The rows span
seven other test files and every phase of the spec, which is why the map lives
in a file of its own rather than inside any one phase gate.

Encoded as data, not as a markdown table in a docstring: a table rots silently
the moment a referenced test is renamed or deleted, and nothing notices.

THE RESIDUAL LIMIT, stated rather than discovered: the walker proves each
referenced test exists and currently passes. It does NOT prove that test still
asserts the claimed feature. Someone gutting a body to `assert True` under an
unchanged name defeats it, and nothing short of re-deriving the proof would
catch that — disproportionate for a table whose job is to point at evidence
rather than re-prove it. Semantic drift stays a review responsibility at the
moment that test is edited.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


# (feature_id, description, test_module, test_name). A row whose honest
# answer is "not covered by a test" carries None plus a one-line reason in
# the fourth field — that is a fact, not a claim, and needs no proof. Every
# other row is walked below and its test RUN, not merely collected.
FEATURE_COVERAGE: list[tuple[int, str, str | None, str | None]] = [
    (1, "Notes in inbox subfolders are discovered and triaged",
     "tests/test_034_t6_2_pipeline_integration.py",
     "TestBoundary1Discovery::"
     "test_a_root_level_note_and_a_two_level_note_are_both_discovered"),
    (2, "Two notes sharing a filename are handled independently",
     "tests/test_034_t2_8_end_to_end_key_trace.py",
     "TestHop4SuggestionsDoc::test_namesakes_keep_their_own_titles"),
    (3, "Marking a source note as captured targets the right note",
     "tests/test_034_t2_5_captured_mark_targets_right_note.py",
     "test_collision_marks_the_approved_note_and_leaves_the_namesake_untouched"),
    (4, "Force Atomic works for a note in a subfolder",
     "tests/test_034_t4_1_dispatcher_real_path.py",
     "TestSubfolderNoteCarriesRealPath::test_extract_fan_items_resolves_subfolder_note"),
    (5, "Audio files match their transcript by note, not by name alone",
     "tests/test_034_t6_2_pipeline_integration.py",
     "TestBoundary1Discovery::"
     "test_the_audio_is_not_paired_by_a_namesake_in_another_folder"),
    (6, "Every run records how much it cost",
     "tests/test_034_t6_1_cost_history.py",
     "TestHistoryFile::test_several_runs_accumulate_and_none_is_overwritten"),
    (7, "Two notes cannot silently claim the same destination",
     "tests/test_034_t5_2_destination_clash_proposal.py",
     "test_second_claimant_on_one_destination_gets_a_distinct_name"),
    (8, "A note whose attachment cannot be filed stays with it",
     "tests/test_034_t6_2_pipeline_integration.py",
     "TestBoundary7InstructionSet::"
     "test_the_second_namesake_s_own_move_is_suppressed_with_it"),
    # Feature 9 is a call-count claim, not a fixture-boundary assertion: the
    # only honest evidence is a client that records the calls it received, and
    # T3.4 already owns that fake. Pointed there rather than restated weakly here.
    (9, "Discovery does not cost an extra vault listing",
     "tests/test_034_t3_4_phase3_gate.py",
     "TestObservedCallCount::test_exactly_one_inbox_listing_per_run"),
    # Feature 10 is agreement between two predicates on inputs Kado never
    # sends. No end-to-end fixture can produce such an input, so it is pointed
    # at the table-driven agreement test T3.1 shipped for exactly this.
    (10, "The two file-type checks agree",
     "tests/test_034_t3_1_one_file_filter.py",
     "test_discover_files_and_build_inbox_index_agree"),
]


def _resolve_rows() -> list[tuple[int, str, str]]:
    """The rows that claim a test, as pytest node ids."""
    rows = []
    for feature_id, description, module, name in FEATURE_COVERAGE:
        if module is None:
            continue
        rows.append((feature_id, description,
                     f"{module}::{name}" if name else module))
    return rows


def test_every_prd_feature_has_a_row():
    ids = [row[0] for row in FEATURE_COVERAGE]
    assert ids == list(range(1, 11)), f"the map skips or repeats a feature: {ids}"


def test_a_row_without_a_test_states_why():
    """Today every feature is covered, so this guard has nothing to iterate —
    which is stated rather than left to look like a passing check. It fires the
    moment a future row is dropped to None without a reason beside it."""
    uncovered = [row for row in FEATURE_COVERAGE if row[2] is None]
    assert uncovered == [], (
        "a feature lost its test — keep the row, set the module to None, and "
        f"give the reason in the fourth field: {uncovered}"
    )
    for feature_id, _description, _module, name in uncovered:
        assert name and name.startswith("NOT COVERED"), (
            f"feature {feature_id} claims nothing and explains nothing"
        )


def test_every_referenced_module_exists():
    """A typo'd module name reaches the walker as a pytest usage error buried
    in captured stdout. Name it here instead."""
    for feature_id, _description, module, _name in FEATURE_COVERAGE:
        if module is None:
            continue
        assert (REPO_ROOT / module).is_file(), (
            f"feature {feature_id} points at {module}, which does not exist"
        )


@pytest.mark.parametrize(
    ("feature_id", "description", "node_id"),
    _resolve_rows(),
    ids=[f"F{row[0]}" for row in _resolve_rows()],
)
def test_the_referenced_test_currently_passes(feature_id, description, node_id):
    """Run the referenced node, do not merely collect it.

    Collectibility alone would accept a row pointing at a test since marked
    `xfail` or `skip`, which collects cleanly and proves nothing. What this
    does NOT prove is stated in the module docstring.

    COST: one pytest subprocess per row, ~0.75s each — 7.6s for the ten rows
    here, and linear in the table's length. The isolation is what makes the
    result mean anything (an in-process call would inherit this session's
    fixtures and plugins), so the cost is accepted rather than optimised; it
    is stated here so whoever adds the eleventh row is not surprised by it.
    """
    result = subprocess.run(
        [sys.executable, "-m", "pytest", node_id, "-q", "-p", "no:cacheprovider",
         "--no-header", "-x"],
        capture_output=True, text=True, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, (
        f"Feature {feature_id} ({description}) points at {node_id}, "
        f"which does not currently pass:\n{result.stdout[-3000:]}"
    )
    assert " passed" in result.stdout, (
        f"Feature {feature_id} points at {node_id}, which ran nothing:\n"
        f"{result.stdout[-2000:]}"
    )
