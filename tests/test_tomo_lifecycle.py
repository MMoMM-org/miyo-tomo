#!/usr/bin/env python3
# version: 0.1.0
"""test_tomo_lifecycle.py — Tests for the tomo_lifecycle state-machine module.

Covers T1.1 (F-47 Phase 1): validate_transition, is_terminal, is_pending, and
STATE_MACHINE completeness for all 5 doc-types (source, suggestions,
suggestions-fan, moc-proposal, instructions).

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/
AC:   AC-3.4 (invalid transitions rejected), AC-7.1 (single import point)
"""
from __future__ import annotations

import sys
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
LIB_DIR = REPO_ROOT / "tomo" / "scripts" / "lib"

sys.path.insert(0, str(LIB_DIR.parent))  # so `import lib.tomo_lifecycle` works

from lib.tomo_lifecycle import (  # noqa: E402
    STATE_MACHINE,
    is_pending,
    is_terminal,
    validate_transition,
)


# ---------------------------------------------------------------------------
# validate_transition — legal paths
# ---------------------------------------------------------------------------


def test_suggestions_pending_to_approved_legal():
    """suggestions: pending-approval → approved is a legal transition."""
    assert validate_transition("suggestions", "pending-approval", "approved") is True


def test_moc_proposal_pending_to_accepted_legal():
    """moc-proposal: pending-accept → accepted is a legal transition."""
    assert validate_transition("moc-proposal", "pending-accept", "accepted") is True


def test_instructions_pending_to_applied_legal():
    """instructions: pending-apply → applied is a legal transition."""
    assert validate_transition("instructions", "pending-apply", "applied") is True


def test_suggestions_fan_pending_to_approved_legal():
    """suggestions-fan: pending-approval → approved is a legal transition (XDD-012 mirror)."""
    assert validate_transition("suggestions-fan", "pending-approval", "approved") is True


def test_initial_assignment_uses_none_from_state():
    """Initial state assignment: None → initial state is always legal."""
    assert validate_transition("suggestions", None, "pending-approval") is True
    assert validate_transition("suggestions-fan", None, "pending-approval") is True
    assert validate_transition("moc-proposal", None, "pending-accept") is True
    assert validate_transition("instructions", None, "pending-apply") is True
    assert validate_transition("source", None, "captured") is True


# ---------------------------------------------------------------------------
# validate_transition — illegal paths (AC-3.4)
# ---------------------------------------------------------------------------


def test_suggestions_pending_to_applied_rejected():
    """Cross-doc-type transition: suggestions → applied is not a valid suggestions state."""
    assert validate_transition("suggestions", "pending-approval", "applied") is False


def test_source_terminal_no_outgoing():
    """Terminal state source.captured has no outgoing transitions."""
    assert validate_transition("source", "captured", "captured") is False


def test_unknown_doc_type_returns_false():
    """Unknown doc_type is safely rejected (AC-3.4 guard)."""
    assert validate_transition("nonexistent-type", "pending-approval", "approved") is False


def test_wrong_initial_target_rejected():
    """None from-state to non-initial state is rejected."""
    assert validate_transition("suggestions", None, "approved") is False


def test_backward_transition_rejected():
    """Backward / self-loop transitions that are not listed are rejected."""
    assert validate_transition("moc-proposal", "accepted", "pending-accept") is False


# ---------------------------------------------------------------------------
# is_terminal
# ---------------------------------------------------------------------------


def test_is_terminal_all_doctypes():
    """Every doc-type has at least one terminal state and lookup is correct."""
    assert is_terminal("source", "captured") is True
    assert is_terminal("suggestions", "approved") is True
    assert is_terminal("suggestions-fan", "approved") is True
    assert is_terminal("moc-proposal", "accepted") is True
    assert is_terminal("instructions", "applied") is True


def test_is_terminal_pending_states_are_not_terminal():
    """Pending states are not terminal for any doc-type."""
    assert is_terminal("suggestions", "pending-approval") is False
    assert is_terminal("moc-proposal", "pending-accept") is False
    assert is_terminal("instructions", "pending-apply") is False


def test_is_terminal_unknown_doc_type_returns_false():
    """Unknown doc_type never raises — returns False."""
    assert is_terminal("ghost-type", "approved") is False


# ---------------------------------------------------------------------------
# is_pending
# ---------------------------------------------------------------------------


def test_is_pending_returns_true_for_pending_prefix():
    """Any state starting with 'pending-' is considered pending."""
    assert is_pending("pending-approval") is True
    assert is_pending("pending-accept") is True
    assert is_pending("pending-apply") is True


def test_is_pending_returns_false_for_terminal():
    """Terminal states do not start with 'pending-'."""
    assert is_pending("approved") is False
    assert is_pending("accepted") is False
    assert is_pending("applied") is False
    assert is_pending("captured") is False


def test_is_pending_edge_cases():
    """'pending' without a dash and empty string are not pending."""
    assert is_pending("pending") is False
    assert is_pending("") is False


# ---------------------------------------------------------------------------
# STATE_MACHINE completeness
# ---------------------------------------------------------------------------


def test_state_machine_has_all_five_doc_types():
    """STATE_MACHINE must include all 5 doc-types required by the spec."""
    required = {"source", "suggestions", "suggestions-fan", "moc-proposal", "instructions"}
    assert required == set(STATE_MACHINE.keys())


def test_state_machine_entries_have_required_keys():
    """Each STATE_MACHINE entry must have initial, states, transitions, and terminal."""
    for doc_type, definition in STATE_MACHINE.items():
        assert "initial" in definition, f"{doc_type} missing 'initial'"
        assert "states" in definition, f"{doc_type} missing 'states'"
        assert "transitions" in definition, f"{doc_type} missing 'transitions'"
        assert "terminal" in definition, f"{doc_type} missing 'terminal'"


def test_state_machine_terminal_states_are_subset_of_states():
    """Terminal states must be listed in states for every doc-type."""
    for doc_type, definition in STATE_MACHINE.items():
        for terminal_state in definition["terminal"]:
            assert terminal_state in definition["states"], (
                f"{doc_type}: terminal state '{terminal_state}' not in states list"
            )
