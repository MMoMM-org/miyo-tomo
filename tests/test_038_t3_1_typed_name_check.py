#!/usr/bin/env python3
"""Spec 038 T3.1 — the typed-name check refuses, it never rewrites.

ADR-5: a new `tomo/scripts/lib/typed_name_check.py` decides whether an
owner-typed attachment name is usable, and returns a closed set of refusal
reasons so the renderer (T3.4) can phrase each without parsing a string.
`sanitize_stem` is NOT reused on this path — it substitutes (`/` -> `-`),
which would file a typed `a/b.png` as `a-b.png` with nothing reported: the
exact defect this spec closes, wearing a different hat.

THREE refusal classes (owner ruling 2026-10-01 — `taken` is a property of
the run, not of the string, and is already decided at
render_actions.py:939):

  1. separator present   -- a name is not a bare basename
  2. forbidden character -- one of FORBIDDEN_CHARS (10 members, incl. NUL)
  3. blank                -- empty or whitespace-only

Ordering: `/` is BOTH a separator and a FORBIDDEN_CHARS member. The
separator check MUST run before the forbidden-character check, or
`a/b.png` would report `forbidden_character` instead of `separator_present`
-- pinned below with a name that is both.

A usable name is returned UNCHANGED -- the check never rewrites.

FALSIFICATION per test, named in each test's own body via the mutation
that would turn it red.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))
from lib.typed_name_check import (  # noqa: E402
    REFUSAL_REASONS,
    check_typed_name,
)


# ---------------------------------------------------------------------------
# Acceptance: a usable name passes through unchanged.
# ---------------------------------------------------------------------------


def test_usable_name_is_accepted_unchanged():
    """A plain basename is usable and returned byte-identical.

    Falsified by: a verdict object that normalises or copies the name
    (e.g. via sanitize_stem) instead of returning the original string.
    """
    verdict = check_typed_name("karte (2).png")
    assert verdict.ok is True
    assert verdict.reason is None
    assert verdict.name == "karte (2).png"


def test_usable_name_with_unicode_is_accepted_unchanged():
    """Non-ASCII basenames are usable too -- nothing here is ASCII-only.

    Falsified by: an implementation that rejects or transliterates
    non-ASCII characters it was never asked to refuse.
    """
    verdict = check_typed_name("karte münchen.png")
    assert verdict.ok is True
    assert verdict.name == "karte münchen.png"


def test_leading_and_trailing_whitespace_is_accepted_and_preserved():
    """PINS TODAY'S ANSWER, not a final ruling (flagged to the owner
    2026-10-01, see the module docstring note below) -- a name padded with
    leading/trailing whitespace (`"  a.png  "`) is neither blank (it has
    non-whitespace content), nor separator-bearing, nor forbidden-char-
    bearing, so it is accepted UNCHANGED, padding and all. The task's
    three refusal classes are a CLOSED set (owner ruling 2026-10-01); a
    fourth "padded" class would need the same kind of explicit ruling that
    excluded `taken`, and ADR-5's two-option discipline (accept verbatim
    or refuse) forbids a third option that trims instead.

    This test exists so a future change to this behaviour is deliberate,
    not an accidental side effect of someone "fixing" `name.strip()` to
    also drive the returned value.

    Falsified by: any change that trims, rejects, or otherwise alters
    `" a.png "` on this path.
    """
    verdict = check_typed_name("  a.png  ")
    assert verdict.ok is True
    assert verdict.name == "  a.png  "


# ---------------------------------------------------------------------------
# Refusal class 1: separator present.
# ---------------------------------------------------------------------------


def test_relative_separator_is_refused():
    """`a/b.png` is refused for its separator, not silently basenamed.

    Falsified by: a check that strips to the last segment (what
    `_asset_dest_join` already does) instead of refusing.
    """
    verdict = check_typed_name("a/b.png")
    assert verdict.ok is False
    assert verdict.reason == "separator_present"


def test_parent_traversal_separator_is_refused():
    """`../../x.png` is refused for its separator.

    Falsified by: a check that only looks for a single '/' at a fixed
    position and misses repeated traversal segments.
    """
    verdict = check_typed_name("../../x.png")
    assert verdict.ok is False
    assert verdict.reason == "separator_present"


def test_absolute_path_separator_is_refused():
    """`/abs.png` is refused for its separator.

    Falsified by: a check that only inspects for a separator strictly
    between two non-empty segments and misses a leading slash.
    """
    verdict = check_typed_name("/abs.png")
    assert verdict.ok is False
    assert verdict.reason == "separator_present"


def test_separator_and_forbidden_char_reports_separator_first():
    """`a:b/c.png` carries both a separator and a forbidden ':' --
    the separator class must win, pinning the ordering ADR-5 requires
    (`/` is itself a FORBIDDEN_CHARS member, so the two checks collide
    on any typed path and the order is not incidental).

    Falsified by: swapping the order of the separator and
    forbidden-character checks in the implementation.
    """
    verdict = check_typed_name("a:b/c.png")
    assert verdict.ok is False
    assert verdict.reason == "separator_present"


# ---------------------------------------------------------------------------
# Refusal class 2: forbidden character (the other nine members of
# FORBIDDEN_CHARS, since '/' is already covered by the separator class).
# ---------------------------------------------------------------------------


def test_each_forbidden_character_is_refused():
    """Every non-separator member of FORBIDDEN_CHARS refuses on its own.

    FORBIDDEN_CHARS has TEN members (obsidian_filename.py:32): the eight
    named in the task (: * ? " < > | and backslash), plus '/' (covered by
    the separator class above), plus NUL (never named in the task's prose,
    refused here so "every forbidden character" means all ten).

    Falsified by: omitting any one of these nine characters from the
    implementation's forbidden set, or reusing a copy that dropped NUL.
    """
    forbidden_non_separator = [":", "*", "?", '"', "<", ">", "|", "\\", "\x00"]
    for char in forbidden_non_separator:
        name = f"karte{char}png"
        verdict = check_typed_name(name)
        assert verdict.ok is False, f"expected refusal for char {char!r}"
        assert verdict.reason == "forbidden_character", (
            f"expected forbidden_character for char {char!r}, got {verdict.reason!r}"
        )


def test_nul_byte_is_refused():
    """NUL is refused even though the task's prose never names it --
    only FORBIDDEN_CHARS' ten-member set does.

    Falsified by: an implementation that hand-lists the eight prose
    characters instead of importing/mirroring the full FORBIDDEN_CHARS set.
    """
    verdict = check_typed_name("karte\x00.png")
    assert verdict.ok is False
    assert verdict.reason == "forbidden_character"


# ---------------------------------------------------------------------------
# Refusal class 3: blank / whitespace-only.
# ---------------------------------------------------------------------------


def test_empty_string_is_refused():
    """"" is refused as blank.

    Falsified by: an implementation that only checks falsiness after
    stripping, and happens to also accept it (this pins the empty case
    independently of the whitespace case below).
    """
    verdict = check_typed_name("")
    assert verdict.ok is False
    assert verdict.reason == "blank"


def test_whitespace_only_is_refused():
    """" " is refused as blank -- closing the gap the two existing
    truthiness guards leave (`not " "` is False, so
    render_actions.py:788's `not remedy_entry.get("proposed_name")` and
    `_asset_dest_join`'s `if not basename` at :572 both let it through
    today). This check must precede both.

    Falsified by: an implementation using bare `not name` instead of
    `not name.strip()`, which is exactly the existing-guard bug repeated.
    """
    verdict = check_typed_name(" ")
    assert verdict.ok is False
    assert verdict.reason == "blank"


def test_whitespace_only_tabs_and_newlines_is_refused():
    """Blank detection covers more than a single space character.

    Falsified by: an implementation checking `name == " "` literally
    instead of `name.strip()`.
    """
    verdict = check_typed_name("\t\n  ")
    assert verdict.ok is False
    assert verdict.reason == "blank"


# ---------------------------------------------------------------------------
# Interface shape.
# ---------------------------------------------------------------------------


def test_refusal_reasons_is_a_closed_set_of_three():
    """REFUSAL_REASONS names exactly the three classes -- not four. `taken`
    is deliberately excluded (owner ruling 2026-10-01): it is a property
    of the run, which render_actions.py:939 already decides, not of the
    string this module checks.

    Falsified by: adding a fourth reason (e.g. `taken`) to the set, or
    naming the three differently than the module documents.
    """
    assert REFUSAL_REASONS == frozenset(
        {"separator_present", "forbidden_character", "blank"}
    )


def test_reason_tokens_are_not_prose():
    """Reason tokens are stable snake_case identifiers, not sentences --
    the renderer (T3.4) must phrase each without parsing a string.

    Falsified by: a reason value containing a space.
    """
    for reason in REFUSAL_REASONS:
        assert " " not in reason


def test_signature_takes_one_argument():
    """check_typed_name takes exactly one positional argument -- no run
    state, no vault listing, no `taken`/`claimed` parameter.

    Falsified by: adding a second required parameter to the function.
    """
    import inspect

    sig = inspect.signature(check_typed_name)
    params = list(sig.parameters.values())
    assert len(params) == 1
