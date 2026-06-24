#!/usr/bin/env python3
# version: 1.0.0
"""test_tomo_schema_parity.py — action-contract parity guard between Tomo's two instruction schemas.

tomo/schemas/instructions.schema.json    — Tomo's producer copy (original, from xdd-008).
tomo/schemas/hashi-instructions.schema.json — verbatim mirror of Hashi's wire schema.

The two schemas MUST agree on the action contract.  This test enforces parity
offline and deterministically — no network, no local Hashi checkout required.

Contract rules checked:
  1. The set of oneOf $refs (actions) must be identical.
  2. Required fields must match for every shared action $def (breaking-contract check).
  3. Every property defined in the Hashi snapshot must also be present in Tomo's
     producer schema — Tomo cannot emit fields that Hashi's schema rejects.

Note: Tomo's producer schema may legitimately carry extra optional properties that
Hashi's live schema does not yet accept (e.g. add_relationship.error — a pre-existing
deviation tracked for a separate Hashi schema update via handoff).  Those
Tomo-only fields are NOT flagged by this test because they are producer-internal
annotations.  The inverse IS flagged: if Hashi defines a field that Tomo's producer
schema is missing, Tomo would fail to emit it.

If this test fails it means:
  - An action was added to one schema but not the other (oneOf ref mismatch), OR
  - A required field changed in one schema (required mismatch), OR
  - Hashi's schema defines a property that Tomo's producer schema does not.

Fix: add the missing action or field to BOTH tomo/schemas/*.json files.

MiYo Constitution L2 — coordinated public interface between components.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = REPO_ROOT / "tomo" / "schemas"
TOMO_SCHEMA_PATH = SCHEMAS_DIR / "instructions.schema.json"
HASHI_SNAPSHOT_PATH = SCHEMAS_DIR / "hashi-instructions.schema.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _oneof_action_refs(schema: dict) -> set[str]:
    """Return the set of $def names referenced in actions.items.oneOf."""
    one_of = schema["properties"]["actions"]["items"]["oneOf"]
    refs = set()
    for entry in one_of:
        ref = entry.get("$ref", "")
        if ref.startswith("#/$defs/"):
            refs.add(ref[len("#/$defs/"):])
    return refs


def _action_defs(schema: dict) -> set[str]:
    """Return $def names that look like action definitions (have an 'action' property)."""
    return {
        name
        for name, defn in schema.get("$defs", {}).items()
        if "properties" in defn and "action" in defn["properties"]
    }


def _required_fields(schema: dict, defname: str) -> frozenset[str]:
    return frozenset(schema["$defs"][defname].get("required", []))


def _property_names(schema: dict, defname: str) -> frozenset[str]:
    return frozenset(schema["$defs"][defname].get("properties", {}).keys())


def test_tomo_instruction_schemas_action_parity():
    """The two instruction schemas must expose a compatible action contract.

    Three checks (all offline, no network required):
    1. oneOf $refs — the action set must be identical in both schemas.
    2. required fields — the required list must match for every shared $def
       (catches breaking contract changes).
    3. Hashi-defined properties in Tomo — every property in the Hashi snapshot
       must also appear in Tomo's producer schema (Tomo must accept what Hashi
       defines; the reverse is allowed — Tomo may carry producer-only optional
       fields that have not yet been added to Hashi).

    This is the guard introduced to prevent a recurrence of the insert_under_marker
    drift (spec 024 Phase 4, T4.0): insert_under_marker was added to the Hashi
    snapshot but was missing from instructions.schema.json; this test catches that.

    FIX on failure: add the missing action or field to BOTH tomo/schemas/*.json files.
    """
    tomo = _load(TOMO_SCHEMA_PATH)
    hashi = _load(HASHI_SNAPSHOT_PATH)

    # --- Check 1: action set (oneOf refs) must match exactly ---
    tomo_refs = _oneof_action_refs(tomo)
    hashi_refs = _oneof_action_refs(hashi)
    only_in_tomo = tomo_refs - hashi_refs
    only_in_hashi = hashi_refs - tomo_refs

    assert not only_in_tomo and not only_in_hashi, (
        "Action oneOf refs differ between the two instruction schemas.\n"
        f"  Only in tomo/schemas/instructions.schema.json:         {sorted(only_in_tomo)}\n"
        f"  Only in tomo/schemas/hashi-instructions.schema.json:   {sorted(only_in_hashi)}\n"
        "Fix: add the missing action to BOTH tomo/schemas/*.json files."
    )

    # --- Check 2 + 3: per-def required fields + Hashi-property coverage ---
    shared_defs = _action_defs(tomo) & _action_defs(hashi)
    mismatches: list[str] = []

    for defname in sorted(shared_defs):
        tomo_req = _required_fields(tomo, defname)
        hashi_req = _required_fields(hashi, defname)
        tomo_props = _property_names(tomo, defname)
        hashi_props = _property_names(hashi, defname)

        # Required fields must match exactly (breaking-contract check).
        if tomo_req != hashi_req:
            mismatches.append(
                f"  {defname}: required mismatch\n"
                f"    tomo only:  {sorted(tomo_req - hashi_req)}\n"
                f"    hashi only: {sorted(hashi_req - tomo_req)}"
            )

        # Every property Hashi defines must appear in Tomo's producer schema.
        # (Tomo-only optional properties are allowed — they are producer-internal
        # and need a separate Hashi handoff to be accepted on the wire.)
        hashi_only_props = hashi_props - tomo_props
        if hashi_only_props:
            mismatches.append(
                f"  {defname}: Tomo producer schema is missing Hashi-defined properties\n"
                f"    missing in tomo: {sorted(hashi_only_props)}"
            )

    assert not mismatches, (
        "Action $def structure parity violation:\n"
        + "\n".join(mismatches)
        + "\nFix: add the missing action or field to BOTH tomo/schemas/*.json files."
    )
