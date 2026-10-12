#!/usr/bin/env python3
# version: 0.3.0
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

import unicodedata
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

# Closed set of folder refusal reasons (spec 039 K4). Own set, not an
# extension of REFUSAL_REASONS: a folder has structure (segments, escape,
# inbox) that a name does not.
FOLDER_REFUSAL_REASONS = frozenset({
    "blank", "escapes_vault", "empty_segment", "edge_whitespace",
    "trailing_separator", "forbidden_character", "breaks_link",
    "unsafe_sequence", "inside_inbox",
})

# `{{` and `<%` are template syntax; control characters corrupt the wire.
_UNSAFE_SUBSTRINGS = ("{{", "<%")


def is_control_char(c: str) -> bool:
    """True for every control character [\\x00-\\x1f\\x7f] — the one predicate."""
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
    template substrings `{{` / `<%` and control characters [\\x00-\\x1f\\x7f]
    (unsafe_sequence), forbidden_character, link-breaking characters
    (breaks_link). Edge whitespace precedes the unsafe checks so a tab at
    either edge (`"\\ta.png"`) is `breaks_link` although a tab is also a
    control character. The unsafe checks precede `forbidden_character`
    because `<` is a FORBIDDEN_CHARS member and would otherwise mask `<%`, and
    `\\x00` is one too and would otherwise mask the control-character rule
    (spec 039 F5-AC7: every control character shares one reason).

    Edge whitespace is refused, never trimmed: `.strip()` only decides
    blankness and edge whitespace; the returned name is the argument as typed.
    """
    if not name.strip():
        return TypedNameVerdict(ok=False, name=name, reason="blank")

    if "/" in name:
        return TypedNameVerdict(ok=False, name=name, reason="separator_present")

    if name != name.strip():
        return TypedNameVerdict(ok=False, name=name, reason="breaks_link")

    if any(u in name for u in _UNSAFE_SUBSTRINGS) or any(
        is_control_char(c) for c in name
    ):
        return TypedNameVerdict(ok=False, name=name, reason="unsafe_sequence")

    if any(c in _NON_SEPARATOR_FORBIDDEN_CHARS for c in name):
        return TypedNameVerdict(ok=False, name=name, reason="forbidden_character")

    if any(c in _LINK_BREAKING_CHARS for c in name):
        return TypedNameVerdict(ok=False, name=name, reason="breaks_link")

    return TypedNameVerdict(ok=True, name=name)


def _is_drive_letter_prefix(folder: str) -> bool:
    """`C:` or `C:/...` — a drive root, not a name that merely has a colon."""
    return (
        len(folder) >= 2
        and folder[0].isalpha()
        and folder[1] == ":"
        and (len(folder) == 2 or folder[2] == "/")
    )


def _escapes_vault(folder: str) -> bool:
    return (
        folder.startswith(("/", "~", "./"))
        or "\\" in folder
        or _is_drive_letter_prefix(folder)
        or any(seg in ("..", ".") for seg in folder.split("/"))
    )


def _comparable(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


def _is_inside_inbox(folder: str, inbox_path: str) -> bool:
    inbox = _comparable(inbox_path).rstrip("/")
    if not inbox:
        return False
    target = _comparable(folder)
    return target == inbox or target.startswith(inbox + "/")


def check_typed_folder(folder: str, *, inbox_path: str) -> TypedNameVerdict:
    """Return a verdict on whether `folder` is usable as a typed attachment folder.

    Refuse, never repair: `.strip()` only decides blankness and edge
    whitespace; the returned `name` is the argument as typed.

    Full order: blank, escapes_vault (leading `/` `~` `./`, backslash, drive
    letter `C:` / `C:/...`, any `..` or `.` segment), empty_segment (`//`),
    edge_whitespace (any segment with whitespace at either end, including a
    whitespace-only segment such as `a/ /b`), trailing_separator, unsafe_sequence
    (`{{`, `<%`, control characters), forbidden_character, breaks_link
    (`# ^ [ ]`), inside_inbox.

    Structural reasons precede character reasons because `\\` and `:` are
    FORBIDDEN_CHARS members and would otherwise mask escapes_vault; `<%` is
    ordered before forbidden_character for the same reason as in
    check_typed_name. A `:` outside a drive prefix (`a:b`) is
    forbidden_character. inside_inbox runs last: it is the only reason that
    depends on `inbox_path`, and a folder that is otherwise malformed is
    better described by what is wrong with the string itself.

    inside_inbox compares NFC-normalised, casefolded text on segment
    boundaries; only `inbox_path` has trailing `/` removed for the comparison
    (the config carries `100 Inbox/`). A blank `inbox_path` never matches.
    """
    def refuse(reason: str) -> TypedNameVerdict:
        return TypedNameVerdict(ok=False, name=folder, reason=reason)

    if not folder.strip():
        return refuse("blank")
    if _escapes_vault(folder):
        return refuse("escapes_vault")
    if "//" in folder:
        return refuse("empty_segment")
    if any(seg != seg.strip() for seg in folder.split("/")):
        return refuse("edge_whitespace")
    if folder.endswith("/"):
        return refuse("trailing_separator")
    if any(u in folder for u in _UNSAFE_SUBSTRINGS) or any(
        is_control_char(c) for c in folder
    ):
        return refuse("unsafe_sequence")
    if any(c in _NON_SEPARATOR_FORBIDDEN_CHARS for c in folder):
        return refuse("forbidden_character")
    if any(c in _LINK_BREAKING_CHARS for c in folder):
        return refuse("breaks_link")
    if _is_inside_inbox(folder, inbox_path):
        return refuse("inside_inbox")
    return TypedNameVerdict(ok=True, name=folder)
