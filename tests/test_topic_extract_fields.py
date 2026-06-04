#!/usr/bin/env python3
# version: 0.2.0
"""test_topic_extract_fields.py — Tests for extract_topics_from_fields() — T1.2 of spec 015 (F-34).

All tests run RED before the implementation is added (CON-1 TDD discipline).
Covers:
  - H1 heading used as title source
  - Filename title fallback when no H1 in headings list
  - Level-2 headings NO LONGER contribute topics (method 2 dropped, v0.3.0)
  - ADR-4: kind=='embed' links excluded; kind=='link' included
  - Link target alias/path/anchor stripping
  - Tags: '#' prefix stripped; STRUCTURAL_TAG_PREFIXES dropped
  - Parity with extract_topics() content path on equivalent input
  - Empty fields returns empty topics
  - clean_title strips wikilink brackets, preserving inner text
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# topic-extract.py has a hyphen — load via importlib (pattern from test_instruction_render_*.py)
_spec = importlib.util.spec_from_file_location(
    "topic_extract", SCRIPTS_DIR / "topic-extract.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

extract_topics_from_fields = _mod.extract_topics_from_fields  # RED until implemented
extract_topics = _mod.extract_topics
clean_title = _mod.clean_title


# ---------------------------------------------------------------------------
# T1.2-1: H1 heading used as title
# ---------------------------------------------------------------------------

def test_h1_heading_used_as_title():
    """H1 in headings list (level==1) feeds into method 1 (title analysis)."""
    result = extract_topics_from_fields(
        title=None,
        headings=[{"heading": "Monte Carlo Tree Search", "level": 1}],
        links=[],
        tags=[],
    )
    topics = result["topics"]
    assert any("monte carlo tree search" in t or "search" in t for t in topics), \
        f"Expected title-derived topics in {topics}"
    assert "title" in result["source_methods"]
    assert len(result["source_methods"]["title"]) > 0


# ---------------------------------------------------------------------------
# T1.2-2: Filename title fallback when no H1
# ---------------------------------------------------------------------------

def test_filename_title_fallback_when_no_h1():
    """When headings has no level==1, the explicit title param is used."""
    result = extract_topics_from_fields(
        title="Alpha Beta Pruning",
        headings=[{"heading": "Overview", "level": 2}],
        links=[],
        tags=[],
    )
    topics = result["topics"]
    assert any("alpha beta pruning" in t or "alpha" in t for t in topics), \
        f"Expected title-derived topics in {topics}"
    # 'Overview' is boilerplate — should not appear in headings source
    assert "overview" not in result["source_methods"]["headings"]


# ---------------------------------------------------------------------------
# T1.2-3: Level-2 headings do NOT contribute topics (method 2 dropped, v0.3.0)
# ---------------------------------------------------------------------------

def test_level2_headings_do_not_contribute_topics():
    """Level==2 headings must NOT produce any topics — method 2 is dropped.

    A note with only level-2 headings and no title/H1/tags/links must yield
    empty topics. The 'headings' key must be empty (or absent) in source_methods.

    Fails if method 2 is still active: game theory and search algorithms would
    then appear as topics — neither may appear after the change.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[
            {"heading": "Game Theory", "level": 2},
            {"heading": "References", "level": 2},
            {"heading": "Search Algorithms", "level": 2},
            {"heading": "Notes", "level": 2},
        ],
        links=[],
        tags=[],
    )
    headings_topics = result["source_methods"].get("headings", [])
    assert headings_topics == [], \
        f"Method 2 must be dropped: expected empty headings, got {headings_topics}"
    assert result["topics"] == [], \
        f"No other signal present — expected empty topics, got {result['topics']}"
    # Specific non-vacuous check: these would appear if method 2 were active
    all_topics = result["topics"]
    assert "game theory" not in all_topics, \
        "Level-2 heading 'game theory' must not contribute — method 2 is dropped"
    assert "search algorithms" not in all_topics, \
        "Level-2 heading 'search algorithms' must not contribute — method 2 is dropped"


# ---------------------------------------------------------------------------
# T1.2-4: ADR-4 — kind=='link' used; kind=='embed' dropped
# ---------------------------------------------------------------------------

def test_links_kind_link_used_kind_embed_dropped():
    """ADR-4: only kind=='link' entries contribute topics; 'embed' entries are excluded."""
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[
            {"target": "Minimax Algorithm", "kind": "link"},
            {"target": "diagram.excalidraw", "kind": "embed"},   # excluded (ADR-4)
            {"target": "Game Theory", "kind": "link"},
        ],
        tags=[],
    )
    link_topics = result["source_methods"]["links"]
    assert "minimax algorithm" in link_topics, \
        f"Expected 'minimax algorithm' in {link_topics}"
    assert "game theory" in link_topics, \
        f"Expected 'game theory' in {link_topics}"
    assert "diagram.excalidraw" not in link_topics, \
        "Embed target must be excluded (ADR-4)"
    assert not any("excalidraw" in t for t in link_topics), \
        "No part of the excalidraw embed should appear"


# ---------------------------------------------------------------------------
# T1.2-5: Link target alias/path/anchor stripped
# ---------------------------------------------------------------------------

def test_link_target_alias_path_anchor_stripped():
    """Raw link target 'Folder/Note#heading|Alias' normalises to just the note name."""
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[
            # Full complex target: path + anchor + alias all present
            {"target": "Folder/Note#heading|Alias", "kind": "link"},
        ],
        tags=[],
    )
    link_topics = result["source_methods"]["links"]
    # Should resolve to 'note' (path prefix dropped, anchor dropped, alias dropped)
    assert "note" in link_topics, \
        f"Expected 'note' after stripping path/anchor/alias, got {link_topics}"
    assert "folder" not in link_topics, "Path prefix should be stripped"
    assert "heading" not in link_topics, "Anchor should be stripped"
    assert "alias" not in link_topics, "Alias should be stripped"


# ---------------------------------------------------------------------------
# T1.2-6: Tags '#' prefix stripped; structural tags filtered
# ---------------------------------------------------------------------------

def test_tags_hash_prefix_stripped_then_structural_filtered():
    """Tags with '#' prefix are stripped; type/ and status/ prefixes are dropped entirely."""
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[],
        tags=["#nlp", "#type/x", "#status/active", "#games", "machine-learning"],
    )
    tag_topics = result["source_methods"]["tags"]
    # '#nlp' → 'nlp' must appear
    assert "nlp" in tag_topics, \
        f"Expected 'nlp' (hash stripped) in {tag_topics}"
    # '#games' → 'games'
    assert "games" in tag_topics, \
        f"Expected 'games' in {tag_topics}"
    # bare 'machine-learning' still valid
    assert "machine-learning" in tag_topics, \
        f"Expected 'machine-learning' in {tag_topics}"
    # structural tags must be filtered out entirely
    assert "type" not in tag_topics, "'type' prefix should be filtered"
    assert "x" not in tag_topics, "Structural tag child 'x' should be filtered"
    assert "status" not in tag_topics, "'status' prefix should be filtered"
    assert "active" not in tag_topics, "Structural tag child 'active' should be filtered"


# ---------------------------------------------------------------------------
# T1.2-7: Parity with extract_topics() on equivalent input
# ---------------------------------------------------------------------------

def test_parity_with_content_path_on_equivalent_input():
    """extract_topics_from_fields() and extract_topics() yield consistent topics for equivalent input."""
    markdown_content = """\
---
tags: [nlp, games]
---

# Alpha Beta Pruning

## Search Algorithms

See also [[Minimax]] and [[Game Theory]].
"""
    content_result = extract_topics(markdown_content)

    # Equivalent structured input (no H1 in headings — title from explicit param)
    fields_result = extract_topics_from_fields(
        title=None,
        headings=[
            {"heading": "Alpha Beta Pruning", "level": 1},
            {"heading": "Search Algorithms", "level": 2},
        ],
        links=[
            {"target": "Minimax", "kind": "link"},
            {"target": "Game Theory", "kind": "link"},
        ],
        tags=["nlp", "games"],
    )

    content_topics = set(content_result["topics"])
    fields_topics = set(fields_result["topics"])

    # The key topics must overlap — both paths surface the same signal
    overlap = content_topics & fields_topics
    assert len(overlap) > 0, \
        f"No overlap between content path {content_topics} and fields path {fields_topics}"

    # "search algorithms" is a level-2 heading — method 2 is dropped in v0.3.0,
    # so it must NOT appear in the fields path.
    for expected in ("minimax", "nlp", "games"):
        assert expected in fields_topics, \
            f"Expected '{expected}' in fields result {fields_topics}"
    assert "search algorithms" not in fields_topics, \
        "Level-2 heading 'search algorithms' must not appear — method 2 dropped"


# ---------------------------------------------------------------------------
# T1.2-8b: H1 heading takes priority over explicit title when both present
# ---------------------------------------------------------------------------

def test_h1_takes_priority_over_explicit_title():
    """When both a level==1 heading and an explicit title are provided, H1 wins."""
    result = extract_topics_from_fields(
        title="Should Not Win",
        headings=[{"heading": "H1 Wins", "level": 1}],
        links=[],
        tags=[],
    )
    title_topics = result["source_methods"]["title"]
    # At least one token from "H1 Wins" must appear
    assert any(tok in title_topics for tok in ("h1 wins", "h1", "wins")), \
        f"Expected H1-derived token in {title_topics}"
    # No token from "Should Not Win" may appear
    assert not any(tok in title_topics for tok in ("should not win", "should", "win")), \
        f"title= value leaked into title_topics: {title_topics}"


# ---------------------------------------------------------------------------
# T1.2-8: Empty fields returns empty topics
# ---------------------------------------------------------------------------

def test_empty_fields_returns_empty_topics():
    """All-empty input yields an empty topics list and empty source_methods lists."""
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[],
        tags=[],
    )
    assert result["topics"] == [], f"Expected [], got {result['topics']}"
    for method, items in result["source_methods"].items():
        assert items == [], \
            f"Expected empty list for method '{method}', got {items}"


# ---------------------------------------------------------------------------
# T1.2-NEW-1: Note with ONLY level-2 headings yields empty topics
# ---------------------------------------------------------------------------

def test_only_level2_headings_yields_empty_topics():
    """A note with only level-2 headings and no other signal must return empty topics.

    Non-vacuous: if method 2 were active the result would contain e.g. 'algorithms'
    — any non-empty topics list means method 2 is still running.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[
            {"heading": "Algorithms", "level": 2},
            {"heading": "Implementation", "level": 2},
            {"heading": "Examples", "level": 2},
        ],
        links=[],
        tags=[],
    )
    assert result["topics"] == [], \
        f"Only level-2 headings present — topics must be empty, got {result['topics']}"
    assert result["source_methods"].get("headings", []) == [], \
        f"headings source must be empty, got {result['source_methods'].get('headings')}"
    # Non-vacuous: 'algorithms' would appear if method 2 were still active
    assert "algorithms" not in result["topics"], \
        "Method 2 still active: 'algorithms' from H2 must not appear"


# ---------------------------------------------------------------------------
# T1.2-NEW-2: H1 (level==1) still feeds method 1 after method 2 is dropped
# ---------------------------------------------------------------------------

def test_h1_still_feeds_method1_after_method2_dropped():
    """Level==1 heading must still produce title topics even after method 2 is removed.

    Non-vacuous: if method 1 were also broken, title source would be empty and
    this test would fail.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[
            {"heading": "Reinforcement Learning", "level": 1},
            {"heading": "Policy Gradient", "level": 2},   # must not contribute
        ],
        links=[],
        tags=[],
    )
    title_topics = result["source_methods"]["title"]
    assert len(title_topics) > 0, \
        f"Method 1 (H1) must still produce topics after method 2 removal, got {title_topics}"
    assert any(tok in title_topics for tok in ("reinforcement learning", "reinforcement", "learning")), \
        f"Expected H1 content in title topics, got {title_topics}"
    # Verify the H2 heading did NOT sneak in via headings source
    headings_topics = result["source_methods"].get("headings", [])
    assert headings_topics == [], \
        f"Method 2 headings must be empty, got {headings_topics}"
    assert "policy gradient" not in result["topics"], \
        "Level-2 heading 'policy gradient' must not appear in topics"


# ---------------------------------------------------------------------------
# T1.2-NEW-3: clean_title strips [[ and ]] brackets, keeps inner text
# ---------------------------------------------------------------------------

def test_clean_title_strips_wikilink_brackets():
    """[[Dataview]] - Foo cleans to text without [[ or ]] fragments.

    Non-vacuous: without the fix, clean_title would leave '[[dataview' in topics
    (because the bracket characters pass through and produce a mangled topic).
    """
    result = clean_title("[[Dataview]] - Foo")
    assert "[[" not in result, f"[[ must be stripped, got {result!r}"
    assert "]]" not in result, f"]] must be stripped, got {result!r}"
    # Inner text must be retained
    assert "Dataview" in result, f"Inner text 'Dataview' must be kept, got {result!r}"
    assert "Foo" in result, f"'Foo' must be kept, got {result!r}"


def test_clean_title_keeps_inner_text_for_plain_wikilink():
    """[[SomeTopic]] alone returns SomeTopic (brackets stripped, inner text retained).

    Non-vacuous: if brackets are kept the result would contain '[' or ']'.
    """
    result = clean_title("[[SomeTopic]]")
    assert "[[" not in result, f"Opening brackets must be stripped, got {result!r}"
    assert "]]" not in result, f"Closing brackets must be stripped, got {result!r}"
    assert "SomeTopic" in result, f"Inner text must survive, got {result!r}"


def test_clean_title_aliased_link_keeps_alias():
    """clean_title strips [[ and ]] from [[target|alias]]; content between brackets survives.

    clean_title's contract: no [[ or ]] remain in the output. It does NOT
    extract the alias — "target|alias" (minus brackets) is passed on as-is
    for the caller (extract_from_title / split_on_delimiters) to process.
    Non-vacuous: without the bracket-strip fix, '[[target' would silently
    enter the topic index.
    """
    result = clean_title("[[target|alias]]")
    assert "[[" not in result, f"Opening brackets must be stripped, got {result!r}"
    assert "]]" not in result, f"Closing brackets must be stripped, got {result!r}"
    # At minimum the content between brackets must survive
    assert len(result.strip()) > 0, f"Result must not be empty, got {result!r}"
