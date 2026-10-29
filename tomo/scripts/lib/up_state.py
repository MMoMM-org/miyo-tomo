# version: 0.1.0
"""up_state.py — classify a parsed `up` target as absent, valid or broken.

`classify_up_target(target, moc_stems, note_stems)` returns
`(up_state, up_broken_reason)`:

    target None                       → ("absent", None)
    target in moc_stems               → ("valid", None)   — the MOC wins a tie
    target in note_stems (not a MOC)  → ("broken", "not-a-moc")
    target in neither                 → ("broken", "unresolved")

The caller parses the target (`lib/up_parse`) and builds both stem sets from
the data it already holds. Used by moc-tree-builder.py and moc-discovery.py.

Rationale: docs/tomo/scripts/lib/up_state.md
"""
from __future__ import annotations

ABSENT = "absent"
VALID = "valid"
BROKEN = "broken"
NOT_A_MOC = "not-a-moc"
UNRESOLVED = "unresolved"


def classify_up_target(
    target: str | None, moc_stems: set[str], note_stems: set[str]
) -> tuple[str, str | None]:
    """Return (up_state, up_broken_reason) for a parsed `up` target."""
    if target is None:
        return ABSENT, None
    if target in moc_stems:
        return VALID, None
    if target in note_stems:
        return BROKEN, NOT_A_MOC
    return BROKEN, UNRESOLVED
