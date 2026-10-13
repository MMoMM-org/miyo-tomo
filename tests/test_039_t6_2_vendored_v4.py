#!/usr/bin/env python3
# version: 0.1.0
"""test_039_t6_2_vendored_v4.py — the vendored consumer copies carry spec 039's
contract: suggestions wire at v4, and the delete_source `depends_on`
description reading "applied or already in place".

Spec 039 Phase 6 T6.2 (F6-AC6). The consumer (Hashi, c217f66) confirmed it
vendored v4 and that "applied" includes skipped-already.

Mechanisms falsified:
- test_vendored_suggestions_copy_is_byte_identical_to_the_live_v4_schema: a
  vendored copy left at v3 (or hand-edited) differs in bytes.
- test_suggestions_parity_delta_is_empty: a copy that is byte-different but
  structurally stale reports a non-empty structural delta.
- test_depends_on_description_says_applied_or_already_in_place: either
  instructions schema still carrying the old "is applied (AND semantics)".
- test_vendored_instructions_copy_is_the_consumer_file_plus_the_one_string_patch:
  a vendored copy taken from OUR live schema (which drifts from the consumer's
  file in 29 unrelated pointers) or any extra edit changes the hash.

Pinned hash derivation (independent of our files), recompute with:
  git -C ../Hashi show c217f66:src/schema/instructions.schema.json
then replace the single occurrence of `is applied (AND semantics)` with
`is applied or already in place (AND semantics)` and take the sha256.

Spec: docs/XDD/specs/039-attachment-conflict-hardening/plan/phase-6.md (T6.2)
Ref: PRD/F6-AC6
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
sys.path.insert(0, str(REPO_ROOT / "tomo" / "scripts"))

from lib.wire_snapshot_parity import snapshot_parity_delta  # noqa: E402

LIVE_SUGGESTIONS = SCHEMAS_DIR / "suggestions-wire.schema.json"
VENDORED_SUGGESTIONS = SCHEMAS_DIR / "hashi-suggestions-wire.schema.json"
INSTRUCTION_SCHEMAS = [
    SCHEMAS_DIR / "instructions.schema.json",
    SCHEMAS_DIR / "hashi-instructions.schema.json",
]

# Hashi c217f66 src/schema/instructions.schema.json with the one-string patch.
VENDORED_INSTRUCTIONS_SHA256 = (
    "9c9565d08caaa8db4a490cda9278dcafaeaf41c10ebf374fd33f4265b705826f"
)


def test_vendored_suggestions_copy_is_byte_identical_to_the_live_v4_schema():
    assert VENDORED_SUGGESTIONS.read_bytes() == LIVE_SUGGESTIONS.read_bytes()


def test_suggestions_parity_delta_is_empty():
    vendored = json.loads(VENDORED_SUGGESTIONS.read_text(encoding="utf-8"))
    live = json.loads(LIVE_SUGGESTIONS.read_text(encoding="utf-8"))
    assert snapshot_parity_delta(vendored, live) == []


@pytest.mark.parametrize("path", INSTRUCTION_SCHEMAS, ids=lambda p: p.name)
def test_depends_on_description_says_applied_or_already_in_place(path):
    text = path.read_text(encoding="utf-8")
    assert "is applied or already in place (AND semantics)" in text
    assert "is applied (AND semantics)" not in text
    assert "move_asset" in text


def test_vendored_instructions_copy_is_the_consumer_file_plus_the_one_string_patch():
    digest = hashlib.sha256(
        (SCHEMAS_DIR / "hashi-instructions.schema.json").read_bytes()
    ).hexdigest()
    assert digest == VENDORED_INSTRUCTIONS_SHA256
