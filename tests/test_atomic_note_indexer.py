#!/usr/bin/env python3
# version: 0.1.0
"""test_atomic_note_indexer.py — Tests for atomic-note-indexer.py — T2.1 of spec 015 (F-34).

RED before GREEN discipline (CON-1/TDD).

Primary fixture: SDD §Complex Logic traced walkthrough, 4 notes, M=3:
  stem                    topics                    up:: ?
  monte-carlo-tree-search [mcts, search, games]     no
  alpha-beta-pruning      [search, games]            no
  board-game-night        [games, social]            yes
  minimax                 [search, games]            no

Expected result:
  {
    "games":  ["alpha-beta-pruning", "minimax", "monte-carlo-tree-search"],
    "search": ["alpha-beta-pruning", "minimax", "monte-carlo-tree-search"],
  }
(board-game-night classified; mcts/social groups below M=3 raw size, never read)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, call

SCRIPTS_DIR = Path(__file__).parent.parent / "tomo" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# atomic-note-indexer.py has a hyphen — load via importlib
_spec = importlib.util.spec_from_file_location(
    "atomic_note_indexer", SCRIPTS_DIR / "atomic-note-indexer.py"
)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

build_accumulation_clusters = _mod.build_accumulation_clusters  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — build fake KadoClient and note fixtures
# ---------------------------------------------------------------------------

def _note(path: str, topics_for_fields: list[str]) -> dict:
    """Build a minimal listNotes item with pre-computed topics embedded as test hints.

    The real indexer calls extract_topics_from_fields(headings, links, tags) per note.
    To keep tests deterministic without re-testing topic extraction, we embed each
    topic as a plain tag (no '#' prefix, no structural prefix) — extract_topics_from_fields
    will surface them via method 4.
    """
    return {
        "path": path,
        "name": Path(path).name,
        "tags": topics_for_fields,   # surfaces via extract_topics_from_fields method 4
        "headings": [],
        "links": [],
    }


def _make_client(
    notes: list[dict],
    classified_stems: set[str],
    *,
    marker: str = "up",
) -> MagicMock:
    """Return a fake KadoClient.

    list_notes() → notes list (single page).
    read_inline_fields(path) → {marker: ["[[MOC]]"]} for classified stems,
                                {}                     for unclassified stems.
    """
    client = MagicMock()
    client.list_notes.return_value = notes

    def _read_inline(path: str) -> dict:
        stem = Path(path).stem
        if stem in classified_stems:
            return {marker: ["[[Hobbies MOC]]"]}
        return {}

    client.read_inline_fields.side_effect = _read_inline
    return client


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BASE_PATH = "Atlas/Atoms"

WALKTHROUGH_NOTES = [
    _note(f"{BASE_PATH}/monte-carlo-tree-search.md", ["mcts", "search", "games"]),
    _note(f"{BASE_PATH}/alpha-beta-pruning.md",      ["search", "games"]),
    _note(f"{BASE_PATH}/board-game-night.md",        ["games", "social"]),
    _note(f"{BASE_PATH}/minimax.md",                 ["search", "games"]),
]

WALKTHROUGH_CLASSIFIED = {"board-game-night"}

EXPECTED_RESULT = {
    "games":  ["alpha-beta-pruning", "minimax", "monte-carlo-tree-search"],
    "search": ["alpha-beta-pruning", "minimax", "monte-carlo-tree-search"],
}


# ---------------------------------------------------------------------------
# T2.1-1: Cluster emitted when min unclassified members met
# ---------------------------------------------------------------------------

def test_cluster_emitted_when_min_unclassified_members():
    """Full walkthrough: both 'games' and 'search' clusters emitted with 3 unclassified stems."""
    client = _make_client(WALKTHROUGH_NOTES, WALKTHROUGH_CLASSIFIED)
    result = build_accumulation_clusters(client, BASE_PATH, min_cluster_size=3)
    assert result == EXPECTED_RESULT, f"Expected {EXPECTED_RESULT}, got {result}"


# ---------------------------------------------------------------------------
# T2.1-2: Classified note excluded via up:: marker
# ---------------------------------------------------------------------------

def test_classified_note_excluded_via_up_marker():
    """board-game-night has up:: → excluded; 'games' group shrinks to 3 unclassified."""
    client = _make_client(WALKTHROUGH_NOTES, WALKTHROUGH_CLASSIFIED)
    result = build_accumulation_clusters(client, BASE_PATH, min_cluster_size=3)

    # board-game-night must not appear in any cluster
    for topic, stems in result.items():
        assert "board-game-night" not in stems, \
            f"Classified stem appeared in topic '{topic}': {stems}"

    # games cluster must still have the 3 unclassified stems
    assert "games" in result
    assert sorted(result["games"]) == sorted(EXPECTED_RESULT["games"])


# ---------------------------------------------------------------------------
# T2.1-3: Group below min never read for up:: (cost bound)
# ---------------------------------------------------------------------------

def test_group_below_min_never_read_for_up():
    """A note belonging ONLY to a sub-threshold group must never trigger an up:: read."""
    # Add a 5th note whose sole topic is "social" — keeping "social" at raw size 2
    # (board-game-night + social-gathering), still below M=3.
    # social-gathering ONLY participates in the sub-threshold "social" group, so
    # read_inline_fields must never be called for it.
    notes_with_sub_threshold = WALKTHROUGH_NOTES + [
        _note(f"{BASE_PATH}/social-gathering.md", ["social"]),
    ]
    client = _make_client(notes_with_sub_threshold, WALKTHROUGH_CLASSIFIED)
    build_accumulation_clusters(client, BASE_PATH, min_cluster_size=3)

    social_gathering_path = f"{BASE_PATH}/social-gathering.md"
    called_paths = {c.args[0] for c in client.read_inline_fields.call_args_list}

    assert social_gathering_path not in called_paths, (
        f"social-gathering.md is only in sub-threshold 'social' group "
        f"but was read for up:: — cost bound violated. Called: {called_paths}"
    )


# ---------------------------------------------------------------------------
# T2.1-4: up:: read deduped across overlapping groups
# ---------------------------------------------------------------------------

def test_up_read_dedup_across_overlapping_groups():
    """Each stem is read for up:: at most once, even if it appears in multiple candidate groups."""
    client = _make_client(WALKTHROUGH_NOTES, WALKTHROUGH_CLASSIFIED)
    build_accumulation_clusters(client, BASE_PATH, min_cluster_size=3)

    # All 4 stems appear in both 'games' and 'search' candidate groups —
    # each should be read exactly once.
    path_call_counts: dict[str, int] = {}
    for c in client.read_inline_fields.call_args_list:
        p = c.args[0]
        path_call_counts[p] = path_call_counts.get(p, 0) + 1

    duplicates = {p: n for p, n in path_call_counts.items() if n > 1}
    assert not duplicates, f"Stems read more than once: {duplicates}"


# ---------------------------------------------------------------------------
# T2.1-5: min_cluster_size defaults to 3
# ---------------------------------------------------------------------------

def test_min_cluster_size_config_default_3():
    """Default M=3: groups with exactly 3 unclassified members are emitted."""
    client = _make_client(WALKTHROUGH_NOTES, WALKTHROUGH_CLASSIFIED)
    # Omit min_cluster_size — implementation reads from config or uses default 3
    result = build_accumulation_clusters(client, BASE_PATH)
    # Both groups have exactly 3 unclassified → must appear
    assert "games" in result
    assert "search" in result


# ---------------------------------------------------------------------------
# T2.1-6: min_cluster_size config override
# ---------------------------------------------------------------------------

def test_min_cluster_size_config_override():
    """M=4: no group reaches 4 unclassified members → empty result."""
    client = _make_client(WALKTHROUGH_NOTES, WALKTHROUGH_CLASSIFIED)
    result = build_accumulation_clusters(client, BASE_PATH, min_cluster_size=4)
    assert result == {}, f"Expected empty dict at M=4, got {result}"


# ---------------------------------------------------------------------------
# T2.1-7: inline field read error treats note as classified (conservative)
# ---------------------------------------------------------------------------

def test_inline_field_read_error_treats_note_classified():
    """read_inline_fields raising Exception → that note treated as classified (dropped)."""
    # minimax raises on read — removes it from both groups, dropping them below M=3
    erroring_stems = {"minimax"}
    client = MagicMock()
    client.list_notes.return_value = WALKTHROUGH_NOTES

    def _read_inline_with_error(path: str) -> dict:
        stem = Path(path).stem
        if stem in erroring_stems:
            raise Exception("kado read error")
        if stem in WALKTHROUGH_CLASSIFIED:
            return {"up": ["[[MOC]]"]}
        return {}

    client.read_inline_fields.side_effect = _read_inline_with_error

    result = build_accumulation_clusters(client, BASE_PATH, min_cluster_size=3)

    # minimax + board-game-night both gone → groups have only 2 unclassified → no clusters
    assert result == {}, \
        f"Expected empty (minimax errors → classified), got {result}"


# ---------------------------------------------------------------------------
# T2.1-7b: Custom parent marker honoured (relationships.parent.marker config)
# ---------------------------------------------------------------------------

def test_custom_marker_honoured():
    """When parent_marker='parent', notes with parent:: are classified; up:: is ignored."""
    # board-game-night has "parent" key → classified
    # alpha-beta-pruning has only "up" key → unclassified (marker is "parent", not "up")
    custom_classified = {"board-game-night"}
    client = _make_client(WALKTHROUGH_NOTES, custom_classified, marker="parent")

    result = build_accumulation_clusters(
        client, BASE_PATH, min_cluster_size=3, parent_marker="parent"
    )

    # With marker="parent":
    # board-game-night classified (has "parent" key); others unclassified.
    # 'games' keeps 3 unclassified stems; 'search' keeps 3.
    assert "games" in result, f"Expected 'games' cluster, got {result}"
    assert "board-game-night" not in result.get("games", []), \
        "Classified note (parent:: set) must be excluded"

    # Now verify up:: alone does NOT classify when marker is "parent".
    # Make a fresh set where alpha-beta-pruning has "up" (wrong marker) but NOT "parent".
    # That note should remain unclassified under marker="parent".
    client2 = MagicMock()
    client2.list_notes.return_value = WALKTHROUGH_NOTES

    def _read_with_up_only(path: str) -> dict:
        if Path(path).stem == "alpha-beta-pruning":
            return {"up": ["[[Some MOC]]"]}  # up:: present but marker is "parent"
        if Path(path).stem == "board-game-night":
            return {"parent": ["[[Hobbies MOC]]"]}  # correct marker → classified
        return {}

    client2.read_inline_fields.side_effect = _read_with_up_only
    result2 = build_accumulation_clusters(
        client2, BASE_PATH, min_cluster_size=3, parent_marker="parent"
    )

    # alpha-beta-pruning has "up" but not "parent" → unclassified → still in clusters
    assert "alpha-beta-pruning" in result2.get("search", []), \
        "Note with up:: (wrong marker) must NOT be classified when marker='parent'"


# ---------------------------------------------------------------------------
# T2.1-8: Empty vault emits empty dict (A6)
# ---------------------------------------------------------------------------

def test_empty_vault_emits_empty_dict():
    """Zero notes → empty cluster dict; no reads attempted."""
    client = MagicMock()
    client.list_notes.return_value = []

    result = build_accumulation_clusters(client, BASE_PATH, min_cluster_size=3)

    assert result == {}, f"Expected {{}}, got {result}"
    client.read_inline_fields.assert_not_called()


# ---------------------------------------------------------------------------
# T2.1-9: Kado unreachable emits empty dict and logs to stderr
# ---------------------------------------------------------------------------

def test_kado_unreachable_emits_empty_dict_and_nonzero_log(capsys):
    """list_notes raising Exception → emit {}, log error to stderr."""
    client = MagicMock()
    client.list_notes.side_effect = Exception("connection refused")

    result = build_accumulation_clusters(client, BASE_PATH, min_cluster_size=3)

    assert result == {}, f"Expected {{}}, got {result}"

    captured = capsys.readouterr()
    assert captured.out == "", "stdout must be empty (JSON-only stdout rule)"
    assert "connection refused" in captured.err or len(captured.err) > 0, \
        "Expected error message on stderr"
