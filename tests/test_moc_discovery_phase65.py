#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_phase65.py — Phase 6.5 existing-`up::` validation.

F-43 Phase 2 T2.7: per-candidate decoration with `existing_up_state` ∈
{"absent", "valid", "broken"} and `existing_up_target`. Phase 6.5 reads each
candidate-child's note body via Kado, extracts the first ``up::`` marker, and
classifies it against the discovery cache (cache.map_notes is the
authoritative MOC index — a target present in cache is "valid", absent is
"broken", and no marker at all is "absent").

Algorithm (per SDD §Implementation Examples / Example 1 + brainstorm §6.5,
lines 147-153 of `docs/XDD/ideas/2026-05-06-moc-creation-skill.md`):

    for cluster in clusters:
        for child_stem in cluster.items:
            note      = kado_client.read_note(stem_to_path[child_stem])
            target    = extract_first_up_marker(note["content"])
            if target is None:
                state = "absent"
            elif target_in_cache(target, cache.map_notes):
                state = "valid"
            else:
                state = "broken"
            cluster.existing_up.append({stem, state, target})

Multi-`up::` lines on the same child → use the first match and emit a stderr
warning so the operator can fix the source note. The renderer downstream
(Rule 4.2 / 4.5) keys off `existing_up_state` only — we do not surface the
warning into the report payload.

Stdlib only — Kado client is faked locally; no live calls.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load moc-discovery.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery"] = moc_discovery
_spec.loader.exec_module(moc_discovery)


# ── Fakes ───────────────────────────────────────────────────────────────────


class _FakeKado:
    """Minimal Kado stub: maps path → ``{"content": str, ...}`` like the real
    `KadoClient.read_note`. Unknown paths raise FileNotFoundError so test
    surprises are loud rather than silent.
    """

    def __init__(self, notes_by_path: dict[str, str]):
        self._notes = dict(notes_by_path)

    def read_note(self, path: str) -> dict:
        if path not in self._notes:
            raise FileNotFoundError(f"_FakeKado: path not registered: {path!r}")
        return {"content": self._notes[path]}


# ── Fixtures ────────────────────────────────────────────────────────────────


def _candidate(stem: str, path: str) -> moc_discovery.Candidate:
    return moc_discovery.Candidate(stem=stem, path=path)


def _cluster(topic: str, items: list[str]) -> dict:
    """Phase-3-shaped Cluster TypedDict — items are candidate stems."""
    return {"topic": topic, "items": list(items), "parent": "", "tags": []}


def _cache(moc_paths: list[tuple[str, str]]) -> dict:
    """Build a cache stub with a populated `map_notes` list.

    Args:
        moc_paths: list of ``(stem, path)`` pairs for existing MOCs.
    """
    return {
        "map_notes": [
            {"path": path, "title": stem, "topics": []}
            for stem, path in moc_paths
        ]
    }


# ── Helper tests ────────────────────────────────────────────────────────────


def test_extract_first_up_marker_returns_none_when_absent():
    """A body with no ``up::`` line → helper returns None."""
    body = "# Some Note\n\nJust prose, no relationship markers.\n"
    assert moc_discovery._extract_first_up_marker(body) is None


def test_extract_first_up_marker_returns_first_target():
    """A single ``up:: [[Target]]`` line → helper returns ``"Target"``."""
    body = "# Note\n\nup:: [[Existing MOC]]\n\nbody text\n"
    assert moc_discovery._extract_first_up_marker(body) == "Existing MOC"


# ── Phase 6.5 tests ─────────────────────────────────────────────────────────


def test_no_up_marker_state_absent():
    """Candidate body has no ``up::`` line → state="absent", target=None."""
    candidates = [_candidate("zsh-aliases", "Atlas/202 Notes/zsh-aliases.md")]
    clusters = [_cluster("shell", ["zsh-aliases"])]
    kado = _FakeKado({
        "Atlas/202 Notes/zsh-aliases.md": "# zsh aliases\n\nNo relationship markers here.\n",
    })
    cache = _cache([])  # empty MOC index — irrelevant for absent case

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )

    assert len(decorated) == 1, f"Cluster count must be preserved; got {decorated!r}"
    rows = decorated[0]["existing_up"]
    assert rows == [
        {"stem": "zsh-aliases", "state": "absent", "target": None}
    ], f"Expected single absent row; got {rows!r}"


def test_valid_up_resolves_state_valid():
    """``up:: [[Existing MOC]]`` AND target is in cache.map_notes → state="valid"."""
    candidates = [_candidate("oh-my-zsh", "Atlas/202 Notes/oh-my-zsh.md")]
    clusters = [_cluster("shell", ["oh-my-zsh"])]
    kado = _FakeKado({
        "Atlas/202 Notes/oh-my-zsh.md": (
            "# oh-my-zsh\n\nup:: [[2600 - Applied Sciences]]\n\nbody.\n"
        ),
    })
    cache = _cache([("2600 - Applied Sciences", "Atlas/200 Maps/2600 - Applied Sciences.md")])

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )

    rows = decorated[0]["existing_up"]
    assert rows == [
        {
            "stem": "oh-my-zsh",
            "state": "valid",
            "target": "2600 - Applied Sciences",
        }
    ], f"Expected valid row; got {rows!r}"


def test_broken_up_state_broken():
    """``up:: [[Phantom MOC]]`` AND target NOT in cache → state="broken".

    Per PRD AC-4.3: a broken existing-`up::` must be classified as
    ``broken`` so the renderer can ignore it (Rule 4.3) without losing
    user data or crashing on a missing target.
    """
    candidates = [_candidate("tmux-setup", "Atlas/202 Notes/tmux-setup.md")]
    clusters = [_cluster("shell", ["tmux-setup"])]
    kado = _FakeKado({
        "Atlas/202 Notes/tmux-setup.md": (
            "# tmux setup\n\nup:: [[Old MOC No Longer Exists]]\n"
        ),
    })
    # Cache has SOME other MOC but not the phantom one.
    cache = _cache([("2600 - Applied Sciences", "Atlas/200 Maps/2600 - Applied Sciences.md")])

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )

    rows = decorated[0]["existing_up"]
    assert rows == [
        {
            "stem": "tmux-setup",
            "state": "broken",
            "target": "Old MOC No Longer Exists",
        }
    ], f"Expected broken row; got {rows!r}"


def test_malformed_multi_up_uses_first_with_warning(capsys):
    """Two ``up::`` lines → use the first, emit stderr WARN."""
    candidates = [_candidate("multi", "Atlas/202 Notes/multi.md")]
    clusters = [_cluster("shell", ["multi"])]
    kado = _FakeKado({
        "Atlas/202 Notes/multi.md": (
            "# multi\n\nup:: [[First MOC]]\nup:: [[Second MOC]]\n"
        ),
    })
    cache = _cache([("First MOC", "Atlas/200 Maps/First MOC.md")])

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )

    rows = decorated[0]["existing_up"]
    assert rows == [
        {"stem": "multi", "state": "valid", "target": "First MOC"}
    ], f"Expected first-up:: target; got {rows!r}"

    captured = capsys.readouterr()
    assert "multiple up:: markers" in captured.err, (
        f"Expected stderr warning about multiple up:: markers; got err={captured.err!r}"
    )
    assert "Atlas/202 Notes/multi.md" in captured.err, (
        f"Stderr warning must name the offending path; got {captured.err!r}"
    )


def test_kado_read_failure_does_not_crash(capsys):
    """One failing `read_note` must not abort decoration of the cluster.

    Real-world failure modes: note deleted between candidate collection and
    Phase 6.5, transient Kado network/permission error. The function must
    continue, mark the unreadable child as ``state="absent"`` /
    ``target=None``, and let the rest of the cluster decorate normally.
    """

    class _FlakyKado:
        """Raises for one configured stem; behaves like _FakeKado otherwise."""

        def __init__(self, notes_by_path: dict[str, str], failing_path: str):
            self._notes = dict(notes_by_path)
            self._failing = failing_path

        def read_note(self, path: str) -> dict:
            if path == self._failing:
                raise RuntimeError(f"_FlakyKado: simulated failure for {path!r}")
            if path not in self._notes:
                raise FileNotFoundError(f"_FlakyKado: path not registered: {path!r}")
            return {"content": self._notes[path]}

    candidates = [
        _candidate("zsh-aliases", "Atlas/202 Notes/zsh-aliases.md"),
        _candidate("oh-my-zsh", "Atlas/202 Notes/oh-my-zsh.md"),
    ]
    clusters = [_cluster("shell", ["zsh-aliases", "oh-my-zsh"])]
    kado = _FlakyKado(
        notes_by_path={
            "Atlas/202 Notes/oh-my-zsh.md": (
                "# oh-my-zsh\n\nup:: [[2600 - Applied Sciences]]\n"
            ),
        },
        failing_path="Atlas/202 Notes/zsh-aliases.md",
    )
    cache = _cache(
        [("2600 - Applied Sciences", "Atlas/200 Maps/2600 - Applied Sciences.md")]
    )

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )

    assert len(decorated) == 1, f"Cluster count must be preserved; got {decorated!r}"
    rows = decorated[0]["existing_up"]
    assert rows == [
        {"stem": "zsh-aliases", "state": "absent", "target": None},
        {
            "stem": "oh-my-zsh",
            "state": "valid",
            "target": "2600 - Applied Sciences",
        },
    ], (
        "Both stems must appear in existing_up; failing one absent/None, the "
        f"other resolved normally; got {rows!r}"
    )

    captured = capsys.readouterr()
    assert "kado read_note" in captured.err, (
        f"Expected stderr warning about failed kado read_note; got err={captured.err!r}"
    )
    assert "Atlas/202 Notes/zsh-aliases.md" in captured.err, (
        f"Stderr warning must name the failing path; got {captured.err!r}"
    )
