---
title: "Phase 5: Reporting, and the delete that waits"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Reporting, and the delete that waits

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F2-AC5, F2-AC8, F3-AC5, F3-AC6, F6]`
- `[ref: SDD/ADR-8, ADR-10]`
- `[ref: SDD/Error Handling]`
- `[ref: SDD/Constraints; CON-2, CON-6]`
- `[ref: research.md/R1 §2, R4 §1 (036's four delete sites), R4 §2 (ADR-029)]`

**Key Decisions**:
- Rendered text states only what was verified (038 CON-6/F3-AC7). "Will be created" is the executor's documented contract (PRD A3), not a prediction.
- The delete waits for **every** `move_asset` of its origin's attachments, including one shared with another origin (F6-AC3, accepted).
- The executor is not changed; its behaviour is asserted from its code and confirmed in the release handoff.

**Dependencies**: Phase 4. **T5.2 additionally requires T1.1 sent** (CON-2).

---

## Tasks

Delivers what the owner reads about the new outcomes, and the dependency that keeps an origin until its attachments arrive.

- [x] **T5.1 Instruction document and shell relay for the new outcomes** `[activity: backend]` `[parallel: true]`

  1. Prime: `render_md.py:76-151, 838-880, 1031-1180`; `render_actions.py:1036-1066, 1494-1520`; `instruction-render.py:1039-1046`; `tomo-tmp/withheld-attachments.md` writer (038 T4.5) `[ref: SDD/Components K7, K8]`
  2. Test: `vault_occupied` bullet names the attachment, the target and its occupier in attachment wording — never "a note already exists" (F3-AC5); `typed_folder_refused` bullet names the attachment and the rule broken, one sentence per reason (F2-AC5); unchecked targets listed as "not checked", never as free (F3-AC6); folders to be created listed (F2-AC8); qualified embeds mentioned with reason ambiguous/unanswered (tracking table); the Ignore disclosure now says the origin is kept if the move fails and no longer says the note is filed either way (F6-AC8); the shell relay file carries one line per withheld attachment and per unchecked target — never a count (038 C1 ruling); `tomo/dot_claude/agents/synthesis-conductor.md:215-217` relays the new unchecked lines (WHY written to its `docs/tomo/` mirror first; `# version:` bumped); no executor internals in any sentence
  3. Implement: renderer branches using K16's sentences; relay lines; conductor imperative. Carried from Phase 3: a malformed folder line (no backticks, a lone backtick, text after the closing one) and two disagreeing folder lines both reach K1 as `""` and are refused `blank`; the owner-facing sentence must not claim the owner left it blank — word the `blank` folder sentence to cover an unreadable folder line, or carry a distinct reason. Carried from T4.5: add `--cost-history state/inbox-cost-history.jsonl` to the `instruction-render.py` call in `synthesis-conductor.md` step 3b — until then C1-AC1 holds only at the `main()` level (the flag defaults to absent so host tests never write `state/`)
  4. Validate: read the rendered document for a fixture covering every kind once; ruff clean
  5. Success: `[ref: PRD/F2-AC5]` `[ref: PRD/F2-AC8]` `[ref: PRD/F3-AC5]` `[ref: PRD/F3-AC6]` `[ref: PRD/F6-AC8]`

- [x] **T5.2 The origin's delete depends on its attachment moves (#186)** `[activity: backend]` `[parallel: true]`

  1. Prime: `render_actions.py:1969-2218` (site 3 at :2096-2165), `:2721-2783` (`withdraw_unjustified_deletes`), `:2841-2862`; `tomo/schemas/instructions.schema.json:253` `[ref: SDD/ADR-10]`. **Gate:** T1.1 sent (CON-2)
  2. Test: origin with one note and two moved attachments → `depends_on` = note id(s) then both asset ids, audio-peer delete identical (F6-AC1); attachment shared by two origins → both deletes name its single id (F6-AC3); a withheld attachment's id appears in no delete (F6-AC4); Keep in inbox → `depends_on` unchanged from today (F6-AC5); a `move_asset` withdrawn by a later guard → the delete is withdrawn by the existing id pass; 036's F5-AC1..AC4 tests green (always present, `[]` explicit, all partners named, no dangling id); Tomo's `instructions.schema.json` description names `move_asset`; the vendored `hashi-instructions.schema.json` stays byte-identical to the consumer's until T6.2 (F6-AC6 completes there); `tests/test_036_*` that pin exact `depends_on` lists reviewed — fixtures with attachments updated with a stated reason
  3. Implement: `build_actions` passes `move_ids_by_origin` to site 3; description text in Tomo's instructions schema
  4. Validate: suite green; instructions-diff paired consumer (`derive_expected`) updated if it re-derives `depends_on`
  5. Success: `[ref: PRD/F6-AC1]` `[ref: PRD/F6-AC3]` `[ref: PRD/F6-AC4]` `[ref: PRD/F6-AC5]`; Tomo half of `[ref: PRD/F6-AC6]`

- [x] **T5.3 The executor needs no change — asserted** `[activity: testing]`

  1. Prime: Hashi `src/executor/planner.ts:39-56, 264-290`, `src/actions/moveAsset.ts:72-87` (read only — no edits in Hashi) `[ref: PRD/F6-AC7, A4]`
  2. Test: a Tomo-side test that every `delete_source.depends_on` id resolves to an action of a kind the vendored instructions schema allows, and that `move_asset` precedes `delete_source` in the vendored kind order if the schema or a vendored artefact records it; the rest is a written trace (file:line) of the planner's skip-on-failed-dependency path, recorded in `docs/tomo/` and asked to be confirmed by Hashi in T6.2
  3. Implement: test + trace
  4. Validate: trace reviewed against the Hashi tree at a named commit
  5. Success: `[ref: PRD/F6-AC7]`; `[ref: PRD/F6-AC2]` by trace now, by live run in T6.3

- [ ] **T5.4 Phase 5 validation** `[activity: validate]`

  - Full suite green; ruff clean; the rendered fixture document read end to end by a reviewer; Kokoro handoff answered before merge; a rejection reverts T5.2 on the branch (CON-2).
