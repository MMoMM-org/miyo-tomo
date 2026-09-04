#!/usr/bin/env python3
# version: 0.3.0
"""test_garden_audit_registration.py — spec 033 T3.1: registration of the new
`parent_not_moc` check across every site that must know its name.

One assertion per site — a single combined assertion would let one missing
registration hide behind a passing sibling (SDD Registration inventory, nine
must-register sites + one should-register). Sites 2-9 must be GREEN; site 1
(`garden-audit.py`'s `_TIER`) is Phase 2's exclusive responsibility
(T2.2) and is expected RED here until Phase 2 lands — see the class docstring
on TestSite1ParentNotMocTier.

Must-NOT-register site 11 (garden-audit.py's `_FIXABLE`) is covered by Phase
2's own tests, not here. Sites 12 and 13 (garden-audit-render.py's
suggest-targets and enrichment tuples) ARE covered here — see the "structural"
tests below — because the T3.2 addition walk (spec 033) found no behavioural
test can reach them: both tuples are unreachable for `parent_not_moc` while
`_FIXABLE` excludes it, so there is no observable behaviour difference to
assert. See `docs/XDD/specs/033-broken-up-cause-split/README.md` Decisions Log
for the full trace.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _ROOT / "tomo" / "scripts"
_SCHEMAS_DIR = _ROOT / "tomo" / "schemas"

sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_module(name: str, filename: str):
    """Load a hyphen-named script fresh — exercises its module-level code
    (imports, module-scope asserts) on every call, not just on first import.

    Each call site passes a distinct throwaway `name` (`_reg`, `_reg2`, `_reg3`,
    …) rather than sharing one module-level load: garden-audit-stats.py's
    `_CHECKS` assert (site 7) runs at import time, so if two tests in this file
    shared a single loaded module, one missing registration would raise
    `AssertionError` during collection and take out every other test in this
    file with it — exactly the failure this per-site-assertion file exists to
    prevent. Reloading per test keeps each site's failure local to its own test.
    """
    spec = importlib.util.spec_from_file_location(name, _SCRIPTS_DIR / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_schema(filename: str) -> dict:
    return json.loads((_SCHEMAS_DIR / filename).read_text(encoding="utf-8"))


def _minimal_doc_finding(check: str, tier: str, fixable: bool) -> dict:
    return {
        "id": "F01",
        "check": check,
        "tier": tier,
        "fixable": fixable,
        "target": {"path": "Notes/Child.md", "stem": "Child"},
        "detail": {},
    }


def _minimal_doc(findings: list[dict]) -> dict:
    return {
        "run_id": "run-registration-001",
        "generated": "2026-09-03T12:00:00Z",
        "profile": "miyo",
        "findings": findings,
        "reappeared_exclusions": [],
    }


def _minimal_wire(findings: list[dict]) -> dict:
    return {
        "schema_version": "1",
        "generated": "2026-09-03T12:00:00Z",
        "run_id": "run-registration-001",
        "profile": "miyo",
        "emit_digest": "sha256:" + "a" * 64,
        "findings": findings,
    }


# ── Site 1 — garden-audit.py _TIER (Phase 2 owns this, T2.2) ──────────────────

class TestSite1ParentNotMocTier:
    """Phase 2 (T2.2) registers `parent_not_moc` in garden-audit.py's `_TIER`
    dict. This test is intentionally RED until that lands — it is written
    here (Phase 3 test authority per the plan) but the registration itself
    is off-limits to Phase 3 (concurrency constraint: Phase 2 owns
    garden-audit.py exclusively). Do NOT fix, skip, or xfail this test.
    """

    def test_tier_advisory(self):
        mod = _load_module("garden_audit_site1", "garden-audit.py")
        assert mod._TIER["parent_not_moc"] == "advisory"


# ── Site 2 — lib/garden_exclusions.py ALL_CHECK_NAMES ─────────────────────────

def test_site2_all_check_names_includes_parent_not_moc():
    from lib.garden_exclusions import ALL_CHECK_NAMES
    assert "parent_not_moc" in ALL_CHECK_NAMES


# ── Site 3 — garden-audit-doc.schema.json check enum ───────────────────────────

def test_site3_doc_schema_validates_parent_not_moc_finding():
    schema = _load_schema("garden-audit-doc.schema.json")
    doc = _minimal_doc([_minimal_doc_finding("parent_not_moc", "advisory", False)])
    jsonschema.validate(instance=doc, schema=schema)  # raises on failure


# ── Site 4 — garden-audit-wire.schema.json check enum ──────────────────────────

def test_site4_wire_schema_validates_parent_not_moc_finding():
    schema = _load_schema("garden-audit-wire.schema.json")
    wire = _minimal_wire([_minimal_doc_finding("parent_not_moc", "advisory", False)])
    jsonschema.validate(instance=wire, schema=schema)  # raises on failure


# ── Site 5 — garden-audit-configure.py _VALID_CHECKS ───────────────────────────

def test_site5_configure_valid_checks_accepts_parent_not_moc():
    mod = _load_module("garden_audit_configure_reg", "garden-audit-configure.py")
    assert "parent_not_moc" in mod._VALID_CHECKS


# ── Site 6 — garden-audit-render.py _CHECK_LABEL ───────────────────────────────

def test_site6_check_label_exists_and_does_not_read_as_breakage():
    mod = _load_module("garden_audit_render_reg", "garden-audit-render.py")
    label = mod._CHECK_LABEL["parent_not_moc"]
    assert label
    assert "broken" not in label.lower()
    assert "up::" not in label


# ── Site 7 — garden-audit-stats.py _CHECKS (+ import-time assert) ─────────────

def test_site7_stats_checks_includes_parent_not_moc_and_import_succeeds():
    # Loading the module IS the test: garden-audit-stats.py:50 runs
    # `assert set(_CHECKS) == set(ALL_CHECK_NAMES)` at module scope, so a
    # missing registration here raises AssertionError on import, before this
    # function body even runs its own assertion.
    mod = _load_module("garden_audit_stats_reg", "garden-audit-stats.py")
    assert "parent_not_moc" in mod._CHECKS


# ── Site 8 — garden-audit-stats.py _COL_LABEL, exercised via render ───────────

def test_site8_stats_area_table_renders_parent_not_moc_without_keyerror():
    from datetime import date
    mod = _load_module("garden_audit_stats_reg2", "garden-audit-stats.py")
    doc = _minimal_doc([_minimal_doc_finding("parent_not_moc", "advisory", False)])
    # render_stats drives _render_area_table, which indexes _COL_LABEL
    # unconditionally for every name in _CHECKS — a missing entry raises
    # KeyError here, not merely on set-membership checks.
    out = mod.render_stats(doc, None, effective_today=date(2026, 9, 3))
    assert isinstance(out, str) and out  # completed without KeyError


# ── Site 9 — garden-audit-exclusions.schema.json checks-array enum ────────────

def test_site9_exclusions_schema_validates_parent_not_moc_rule():
    schema = _load_schema("garden-audit-exclusions.schema.json")
    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "note", "value": "Notes/Child.md"},
                "checks": ["parent_not_moc"],
                "mode": "permanent",
                "reason": "Deliberately unlinked reference note.",
                "created": "2026-09-03",
            }
        ],
    }
    jsonschema.validate(instance=config, schema=schema)  # raises on failure


# ── Should-register — garden-audit-stats.py stats-local _TIER (consistency) ───

def test_should_register_stats_local_tier_matches_advisory():
    mod = _load_module("garden_audit_stats_reg3", "garden-audit-stats.py")
    assert mod._TIER.get("parent_not_moc") == "advisory"


# ── ADR-4 — registering the check changes what existing exclusion configs do ──
#
# Two consequences, opposite in sign (SDD ADR-4, T3.3):
#   - `checks: all` starts covering `parent_not_moc` with no config edit — correct,
#     no migration needed.
#   - an exclusion that names `broken_up` explicitly does NOT also cover
#     `parent_not_moc` — a finding the user thought they had silenced reappears,
#     in the advisory tier, under the new check name.
# T3.3 step 4 ran this same loader against the live instance config
# (tomo-instance/config/garden-audit-exclusions.yaml) and found both cases are
# real today: 4 of 6 rules use `checks: all` (auto-covered); the `Efforts/` rule
# lists `[broken_up, dead_link, stale_moc]` explicitly and will see reappearance.
# Recorded in the spec README Decisions Log.

def _adr4_note(path: str) -> dict:
    return {"path": path, "tags": []}


def test_adr4_checks_all_covers_parent_not_moc_without_config_changes():
    from lib.garden_exclusions import GardenExclusions

    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "path", "value": "Foo/"},
                "checks": "all",
                "mode": "permanent",
                "reason": "test",
                "created": "2026-09-03",
            }
        ],
    }
    excl = GardenExclusions.from_dict(config)
    assert excl.is_excluded(_adr4_note("Foo/Bar.md"), "parent_not_moc") is True


def test_adr4_explicit_broken_up_exclusion_does_not_cover_parent_not_moc_reappears():
    from lib.garden_exclusions import GardenExclusions

    config = {
        "version": 1,
        "exclusions": [
            {
                "target": {"type": "path", "value": "Foo/"},
                "checks": ["broken_up"],
                "mode": "permanent",
                "reason": "test",
                "created": "2026-09-03",
            }
        ],
    }
    excl = GardenExclusions.from_dict(config)
    note = _adr4_note("Foo/Bar.md")

    # The exclusion still does exactly what it always did for broken_up...
    assert excl.is_excluded(note, "broken_up") is True

    # ...but a broken_up finding on this same note that now reclassifies as
    # parent_not_moc REAPPEARS: the exclusion rule never named the new check,
    # so it does not suppress it. This is the positive assertion the reviewer
    # asked for — not merely "checks doesn't match", but "the finding is
    # visible again".
    reappears = not excl.is_excluded(note, "parent_not_moc")
    assert reappears, (
        "an exclusion naming 'broken_up' explicitly must NOT also suppress "
        "'parent_not_moc' — ADR-4's reappearance case"
    )


# ── Sites 12 & 13 — must-not-register, asserted structurally ──────────────────
#
# T3.2's addition walk (spec 033) found that adding "parent_not_moc" to EITHER
# tuple below produces ZERO test failures anywhere in the suite: both live
# inside code paths gated by `decision is not None`
# (`garden-audit-render.py:527`), and `decision` is attached to a finding only
# when it is fixable — controlled exclusively by `_FIXABLE` (site 11). Since
# `parent_not_moc` is never in `_FIXABLE`, these branches are structurally
# unreachable for it, so there is no BEHAVIOUR to observe and no behavioural
# test can cover them. The realistic regression here is not a behaviour
# change — it is an editor tidying up, noticing "parent_not_moc" missing from
# a check-name list, and adding it for consistency. So these two tests assert
# the tuples' literal CONTENTS directly (via `ast`, reading the real source —
# not a text/string search) rather than any observable behaviour: they go red
# the moment the name is added, regardless of whether the resulting code path
# is reachable. Do not delete these as "pointless string checks" — they are
# the only automated defence these two sites have.

def _check_name_tuples_in(func_name: str) -> list[list[str]]:
    """Every check-name tuple used in an `in (...)` / `not in (...)` test
    inside the named function, found by parsing garden-audit-render.py's real
    source with `ast` (not by importing it — these tuples are literals inside
    function bodies, not module-level constants, so they cannot be imported).
    """
    src = (_SCRIPTS_DIR / "garden-audit-render.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == func_name:
            for sub in ast.walk(node):
                if not isinstance(sub, ast.Compare):
                    continue
                for op, comparator in zip(sub.ops, sub.comparators):
                    if not isinstance(op, (ast.In, ast.NotIn)):
                        continue
                    if not isinstance(comparator, ast.Tuple):
                        continue
                    values = []
                    all_str_const = True
                    for elt in comparator.elts:
                        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                            values.append(elt.value)
                        else:
                            all_str_const = False
                    # Only the check-name tuples, identified by carrying the
                    # four checks every must-not-register site's tuple starts
                    # from — filters out unrelated `in (...)` tests in the
                    # same function without hardcoding a line number.
                    if all_str_const and {
                        "dead_link", "broken_up", "unparented", "orphan"
                    } <= set(values):
                        found.append(values)
    return found


def test_site12_suggest_targets_tuple_excludes_parent_not_moc():
    tuples = _check_name_tuples_in("_render_finding")
    assert tuples, (
        "expected to find the suggest-targets check-name tuple inside "
        "_render_finding — if this function was renamed or the tuple "
        "restructured, update _check_name_tuples_in's target, don't delete "
        "this test"
    )
    for values in tuples:
        assert "parent_not_moc" not in values, (
            "site 12: parent_not_moc must NOT be added to the suggest-targets "
            "tuple in _render_finding — see the module docstring"
        )


def test_site13_enrichment_tuple_excludes_parent_not_moc():
    tuples = _check_name_tuples_in("enrich_report_with_suggestions")
    assert tuples, (
        "expected to find the enrichment check-name tuple inside "
        "enrich_report_with_suggestions — if this function was renamed or "
        "the tuple restructured, update _check_name_tuples_in's target, "
        "don't delete this test"
    )
    for values in tuples:
        assert "parent_not_moc" not in values, (
            "site 13: parent_not_moc must NOT be added to the enrichment "
            "tuple in enrich_report_with_suggestions — see the module "
            "docstring"
        )
