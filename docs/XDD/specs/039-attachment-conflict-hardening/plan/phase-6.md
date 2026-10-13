---
title: "Phase 6: Release, live run, close-out"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Release, live run, close-out

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/S1, F1-AC4, F4-AC7, F6-AC2]`
- `[ref: SDD/Deployment View]` — release order
- `[ref: SDD/Constraints; CON-1]`
- `[ref: research.md/R2 §6]` — the docs to update
- Close-out precedent: `docs/XDD/specs/038-every-editable-decision-reaches-the-wire/close-out.md`

**Key Decisions**:
- Every PRD criterion is traced to a test node id executed in **one** pytest invocation (the 036–038 close-out rule).
- The live run targets `tomo-instance`, never `tomo-privat`; sync the instance first and grep that the new versions arrived.
- The vendored consumer copy moves to v4 only after Hashi confirms (038 ADR-1 pattern).

**Dependencies**: Phases 1–5.

---

## Tasks

Delivers the owner documentation, the coordinated release to Hashi, a live run, and the evidence that every criterion holds.

- [ ] **T6.1 Owner documentation and WHY mirrors** `[activity: documentation]` `[parallel: true]`

  1. Prime: `docs/usage.md:48-97`, `docs/troubleshooting.md:222-250`, `docs/instructions-json.md:768-800`; research.md R2 §6 list of `docs/tomo/` mirrors `[ref: PRD/S1]`
  2. Test: n/a (docs). Checklist: usage describes the folder line, the folder and name refusal rules, and that Hashi's editor sanitises what the markdown refuses (S1-AC1); troubleshooting no longer says the destination is checked only in Pass 1 and explains "occupied" and "not checked" (S1-AC2); every changed script's `docs/tomo/` mirror carries the WHY for its change; no executor internals in user docs; carried from Phase 4: `vault_paths.py`'s module docstring and `docs/tomo/scripts/lib/vault_paths.md` still say `path_key` is the one key every comparison uses — name the sanctioned exception `nfc_lower` (audio↔transcript pairing)
  3. Implement: edits
  4. Validate: reader test — someone who has not read the spec can resolve a refused folder from the docs alone
  5. Success: `[ref: PRD/S1-AC1]` `[ref: PRD/S1-AC2]`

- [ ] **T6.2 Release handoff to Hashi, then vendored copy to v4** `[activity: integration]`

  1. Prime: T1.2's reply and any answer; 038's wire-v3 handoff as the template `[ref: SDD/Deployment View; PRD/CON-1, CON-3]`
  2. Test: after Hashi confirms vendoring, the vendored suggestions copy equals Tomo's live v4 schema byte-identically and the parity test's delta is empty; the vendored instructions copy equals the consumer's updated file (`cmp`), carrying the new `depends_on` description (F6-AC6)
  3. Implement: `/miyo-outbox` handoff with the v4 schema, shape manifest, inventory (D26), the `depends_on` description change, a runnable test run (precedent: 038's run fixture), and the asks — confirm the executor cascade for `move_asset` (F6-AC7) and a three-candidate tie-break probe only if F4 ever needs it (A1 and A3 measured by Hashi 2026-10-12); then refresh both vendored copies. State that #141 ships once, on v4, with the picker — no interim v3 release (owner ruling via Kokoro, ADR-029 §7, 2026-10-12)
  4. Validate: Hashi's confirmation recorded in the README decisions log
  5. Success: consumer on v4 `[ref: PRD/CON-1]`; consumer half of `[ref: PRD/F6-AC6]`

- [ ] **T6.3 End-to-end, live run and close-out** `[activity: validate]`

  1. Prime: `close-out.md` of 038; memory notes on syncing the instance before a live walk and on update-tomo being version-gated `[ref: PRD/Success Metrics]`
  2. Test: (a) convergence — the same typed folder decision through the markdown path and the wire path produces identical instruction sets (extend `test_038_t4_4_the_two_paths_converge.py`) (F1-AC4); (b) a note rendered by this run with a qualified embed, fed to triage's embed extraction, is recognised as an attachment (F4-AC7); (c) live run on `tomo-instance`: a conflict resolved by folder only, a forced ambiguous basename, a refused folder, and an Ignore whose move fails at apply — the origin survives (F6-AC2); (c2) after applying a run with a held attachment whose target is still taken, `/inbox --recover` re-intakes the held note and the new suggestions document offers the attachment's folder/name again (T5.4 owner ruling 2026-10-13 — the after-apply remedy depends on it); (d) one pytest invocation executing every node id in the trace
  3. Implement: tests, live run notes, `close-out.md` mapping all 53 criteria to node ids or to the live run
  4. Validate: the trace is checked by a reviewer who re-runs the listed node ids
  5. Success: `[ref: PRD/F1-AC4]` `[ref: PRD/F4-AC7]` `[ref: PRD/F6-AC2]`; Success Metrics met

- [ ] **T6.4 Backlog, memory and spec finalisation** `[activity: documentation]`

  - Backlog: resolve `:1109`, `:1757`, `:1917`, `:1956`, `:2457`, `:2500` with SHAs; update `:1149` ("no occupancy check anywhere in Pass 2" is no longer true); add the out-of-scope items (empty typed name stays `:1839`, fan-wire conflicts, edited-wire schema validation). Close GitHub #185 and #186 with references; the PR cites spec 039, #185 and #186. Record the net line-count change of `render_actions.py`, `suggestion-parser.py` and `suggestions-reducer.py`, and file a backlog item to split `render_actions.py` if it grew. Add the close-out to `docs/ai/memory/memory.md` Critical Documentation. Finalise the spec via xdd-meta.
