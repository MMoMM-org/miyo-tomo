#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t1_6_computed_names_pass_typed_rules.py — spec 039 T1.6, PRD F5-AC6.

The join between two modules that never import each other: every name
`_propose_asset_name` computes for a conflict must be accepted by
`check_typed_name`, so Tomo never proposes a name it would refuse if the owner
typed it back.

Scope is every source basename the vault allows and Tomo would not refuse for
link-breaking reasons: no `#`, `^`, `[`, `]`, no leading/trailing whitespace,
no FORBIDDEN_CHARS, no `{{`, `<%` or control characters. The four rows
`.hidden`, `README`, `karte (7)` and `report.tar.gz` are deliberately broader
than PRD F5-AC6's discoverable set (they lack a KNOWN_FILE_EXTENSIONS suffix
or have multiple dots); they cover the extension-less and multi-dot branches
of the "(n)" suffix logic, which do not depend on discovery.
Excluded on purpose, and why:
  - `# ^ [ ]` and edge whitespace: never discovered as attachments, and a later
    task (T2.1) makes the checker refuse them (`breaks_link`).
  - `{{`, `<%`, control characters: likewise refused by T2.1 (`unsafe_sequence`).
  - A FORBIDDEN_CHARS source (`foo*bar.png`): the computed name is refused by
    design; pinned as a known divergence by
    tests/test_038_t4_4_the_two_paths_converge.py
    (test_an_unusable_computed_name_is_refused_on_the_wire_and_filed_in_the_markdown).
The table avoids all of these so this file survives T2.1 unchanged.

FALSIFICATION: `test_the_join_detects_a_bad_proposer` runs the same join with a
stub proposer that emits `/`; it must report failures. Deleting the join's
assertion, or pointing it at a checker that accepts everything, turns that
control red.

CON-7: pure functions, fakes only.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.typed_name_check import check_typed_name  # noqa: E402


def _load_reducer():
    spec = importlib.util.spec_from_file_location(
        "suggestions_reducer_t039_t1_6", SCRIPTS_DIR / "suggestions-reducer.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules["suggestions_reducer_t039_t1_6"] = mod
    spec.loader.exec_module(mod)
    return mod


REDUCER = _load_reducer()
ASSET_FOLDER = "900 Assets/"

BASENAMES = [
    "karte.png",
    "my photo.png",
    "Übersicht Größe.pdf",
    "ärger.jpeg",
    "v1.2.final.png",
    "report.tar.gz",
    "karte (2).png",
    "karte (7)",
    "README",
    ".hidden",
    "Mixed CASE.PNG",
    "日本語.png",
]


# Must mirror the reducer's occupancy keys (`_asset_dest_join(...).casefold()`), or the pressure rows stop colliding.
def _key(name: str) -> str:
    return REDUCER._asset_dest_join(ASSET_FOLDER, name).casefold()


def _occupancies(basename: str):
    """(vault_assets, occupied_folders, proposed) triples with growing pressure."""
    first = REDUCER._propose_asset_name(ASSET_FOLDER, basename, {}, set(), set())
    yield {}, set(), set()
    yield {_key(basename): "f"}, set(), set()
    yield {_key(basename): "f"}, {_key(first)}, set()
    yield {_key(basename): "f"}, set(), {_key(first)}
    yield {_key(basename): "f", _key(first): "f"}, set(), set()


def join_failures(proposer) -> list[tuple[str, str, str | None]]:
    """(source, computed, refusal reason) for every computed name the checker refuses."""
    failures = []
    for basename in BASENAMES:
        for assets, folders, proposed in _occupancies(basename):
            computed = proposer(ASSET_FOLDER, basename, assets, folders, proposed)
            if computed is None:
                continue
            verdict = check_typed_name(computed)
            if not verdict.ok:
                failures.append((basename, computed, verdict.reason))
    return failures


def test_every_computed_name_is_accepted_by_the_typed_name_rules():
    produced = [
        REDUCER._propose_asset_name(ASSET_FOLDER, b, a, f, p)
        for b in BASENAMES
        for a, f, p in _occupancies(b)
    ]
    # Guard against a vacuous pass: names were really computed, including (n) variants.
    assert sum(1 for n in produced if n is not None) >= len(BASENAMES) * 4
    assert any(n is not None and "(3)" in n for n in produced), produced

    assert join_failures(REDUCER._propose_asset_name) == []


def test_the_join_detects_a_bad_proposer():
    """Negative control: a proposer that emits a separator must be caught."""

    def bad_proposer(asset_folder, basename, vault_assets, occupied_folders, proposed):
        return f"sub/{basename} (2)"

    failures = join_failures(bad_proposer)
    assert failures, "join passed a proposer that emits '/'"
    assert {reason for _, _, reason in failures} == {"separator_present"}


@pytest.mark.parametrize("basename", BASENAMES)
def test_each_source_yields_a_name_for_the_first_free_slot(basename):
    computed = REDUCER._propose_asset_name(ASSET_FOLDER, basename, {_key(basename): "f"}, set(), set())
    assert computed is not None
    assert check_typed_name(computed).ok
