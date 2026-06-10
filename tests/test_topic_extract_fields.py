#!/usr/bin/env python3
# version: 0.3.1
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
  - v0.4.0: Method 4 only yields topics for configured topic-prefix tags (topic/)
  - v0.4.0: Method 1 multi-word title segment stays single (no word explosion)
  - v0.4.0: Method 3 date-shaped link targets filtered (YYYY-MM-DD)
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
    """Tags without topic/ prefix are ignored; structural type/ and status/ dropped.

    v0.4.0: only topic/ prefix tags yield topics. Bare tags (#nlp, #games,
    machine-learning) and structural tags are ALL ignored by method 4.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[],
        tags=["#topic/nlp", "#type/x", "#status/active", "#games", "machine-learning"],
    )
    tag_topics = result["source_methods"]["tags"]
    # '#topic/nlp' → leaf 'nlp' must appear
    assert "nlp" in tag_topics, \
        f"Expected 'nlp' (from #topic/nlp) in {tag_topics}"
    # Structural tags must be filtered out entirely — same as before
    assert "type" not in tag_topics, "'type' prefix should be filtered"
    assert "x" not in tag_topics, "Structural tag child 'x' should be filtered"
    assert "status" not in tag_topics, "'status' prefix should be filtered"
    assert "active" not in tag_topics, "Structural tag child 'active' should be filtered"
    # v0.4.0: bare tags without topic/ prefix must also be ignored
    assert "games" not in tag_topics, "bare '#games' must be ignored (no topic/ prefix)"
    assert "machine-learning" not in tag_topics, \
        "bare 'machine-learning' must be ignored (no topic/ prefix)"


# ---------------------------------------------------------------------------
# T1.2-7: Parity with extract_topics() on equivalent input
# ---------------------------------------------------------------------------

def test_parity_with_content_path_on_equivalent_input():
    """extract_topics_from_fields() and extract_topics() yield overlap on title/links signal.

    v0.4.0: Tags in both paths use topic/ prefix so they contribute equally.
    The content path (extract_topics) still uses the old all-tag logic; for
    parity on title+links we use topic/-prefixed tags in both.
    """
    markdown_content = """\
---
tags: [topic/nlp, topic/games]
---

# Alpha Beta Pruning

## Search Algorithms

See also [[Minimax]] and [[Game Theory]].
"""
    content_result = extract_topics(markdown_content)

    # Equivalent structured input
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
        tags=["topic/nlp", "topic/games"],
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


# ---------------------------------------------------------------------------
# v0.4.0 — Method 4: only configured topic-prefix tags
# ---------------------------------------------------------------------------

def test_method4_only_topic_prefix_tags_yield_topics():
    """Only tags under topic/ prefix yield topics; all other tags are ignored.

    Non-vacuous: if the old behaviour (all-tags-minus-structural) were active,
    'lyt', 'games', 'note/code', and 'type/x' would produce topics. This test
    asserts NONE of those non-topic/ tags appear.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[],
        tags=["topic/japan", "note/code", "type/x", "stage/🟢", "lyt", "games"],
    )
    tag_topics = result["source_methods"]["tags"]
    # Matching tag: topic/japan → leaf is 'japan'
    assert "japan" in tag_topics, f"Expected 'japan' from topic/japan, got {tag_topics}"
    # Non-topic-prefix tags must all be silently ignored
    assert "note" not in tag_topics, "'note' is a non-topic prefix — must be ignored"
    assert "code" not in tag_topics, "leaf of note/code must be ignored"
    assert "type" not in tag_topics, "type/ is structural — must be ignored"
    assert "x" not in tag_topics, "leaf of type/x must be ignored"
    assert "stage" not in tag_topics, "stage/ is non-topic prefix — must be ignored"
    assert "lyt" not in tag_topics, "bare 'lyt' tag must be ignored (no topic/ prefix)"
    assert "games" not in tag_topics, "bare 'games' tag must be ignored (no topic/ prefix)"


def test_method4_hierarchical_topic_tag_yields_leaf():
    """topic/applied/shell → leaf segment 'shell' (not 'applied' or 'topic').

    Non-vacuous: if the old split-all-segments logic were active, both 'shell'
    AND 'applied' would appear. This asserts only the leaf 'shell' appears.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[],
        tags=["topic/applied/shell"],
    )
    tag_topics = result["source_methods"]["tags"]
    assert "shell" in tag_topics, f"Expected leaf 'shell' from topic/applied/shell, got {tag_topics}"
    # Only the leaf after the matched prefix — 'applied' is a path segment within the
    # topic hierarchy, not a separate topic leaf.
    assert "applied" not in tag_topics, \
        "Only the leaf segment after the matched prefix must be emitted, not intermediate segments"
    assert "topic" not in tag_topics, "Prefix itself must not appear as a topic"


def test_method4_hash_prefix_stripped_then_topic_prefix_checked():
    """#topic/japan (with leading #) must still be recognized as a topic/ tag.

    Non-vacuous: if the # is not stripped before prefix matching, the tag
    '#topic/japan' would NOT match prefix 'topic/' and would be silently ignored.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[],
        tags=["#topic/japan", "#lyt", "#games"],
    )
    tag_topics = result["source_methods"]["tags"]
    assert "japan" in tag_topics, \
        f"#topic/japan must yield 'japan' after # stripping + prefix match, got {tag_topics}"
    assert "lyt" not in tag_topics, "bare #lyt must be ignored"
    assert "games" not in tag_topics, "bare #games must be ignored"


def test_method4_custom_prefix_list_respected():
    """A custom topic_tag_prefixes list picks up matching tags and ignores topic/.

    Non-vacuous: if the prefix list were ignored (hardcoded to ['topic/']), then
    'theme/gaming' would be silently dropped and 'topic/japan' would appear — the
    opposite of what this test asserts.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[],
        tags=["theme/gaming", "topic/japan", "lyt"],
        topic_tag_prefixes=["theme/"],
    )
    tag_topics = result["source_methods"]["tags"]
    # theme/gaming → leaf 'gaming' must appear
    assert "gaming" in tag_topics, \
        f"Expected 'gaming' from theme/gaming with custom prefix, got {tag_topics}"
    # topic/japan must NOT appear — 'topic/' is not in the custom prefix list
    assert "japan" not in tag_topics, \
        "topic/japan must be ignored when prefix list is ['theme/'] (not 'topic/')"
    # bare 'lyt' must be ignored
    assert "lyt" not in tag_topics, "bare 'lyt' must be ignored"


def test_method4_default_none_behaves_as_topic_prefix():
    """Default topic_tag_prefixes=None must behave identically to ['topic/'].

    Non-vacuous: if None caused all-tags-pass (old behaviour) instead of
    defaulting to ['topic/'], then 'games' would appear. It must not.
    """
    result_default = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[],
        tags=["topic/japan", "games"],
        # topic_tag_prefixes not passed — must default to ["topic/"]
    )
    result_explicit = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[],
        tags=["topic/japan", "games"],
        topic_tag_prefixes=["topic/"],
    )
    assert result_default["source_methods"]["tags"] == result_explicit["source_methods"]["tags"], (
        f"Default None must equal explicit ['topic/']. "
        f"default={result_default['source_methods']['tags']!r}, "
        f"explicit={result_explicit['source_methods']['tags']!r}"
    )
    assert "japan" in result_default["source_methods"]["tags"], "topic/japan must yield 'japan'"
    assert "games" not in result_default["source_methods"]["tags"], "bare 'games' must be ignored"


# ---------------------------------------------------------------------------
# v0.4.0 — Method 1: no single-word explosion from multi-word title segments
# ---------------------------------------------------------------------------

def test_method1_multiword_title_segment_stays_single():
    """A multi-word title segment produces ONE topic, not individual words.

    Non-vacuous: if the old word-explosion code were still active, 'Personal Need'
    would produce BOTH 'personal need' AND 'personal' AND 'need' as separate topics.
    After the fix, only 'personal need' must appear — 'personal' and 'need' alone
    must NOT appear as standalone topics from method 1.
    """
    result = extract_topics_from_fields(
        title="Personal Need",
        headings=[],
        links=[],
        tags=[],
    )
    title_topics = result["source_methods"]["title"]
    assert "personal need" in title_topics, \
        f"Expected 'personal need' as a single topic, got {title_topics}"
    # Non-vacuous: these would appear if the explosion were still active
    assert "personal" not in title_topics, \
        "Word explosion must be removed: 'personal' must not appear as standalone topic"
    assert "need" not in title_topics, \
        "Word explosion must be removed: 'need' must not appear as standalone topic"


def test_method1_single_word_title_still_works():
    """A single-word title segment still produces a topic (no regression).

    Non-vacuous: if method 1 were completely broken by the change, no topic
    at all would be produced — the assert on non-empty title_topics would fail.
    """
    result = extract_topics_from_fields(
        title="Japan",
        headings=[],
        links=[],
        tags=[],
    )
    title_topics = result["source_methods"]["title"]
    assert "japan" in title_topics, f"Single-word title 'japan' must still produce a topic, got {title_topics}"


def test_method1_delimiter_split_still_produces_separate_topics():
    """Title split on ' - ' produces one topic per segment (delimiter split unchanged).

    Non-vacuous: if the delimiter split were broken, only one topic would be
    produced instead of two.
    """
    result = extract_topics_from_fields(
        title="Shell Scripting - Tips and Tricks",
        headings=[],
        links=[],
        tags=[],
    )
    title_topics = result["source_methods"]["title"]
    # Each delimiter-split segment must produce exactly one topic
    assert "shell scripting" in title_topics, \
        f"Expected 'shell scripting' (left of ' - '), got {title_topics}"
    assert "tips and tricks" in title_topics, \
        f"Expected 'tips and tricks' (right of ' - '), got {title_topics}"
    # Word explosion must not have fired on either segment
    assert "shell" not in title_topics, \
        "Word explosion must not fire: 'shell' alone must not be a separate topic"
    assert "tips" not in title_topics, \
        "Word explosion must not fire: 'tips' alone must not be a separate topic"


# ---------------------------------------------------------------------------
# v0.4.0 — Method 3: date-shaped link targets filtered
# ---------------------------------------------------------------------------

def test_method3_date_shaped_link_target_filtered():
    """Link targets matching YYYY-MM-DD (daily-note links) must be dropped.

    Non-vacuous: without the filter, '2026-05-01' would appear verbatim as a
    topic — the assert 'not in link_topics' would fail.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[
            {"target": "2026-05-01", "kind": "link"},    # daily-note → must be dropped
            {"target": "Minimax Algorithm", "kind": "link"},  # real topic → must survive
        ],
        tags=[],
    )
    link_topics = result["source_methods"]["links"]
    assert "2026-05-01" not in link_topics, \
        "Date-shaped link target '2026-05-01' must be filtered out"
    assert "minimax algorithm" in link_topics, \
        f"Normal link target must survive date filter, got {link_topics}"


def test_method3_date_shaped_target_in_path_is_filtered():
    """A link whose path component resolves to a date must also be filtered.

    Example: 'Calendar/Days/2026-05-01' strips to '2026-05-01' → drop.
    Non-vacuous: without the filter the date would appear in link_topics.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[
            {"target": "Calendar/Days/2026-05-01", "kind": "link"},
            {"target": "Atlas/202 Notes/Japan Trip", "kind": "link"},
        ],
        tags=[],
    )
    link_topics = result["source_methods"]["links"]
    assert "2026-05-01" not in link_topics, \
        "Date-shaped stem after path-stripping must be filtered"
    assert "japan trip" in link_topics, \
        f"Non-date link target 'japan trip' must survive, got {link_topics}"


def test_method3_non_date_numeric_targets_not_filtered():
    """Numeric targets that are NOT in YYYY-MM-DD format must not be filtered.

    Non-vacuous: an over-eager filter (e.g. \\d+) would drop these legitimate
    note names, causing them to disappear from link_topics.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[],
        links=[
            {"target": "2026", "kind": "link"},          # year only — not a date
            {"target": "2026-05", "kind": "link"},        # year-month — not a date
            {"target": "Note 42", "kind": "link"},        # note name with digits
        ],
        tags=[],
    )
    link_topics = result["source_methods"]["links"]
    assert "2026" in link_topics, "Year-only target must not be filtered"
    assert "2026-05" in link_topics, "Year-month target must not be filtered"
    assert "note 42" in link_topics, "Numeric note name must not be filtered"


# ---------------------------------------------------------------------------
# Malformed-shape contract (defends the .get() handling of Kado field dicts)
# ---------------------------------------------------------------------------

def test_malformed_field_dicts_do_not_crash():
    """Heading/link dicts missing level/kind/target are tolerated, not KeyError.

    extract_topics_from_fields consumes Kado listNotes output (an external
    producer contract). This pins the defensive .get() behaviour so a future
    refactor to [] indexing would fail here rather than in production.
    """
    result = extract_topics_from_fields(
        title=None,
        headings=[
            {"heading": "No Level Here"},   # missing 'level' → not treated as H1
            {"level": 1},                    # missing 'heading' → empty H1 text
        ],
        links=[
            {"target": "Some Note"},         # missing 'kind' → not kind=='link'
            {"kind": "link"},                # missing 'target' → no topic
        ],
        tags=["topic/"],                     # empty leaf after prefix
    )
    # Contract: returns the normal shape, no exception, no spurious topics.
    assert set(result.keys()) >= {"topics", "source_methods"}
    assert isinstance(result["topics"], list)
    assert "no level here" not in result["topics"]   # non-H1 heading ignored
    assert "some note" not in result["source_methods"].get("links", [])  # missing kind
