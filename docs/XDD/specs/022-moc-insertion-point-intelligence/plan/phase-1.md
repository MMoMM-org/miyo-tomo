---
title: "Phase 1: Shared parse foundation"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Shared parse foundation

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/Building Block View; Directory Map]` — `lib/moc_structure.py` (NEW)
- `[ref: solution.md/ADR-4]` — single source of truth for parsing
- `[ref: research-synthesis.md/Convergent finding]` — regexes at `instruction-render.py:1510-1511`

**Key Decisions**:
- ADR-4: build-time inventory and render-time fallback MUST share one parser.
- Gotcha: `FOOTER_CALLOUTS` (`instruction-render.py:1471`) stays hardcoded for #35/F-55 — the lib
  takes the footer set as a **parameter**, never re-hardcodes it.

**Dependencies**: none (foundation).

---

## Tasks

Establishes the shared MOC-structure parsing capability both the inventory producer and the render
fallback depend on.

- [ ] **T1.1 `lib/moc_structure.py` parser** `[activity: domain-modeling]`

  1. Prime: Read the existing inline regexes and footer logic `[ref: instruction-render.py; lines: 1471, 1476, 1510-1511, 1558-1601]`.
  2. Test (red): `tests/test_moc_structure.py` under `./venv/bin/python` —
     - `parse_headings(body)` returns ordered `{text, level}` for H2/H3 before the footer; empty list when none.
     - `parse_editable_callouts(body, editable_set)` returns full callout opening lines present, in order; honors the passed `editable_set` (NOT a hardcoded set).
     - `footer_index(lines, footer_set)` returns the first footer-callout line index; `len(lines)` when no footer.
     - Fixture sourced from the real `Atlas/200 Maps/Systems Thinking (MOC).md` shape (headings under `[!blocks] Key Concepts`, footer `[!video]`).
  3. Implement (green): Create `tomo/scripts/lib/moc_structure.py`; lift the heading/callout regexes verbatim from `instruction-render.py:1510-1511`; accept `footer_set` + `editable_set` as params.
  4. Validate: unit tests pass; no hardcoded footer/editable sets inside the lib.
  5. Success:
     - [ ] Heading inventory matches render-time `_pick_content_heading` extraction on the same body `[ref: solution.md/ADR-4]`
     - [ ] Footer set is parameterized `[ref: solution.md/Implementation Gotchas]`

- [ ] **T1.2 Phase Validation** `[activity: validate]`

  - Run `tests/test_moc_structure.py`. Confirm the lib is import-clean and has no Kado/IO dependency (pure functions over a body string).
