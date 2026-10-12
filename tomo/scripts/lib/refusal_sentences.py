#!/usr/bin/env python3
# version: 0.1.1
"""refusal_sentences.py — the prose the owner reads when a typed name is refused.

One home for every refusal sentence, so the wording of a refusal is edited in
one file and never spread across the renderers that report it. Pure functions
on strings: no I/O, no run state. Each takes a reason code from
`lib.typed_name_check.REFUSAL_REASONS` and raises `ValueError` on a code it does
not know — an unknown code is a bug upstream, never reported as some other
refusal.

Sentences state only what was verified about the typed name (no remedy text, no
promise about a re-run) and name the typed name itself, with control characters
shown as escapes so the sentence stays readable.
"""
from __future__ import annotations

from lib.typed_name_check import is_control_char


def _visible(text: str) -> str:
    """`text` with every control character replaced by its `\\xNN` escape."""
    return "".join(
        f"\\x{ord(c):02x}" if is_control_char(c) else c for c in text
    )


def typed_name_sentence(reason: str, name: str) -> str:
    """The sentence for one refused typed name, given its reason code."""
    shown = _visible(name)
    if reason == "separator_present":
        return (
            f"typed name refused: `{shown}` contains a path "
            f"separator, which is not allowed in a filename"
        )
    if reason == "forbidden_character":
        return (
            f"typed name refused: `{shown}` contains a character "
            f"Obsidian does not allow in a filename"
        )
    if reason == "blank":
        return "typed name refused: the typed name is blank"
    if reason == "breaks_link":
        return (
            f"typed name refused: `{shown}` has leading or trailing "
            f"whitespace or one of # ^ [ ], which would break the link"
        )
    if reason == "unsafe_sequence":
        return (
            f"typed name refused: `{shown}` contains a control character or "
            f"a template sequence, which would corrupt the instruction set"
        )
    raise ValueError(f"unknown typed-name refusal reason: {reason!r}")
