#!/usr/bin/env python3
# version: 0.1.0
"""test_040_moc_folders_and_exclude.py — spec 040 T1.3.

Two predicates the shared-ctx builder needs for MOC eligibility and naming:
- `lib.moc_folders`: which folders count as "the configured MOC folders"
  (`concepts.map_note`), used by the delivered-name collision rule (ADR-1).
- `lib.moc_tags.is_excluded_moc`: whether a MOC carries `MiYo/Tomo/exclude/moc`
  (ADR-5) — case-insensitive and tolerant of one leading `#`, because
  Obsidian tags are case-insensitive and inline tags keep their `#`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "tomo" / "scripts"))

from lib.moc_folders import in_moc_folders, moc_folder_prefixes  # noqa: E402
from lib.moc_tags import is_excluded_moc  # noqa: E402


def _cfg(map_note):
    return {"concepts": {"map_note": map_note}}


@pytest.mark.parametrize(
    "map_note, expected",
    [
        ({"paths": ["Atlas/200 Maps/"], "tags": ["type/others/moc"]}, ("Atlas/200 Maps/",)),
        ({"paths": ["Atlas/200 Maps", "Efforts/Maps/"]}, ("Atlas/200 Maps/", "Efforts/Maps/")),
        ({"path": "Atlas/200 Maps"}, ("Atlas/200 Maps/",)),
        ("Atlas/200 Maps/", ("Atlas/200 Maps/",)),
        ({"paths": ["  Atlas/200 Maps/  ", "", None]}, ("Atlas/200 Maps/",)),
        ({"tags": ["type/others/moc"]}, ()),
        (None, ()),
    ],
)
def test_moc_folder_prefixes_normalises_every_config_shape(map_note, expected):
    assert moc_folder_prefixes(_cfg(map_note)) == expected


def test_moc_folder_prefixes_without_concepts_is_empty():
    assert moc_folder_prefixes({}) == ()
    assert moc_folder_prefixes({"concepts": None}) == ()


def test_in_moc_folders_is_true_for_direct_and_nested_paths():
    prefixes = ("Atlas/200 Maps/",)
    assert in_moc_folders("Atlas/200 Maps/Vacation (MOC).md", prefixes)
    assert in_moc_folders("Atlas/200 Maps/Sub/Projects.md", prefixes)


def test_in_moc_folders_rejects_sibling_folders_sharing_a_prefix():
    prefixes = ("Atlas/200 Maps/",)
    assert not in_moc_folders("Atlas/200 Maps2/Projects.md", prefixes)
    assert not in_moc_folders("Efforts/Work/Projects.md", prefixes)


def test_in_moc_folders_compares_with_the_vault_path_key():
    # path_key = NFC + casefold, the one comparison key for vault paths.
    assert in_moc_folders("atlas/200 maps/Vacation (MOC).md", ("Atlas/200 Maps/",))


def test_in_moc_folders_with_no_folders_is_false():
    assert not in_moc_folders("Atlas/200 Maps/Vacation (MOC).md", ())


@pytest.mark.parametrize(
    "tags",
    [
        ["MiYo/Tomo/exclude/moc"],
        ["#MiYo/Tomo/exclude/moc"],
        ["miyo/tomo/exclude/MOC"],
        ["type/others/moc", "MiYo/Tomo/exclude/moc"],
    ],
)
def test_is_excluded_moc_accepts_the_tag_in_any_spelling(tags):
    assert is_excluded_moc(tags)


@pytest.mark.parametrize(
    "tags",
    [
        ["MiYo/Tomo/exclude/note"],
        ["MiYo/Tomo/exclude/mocs"],
        ["MiYo/Tomo/exclude"],
        ["##MiYo/Tomo/exclude/moc"],
        ["type/others/moc"],
        [],
        None,
        [None, 42],
    ],
)
def test_is_excluded_moc_rejects_near_misses_and_empty_input(tags):
    assert not is_excluded_moc(tags)
