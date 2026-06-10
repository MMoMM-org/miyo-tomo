#!/usr/bin/env python3
# version: 0.2.0
"""test_moc_discovery_phase65.py — Phase 6.5 existing-`up::` validation.

Per-candidate decoration with `state` ∈ {"absent", "valid", "broken"} and
`target`. Phase 6.5 reads each candidate-child's note body via Kado ONCE, then
resolves the `up` relationship via lib/up_parse.parse_up_from_content (spec 021
T2.2) — which recognises BOTH the inline `up:: [[X]]` form AND the frontmatter
`up:` form, with inline winning on conflict (C1/ADR-2/ADR-6: the frontmatter
block is split locally from the same content, no extra Kado call). The caller
classifies the resolved target against the cache MOC stem set (cache.map_notes
is the authoritative MOC index — present → "valid", absent → "broken", no
target → "absent").

Algorithm (spec 021 T2.2):

    for cluster in clusters:
        for child_stem in cluster.items:
            note      = kado_client.read_note(stem_to_path[child_stem])
            target    = parse_up_from_content(note["content"]).target  # inline OR frontmatter
            if target is None:
                state = "absent"
            elif target in moc_stems(cache.map_notes):
                state = "valid"
            else:
                state = "broken"
            cluster.existing_up.append({stem, state, target})

Multi-INLINE-`up::` lines on the same child → use the first and emit a stderr
warning so the operator can fix the source note (a single frontmatter up: + one
inline up:: is the normal conflict case, resolved by inline-wins, not a
malformed note). The renderer downstream (Rule 4.2 / 4.5) keys off `state` only.

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


# ── Phase 6.5 tests ─────────────────────────────────────────────────────────
#
# T2.2 (spec 021): Phase 6.5 now resolves the `up` relationship via
# lib/up_parse.parse_up_from_content on the SAME read_note content (C1 — split
# frontmatter locally, no extra Kado call). This recognises BOTH the inline
# `up:: [[X]]` form AND the frontmatter `up:` form, with inline winning on
# conflict (ADR-2/ADR-6). The old inline-only `_extract_first_up_marker` helper
# and its two direct unit tests were retired — that behaviour (no-marker→None,
# inline→target) is covered by tests/test_up_parse.py, and the
# frontmatter/inline-wins additions below cover the new surface.


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


# ── T2.2: dual-`up` (frontmatter + inline) via lib/up_parse ──────────────────


def test_frontmatter_up_only_resolves_valid():
    """Frontmatter `up:` only (no inline `up::`) AND target in cache → valid.

    The whole point of T2.2: a note that declares its parent in frontmatter is
    no longer falsely treated as an orphan (PRD AC F2#1).
    """
    candidates = [_candidate("fish-config", "Atlas/202 Notes/fish-config.md")]
    clusters = [_cluster("shell", ["fish-config"])]
    kado = _FakeKado({
        "Atlas/202 Notes/fish-config.md": (
            "---\ntitle: fish config\nup: \"[[2600 - Applied Sciences]]\"\n---\n"
            "# fish config\n\nNo inline marker here.\n"
        ),
    })
    cache = _cache([("2600 - Applied Sciences", "Atlas/200 Maps/2600 - Applied Sciences.md")])

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )

    rows = decorated[0]["existing_up"]
    assert rows == [
        {"stem": "fish-config", "state": "valid", "target": "2600 - Applied Sciences"}
    ], f"Frontmatter up: must resolve valid; got {rows!r}"


def test_frontmatter_up_list_form_resolves_valid():
    """Frontmatter `up:` as a YAML list → first entry used, resolves valid."""
    candidates = [_candidate("nu-shell", "Atlas/202 Notes/nu-shell.md")]
    clusters = [_cluster("shell", ["nu-shell"])]
    kado = _FakeKado({
        "Atlas/202 Notes/nu-shell.md": (
            "---\nup:\n  - \"[[2600 - Applied Sciences]]\"\n---\n# nu shell\n"
        ),
    })
    cache = _cache([("2600 - Applied Sciences", "Atlas/200 Maps/2600 - Applied Sciences.md")])

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )
    rows = decorated[0]["existing_up"]
    assert rows == [
        {"stem": "nu-shell", "state": "valid", "target": "2600 - Applied Sciences"}
    ], f"Frontmatter list up: must resolve valid; got {rows!r}"


def test_inline_up_wins_over_frontmatter_on_conflict():
    """Both inline `up::` AND frontmatter `up:` present, differing targets →
    inline target wins (ADR-2/ADR-6, PRD AC F2#3)."""
    candidates = [_candidate("conflict", "Atlas/202 Notes/conflict.md")]
    clusters = [_cluster("shell", ["conflict"])]
    kado = _FakeKado({
        "Atlas/202 Notes/conflict.md": (
            "---\nup: \"[[Frontmatter MOC]]\"\n---\n"
            "# conflict\n\nup:: [[Inline MOC]]\n"
        ),
    })
    # BOTH targets exist in cache, so the resolved one is unambiguous by target.
    cache = _cache([
        ("Inline MOC", "Atlas/200 Maps/Inline MOC.md"),
        ("Frontmatter MOC", "Atlas/200 Maps/Frontmatter MOC.md"),
    ])

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )
    rows = decorated[0]["existing_up"]
    assert rows == [
        {"stem": "conflict", "state": "valid", "target": "Inline MOC"}
    ], f"Inline up:: must win over frontmatter up:; got {rows!r}"


def test_frontmatter_up_broken_when_target_not_in_cache():
    """Frontmatter `up:` whose target is not a known MOC → broken (not absent)."""
    candidates = [_candidate("orphan-fm", "Atlas/202 Notes/orphan-fm.md")]
    clusters = [_cluster("shell", ["orphan-fm"])]
    kado = _FakeKado({
        "Atlas/202 Notes/orphan-fm.md": (
            "---\nup: \"[[Ghost MOC]]\"\n---\n# orphan fm\n"
        ),
    })
    cache = _cache([("2600 - Applied Sciences", "Atlas/200 Maps/2600 - Applied Sciences.md")])

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )
    rows = decorated[0]["existing_up"]
    assert rows == [
        {"stem": "orphan-fm", "state": "broken", "target": "Ghost MOC"}
    ], f"Frontmatter up: to unknown MOC must be broken; got {rows!r}"


def test_empty_frontmatter_up_is_absent():
    """Empty frontmatter `up:` (and no inline) → absent, target None."""
    candidates = [_candidate("no-up", "Atlas/202 Notes/no-up.md")]
    clusters = [_cluster("shell", ["no-up"])]
    kado = _FakeKado({
        "Atlas/202 Notes/no-up.md": "---\nup: []\ntitle: no up\n---\n# no up\n",
    })
    cache = _cache([])

    decorated = moc_discovery.phase65_validate_existing_up(
        clusters, candidates, kado, cache
    )
    rows = decorated[0]["existing_up"]
    assert rows == [
        {"stem": "no-up", "state": "absent", "target": None}
    ], f"Empty frontmatter up: must be absent; got {rows!r}"
