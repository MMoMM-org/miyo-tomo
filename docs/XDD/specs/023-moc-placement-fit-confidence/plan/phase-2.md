---
title: "Phase 2: Footer inventory"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: Footer inventory

## Phase Context

**GATE**: Read referenced files before starting.

**Specification References**:
- `[ref: solution.md/ADR-5]` — `has_footer` inventory flag for Pass-1 footer-awareness
- `[ref: requirements.md/AC-9a]` — analyst reads `has_footer` to pick the truthful tier-2 anchor type
- `[ref: solution.md/Two-pass timing]` — why footer presence must be known at Pass-1 (the doc is a Pass-1 artifact)
- `[ref: tomo/scripts/moc-tree-builder.py; lines: 334-374]` — MOC cache entry build (body + FOOTER_CALLOUTS already in hand)
- `[ref: tomo/scripts/shared-ctx-builder.py; lines: 210-244]` — MOC inventory passthrough into shared-ctx
- `[ref: tomo/scripts/lib/moc_structure.py; lines: 37-55]` — `footer_index` (returns `len(lines)` when no footer)

**Key Decisions**:
- `has_footer` is computed at cache build from body bytes already loaded — **no new Kado read** (CON-2 holds). `has_footer = footer_index(body.splitlines(), FOOTER_CALLOUTS) < len(body.splitlines())`.
- It is a **cache-schema change** → the cache must be rebuilt (`/explore-vault`) before it appears; absent `has_footer` degrades to 022 behavior (Phase 3 handles the absent case).
- This phase ships the SIGNAL only; the analyst consumes it in Phase 3. It gates Phase 3.

**Dependencies**: None beyond the shipped 022 inventory (`headings`, `editable_callouts`). Independent of Phase 1.

---

## Tasks

Surfaces a cheap footer-presence flag on the MOC inventory so Pass-1 can choose a truthful tier-2 anchor type.

- [x] **T2.1 `has_footer` on MOC inventory (cache + shared-ctx)** `[activity: backend]`

  1. Prime: Read the cache-entry build in `moc-tree-builder.py` `[ref: lines: 334-374]` (note `body = get_body(content)` and `FOOTER_CALLOUTS` already in scope) and the shared-ctx passthrough in `shared-ctx-builder.py` `[ref: lines: 210-244]`. Read `footer_index` `[ref: tomo/scripts/lib/moc_structure.py; lines: 37-55]`.
  2. Test (red): in `tests/test_moc_structure_inventory.py` (new file, or extend the moc-tree-builder test if one exists), assert — a MOC body containing a footer-marker callout (e.g. `> [!video]`) yields `has_footer == True`; a body with headings but NO footer-marker callout yields `has_footer == False`; and the shared-ctx builder copies `has_footer` onto `shared_ctx.mocs[]`.
  3. Implement (green): in `moc-tree-builder.py`, add `entry["has_footer"] = moc_structure.footer_index(body.splitlines(), FOOTER_CALLOUTS) < len(body.splitlines())` alongside the existing `headings`/`editable_callouts` population. In `shared-ctx-builder.py`, pass `has_footer` through into the `moc` inventory dict (mirror the `headings`/`editable_callouts` passthrough). Bump `# version:` on both files.
  4. Validate: `./venv/bin/python -m pytest tests/test_moc_structure_inventory.py`; confirm no new Kado call was introduced (the flag is computed from `body` already in `raw_by_path`).
  5. Success:
     - [ ] `has_footer` recorded per MOC at cache build, no new Kado read `[ref: ADR-5; CON-2]`
     - [ ] `has_footer` surfaced on `shared_ctx.mocs[]` for Pass-1 `[ref: AC-9a]`

- [x] **T2.2 Phase Validation** `[activity: validate]`

  - Run the inventory suite. Confirm both `# version:` bumps are present (else `update-tomo` silently skips). Confirm `has_footer` is additive — existing moc-tree-builder / shared-ctx tests still pass. Note for the live walk: the cache must be rebuilt via `/explore-vault` for `has_footer` to populate.
