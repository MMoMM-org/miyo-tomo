---
title: "Phase 5: Integration, the live path, and one handoff"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Integration, the live path, and one handoff

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/S1]` — the documentation criteria
- `[ref: PRD/C2]` — the inventory's optional note
- `[ref: PRD/Success Metrics; Tracking Requirements]` — what the live run must exercise
- `[ref: SDD/CON-1]` — the release is coordinated and cannot be split
- `[ref: SDD/CON-8]` — the live Kokoro obligation
- `[ref: README/Decisions Log; 2026-09-30]` — the runnable test setup is a deliverable, not a nicety

**Key Decisions**:
- **One handoff, complete, after the producer side is finished** `[ref: SDD/CON-1]`.
  The consumer's vendored schema pins the version and rejects unknown properties,
  and treats a validation failure as fatal for the whole document — so an early
  ship takes their editor out of service on exactly the runs this spec serves.
- The handoff **includes a runnable run**, because their QA vault has one worthy
  card and no run anywhere carries `delete_source: true` — the control they built
  on our table is otherwise reachable only by hand.
- CON-8 is an **open constitutional obligation**: the Kokoro handoff must go out
  before or alongside the implementation, not after.

**Dependencies**: Phases 1–4 complete.

---

## Tasks

Delivers the release: documentation, a live proof, the coordinated handoff, and a
close-out that traces every criterion to a test that was executed.

- [x] **T5.1 User documentation** `[activity: documentation]` `[parallel: true]`

  1. Prime: read `docs/usage.md:48-85` ("When an attachment's name is already
     taken") and `docs/troubleshooting.md:220-259`. The usage section currently
     describes the computed name as fixed, and neither document covers a refused
     name.
  2. Test: not unit-testable. The check is a read-through against `[ref: SDD/CON-6]`
     and `[ref: SDD/CON-7]`: effect not mechanism, and nothing implying the
     owning-note list is exhaustive.
  3. Implement: state that the name is editable; describe what a refusal looks like
     and what to do; state the precedence rule plainly — once the run has been
     saved in the editor, the editor's values are the ones Pass 2 uses
     `[ref: PRD/S1]`. Add a troubleshooting entry for "I typed a name Pass 2 could
     not use", distinct from the existing apply-time refusal entry.
  4. Validate: grep the new text for function names, module names and wire action
     names — there should be none.
  5. Success:
     - [x] `usage.md` says the name is editable and covers a refusal `[ref: PRD/S1]`
       — the Rename bullet carries both halves of S1-AC2: the target is the
       backtick content and is typed over, empty when Pass 1 found no free name;
       and the three closed refusal classes are named in owner terms, with
       `taken` explicitly excluded and the accept-verbatim padding case called out
       as *not* a refusal.
     - [x] The precedence rule is stated `[ref: PRD/S1]` — **and it took two FAILs
       to state it correctly.** The first draft said the editor wins *"for anything
       you changed there"*, which promises a per-field merge; the rule is
       whole-document, because the digest can only answer *edited at all* and there
       is no field provenance on the wire to merge against. Spec compliance found it
       via the spec's own decisions log, the orchestrator via the control flow —
       `build_from_wire` runs and `main` returns before the split-and-parse block
       that reads the markdown. The second FAIL was the Rename bullet's
       back-reference saying "both" with no antecedent inside the sentence.
     - [x] A new troubleshooting entry exists, distinct from the apply-time one —
       "I Typed a Name Pass 2 Could Not Use", placed beside the existing
       "Inconsistent state" entry and opening on the distinction: this one fires
       before any action is emitted and nothing fails at apply time.
     - [x] No executor internals `[ref: SDD/CON-6]` — re-grepped across the whole
       T5.1 range (3 commits, 90 added lines in the two files) rather than per
       commit, after the orchestrator mislabelled a single-hunk grep as covering
       the range: **0 matches**. CON-7 holds too — every sentence about embedding
       notes is scoped "in this run".

- [x] **T5.2 — moved to Phase 2 as T2.1b** `[activity: data-architecture]`

  The inventory's remedy row moving off `null` was scheduled here, but T2.1 made
  the wire field exist and Phase 1's two-sided join went red the moment it did —
  `25` marked against `23` backed. This task's own step 2 said that failure "is the
  mechanism working", and it is; but left here it would have run red through
  Phases 3 and 4, each of whose gates demands a green suite. Owner ruled
  2026-10-01 to pull it forward. It also had to widen: T2.1 added **two** editable
  fields, not one, so a second row and both count guards came with it. See
  `phase-2.md`'s T2.1b. T5.3–T5.5 keep their numbers.

- [ ] **T5.3 The live run** `[activity: validate]`

  1. Prime: read `scripts/spec037-fixture.sh` and the 037 live runbook for how a
     live run is staged and reset. **`tomo-privat` is LIVE — never touch it.** All
     work is `--instance tomo-instance`.
  2. Test: the run **is** the test. Exercise, in one pass where possible: a remedy
     surviving a wire edit (F1); a typed name accepted end to end including the
     embed rewrite (F2); a typed name refused, with the owning note held and the
     instruction document reporting it (F3).
  3. Implement: sync the instance first — instance scripts go stale and a live walk
     against a stale instance proves nothing.
  4. Validate: read the rendered documents as the owner would, not as the author.
     Spec 037's four defective sentences were caught by the owner reading shipped
     output, not by review.
  5. Success:
     - [ ] A remedy survives a wire edit in a real run `[ref: PRD/F1]`
     - [ ] A typed name files the attachment and rewrites the embeds `[ref: PRD/F2]`
     - [ ] A refused name holds the note and is reported `[ref: PRD/F3]`
     - [ ] The cost log is updated, as after every live run

- [ ] **T5.4 The coordinated handoff, and the Kokoro obligation** `[activity: documentation]`

  1. Prime: read the pending handoff in `_outbox/for-hashi/`. **Measured
     2026-10-01 (T2.5): only that one is outstanding.** The Kokoro handoff
     `2026-09-29_tomo-to-kokoro_four-specs-since-july-034-through-037.md` is
     already `status: done` and Kokoro replied with ADR-029/030/031, so **CON-8
     is discharged before this phase begins** `[ref: SDD/CON-8]`. Confirm that
     reply; do not re-send it.

     **The consumer's starting position, read directly on 2026-10-02 rather than
     inferred.** Hashi's vendored `src/schema/suggestions-wire.schema.json` pins
     `schema_version` to `const: "2"`, and contains **none** of
     `attachment_conflict_remedies`, `proposed_name`, `remedy`,
     `refusal_reason` or `skipped_assets`. Across Hashi's `.ts`/`.js`/`.json`
     sources those four field names appear **zero** times. The search is sound
     rather than mis-aimed: the same grep finds `suggestions` in 98 files,
     `move_asset` in 17 and `schema_version` in 54.

     So the handoff is not a version-bump notice — **the consumer does not yet
     know the remedy exists.** Tomo moved this wire to `schema_version` 3 in T2.1
     and projected the remedies onto it in T2.2, and Hashi is reading 2 with no
     remedy fields at all. Write the handoff for a reader starting from zero on
     this feature, not one reconciling a field they already parse.

     This also cannot be checked from the suite: the test that would compare our
     vendored snapshot against Hashi's live copy is skipped on this very wire —
     see obligation 4 below and `docs/XDD/backlog.md`. The reading above was done
     by opening Hashi's file, which is the only method that currently works.
     Hashi is read-only to this repo; reading it is allowed, editing it never is.
  2. Test: not testable. The check is completeness: schema pair attached, the run
     fixture attached, the version move named, the `source`-not-`item_key` keying
     restated, and the inventory attached.
  3. Implement: one handoff to the consumer carrying the new schema, the inventory,
     and a runnable suggestions run with a real conflict — a run their QA vault
     cannot produce. Attach the artefacts rather than describing them: the 2026-09-18
     schema pair and the 2026-09-14 run fixture are the precedents. The Kokoro
     handoff needs no coupling here — it went out 2026-09-29 and is answered.

     **Carry these three. Measured in Phase 2 (T2.5); the suite can see neither
     the first nor the third.**
     - The **`handover` action itself**. The gate emits `move_version` +
       `handover` only while the version is still held back, and stops emitting
       it the moment the move completes — which T2.1 did. So no tooling will
       remind this phase that a handover is owed; this bullet is the reminder.
     - The **six reportable structural entries**, pinned at
       `tests/test_wire_snapshot_parity.py:738-752`: `schema_version` gaining
       `'3'` and losing `'2'`, `attachment_conflicts` added and required, the
       `/properties/attachment_conflicts/items` node, and `attachments` becoming
       required under `/properties/suggestions/items`.
     - **Three divergences no test can see.** `snapshot_parity_delta` compares
       structure only and ignores `description`, so `candidate_mocs[].selected`,
       `candidate_mocs[].anchor` and `proposed_mocs[].tags` already differ in
       prose between our schema and the vendored copy with the suite entirely
       green. Name them in the handoff body explicitly — nothing else surfaces
       them, and refreshing the vendored copy without them re-vendors the
       divergence.
     - **The upstream comparison may not have run at all.** Measured 2026-10-01:
       `test_wire_snapshot_parity.py`'s `_fetch_or_skip` (`:149-180`) turns a
       partial read into `pytest.skip`, and the fetch of Hashi's live
       `suggestions-wire.schema.json` truncates at the **same offset on repeated
       attempts** (`IncompleteRead(8268 read, 4306 more expected)`), so
       `test_suggestions_snapshot_matches_upstream_hashi` (`:262`) does not run
       here — on this wire it is not flaky, it is absent. The hermetic offline
       comparison still pins the six-entry delta, so drift between our two local
       files is caught; drift between our snapshot and what Hashi actually
       publishes is not, and the suite is green either way. **Do not treat a green
       suite as evidence the vendored snapshot still matches upstream.** Verify it
       against the schema the consumer confirms in the handoff instead, which this
       task already attaches. See `docs/XDD/backlog.md`, "the upstream-parity
       check skips silently".
  4. Validate: re-read the consumer's last message and confirm each of their action
     items is answered.
  5. Success:
     - [ ] One handoff, complete, with artefacts attached `[ref: SDD/CON-1]`
     - [ ] A runnable conflict run is included `[ref: README/Decisions Log]`
     - [ ] CON-8's discharge is confirmed from Kokoro's reply rather than
           re-sent — it was already `done` on 2026-09-29 `[ref: SDD/CON-8]`
     - [ ] The three description-only divergences are named in the handoff body
     - [ ] Nothing was shipped to a live wire before their copy was updated

- [ ] **T5.5 Close-out** `[activity: documentation]`

  1. Prime: read `docs/XDD/specs/037-…/close-out.md` as the model, and
     `docs/XDD/specs/036-…/close-out.md` for the trace format.
  2. Test: the close-out **is** the check. Every one of the PRD's 38 criteria maps
     to a test that was **executed**, named by node id from a real pytest
     invocation — not to a task that mentions it. This is the check that caught
     037's S2-AC1 being claimed by a parser task that structurally could not render
     anything.
  3. Implement: `close-out.md` with the full trace, the four open items this spec
     leaves behind (the hand-written inventory, the earlier-run embed break, the
     `delete_source` normalisation divergence, and anything Phase 1's discrepancy
     list did not absorb), and the honest record of what the spec cost.
  4. Validate: pick three criteria at random and verify their node ids by running
     them. A trace nobody spot-checks is a trace nobody can trust.
  5. Success:
     - [ ] All 38 PRD criteria traced to executed tests by node id `[ref: PRD]`
     - [ ] Open items recorded rather than quietly closed
     - [ ] Three traces spot-checked by execution
     - [ ] `Skill(tcs-workflow:xdd-meta)` Finalize has run — the spec reaches
           `Implemented` rather than sitting on `Ready`
