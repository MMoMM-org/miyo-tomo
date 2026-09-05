---
title: "Phase 4: Coverage audit and dry run"
status: completed
version: "1.0"
phase: 4
---

# Phase 4: Coverage audit and dry run

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Known Technical Issues; "instructions-diff blind spot"]`
- `[ref: SDD/Complex Logic; "The audit must dedup identically"]`
- `[ref: SDD/Architecture Decisions; ADR-6]`
- `[ref: PRD/Feature 5]`, `[ref: PRD/Risks; row 1 — Likelihood High]`
- Source to read: `instructions-diff.py:168-177` (counts init), `:280-336` (`expected_deletions` and the audio-peer mirror at `:296-318`), `:357-366` (`summarize_actual`, generic), `:429-433` (`ACTION_ORDER`), `:645-659` (`run_diff` reconciliation); `instructions-dryrun.py:25-33`

**Key Decisions**:
- **This is the phase the PRD singles out as highest-risk.** An unlisted kind is counted by `summarize_actual` but never reconciled, so the audit passes **green** while N actions go unchecked. The only symptom is `action_count` exceeding the printed `TOTAL`.
- **ADR-6** — attachments must **not** be appended to `expected_deletions`. That is the audio-peer behaviour and the exact inversion this feature depends on.
- Renderer and audit must dedup on the **same normalised string**: the resolved vault-relative path.

**Dependencies**: none on other phases. Uses synthetic parsed/instruction pairs.

---

## Tasks

Closes the blind spot so that a missing or spurious attachment move fails loudly.

- [x] **T4.1 Audit registration** `[activity: backend-logic]`

  1. **Prime**: Read `run_diff` at `:645-659`. It iterates `ACTION_ORDER`; a kind absent from that list contributes nothing to `total_actual` and never appears in the table.
  2. **Test** (RED) — **write the failing-audit test first, before registration**:
     - given an instruction set containing `move_asset` and an expectation of the same count, the audit currently reports a total that **excludes** them — this test documents the pre-fix blind spot and must fail once fixed
     - after registration: expected N, actual N → pass `[ref: PRD/AC-F5.1]`
     - expected N, actual N-1 → **hard fail** with a per-kind mismatch `[ref: PRD/AC-F5.2]`
     - expected N, actual N+1 → hard fail
     - `move_asset` appears in the printed table and contributes to `TOTAL` `[ref: PRD/AC-F5.3]`
     - `action_count` in the header equals the printed `TOTAL` for a set containing attachments — the symptom test
  3. **Implement**: add `"move_asset": 0` to the counts initialiser and `"move_asset"` to `ACTION_ORDER`, positioned directly after `"move_note"` to mirror emission order.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**: an unaudited attachment move is impossible `[ref: PRD/Risks; row 1]`

- [x] **T4.2 Expectation derivation** `[activity: backend-logic]`

  1. **Prime**: Read the audio-peer expectation block at `:296-318` — structurally what is needed, semantically inverted. Note the documented asymmetry: that block dedups on the parser-supplied basename while the renderer dedups on the inbox-joined path `[ref: SDD/Technical Debt]`.
  2. **Test** (RED):
     - one confirmed item with 2 unique attachments → expects 2 `[ref: PRD/AC-F5.1]`
     - two confirmed items sharing one attachment → expects **1**, matching the renderer's global dedup `[ref: PRD/AC-F4.2]`
     - two items with same-basename-different-path attachments → expects 2, proving the key is the full path, not the basename
     - `create_moc` items are skipped, as in the existing passes
     - **attachments never appear in `expected_deletions`** — the ADR-6 guard on the *expectation* side; the emitted side is asserted in Phase 2 T2.2 `[ref: ADR-6]`
     - a skipped item's attachments contribute nothing `[ref: PRD/AC-F4.5]`
  3. **Implement**: add an expectation pass in `derive_expected` collecting `item.get("attachments")` into an `attachments_seen: set[str]`, then `counts["move_asset"] = len(attachments_seen)`. Key on the resolved path.
  4. **Validate**: unit tests pass.
  5. **Success**:
     - [ ] Renderer and audit dedup keys are the same string `[ref: SDD/Complex Logic]`
     - [ ] No attachment can reach a deletion expectation `[ref: ADR-6]`

- [x] **T4.3 Dry-run support** `[activity: backend-logic]` `[parallel: true]`

  1. **Prime**: Read `instructions-dryrun.py:25-33`. The `REQUIRED` table is a whitelist; an unlisted kind reports unknown type and exits 1.
  2. **Test** (RED):
     - a dry run over a set containing `move_asset` exits 0 and describes each action `[ref: PRD/AC-F5.4]`
     - a `move_asset` missing `destination` is reported as invalid
  3. **Implement**: add `"move_asset": {"id", "action", "source", "destination"}` to `REQUIRED` and a `describe` branch.
  4. **Validate**: unit tests pass; `# version:` bumped.
  5. **Success**: dry run no longer rejects a valid set `[ref: PRD/AC-F5.4]`

- [x] **T4.4 Phase Validation** `[activity: validate]`

  - Run all Phase 4 tests plus the full suite. Confirm the count-parity trap is avoided: the tests must model *execution* (which paths are expected) and not merely compare totals `[ref: memory: count parity ≠ correctness]`. Confirm the pre-fix blind-spot test now fails for the right reason. `ruff` clean.
