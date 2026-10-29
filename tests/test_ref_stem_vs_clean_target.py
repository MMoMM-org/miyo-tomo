#!/usr/bin/env python3
# version: 0.1.0
"""test_ref_stem_vs_clean_target.py — two target cleaners that differ on purpose (#216).

`lib/up_parse._clean_target` turns the text inside `[[ ]]` into the cached
`up_target` (anchor and alias stripped, the target otherwise as written).
`moc-discovery.py` `_ref_stem` reduces any cached ref shape to a bare stem for the
`--around <MOC>` missing-member match. They agree on alias and heading; they must
keep differing on `[[ ]]`, folder path, `.md` and a list repr. Rationale:
docs/tomo/scripts/moc-discovery.md ("Why `_ref_stem` is not `up_parse._clean_target`").
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.up_parse import _clean_target  # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "moc_discovery_ref_stem", SCRIPTS_DIR / "moc-discovery.py"
)
_disc = importlib.util.module_from_spec(_spec)
sys.modules["moc_discovery_ref_stem"] = _disc
_spec.loader.exec_module(_disc)


@pytest.mark.parametrize("raw, both", [
    ("Gardening (MOC)", "Gardening (MOC)"),
    ("Gardening (MOC)|Garden", "Gardening (MOC)"),
    ("Gardening (MOC)#Roses", "Gardening (MOC)"),
    ("Gardening (MOC)#^block|Garden", "Gardening (MOC)"),
    ("  Gardening (MOC)  ", "Gardening (MOC)"),
])
def test_they_agree_on_alias_and_heading(raw, both):
    assert _clean_target(raw) == both
    assert _disc._ref_stem(raw) == both


@pytest.mark.parametrize("raw, clean_target, ref_stem", [
    # folder path: the parser keeps the user's disambiguation
    ("Atlas/200 Maps/Gardening (MOC)", "Atlas/200 Maps/Gardening (MOC)", "Gardening (MOC)"),
    # .md suffix
    ("Gardening (MOC).md", "Gardening (MOC).md", "Gardening (MOC)"),
    # [[ ]] wrapper: the parser receives inner text only; a cached up_value keeps it
    ("[[Gardening (MOC)|Garden]]", "[[Gardening (MOC)", "Gardening (MOC)"),
    # list repr of a dirty cache
    ("['Gardening (MOC)']", "['Gardening (MOC)']", "Gardening (MOC)"),
    # all at once
    ("[[Maps/Gardening (MOC).md#Roses|G]]", "[[Maps/Gardening (MOC).md", "Gardening (MOC)"),
])
def test_they_differ_on_wrapper_folder_suffix_and_list_repr(raw, clean_target, ref_stem):
    assert _clean_target(raw) == clean_target
    assert _disc._ref_stem(raw) == ref_stem
