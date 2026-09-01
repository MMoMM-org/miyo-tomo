---
title: "Phase 3: Field threading through both review channels"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Field threading through both review channels

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Constraints; CON-5]` — the two review channels must stay in lockstep
- `[ref: SDD/Interface Specifications; Application Data Models]`
- `[ref: SDD/Cross-Cutting Concepts; User Interface & UX]`
- `[ref: PRD/Feature 3]`
- Read in full: `docs/tomo/scripts/suggestion-parser.md:180-186` — the explicit-projection silent-drop trap
- Source to read: `suggestions-reducer.py:370-390` and `:1774-1783`; `suggestions-render.py:272-300`; `suggestion-parser.py:305`, `:586`, `:704-712`, `:2006-2024`

**Key Decisions**:
- The field is `attachments`: a list of resolved vault-relative path strings, default `[]`.
- It gets **its own `**Attachments:**` line**. It must not extend the `**Source:**` line — the parser keys off wikilink *index* there (`suggestion-parser.py:712`), which only works for 0-or-1.
- Paths render **backticked and full**, not as wikilinks. The subfolder is the information the user needs to sanity-check resolution.

**Dependencies**: Phase 1 fixes the field shape. Independent of Phases 2 and 4.

---

## Tasks

Carries the attachment list from the analyst contract to the render manifest, across both review channels, without a silent drop.

- [ ] **T3.1 Schema declarations** `[activity: data-architecture]`

  1. **Prime**: Note that all three schemas set `additionalProperties:false` — `item-result.schema.json:52`, `suggestions-doc.schema.json:59`, `suggestions-wire.schema.json:26`. A field not declared is a validation failure, not a silent pass.
  2. **Test** (RED):
     - an item carrying `attachments` validates against `item-result.schema.json`
     - an item **without** `attachments` still validates — it must not be in `required` `[ref: CON-8]`
     - the same two cases for `suggestions-doc.schema.json` and `suggestions-wire.schema.json`
     - a non-list `attachments` is rejected
  3. **Implement**: add `"attachments": {"type": "array", "items": {"type": "string"}}` to the three schemas, none in `required`.
  4. **Validate**: schema tests pass. Schemas sync bytewise, so no version bump is needed `[ref: CON-7]`.
  5. **Success**: legacy artefacts without the field still validate `[ref: CON-8]`

- [ ] **T3.2 Review surface — both channels** `[activity: frontend-ui]`

  1. **Prime**: Read `suggestions-reducer.py:370-390` (markdown) **and** `:1774-1783` (structured mirror). `[ref: CON-5]` — a field added to one only is invisible on the other path.
  2. **Test** (RED):
     - an item with attachments renders an `**Attachments:**` line naming each path and the destination folder `[ref: PRD/AC-F3.1]`
     - an item with none renders **no** attachment line `[ref: PRD/AC-F3.2]`
     - the structured `item` dict carries the identical list `[ref: PRD/AC-F3.4]`
     - unresolved and ambiguous embeds render an `**Unresolved embeds:**` line, only when non-empty `[ref: PRD/Should-have: unresolved reporting]`
     - the `**Source:**` line is unchanged for a voice item with an `audio_peer` — no regression on the positional wikilink encoding
  3. **Implement**: add the markdown line in `render_create_atomic_note` and the field in the structured mirror.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**: both channels carry the same list for the same item `[ref: CON-5]`

- [ ] **T3.3 Wire projection** `[activity: data-architecture]` `[parallel: true]`

  1. **Prime**: Read `_wire_note` at `suggestions-render.py:272-300`; `tags` at `:295` is the list-shaped precedent.
  2. **Test** (RED):
     - `attachments` appears in the wire suggestion
     - an absent field projects as `[]`, not `None`
     - `emit_digest` changes when the list changes — the digest hashes the whole payload, so this is automatic, and the test documents it `[ref: SDD/Interface Specifications]`
  3. **Implement**: add the projection line to `_wire_note`.
  4. **Validate**: unit tests pass; `# version:` bumped. **Land this together with T3.1's wire-schema change** — a half-added wire field makes a mid-flight payload read as "edited" `[ref: SDD/Implementation Gotchas]`.
  5. **Success**: the wire carries the field and the digest covers it `[ref: PRD/AC-F3.3]`

- [ ] **T3.4 Parser round trip — four sites** `[activity: backend-logic]`

  1. **Prime**: Read all four sites. The projection dicts at `:305` and `:2006` are the silent-drop trap — a field on `result` that is missing from the projection never reaches the output.
  2. **Test** (RED):
     - **markdown path**: an `**Attachments:**` line parses back to the identical list `[ref: PRD/AC-F3.3]`
     - **markdown path**: an item with no attachment line yields `[]` from the defaults
     - **wire path**: `build_from_wire` carries the list through `[ref: PRD/AC-F3.4]`
     - **both paths produce identical `confirmed_items` for the same logical item** — the CON-5 guarantee, asserted directly
     - a round trip through render → parse → render is stable
  3. **Implement**: four edits — wire projection (`:305`), markdown defaults (`:586`), a new `elif key == "attachments":` branch in the dispatch chain (`:704`, alongside `tags`), and the markdown projection (`:2009`). Do **not** extend the `wikilinks[1]` logic.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**:
     - [ ] The field survives both parse paths `[ref: PRD/AC-F3.3, AC-F3.4]`
     - [ ] Neither projection drops it `[ref: docs/tomo/scripts/suggestion-parser.md:180-186]`

- [ ] **T3.5 Manifest entry** `[activity: backend-logic]`

  1. **Prime**: Read `instruction-render.py:307-317` (the per-item loop) and `:425-430` (the manifest entry). Note `:313` — items with no template are `continue`d before the entry is built.
  2. **Test** (RED):
     - a confirmed item's attachments reach the manifest entry
     - an item without the field yields `[]`
     - an instruction-only item (no template) produces no manifest entry, so its attachments are dropped — asserted deliberately, matching the PRD's out-of-scope note `[ref: PRD/Edge case: item with no note move]`
  3. **Implement**: read the field in the loop and add it to the entry dict.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**: `_build_move_asset_actions` receives real data `[ref: SDD/Integration Points]`

- [ ] **T3.6 Phase Validation** `[activity: validate]`

  - Run all Phase 3 tests plus the full suite. Confirm with a single end-to-end assertion that an item's attachment list is identical after: reducer → wire → parser, and after reducer → markdown → parser. `ruff` clean.
