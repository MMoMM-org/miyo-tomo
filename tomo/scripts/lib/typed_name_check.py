#!/usr/bin/env python3
# version: 0.2.0
"""typed_name_check.py — decide whether an owner-typed attachment name is usable.

ADR-5 (spec 038): a typed name is rejected, never sanitised. `sanitize_stem`
(obsidian_filename.py) substitutes forbidden characters in place — `/` becomes
`-` — which would silently file an owner's `a/b.png` as `a-b.png`. Reusing it
on this path would be the exact defect spec 038 closes, wearing a different
hat. This module never rewrites; it only verdicts.

A separate module rather than a branch inside the move builder, because the
same rule must serve both the markdown control (T3.4) and the wire path, and a
rule inside the builder is reachable from neither independently.

This module takes no dependency on render_actions.py (or any other caller) so
it stays usable from the parser side too, and it is a pure function on a
string: one argument, no run state, no vault listing. `taken` is deliberately
not a reason here — it is a property of the run, not of the string, and the
run already decides it (render_actions.py:945); handing this module run state
to duplicate that check was rejected by the owner (2026-10-01).
"""
from __future__ import annotations

from dataclasses import dataclass

from lib.obsidian_filename import FORBIDDEN_CHARS

# Closed set of refusal reasons, so a renderer can phrase each without parsing
# a string. Exactly five members — `taken` is excluded on purpose; see the
# module docstring.
REFUSAL_REASONS = frozenset({
    "separator_present", "forbidden_character", "blank",
    "breaks_link", "unsafe_sequence",
})

# Characters a wikilink cannot carry (heading, block, nested-link syntax).
# Local on purpose: FORBIDDEN_CHARS is the sanitiser's set and `sanitize_stem`
# must keep leaving `C# Notizen` alone.
_LINK_BREAKING_CHARS = frozenset("#^[]")

# `{{` and `<%` are template syntax; control characters corrupt the wire.
_UNSAFE_SUBSTRINGS = ("{{", "<%")


def _is_control(c: str) -> bool:
    return ord(c) < 0x20 or ord(c) == 0x7F


# '/' is a member of FORBIDDEN_CHARS but is reported as `separator_present`,
# not `forbidden_character` — the separator check runs first (see
# check_typed_name) so this set excludes it to make that split explicit here
# too, rather than relying on ordering alone.
_NON_SEPARATOR_FORBIDDEN_CHARS = FORBIDDEN_CHARS - {"/"}


@dataclass(frozen=True)
class TypedNameVerdict:
    """Result of checking one owner-typed name.

    `name` is the original string, returned unchanged when `ok` is True.
    `reason` is one of REFUSAL_REASONS when `ok` is False, else None.
    """

    ok: bool
    name: str
    reason: str | None = None


def check_typed_name(name: str) -> TypedNameVerdict:
    """Return a verdict on whether `name` is usable as a typed attachment name.

    Order matters: '/' is both a path separator and a FORBIDDEN_CHARS member,
    so the separator check runs BEFORE the forbidden-character check — a typed
    `a/b.png` must report `separator_present`, not `forbidden_character`.
    Blank is checked first of all, since an empty or whitespace-only string
    has no meaningful separator or character content to classify.

    Full order: blank, separator_present, edge whitespace (breaks_link),
    template substrings `{{` / `<%` (unsafe_sequence), forbidden_character,
    control characters (unsafe_sequence), link-breaking characters
    (breaks_link). Edge whitespace precedes the unsafe checks so a tab at
    either edge (`"\ta.png"`) is `breaks_link` although a tab is also a
    control character; an interior control character (`"a\x01b.png"`) is
    `unsafe_sequence`. `<%` is tested before `forbidden_character` because `<`
    is a FORBIDDEN_CHARS member and would otherwise mask it. `\x00` is also a
    FORBIDDEN_CHARS member and stays `forbidden_character` (spec 038 pin); it
    is refused either way and never aborts the run.

    Edge whitespace is refused, never trimmed: `.strip()` only decides
    blankness and edge whitespace; the returned name is the argument as typed.
    """
    if not name.strip():
        return TypedNameVerdict(ok=False, name=name, reason="blank")

    if "/" in name:
        return TypedNameVerdict(ok=False, name=name, reason="separator_present")

    if name != name.strip():
        return TypedNameVerdict(ok=False, name=name, reason="breaks_link")

    if any(u in name for u in _UNSAFE_SUBSTRINGS):
        return TypedNameVerdict(ok=False, name=name, reason="unsafe_sequence")

    if any(c in _NON_SEPARATOR_FORBIDDEN_CHARS for c in name):
        return TypedNameVerdict(ok=False, name=name, reason="forbidden_character")

    if any(_is_control(c) for c in name):
        return TypedNameVerdict(ok=False, name=name, reason="unsafe_sequence")

    if any(c in _LINK_BREAKING_CHARS for c in name):
        return TypedNameVerdict(ok=False, name=name, reason="breaks_link")

    return TypedNameVerdict(ok=True, name=name)
