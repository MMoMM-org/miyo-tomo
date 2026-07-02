#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_phase4.py — Phase 4 title generation for moc-discovery.py.

F-43 Phase 2 T2.5 (first half): per-profile title generation. Phase 4 takes a
single Cluster (from Phase 3) plus the active profile and the run's
(mode, trigger_arg) pair, and returns the proposed MOC title as a string.

The two profile-shaped behaviours covered:

  - **miyo:** all MOCs carry an explicit `MOC` suffix (e.g. ``"Shell MOC"``)
    matching `tier-3/lyt-moc/new-moc-proposal.md` §7's MiYo row.
  - **lyt:** plain title with no suffix (``"Shell"``).

The mode-aware override:

  - **mode == "title":** the user's free-text trigger_arg is the proposed
    title verbatim — title generation does not second-guess it (PRD AC-2.4).

For all other modes (`scan`, `tag`, `folder`, `class`, `free-text`), the
cluster's normalised topic is the seed; we Title-Case it and apply the
profile's suffix rule.

No Kado, no LLM, no fixtures on disk — pure-function tests.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import yaml

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
PROFILES_DIR = REPO_ROOT / "tomo" / "profiles"
SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load moc-discovery.py as a module (hyphen in filename → importlib).
_spec = importlib.util.spec_from_file_location("moc_discovery", SCRIPT_PATH)
moc_discovery = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["moc_discovery"] = moc_discovery
_spec.loader.exec_module(moc_discovery)


# ── Fixtures ────────────────────────────────────────────────────────────────


def _load_profile(name: str) -> dict:
    with (PROFILES_DIR / f"{name}.yaml").open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _cluster(topic: str, items: list[str]) -> dict:
    """Build a Phase-3-shaped Cluster TypedDict for tests."""
    return {"topic": topic, "items": list(items), "parent": "", "tags": []}


# ── Tests ────────────────────────────────────────────────────────────────────


def test_miyo_title_appends_moc_suffix():
    """miyo profile → derived title carries the ``MOC`` suffix.

    Per `tier-3/lyt-moc/new-moc-proposal.md` §7, MiYo MOCs follow the pattern
    ``<Topic> MOC`` (Marcus's vault uses parens-styled ``(MOC)`` in raw
    titles, but the proposal's TopicTitle is the plain "<Topic> MOC" form;
    final user-visible polish is handled at render time).
    """
    profile = _load_profile("miyo")
    cluster = _cluster("shell", ["zsh", "bash", "fish"])

    title = moc_discovery.phase4_title(cluster, profile, mode="scan", trigger_arg="")

    assert title == "Shell (MOC)", (
        f"miyo profile must append ' (MOC)' suffix; got {title!r}"
    )


def test_lyt_title_plain():
    """lyt profile → plain Title-Cased topic, no suffix."""
    profile = _load_profile("lyt")
    cluster = _cluster("shell", ["zsh", "bash", "fish"])

    title = moc_discovery.phase4_title(cluster, profile, mode="scan", trigger_arg="")

    assert title == "Shell", (
        f"lyt profile must NOT append a suffix; got {title!r}"
    )


def test_title_mode_uses_user_input_verbatim():
    """mode == 'title' → trigger_arg wins, untouched, regardless of profile.

    PRD AC-2.4: when the user explicitly provides a title via ``--title``, the
    pipeline must not rewrite, suffix, or re-case it. Both profiles must
    return the user input as-is.
    """
    user_input = "My Custom"
    cluster = _cluster("shell", ["zsh", "bash", "fish"])

    for profile_name in ("miyo", "lyt"):
        profile = _load_profile(profile_name)
        title = moc_discovery.phase4_title(
            cluster, profile, mode="title", trigger_arg=user_input
        )
        assert title == user_input, (
            f"mode='title' must use trigger_arg verbatim ({profile_name=}); "
            f"got {title!r}"
        )


def test_title_suffix_comes_from_profile_not_hardcoded():
    """Suffix is read from the profile's map_note.name_suffix, not a name-keyed
    hardcoded dict. A fabricated profile with a custom suffix must be honoured.

    F-55 / spec 028 T2.1: this fails while the suffix is a hardcoded
    `_PROFILE_TITLE_SUFFIX` dict keyed on the profile name.
    """
    profile = {"concept_defaults": {"map_note": {"name_suffix": " ~Map~"}}}
    cluster = _cluster("shell", ["zsh", "bash", "fish"])

    title = moc_discovery.phase4_title(cluster, profile, mode="scan", trigger_arg="")

    assert title == "Shell ~Map~", (
        f"suffix must come from profile map_note.name_suffix; got {title!r}"
    )


def test_title_apply_once_no_double_suffix():
    """A profile whose suffix already terminates the derived title must not be
    double-applied (apply-once rule)."""
    # Suffix chosen so str.title() does not alter it (all-caps/word-boundary safe).
    profile = {"concept_defaults": {"map_note": {"name_suffix": " Map"}}}
    cluster = _cluster("shell map", ["zsh", "bash"])

    title = moc_discovery.phase4_title(cluster, profile, mode="scan", trigger_arg="")

    assert title == "Shell Map", f"apply-once violated; got {title!r}"


def test_miyo_title_byte_identical_regression():
    """Byte-identical miyo regression: a spread of topics all end in ' (MOC)'."""
    profile = _load_profile("miyo")
    cases = {
        "shell": "Shell (MOC)",
        "knowledge management": "Knowledge Management (MOC)",
        "vcs": "Vcs (MOC)",
    }
    for topic, expected in cases.items():
        got = moc_discovery.phase4_title(
            _cluster(topic, ["a", "b", "c"]), profile, mode="scan", trigger_arg=""
        )
        assert got == expected, f"miyo byte-identity broke for {topic!r}: {got!r}"


def test_scan_multi_cluster_one_title_per_cluster():
    """mode == 'scan' with N clusters → N distinct titles, one per cluster."""
    profile = _load_profile("miyo")
    clusters = [
        _cluster("shell", ["zsh", "bash", "fish"]),
        _cluster("editor", ["vim", "neovim", "emacs"]),
        _cluster("vcs", ["git", "hg", "fossil"]),
    ]

    titles = [
        moc_discovery.phase4_title(c, profile, mode="scan", trigger_arg="")
        for c in clusters
    ]

    assert titles == ["Shell (MOC)", "Editor (MOC)", "Vcs (MOC)"], (
        f"Each cluster must get its own derived title; got {titles!r}"
    )
    assert len(titles) == len(set(titles)), (
        f"Distinct cluster topics must yield distinct titles; got {titles!r}"
    )
