#!/usr/bin/env python3
# version: 0.2.0
"""test_moc_discovery_scan_orphans.py — T5.1 scan-mode orphan sourcing from cache.

spec 021, Phase 5: scan mode must source candidates from cache entries with
kind=="note" AND up_state=="absent" (orphans), not from live list_dir calls.
Scoped modes (folder/tag/class/title) remain unchanged — no orphan filter.
_build_topics_index must resolve kind==note paths (was miss before T5.1).
candidate_cap default raised to 500.

ADR-11: The scan mode abort (candidate-cap-exceeded) was caused by counting
EVERY atomic note (incl. already-MOC-linked) toward a 200 cap. Fix: scan
sources only orphans from the cache; cap raised to 500.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
PROFILES_DIR = REPO_ROOT / "tomo" / "profiles"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.moc_tags import EXCLUDE_NOTE_TAG  # noqa: E402

# Load moc-discovery.py as a module (hyphen in name → importlib).
_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules.setdefault("moc_discovery", moc_discovery)
_spec.loader.exec_module(moc_discovery)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _load_miyo_profile() -> dict:
    with (PROFILES_DIR / "miyo.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture
def miyo_profile() -> dict:
    return _load_miyo_profile()


class SpyKadoClient:
    """Recording stub — tracks list_dir calls so tests can assert zero were made."""

    def __init__(self):
        self.list_dir_calls: list[str] = []
        self.search_by_tag_calls: list[str] = []
        self._listdir_responses: dict[str, list[dict]] = {}

    def set_listdir_response(self, path: str, items: list[dict]) -> None:
        self._listdir_responses[path] = items

    def list_dir(self, path: str = "/", *, depth: int = None, limit: int = 500) -> list:
        self.list_dir_calls.append(path)
        return list(self._listdir_responses.get(path, []))

    def search_by_tag(self, tag: str, limit: int = 500) -> list:
        self.search_by_tag_calls.append(tag)
        return []


def _make_cache(entries: list[dict]) -> dict:
    """Build a cache dict with entries + map_notes shim (kind==moc entries)."""
    map_notes = [e for e in entries if e.get("kind") == "moc"]
    return {"entries": entries, "map_notes": map_notes}


def _orphan_entry(path: str, topics: list[str] | None = None) -> dict:
    """A kind==note, up_state==absent cache entry."""
    stem = path.rsplit("/", 1)[-1].removesuffix(".md")
    return {
        "kind": "note",
        "path": path,
        "stem": stem,
        "title": stem,
        "topics": topics or [],
        "up_state": "absent",
        "up_target": None,
        "up_source": None,
        "tags": [],
    }


def _valid_note_entry(path: str) -> dict:
    """A kind==note, up_state==valid cache entry (already has a parent)."""
    stem = path.rsplit("/", 1)[-1].removesuffix(".md")
    return {
        "kind": "note",
        "path": path,
        "stem": stem,
        "title": stem,
        "topics": ["existing-topic"],
        "up_state": "valid",
        "up_target": "Atlas/200 Maps/some-moc.md",
        "up_source": "frontmatter",
        "tags": [],
    }


def _broken_note_entry(path: str) -> dict:
    """A kind==note, up_state==broken cache entry (up:: points to non-existent target)."""
    stem = path.rsplit("/", 1)[-1].removesuffix(".md")
    return {
        "kind": "note",
        "path": path,
        "stem": stem,
        "title": stem,
        "topics": [],
        "up_state": "broken",
        "up_target": "Atlas/200 Maps/gone-moc.md",
        "up_source": "frontmatter",
        "tags": [],
    }


def _moc_entry(path: str) -> dict:
    """A kind==moc cache entry."""
    stem = path.rsplit("/", 1)[-1].removesuffix(".md")
    return {
        "kind": "moc",
        "path": path,
        "stem": stem,
        "title": stem,
        "topics": ["moc-topic"],
        "up_state": "valid",
        "up_target": None,
        "up_source": None,
        "tags": ["type/others/moc"],
    }


# ── T5.1 Case 1: scan candidates == orphans (kind==note, up_state==absent) ──


def test_scan_mode_candidates_are_cache_orphans_only(miyo_profile):
    """scan mode: only kind==note + up_state==absent entries become candidates.

    A valid note (up_state==valid) and a broken note (up_state==broken) in the
    cache are excluded. Only the absent-state orphans are returned.
    """
    orphan_path = "Atlas/202 Notes/2611 Code Snippets/orphan.md"
    valid_path = "Atlas/202 Notes/2611 Code Snippets/already-linked.md"
    broken_path = "Atlas/202 Notes/2611 Code Snippets/broken-up.md"

    cache = _make_cache([
        _orphan_entry(orphan_path, topics=["python", "scripting"]),
        _valid_note_entry(valid_path),
        _broken_note_entry(broken_path),
        _moc_entry("Atlas/200 Maps/some-moc.md"),
    ])

    class _Cfg:
        candidate_cap = 500

    spy = SpyKadoClient()
    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="scan",
        trigger_arg="",
        profile=miyo_profile,
        cache=cache,
        kado_client=spy,
        config=_Cfg(),
    )

    assert abort is None
    paths = {c.path for c in candidates}
    assert orphan_path in paths, "orphan (up_state==absent) must be a candidate"
    assert valid_path not in paths, "valid note (up_state==valid) must be excluded"
    assert broken_path not in paths, "broken note (up_state==broken) must be excluded"


# ── T5.1 Case 2: scan mode performs ZERO live list_dir calls ────────────────


def test_scan_mode_zero_list_dir_calls(miyo_profile):
    """scan mode must NOT call kado_client.list_dir at all.

    All candidates are sourced from cache entries — the live list_dir enumeration
    of atomic-note subdirectories is skipped entirely (ADR-11).
    """
    cache = _make_cache([
        _orphan_entry("Atlas/202 Notes/2611 Code Snippets/note1.md"),
        _orphan_entry("Atlas/202 Notes/2611 Code Snippets/note2.md"),
    ])

    class _Cfg:
        candidate_cap = 500

    spy = SpyKadoClient()
    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="scan",
        trigger_arg="",
        profile=miyo_profile,
        cache=cache,
        kado_client=spy,
        config=_Cfg(),
    )

    assert abort is None
    assert spy.list_dir_calls == [], (
        f"scan mode must not call list_dir; called with: {spy.list_dir_calls}"
    )


# ── T5.1 Case 3: scan candidates carry topics from cache entry ───────────────


def test_scan_candidates_carry_topics_from_cache(miyo_profile):
    """Candidates produced by scan mode must carry topics from their cache entry.

    _candidate_from_path produces empty topics; the new scan handler must
    copy topics from the cache entry onto each Candidate.
    """
    cache = _make_cache([
        _orphan_entry(
            "Atlas/202 Notes/2611 Code Snippets/python-typing.md",
            topics=["python", "type-hints", "mypy"],
        ),
    ])

    class _Cfg:
        candidate_cap = 500

    spy = SpyKadoClient()
    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="scan",
        trigger_arg="",
        profile=miyo_profile,
        cache=cache,
        kado_client=spy,
        config=_Cfg(),
    )

    assert abort is None
    assert len(candidates) == 1
    c = candidates[0]
    assert "python" in c.topics
    assert "type-hints" in c.topics
    assert "mypy" in c.topics


# ── T5.1 Case 4: scoped modes unchanged — valid note stays as candidate ──────


def test_folder_mode_includes_valid_already_parented_note(miyo_profile):
    """Scoped modes (folder/tag/class/title) must NOT apply the orphan filter.

    A valid (already-parented) note inside the scoped target is still a
    candidate — orphan-filter is scan-ONLY. This is the regression guard.
    """
    valid_path = "Atlas/202 Notes/2611 Code Snippets/already-linked.md"

    # Cache not consulted by folder mode (Kado provides the file list),
    # but we set up a minimal map_notes so the config loads cleanly.
    cache = _make_cache([
        _moc_entry("Atlas/200 Maps/some-moc.md"),
        _valid_note_entry(valid_path),
    ])

    class _Cfg:
        candidate_cap = 500

    spy = SpyKadoClient()
    spy.set_listdir_response(
        "Atlas/202 Notes/2611 Code Snippets/",
        [
            {
                "type": "file",
                "path": valid_path,
                "name": "already-linked.md",
            }
        ],
    )

    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="folder",
        trigger_arg="Atlas/202 Notes/2611 Code Snippets/",
        profile=miyo_profile,
        cache=cache,
        kado_client=spy,
        config=_Cfg(),
    )

    assert abort is None
    paths = {c.path for c in candidates}
    assert valid_path in paths, (
        "folder mode must include valid notes — orphan filter is scan-ONLY"
    )


# ── T5.1 Case 5: _build_topics_index resolves kind==note path ───────────────


def test_build_topics_index_resolves_note_path():
    """_build_topics_index must index kind==note entries so scan candidates are hits.

    Before T5.1, the index only covered cache["map_notes"] (kind==moc entries).
    After T5.1, it must also index kind==note entries from cache["entries"] so
    phase2_extract_topics treats scan candidates as cache hits (not misses that
    require LLM batching).
    """
    note_path = "Atlas/202 Notes/2611 Code Snippets/zsh-prompt.md"
    moc_path = "Atlas/200 Maps/shell-moc.md"

    cache = _make_cache([
        _orphan_entry(note_path, topics=["shell", "zsh"]),
        _moc_entry(moc_path),
    ])

    index = moc_discovery._build_topics_index(cache)

    assert note_path in index, (
        "_build_topics_index must include kind==note paths from cache['entries']"
    )
    assert "shell" in index[note_path]
    assert "zsh" in index[note_path]
    # kind==moc entries must still be indexed (don't regress).
    assert moc_path in index


# ── T5.1 Case 6: candidate_cap default is 500 ───────────────────────────────


def test_candidate_cap_default_is_500(miyo_profile):
    """candidate_cap default in phase1_select_candidates must be 500 (was 200).

    An orphan set of exactly 500 must pass; 501 must abort with
    candidate-cap-exceeded.
    """
    # Build 501 orphan entries inside atomic-note scope.
    base = "Atlas/202 Notes/2611 Code Snippets/"
    entries_501 = [_orphan_entry(f"{base}n{i}.md") for i in range(501)]
    entries_500 = entries_501[:500]

    cache_501 = _make_cache(entries_501)
    cache_500 = _make_cache(entries_500)

    class _CfgNoOverride:
        # candidate_cap is intentionally absent — forces getattr fallback to default.
        pass

    spy = SpyKadoClient()

    _, abort_501 = moc_discovery.phase1_select_candidates(
        mode="scan",
        trigger_arg="",
        profile=miyo_profile,
        cache=cache_501,
        kado_client=spy,
        config=_CfgNoOverride(),
    )
    assert abort_501 == "candidate-cap-exceeded", (
        "501 orphans with default cap must abort as candidate-cap-exceeded"
    )

    _, abort_500 = moc_discovery.phase1_select_candidates(
        mode="scan",
        trigger_arg="",
        profile=miyo_profile,
        cache=cache_500,
        kado_client=spy,
        config=_CfgNoOverride(),
    )
    assert abort_500 is None, "500 orphans must pass with default cap of 500"


# ── T7.2: exclude/note tag — scan candidate filtering (ADR-13 B-note / PRD F8 AC6) ──


def _excluded_note_entry(path: str, topics: list[str] | None = None) -> dict:
    """An orphan note entry carrying the exclude/note tag."""
    stem = path.rsplit("/", 1)[-1].removesuffix(".md")
    return {
        "kind": "note",
        "path": path,
        "stem": stem,
        "title": stem,
        "topics": topics or [],
        "up_state": "absent",
        "up_target": None,
        "up_source": None,
        "tags": [EXCLUDE_NOTE_TAG],
    }


def test_scan_excludes_note_tagged_exclude_note(miyo_profile):
    """AC6: _handle_scan must skip a note entry whose tags include exclude/note.

    The note is orphaned (up_state==absent) but carries the tag — it must NOT
    appear in the scan candidates list (never clustered).
    """
    excluded_path = "Atlas/202 Notes/2611 Code Snippets/excluded-note.md"
    included_path = "Atlas/202 Notes/2611 Code Snippets/normal-orphan.md"

    cache = _make_cache([
        _excluded_note_entry(excluded_path, topics=["python"]),
        _orphan_entry(included_path, topics=["shell"]),
        _moc_entry("Atlas/200 Maps/some-moc.md"),
    ])

    class _Cfg:
        candidate_cap = 500

    spy = SpyKadoClient()
    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="scan",
        trigger_arg="",
        profile=miyo_profile,
        cache=cache,
        kado_client=spy,
        config=_Cfg(),
    )

    assert abort is None
    paths = {c.path for c in candidates}
    assert excluded_path not in paths, (
        f"note tagged {EXCLUDE_NOTE_TAG!r} must not be a scan candidate; got {paths}"
    )
    assert included_path in paths, "normal orphan note must still be a candidate"


def test_scan_without_excluded_notes_unchanged(miyo_profile):
    """Regression: scan mode with no excluded notes behaves identically to before T7.2."""
    path = "Atlas/202 Notes/2611 Code Snippets/regular.md"
    cache = _make_cache([
        _orphan_entry(path, topics=["topic"]),
    ])

    class _Cfg:
        candidate_cap = 500

    spy = SpyKadoClient()
    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="scan",
        trigger_arg="",
        profile=miyo_profile,
        cache=cache,
        kado_client=spy,
        config=_Cfg(),
    )

    assert abort is None
    paths = {c.path for c in candidates}
    assert path in paths, "note without exclude tag must remain a candidate"
