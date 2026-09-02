#!/usr/bin/env python3
# version: 0.1.0
"""test_032_t3_2_edit_frontmatter_fields.py — pure transform for broken-up
frontmatter fixes (T3.2).

``_construct_edit_frontmatter_fields(up_value, up_target, choice, new_target=None)``
builds the ``{operation, value, expected}`` triad an ``edit_frontmatter`` action
needs, from the observed frontmatter value, the broken stem, and the user's
remove/repoint choice. Pure — no action dict, no dispatch wiring (T3.3 owns
that; see the T3.2 SEAM block in phase-3.md).

Fixture reproduces the SDD's traced walkthrough verbatim (solution.md
"Constructing value and expected"): up_value == ["[[Alte MOC]]",
"[[Reisen (MOC)]]"], up_target == "Alte MOC".

Spec: docs/XDD/specs/032-up-source-routing/plan/phase-3.md T3.2
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.X` works

from lib.render_actions import (  # noqa: E402
    UnsupportedShapeError,
    _construct_edit_frontmatter_fields,
)

_UP_VALUE = ["[[Alte MOC]]", "[[Reisen (MOC)]]"]
_UP_TARGET = "Alte MOC"


def _assert_no_expected_absent(fields: dict) -> None:
    """expected_absent is never reachable from this transform (SDD:
    "expected_absent is not reachable here") — every action targets a
    property that exists."""
    assert "expected_absent" not in fields, fields


# 1. repoint → operation "set", sibling survives in position, expected verbatim.
def test_repoint_sibling_survives_in_position():
    fields = _construct_edit_frontmatter_fields(
        _UP_VALUE, _UP_TARGET, "repoint", new_target="Neue MOC",
    )
    assert fields["operation"] == "set"
    assert fields["value"] == ["[[Neue MOC]]", "[[Reisen (MOC)]]"]
    assert fields["expected"] == ["[[Alte MOC]]", "[[Reisen (MOC)]]"]
    _assert_no_expected_absent(fields)


# 2. remove with a sibling → operation "set", broken entry dropped, sibling kept.
def test_remove_with_sibling_keeps_property():
    fields = _construct_edit_frontmatter_fields(_UP_VALUE, _UP_TARGET, "remove")
    assert fields["operation"] == "set"
    assert fields["value"] == ["[[Reisen (MOC)]]"]
    assert fields["expected"] == ["[[Alte MOC]]", "[[Reisen (MOC)]]"]
    _assert_no_expected_absent(fields)


# 3. remove as the sole (list) entry → operation "remove", no `value` — the
# case that would delete a legitimate sibling if `remove` were reached for
# unconditionally on user choice "remove".
def test_remove_sole_list_entry_removes_property():
    fields = _construct_edit_frontmatter_fields(["[[Alte MOC]]"], _UP_TARGET, "remove")
    assert fields["operation"] == "remove"
    assert "value" not in fields
    assert fields["expected"] == ["[[Alte MOC]]"]
    _assert_no_expected_absent(fields)


# 4. scalar property, repoint → value is a scalar, not a one-item list.
def test_scalar_repoint_stays_scalar():
    fields = _construct_edit_frontmatter_fields(
        "[[Alte MOC]]", _UP_TARGET, "repoint", new_target="Neue MOC",
    )
    assert fields["operation"] == "set"
    assert fields["value"] == "[[Neue MOC]]"
    assert isinstance(fields["value"], str)
    assert fields["expected"] == "[[Alte MOC]]"
    _assert_no_expected_absent(fields)


# 5. scalar property, remove → operation "remove".
def test_scalar_remove_removes_property():
    fields = _construct_edit_frontmatter_fields("[[Alte MOC]]", _UP_TARGET, "remove")
    assert fields["operation"] == "remove"
    assert "value" not in fields
    assert fields["expected"] == "[[Alte MOC]]"
    _assert_no_expected_absent(fields)


# 6. the broken entry appears twice → both transformed; expected still the
# observed list verbatim (order included).
def test_duplicate_broken_entry_both_transformed():
    up_value = ["[[Alte MOC]]", "[[Reisen (MOC)]]", "[[Alte MOC]]"]
    fields = _construct_edit_frontmatter_fields(
        up_value, _UP_TARGET, "repoint", new_target="Neue MOC",
    )
    assert fields["value"] == ["[[Neue MOC]]", "[[Reisen (MOC)]]", "[[Neue MOC]]"]
    assert fields["expected"] == up_value
    _assert_no_expected_absent(fields)


# 7. expected is byte-for-byte the observed value in every case, order included.
@pytest.mark.parametrize(
    "up_value,choice,kwargs",
    [
        (_UP_VALUE, "repoint", {"new_target": "Neue MOC"}),
        (_UP_VALUE, "remove", {}),
        (["[[Alte MOC]]"], "remove", {}),
        ("[[Alte MOC]]", "repoint", {"new_target": "Neue MOC"}),
        ("[[Alte MOC]]", "remove", {}),
        (["[[Alte MOC]]", "[[Reisen (MOC)]]", "[[Alte MOC]]"], "repoint", {"new_target": "Neue MOC"}),
    ],
)
def test_expected_is_byte_for_byte_observed_value_every_case(up_value, choice, kwargs):
    fields = _construct_edit_frontmatter_fields(up_value, _UP_TARGET, choice, **kwargs)
    assert fields["expected"] == up_value


# 8. a map-shaped up_value → unroutable, not transformed. Guessing a transform
# for a shape never observed is how the current defect was born (SDD).
def test_map_shaped_value_is_unroutable():
    with pytest.raises(UnsupportedShapeError):
        _construct_edit_frontmatter_fields({"target": "Alte MOC"}, _UP_TARGET, "remove")


# 9. expected_absent is never emitted — assert on every produced result, not
# just a hand-picked one.
def test_expected_absent_never_emitted_across_all_cases():
    cases = [
        (_UP_VALUE, "repoint", {"new_target": "Neue MOC"}),
        (_UP_VALUE, "remove", {}),
        (["[[Alte MOC]]"], "remove", {}),
        ("[[Alte MOC]]", "repoint", {"new_target": "Neue MOC"}),
        ("[[Alte MOC]]", "remove", {}),
    ]
    for up_value, choice, kwargs in cases:
        fields = _construct_edit_frontmatter_fields(up_value, _UP_TARGET, choice, **kwargs)
        _assert_no_expected_absent(fields)
