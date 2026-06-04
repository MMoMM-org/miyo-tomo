#!/usr/bin/env python3
# version: 0.1.0
"""test_topic_extract_fields.py — Tests for extract_topics_from_fields() — T1.2 of spec 015 (F-34).

All tests run RED before the implementation is added (CON-1 TDD discipline).
Covers:
  - H1 heading used as title source
  - Filename title fallback when no H1 in headings list
  - Level-2 headings become subtopics; boilerplate skipped
  - ADR-4: kind=='embed' links excluded; kind=='link' included
  - Link target alias/path/anchor stripping
  - Tags: '#' prefix stripped; STRUCTURAL_TAG_PREFIXES dropped
  - Parity with extract_topics() content path on equivalent input
  - Empty fields returns empty topics
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
# T1.2-3: Level-2 headings become subtopics; boilerplate skipped
# ---------------------------------------------------------------------------

def test_level2_headings_become_subtopics_boilerplate_skipped():
    """Level==2 headings produce method-2 topics; boilerplate headings are excluded."""
    result = extract_topics_from_fields(
        title=None,
        headings=[
            {"heading": "Game Theory", "level": 2},
            {"heading": "References", "level": 2},   # boilerplate — must be skipped
            {"heading": "Search Algorithms", "level": 2},
            {"heading": "Notes", "level": 2},         # boilerplate — must be skipped
        ],
        links=[],
        tags=[],
    )
    headings_topics = result["source_methods"]["headings"]
    assert "game theory" in headings_topics, \
        f"Expected 'game theory' in {headings_topics}"
    assert "search algorithms" in headings_topics, \
        f"Expected 'search algorithms' in {headings_topics}"
    assert "references" not in headings_topics, \
        "'references' should be filtered as boilerplate"
    assert "notes" not in headings_topics, \
        "'notes' should be filtered as boilerplate"


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

    for expected in ("search algorithms", "minimax", "nlp", "games"):
        assert expected in fields_topics, \
            f"Expected '{expected}' in fields result {fields_topics}"


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
