#!/usr/bin/env python3
# version: 0.2.0
"""test_moc_discovery_phase1.py — Phase 1 candidate selection for moc-discovery.py.

F-43 Phase 2 T2.2: covers the five mode handlers (`tag`, `folder`, `class`,
`title`/`free-text`, `scan`), the strict pre-filter to atomic-note paths, and
the abort branches (`zero-candidates`, `candidate-cap-exceeded`). Tests
exercise the unit functions directly with a fake KadoClient so no real Kado
connection is required.

Why a fake instead of `unittest.mock`: a small recording fake makes the
"glob-suffix `*` was actually appended" and "listDir was called once per
subdirectory" assertions trivial, and keeps test bodies readable.
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

# Load moc-discovery.py as a module (hyphen in name → importlib).
_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery"] = moc_discovery
_spec.loader.exec_module(moc_discovery)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _load_miyo_profile() -> dict:
    """Load the miyo profile YAML — used as the canonical profile for tests."""
    with (PROFILES_DIR / "miyo.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


@pytest.fixture
def miyo_profile() -> dict:
    return _load_miyo_profile()


@pytest.fixture
def empty_cache() -> dict:
    return {"map_notes": []}


@pytest.fixture
def small_config() -> object:
    """A MocProposalConfig-shaped object with the spec defaults."""
    # Avoid importing shared-ctx-builder here — the dataclass shape is stable
    # and trivially mocked. Phase1 only reads `candidate_cap`.
    class _Cfg:
        candidate_cap = 200
    return _Cfg()


class FakeKadoClient:
    """Minimal recording stand-in for `lib.kado_client.KadoClient`.

    Implements only the surface phase1 calls today: `search_by_tag` and
    `list_dir`. Each call records its arguments so tests can assert on them
    (e.g. that the `*` glob suffix landed on the byTag query). Returns are
    set per-test via `set_response`.
    """

    def __init__(self):
        self.calls: list[tuple[str, tuple, dict]] = []
        self._tag_responses: dict[str, list[dict]] = {}
        self._listdir_responses: dict[str, list[dict]] = {}
        self._listdir_default: list[dict] = []
        self._tag_default: list[dict] = []

    def set_tag_response(self, query: str, items: list[dict]) -> None:
        self._tag_responses[query] = items

    def set_listdir_response(self, path: str, items: list[dict]) -> None:
        self._listdir_responses[path] = items

    def set_listdir_default(self, items: list[dict]) -> None:
        self._listdir_default = items

    def search_by_tag(self, tag: str, limit: int = 500) -> list:
        self.calls.append(("search_by_tag", (tag,), {"limit": limit}))
        return list(self._tag_responses.get(tag, self._tag_default))

    def list_dir(self, path: str = "/", *, depth: int = None, limit: int = 500) -> list:
        self.calls.append(("list_dir", (path,), {"depth": depth, "limit": limit}))
        # Match by exact path key first, then default.
        if path in self._listdir_responses:
            return list(self._listdir_responses[path])
        return list(self._listdir_default)


# ── Mode handler tests ──────────────────────────────────────────────────────


def test_tag_mode_appends_glob_suffix(miyo_profile, empty_cache, small_config):
    """ADR-7: `--tag topic/applied/zsh` → Kado byTag query `#topic/applied/zsh*`."""
    fake = FakeKadoClient()
    fake.set_tag_response(
        "#topic/applied/zsh*",
        [
            {"path": "Atlas/202 Notes/2611 Code Snippets/zsh-aliases.md"},
            {"path": "Atlas/202 Notes/2611 Code Snippets/zsh-prompt.md"},
        ],
    )

    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="tag",
        trigger_arg="topic/applied/zsh",
        profile=miyo_profile,
        cache=empty_cache,
        kado_client=fake,
        config=small_config,
    )

    assert abort is None
    # Recorded call shows the literal `*` suffix per ADR-7.
    tag_calls = [c for c in fake.calls if c[0] == "search_by_tag"]
    assert len(tag_calls) == 1
    assert tag_calls[0][1][0] == "#topic/applied/zsh*"
    assert {c.path for c in candidates} == {
        "Atlas/202 Notes/2611 Code Snippets/zsh-aliases.md",
        "Atlas/202 Notes/2611 Code Snippets/zsh-prompt.md",
    }


def test_folder_mode_md_filter_clientside(miyo_profile, empty_cache, small_config):
    """ADR-6: listDir returns mixed entries; only `.md` files survive client-side."""
    fake = FakeKadoClient()
    fake.set_listdir_response(
        "Atlas/202 Notes/2611 Code Snippets/",
        [
            {"type": "file", "path": "Atlas/202 Notes/2611 Code Snippets/note.md", "name": "note.md"},
            {"type": "file", "path": "Atlas/202 Notes/2611 Code Snippets/diagram.canvas", "name": "diagram.canvas"},
            {"type": "folder", "path": "Atlas/202 Notes/2611 Code Snippets/sub", "name": "sub"},
            {"type": "file", "path": "Atlas/202 Notes/2611 Code Snippets/image.png", "name": "image.png"},
            {"type": "file", "path": "Atlas/202 Notes/2611 Code Snippets/another.md", "name": "another.md"},
        ],
    )

    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="folder",
        trigger_arg="Atlas/202 Notes/2611 Code Snippets/",
        profile=miyo_profile,
        cache=empty_cache,
        kado_client=fake,
        config=small_config,
    )

    assert abort is None
    paths = {c.path for c in candidates}
    assert paths == {
        "Atlas/202 Notes/2611 Code Snippets/note.md",
        "Atlas/202 Notes/2611 Code Snippets/another.md",
    }


def test_class_mode_resolves_subdir_via_profile(miyo_profile, empty_cache, small_config):
    """`--class 2600` → resolves the 26xx atomic-note subdirectory via profile."""
    fake = FakeKadoClient()
    # 2600 maps to "2611 Code Snippets" in miyo.yaml (dewey_parent: 2600).
    fake.set_listdir_response(
        "Atlas/202 Notes/2611 Code Snippets/",
        [
            {"type": "file", "path": "Atlas/202 Notes/2611 Code Snippets/zsh.md", "name": "zsh.md"},
            {"type": "file", "path": "Atlas/202 Notes/2611 Code Snippets/git.md", "name": "git.md"},
        ],
    )

    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="class",
        trigger_arg="2600",
        profile=miyo_profile,
        cache=empty_cache,
        kado_client=fake,
        config=small_config,
    )

    assert abort is None
    # The handler must have called list_dir on the resolved subdir.
    listdir_paths = [c[1][0] for c in fake.calls if c[0] == "list_dir"]
    assert "Atlas/202 Notes/2611 Code Snippets/" in listdir_paths
    paths = {c.path for c in candidates}
    assert "Atlas/202 Notes/2611 Code Snippets/zsh.md" in paths
    assert "Atlas/202 Notes/2611 Code Snippets/git.md" in paths


def test_title_and_freetext_topic_match_against_cache(
    miyo_profile, small_config
):
    """`--title <text>` and free-text both match against `cache.map_notes[].topics`.

    Title/free-text uses the existing discovery cache as the source — no Kado
    call is required (the cache already lists every note's topics). A naive
    substring match against any topic counts as a hit.
    """
    cache = {
        "map_notes": [
            {
                "path": "Atlas/202 Notes/2611 Code Snippets/zsh-prompt.md",
                "topics": ["shell", "zsh", "prompt"],
            },
            {
                "path": "Atlas/202 Notes/2611 Code Snippets/git-aliases.md",
                "topics": ["git", "shell"],
            },
            {
                "path": "Atlas/202 Notes/2021 Thoughts/morning-routine.md",
                "topics": ["routine", "habits"],
            },
        ]
    }
    fake = FakeKadoClient()  # not consulted in this mode

    cands_title, abort_t = moc_discovery.phase1_select_candidates(
        mode="title",
        trigger_arg="shell",
        profile=miyo_profile,
        cache=cache,
        kado_client=fake,
        config=small_config,
    )
    assert abort_t is None
    paths_t = {c.path for c in cands_title}
    assert paths_t == {
        "Atlas/202 Notes/2611 Code Snippets/zsh-prompt.md",
        "Atlas/202 Notes/2611 Code Snippets/git-aliases.md",
    }

    cands_free, abort_f = moc_discovery.phase1_select_candidates(
        mode="free-text",
        trigger_arg="zsh",
        profile=miyo_profile,
        cache=cache,
        kado_client=fake,
        config=small_config,
    )
    assert abort_f is None
    paths_f = {c.path for c in cands_free}
    assert paths_f == {"Atlas/202 Notes/2611 Code Snippets/zsh-prompt.md"}

    # Neither mode hit Kado.
    assert fake.calls == []


def test_scan_mode_sources_orphans_from_cache(miyo_profile, small_config):
    """scan mode: sources candidates from cache orphans, NOT from live list_dir.

    T5.1 / ADR-11: _handle_scan now reads cache["entries"] filtered to
    kind=="note" AND up_state=="absent". Kado list_dir is never called.
    An empty cache yields zero-candidates (correct — no orphans to process).
    A cache with two orphan entries yields exactly two candidates.
    """
    # Build a minimal cache with two orphan notes inside atomic-note scope.
    orphan_paths = [
        "Atlas/202 Notes/2611 Code Snippets/n0.md",
        "Atlas/202 Notes/2021 Thoughts/n1.md",
    ]
    entries = [
        {
            "kind": "note",
            "path": p,
            "stem": p.rsplit("/", 1)[-1][:-3],
            "title": p.rsplit("/", 1)[-1][:-3],
            "topics": ["t"],
            "up_state": "absent",
            "up_target": None,
            "up_source": None,
            "tags": [],
        }
        for p in orphan_paths
    ]
    cache_with_orphans = {"entries": entries, "map_notes": []}

    fake = FakeKadoClient()

    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="scan",
        trigger_arg="",
        profile=miyo_profile,
        cache=cache_with_orphans,
        kado_client=fake,
        config=small_config,
    )

    assert abort is None
    # No list_dir calls — scan is fully cache-sourced (ADR-11).
    listdir_paths = [c[1][0] for c in fake.calls if c[0] == "list_dir"]
    assert listdir_paths == [], f"scan must not call list_dir; got: {listdir_paths}"
    # Both orphan entries become candidates.
    assert {c.path for c in candidates} == set(orphan_paths)


def test_pre_filter_outside_atomic_note_warns_and_intersects(
    miyo_profile, empty_cache, small_config, capsys
):
    """Folder outside atomic-note scope → stderr WARN + only intersection kept."""
    fake = FakeKadoClient()
    # Folder is "Atlas/300 Logs/" — outside Atlas/202 Notes/.
    fake.set_listdir_response(
        "Atlas/300 Logs/",
        [
            # Fully outside atomic-note scope.
            {"type": "file", "path": "Atlas/300 Logs/2026-04.md", "name": "2026-04.md"},
            {"type": "file", "path": "Atlas/300 Logs/2026-05.md", "name": "2026-05.md"},
        ],
    )

    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="folder",
        trigger_arg="Atlas/300 Logs/",
        profile=miyo_profile,
        cache=empty_cache,
        kado_client=fake,
        config=small_config,
    )

    captured = capsys.readouterr()
    # Pre-filter dropped everything → empty intersection → zero-candidates abort.
    assert abort == "zero-candidates"
    assert candidates == []
    # Warning on stderr explaining the intersection.
    assert "WARN" in captured.err or "warn" in captured.err.lower()
    assert "atomic" in captured.err.lower() or "outside" in captured.err.lower()


def test_candidate_cap_exceeded_aborts(miyo_profile, empty_cache):
    """>cap candidates after pre-filter → `abort_reason="candidate-cap-exceeded"`."""

    class _Cfg:
        candidate_cap = 5  # tiny cap to keep test cheap

    fake = FakeKadoClient()
    # 6 candidates inside atomic-note scope → exceeds cap=5.
    items = [
        {"type": "file", "path": f"Atlas/202 Notes/2611 Code Snippets/n{i}.md", "name": f"n{i}.md"}
        for i in range(6)
    ]
    fake.set_listdir_response("Atlas/202 Notes/2611 Code Snippets/", items)

    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="folder",
        trigger_arg="Atlas/202 Notes/2611 Code Snippets/",
        profile=miyo_profile,
        cache=empty_cache,
        kado_client=fake,
        config=_Cfg(),
    )

    assert abort == "candidate-cap-exceeded"
    # Per spec: abort short-circuits — no candidates returned.
    assert candidates == []


def test_zero_candidates_aborts(miyo_profile, empty_cache, small_config):
    """0 candidates after pre-filter → `abort_reason="zero-candidates"`."""
    fake = FakeKadoClient()
    fake.set_tag_response("#topic/nonexistent*", [])  # nothing returned

    candidates, abort = moc_discovery.phase1_select_candidates(
        mode="tag",
        trigger_arg="topic/nonexistent",
        profile=miyo_profile,
        cache=empty_cache,
        kado_client=fake,
        config=small_config,
    )

    assert abort == "zero-candidates"
    assert candidates == []
