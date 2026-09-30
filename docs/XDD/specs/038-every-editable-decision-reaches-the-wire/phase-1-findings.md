---
title: "Phase 1 findings: the discrepancy report"
version: "1.0"
phase: 1
---

# Phase 1 findings: the discrepancy report

Phase 1 was sequenced first so that what it revealed could reshape Phases 2–4
before they were committed to. This document is that output — the inventory
(`tomo/schemas/suggestions-decision-inventory.json`) is arguably the side
effect. **None of the twenty findings below came from a failing test.** Every
one came from counting or executing something a document — the plan, a
docstring, a schema description — asserted. That is the most transferable
thing Phase 1 produced: a plan's claims about a codebase are hypotheses, not
facts, until something runs against the real artefact.

Findings are grouped by disposition, not by the order they were found in.
None is resolved by this document — Phase 1's own task list resolved
seventeen of them as it went; the three below that remained open at T1.3's
start are the ones this task disposes of.

## Resolved during the phase (14)

These landed as part of T1.1/T1.1b/T1.2's own commits, each fixing the
document (plan, docstring, or schema) that was wrong, not absorbing new scope.
#15 appears here for its plan-side half only — its schema-side half is this
task's own work, listed under "Resolved by this task" below.

| # | Finding | Resolution |
|---|---|---|
| 1 | The plan asserted 23 `Editable`-marked schema fields in four places; measured 21, and 21 at `main` too, so it was wrong when written. | `de8da00`; recorded in the deviation table. |
| 2 | `candidate_mocs[].selected` and `.anchor` are honoured by `build_from_wire` (skips unselected entries, reads `anchor`) yet carried no `Editable` marker — the schema-side join was structurally blind to them. | T1.1b `45aa5cc`; count now 23. |
| 3 | The plan estimated "~7 recognised controls"; measured 34 distinct `parser_label` literals — a different unit, not a corrected value. | Estimate retired rather than replaced. |
| 6 | PRD/F4's "a malformed row fails Tomo's tests" was owned by no test — T1.1 declared none, and T1.2's join proves completeness, not row validity. | `fe53f46`; T1.1 gained the test. |
| 7 | Three declared schema constraints had no rejection test while the test docstring claimed every constraint had one. | `77c05c1`; a later pass verified all 26 exhaustively. |
| 8 | A number swap in `phase-1.md` broke the sentence's inference — "23 fields against 34 literals means…" does not follow, and the same commit's deviation row said the units are incomparable. | `7030070`; the arithmetic retired rather than restated. |
| 9 | Nothing would catch a row at `editable: false` whose parser control is still live — the consumer would be told to delete a control that still works. | Became a T1.2 success criterion; `test_injection_c_stale_exemption_fails`. Imported from the consumer's own fourth test. |
| 10 | The join could pass vacuously — a reworded marker makes the enumeration match nothing and every assertion below it pass. The consumer anticipated this in a comment in the test we mirrored. | Floored at 23, plus `test_parser_harvest_meets_the_measured_floor`. |
| 11 | The identifier guard missed a bare `037` — verbatim the shape of the note it was written to replace. The ablation was run, but planted `"spec 037"`, a string the regex already handled. | `833850e`. |
| 12 | D09's prose promised an `"Approve/Skip"` checkbox; no `Skip` literal exists in parser or renderer. Would have told the consumer to honour a control that never renders. | `56dc865`. |
| 13 | The replacement bare-number branch missed `100`/`0038` and false-positived on `"030-day"`. | `56dc865` with `\b\d{3,4}\b`, a deliberately eager trade-off. |
| 15 | The plan's marker predicate was `"Editable — "`, which finds 22 — `proposed_mocs[].tags` carries a bare `"Editable."`. Found by T1.2's implementer measuring and reporting rather than adjusting. | Plan resolved `c5ad683`; schema normalisation is T1.3 part 2, below. |
| 16 | The injection docstrings claimed a discrimination a bare `pytest.raises(AssertionError)` could not prove — either assertion in a helper satisfied the raise. | `da6e364` with `match=` pins, each shown discriminating. |
| 17 | Each injection's fixture premise held by accident rather than assertion — (c) worked only because `"approve"` happens to be live on three rows today. | `4b74e45`; all four premises now enforced. |

## Withdrawn (1)

| # | Finding | Disposition |
|---|---|---|
| 14 | Claimed D02 names a caption the renderer never emits. | **Withdrawn, not a defect.** The contract is prose ↔ `parser_label`, which D02 satisfies; the aliases are real parser tolerances. Recorded here because a finding retracted on examination belongs in the list as much as one confirmed — otherwise the list overstates how much was actually wrong. |

## Resolved by this task, T1.3 (2)

| # | Finding | Resolution |
|---|---|---|
| 15 (schema side) | `proposed_mocs[].tags` description read bare `"Editable."` against 22 siblings reading `"Editable — …"`. | Normalised to `"Editable — tags to add."` in `tomo/schemas/suggestions-wire.schema.json`. RED written first against the real schema (`test_wire_schema_editable_markers_use_uniform_dash_form`), confirmed failing, then the schema fixed, confirmed green. See task report for the RED/GREEN transcript. |
| 18 | `_OPTION_VALUE_LITERALS` in `tests/test_038_decision_inventory_join.py` mixed true option synonyms, internal non-wire field keys, and raw punctuation under one name — a maintainer extending the rules by analogy with `placement` would reach for the option-value predicate for the wrong reason. | Split into `_OPTION_SYNONYM_LITERALS`, `_NON_WIRE_FIELD_KEY_LITERALS`, and `_PARSING_PUNCTUATION_LITERALS`, each with its own predicate, comment, and `ABSENCE_RULES` entry. `"other sections in this moc"` was placed in the field-key bucket rather than the option-synonym bucket the plan's example implied — `suggestion-parser.py:848` compares it only as a field-line *key* (`key in (...)`), the same shape as `"placement"`, never against checkbox display text the way `"keep"`/`"preserve"`/`"behalten"`/`"related"` are at `suggestion-parser.py:1718-1719`. Verified no literal is double-covered (five disjoint sets, checked by inspection) and that dropping a literal from every bucket reddens `test_real_artefacts_parser_side_join_passes` (dropped `"placement"`; failure named it: `uncovered = ['placement']`; file restored and confirmed byte-identical via `cmp`). |

## Backlog, already written (2)

Not new — surfaced during the phase, already recorded in `docs/XDD/backlog.md`
before this task started.

| # | Finding | Status |
|---|---|---|
| 4 | `classification` is parsed (`suggestion-parser.py`) but unreachable from the review surface — no renderer emits the line, field lines are emitted literally rather than from a generic emitter, so the value is always `None`. | **CLOSED** in backlog (`## CLOSED — classification is parsed but unreachable from the review surface`). Not an editable decision, owes no wire field. This *removed* a phantom Phase 2 obligation rather than adding one. |
| 5 | The `type` field line has no `suggestions-wire` counterpart and was not traced. | **OPEN** in backlog (`## OPEN — the type field line has no wire-schema counterpart, untraced`), lower confidence than #4 — same shape, not yet given the same renderer/emission trace. |

## Accepted limitations — not backlog items (2)

These are deliberate boundaries of what a count-and-literal join can prove,
not gaps to schedule work against. Closing either would mean reversing a
design decision this spec already made for a stated reason.

| # | Finding | Why this is a limitation, not a gap |
|---|---|---|
| 19 | No honesty check exists on an absence rule's *stated reason* — nothing notices if a field excused as read-only later becomes `Editable`. | The schema-side join catches the dangerous end state anyway: flipping `summary` or `attachments` to `Editable` with no row makes marked 24 against backed 23, and `_assert_schema_side_join`'s equality assertion fires. Closing the *reason*-level gap would mean reintroducing `wire_field` path-string matching, which this spec deliberately rejected — D24's `wire_field` is `null`, and Known Limitation 1 in `test_038_decision_inventory_join.py`'s module docstring exists for exactly that reason. |
| 20 | Two further call-chain comparisons at `suggestion-parser.py:1528,1611` are missed by the AST visitor. | Not a new gap. `"accept"` is already harvested from the plain comparison at `:816` — the visitor's blind spot to call-chain shapes (`cb.group(1).lower()` and siblings) is the same documented class as Known Limitation 3's `force atomic note` (D18). Recorded there once; this is not a second instance needing its own entry. |

## Recommendation

None of the twenty findings leaves open scope for Phases 2–4 to absorb. The
two backlog items (#4, #5) are already tracked at the right severity outside
this spec; the two accepted limitations (#19, #20) are consequences of design
choices ADR-7 already made, not omissions. Phase 2 can proceed against the
inventory as-is.
