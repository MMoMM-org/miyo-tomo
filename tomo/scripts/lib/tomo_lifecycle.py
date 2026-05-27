# version: 0.1.0
"""tomo_lifecycle.py — Pure-data state machine for all Tomo-produced doc-types.

ADR-1 (SDD §Architecture Decisions): the state machine is a plain dict-of-dicts
— no class hierarchy, no transitions library, no hidden behaviour. This keeps
the module importable anywhere (stdlib only), trivially auditable, and avoids
coupling state knowledge to any particular producer or consumer.

All five doc-types produced by Tomo are represented:

  source         — inbox source items; captured at Pass-1 dispatch
  suggestions    — Pass-1 analysis output; approved after Pass-2 success
  suggestions-fan— XDD-012 Force-Atomic-Resolve companion; same lifecycle
  moc-proposal   — /moc-propose output; accepted after MOC-consumption
  instructions   — Pass-2 / MOC-consumption output; applied when Hashi is done

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/solution.md §Application Data Models
AC:   AC-3.4 (invalid transition rejected), AC-7.1 (single import point)
"""
from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# STATE_MACHINE
# ---------------------------------------------------------------------------

STATE_MACHINE: dict[str, dict[str, Any]] = {
    "suggestions": {
        "initial": None,
        "states": ["pending-approval", "approved"],
        "transitions": [
            {"from": None, "to": "pending-approval", "trigger": "renderer write"},
            {
                "from": "pending-approval",
                "to": "approved",
                "trigger": "state-promoter after Pass-2 success",
            },
        ],
        "terminal": ["approved"],
    },
    "suggestions-fan": {
        # XDD-012 Force-Atomic-Resolve doc — companion to suggestions; same shape.
        "initial": None,
        "states": ["pending-approval", "approved"],
        "transitions": [
            {
                "from": None,
                "to": "pending-approval",
                "trigger": "suggestions-reducer --fan-resolve write",
            },
            {
                "from": "pending-approval",
                "to": "approved",
                "trigger": "state-promoter after FAN-resolve Pass-2 success",
            },
        ],
        "terminal": ["approved"],
    },
    "moc-proposal": {
        "initial": None,
        "states": ["pending-accept", "accepted"],
        "transitions": [
            {"from": None, "to": "pending-accept", "trigger": "moc-architect write"},
            {
                "from": "pending-accept",
                "to": "accepted",
                "trigger": "state-promoter after MOC Pass-2 success",
            },
        ],
        "terminal": ["accepted"],
    },
    "instructions": {
        "initial": None,
        "states": ["pending-apply", "applied"],
        "transitions": [
            {"from": None, "to": "pending-apply", "trigger": "instruction-builder write"},
            {
                "from": "pending-apply",
                "to": "applied",
                "trigger": "Hashi after last [x] Applied",
            },
        ],
        "terminal": ["applied"],
    },
    "source": {
        # Source items have no outgoing transitions once captured.
        "initial": None,
        "states": ["captured"],
        "transitions": [
            {
                "from": None,
                "to": "captured",
                "trigger": "mark-captured at Pass-1 dispatch",
            }
        ],
        "terminal": ["captured"],
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def validate_transition(
    doc_type: str,
    from_state: str | None,
    to_state: str,
) -> bool:
    """Return True iff (from_state → to_state) is a legal transition for doc_type.

    from_state=None means 'initial state assignment': legal iff to_state equals
    STATE_MACHINE[doc_type]['initial'] target (the first None→<state> row).
    Unknown doc_type always returns False (AC-3.4 guard).
    """
    definition = STATE_MACHINE.get(doc_type)
    if definition is None:
        return False
    for t in definition["transitions"]:
        if t["from"] == from_state and t["to"] == to_state:
            return True
    return False


def is_terminal(doc_type: str, state: str) -> bool:
    """True iff state is in STATE_MACHINE[doc_type]['terminal'].

    Unknown doc_type returns False without raising.
    """
    definition = STATE_MACHINE.get(doc_type)
    if definition is None:
        return False
    return state in definition["terminal"]


def is_pending(state: str) -> bool:
    """True iff state starts with 'pending-'. Doc-type agnostic."""
    return state.startswith("pending-")
