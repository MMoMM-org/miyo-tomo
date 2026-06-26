#!/usr/bin/env python3
# version: 2.1.0
"""test_tomo_schema_parity.py — bidirectional action-contract parity guard between Tomo's two instruction schemas.

tomo/schemas/instructions.schema.json    — Tomo's producer copy (original, from xdd-008).
tomo/schemas/hashi-instructions.schema.json — verbatim mirror of Hashi's wire schema.

The two schemas MUST agree on the action contract.  This test enforces parity
offline and deterministically — no network, no local Hashi checkout required.

Contract rules checked:
  1. The set of oneOf $refs (actions) must be identical, EXCEPT for actions listed in
     MIRROR_ONLY_ACTIONS (actions present in the Hashi mirror but not in Tomo's producer
     because there is no Tomo emitter — the mirror tracks Hashi's full wire surface).
  2. Required fields must match for every shared action $def (breaking-contract check).
  3. Every property defined in the Hashi snapshot must also be present in Tomo's
     producer schema (Hashi ⊆ Tomo) — if Hashi defines a property that Tomo is missing,
     Tomo would fail to emit it and the instruction set would be incomplete.
  4. [NEW — the apply-breaking direction] Every property in Tomo's PRODUCER schema must
     also appear in Hashi's wire schema (Tomo ⊆ Hashi), unless it is explicitly listed
     in PRODUCER_ONLY_PROPS below with a documented reason.  A Tomo-only property that
     reaches Hashi causes the ENTIRE instruction set to be rejected at apply time because
     Hashi's schema has additionalProperties:false on every action $def.

Exception registry (PRODUCER_ONLY_PROPS):
  Properties may appear in the Tomo producer schema but not in Hashi's wire schema for
  exactly two reasons:
    "stripped"  — the property is removed before serialisation and never reaches Hashi.
    "drift"     — a known, tracked divergence; Hashi would reject it if it arrived on the
                  wire.  These are technical debt entries — REMOVE when resolved (either
                  Tomo filters the field before the wire, or Hashi adds the field).

Exception registry (MIRROR_ONLY_ACTIONS):
  Actions may appear in the Hashi mirror schema but not in Tomo's producer schema when
  there is no Tomo emitter.  The mirror faithfully tracks Hashi's full wire surface for
  offline parity testing — not every Hashi action requires a Tomo counterpart.
  Each entry MUST carry a documented reason.  REMOVE when a Tomo emitter is added.

If this test fails it means:
  - An action was added to one schema but not the other (oneOf ref mismatch, not in
    MIRROR_ONLY_ACTIONS), OR
  - A required field changed in one schema (required mismatch), OR
  - Hashi's schema defines a property missing from Tomo's producer schema, OR
  - [NEW] Tomo's producer schema defines a property absent from Hashi's wire schema and
    not listed in PRODUCER_ONLY_PROPS.

Fix: add the missing field to both schemas, OR add an entry to PRODUCER_ONLY_PROPS with
a "stripped" or "drift" reason, OR (for actions) add to MIRROR_ONLY_ACTIONS.

MiYo Constitution L2 — coordinated public interface between components.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

# ---------------------------------------------------------------------------
# Exception registry — Tomo producer-schema properties intentionally absent
# from the Hashi wire schema.  Each entry MUST carry a reason.
#
#   "stripped" — removed before serialisation; never reaches Hashi (safe).
#   "drift"    — a KNOWN unresolved divergence Hashi would reject at apply time.
#                Tracked for resolution.  REMOVE entry when fixed.
# ---------------------------------------------------------------------------
PRODUCER_ONLY_PROPS: dict[tuple[str, str], str] = {
    # Empty — add_relationship.error was resolved: filter_unappliable_relationships
    # removes error-bearing sentinels before the wire (spec 024 follow-up).
}

# ---------------------------------------------------------------------------
# Exception registry — actions present in Hashi's mirror schema but not in
# Tomo's producer schema because there is no Tomo emitter yet.
# The mirror tracks Hashi's full wire surface for offline parity testing.
#
# Each entry: action_name -> reason string.
# REMOVE an entry when a Tomo emitter is added (and add the $def + oneOf ref
# to instructions.schema.json simultaneously).
# ---------------------------------------------------------------------------
MIRROR_ONLY_ACTIONS: dict[str, str] = {
    "replace_section": (
        "no Tomo emitter — parity-only mirror of Hashi's shipped wire surface "
        "(spec 025 ADR-7). Add a Tomo emitter if/when the structured-compose "
        "producer needs to overwrite sections."
    ),
}

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
    """The two instruction schemas must expose a bidirectionally compatible action contract.

    Four checks (all offline, no network required):
    1. oneOf $refs — the action set must be identical in both schemas, EXCEPT for actions
       in MIRROR_ONLY_ACTIONS (Hashi wire surface with no Tomo emitter).
    2. required fields — the required list must match for every shared $def
       (catches breaking contract changes).
    3. Hashi ⊆ Tomo — every property in the Hashi snapshot must also appear in
       Tomo's producer schema (Tomo must be able to emit what Hashi defines).
    4. [NEW] Tomo ⊆ Hashi — every property in Tomo's producer schema must also
       appear in Hashi's wire schema, UNLESS explicitly listed in PRODUCER_ONLY_PROPS
       with a documented reason.  This is the apply-breaking direction: a Tomo-only
       property causes Hashi to reject the entire instruction set at apply time
       (Hashi's additionalProperties:false).  This check is the recurrence guard for
       that class of bug.

    The PRODUCER_ONLY_PROPS registry (module-level) tracks known property exceptions.
    The MIRROR_ONLY_ACTIONS registry (module-level) tracks actions that are present in
    Hashi's wire schema but have no Tomo emitter yet (mirror-tracks-Hashi pattern).

    This guard was introduced in spec 024 Phase 4:
      - T4.0 caught insert_under_marker missing from instructions.schema.json (Hashi ⊆ Tomo).
      - Bidirectional extension (T4.x) catches add_relationship.error present in
        instructions.schema.json but absent from hashi-instructions.schema.json
        (Tomo ⊆ Hashi, the apply-breaking direction).
    Extended in spec 025 Phase 1 (T1.3):
      - MIRROR_ONLY_ACTIONS allows the mirror to faithfully track Hashi's full wire
        surface (e.g. replace_section) without requiring a matching Tomo emitter.

    FIX on failure:
      - For Check 1 (Tomo-only actions): add the missing action to hashi-instructions.schema.json.
      - For Check 1 (Hashi-only actions, not in MIRROR_ONLY_ACTIONS): add to instructions.schema.json
        OR add to MIRROR_ONLY_ACTIONS with a documented reason.
      - For Check 2/3: add the missing action or field to BOTH tomo/schemas/*.json.
      - For Check 4: add the property to Hashi's schema, OR add an entry to
        PRODUCER_ONLY_PROPS in this file with a "stripped" or "drift" reason.
    """
    tomo = _load(TOMO_SCHEMA_PATH)
    hashi = _load(HASHI_SNAPSHOT_PATH)

    # --- Check 1: action set (oneOf refs) must match, modulo MIRROR_ONLY_ACTIONS ---
    tomo_refs = _oneof_action_refs(tomo)
    hashi_refs = _oneof_action_refs(hashi)
    only_in_tomo = tomo_refs - hashi_refs
    # Hashi-only actions that are registered as mirror-only are permitted.
    only_in_hashi_unregistered = (hashi_refs - tomo_refs) - set(MIRROR_ONLY_ACTIONS.keys())

    assert not only_in_tomo, (
        "Action oneOf refs found in tomo/schemas/instructions.schema.json but NOT in the "
        "Hashi mirror (hashi-instructions.schema.json).\n"
        f"  Only in tomo producer: {sorted(only_in_tomo)}\n"
        "Fix: add the missing action to hashi-instructions.schema.json."
    )
    assert not only_in_hashi_unregistered, (
        "Action oneOf refs found in hashi-instructions.schema.json but NOT in Tomo's "
        "producer schema AND NOT registered in MIRROR_ONLY_ACTIONS.\n"
        f"  Unregistered hashi-only: {sorted(only_in_hashi_unregistered)}\n"
        "Fix: add the missing action to instructions.schema.json, OR add to "
        "MIRROR_ONLY_ACTIONS with a documented reason (no Tomo emitter)."
    )

    # --- Checks 2, 3, 4: per-def required fields + bidirectional property coverage ---
    shared_defs = _action_defs(tomo) & _action_defs(hashi)
    mismatches: list[str] = []

    for defname in sorted(shared_defs):
        tomo_req = _required_fields(tomo, defname)
        hashi_req = _required_fields(hashi, defname)
        tomo_props = _property_names(tomo, defname)
        hashi_props = _property_names(hashi, defname)

        # Check 2: required fields must match exactly (breaking-contract check).
        if tomo_req != hashi_req:
            mismatches.append(
                f"  {defname}: required mismatch\n"
                f"    tomo only:  {sorted(tomo_req - hashi_req)}\n"
                f"    hashi only: {sorted(hashi_req - tomo_req)}"
            )

        # Check 3: Hashi ⊆ Tomo — every property Hashi defines must appear in Tomo's
        # producer schema (Tomo must be able to emit what Hashi accepts).
        hashi_only_props = hashi_props - tomo_props
        if hashi_only_props:
            mismatches.append(
                f"  {defname}: Tomo producer schema is missing Hashi-defined properties\n"
                f"    missing in tomo: {sorted(hashi_only_props)}"
            )

        # Check 4 [NEW]: Tomo ⊆ Hashi — every property in Tomo's producer schema must
        # appear in Hashi's wire schema, UNLESS in PRODUCER_ONLY_PROPS.
        # A property that reaches Hashi but is absent from Hashi's schema causes Hashi
        # to reject the whole instruction set (additionalProperties:false).
        tomo_only_props = tomo_props - hashi_props
        unregistered = {
            prop
            for prop in tomo_only_props
            if (defname, prop) not in PRODUCER_ONLY_PROPS
        }
        if unregistered:
            mismatches.append(
                f"  {defname}: Tomo producer schema has properties absent from "
                f"Hashi's wire schema and NOT in PRODUCER_ONLY_PROPS\n"
                f"    unregistered tomo-only: {sorted(unregistered)}\n"
                f"    Fix: add to Hashi's schema OR add to PRODUCER_ONLY_PROPS "
                f"with a 'stripped' or 'drift' reason."
            )

    assert not mismatches, (
        "Action $def structure parity violation:\n"
        + "\n".join(mismatches)
        + "\nFix: see docstring for per-check remediation."
    )
