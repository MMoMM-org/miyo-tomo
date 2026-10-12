#!/usr/bin/env python3
"""test_039_t2_2_check_typed_folder.py — spec 039 T2.2 (F2-AC1, AC2, AC3, AC5, AC9).

`check_typed_folder(folder, *, inbox_path)` refuses an owner-typed attachment
folder with one of nine closed reasons, never rewriting it. Check order:
blank, escapes_vault, empty_segment, edge_whitespace, trailing_separator,
unsafe_sequence, forbidden_character, breaks_link, inside_inbox.
"""
from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.refusal_sentences import folder_sentence  # noqa: E402
from lib.render_actions import _check_path_shape  # noqa: E402
from lib.typed_name_check import (  # noqa: E402
    FOLDER_REFUSAL_REASONS,
    check_typed_folder,
)

INBOX = "100 Inbox"

REFUSALS = [
    ("", "blank"), ("  ", "blank"), ("\t", "blank"),
    ("../x", "escapes_vault"), ("a/../b", "escapes_vault"),
    ("..", "escapes_vault"), ("/abs", "escapes_vault"),
    ("~/x", "escapes_vault"), ("~x", "escapes_vault"), ("~", "escapes_vault"),
    ("./a", "escapes_vault"), ("a/./b", "escapes_vault"), (".", "escapes_vault"),
    ("a\\b", "escapes_vault"), ("C:/x", "escapes_vault"), ("C:", "escapes_vault"),
    ("a//b", "empty_segment"), ("a///b", "empty_segment"), ("a//", "empty_segment"),
    (" a", "edge_whitespace"), ("a /b", "edge_whitespace"),
    ("a/ b", "edge_whitespace"), ("a/b ", "edge_whitespace"),
    ("a/ /b", "edge_whitespace"), ("\ta", "edge_whitespace"),
    ("a/", "trailing_separator"), ("a/b/", "trailing_separator"),
    ("a:b", "forbidden_character"), ("a*b", "forbidden_character"),
    ("a?b", "forbidden_character"), ("a|b", "forbidden_character"),
    ("a#b", "breaks_link"), ("C# Projekte", "breaks_link"),
    ("a[b", "breaks_link"), ("a]b", "breaks_link"), ("a^b", "breaks_link"),
    ("a/{{x}}", "unsafe_sequence"), ("a<%b", "unsafe_sequence"),
    ("a\x01b", "unsafe_sequence"), ("a\nb", "unsafe_sequence"),
    ("a\x00b", "unsafe_sequence"), ("a\x7fb", "unsafe_sequence"),
    ("100 Inbox", "inside_inbox"), ("100 Inbox/sub", "inside_inbox"),
    ("100 inbox", "inside_inbox"), ("100 INBOX/Sub/deep", "inside_inbox"),
]

ACCEPTED = [
    "Atlas/290 Assets/296 Maps", "Ä/ü ß", "a", "a b/c d", "a.b/c.d", "...",
    "100 Inbox Archive", "100 Inbox2/x", "Archive/100 Inbox",
    "a~", "a.", ".hidden",
]


@pytest.mark.parametrize("folder,reason", REFUSALS)
def test_refusal_reason(folder, reason):
    v = check_typed_folder(folder, inbox_path=INBOX)
    assert (v.ok, v.reason) == (False, reason)
    assert v.name == folder


@pytest.mark.parametrize("folder", ACCEPTED)
def test_accepted_unchanged(folder):
    v = check_typed_folder(folder, inbox_path=INBOX)
    assert (v.ok, v.reason, v.name) == (True, None, folder)


def test_every_reason_is_exercised_and_set_is_closed():
    assert FOLDER_REFUSAL_REASONS == frozenset({
        "blank", "escapes_vault", "empty_segment", "edge_whitespace",
        "trailing_separator", "forbidden_character", "breaks_link",
        "unsafe_sequence", "inside_inbox",
    })
    assert {r for _, r in REFUSALS} == FOLDER_REFUSAL_REASONS


@pytest.mark.parametrize("inbox", ["100 Inbox/", "100 Inbox//", "100 INBOX"])
def test_inbox_path_normalised_for_comparison_only(inbox):
    assert check_typed_folder("100 Inbox/x", inbox_path=inbox).reason == "inside_inbox"
    assert check_typed_folder("100 Inbox Archive", inbox_path=inbox).ok


def test_inbox_comparison_ignores_unicode_normalisation():
    nfd = "Posteingang \u00dc"  # precomposed
    decomposed = "Posteingang U\u0308"
    assert check_typed_folder(decomposed, inbox_path=nfd).reason == "inside_inbox"
    assert check_typed_folder(decomposed + "/x", inbox_path=nfd).reason == "inside_inbox"


def test_blank_inbox_path_never_matches():
    assert check_typed_folder("a", inbox_path="").ok
    assert check_typed_folder("a", inbox_path="/").ok


def test_order_of_overlapping_inputs():
    # forbidden chars present, but the structural reason wins
    assert check_typed_folder("a<%b", inbox_path=INBOX).reason == "unsafe_sequence"
    assert check_typed_folder("a/../b:", inbox_path=INBOX).reason == "escapes_vault"
    # '..' beats an empty segment; empty segment beats edge whitespace
    assert check_typed_folder("../a//b", inbox_path=INBOX).reason == "escapes_vault"
    assert check_typed_folder(" a//b", inbox_path=INBOX).reason == "empty_segment"
    # edge whitespace beats trailing separator and unsafe (tab is a control char)
    assert check_typed_folder("a /", inbox_path=INBOX).reason == "edge_whitespace"
    # a refused inbox folder with a link-breaking char reports the char first
    assert check_typed_folder("100 Inbox/a#b", inbox_path=INBOX).reason == "breaks_link"


def test_property_every_path_shape_rejection_is_refused():
    tokens = ["a", "/", ".", "..", "\\", "~", ":", "C", "{{", "<%", " ", "\x01",
              "\n", "#", "*", "./"]
    corpus = [""]
    for n in range(1, 5):
        corpus += ["".join(t) for t in itertools.product(tokens, repeat=n)]
    assert len(corpus) > 69000
    rejected_by_shape = 0
    missed = []
    for s in corpus:
        if _check_path_shape(s) is not None:
            rejected_by_shape += 1
            if check_typed_folder(s, inbox_path=INBOX).ok:
                missed.append(s)
    assert rejected_by_shape > 10000  # the corpus actually exercises the shape rules
    assert missed == []


def test_never_raises_and_never_rewrites_over_corpus():
    for s in ["", " ", "a/b", "\x00", "ü/ß", "/" * 5]:
        v = check_typed_folder(s, inbox_path=INBOX)
        assert v.name == s


@pytest.mark.parametrize("reason", sorted(FOLDER_REFUSAL_REASONS))
def test_sentence_per_reason(reason):
    s = folder_sentence(reason, "a/b")
    assert s.startswith("typed folder refused:")
    if reason != "blank":
        assert "`a/b`" in s


def test_sentences_are_distinct_and_escape_control_chars():
    sentences = {folder_sentence(r, "x") for r in FOLDER_REFUSAL_REASONS}
    assert len(sentences) == len(FOLDER_REFUSAL_REASONS)
    s = folder_sentence("unsafe_sequence", "a\x01b\nc")
    assert "\x01" not in s and "\n" not in s
    assert "a\\x01b\\x0ac" in s


def test_unknown_sentence_reason_raises():
    with pytest.raises(ValueError):
        folder_sentence("taken", "a")
    with pytest.raises(ValueError):
        folder_sentence("", "a")


def test_no_production_call_site_yet():
    import subprocess
    out = subprocess.run(
        ["rg", "-l", "check_typed_folder", str(SCRIPTS_DIR)],
        capture_output=True, text=True,
    ).stdout.split()
    assert [Path(p).name for p in out] == ["typed_name_check.py"]
