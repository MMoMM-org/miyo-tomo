---
title: "Phase 3: Honouring the remedy in Pass 2"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Honouring the remedy in Pass 2

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-3]` — reuse `skipped_assets`
- `[ref: SDD/Runtime View; Primary Flow — Pass 2]`
- `[ref: SDD/Interface Specifications; skipped_assets kind]`
- `[ref: PRD/F3]`

**Key Decisions**:
- `keep_in_inbox` records `kind: vault_collision_held` in the **existing**
  `skipped_assets`. `_subtract_skipped_assets` already lowers expected
  `move_asset` for each entry, so no new subtraction is written.
- `ignore` emits the move **unchanged** against the occupied destination and
  records **nothing** in `skipped_assets` — the audit counts it as any other
  move. Only Hashi refuses it, which is the point of the remedy.
- A rename rewrites every owning note's embed in the same task that emits the
  move. A rename that does not rewrite is a failed criterion, not a partial one.
- ADR-3's claim that the paired consumer needs no change is **proven here**, not
  assumed. The repo has already lost a Pass 2 to a coverage mismatch.
- `_walk_attachment_conflicts` reads only the FIRST `## Attachment Conflicts`
  section in the document — a deliberate contract (T2.4), not a bug. A document
  with a duplicated section yields a partial result silently, with no error.
  Decide here whether this phase's consumer needs to notice that.

**Dependencies**: Phase 2 (`remedy` must be parseable before it can be honoured).

---

## Tasks

Establishes that the owner's tick is what the vault actually receives.

- [ ] **T3.1 Each remedy produces its own outcome** `[activity: backend-api]`

  1. Prime: Read `_build_move_asset_actions` end to end `[ref: render_actions.py:640-728]` — the global `seen` dedup, the `claimed` map, the skip entries and their `kind`
  2. Test: `rename` emits a move to a name free in the vault **and** free among this run's claims `[ref: PRD/F3-AC1, Rule 5]`; `keep_in_inbox` emits no move and no action fails at apply because of it `[ref: PRD/F3-AC2]`; `ignore` emits the move unchanged against the occupied destination `[ref: PRD/F3-AC3]`; **no remedy emits an action whose destination holds a different file, except `ignore`** `[ref: PRD/F3-AC4]`; a conflict gone by Pass 2 emits the plain move `[ref: PRD/Scenario 5]`
  3. Implement: consult `remedy` before claiming a destination; keep the in-run collision path untouched
  4. Validate: full suite; `ruff`; prove the `ignore` test RED by making it behave like `keep_in_inbox`
  5. Success: the strongest outcome any remedy produces is a move to a free name `[ref: PRD/Rule 6]`; the in-run collision behaviour is unchanged `[ref: SDD/Constraints, additive only]`

- [ ] **T3.2 The coverage audit needs no new arithmetic — proven** `[activity: testing]`

  1. Prime: Read `_subtract_skipped_assets` and its docstring `[ref: instructions-diff.py:858-883]`, and `derive_expected`'s `move_asset` count `[ref: instructions-diff.py:465-476]`
  2. Test: a run with one `keep_in_inbox` conflict passes the audit with expected == actual `[ref: PRD/F3-AC5]`; a run with one `ignore` conflict passes, the move counted as any other `[ref: SDD/Interface Specifications]`; a run with one `rename` passes; a run mixing all three passes; **`instructions-diff.py` is byte-identical to its pre-change version** — the assertion that ADR-3 held
  3. Implement: nothing in `instructions-diff.py`. If a change proves necessary, that is a deviation: stop, record it, and revisit ADR-3 before proceeding `[ref: plan/README.md; Deviation Protocol]`
  4. Validate: run `instructions-diff.py` against fixtures for all three remedies and assert exit 0
  5. Success: ADR-3 is demonstrated rather than asserted `[ref: SDD/ADR-3]`; the paired-consumer trap that aborted Pass 2 on 2026-09-15 is closed by evidence

- [ ] **T3.3 A renamed attachment takes its embeds with it** `[activity: backend-api]`

  1. Prime: Read how the rendered note body is produced and where the embed text originates; read the 2026-09-15 end state — `![[Scans/karte.png]]` in an Atlas note `[ref: README.md; Context]`
  2. Test: a renamed attachment's owning note embeds the **new** name; a note embedding it twice has both rewritten; a note embedding two attachments, one renamed and one not, keeps the untouched one verbatim; an embed carrying an alias or an anchor survives the rewrite with alias and anchor intact
  3. Implement: rewrite the embed target for every owning note when the remedy is `rename`
  4. Validate: full suite; `ruff`; prove RED by emitting the move without the rewrite and asserting the note points at a name that no longer exists
  5. Success: no rendered note references a name the run did not file `[ref: PRD/F3-AC1]`; the basename survives verbatim where unchanged `[ref: render_actions.py:509 docstring]`
