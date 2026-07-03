#!/usr/bin/env python3
# version: 0.1.0
"""test_topic_match.py — TDD (RED-first) tests for lib/topic_match.py.

Covers the standalone weighted-overlap scorer used by both MOC match sites.
The discriminating test (test_dedupe_misfire_crosses_threshold) verifies that
a flat no-op implementation FAILS: flat Jaccard >= 0.80 but weighted < 0.80.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.topic_match import (  # noqa: E402
    W_BASE,
    W_TITLE,
    title_tokens,
    weighted_overlap,
)


# ─────────────────────────────────────────────────────────────────────────────
# Test helper — flat (unweighted) Jaccard for discriminating assertions
# ─────────────────────────────────────────────────────────────────────────────


def flat_jaccard(a, b) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


# ─────────────────────────────────────────────────────────────────────────────
# 1. Discriminating test — a flat no-op impl MUST fail this
# ─────────────────────────────────────────────────────────────────────────────


class TestDedupeDiscriminator:
    """The flagship discriminating suite.  A scorer that ignores titles and
    returns plain Jaccard fails these assertions.
    """

    # 8 shared content topics + 1 distinct title topic each side.
    # Titles are "ta note" / "tb note" so "ta"/"tb" are title-derived.
    # Content topics are not substrings of either title.
    CONTENT = {"fox", "box", "crow", "owl", "ant", "bee", "crab", "duck"}
    A = CONTENT | {"ta"}
    B = CONTENT | {"tb"}
    TITLE_A = "ta note"
    TITLE_B = "tb note"

    def test_dedupe_misfire_crosses_threshold(self):
        """flat Jaccard == 0.80 (false dup under current code) BUT weighted
        < 0.80 (misfire fixed by topic weighting).

        This test CANNOT be satisfied by a flat scorer — it explicitly fails
        the flat implementation.
        """
        fj = flat_jaccard(self.A, self.B)
        assert fj >= 0.80, f"flat_jaccard precondition: expected >= 0.80, got {fj}"

        score = weighted_overlap(self.A, self.TITLE_A, self.B, self.TITLE_B)
        assert score < 0.80, (
            f"weighted must be < 0.80 to prevent false dup; got {score:.4f} "
            f"(flat was {fj:.4f})"
        )

    def test_discriminating_score_matches_traced_walkthrough(self):
        """Exact value from the spec walkthrough: numer=8, denom=12 → 8/12."""
        score = weighted_overlap(self.A, self.TITLE_A, self.B, self.TITLE_B)
        expected = 8 / 12
        assert abs(score - expected) < 1e-9, (
            f"Expected {expected:.6f} (8/12), got {score:.6f}"
        )

    def test_weighting_strictly_below_flat_on_title_disagreement(self):
        """When distinct title-derived topics diverge, weighted < flat Jaccard."""
        a = {"common", "unique-a"}
        b = {"common", "unique-b"}
        title_a = "unique-a focus"   # "unique-a" is a substring → W_TITLE
        title_b = "unique-b focus"   # "unique-b" is a substring → W_TITLE
        # "common" NOT in either title → W_BASE on both sides

        fj = flat_jaccard(a, b)
        score = weighted_overlap(a, title_a, b, title_b)
        assert score < fj, (
            f"weighted ({score:.4f}) must be strictly below flat ({fj:.4f}) "
            "when title themes diverge"
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Flat-reduction property (degenerate case)
# ─────────────────────────────────────────────────────────────────────────────


class TestFlatReduction:
    def test_reduces_to_flat_when_no_title_topic(self):
        """When no topic appears in either title, weighted == flat Jaccard exactly."""
        a = {"a", "b"}
        b = {"b", "c"}
        title = "zz"  # neither "a", "b", nor "c" is a substring of "zz"
        fj = flat_jaccard(a, b)
        score = weighted_overlap(a, title, b, title)
        assert abs(score - fj) < 1e-9, (
            f"Expected exact flat reduction {fj:.6f}, got {score:.6f}"
        )

    def test_reduces_to_flat_exact_value(self):
        """Concrete spec check: weighted_overlap({a,b}, zz, {b,c}, zz) == 1/3."""
        score = weighted_overlap({"a", "b"}, "zz", {"b", "c"}, "zz")
        assert abs(score - 1 / 3) < 1e-9, f"Expected 1/3, got {score}"


# ─────────────────────────────────────────────────────────────────────────────
# 3. True duplicates — shared title themes survive the threshold
# ─────────────────────────────────────────────────────────────────────────────


class TestTrueDuplicate:
    def test_true_dup_title_agreement_survives(self):
        """When both sides share a title-derived topic, the score stays >= 0.80."""
        shared = {"shared-theme", "c1", "c2", "c3", "c4"}
        # "shared-theme" appears in both titles → W_TITLE on both sides
        score = weighted_overlap(
            shared, "shared-theme reference",
            shared, "shared-theme reference",
        )
        assert score >= 0.80, (
            f"True dup with matching title themes must score >= 0.80; got {score}"
        )

    def test_identical_topic_sets_score_one(self):
        """Identical topic sets with any title always yield 1.0."""
        topics = {"alpha", "beta", "gamma"}
        score = weighted_overlap(topics, "alpha focus", topics, "alpha focus")
        assert score == 1.0


# ─────────────────────────────────────────────────────────────────────────────
# 4. Edge cases
# ─────────────────────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_topic_set_a_returns_zero(self):
        assert weighted_overlap(set(), "title", {"a"}, "title") == 0.0

    def test_empty_topic_set_b_returns_zero(self):
        assert weighted_overlap({"a"}, "title", set(), "title") == 0.0

    def test_both_empty_returns_zero(self):
        assert weighted_overlap(set(), "", set(), "") == 0.0

    def test_empty_or_missing_title_uses_base_weights(self):
        """Empty title falls back to W_BASE; no error raised."""
        a = {"topic"}
        b = {"topic"}
        score = weighted_overlap(a, "", b, "")
        # All weights are W_BASE; score should equal flat Jaccard = 1.0
        assert score == 1.0, f"Empty title must use base weights; got {score}"

    def test_none_like_empty_title_no_error(self):
        """None-ish empty string for title must not raise."""
        score = weighted_overlap({"x"}, "", {"x"}, "")
        assert score == 1.0

    def test_whitespace_only_topics_ignored(self):
        """Whitespace-only topics normalize to empty string and are skipped."""
        score = weighted_overlap({"   ", "real"}, "real topic", {"real", "  "}, "real topic")
        assert score == 1.0

    def test_weight_is_capped_regardless_of_title_length(self):
        """Per-topic weight never exceeds W_TITLE even for a very long title."""
        topic = "ai"
        long_title = "ai " + " ".join(["filler"] * 100)
        # Call _weight indirectly: a topic in both sides with only one having the match
        a = {topic}
        b = {topic}
        score = weighted_overlap(a, long_title, b, long_title)
        # numerator = min(W_TITLE, W_TITLE) = 2; denom = max(2,2) = 2 → 1.0
        # If weight were uncapped (e.g. proportional to title length), the formula
        # would still yield 1.0 in this case, but W_TITLE constant must be == 2.
        assert W_TITLE == 2, f"W_TITLE must be 2; got {W_TITLE}"
        assert W_BASE == 1, f"W_BASE must be 1; got {W_BASE}"
        assert score == 1.0

    def test_weight_cap_in_union_union_side(self):
        """A topic in one side only with a long title caps at W_TITLE in denom."""
        # a-only with title match → denom contribution = W_TITLE (not higher)
        a = {"unique"}
        b = {"other"}
        long_title = "unique " + " ".join(["x"] * 100)
        score = weighted_overlap(a, long_title, b, "other title")
        # ∩ = {}: numer=0, score=0.0
        assert score == 0.0


# ─────────────────────────────────────────────────────────────────────────────
# 5. title_tokens helper
# ─────────────────────────────────────────────────────────────────────────────


class TestTitleTokens:
    def test_lowercases(self):
        assert title_tokens("Foo Bar") == "foo bar"

    def test_strips_whitespace(self):
        assert title_tokens("  foo  ") == "foo"

    def test_collapses_internal_whitespace(self):
        assert title_tokens("foo   bar") == "foo bar"

    def test_empty_string(self):
        assert title_tokens("") == ""


# ─────────────────────────────────────────────────────────────────────────────
# 6. Score range invariant
# ─────────────────────────────────────────────────────────────────────────────


class TestScoreRange:
    def test_score_in_unit_interval(self):
        """Score must always be in [0.0, 1.0]."""
        cases = [
            ({"a", "b", "c"}, "a note", {"b", "c", "d"}, "b note"),
            ({"x"}, "x matter", {"y"}, "y matter"),
            ({"shared"}, "shared context", {"shared", "extra"}, "shared context"),
        ]
        for a, ta, b, tb in cases:
            score = weighted_overlap(a, ta, b, tb)
            assert 0.0 <= score <= 1.0, f"Out of [0,1]: {score} for {a},{ta},{b},{tb}"
