#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_tree_builder_inline_tags.py — inline exclude-tag support (#50).

The ADR-13 exclude tags (MiYo/Tomo/exclude/moc, .../exclude/note) used to take
effect ONLY in YAML frontmatter; an inline `#MiYo/Tomo/exclude/moc` was silently
ignored, while MOC discovery (Kado search_by_tag) matched inline + frontmatter
both. extract_tags now merges inline tags from the body so the two forms are
equivalent.

Issue: https://github.com/MMoMM-org/miyo-tomo/issues/50
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def _load(module_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(module_name, SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_builder = _load("moc_tree_builder", "moc-tree-builder.py")
from lib.moc_tags import EXCLUDE_MOC_TAG, EXCLUDE_NOTE_TAG  # noqa: E402

extract_tags = _builder.extract_tags
parse_inline_tags = _builder.parse_inline_tags


# ── backward compatibility (frontmatter-only, no body) ───────────────────────


def test_frontmatter_list_unchanged_without_body():
    assert extract_tags({"tags": ["a", "b"]}) == ["a", "b"]


def test_frontmatter_scalar_unchanged_without_body():
    assert extract_tags({"tags": "solo"}) == ["solo"]


def test_no_tags_returns_empty_list_not_none():
    assert extract_tags({}) == []
    assert extract_tags({}, "body with no tags") == []


# ── the fix: inline tags are recognised ──────────────────────────────────────


def test_inline_only_tag_recognised():
    tags = extract_tags({}, "Some prose.\n\n#MiYo/Tomo/exclude/moc\n")
    assert "MiYo/Tomo/exclude/moc" in tags


def test_inline_exclude_moc_matches_constant():
    """End-to-end: an inline exclude tag satisfies the membership check the
    real filters (orphan_link / moc-discovery) perform."""
    tags = extract_tags({}, "#MiYo/Tomo/exclude/moc trailing text")
    assert EXCLUDE_MOC_TAG in tags


def test_inline_exclude_note_matches_constant():
    tags = extract_tags({}, "intro #MiYo/Tomo/exclude/note")
    assert EXCLUDE_NOTE_TAG in tags


def test_frontmatter_and_inline_merged_deduped():
    tags = extract_tags(
        {"tags": ["topic/x", "MiYo/Tomo/exclude/moc"]},
        "body #topic/y and #MiYo/Tomo/exclude/moc again",
    )
    # frontmatter first, then new inline; the duplicate exclude tag appears once.
    assert tags == ["topic/x", "MiYo/Tomo/exclude/moc", "topic/y"]


# ── parser hygiene ───────────────────────────────────────────────────────────


def test_code_fence_tags_skipped():
    body = "real #keep/this\n\n```\n#not/a/tag inside a fence\n```\n"
    tags = parse_inline_tags(body)
    assert "keep/this" in tags
    assert "not/a/tag" not in tags


def test_inline_code_span_tags_skipped():
    tags = parse_inline_tags("prose `#not/a/tag` and #real/tag here")
    assert "real/tag" in tags
    assert "not/a/tag" not in tags


def test_heading_hashes_not_tags():
    tags = parse_inline_tags("## Content\n### Structure\ntext")
    assert tags == []


def test_pure_numeric_not_a_tag():
    assert parse_inline_tags("issue #123 and #v2/topic") == ["v2/topic"]


def test_midword_hash_not_a_tag():
    assert parse_inline_tags("email me foo#bar please") == []


def test_nested_slash_tag_preserved():
    assert parse_inline_tags("#MiYo/Tomo/exclude/moc") == ["MiYo/Tomo/exclude/moc"]


def test_trailing_punctuation_trimmed():
    # A trailing slash/hyphen is not part of the tag.
    assert parse_inline_tags("see #topic/a- and #topic/b/") == ["topic/a", "topic/b"]


def test_first_seen_order_and_dedup():
    assert parse_inline_tags("#b #a #b #c #a") == ["b", "a", "c"]


def test_empty_body_returns_empty():
    assert parse_inline_tags(None) == []
    assert parse_inline_tags("") == []


if __name__ == "__main__":
    import pytest
    raise SystemExit(pytest.main([__file__, "-v"]))
