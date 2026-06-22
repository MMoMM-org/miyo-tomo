---
title: "Phase 4: Surfacing & resolution"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Surfacing & resolution

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/Implementation Examples; _placement_line]` — confidence-% + tier-2 destination wording
- `[ref: requirements.md/AC-11, AC-12, AC-13]` — confidence shown; back-compat; tier-2 destination shown
- `[ref: solution.md/Complex Logic — PASS-2]` — render resolves null `line` anchors to the last body line
- `[ref: requirements.md/AC-9, AC-10]` — no-footer resolution + spacing
- `[ref: requirements.md/Tracking Requirements; solution.md/System-Wide Patterns — Logging]` — metadata-only telemetry (Constitution L2)
- `[ref: solution.md/Implementation Gotchas]` — no-leak into Hashi anchor; render resolves null line anchors
- `[ref: tomo/scripts/suggestions-reducer.py; lines: 95-144]` — `_placement_line` (version 1.10.7)
- `[ref: tomo/scripts/instruction-render.py; lines: 1498-1604, 1646-1740]` — `resolve_section_names`/`_pick_anchor` + apply loop + `_emit_resolution_telemetry` (version 0.24.9)

**Key Decisions**:
- The confidence % is appended ONLY in the `type==heading` branch when `fit_confidence` is a number; absent → line byte-identical to 022 (AC-12).
- Tier-2 destination wording is driven by the anchor TYPE the analyst already chose (Phase 3): `callout` → `(before the footer)`; `line` → `(at the end of the MOC)` (AC-13). The reducer reads the type — it does NOT re-derive footer presence.
- Render gains the no-footer tier: `_pick_anchor` returns `{type:line, value:<last body line>, placement:after}` when there is no footer, AND `resolve_section_names` now resolves null-value `line` anchors (it historically skipped `line` anchors). The existing honor-guard stays — a `line` anchor whose value is ALREADY set is left untouched.
- Telemetry stays metadata-only: counts + the confidence *number*, never heading text (CON-5 / L2).

**Dependencies**: Phase 1 (schema field), Phase 2 (`has_footer`), Phase 3 (analyst emits the typed null-value anchors this phase renders/resolves).

---

## Tasks

Surfaces placement to the user (doc) and resolves the body-derived values (render). T4.1 (reducer) and T4.2 (instruction-render) touch different files and run in parallel.

- [x] **T4.1 Suggestions-doc placement line: confidence % + tier-2 destination** `[parallel: true]` `[activity: backend]`

  1. Prime: Read `_placement_line` `[ref: tomo/scripts/suggestions-reducer.py; lines: 95-144]` and the SDD render example `[ref: solution.md/Implementation Examples; _placement_line]`.
  2. Test (red): in `tests/test_suggestions_reducer_t6_1_placement.py`, assert — a heading anchor with `fit_confidence:0.89` renders `under \`## <value>\` (confidence: 89%)` (AC-11); a heading anchor without `fit_confidence` (and a legacy 022 anchor) renders byte-identical to 022 (AC-12); a tier-2 `callout` + `new_section` renders `new section \`## <topic>\` (before the footer)`; a tier-2 `line` + `new_section` renders `new section \`## <topic>\` (at the end of the MOC)` (AC-13); a non-number `fit_confidence` is ignored.
  3. Implement (green): in `_placement_line` — tier-1 heading branch appends `f" (confidence: {int(conf*100)}%)"` only when `isinstance(conf,(int,float))`; tier-2 new-section branch appends the destination phrase by anchor type. Bump `# version:` (1.10.7 → next).
  4. Validate: `./venv/bin/python -m pytest tests/test_suggestions_reducer_t6_1_placement.py`; % format matches the existing Why-line convention.
  5. Success:
     - [ ] tier-1 placement shows `(confidence: NN%)`, absent → unchanged `[ref: AC-11, AC-12]`
     - [ ] tier-2 shows `(before the footer)` / `(at the end of the MOC)` `[ref: AC-13]`

- [x] **T4.2 Render: no-footer resolution + telemetry + no-leak guard** `[parallel: true]` `[activity: backend]`

  1. Prime: Read `resolve_section_names`/`_pick_anchor` + the apply loop `[ref: tomo/scripts/instruction-render.py; lines: 1498-1604, 1646-1677]`, `_emit_resolution_telemetry` `[ref: lines: 1680-1740]`, and the `_emit` anchor decomposition `[ref: lines: 777-807]`. Note the apply loop currently only resolves empty-value `callout` anchors (line ~1653) and rewrites the type from `_pick_anchor`'s result.
  2. Test (red): assert — (a) a footer-less MOC body → `_pick_anchor` returns `{type:line, value:<last body line>, placement:after}` (the NEW 4th tier); (b) the apply loop resolves a null-value `line` anchor → value set to the last body line; (c) `_serialize_new_sections` then yields `line_to_add == "## <section>\n\n- [[Note]]\n"` (correct spacing, AC-10); (d) telemetry emits a `tier1_confident` count + a rejected→tier-2 signal with NO heading text in the line (metadata-only — scan the string); (e) a Pass-1 anchor with `fit_confidence` decomposes so the Pass-2 action anchor has NO `fit_confidence` key (no-leak).
  3. Implement (green): add the no-footer tier to `_pick_anchor` (after the footer branch: if no footer, return `{type:line, value:<last body line>, placement:after}`); allow `resolve_section_names` to resolve null-value `line` anchors (extend the `anchor.type` guard at ~1653 to include `line`, keeping the "value already set → skip" honor-guard). Extend `_emit_resolution_telemetry` with the confident/rejected counts (numbers only). Confirm (do not re-add) `_emit` strips `fit_confidence`; if a test proves a leak, strip it there. Bump `# version:` (0.24.9 → next).
  4. Validate: `./venv/bin/python -m pytest tests/test_moc_insertion_resolution.py`; grep the emitted telemetry line in a test to confirm only counts/paths/numbers.
  5. Success:
     - [ ] no-footer `line` anchor resolves to the last body line, correct spacing `[ref: AC-9, AC-10]`
     - [ ] telemetry counts confident-tier-1 vs rejected→tier-2, metadata-only `[ref: Tracking Requirements; Constitution L2]`
     - [ ] `fit_confidence` never reaches the Pass-2 `{type,value}` action anchor `[ref: solution.md/Implementation Gotchas]`

- [x] **T4.3 Phase Validation** `[activity: validate]`

  - Run the three affected suites (`test_suggestions_reducer_t6_1_placement.py`, `test_moc_insertion_resolution.py`, `test_spec022_schema_additions.py`). Confirm both consumer `# version:` bumps, the telemetry line is metadata-only, the `alt_headings` advisory still empty-filters (no bare `## `), and the honor-guard still leaves a populated `line` anchor untouched.
