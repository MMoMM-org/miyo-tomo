#!/usr/bin/env python3
# version: 0.1.0
"""Spec 038 T2.4 — a conflict-free wire payload differs from its pre-038 shape
in EXACTLY the two intended ways and no others.

T2.1 moved schema_version "2" -> "3"; T2.2 added the top-level
attachment_conflicts[] array. Nothing else about build_wire_payload's
conflict-free output should have moved. The baseline this test diffs against
is a captured, reproducible fixture (tests/fixtures/038-wire-baseline/), not a
hand-typed expected value -- see the comment on BASELINE below for the
regeneration rule.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "tomo" / "scripts"
BASELINE_PATH = REPO_ROOT / "tests" / "fixtures" / "038-wire-baseline" / "payload.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def _load_render_mod():
    spec = importlib.util.spec_from_file_location(
        "suggestions_render_wire_baseline_diff", SCRIPTS_DIR / "suggestions-render.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_MOD = _load_render_mod()

# This is a FROZEN pre-038 artefact, captured from commit 50d8f1b (the last
# commit before Phase 2 touched either the wire schema or
# suggestions-render.py) by tests/fixtures/038-wire-baseline/generate_baseline.py.
# A diff against it moving is a FINDING about today's build_wire_payload, not a
# maintenance chore. Regenerate it ONLY when the pre-038 reference commit
# itself is deliberately re-chosen -- never because today's payload changed;
# regenerating to make a failure go away silences the exact regression this
# test exists to catch.
BASELINE = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))


def _today_doc() -> dict:
    # Reuse the emit suite's canonical conflict-free fixture so both payloads
    # are built from the same input as the baseline was.
    from test_suggestions_wire_emit import _doc

    return _doc()


def test_conflict_free_payload_differs_from_pre_038_baseline_in_exactly_two_ways():
    today = _MOD.build_wire_payload(_today_doc())

    today_keys = set(today)
    baseline_keys = set(BASELINE)

    added = today_keys - baseline_keys
    removed = baseline_keys - today_keys
    # emit_digest is a hash over the whole payload minus itself, so it
    # necessarily moves whenever ANY field changes -- it is not one of the
    # "two intended ways" and is asserted separately, via reconstruction,
    # below. Exclude it here so the key-set/value-set comparison isolates the
    # two changes this task actually claims.
    changed_values = {
        k
        for k in (today_keys & baseline_keys)
        if k != "emit_digest" and today[k] != BASELINE[k]
    }

    assert added == {"attachment_conflicts"}, (
        f"unexpected added top-level key(s): {added - {'attachment_conflicts'}}"
    )
    assert removed == set(), f"unexpected removed top-level key(s): {removed}"
    assert changed_values == {"schema_version"}, (
        f"unexpected changed top-level value(s): {changed_values - {'schema_version'}}"
    )
    assert today["attachment_conflicts"] == []
    assert BASELINE["schema_version"] == "2"
    assert today["schema_version"] == "3"


def test_digest_reconstructs_from_baseline_plus_only_the_two_intended_changes():
    """Strong form: prove emit_digest covers the new field by RECONSTRUCTION,
    not by observing that it merely changed (which would pass even if an
    unrelated field had been renamed instead)."""
    from lib.render_md import compute_payload_digest

    today = _MOD.build_wire_payload(_today_doc())

    reconstructed = dict(BASELINE)
    reconstructed["schema_version"] = "3"
    reconstructed["attachment_conflicts"] = []

    assert compute_payload_digest(reconstructed) == today["emit_digest"]

    # Negative control: omitting the new key must NOT reproduce today's digest.
    reconstructed_without_new_key = dict(BASELINE)
    reconstructed_without_new_key["schema_version"] = "3"
    assert compute_payload_digest(reconstructed_without_new_key) != today["emit_digest"]
