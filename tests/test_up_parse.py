#!/usr/bin/env python3
# version: 0.3.0
"""test_up_parse.py — Tests for lib/up_parse.parse_up_from_content.

Covers the dual-up SSoT (spec 021, Phase 1, T1.1):
- inline-only `up::` → target+source=inline
- frontmatter-only `up:` list / scalar / "[[X]]" → target+source=frontmatter
- BOTH present, differing targets → inline WINS (ADR-2)
- empty / null variants → target=None, source=None
- alias [[Stem|Alias]] → stem only
- anchor [[X#^id]] / [[X#Heading]] → X only
- frontmatter block split out of raw content correctly

Stdlib + yaml only — no live Kado calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.up_parse` works

from lib import up_parse  # noqa: E402


# ── helpers ─────────────────────────────────────────────────────────────────


def _fm(up_value: object) -> str:
    """Build a raw note with only frontmatter `up:` set to `up_value`."""
    fm = yaml.dump({"up": up_value}, default_flow_style=False, allow_unicode=True)
    return f"---\n{fm}---\nSome body text.\n"


def _inline(target: str) -> str:
    """Raw note with only an inline `up::` line."""
    return f"Some intro.\n\nup:: [[{target}]]\n\nMore text.\n"


def _both(fm_target: str, inline_target: str) -> str:
    """Raw note with frontmatter `up:` AND inline `up::`, differing targets."""
    fm = yaml.dump({"up": f"[[{fm_target}]]"}, default_flow_style=False)
    return f"---\n{fm}---\nup:: [[{inline_target}]]\n\nBody.\n"


# ── inline-only ─────────────────────────────────────────────────────────────


def test_inline_only_plain():
    result = up_parse.parse_up_from_content(_inline("ParentNote"))
    assert result.target == "ParentNote"
    assert result.source == "inline"


def test_inline_only_with_alias():
    result = up_parse.parse_up_from_content(_inline("ParentNote|My Alias"))
    assert result.target == "ParentNote"
    assert result.source == "inline"


def test_inline_only_anchor_block_id():
    result = up_parse.parse_up_from_content(_inline("ParentNote#^block-id"))
    assert result.target == "ParentNote"
    assert result.source == "inline"


def test_inline_only_anchor_heading():
    result = up_parse.parse_up_from_content(_inline("ParentNote#Heading Title"))
    assert result.target == "ParentNote"
    assert result.source == "inline"


def test_inline_only_alias_and_anchor():
    # anchor before alias is not standard Obsidian but we still strip both
    result = up_parse.parse_up_from_content(_inline("ParentNote#^id|Alias"))
    # strip anchor first, then alias → "ParentNote"
    assert result.target == "ParentNote"
    assert result.source == "inline"


def test_inline_inside_callout():
    """up:: inside a callout-block prefix (> ) must still match."""
    content = "---\ntitle: Test\n---\n> up:: [[CalloutParent]]\n"
    result = up_parse.parse_up_from_content(content)
    assert result.target == "CalloutParent"
    assert result.source == "inline"


# ── frontmatter-only ────────────────────────────────────────────────────────


def test_frontmatter_list_wikilink():
    content = _fm(["[[FrontParent]]"])
    result = up_parse.parse_up_from_content(content)
    assert result.target == "FrontParent"
    assert result.source == "frontmatter"


def test_frontmatter_scalar_wikilink():
    content = _fm("[[ScalarParent]]")
    result = up_parse.parse_up_from_content(content)
    assert result.target == "ScalarParent"
    assert result.source == "frontmatter"


def test_frontmatter_list_plain_stem():
    """Plain stem (no [[...]]) in a frontmatter list is accepted."""
    content = _fm(["PlainStem"])
    result = up_parse.parse_up_from_content(content)
    assert result.target == "PlainStem"
    assert result.source == "frontmatter"


def test_frontmatter_scalar_plain_stem():
    content = _fm("PlainStem")
    result = up_parse.parse_up_from_content(content)
    assert result.target == "PlainStem"
    assert result.source == "frontmatter"


def test_frontmatter_wikilink_with_alias():
    content = _fm("[[FMParent|Some Display Name]]")
    result = up_parse.parse_up_from_content(content)
    assert result.target == "FMParent"
    assert result.source == "frontmatter"


def test_frontmatter_wikilink_with_anchor():
    content = _fm("[[FMParent#Heading]]")
    result = up_parse.parse_up_from_content(content)
    assert result.target == "FMParent"
    assert result.source == "frontmatter"


def test_frontmatter_list_first_wins():
    """When the list has multiple entries only the first is used."""
    content = _fm(["[[FirstParent]]", "[[SecondParent]]"])
    result = up_parse.parse_up_from_content(content)
    assert result.target == "FirstParent"
    assert result.source == "frontmatter"


# ── stringified list-repr (dirty cache) — FIX 2 root cause ───────────────────
# Some caches persist a frontmatter `up:` list as its Python str repr, e.g.
# "['020 Active MOC']". Treated as a bare stem it becomes garbage (and FALSELY
# marks the note broken_up). _first_wikilink must yaml.safe_load such a string
# and take the first non-empty element.


def test_frontmatter_stringified_single_element_list():
    content = _fm("['020 Active MOC']")
    result = up_parse.parse_up_from_content(content)
    assert result.target == "020 Active MOC"
    assert result.source == "frontmatter"


def test_frontmatter_stringified_multi_element_list_first_wins():
    content = _fm("['a', 'b']")
    result = up_parse.parse_up_from_content(content)
    assert result.target == "a"
    assert result.source == "frontmatter"


def test_frontmatter_stringified_double_quoted_list():
    content = _fm('["x"]')
    result = up_parse.parse_up_from_content(content)
    assert result.target == "x"
    assert result.source == "frontmatter"


def test_genuine_wikilink_unchanged_by_list_repr_fix():
    """A real [[020 Active MOC]] must still parse to the bare stem, untouched."""
    content = _fm("[[020 Active MOC]]")
    result = up_parse.parse_up_from_content(content)
    assert result.target == "020 Active MOC"
    assert result.source == "frontmatter"


def test_genuine_bare_stem_unchanged_by_list_repr_fix():
    """A plain bare stem (no brackets) must still parse unchanged."""
    content = _fm("020 Active MOC")
    result = up_parse.parse_up_from_content(content)
    assert result.target == "020 Active MOC"
    assert result.source == "frontmatter"


# ── BOTH present — inline WINS ───────────────────────────────────────────────


def test_inline_wins_over_frontmatter():
    content = _both(fm_target="FMParent", inline_target="InlineParent")
    result = up_parse.parse_up_from_content(content)
    assert result.target == "InlineParent"
    assert result.source == "inline"


def test_inline_wins_even_when_same_target():
    content = _both(fm_target="SameParent", inline_target="SameParent")
    result = up_parse.parse_up_from_content(content)
    assert result.source == "inline"


# ── empty / null / absent ────────────────────────────────────────────────────


def test_no_up_at_all():
    content = "---\ntitle: No parent\n---\nJust some body.\n"
    result = up_parse.parse_up_from_content(content)
    assert result.target is None
    assert result.source is None


def test_frontmatter_up_empty_string():
    content = _fm("")
    result = up_parse.parse_up_from_content(content)
    assert result.target is None
    assert result.source is None


def test_frontmatter_up_null():
    content = _fm(None)
    result = up_parse.parse_up_from_content(content)
    assert result.target is None
    assert result.source is None


def test_frontmatter_up_empty_list():
    content = _fm([])
    result = up_parse.parse_up_from_content(content)
    assert result.target is None
    assert result.source is None


def test_inline_up_without_wikilink():
    """up:: present but not followed by a [[...]] → treated as absent."""
    content = "---\ntitle: X\n---\nup:: just text, no wikilink\n"
    result = up_parse.parse_up_from_content(content)
    assert result.target is None
    assert result.source is None


def test_inline_up_empty():
    """up:: with nothing after it → absent."""
    content = "---\ntitle: X\n---\nup::\n"
    result = up_parse.parse_up_from_content(content)
    assert result.target is None
    assert result.source is None


def test_no_frontmatter_no_inline():
    """Bare note with no frontmatter and no up:: line."""
    content = "Just plain text.\n"
    result = up_parse.parse_up_from_content(content)
    assert result.target is None
    assert result.source is None


# ── return type ──────────────────────────────────────────────────────────────


def test_result_is_up_parse_result():
    result = up_parse.parse_up_from_content(_inline("X"))
    assert isinstance(result, up_parse.UpParseResult)


def test_result_has_target_and_source_attrs():
    result = up_parse.parse_up_from_content("")
    assert hasattr(result, "target")
    assert hasattr(result, "source")


# ── frontmatter split offset regression (FIX 1) ──────────────────────────────


def test_leading_newline_does_not_corrupt_body_slice():
    """Raw content with a leading newline must still parse correctly.

    Guards the _split_frontmatter fix: match.end() must be an offset into the
    lstrip()-normalized string, not the original — otherwise the body slice
    starts mid-delimiter and the inline regex silently fails.
    """
    content = "\n---\ntitle: X\n---\nup:: [[LeadingNewlineParent]]\n"
    result = up_parse.parse_up_from_content(content)
    assert result.target == "LeadingNewlineParent"
    assert result.source == "inline"


# ── raw_value (spec 032, Phase 1, T1.1) ───────────────────────────────────────
# raw_value carries the observed frontmatter `up:` property value VERBATIM
# (shape and order intact) so a later phase can guard against re-emitting an
# already-broken declaration. Inline declarations carry no value — there is
# no property to guard (ADR-1).


def test_raw_value_frontmatter_list_preserves_shape_and_order():
    content = _fm(["[[A]]", "[[B]]"])
    result = up_parse.parse_up_from_content(content)
    assert result.raw_value == ["[[A]]", "[[B]]"]


def test_raw_value_frontmatter_scalar_not_wrapped_in_list():
    content = _fm("[[A]]")
    result = up_parse.parse_up_from_content(content)
    assert result.raw_value == "[[A]]"
    assert not isinstance(result.raw_value, list)


def test_raw_value_inline_is_none():
    content = _inline("A")
    result = up_parse.parse_up_from_content(content)
    assert result.source == "inline"
    assert result.raw_value is None


def test_raw_value_both_present_inline_wins_raw_value_none():
    """Inline still wins (unchanged precedence, ADR-2); raw_value stays None —
    inline has no property to guard, and the frontmatter value it shadows must
    not leak through."""
    content = _both(fm_target="FMParent", inline_target="InlineParent")
    result = up_parse.parse_up_from_content(content)
    assert result.source == "inline"
    assert result.target == "InlineParent"
    assert result.raw_value is None


def test_raw_value_no_declaration_is_none():
    content = "Just plain text.\n"
    result = up_parse.parse_up_from_content(content)
    assert result.target is None
    assert result.source is None
    assert result.raw_value is None


def test_raw_value_empty_property_falls_through_to_none():
    """An empty `up:` property makes _first_wikilink return falsy, so control
    falls through past the frontmatter return site to the final absent-branch
    return — which does NOT populate raw_value. This means an empty property,
    an inline declaration, and total absence all yield raw_value is None. That
    is expected: ADR-3's `_MISSING` sentinel (not a `None` check) is what later
    distinguishes freshness downstream — this fall-through path is NOT to be
    "fixed" to populate raw_value, since that would be a design change."""
    empty_string = up_parse.parse_up_from_content(_fm(""))
    empty_list = up_parse.parse_up_from_content(_fm([]))
    assert empty_string.target is None
    assert empty_string.raw_value is None
    assert empty_list.target is None
    assert empty_list.raw_value is None
