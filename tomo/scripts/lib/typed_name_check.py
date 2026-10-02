#!/usr/bin/env python3
# version: 0.1.2
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
# a string. Exactly three members — `taken` is excluded on purpose; see the
# module docstring.
REFUSAL_REASONS = frozenset({"separator_present", "forbidden_character", "blank"})

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

    A name padded with leading/trailing whitespace (`"  a.png  "`) is none
    of the three refusal classes, so it is accepted verbatim, padding and
    all — `.strip()` here only decides blankness, it never trims the
    returned name. Flagged to the owner 2026-10-01 as a possible fourth
    case (whitespace is easy to type by accident and invisible once typed);
    left as accept-as-is pending a ruling, since ADR-5 permits only accept-
    verbatim or refuse, never trim, and the three classes are a closed set.
    See tests/test_038_t3_1_typed_name_check.py's pinning test.
    """
    if not name.strip():
        return TypedNameVerdict(ok=False, name=name, reason="blank")

    if "/" in name:
        return TypedNameVerdict(ok=False, name=name, reason="separator_present")

    if any(c in _NON_SEPARATOR_FORBIDDEN_CHARS for c in name):
        return TypedNameVerdict(ok=False, name=name, reason="forbidden_character")

    return TypedNameVerdict(ok=True, name=name)
