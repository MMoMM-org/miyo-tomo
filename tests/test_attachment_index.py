#!/usr/bin/env python3
# version: 0.1.0
"""test_attachment_index.py — Tests for lib.attachment_index.extract_attachment_embeds() —
T1.1 of spec 031 (Inbox attachment filing), Phase 1.

Covers PRD Feature 1 (detect embedded attachments):
  - AC-F1.1: `![[karte.jpg]]` embed is recorded
  - AC-F1.2: note-to-note embed `![[Some Note]]` is NOT recorded
  - AC-F1.3: plain link `[[karte.jpg]]` (no bang) is NOT recorded
  - AC-F1.4: the same embed twice is recorded once, in document order
  - AC-F1.5: no embeds → empty list

Plus the two-step classifier boundary (SDD "Example: Embed extraction"): the
`_KNOWN_FILE_EXTENSIONS` frozenset in render_actions.py contains `md`, so a naive
membership check would wrongly treat `![[Note.md]]` as an attachment. And PRD
Feature 2 criterion 2: a path-qualified embed target keeps its path — unlike
topic-extract.py's `_strip_link_target`, which discards it.
"""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from lib.attachment_index import extract_attachment_embeds  # noqa: E402


def test_embed_with_extension_is_recorded():
    """AC-F1.1: `![[karte.jpg]]` is recorded as an attachment."""
    assert extract_attachment_embeds("![[karte.jpg]]") == ["karte.jpg"]


def test_plain_link_is_not_recorded():
    """AC-F1.3: a plain `[[...]]` link (no bang) is not an attachment."""
    assert extract_attachment_embeds("[[karte.jpg]]") == []


def test_note_embed_without_extension_is_not_recorded():
    """AC-F1.2: `![[Some Note]]` names a note, not a file — not an attachment."""
    assert extract_attachment_embeds("![[Some Note]]") == []


def test_md_embed_is_not_recorded_despite_being_in_known_extensions():
    """The two-step classifier: `md` IS in _KNOWN_FILE_EXTENSIONS, but a note
    embed must still be excluded — a naive membership check would wrongly emit
    a move_asset for a note (Hashi rejects this, CON-3)."""
    assert extract_attachment_embeds("![[Note.md]]") == []


def test_canvas_embed_is_not_recorded():
    assert extract_attachment_embeds("![[Board.canvas]]") == []


def test_base_embed_is_not_recorded():
    assert extract_attachment_embeds("![[Data.base]]") == []


def test_embed_with_alias_is_recorded_without_alias():
    assert extract_attachment_embeds("![[karte.jpg|Karte]]") == ["karte.jpg"]


def test_embed_with_anchor_is_recorded_without_anchor():
    assert extract_attachment_embeds("![[karte.jpg#section]]") == ["karte.jpg"]


def test_path_qualified_embed_keeps_its_path():
    """PRD Feature 2, criterion 2: a path-qualified embed is already an answer
    and must not be discarded — unlike topic-extract.py's _strip_link_target,
    which ends with split("/")[-1]."""
    assert extract_attachment_embeds("![[Images/karte.jpg]]") == ["Images/karte.jpg"]


def test_duplicate_embed_recorded_once_in_document_order():
    """AC-F1.4: the same embed twice is recorded once."""
    body = "See ![[karte.jpg]] here and again ![[karte.jpg]] later, plus ![[other.png]]."
    assert extract_attachment_embeds(body) == ["karte.jpg", "other.png"]


def test_mixed_case_extension_is_recorded():
    """The `.lower()` in _is_attachment_target's extension check is the only
    thing making a mixed-case extension classify as an attachment — nothing
    else tests it, so a refactor dropping it would break case-insensitive
    matching silently. Original casing is preserved in the returned value."""
    assert extract_attachment_embeds("![[FOTO.JPG]]") == ["FOTO.JPG"]


def test_empty_body_returns_empty_list():
    """AC-F1.5: no embeds → empty attachment list."""
    assert extract_attachment_embeds("") == []


def test_body_with_no_embeds_returns_empty_list():
    """AC-F1.5: prose with no wikilinks at all → empty attachment list."""
    assert extract_attachment_embeds("Just plain prose, no links here.") == []
