#!/usr/bin/env python3
# version: 0.1.0
"""Tests for lib/item_key.py — item identity derivation and filename encoding.

Spec 034 (recursive inbox discovery), Phase 1 T1.1. The item key is the
vault-relative path itself (ADR-1); `to_filename` must stay collision-free
even under a case-insensitive filesystem (CON-6, ADR-5).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.item_key import derive, to_filename  # noqa: E402


def test_derive_returns_the_path_unchanged():
    """ADR-1: the key IS the path — no transformation, no loss."""
    path = "100 Inbox/Places/Dresden.md"
    assert derive(path) == path


def test_to_filename_is_stable_across_calls():
    """Same key must always produce the same filename."""
    key = "100 Inbox/Places/Dresden.md"
    assert to_filename(key) == to_filename(key)


def test_two_keys_differing_only_in_case_get_distinct_filenames():
    """CON-6: the filesystem folds case; the digest must not."""
    a = to_filename("100 Inbox/Places/Dresden.md")
    b = to_filename("100 inbox/places/dresden.md")
    assert a != b


def test_two_keys_differing_anywhere_get_distinct_filenames():
    """Two unrelated paths must not collide."""
    a = to_filename("100 Inbox/Places/Dresden.md")
    b = to_filename("100 Inbox/Reise/Dresden.md")
    assert a != b


def test_filename_contains_the_readable_stem():
    """A human reading tomo-tmp by hand must be able to identify the item."""
    name = to_filename("100 Inbox/Places/Dresden.md")
    assert "dresden" in name.lower()


def test_a_path_with_filename_unsafe_characters_still_yields_a_usable_name():
    """PRD Edge Cases: a path with characters awkward in a filename still
    yields a filesystem-safe, usable name."""
    name = to_filename('100 Inbox/Notes/Q&A: "what now"?.md')
    forbidden = set('\\/:*?"<>|\x00')
    assert not any(c in forbidden for c in name)
    assert name  # non-empty


@pytest.mark.parametrize("bad_key", ["", None])
def test_empty_or_none_key_raises_value_error(bad_key):
    """An empty or missing key must raise rather than silently produce a
    name that could collide with a legitimate one."""
    with pytest.raises(ValueError):
        to_filename(bad_key)


@pytest.mark.parametrize("bad_key", [123, Path("100 Inbox/Dresden.md")])
def test_non_string_key_raises_type_error(bad_key):
    """A truthy non-string key must raise TypeError rather than leak a bare
    AttributeError out of the digest computation."""
    with pytest.raises(TypeError):
        to_filename(bad_key)
