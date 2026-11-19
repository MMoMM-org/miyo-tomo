#!/usr/bin/env python3
# version: 0.2.0
"""test_039_t6_2_vendored_v4.py — the vendored consumer copies carry spec 039's
contract: suggestions wire at v4, and the delete_source `depends_on`
description reading "applied or already in place".

Spec 039 Phase 6 T6.2 (F6-AC6). The consumer (Hashi, c217f66) confirmed it
vendored v4 and that "applied" includes skipped-already.

Mechanisms falsified:
- test_vendored_suggestions_copy_is_byte_identical_to_the_live_v4_schema: a
  vendored copy left at v3 (or hand-edited) differs in bytes.
- test_suggestions_parity_delta_is_empty: implied by the byte test above; it
  states the plan's wording ("the parity delta is empty") as its own assertion.
- test_depends_on_description_says_applied_or_already_in_place: either
  instructions schema still carrying the old "is applied (AND semantics)".
- test_vendored_instructions_copy_is_the_consumer_file:
  a vendored copy taken from OUR live schema (which drifts from the consumer's
  file in unrelated pointers) or any edit changes the hash.

Pinned hash derivation (independent of our files), recompute with:
  git -C ../Hashi show abd92d6:src/schema/instructions.schema.json | shasum -a 256
Spec 046 T6.1 re-vendored the copy from Hashi abd92d6 (pre-release, wire v4),
which carries the "applied or already in place" wording itself, so the
one-string patch of c217f66 is no longer needed.

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

# Hashi abd92d6 src/schema/instructions.schema.json, byte for byte (spec 046 T6.1).
VENDORED_INSTRUCTIONS_SHA256 = (
    "51b80e494493c08ac2f03c90b4002e5ad1dd44d4dac1348b5bd22983bec23c91"
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


def test_vendored_instructions_copy_is_the_consumer_file():
    digest = hashlib.sha256(
        (SCHEMAS_DIR / "hashi-instructions.schema.json").read_bytes()
    ).hexdigest()
    assert digest == VENDORED_INSTRUCTIONS_SHA256
