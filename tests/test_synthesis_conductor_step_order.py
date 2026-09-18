#!/usr/bin/env python3
# version: 0.1.0
"""test_synthesis_conductor_step_order.py — the coverage audit gates delivery.

`tomo/dot_claude/agents/synthesis-conductor.md` Step 3 used to run:
    3a parse -> 3b render -> 3c upload -> 3d flip source state -> 3e audit

The audit's STRICT stop ("on a coverage mismatch you STOP ... do not continue
to the next doc") only protected documents AFTER the one that failed — by the
time 3e ran, 3c had already uploaded the rendered instructions into the
user's vault (live in Kado) and 3d had already flipped the source doc's
frontmatter state. A live run on 2026-09-18 hit exactly this: the conductor
halted on a coverage mismatch and reported that nothing had been written,
while the instructions were in fact already sitting in the vault at
`state: pending-apply`, reachable by the Hashi plugin before the user ever
read the stop message.

This file pins the fix: the audit now runs BEFORE upload and BEFORE the
state flip, so a STOP actually prevents delivery for the current document
instead of merely apologizing for it after the fact:
    3a parse -> 3b render -> 3c audit -> 3d upload -> 3e flip source state

Tests are RED against the pre-fix ordering (audit last, as `upload-rendered`
then `state-promoter.py flip` then `instructions-diff.py`) and GREEN after
the reorder. This is a structural/text-order assertion, not a runtime
execution test — this agent file has no unit-testable code, it is parsed
and followed by an LLM at runtime, so the position of each script
invocation IN THE FILE is the only thing pytest can verify.

CON-7: fixtures and fakes only. No live vault, no live Kado, no Docker.
"""
from __future__ import annotations

import re
from pathlib import Path

CONDUCTOR = (
    Path(__file__).resolve().parent.parent
    / "tomo"
    / "dot_claude"
    / "agents"
    / "synthesis-conductor.md"
)


def _text() -> str:
    return CONDUCTOR.read_text(encoding="utf-8")


def _first_index(text: str, needle: str) -> int:
    idx = text.find(needle)
    assert idx != -1, f"{needle!r} not found in {CONDUCTOR}"
    return idx


class TestCoverageAuditRunsBeforeDelivery:
    """The audit's invocation must precede both the upload and the state
    flip invocations, in file order — that order is what the conductor
    follows step by step."""

    def test_audit_precedes_upload(self):
        text = _text()
        audit_idx = _first_index(text, "scripts/instructions-diff.py")
        upload_idx = _first_index(text, "scripts/upload-rendered.py")
        assert audit_idx < upload_idx, (
            "the coverage audit (instructions-diff.py) must be invoked "
            "before upload-rendered.py — a mismatch must block delivery, "
            "not follow it"
        )

    def test_audit_precedes_state_flip(self):
        text = _text()
        audit_idx = _first_index(text, "scripts/instructions-diff.py")
        flip_idx = _first_index(text, "scripts/state-promoter.py flip")
        assert audit_idx < flip_idx, (
            "the coverage audit (instructions-diff.py) must be invoked "
            "before state-promoter.py flip — a mismatch must leave the "
            "source doc unconsumed, not mark it approved"
        )

    def test_upload_still_precedes_state_flip(self):
        """The reorder moves only the audit — upload must still happen
        before the state flip, unchanged from the pre-fix ordering."""
        text = _text()
        upload_idx = _first_index(text, "scripts/upload-rendered.py")
        flip_idx = _first_index(text, "scripts/state-promoter.py flip")
        assert upload_idx < flip_idx

    def test_step_letters_match_the_new_order(self):
        """3c is the audit, 3d is upload, 3e is the state flip — the
        letters were relabeled along with the reorder, not left stale."""
        text = _text()
        assert re.search(
            r"#### 3c\s*—\s*Coverage audit", text
        ), "Step 3c must be the coverage audit"
        assert re.search(
            r"#### 3d\s*—\s*Upload rendered files", text
        ), "Step 3d must be the upload"
        assert re.search(
            r"#### 3e\s*—\s*Flip source doc state", text
        ), "Step 3e must be the state flip"
