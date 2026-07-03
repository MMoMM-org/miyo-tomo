#!/usr/bin/env python3
# version: 0.1.0
"""test_analyst_recipe_decision.py — Decision-direction contract for spec-029 Step 4.

Locks the decision that a MOC whose TITLE theme matches the item (title-derived
overlap) must score strictly higher than a MOC with only incidental content-keyword
overlap (no title agreement).

This uses Site 1's Python scorer (weighted_overlap in lib/topic_match.py) as the
decision oracle, per ADR-4 decision-equivalence: the LLM recipe in Step 4 of
inbox-analyst.md (Site 2) must produce equivalent ordering, even though the
numeric values are not required to be identical.

Import pattern mirrors tests/test_topic_match.py — direct sys.path insertion into
tomo/scripts, since topic_match is not an installed package.
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))

from lib.topic_match import weighted_overlap  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# Worked example construction
# ─────────────────────────────────────────────────────────────────────────────
#
# ITEM:  topics={"alpha","beta","gamma"}, title="alpha overview"
#         "alpha" is title-derived on the item side → W_TITLE=2
#
# MOC-A: topics={"alpha","delta"}, title="alpha index"
#         "alpha" is ALSO title-derived on MOC-A side → W_TITLE=2 on both sides
#         Intersection = {"alpha"}; numer = min(2,2) = 2; union = 4 topics
#         denom = max(2,2)[alpha] + max(1,0)[beta] + max(1,0)[gamma]
#                + max(0,1)[delta] = 2+1+1+1 = 5
#         score_A = 2/5 = 0.40
#
# MOC-B: topics={"beta","gamma","zeta","eta"}, title="zeta collection"
#         "beta"/"gamma" shared with item but neither appears in either title
#         (W_BASE=1 on both sides).
#         "zeta" title-derived on MOC-B side (W_TITLE=2); "eta" is a substring
#         of "zeta" in "zeta collection" → also W_TITLE=2 on MOC-B side.
#         Intersection = {"beta","gamma"}; numer = min(1,1)+min(1,1) = 2
#         union = {"alpha","beta","gamma","zeta","eta"}
#         denom = max(2,0)[alpha] + max(1,1)[beta] + max(1,1)[gamma]
#                + max(0,2)[zeta] + max(0,2)[eta] = 2+1+1+2+2 = 8
#         score_B = 2/8 = 0.25
#
# Decision: score_A (0.40) > score_B (0.25) — title-theme alignment wins.

ITEM_TOPICS = {"alpha", "beta", "gamma"}
ITEM_TITLE = "alpha overview"

MOC_A_TOPICS = {"alpha", "delta"}
MOC_A_TITLE = "alpha index"

MOC_B_TOPICS = {"beta", "gamma", "zeta", "eta"}
MOC_B_TITLE = "zeta collection"


class TestAnalystRecipeDecisionDirection:
    """Contract: title-derived overlap wins over incidental content-keyword overlap.

    A scorer that ignores titles and returns plain Jaccard would get this wrong:
    flat Jaccard(item, A) = 1/4 = 0.25, flat Jaccard(item, B) = 2/5 = 0.4
    — the flat scorer would REVERSE the ordering and prefer MOC-B.
    The weighted scorer must prefer MOC-A because 'alpha' is title-derived on
    both sides.
    """

    def test_title_match_beats_incidental_content_overlap(self):
        """MOC-A (title-theme alignment) scores strictly above MOC-B (content only).

        This is the primary ADR-4 decision-equivalence lock:
        the LLM recipe in inbox-analyst Step 4 must produce the same ordering.
        """
        score_a = weighted_overlap(ITEM_TOPICS, ITEM_TITLE, MOC_A_TOPICS, MOC_A_TITLE)
        score_b = weighted_overlap(ITEM_TOPICS, ITEM_TITLE, MOC_B_TOPICS, MOC_B_TITLE)
        assert score_a > score_b, (
            f"MOC-A (title-aligned, score={score_a:.4f}) must beat "
            f"MOC-B (content-only, score={score_b:.4f})"
        )

    def test_score_a_exact_value(self):
        """MOC-A: numer=2 (alpha×2/2), denom=5 → score = 2/5 = 0.40."""
        score_a = weighted_overlap(ITEM_TOPICS, ITEM_TITLE, MOC_A_TOPICS, MOC_A_TITLE)
        assert abs(score_a - 2 / 5) < 1e-9, (
            f"Expected score_A = 2/5 = 0.4, got {score_a:.6f}"
        )

    def test_score_b_exact_value(self):
        """MOC-B: numer=2 (beta+gamma, both W_BASE), denom=8 → score = 2/8 = 0.25.

        'eta' in 'zeta collection' is a true substring match → W_TITLE=2 in denom,
        which is why denom=8 not 7.
        """
        score_b = weighted_overlap(ITEM_TOPICS, ITEM_TITLE, MOC_B_TOPICS, MOC_B_TITLE)
        assert abs(score_b - 2 / 8) < 1e-9, (
            f"Expected score_B = 2/8 = 0.25, got {score_b:.6f}"
        )

    def test_flat_scorer_would_reverse_ordering(self):
        """Document WHY weighted scoring is needed: flat Jaccard reverses the decision.

        flat Jaccard(item, A) = |{alpha}| / |{alpha,beta,gamma,delta}| = 1/4 = 0.25
        flat Jaccard(item, B) = |{beta,gamma}| / |{alpha,beta,gamma,zeta,eta}| = 2/5 = 0.4
        → flat scorer prefers MOC-B, which is the WRONG answer.
        Weighted scoring corrects this by amplifying title-derived topics.
        """
        # flat Jaccard — no title weighting
        def flat_jaccard(a, b):
            sa, sb = set(a), set(b)
            if not sa or not sb:
                return 0.0
            return len(sa & sb) / len(sa | sb)

        flat_a = flat_jaccard(ITEM_TOPICS, MOC_A_TOPICS)
        flat_b = flat_jaccard(ITEM_TOPICS, MOC_B_TOPICS)

        # Assert the reversal — this is the WRONG ordering the unweighted scorer produces
        assert flat_a < flat_b, (
            f"Flat Jaccard: expected flat_A ({flat_a:.4f}) < flat_B ({flat_b:.4f}) "
            "(this reversal is the problem that weighted scoring solves)"
        )

        # Weighted scorer must CORRECT the ordering
        weighted_a = weighted_overlap(ITEM_TOPICS, ITEM_TITLE, MOC_A_TOPICS, MOC_A_TITLE)
        weighted_b = weighted_overlap(ITEM_TOPICS, ITEM_TITLE, MOC_B_TOPICS, MOC_B_TITLE)
        assert weighted_a > weighted_b, (
            f"Weighted scorer must flip the ordering: "
            f"A={weighted_a:.4f} > B={weighted_b:.4f}"
        )
