# review_new_note.py — the text of a new periodic note a /review delivery builds in the inbox.
# version: 0.1.1
"""Compose a new note's text (spec 045 ADR-8; spec 046 T5.2, F4-AC5).

``Template`` holds the configured template's text and its Tomo variant's (None when absent or
unreadable); ``template_choice`` picks the text a new note is built from — the variant when one is
configured and readable, else the raw template (``variant_missing`` when a variant was configured),
else None for a plain note — with the Templater hint. ``note_name`` is the note's title,
``plain_note`` the note without a template (the title as H1, then the section), ``spliced`` the
template text with every ``(line index, lines)`` block inserted and its final newline kept as the
template had it, ``stamped`` the note with the rendered-note / pending-move block
(``FrontmatterMergeError`` when the template's frontmatter cannot take it).

Plain values in, text out: no ``ReviewPlan``, no Kado, no clock, no file I/O. Imported by
``review_actions`` and the review scripts; imports ``review_section_set`` and
``review_hashi_text``, never ``review_actions``.

Design notes: docs/tomo/scripts/lib/review_new_note.md
"""
from __future__ import annotations

import posixpath
from dataclasses import dataclass
from typing import List, Optional, Sequence, Tuple

from lib import review_config as rc
from lib import review_hashi_text as rht
from lib import review_section_set as rss
from lib.doc_frontmatter import build_tomo_block, merge_tomo_block_into_markdown
from lib.review_vault import TEMPLATER_MARK

NOTE_DOC_TYPE, NOTE_STATE = "rendered-note", "pending-move"


@dataclass(frozen=True)
class Template:
    raw: Optional[str] = None                  # the configured template's text, None when absent or unreadable
    variant: Optional[str] = None              # the Tomo variant's text, None when absent or unreadable


def template_choice(setup: rc.ReviewSetup, template: Template) -> Tuple[Optional[str], bool, bool]:
    """``(text, templater_hint, variant_missing)``: the variant text when one is configured and readable,
    else the raw template (``variant_missing`` when a variant was configured), else None for a plain note."""
    if setup.template is None or template.raw is None:
        return None, False, False
    if setup.template_variant is not None and template.variant is not None:
        return template.variant, TEMPLATER_MARK in template.variant, False
    return template.raw, TEMPLATER_MARK in template.raw, setup.template_variant is not None


def note_name(target_path: str) -> str:
    """The note's title: the target's file name without ``.md``."""
    name = posixpath.basename(target_path)
    return name[:-3] if name.endswith(".md") else name


def plain_note(name: str, section_md: str) -> str:
    """The note without a template: the title as H1, a blank line, the rendered section."""
    return f"# {name}\n\n{section_md}"


def spliced(text: str, inserts: Sequence[Tuple[int, List[str]]]) -> str:
    """``text`` with every ``(line index, lines)`` inserted (``review_section_set.splice_blocks``); the
    final newline only when ``text`` had one."""
    lines, trailing = rht.split_lines(text)
    rss.splice_blocks(lines, inserts)
    return "\n".join(lines) + ("\n" if trailing else "")


def stamped(note: str, run_id: str, generated: str) -> str:
    """``note`` with the rendered-note / pending-move block, ``updated_at = generated``."""
    block = build_tomo_block(NOTE_DOC_TYPE, NOTE_STATE, run_id)
    block["updated_at"] = generated
    return merge_tomo_block_into_markdown(note, block)
