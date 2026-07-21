#!/usr/bin/env python3
# version: 0.2.0
"""test_state_promoter.py — T3.2 (F-47 Phase 3): state-promoter.py check_tick + flip_state.

Covers:
  AC-3.1  pending-approval + [x] Approved → flip to approved
  AC-3.2  pending-accept   + [x] Accept   → flip to accepted
  AC-3.3  no checkbox ticked             → no flip
  AC-3.4  invalid transition rejected    → no write, lifecycle.transition_rejected logged
  AC-3.5  malformed body                 → warning logged, skip

SDD §Implementation Examples lines 656-707 (flip_state walkthrough + retry-once pattern)
SDD §Complex Logic lines 866-875 (sequential state-promotion algorithm step 5)

Spec: docs/XDD/specs/017-tomo-lifecycle-tags/
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"

sys.path.insert(0, str(SCRIPTS_DIR))


# ---------------------------------------------------------------------------
# Module loader (hyphen in filename → importlib)
# ---------------------------------------------------------------------------

def _load_module(name: str, script_path: Path):
    spec = importlib.util.spec_from_file_location(name, script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = None


def get_mod():
    global _MOD
    if _MOD is None:
        _MOD = _load_module("state_promoter", SCRIPTS_DIR / "state-promoter.py")
    return _MOD


# ---------------------------------------------------------------------------
# Helpers to import lazily (module not created yet → fail at call-time)
# ---------------------------------------------------------------------------

def check_tick(body: str, doc_type: str) -> bool:
    return get_mod().check_tick(body, doc_type)


def flip_state(client, path, doc_type, from_state, to_state, run_id,
               expected_modified=None):
    return get_mod().flip_state(
        client, path, doc_type, from_state, to_state, run_id,
        expected_modified=expected_modified,
    )


def KadoConcurrencyError():
    """Return the KadoConcurrencyError class from the same module import the script uses.

    state-promoter.py does `from lib.kado_client import KadoConcurrencyError`.
    We must use the identical class object so `except KadoConcurrencyError` in the
    script catches exceptions raised in tests — using a second module load would
    produce a different class and the except clause would not trigger.
    """
    mod = get_mod()
    # The module keeps the imported class as a module-level name
    return mod.KadoConcurrencyError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SUGGESTIONS_BODY_APPROVED = """\
---
tomo:
  doc_type: suggestions
  state: pending-approval
---

# Inbox Suggestions — 2026-05-21

- [x] Approved — check this box when you have finished reviewing, then run `/inbox` for Pass 2

## Summary

- Items processed: 1
"""

SUGGESTIONS_BODY_UNCHECKED = """\
---
tomo:
  doc_type: suggestions
  state: pending-approval
---

# Inbox Suggestions — 2026-05-21

- [ ] Approved — check this box when you have finished reviewing, then run `/inbox` for Pass 2

## Summary

- Items processed: 1
"""

SUGGESTIONS_FAN_BODY_APPROVED = """\
---
tomo:
  doc_type: suggestions-fan
  state: pending-approval
---

# Inbox Suggestions — Force-Atomic Resolve — 2026-05-21

- [x] Approved — check this box when you have finished reviewing, then run `/inbox` for Pass 2

## Summary

- Items processed: 1
"""

MOC_PROPOSAL_BODY_ACCEPTED = """\
---
tomo:
  doc_type: moc-proposal
  state: pending-accept
---

# MOC Proposal — 2026-05-21

### MOC01 — Shell & Terminal (MOC)

- [x] Accept

**Title:** `Shell & Terminal (MOC)`
**Location:** `Atlas/200 Maps/`
"""

MOC_PROPOSAL_BODY_UNCHECKED = """\
---
tomo:
  doc_type: moc-proposal
  state: pending-accept
---

# MOC Proposal — 2026-05-21

### MOC01 — Shell & Terminal (MOC)

- [ ] Accept

**Title:** `Shell & Terminal (MOC)`
"""

# garden-audit gates on a top-level [x] Approved box (ADR-1 revised).
GARDEN_AUDIT_BODY_APPROVED = """\
---
tomo:
  doc_type: garden-audit
  state: pending-accept
---

# Knowledge-Garden Audit — 2026-07-21

- [x] Approved — check this box when you've finished reviewing, then run `/inbox` to apply the ticked fixes.

## Summary
"""

GARDEN_AUDIT_BODY_UNCHECKED = """\
---
tomo:
  doc_type: garden-audit
  state: pending-accept
---

# Knowledge-Garden Audit — 2026-07-21

- [ ] Approved — check this box when you've finished reviewing, then run `/inbox` to apply the ticked fixes.

## Summary
"""


# ---------------------------------------------------------------------------
# check_tick tests
# ---------------------------------------------------------------------------

class TestCheckTick:
    def test_suggestions_finds_header_approved(self):
        """Body with checked [x] Approved line → True for suggestions."""
        assert check_tick(SUGGESTIONS_BODY_APPROVED, "suggestions") is True

    def test_suggestions_unchecked_returns_false(self):
        """Unchecked [ ] Approved → False."""
        assert check_tick(SUGGESTIONS_BODY_UNCHECKED, "suggestions") is False

    def test_suggestions_fan_finds_header_approved(self):
        """suggestions-fan uses same [x] Approved pattern."""
        assert check_tick(SUGGESTIONS_FAN_BODY_APPROVED, "suggestions-fan") is True

    def test_moc_proposal_finds_any_accept(self):
        """moc-proposal body with at least one [x] Accept → True."""
        assert check_tick(MOC_PROPOSAL_BODY_ACCEPTED, "moc-proposal") is True

    def test_moc_proposal_unchecked_returns_false(self):
        """moc-proposal body with no ticked Accept → False."""
        assert check_tick(MOC_PROPOSAL_BODY_UNCHECKED, "moc-proposal") is False

    def test_malformed_body_returns_false_and_logs(self, capsys):
        """Garbled or empty body → False; warning appears on stderr."""
        result = check_tick("", "suggestions")
        assert result is False
        captured = capsys.readouterr()
        assert captured.err  # some warning on stderr

    def test_malformed_body_nocrash_on_none_like_input(self, capsys):
        """Completely malformed string (no recognisable structure) → False, no exception."""
        result = check_tick("\x00\x01\x02binary garbage", "suggestions")
        assert result is False

    def test_garden_audit_finds_header_approved(self):
        """garden-audit uses the same [x] Approved pattern (ADR-1 revised)."""
        assert check_tick(GARDEN_AUDIT_BODY_APPROVED, "garden-audit") is True

    def test_garden_audit_unchecked_returns_false(self):
        """Unticked garden-audit Approved box → False (stays pending-accept)."""
        assert check_tick(GARDEN_AUDIT_BODY_UNCHECKED, "garden-audit") is False

    def test_unknown_doc_type_returns_false_and_logs(self, capsys):
        """Unknown doc_type → False; warning on stderr containing 'unknown doc_type'."""
        result = check_tick(SUGGESTIONS_BODY_APPROVED, "totally-unknown-type")
        assert result is False
        captured = capsys.readouterr()
        assert "unknown doc_type" in captured.err


# ---------------------------------------------------------------------------
# flip_state tests
# ---------------------------------------------------------------------------

class TestFlipState:
    def _make_client(self):
        client = MagicMock()
        client.write_frontmatter.return_value = {"path": "inbox/x.md", "modified": 124}
        return client

    def test_calls_write_frontmatter_with_correct_payload(self):
        """flip_state calls write_frontmatter with merge-mode tomo block (state + updated_at only)."""
        client = self._make_client()
        flip_state(
            client,
            "inbox/x.md",
            "suggestions",
            "pending-approval",
            "approved",
            "run-r1",
            expected_modified=123,
        )
        assert client.write_frontmatter.call_count == 1
        args, kwargs = client.write_frontmatter.call_args
        # positional or keyword — normalise
        call_path = args[0] if args else kwargs.get("path")
        call_fm = args[1] if len(args) > 1 else kwargs.get("frontmatter")
        call_mode = kwargs.get("mode") or (args[2] if len(args) > 2 else None)
        call_em = kwargs.get("expected_modified")

        assert call_path == "inbox/x.md"
        assert call_mode == "merge"
        assert call_em == 123
        # tomo block contains state + updated_at ONLY
        tomo = call_fm.get("tomo", call_fm)
        assert tomo["state"] == "approved"
        assert "updated_at" in tomo
        # run_id must NOT be in the merge payload (preserved from existing frontmatter)
        assert "run_id" not in tomo

    def test_rejects_invalid_transition_no_kado_call(self, capsys):
        """Invalid transition (pending-approval → applied) → no write, warning on stderr."""
        client = self._make_client()
        flip_state(
            client,
            "inbox/x.md",
            "suggestions",
            "pending-approval",
            "applied",  # not a valid suggestions transition
            "run-r1",
            expected_modified=100,
        )
        assert client.write_frontmatter.call_count == 0
        captured = capsys.readouterr()
        assert "transition_rejected" in captured.err or "REJECT" in captured.err

    def test_retries_once_on_concurrency_error_idempotent(self):
        """First write raises KadoConcurrencyError; re-read shows target state already reached.

        Expected behaviour (SDD lines 691-696):
          - write_frontmatter raises KadoConcurrencyError (1 call total)
          - read_frontmatter called once to inspect current state
          - current state == to_state → idempotent no-op, no raise
        """
        ConcurrencyError = KadoConcurrencyError()
        client = self._make_client()
        client.write_frontmatter.side_effect = ConcurrencyError("mismatch")
        client.read_frontmatter.return_value = {
            "content": {"tomo": {"state": "approved", "updated_at": "2026-05-21T00:00:00Z"}},
            "modified": 456,
        }

        # Should not raise
        flip_state(
            client,
            "inbox/x.md",
            "suggestions",
            "pending-approval",
            "approved",
            "run-r1",
            expected_modified=100,
        )

        assert client.write_frontmatter.call_count == 1
        assert client.read_frontmatter.call_count == 1

    def test_raises_on_persistent_conflict(self):
        """Both write attempts fail (or re-read shows wrong state) → raises KadoConcurrencyError.

        On first KadoConcurrencyError, read_frontmatter returns a state != to_state
        → retry write with new modified. If second write also raises → re-raise.
        """
        ConcurrencyError = KadoConcurrencyError()
        client = self._make_client()
        client.write_frontmatter.side_effect = ConcurrencyError("mismatch")
        # Re-read shows we're still in from_state, not target state
        client.read_frontmatter.return_value = {
            "content": {"tomo": {"state": "pending-approval", "updated_at": "t0"}},
            "modified": 456,
        }

        with pytest.raises(Exception):  # KadoConcurrencyError or equivalent
            flip_state(
                client,
                "inbox/x.md",
                "suggestions",
                "pending-approval",
                "approved",
                "run-r1",
                expected_modified=100,
            )

        # Verify that the retry write attempt was made
        assert client.write_frontmatter.call_count == 2

    def test_flip_state_returns_false_on_invalid_transition(self, capsys):
        """Invalid transition returns False (no exception, no write)."""
        client = self._make_client()
        result = flip_state(
            client,
            "inbox/x.md",
            "suggestions",
            "pending-approval",
            "applied",  # invalid
            "run-r1",
            expected_modified=100,
        )
        assert result is False
        assert client.write_frontmatter.call_count == 0
        captured = capsys.readouterr()
        assert "transition_rejected" in captured.err

    def test_flip_state_returns_true_on_success(self):
        """Valid transition returns True."""
        client = self._make_client()
        result = flip_state(
            client,
            "inbox/x.md",
            "suggestions",
            "pending-approval",
            "approved",
            "run-r1",
            expected_modified=100,
        )
        assert result is True
        assert client.write_frontmatter.call_count == 1


# ---------------------------------------------------------------------------
# CLI flip tests
# ---------------------------------------------------------------------------

class TestCLIFlip:
    """Test CLI flip command exit codes and behavior."""

    def test_cli_flip_invalid_transition_exits_1(self):
        """CLI flip with invalid transition exits 1."""
        # Mock KadoClient in the module
        mod = get_mod()
        with patch.object(mod, 'KadoClient') as MockClient:
            client_instance = MagicMock()
            client_instance.read_note.return_value = {"content": ""}
            MockClient.return_value = client_instance

            # Call main CLI with invalid transition
            exit_code = mod.main([
                'flip',
                'inbox/x.md',
                'suggestions',
                'pending-approval',
                'applied',  # invalid transition
                'run-r1',
                '100',
            ])
            assert exit_code == 1

    def test_cli_flip_valid_transition_exits_0(self):
        """CLI flip with valid transition exits 0."""
        mod = get_mod()
        with patch.object(mod, 'KadoClient') as MockClient:
            client_instance = MagicMock()
            client_instance.write_frontmatter.return_value = {"path": "inbox/x.md", "modified": 124}
            MockClient.return_value = client_instance

            # Call main CLI with valid transition
            exit_code = mod.main([
                'flip',
                'inbox/x.md',
                'suggestions',
                'pending-approval',
                'approved',  # valid transition
                'run-r1',
                '100',
            ])
            assert exit_code == 0

    def test_cli_flip_missing_args_exits_1(self):
        """CLI flip with missing arguments exits 1."""
        mod = get_mod()
        # Not enough arguments
        exit_code = mod.main(['flip', 'inbox/x.md', 'suggestions'])
        assert exit_code == 1

    def test_cli_flip_bad_expected_modified_exits_1(self):
        """CLI flip with non-integer expected_modified exits 1."""
        mod = get_mod()
        exit_code = mod.main([
            'flip',
            'inbox/x.md',
            'suggestions',
            'pending-approval',
            'approved',
            'run-r1',
            'not-a-number',
        ])
        assert exit_code == 1
