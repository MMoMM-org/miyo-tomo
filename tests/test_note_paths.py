#!/usr/bin/env python3
# version: 0.1.0
"""test_note_paths.py — Behavioural tests for lib.note_paths (spec 044 T2.4).

Covers the shared /note path rules:
- vault_folder: relative folders accepted with one trailing '/'; absolute,
  traversing, hidden, blank-segment, backslash, template-syntax and unsafe
  values refused; the Unicode form is kept
- vault_note: the same rules on a .md path
- has_unsafe_char: Cc, Cf, Zl, Zp
- is_inside: path_key comparison on a segment boundary
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib import note_paths  # noqa: E402

VALID_FOLDERS = [("Atlas/Meetings", "Atlas/Meetings/"), ("Atlas/Meetings/", "Atlas/Meetings/"),
                 ("  Notes  ", "Notes/"), ("+", "+/"), ("A b/C d", "A b/C d/"),
                 ("v1.2/a~b", "v1.2/a~b/")]
INVALID_FOLDERS = ["", "   ", "/", "/abs/", " /abs", "../x", "Atlas/../x/", "a/ ../b",
                   "a\\b", "a//b", "a//b\\c", "a//", "a/\n/b", "a\tb", "a\x00b", "./a",
                   "..", "~", "~/Notes", "C:", "C:/Users", ".obsidian", "Atlas/.trash",
                   "{{folder}}", "Meetings/<% tp.date.now() %>",
                   "a\u200bb", "\ufeffNotes", "a\u202eb", "a\u2028b", "a\u2029b", None, 7]


@pytest.mark.parametrize("value, expected", VALID_FOLDERS)
def test_vault_folder_accepts_relative_folders(value, expected):
    assert note_paths.vault_folder(value) == expected


@pytest.mark.parametrize("value", INVALID_FOLDERS)
def test_vault_folder_refuses_unsafe_values(value):
    assert note_paths.vault_folder(value) is None


def test_vault_folder_keeps_the_unicode_form():
    nfc, nfd = (unicodedata.normalize(form, "Atlas/Größe") for form in ("NFC", "NFD"))
    assert note_paths.vault_folder(nfc) == nfc + "/"
    assert note_paths.vault_folder(nfd) == nfd + "/"


@pytest.mark.parametrize("value, expected", [("In/x.md", "In/x.md"), ("  x.md\n", "x.md")])
def test_vault_note_accepts_relative_md_paths(value, expected):
    assert note_paths.vault_note(value) == expected


@pytest.mark.parametrize("value", ["/x.md", "../x.md", "In//x.md", "In\\x.md", "In/.md",
                                   "In/x\u200b.md", "In/x.txt", "In/x.md/", "", None])
def test_vault_note_refuses_unsafe_paths(value):
    assert note_paths.vault_note(value) is None


@pytest.mark.parametrize("value", ["a\nb", "\x7f", "a\u200bb", "\ufeff", "a\u202eb",
                                   "a\u2028b", "a\u2029b", "soft\u00adhyphen"])
def test_has_unsafe_char_flags_invisible_and_breaking_characters(value):
    assert note_paths.has_unsafe_char(value) is True


@pytest.mark.parametrize("value", ["Größe", unicodedata.normalize("NFD", "Größe"), "a b", ""])
def test_has_unsafe_char_passes_visible_text(value):
    assert note_paths.has_unsafe_char(value) is False


@pytest.mark.parametrize("path, folder, inside", [
    ("100 Inbox/x.md", "100 Inbox/", True),
    ("100 Inbox/Sub/x.md", "100 Inbox/", True),
    ("100 inbox/x.md", "100 Inbox/", True),
    (unicodedata.normalize("NFD", "Eingänge/x.md"), "Eingänge/", True),
    ("100 Inbox Archive/x.md", "100 Inbox/", False),
    ("100 Inbox.md", "100 Inbox/", False),
    ("Atlas/x.md", "100 Inbox/", False),
])
def test_is_inside_compares_path_keys_on_a_segment_boundary(path, folder, inside):
    assert note_paths.is_inside(path, folder) is inside
