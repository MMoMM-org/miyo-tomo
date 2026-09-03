---
title: "Phase 4: Report surface"
status: pending
version: "1.0"
phase: 4
---

# Phase 4: Report surface

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-5, ADR-6, ADR-7]`
- `[ref: SDD/Cross-Cutting Concepts; User Interface & UX]` — the constraints the wording must meet
- `[ref: PRD/Feature 2]`, `[ref: PRD/Feature 3]`, `[ref: PRD/Feature 5]`, `[ref: PRD/Feature 6]`
- Source to read: `tomo/scripts/garden-audit-render.py:580-587` (the advisory branch and its single
  fixed line), `:63` (`_CHECK_LABEL`), `:485-495` (the per-finding detail line, which spec 032 taught
  to branch on declaration site), `:312-325` (the all-advisory path), `:425-440`
  (`_render_broken_up_split`, whose denominator this phase changes)

**Key Decisions**:
- **ADR-5** — the advisory message is per-check, with a fallback to today's generic line so
  `duplicate_stem` and `stale_moc` stay byte-identical.
- **ADR-6** — say *not found in the audited area*; never assert the note is gone.
- **ADR-7** — 032's declaration-site line now counts survivors only; the drop is expected.

**Dependencies**: Phase 2 (there must be two checks to render).

---

## Tasks

- [ ] **T4.1 The advisory message names the target and inverts the suggestion** `[activity: ux]`

  1. **Prime**: read `:580-587`. Today every advisory renders *"Advisory — no automated fix. Review
     and handle manually."* For this check that is true and useless — there **is** an action, just
     not one Tomo performs `[ref: SDD/ADR-5]`.
  2. **Test** (RED):
     - a `parent_not_moc` block names the **target** as the thing to change `[ref: PRD/F2 crit 3]`
     - it contains neither "broken" nor "remove" `[ref: SDD/UI & UX]`
     - it contains **no** `- [ ]` checkbox and no `Repoint to:` field `[ref: PRD/F2 crit 2]`
     - several findings sharing one target render the one-action-settles-many relationship
       `[ref: PRD/F2 crit 4]`
     - `duplicate_stem` and `stale_moc` blocks are **byte-identical** to today's — the fallback path
       `[ref: CON-3]`
  3. **Implement**: a per-check advisory message table; `.get(check)` falling back to the existing
     line.
  4. **Validate**: `./venv/bin/python -m pytest tests/test_garden_audit_render.py -q`
  5. **Success**: a reader who acts on the advisory changes the right note.

- [ ] **T4.2 `broken_up` says *not found in the audited area*** `[activity: ux]`

  1. **Prime**: `[ref: SDD/ADR-6]`. The group is provably mixed — some targets exist outside the
     scanned folders. Asserting the note is gone is the false claim this spec removes.
  2. **Test** (RED):
     - the fix line says the target was not found **in the audited area** `[ref: PRD/F3 crit 1]`
     - it does **not** assert the note does not exist
     - it points at the audited scope as user-controllable `[ref: PRD/F3 crit 2]`
     - remove and repoint remain available `[ref: PRD/F3 crit 3]`
     - a property-resident one still carries spec 032's `Fix target:` disclosure — this phase must
       not disturb it `[ref: SDD/ADR-7]`
  3. **Implement**: reword the `broken_up` fix summary only.
  4. **Validate**: render suite, plus the spec 032 emission tests.
  5. **Success**: the report describes a scan boundary, not a missing note.

- [ ] **T4.3 Per-situation counts** `[activity: ux]`

  1. **Prime**: `[ref: PRD/F5]` and 032's `_render_broken_up_split`, which solved the same shape and
     hit the same trap — a breakdown that implies a division when only one bucket is populated.
  2. **Test** (RED):
     - both situations present → the line states both counts, summing to the total flagged
     - only one present → **no** breakdown implying a division `[ref: PRD/F5 crit 2]`
     - no flagged parents → **no** line at all `[ref: PRD/F5 crit 3]`
     - 032's declaration-site line now counts `broken_up` survivors only, and says so
       `[ref: SDD/ADR-7]`
  3. **Implement**: extend the summary renderer.
  4. **Validate**: render suite.
  5. **Success**: a reader can triage from the summary without reading 42 blocks.

- [ ] **T4.4 A pre-033 cache discloses rather than guesses** `[activity: ux]`

  1. **Prime**: `[ref: PRD/F6]`, and 032's `_UNROUTABLE_REMEDY` — the same disclosure shape, already
     built and tested. Reuse it rather than adding a parallel mechanism.
  2. **Test** (RED):
     - no finding claims a cause `[ref: PRD/F6 crit 1]`
     - the report says the index predates the distinction and how to refresh it `[ref: F6 crit 2]`
     - no fix is offered that would be wrong for two of the three situations `[ref: F6 crit 3]`
  3. **Implement**: the disclosure line, on the existing mechanism.
  4. **Validate**: render suite against a fixture cache built without the field.
  5. **Success**: an unrefreshed index produces a report that is honest rather than confident.

- [ ] **T4.5 Read the rendered report as prose** `[activity: validate]`

  1. **Prime**: spec 032 shipped a block that said `up::` in its heading and `up` property in its fix
     line — every test green, both review gates passed, and the contradiction was visible to the
     first person who read the output as English. No test finds that, because no test reads.
  2. **Implement**: render a document containing every combination — advisory, unresolved
     body-resident, unresolved property-resident, pre-033 — and **read the result end to end**.
  3. **Validate**: no block contradicts itself; no block uses two nouns for one thing; the advisory
     and integrity sections do not describe the same situation differently.
  4. **Success**: the report reads as one voice. Record what was read, not that it was read.

- [ ] **T4.6 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - The all-advisory case renders correctly — if every flagged parent is `parent_not_moc`, the
    integrity section has no broken-parent entries `[ref: SDD/Implementation Gotchas 4]`.
