---
title: "Phase 2: Action emission"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Action emission

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-5, ADR-6]`
- `[ref: SDD/Implementation Examples; "Destination join — the trap"]`
- `[ref: SDD/Complex Logic; "Global deduplication across the run"]`
- `[ref: PRD/Feature 4]`, `[ref: PRD/Feature 6]`, `[ref: PRD/Business rules 5, 6, 7, 8]`
- Source to read: `tomo/scripts/lib/render_actions.py:559` (`_build_move_note_actions`, the template), `:920-935` (the audio-peer dedup — note it is *per group*), `:1275-1327` (`build_actions` ordering), `:488-498` (`_dest_join`, the trap), `:204-219` (`_REQUIRED_PATH_FIELDS`)

**Key Decisions**:
- **ADR-5** — the emitter reads the **manifest**, not `move_notes`. It must not touch the `move_note` action.
- **ADR-6** — no deletion is ever emitted for an attachment.
- **ADR-3** — a destination occupied by a *different* file means skip and report.

**Dependencies**: Phase 1 fixes the resolved-path shape. Tests here use synthetic manifest entries, so this phase does not wait for Phase 5.

---

## Tasks

Delivers executable `move_asset` actions and their human-readable rendering.

- [ ] **T2.1 Asset destination join** `[activity: domain-modeling]`

  1. **Prime**: Read the destination-join example `[ref: SDD/Implementation Examples]`. Two existing helpers look reusable and are actively harmful.
  2. **Test** (RED):
     - `("Atlas/290 Assets/295 Attachments/", "100 Inbox/Images/karte.jpg")` → `Atlas/290 Assets/295 Attachments/karte.jpg`
     - extension is preserved exactly, including uppercase (`FOTO.JPG` stays `FOTO.JPG`) `[ref: PRD/Edge case: unusual extension]`
     - a folder given without a trailing slash still joins correctly
     - the basename is **not** passed through `sanitize_stem` — an existing filename must survive verbatim so the embed keeps resolving
     - a regression test asserting `_ensure_md_extension("foto.jpg")` returns `foto.jpg.md`, documenting *why* it is not used here
  3. **Implement**: `_asset_dest_join(asset_folder, source_path)` in `tomo/scripts/lib/render_actions.py`.
  4. **Validate**: unit tests pass; `ruff` clean; `# version:` bumped.
  5. **Success**:
     - [ ] No `.md` ever appears on an asset destination `[ref: PRD/AC-F4.1]`
     - [ ] `_dest_join` and `_ensure_md_extension` are not called on any attachment path `[ref: SDD/Implementation Gotchas]`

- [ ] **T2.2 move_asset emission with global de-duplication** `[activity: backend-logic]`

  1. **Prime**: Read `[ref: SDD/Complex Logic]`. The audio-peer set at `render_actions.py:927` dedups *within* an origin-stem group; attachments dedup **globally**.
  2. **Test** (RED):
     - one item with one attachment → one action, correct source and destination `[ref: PRD/AC-F4.1]`
     - two items embedding the same path → **one** action `[ref: PRD/AC-F4.2]`
     - two items embedding different files with the same basename → two actions (dedup keys on the full path, not the basename)
     - an item with an empty attachment list → no actions
     - a manifest with no attachment keys at all → no actions, and the rest of the set is byte-identical `[ref: CON-8]`
     - IDs are assigned from the shared counter and are monotonic
     - **no `delete_source` action references any attachment path** `[ref: ADR-6]`
  3. **Implement**: `_build_move_asset_actions(manifest, inbox_path, asset_folder, counter)` reading `m.get("attachments")`. Insert into `build_actions` between the `move_note` extend and the `link_to_moc` extend, and update the ordering docstring at `:1287-1303`.
  4. **Validate**: unit tests pass; full suite run to surface ID-renumbering churn in existing fixtures (expected, not a regression) `[ref: SDD/Implementation Gotchas]`.
  5. **Success**:
     - [ ] Dedup is global across the run, not per item `[ref: PRD/Business rule 5]`
     - [ ] Only approved items contribute, since the manifest holds only approved items `[ref: PRD/Business rule 6]`
     - [ ] Actions occupy planner slot 3 `[ref: docs/instructions-json.md]`

- [ ] **T2.3 Readable instruction rendering** `[activity: backend-logic]` `[parallel: true]`

  1. **Prime**: Read `tomo/scripts/lib/render_md.py:31-46` (`_md_section_for`) and `:239` (the unknown-action fallback).
  2. **Test** (RED):
     - a `move_asset` action renders with name, source and destination `[ref: PRD/AC-F6.1]`
     - the string `unknown action` never appears for `move_asset` `[ref: PRD/AC-F6.2]`
     - it is routed to a sensible section rather than falling through to the `new_files` default
  3. **Implement**: add the `move_asset` branch to both `_md_section_for` and `_render_action_md`.
  4. **Validate**: unit tests pass; `ruff` clean; `# version:` bumped.
  5. **Success**: the readable document describes attachment moves in plain language `[ref: PRD/Feature 6]`

- [ ] **T2.4 Destination collision guard** `[activity: backend-logic]`

  1. **Prime**: Read `[ref: SDD/Architecture Decisions; ADR-3]`. Renaming is explicitly deferred; the behaviour must still be defined.
  2. **Test** (RED):
     - two attachments with the same basename from different source folders → the second is skipped and reported, not silently overwritten `[ref: PRD/Should-have: destination collision]`
     - the same file resolved twice → one action, no collision (dedup handles it before the guard)
     - a collision does not suppress the note's own `move_note`
  3. **Implement**: within `_build_move_asset_actions`, track claimed destinations; on a conflicting claim, skip and record a report entry.
  4. **Validate**: unit tests pass.
  5. **Success**: no two emitted actions target the same destination `[ref: ADR-3]`

- [ ] **T2.5 Path validation and config default** `[activity: backend-logic]` `[parallel: true]`

  1. **Prime**: Read `_REQUIRED_PATH_FIELDS` at `render_actions.py:204-219` and `CONFIG_DEFAULTS` at `instruction-render.py:105-111`. `concepts.asset` is absent from the latter — verified.
  2. **Test** (RED):
     - `_validate_action_paths` rejects a `move_asset` with an empty `source` or `destination` — proving the kind is no longer skipped
     - resolving `concepts.asset` on a profile that omits the key returns the default instead of raising `KeyError` `[ref: SDD/Known Technical Issues]`
  3. **Implement**: add `"move_asset": ("source", "destination")` to `_REQUIRED_PATH_FIELDS`; add a `concepts.asset` entry to `CONFIG_DEFAULTS`.
  4. **Validate**: unit tests pass; `# version:` bumped on both files.
  5. **Success**:
     - [ ] Asset paths are shape-validated like every other kind
     - [ ] No `KeyError` on a profile without the asset concept

- [ ] **T2.6 Phase Validation** `[activity: validate]`

  - Run all Phase 2 tests plus the full suite. Confirm: an emitted set containing `move_asset` validates against `tomo/schemas/instructions.schema.json` `[ref: PRD/AC-F4.4]`; `schema_version` is unchanged `[ref: CON-2]`; zero `delete_source` actions reference an attachment path `[ref: ADR-6]`. `ruff` clean.
