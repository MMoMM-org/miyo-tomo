#!/usr/bin/env python3
# version: 0.1.0
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
