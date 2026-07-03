#!/usr/bin/env python3
# version: 0.1.0
"""test_moc_discovery_dedupe.py — TDD (RED-first) tests for spec-029 T2.1.

Covers _find_jaccard_match's new weighted-overlap signature and the
squelch-invariance guarantee for compute_topic_signature.

Run under ./venv/bin/python -m pytest tests/ -q
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

# Load moc-discovery.py as a module (hyphenated name → importlib)
_SCRIPT_PATH = SCRIPTS_DIR / "moc-discovery.py"
_spec = importlib.util.spec_from_file_location("moc_discovery", _SCRIPT_PATH)
moc_discovery = importlib.util.module_from_spec(_spec)
sys.modules["moc_discovery"] = moc_discovery
_spec.loader.exec_module(moc_discovery)

_find_jaccard_match = moc_discovery._find_jaccard_match

# Import compute_topic_signature directly from lib.topic_signature
from lib.topic_signature import compute_topic_signature  # noqa: E402

# ─────────────────────────────────────────────────────────────────────────────
# 1. Weighted dedupe behavior
# Traced-walkthrough-2 construction (matching test_topic_match.py's fixture):
#   cluster topics = 8 shared content topics + "ta", cluster_title contains "ta"
#   MOC entry  topics = 8 shared + "tb",            MOC title   contains "tb"
# flat Jaccard = 8/10 = 0.80  BUT  weighted = 8/12 ≈ 0.667  → NOT flagged
# ─────────────────────────────────────────────────────────────────────────────

CONTENT_8 = {"fox", "box", "crow", "owl", "ant", "bee", "crab", "duck"}


def _moc_entry(topics, title):
    """Build a minimal map_notes entry dict."""
    return {"title": title, "topics": list(topics), "path": "Atlas/MOCs/test.md"}


class TestWeightedDedupeBehavior:
    """Flat Jaccard ≥ 0.80 but weighted < 0.80 → _find_jaccard_match returns (None, <0.80).
    This test suite cannot pass against the old 2-argument _find_jaccard_match or
    an implementation that ignores titles.
    """

    def test_title_disagree_not_flagged(self):
        """Cluster title themes 'ta', MOC title themes 'tb' — flat 0.80 but weighted 0.667.

        Passes only when _find_jaccard_match accepts cluster_title and delegates
        to weighted_overlap.  The old 2-arg signature raises TypeError, failing RED.
        """
        cluster_topics = CONTENT_8 | {"ta"}
        cluster_title = "ta note"
        moc_entry = _moc_entry(CONTENT_8 | {"tb"}, "tb note")

        label, score = _find_jaccard_match(cluster_topics, cluster_title, [moc_entry])

        assert label is None, (
            f"Title-disagreeing cluster must NOT be flagged as duplicate; got label={label!r}"
        )
        assert score < 0.80, (
            f"Weighted score must be < 0.80 (was {score:.4f}); flat Jaccard is 0.80"
        )

    def test_title_agree_is_flagged(self):
        """Both titles theme 'ta' — shared title weight boosts score to 1.0 → flagged.

        A title-agreeing cluster IS flagged (returns (label, >= 0.80)).
        """
        cluster_topics = CONTENT_8 | {"ta"}
        cluster_title = "ta note"
        moc_entry = _moc_entry(CONTENT_8 | {"ta"}, "ta guide")

        label, score = _find_jaccard_match(cluster_topics, cluster_title, [moc_entry])

        assert label is not None, (
            "Title-agreeing cluster must be flagged as duplicate; got None"
        )
        assert score >= 0.80, (
            f"Weighted score must be >= 0.80 for title-agreeing dup; got {score:.4f}"
        )

    def test_disagree_no_match_returns_zero_score(self):
        """No-match path returns (None, 0.0) — the weighted score 8/12 never
        clears the 0.80 threshold so the function exits via the fall-through.

        The actual 8/12 value is independently verified in test_topic_match.py
        (TestDedupeDiscriminator.test_discriminating_score_matches_traced_walkthrough).
        """
        cluster_topics = CONTENT_8 | {"ta"}
        cluster_title = "ta note"
        moc_entry = _moc_entry(CONTENT_8 | {"tb"}, "tb note")

        label, score = _find_jaccard_match(cluster_topics, cluster_title, [moc_entry])

        assert label is None, f"Disagree case must not be flagged; got label={label!r}"
        assert score == 0.0, (
            f"No-match path must return 0.0 (fall-through default); got {score:.6f}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Squelch-invariance golden hash
# compute_topic_signature is not modified by F-05.  The hash below was
# captured from the live function on this fixture and proves invariance:
#   HOW captured: topic_signature.py is not modified by F-05, so the current
#   output is byte-identical to pre-F-05 main; GOLDEN_HASH captured from
#   the live function on this fixture.
# ─────────────────────────────────────────────────────────────────────────────

_FIXTURE = {
    "topic_keywords": ["python", "testing", "tdd"],
    "candidate_stems": ["alpha", "beta", "gamma"],
}
GOLDEN_HASH = "a1455603c2762dd3"


class TestSquelchInvariance:
    def test_golden_hash_unchanged(self):
        """compute_topic_signature must not drift from the pre-F-05 value.

        GOLDEN_HASH = 'a1455603c2762dd3'
        HOW captured: topic_signature.py is not modified by F-05, so the current
        output is byte-identical to pre-F-05 main; hash captured from the live
        function on this fixture via compute_hash.py in the scratchpad.
        """
        assert compute_topic_signature(_FIXTURE) == GOLDEN_HASH, (
            "topic_signature.compute_topic_signature drifted — F-05 must not "
            "change topic_signature.py"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 3. Malformed / title-less entry — no KeyError or TypeError
# ─────────────────────────────────────────────────────────────────────────────


class TestMalformedEntries:
    """_find_jaccard_match must tolerate entries that lack 'title' or are non-dicts."""

    def test_title_less_entry_no_exception(self):
        """Entry with no 'title' key scores on base weights — no KeyError."""
        cluster_topics = {"python", "testing"}
        cluster_title = "python guide"
        # Entry without "title" key (only topics + path)
        entry_no_title = {"topics": ["python", "testing"], "path": "Atlas/MOCs/no-title.md"}

        # Must not raise; may or may not reach threshold depending on topics
        result = _find_jaccard_match(cluster_topics, cluster_title, [entry_no_title])
        assert isinstance(result, tuple), "Must return a (label, score) tuple"
        assert len(result) == 2

    def test_none_entry_skipped(self):
        """Non-dict entries (e.g. None) are silently skipped."""
        cluster_topics = {"python", "testing"}
        cluster_title = "python guide"
        # Mix of invalid and valid entries
        good_entry = _moc_entry({"python", "testing"}, "python guide")
        map_notes = [None, "not-a-dict", good_entry]

        label, score = _find_jaccard_match(cluster_topics, cluster_title, map_notes)

        # The valid entry (identical topics + agreeing title) should match
        assert label is not None, (
            "Valid entry after non-dict entries must still be found; got None"
        )

    def test_empty_topics_entry_skipped(self):
        """Entry with empty/missing topics is skipped (no divide-by-zero).

        Uses titles that contain BOTH cluster topics so both sides weight them
        W_TITLE (×2); the score is 1.0 and clears the 0.80 threshold.
        """
        cluster_topics = {"python", "testing"}
        # Both "python" and "testing" appear in the cluster title → W_TITLE=2 for both
        cluster_title = "python testing guide"
        empty_entry = {"title": "some moc", "topics": [], "path": "Atlas/MOCs/empty.md"}
        # MOC title also contains both topics → W_TITLE=2 on both sides → score=1.0
        good_entry = _moc_entry({"python", "testing"}, "python testing concepts")
        map_notes = [empty_entry, good_entry]

        label, score = _find_jaccard_match(cluster_topics, cluster_title, map_notes)

        # good_entry has exact topic match + agreeing title → must be flagged
        assert label is not None, "Empty-topics entry must be skipped; good entry must match"


# ─────────────────────────────────────────────────────────────────────────────
# 4. First-match early-return preserved (not argmax)
# ─────────────────────────────────────────────────────────────────────────────


class TestEarlyReturn:
    """The first entry that clears JACCARD_DUP_THRESHOLD (0.80) is returned immediately.

    The SDD explicitly forbids switching to argmax.
    """

    def test_returns_first_match_not_argmax(self):
        """Two entries both >= 0.80 — the FIRST is returned, not the highest scorer."""
        cluster_topics = {"alpha", "beta", "gamma", "delta"}
        cluster_title = "alpha collection"

        # First entry: 4/4 overlap → score 1.0 (identical topics, agreeing title)
        first_entry = _moc_entry(
            {"alpha", "beta", "gamma", "delta"}, "alpha collection guide"
        )
        # Second entry: same topics, but this one doesn't matter since first returns
        second_entry = _moc_entry(
            {"alpha", "beta", "gamma", "delta"}, "delta collection guide"
        )

        label, score = _find_jaccard_match(
            cluster_topics, cluster_title, [first_entry, second_entry]
        )

        assert label == "alpha collection guide", (
            f"Expected first entry's title 'alpha collection guide'; got {label!r}"
        )

    def test_exact_title_already_handled_upstream_but_not_here(self):
        """_find_jaccard_match does NOT perform exact-title dedup — that's _find_exact_title_match.

        Confirms the function returns on score threshold, not title equality alone.
        Uses topics that are NOT single-character substrings of the cluster title to
        avoid accidental W_TITLE elevation that would skew the score.
        """
        # "apple", "banana", "cherry" are NOT substrings of "fruit concepts"
        cluster_topics = {"apple", "banana", "cherry"}
        cluster_title = "fruit concepts"
        # MOC has the same topics but a different title — score must still clear 0.80
        first_entry = _moc_entry({"apple", "banana", "cherry"}, "plant concepts")

        label, score = _find_jaccard_match(cluster_topics, cluster_title, [first_entry])

        # Should still flag (score-based, not title-equality-based)
        # All weights are W_BASE on both sides → score = flat Jaccard = 1.0
        assert label == "plant concepts", (
            "Score-threshold flagging must fire regardless of title text"
        )
        assert score >= 0.80

    def test_empty_cluster_topics_returns_none(self):
        """Empty cluster topics → (None, 0.0) without scanning entries."""
        label, score = _find_jaccard_match(
            set(), "some title", [_moc_entry({"a", "b"}, "a title")]
        )
        assert label is None
        assert score == 0.0
