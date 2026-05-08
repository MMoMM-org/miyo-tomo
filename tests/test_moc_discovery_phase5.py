#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_phase5.py — Phase 5 parent resolution for moc-discovery.py.

F-43 Phase 2 T2.5 (second half): match a cluster's topic keywords against the
active profile's `classification.categories` and return up to three
`ParentOption` entries ranked by overlap confidence (descending).

Algorithm (per SDD §Pseudocode line 877 + tier-3 `moc-matching.md` §3):

  - For each `classification.categories.NNNN`, compute keyword overlap
    between the cluster's topics and the category's `keywords`.
  - Score = simple overlap-ratio (count(matched) / max(len(cluster_topics),1)),
    with deeper / more specific matches not yet penalised in this phase
    (depth bonus is a MOC-matching concern, not a classification concern).
  - Sort descending; return top 3.
  - Categories with zero overlap are not returned.

`ParentOption` fields (per SDD line 547):
  - `moc_stem`: the canonical stem of the parent MOC ("2600 - Applied Sciences")
  - `confidence`: float in [0.0, 1.0]
  - `label`: short human-readable hint, e.g. "Applied Sciences (Dewey 2600)"

The miyo profile's keyword for `2600 - Applied Sciences` includes ``shell``
explicitly, so a cluster topic "shell" must rank Applied Sciences first.
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


def _empty_cache() -> dict:
    return {"map_notes": []}


# ── Tests ────────────────────────────────────────────────────────────────────


def test_classification_keyword_match_top_parent():
    """miyo profile + cluster `shell` → ``2600 - Applied Sciences`` ranks first.

    `classification.categories.2600.keywords` in `miyo.yaml` includes
    ``shell`` explicitly — Phase 5 must recognise the literal overlap and
    surface 2600 as the top parent option.
    """
    profile = _load_profile("miyo")
    cluster = _cluster("shell", ["zsh", "bash", "fish"])

    parents = moc_discovery.phase5_resolve_parents(cluster, profile, _empty_cache())

    assert parents, "Expected at least one parent option for cluster topic 'shell'"
    top = parents[0]
    # `moc_stem` should clearly identify the Dewey 2600 category.
    assert "2600" in top.moc_stem, (
        f"Top parent must be the 2600 - Applied Sciences class; got {top.moc_stem!r}"
    )
    assert top.confidence > 0.0, (
        f"Top parent must carry a non-zero confidence; got {top.confidence!r}"
    )
    assert top.label, "Top parent must carry a non-empty human-readable label"


def test_no_keyword_match_returns_null_parent():
    """Cluster topics with zero overlap → empty list (no false-positive parent).

    A topic like ``raclette-machine`` has no matching keyword in either
    profile's categories, so Phase 5 must return an empty list rather than
    forcing a low-confidence guess.
    """
    profile = _load_profile("miyo")
    cluster = _cluster("raclette-machine", ["raclette-grill", "raclette-pan"])

    parents = moc_discovery.phase5_resolve_parents(cluster, profile, _empty_cache())

    assert parents == [], (
        f"No-overlap cluster must yield zero parent options; got {parents!r}"
    )


def test_top_3_parents_offered():
    """Multi-category cluster → at most 3 parents, sorted by confidence DESC.

    Cluster topics are chosen to overlap with three different miyo Dewey
    categories (2000 = knowledge, 2600 = applied, 2700 = recreation). Phase 5
    must return all three (since each scores > 0), sorted by confidence
    descending, capped at 3 results.
    """
    profile = _load_profile("miyo")
    # Topics chosen so each overlaps with a different category:
    #   "knowledge" → 2000 (Knowledge Management)
    #   "shell"     → 2600 (Applied Sciences)
    #   "music"     → 2700 (Art & Recreation)
    cluster = {
        "topic": "knowledge",  # display topic from Phase 3 — first item wins
        "items": ["a", "b", "c"],
        "parent": "",
        "tags": [],
        # The cluster also carries multi-topic context via `topic_keywords`
        # (Phase 3's reducer doesn't expose a list per cluster, so Phase 5
        # falls back to splitting the display topic + items context). We
        # supply an explicit topic_keywords field — the implementation must
        # tolerate either shape (single `topic` or list `topic_keywords`).
        "topic_keywords": ["knowledge", "shell", "music"],
    }

    parents = moc_discovery.phase5_resolve_parents(cluster, profile, _empty_cache())

    assert 1 <= len(parents) <= 3, (
        f"Phase 5 must cap at 3 parents; got {len(parents)}"
    )
    # All scored entries must have positive confidence.
    for p in parents:
        assert p.confidence > 0.0, (
            f"Returned parent options must have confidence > 0; got {p}"
        )
    # Sorted descending by confidence.
    confidences = [p.confidence for p in parents]
    assert confidences == sorted(confidences, reverse=True), (
        f"Parents must be sorted by confidence DESC; got {confidences}"
    )
    # All three target Dewey classes must be represented (each topic matches
    # exactly one category in miyo.yaml).
    stems = " ".join(p.moc_stem for p in parents)
    for expected_class in ("2000", "2600", "2700"):
        assert expected_class in stems, (
            f"Expected Dewey {expected_class} in parents; got {stems!r}"
        )
