#!/usr/bin/env python3
# version: 0.2.0
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


_FOLDER_TAILS = {
    "escapes_vault": "leaves the vault or is not a plain vault-relative path",
    "empty_segment": "contains an empty path segment (`//`)",
    "edge_whitespace": "has whitespace at the start or end of a path segment",
    "trailing_separator": "ends in a path separator",
    "forbidden_character": "contains a character Obsidian does not allow in a name",
    "breaks_link": "contains one of # ^ [ ], which would break the link",
    "unsafe_sequence": (
        "contains a control character or a template sequence, which would "
        "corrupt the instruction set"
    ),
    "inside_inbox": (
        "is the inbox folder or inside it, so the next run would read it as "
        "inbox material"
    ),
}


def folder_sentence(reason: str, folder: str) -> str:
    """The sentence for one refused typed folder, given its reason code."""
    if reason == "blank":
        return "typed folder refused: the typed folder is blank"
    tail = _FOLDER_TAILS.get(reason)
    if tail is None:
        raise ValueError(f"unknown typed-folder refusal reason: {reason!r}")
    return f"typed folder refused: `{_visible(folder)}` {tail}"
