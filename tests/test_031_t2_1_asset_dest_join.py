#!/usr/bin/env python3
# version: 0.2.0
"""test_031_t2_1_asset_dest_join.py — spec 031 T2.1 asset destination join.

_asset_dest_join(asset_folder, source_path) joins the configured asset folder
with an attachment source path's basename, preserving it verbatim — no .md
suffix, no sanitize_stem, exact case and extension.

Also pins the regression this function exists to avoid: _ensure_md_extension
is unsafe for asset paths. It is a silent no-op for an allowlisted extension
(foto.jpg -> foto.jpg, proves nothing) but appends .md to anything outside the
allowlist (scan.heic -> scan.heic.md), which is why _asset_dest_join must
never delegate to it.

And the basename guard (code-quality fix on T2.1): a source path with no
filename (empty, or ending in "/") must never silently produce a
destination that is just a bare folder — _asset_dest_join raises instead.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.render_actions import _asset_dest_join, _ensure_md_extension  # noqa: E402


def test_joins_folder_and_basename():
    dest = _asset_dest_join("Atlas/290 Assets/295 Attachments/", "100 Inbox/Images/karte.jpg")
    assert dest == "Atlas/290 Assets/295 Attachments/karte.jpg"


def test_non_allowlisted_extension_is_preserved_not_corrupted():
    """scan.heic falsifies a wrong helper — .jpg is a no-op under
    _ensure_md_extension and proves nothing on its own."""
    dest = _asset_dest_join("Atlas/290 Assets/295 Attachments/", "100 Inbox/Images/scan.heic")
    assert dest == "Atlas/290 Assets/295 Attachments/scan.heic"


def test_uppercase_extension_is_preserved_exactly():
    dest = _asset_dest_join("Atlas/290 Assets/295 Attachments/", "100 Inbox/Images/FOTO.JPG")
    assert dest == "Atlas/290 Assets/295 Attachments/FOTO.JPG"


def test_folder_without_trailing_slash_still_joins_correctly():
    dest = _asset_dest_join("Atlas/290 Assets/295 Attachments", "100 Inbox/Images/karte.jpg")
    assert dest == "Atlas/290 Assets/295 Attachments/karte.jpg"


def test_basename_survives_sanitize_stem_verbatim():
    """An Obsidian-forbidden character in the basename must NOT be rewritten —
    sanitize_stem would replace ':' with '-', which breaks the embed. Fails if
    _asset_dest_join runs the basename through sanitize_stem."""
    dest = _asset_dest_join(
        "Atlas/290 Assets/295 Attachments/", "100 Inbox/Images/dresden:karte.jpg"
    )
    assert dest == "Atlas/290 Assets/295 Attachments/dresden:karte.jpg"


def test_ensure_md_extension_is_a_silent_noop_for_allowlisted_extensions():
    """Regression pin: an allowlisted extension passes through _ensure_md_extension
    completely unchanged — the trap this function must never fall into."""
    assert _ensure_md_extension("100 Inbox/Images/foto.jpg") == "100 Inbox/Images/foto.jpg"


def test_ensure_md_extension_corrupts_non_allowlisted_extensions():
    """Regression pin: an extension NOT in the allowlist gets '.md' appended —
    the actual hazard, and why _ensure_md_extension must never touch an asset path."""
    assert _ensure_md_extension("100 Inbox/Images/scan.heic") == "100 Inbox/Images/scan.heic.md"


@pytest.mark.parametrize("source_path", ["", "100 Inbox/Images/"])
def test_raises_on_a_source_path_with_no_basename(source_path):
    """A trailing-slash or empty source path has no filename — silently
    returning a bare folder path (which build_inbox_index's malformed-entry
    guard cannot rule out) would tell Hashi to move a file to a directory."""
    with pytest.raises(ValueError):
        _asset_dest_join("Atlas/290 Assets/295 Attachments/", source_path)
