#!/usr/bin/env python3
# version: 0.1.0
"""test_suggestions_reducer_multi_atomic.py — F-41 T3.1.

Covers the two silent-collapse fixes in suggestions-reducer.py that let N
atomic notes from a single source coexist (C1) and keep distinct titles (C2):

  C1 — _enforce_coexistence partitions atomics by worthiness/force_atomic:
        survivors (>=0.5 or force_atomic) are kept, sub-worthy are dropped
        individually, and the daily log_entry converts to a log_link only
        when at least one survivor remains.
  C2 — per-atomic keying so N atomics in one section keep distinct titles
        through build_topic_clusters → _enrich_proposed_mocs, while the
        single-thread case stays byte-identical (CON-2).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "suggestions-reducer.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load suggestions-reducer.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("suggestions_reducer", SCRIPT_PATH)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["suggestions_reducer"] = _mod
_spec.loader.exec_module(_mod)

_enforce_coexistence = _mod._enforce_coexistence  # type: ignore[attr-defined]
_enrich_proposed_mocs = _mod._enrich_proposed_mocs  # type: ignore[attr-defined]
_atomic_id = _mod._atomic_id  # type: ignore[attr-defined]
build_topic_clusters = _mod.build_topic_clusters  # type: ignore[attr-defined]
ClusterCandidate = _mod.ClusterCandidate  # type: ignore[attr-defined]


# ── Factories ────────────────────────────────────────────────────────────────


def make_atomic(
    *,
    title: str,
    worthiness: float,
    stem: str = "src-note",
    force_atomic: bool | None = None,
    needs_new_moc: bool = False,
    topic: str = "",
    tags: list[str] | None = None,
) -> dict:
    a: dict = {
        "kind": "create_atomic_note",
        "suggested_title": title,
        "atomic_note_worthiness": worthiness,
        "stem": stem,
    }
    if force_atomic is not None:
        a["force_atomic"] = force_atomic
    if needs_new_moc:
        a["needs_new_moc"] = True
        a["proposed_moc_topic"] = topic
        a["classification"] = {"category": "100 Philosophy"}
        a["tags_to_add"] = tags or []
    return a


def make_update_daily(
    *,
    content: str = "did a thing",
    time: str = "09:00",
) -> dict:
    return {
        "kind": "update_daily",
        "daily_note_path": "Daily/2026-06-11.md",
        "updates": [
            {
                "kind": "log_entry",
                "time": time,
                "time_source": "frontmatter",
                "position": "append",
                "content": content,
                "reason": "logged",
            }
        ],
    }


def _log_links(actions: list[dict]) -> list[dict]:
    out: list[dict] = []
    for a in actions:
        if a.get("kind") != "update_daily":
            continue
        for u in a.get("updates") or []:
            if u.get("kind") == "log_link":
                out.append(u)
    return out


def _log_entries(actions: list[dict]) -> list[dict]:
    out: list[dict] = []
    for a in actions:
        if a.get("kind") != "update_daily":
            continue
        for u in a.get("updates") or []:
            if u.get("kind") == "log_entry":
                out.append(u)
    return out


def _atomics(actions: list[dict]) -> list[dict]:
    return [a for a in actions if a.get("kind") == "create_atomic_note"]


# ── C1 — _enforce_coexistence ────────────────────────────────────────────────


def test_two_survivors_both_kept_log_converted():
    """Test 1: 2 atomics (0.7, 0.6) + daily log_entry → both kept, log→link."""
    actions = [
        make_atomic(title="Alpha", worthiness=0.7),
        make_atomic(title="Beta", worthiness=0.6),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)

    kept = _atomics(out)
    assert {a["suggested_title"] for a in kept} == {"Alpha", "Beta"}

    links = _log_links(out)
    assert len(links) == 1
    assert links[0]["target_stem"] == "Alpha"  # first survivor's title
    assert _log_entries(out) == []


def test_mixed_worthiness_drops_subworthy_keeps_survivor():
    """Test 2: atomic 0.7 + atomic 0.3 + log_entry → 0.7 kept, 0.3 dropped."""
    actions = [
        make_atomic(title="Keep", worthiness=0.7),
        make_atomic(title="Drop", worthiness=0.3),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)

    kept = _atomics(out)
    assert [a["suggested_title"] for a in kept] == ["Keep"]

    links = _log_links(out)
    assert len(links) == 1
    assert links[0]["target_stem"] == "Keep"
    assert _log_entries(out) == []


def test_all_subworthy_drops_atomics_keeps_log_entry():
    """Test 3: atomic 0.3 + atomic 0.4 + log_entry → both dropped, log kept."""
    actions = [
        make_atomic(title="A", worthiness=0.3),
        make_atomic(title="B", worthiness=0.4),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)

    assert _atomics(out) == []
    assert _log_links(out) == []
    entries = _log_entries(out)
    assert len(entries) == 1
    assert entries[0]["content"] == "did a thing"


def test_force_atomic_survivor_overrides_subworthiness():
    """force_atomic truthy keeps a sub-worthy atomic as a survivor."""
    actions = [
        make_atomic(title="Forced", worthiness=0.2, force_atomic=True),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)

    kept = _atomics(out)
    assert [a["suggested_title"] for a in kept] == ["Forced"]
    links = _log_links(out)
    assert len(links) == 1
    assert links[0]["target_stem"] == "Forced"


# ── C1 — CON-2 single-thread regression ──────────────────────────────────────


def test_single_thread_coexistence_byte_identical():
    """Test 5a: 1 atomic + log_entry → exact legacy log_link shape (CON-2)."""
    actions = [
        make_atomic(title="Solo", worthiness=0.8, stem="src"),
        make_update_daily(time="07:30"),
    ]
    out = _enforce_coexistence(actions)

    assert [a["suggested_title"] for a in _atomics(out)] == ["Solo"]
    links = _log_links(out)
    assert links == [
        {
            "kind": "log_link",
            "target_stem": "Solo",
            "time": "07:30",
            "time_source": "frontmatter",
            "position": "append",
            "reason": "logged",
        }
    ]


def test_single_subworthy_atomic_dropped_log_kept():
    """Single sub-worthy atomic + log_entry → atomic dropped, log kept (legacy)."""
    actions = [
        make_atomic(title="Weak", worthiness=0.3),
        make_update_daily(),
    ]
    out = _enforce_coexistence(actions)
    assert _atomics(out) == []
    assert len(_log_entries(out)) == 1
    assert _log_links(out) == []


def test_no_log_entry_returns_actions_unchanged():
    """Early return: atomic present but no log_entry → actions untouched."""
    actions = [make_atomic(title="X", worthiness=0.9)]
    out = _enforce_coexistence(actions)
    assert out == actions


# ── C2 — per-atomic titles survive into proposed-MOC note_titles ──────────────


def _build_clusters_like_loop(atomics_per_section: dict[str, list[dict]]):
    """Mirror the reducer action-loop's keying of cluster_candidates and
    section_titles, then run the same post-processing the reducer runs.

    atomics_per_section maps section_id (e.g. "S01") → ordered list of atomic
    action dicts (each carrying needs_new_moc/proposed_moc_topic/tags).
    Returns the enriched proposed_mocs list.
    """
    cluster_candidates = []
    section_titles: dict[str, str] = {}
    for section_id, atomics in atomics_per_section.items():
        atomic_idx = 0
        for action in atomics:
            stem = action.get("stem", "")
            # Key exactly as the reducer loop does (production helper).
            atomic_id = _atomic_id(section_id, atomic_idx)
            if action.get("needs_new_moc"):
                topic_raw = (action.get("proposed_moc_topic") or "").strip()
                if topic_raw:
                    cls = action.get("classification") or {}
                    parent = cls.get("category") or ""
                    item_tags = [t for t in (action.get("tags_to_add") or []) if t]
                    cluster_candidates.append(
                        ClusterCandidate(
                            section_id=atomic_id,
                            topic=topic_raw,
                            parent=parent,
                            tags=item_tags,
                        )
                    )
            title = (action.get("suggested_title") or "").strip() or stem
            section_titles[atomic_id] = title
            atomic_idx += 1

    proposed_mocs = list(build_topic_clusters(cluster_candidates, threshold=1))
    _enrich_proposed_mocs(proposed_mocs, section_titles)
    return proposed_mocs


def test_two_atomics_same_section_distinct_titles_survive():
    """Test 4: two distinct-topic needs_new_moc atomics in ONE source → both
    titles survive into their proposed-MOC note_titles (no overwrite)."""
    atomics = [
        make_atomic(
            title="Stoicism Note", worthiness=0.8, needs_new_moc=True,
            topic="Stoicism", tags=["#philosophy"],
        ),
        make_atomic(
            title="Epicureanism Note", worthiness=0.8, needs_new_moc=True,
            topic="Epicureanism", tags=["#philosophy"],
        ),
    ]
    proposed = _build_clusters_like_loop({"S01": atomics})

    titles_by_topic = {pm["topic"]: pm["note_titles"] for pm in proposed}
    assert titles_by_topic["Stoicism"] == ["Stoicism Note"]
    assert titles_by_topic["Epicureanism"] == ["Epicureanism Note"]


def test_single_atomic_proposed_moc_byte_identical_keying():
    """Test 5b: single atomic → note_titles resolves via the bare S01 key,
    byte-identical to legacy single-thread behaviour (CON-2)."""
    atomics = [
        make_atomic(
            title="Lone Topic Note", worthiness=0.8, needs_new_moc=True,
            topic="Lone Topic", tags=["#x"],
        ),
    ]
    proposed = _build_clusters_like_loop({"S01": atomics})
    assert len(proposed) == 1
    assert proposed[0]["topic"] == "Lone Topic"
    assert proposed[0]["note_titles"] == ["Lone Topic Note"]
    # The cluster item key must be the bare section id for single-thread.
    assert proposed[0]["items"] == ["S01"]
