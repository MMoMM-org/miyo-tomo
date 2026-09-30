#!/usr/bin/env python3
# version: 0.3.0
"""test_038_decision_inventory_join.py — the two-sided join test for
suggestions-decision-inventory.json (spec 038 Phase 1, T1.2).

ADR-7's inventory is a hand-written registry, and a hand-written registry
drifts unless something checks it from BOTH sides:

  SCHEMA SIDE  — every field suggestions-wire.schema.json marks Editable must
                 have a row (a marker with no row means a decision reaches the
                 wire with no vendored consumer able to discover it, the #140
                 class this spec mirrors from Hashi's own guard).
  PARSER SIDE  — every control literal suggestion-parser.py actually
                 recognises must be either in some row's `parser_label` or in
                 an explicit, justified-absence list (a control the parser
                 recognises with no row means the inventory is lying about
                 what the markdown offers).

The join key is `parser_label` (T1.1b), never `markdown_control` prose and
never `wire_field` — D24's `wire_field` is null, and the SCHEMA side's own
correspondence is counted (marked-field count vs. wire-backed-row count), not
matched by string path, for the same reason: a path-string join has no answer
for the one row that has no path.

THE FIRST RUN IS EXPECTED TO PASS. The inventory, the schema and the 23
markers are already correct and reviewed (T1.1/T1.1b); this file's RED comes
from the five deliberate injections below, run against in-memory fixtures —
never against the real schema or inventory files, which this test never
mutates. Do not read a green first run as evidence the test is weak; read the
five reddened injections as the evidence.

Measured 2026-09-30 (do not "correct" these to agree with each other — they
are not supposed to):
  - the parser's subject-filtered AST harvest yields 61 literals
  - the inventory carries 34 distinct `parser_label` literals
  - 31 of the 61 are legitimately absent from every row (see ABSENCE_RULES)
  - the wire schema marks 23 fields Editable

A NOTE ON THE SCHEMA-SIDE MATCH PREDICATE: the plan text for this task
describes the marker as a description "beginning `Editable — ` [em dash]".
Measured: only 22 of the 23 marked fields actually begin with that exact
string — `proposed_mocs[].tags` reads bare `"Editable."`, no dash. Using the
literal em-dash prefix yields 22, breaching the specified floor of 23 and
disagreeing with T1.1b's own already-committed, already-green
`test_wire_schema_marks_exactly_23_editable_fields`, which matches on
`description.startswith("Editable")` (no dash). This file mirrors T1.1b's
broader predicate for that reason — consistency with the existing count, and
the floor is actually reachable — rather than the plan text's narrower one.
Flagged for the record, not fixed: the wire schema is off-limits for editing
here regardless of which predicate is "right".

KNOWN LIMITATIONS (deliberate, not to be fixed by this test):
  1. This catches a *missing* row, not a *wrong* one. A row whose `wire_field`
     names the wrong path still passes — the consumer's own join (Hashi's
     editable-field-coverage.test.ts) catches that from the other side.
  2. This catches a newly added LITERAL-matched control, not a
     pattern-matched one. `RE_DAILY_LOG_LINE` matches one line and yields
     time, position and content together, so the literal `"—"` keys D14, D15
     and D16 identically. A fourth decision added to that same regex-matched
     line would find `"—"` already has rows and the join would stay green.
  3. Four row labels cannot be harvested by ANY AST filter over the shapes
     used here, and are simply unguarded by the parser-side direction (they
     already have rows, and the join runs harvested-literal → row, never the
     reverse):
       - `—` (D14/D15/D16) lives inside `RE_DAILY_LOG_LINE`, a regex, not a
         plain comparison.
       - `after_last_line` / `before_first_line` (D15) are set by literal
         assignment / a module-level constant default, not compared against
         one of the six control subjects.
       - `force atomic note` (D18) is compared through
         `cb.group(1).lower()` — a call chain, not a bare subject name.
     Do not contort the extraction to reach these; the plan explicitly
     rejects that (rejected alternatives: hand-written literal list, regex
     over source, function-scoped walk — see plan/phase-1.md T1.2).

TWO GUARDS THAT LOOK REDUNDANT AND ARE NOT (both must remain):
  `test_038_inventory_schema_validation.py`'s
  `test_wire_schema_marks_exactly_23_editable_fields` asserts `== 23` and
  catches a marker being DELETED. This file's `>= 23` floor (inside
  `_assert_schema_side_join`) catches the enumeration silently matching
  NOTHING after a REWORD — a different mutation, in a different file, from a
  different starting predicate. Either is deletable alone; both stay.

CRITERIA 3 AND 4 (`must fail` / `must pass`) ARE EXERCISED ON SYNTHETIC ROWS.
No row in the real inventory currently has `editable: false`, so the
staleness guard and its "legitimate retirement" counterpart can only be
demonstrated against fabricated rows appended to a copy of the real row list.
They model future rows that do not exist yet — the exemption cannot be
proven honest until a real control is retired, and that is the point of
writing the proof now rather than when the first one is.

Spec: docs/XDD/specs/038-every-editable-decision-reaches-the-wire/
Ref: PRD/F4; SDD/ADR-7
"""
from __future__ import annotations

import ast
import copy
import json
import re
import sys
from pathlib import Path

import pytest

_DEPS = "/tmp/claude/py_deps"
if Path(_DEPS).is_dir() and _DEPS not in sys.path:
    sys.path.insert(0, _DEPS)

TESTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TESTS_DIR.parent
INVENTORY_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-decision-inventory.json"
WIRE_SCHEMA_PATH = REPO_ROOT / "tomo" / "schemas" / "suggestions-wire.schema.json"
PARSER_PATH = REPO_ROOT / "tomo" / "scripts" / "suggestion-parser.py"

FLOOR_HARVESTED_LITERALS = 61
FLOOR_SCHEMA_MARKED_FIELDS = 23


# ---------------------------------------------------------------------------
# Parser-side harvest: Python's stdlib `ast`, filtered by comparison SUBJECT
# (what is being compared), not by which function it sits in — measured to
# be the only filter that removes the noise (an unscoped walk yields 78;
# scoping to the five control-recognition functions still yields ~70).
# ---------------------------------------------------------------------------

# The parser's control-recognition subjects — every local the parser compares
# a literal against when recognising a checkbox label or a field-line key.
CONTROL_SUBJECTS = {"text_lower", "key", "label", "cb_text", "text", "stripped"}


def _string_constant(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_control_subject(node: ast.AST) -> bool:
    return isinstance(node, ast.Name) and node.id in CONTROL_SUBJECTS


def _harvest_control_literals(source: str) -> set[str]:
    """Harvest string literals compared against a control subject.

    Shapes recognised, for any of the six ``CONTROL_SUBJECTS`` (not only the
    one subject each example below happens to show):
      - ``"x" in text_lower``          — literal `in` subject
      - ``key == "x"``                 — subject `==` literal (either order)
      - ``key in ("x", "y")``          — subject `in` a tuple/list of literals
      - ``label.startswith("x")``      — subject`.startswith(literal)`
    """
    tree = ast.parse(source)
    found: set[str] = set()

    class _Visitor(ast.NodeVisitor):
        def visit_Compare(self, node: ast.Compare) -> None:
            left = node.left
            for op, comparator in zip(node.ops, node.comparators):
                if isinstance(op, ast.In):
                    lit = _string_constant(left)
                    if lit is not None and _is_control_subject(comparator):
                        found.add(lit)
                    if _is_control_subject(left) and isinstance(comparator, (ast.Tuple, ast.List)):
                        for elt in comparator.elts:
                            elt_lit = _string_constant(elt)
                            if elt_lit is not None:
                                found.add(elt_lit)
                elif isinstance(op, ast.Eq):
                    if _is_control_subject(left):
                        lit = _string_constant(comparator)
                        if lit is not None:
                            found.add(lit)
                    if _is_control_subject(comparator):
                        lit = _string_constant(left)
                        if lit is not None:
                            found.add(lit)
                left = comparator
            self.generic_visit(node)

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            if (
                isinstance(func, ast.Attribute)
                and func.attr == "startswith"
                and _is_control_subject(func.value)
            ):
                for arg in node.args:
                    lit = _string_constant(arg)
                    if lit is not None:
                        found.add(lit)
            self.generic_visit(node)

    _Visitor().visit(tree)
    return found


# ---------------------------------------------------------------------------
# Justified absences: the 31 currently-harvested literals with no row, as
# rules plus a few specifics rather than 31 hand-written entries. Grouped and
# commented per group so a future reader can see WHY each is here — and
# `test_absence_rules_never_shadow_a_real_control_label` proves none of them
# is over-broad enough to swallow an actual `parser_label` entry.
# ---------------------------------------------------------------------------

# Structural markers: section/heading/field-line scaffolding, never a control
# a user ticks or retypes. "- Time:" is deliberately NOT here — it is D14's
# real parser_label, so it must be found by a row, not excused by a rule.
_STRUCTURAL_FIELD_LINE_LABELS = {"- Source:", "- Position:", "- Reason:"}


def _is_structural_marker(literal: str) -> bool:
    return (
        literal.startswith("#")
        or literal.startswith("**Possible")  # block headers, not "**Placement:**" (D23's control)
        or literal in _STRUCTURAL_FIELD_LINE_LABELS
    )


# Option values the parser matches against — real strings in the markdown,
# but naming a CHOICE, not a control someone toggles or retypes.
_OPTION_VALUE_LITERALS = {
    "keep", "preserve", "behalten", "related",
    "other sections in this moc", "supporting items", "placement", "items",
    ",", "- ", "[",
}


def _is_option_value(literal: str) -> bool:
    return literal in _OPTION_VALUE_LITERALS


# Read-only field keys: the harvest correctly finding non-editable fields,
# including the dead `classification` branch this phase recorded in the
# backlog (it is parsed but never surfaces on the wire).
_READ_ONLY_FIELD_KEYS = {
    "summary", "classification", "source", "type", "attachments",
    "doc_type:", "tomo:",
}


def _is_read_only_field_key(literal: str) -> bool:
    return literal in _READ_ONLY_FIELD_KEYS


ABSENCE_RULES: tuple[tuple[str, "callable[[str], bool]"], ...] = (
    ("structural marker", _is_structural_marker),
    ("option value, not a control label", _is_option_value),
    ("read-only field key", _is_read_only_field_key),
)


def _is_justified_absence(literal: str) -> bool:
    return any(rule(literal) for _, rule in ABSENCE_RULES)


# ---------------------------------------------------------------------------
# Schema side: count of `Editable`-marked fields vs. count of rows that
# actually carry a wire path. No field-path string matching (that would be
# joining on `wire_field`, which D24's null value forbids) — a count
# correspondence, floored so a reword cannot silently match nothing.
# ---------------------------------------------------------------------------


def _count_editable_marked_descriptions(node: object) -> int:
    count = 0

    def walk(n: object) -> None:
        nonlocal count
        if isinstance(n, dict):
            description = n.get("description")
            if isinstance(description, str) and description.startswith("Editable"):
                count += 1
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for item in n:
                walk(item)

    walk(node)
    return count


def _wire_backed_editable_row_count(rows: list[dict]) -> int:
    return sum(
        1 for row in rows
        if row.get("editable") is True and row.get("wire_field") is not None
    )


def _assert_schema_side_join(schema_doc: dict, rows: list[dict]) -> None:
    marked = _count_editable_marked_descriptions(schema_doc)
    assert marked >= FLOOR_SCHEMA_MARKED_FIELDS, (
        f"only {marked} wire-schema field(s) marked Editable (floor "
        f"{FLOOR_SCHEMA_MARKED_FIELDS}) — a reworded marker may be silently "
        "matching nothing"
    )
    backed = _wire_backed_editable_row_count(rows)
    assert backed == marked, (
        f"{marked} schema field(s) marked Editable but only {backed} "
        "inventory row(s) carry a non-null wire_field — a marked field has "
        "no row"
    )


def _reword_one_editable_marker(node: object) -> bool:
    """Mutate the first Editable-marked description so it no longer matches.

    DFS, in place, on a fixture already `copy.deepcopy`'d by the caller.
    Returns True iff a description was rewritten (used to assert the fixture
    setup itself did not silently no-op).
    """
    if isinstance(node, dict):
        description = node.get("description")
        if isinstance(description, str) and description.startswith("Editable"):
            node["description"] = "Read-only — " + description
            return True
        for v in node.values():
            if _reword_one_editable_marker(v):
                return True
    elif isinstance(node, list):
        for item in node:
            if _reword_one_editable_marker(item):
                return True
    return False


# ---------------------------------------------------------------------------
# Parser side: every harvested literal must be in some ACTIVE row's
# parser_label, or justified-absent. A retired row's parser_label (if it
# carries one) does not count as coverage — that would let a stale exemption
# quietly "cover" a control it no longer claims to recognise — but a live
# harvested literal appearing there IS reported, as the staleness guard.
# ---------------------------------------------------------------------------


def _active_parser_labels(rows: list[dict]) -> set[str]:
    return {
        literal
        for row in rows
        if row.get("editable") is True
        for literal in row.get("parser_label", [])
    }


def _assert_parser_side_join(harvested: set[str], rows: list[dict]) -> None:
    active_labels = _active_parser_labels(rows)
    uncovered = sorted(
        literal for literal in harvested
        if literal not in active_labels and not _is_justified_absence(literal)
    )
    assert not uncovered, (
        f"harvested literal(s) with no row and no justified absence: {uncovered}"
    )

    stale = sorted(
        row["id"] for row in rows
        if row.get("editable") is False
        and any(literal in harvested for literal in row.get("parser_label") or [])
    )
    assert not stale, (
        f"row(s) marked retired (editable: false) but parser control still "
        f"live: {stale}"
    )


def _synthetic_row(**overrides: object) -> dict:
    row: dict = {
        "id": "D99",
        "markdown_control": "Synthetic row, injection test only.",
        "wire_field": None,
        "editable": True,
        "parser_label": ["placeholder-literal"],
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# Fixtures — real artefacts, loaded once per module.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def wire_schema_doc() -> dict:
    return json.loads(WIRE_SCHEMA_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def inventory_rows() -> list[dict]:
    doc = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    return doc["decisions"]


@pytest.fixture(scope="module")
def harvested_literals() -> set[str]:
    return _harvest_control_literals(PARSER_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Floors — pinned so a silent extraction failure fails loudly rather than
# vacuously satisfying every assertion below it.
# ---------------------------------------------------------------------------


def test_parser_harvest_meets_the_measured_floor(harvested_literals: set[str]) -> None:
    assert len(harvested_literals) >= FLOOR_HARVESTED_LITERALS


# ---------------------------------------------------------------------------
# Real artefacts: expected to PASS on the first run (see module docstring).
# ---------------------------------------------------------------------------


def test_real_artefacts_schema_side_join_passes(
    wire_schema_doc: dict, inventory_rows: list[dict]
) -> None:
    _assert_schema_side_join(wire_schema_doc, inventory_rows)


def test_real_artefacts_parser_side_join_passes(
    inventory_rows: list[dict], harvested_literals: set[str]
) -> None:
    _assert_parser_side_join(harvested_literals, inventory_rows)


def test_absence_rules_never_shadow_a_real_control_label(inventory_rows: list[dict]) -> None:
    """The consumer's own honesty check, mirrored: prove the absence rules
    are not over-broad by asserting none of them matches a literal a row
    actually claims as its `parser_label`. A rule that did would silently
    re-open the hole this whole file exists to close."""
    row_labels = {
        literal for row in inventory_rows for literal in row.get("parser_label", [])
    }
    shadowed = sorted(literal for literal in row_labels if _is_justified_absence(literal))
    assert not shadowed, (
        f"absence rule(s) would swallow real control label(s): {shadowed}"
    )


# ---------------------------------------------------------------------------
# The five injections (PRD/F4). Each fabricates its failure in a fixture —
# never in the real schema or inventory files — and demonstrates the result
# by pytest node id, per the task's own instruction to report every one.
# ---------------------------------------------------------------------------


def test_injection_a_marked_schema_field_with_no_row_fails(
    wire_schema_doc: dict, inventory_rows: list[dict]
) -> None:
    """(a) Drop D05 (suggestions[].title, a wire-backed row) from a COPY of
    the real rows. The wire schema is untouched — title stays marked Editable
    — so wire-backed-row-count drops to 22 against a still-23 marked count,
    and the equality check inside _assert_schema_side_join fails."""
    dropped_row = next((row for row in inventory_rows if row["id"] == "D05"), None)
    assert (
        dropped_row is not None
        and dropped_row.get("editable") is True
        and dropped_row.get("wire_field") is not None
    ), (
        'fixture premise: "D05" must exist in the real inventory as an '
        "editable, wire-backed row for dropping it to actually reduce the "
        "backed count below the marked count — if this fails, pick a "
        "different wire-backed row to drop, rather than loosen the pin"
    )
    mutated_rows = [row for row in inventory_rows if row["id"] != "D05"]
    with pytest.raises(AssertionError, match=re.escape("a marked field has no row")):
        _assert_schema_side_join(wire_schema_doc, mutated_rows)


def test_injection_b_unmapped_harvested_literal_fails(inventory_rows: list[dict]) -> None:
    """(b) A harvested literal in neither a row nor the absence list. Rather
    than editing the real parser to invent a new control string, the join
    takes a harvested-literal SET as input — so inject directly into a copy
    of that set, never into suggestion-parser.py."""
    injected_literal = "zzz-unmapped-control-literal"
    assert injected_literal not in _active_parser_labels(inventory_rows), (
        f'fixture premise: "{injected_literal}" must not already be a live '
        "parser_label on some editable row — this test models a harvested "
        "literal with genuinely no row, so if this fails, pick a literal "
        "that truly has none, rather than loosen the pin"
    )
    assert not _is_justified_absence(injected_literal), (
        f'fixture premise: "{injected_literal}" must not be absorbed by any '
        "absence rule — this test models a harvested literal with no row AND "
        "no excuse, so if a future absence rule grows broad enough to "
        "swallow it, pick a literal that still isn't, rather than loosen "
        "the pin"
    )
    injected = _harvest_control_literals(PARSER_PATH.read_text(encoding="utf-8"))
    injected.add(injected_literal)
    with pytest.raises(AssertionError, match=re.escape("no row and no justified absence")):
        _assert_parser_side_join(injected, inventory_rows)


def test_injection_c_stale_exemption_fails(
    inventory_rows: list[dict], harvested_literals: set[str]
) -> None:
    """(c) STALE EXEMPTION — synthetic (see module docstring: no real row is
    editable: false yet). Models a future row retired while its control is
    still live: editable: false, parser_label still names "approve", a
    literal the real harvest still finds. Without the staleness guard this
    row would sit exempt while telling a consumer to delete a control that
    still fires — the opposite of what editable: false exists to say."""
    live_literal = "approve"
    assert live_literal in _active_parser_labels(inventory_rows), (
        f'fixture premise: "{live_literal}" must be a live parser_label on '
        "some editable row in the real inventory — this test models a row "
        "retired while its control is still live, so the injected literal "
        "has to actually be live (otherwise the uncovered assertion fires "
        "instead of the stale one, for an unrelated reason); if this fails, "
        "pick a literal that still is live, rather than loosen the pin"
    )
    stale_row = _synthetic_row(id="D90", editable=False, parser_label=[live_literal])
    mutated_rows = inventory_rows + [stale_row]
    with pytest.raises(AssertionError, match=re.escape("parser control still live")):
        _assert_parser_side_join(harvested_literals, mutated_rows)


def test_injection_d_legitimate_retirement_passes(
    inventory_rows: list[dict], harvested_literals: set[str]
) -> None:
    """(d) LEGITIMATE RETIREMENT — synthetic (see module docstring). Models a
    future row retired because its control is genuinely gone: editable:
    false, parser_label names a literal absent from the current harvest. This
    is the one case where a row legitimately has no live control, and the
    join must let it through without raising."""
    retired_row = _synthetic_row(
        id="D91", editable=False, parser_label=["zzz-retired-control-literal"]
    )
    mutated_rows = inventory_rows + [retired_row]
    _assert_parser_side_join(harvested_literals, mutated_rows)  # must not raise


def test_injection_e_reworded_marker_breaches_the_floor(
    wire_schema_doc: dict, inventory_rows: list[dict]
) -> None:
    """(e) Reword one Editable-marked description (on a deepcopy) so it no
    longer matches. The enumeration drops from 23 to 22 and the FLOOR
    assertion inside _assert_schema_side_join — not the equality check below
    it — is what fails first, proving the floor is load-bearing rather than
    an assertion the equality check would have caught anyway."""
    marked_before = _count_editable_marked_descriptions(wire_schema_doc)
    assert marked_before == FLOOR_SCHEMA_MARKED_FIELDS, (
        f"fixture premise: the real schema must mark exactly "
        f"{FLOOR_SCHEMA_MARKED_FIELDS} field(s) Editable ({marked_before} "
        "found) for rewording one of them to breach the floor rather than "
        "merely narrow it — if this fails, a schema change moved the count "
        "out from under this injection; pick a fixture that actually sits "
        "on the floor, rather than loosen the pin"
    )
    mutated_schema = copy.deepcopy(wire_schema_doc)
    reworded = _reword_one_editable_marker(mutated_schema)
    assert reworded, "fixture setup: no Editable-marked description found to reword"
    with pytest.raises(AssertionError, match=re.escape("may be silently matching nothing")):
        _assert_schema_side_join(mutated_schema, inventory_rows)
