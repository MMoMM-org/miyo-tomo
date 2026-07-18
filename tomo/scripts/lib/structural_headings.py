# version: 0.1.0
"""structural_headings.py — the shared set of MOC structural/scaffolding headings.

Single source of truth for the #71 structural-heading list, consumed by BOTH the
runtime demotion backstop in suggestions-reducer.py and the offline tuning aid
scripts/analyze-placement-confidence.py. See docs/tomo/scripts/lib/structural_headings.md
for the WHY (spec 023 backstop, ADR-6).
"""
from __future__ import annotations

# Structural / scaffolding headings: these organize a MOC itself rather than name
# a topic, so a content note landing under them is the anti-pattern spec 023
# targets. A note whose best tier-1 fit is one of these is demoted to a new
# section regardless of the LLM's self-assessed fit_confidence.
DEFAULT_STRUCTURAL_HEADINGS = [
    "Content",
    "Contents",
    "Structure",
    "Link MOC",
    "Primer Questions",
    "Processes",
]


def structural_set(extra: list[str] | None = None) -> set[str]:
    """Return the casefolded structural-heading set, optionally extended."""
    return {
        h.strip().casefold()
        for h in DEFAULT_STRUCTURAL_HEADINGS + list(extra or [])
    }


def is_structural(heading: str, structural: set[str] | None = None) -> bool:
    """True when `heading` matches a structural heading (case/whitespace-insensitive)."""
    if structural is None:
        structural = structural_set()
    return heading.strip().casefold() in structural
