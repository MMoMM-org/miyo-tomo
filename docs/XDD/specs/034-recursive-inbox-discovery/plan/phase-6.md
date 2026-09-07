---
title: "Phase 6: Cost history, integration and live validation"
status: pending
version: "1.0"
phase: 6
---

# Phase 6: Cost history, integration and live validation

## Phase Context

**GATE**: read these before starting.

**Specification References**:
- `[ref: PRD/Feature 6]` and `[ref: PRD/Success Metrics]`
- `[ref: SDD/Data Storage Changes; cost_history]`
- `[ref: SDD/Quality Requirements]`
- `[ref: SDD/Constraints; CON-1, CON-7]`

**Key Decisions**:
- The container cannot see `docs/`, so the run writes its cost entry into the instance's own
  persistent state. Transcribing a notable run into the repository's cost log stays a
  deliberate host-side act.
- Live validation is the user's to run. No task here may attempt it `[ref: SDD/CON-7]`.

**Dependencies**: Phase 5 complete.

---

## Tasks

- [ ] **T6.1 The run records its own cost** `[activity: backend]`

  **Added 2026-09-06 by the Phase 3 gate — the number this task is about to make durable cannot
  detect its own regression.** `_count_kado_calls` (`inbox-triage.py:1863`) hardcodes the base as a
  literal `2`. The gate proved the consequence rather than arguing it: when it mutated
  `build_attachment_index(all_files)` back to a second `client.list_dir(...)` call, the fake client
  recorded **3** base calls while the estimator still printed `kado_calls=9`. Nothing in the suite
  observed the true count until that gate ran.

  ADR-3's whole claim is that recursion makes discovery *cheaper* — base calls 3 → 2 — and this
  task writes that figure into a permanent history. A history whose source is a constant records
  the intent, not the behaviour, and would keep reporting 2 through any future change that
  reintroduces a listing.

  **T5.2 added a second kind of listing — expect the observed count to move, and say why.**
  Added 2026-09-07. `_vault_folder_notes` (`suggestions-reducer.py`) issues one cached
  `list_dir(location, depth=1)` per distinct **destination** folder, to check whether a proposed
  name is already taken. Two things follow, and neither is a defect to fix here:

  - It is not an inbox listing, so F9's first criterion ("directory listings **of the inbox**")
    is untouched. Do not count it against that.
  - It is a real per-run cost that scales with the number of distinct destination folders in the
    run, and it is currently **unmeasured**. F9's second criterion asks for the actual figure to
    be recorded, and its user story is "recursion does not make my runs more expensive". Record
    it as its own line rather than folding it into the base — a single number that mixes a fixed
    pipeline cost with a content-scaling one tells the user nothing about either.

  Precedent for treating it as outside the base bucket: the pre-existing I38 daily-note existence
  probe is already a per-item, content-scaling Kado cost and has never been counted as a base
  call. T5.2's listing follows that pattern. Surfaced by T5.2's compliance review, which judged
  the literal text not violated and flagged the tension here rather than failing the task.

  So this task must also:
  - Derive the recorded base count from the run's **observed** Kado calls, not a literal. If the
    client cannot report its own call count today, add that capability rather than keeping the
    constant.
  - Report the destination-folder listings separately from the base count, with the folder count
    that produced them, so a future reader can tell a pipeline regression from a busy run.
  - Add a test that **fails** when a second base listing is reintroduced — the exact mutation the
    gate ran. The plan already states the principle for T3.4: *"the estimator is the thing under
    test, so it cannot also be the evidence."* The same holds once the estimator's output is being
    persisted.
  - If the count genuinely cannot be observed without disproportionate change, say so and record
    the constant as a known limitation **in the history's own schema**, so a later reader knows the
    figure is declared rather than measured.

  1. **Prime**: Read `[ref: SDD/Data Storage Changes; cost_history]`. Read
     `mark-captured.py:78-79`, whose `state/moc-squelch.json` default is the precedent — a small
     persistent registry in the instance state, addressed cwd-relative. Read
     `_count_kado_calls` (`inbox-triage.py:1738-1778`), whose base term changes from 3 to 2 in
     Phase 3.
  2. **Test** (RED):
     - a completed Pass 1 appends one entry with its timestamp, run id, item count and call
       counts `[ref: PRD/AC Feature 6]`
     - several runs accumulate — an entry is never overwritten by a later one
     - clearing the working directory leaves earlier entries intact
     - an unwritable history warns and the run continues; measurement must never fail a run
       `[ref: SDD/Error Handling]`
  3. **Implement**: append-only JSONL in the instance's persistent state directory.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] A history accumulates without anyone remembering to record it
           `[ref: PRD/AC Feature 6]`

- [ ] **T6.2 Integration across the whole pipeline** `[activity: test-strategy]`

  1. **Prime**: Read `[ref: SDD/Runtime View]` and `[ref: SDD/Quality Requirements]`.
  2. **Test**:
     - end to end over a fixture inbox containing: a root note, a subfolder note, a nested
       note, two namesakes in different subfolders, a namesake pair of attachments, a note with
       no embed, and an audio file with a namesake elsewhere
     - assert at every artefact boundary, not only at the end — routing plan, per-item results,
       suggestions document, wire, parsed suggestions, instruction set
     - assert the instruction set is byte-identical for the flat-inbox subset `[ref: SDD/CON-4]`
  3. **Implement**: n/a — test only.
  4. **Validate**: full suite green; `ruff` clean.
  5. **Success**:
     - [ ] Every PRD feature has a passing end-to-end assertion, walked one by one against the
           feature list `[ref: PRD/Feature Requirements]`

- [ ] **T6.3 Prepare the live-validation fixtures** `[activity: validate]`

  1. **Prime**: Read `[ref: SDD/CON-7]`. Read the spec 031 T6.5 entry in
     `docs/evolution/inbox-cost-log.md` — its first run produced nothing because the fixtures
     sat in a subfolder that discovery could not see. That failure is this spec's subject, so
     the same fixtures should now work; do not assume it, check it.
  2. **Test**: n/a — preparation.
  3. **Implement**: place fixtures in the test vault covering the cases in T6.2, and state in
     the phase notes exactly what each one proves and what the expected output is, so the
     result can be read against an expectation rather than interpreted after the fact.
  4. **Validate**: a host-side dry run of the resolution chain over the real fixture layout
     agrees with the expectation before anything live is attempted.
  5. **Success**:
     - [ ] Every fixture has a written expected outcome `[ref: PRD/Success Metrics]`

- [ ] **T6.4 Live validation** `[activity: validate]` — **the user's to run, not the
      implementation's.** Not skipped, not forgotten.

  1. **Prime**: `./scripts/update-tomo.sh --yolo` first — the bare form stalls without copying,
     and an unchanged `# version:` ships nothing. Grep the instance afterwards to confirm the
     files actually arrived.
  2. **Test**: run `/inbox` in the container against the prepared vault and check:
     - the subfolder note appears in the suggestions document
     - two namesakes appear as two suggestions with distinguishable links
     - a destination clash halts both and says so
     - an attachment clash keeps its note in the inbox
     - after apply: the right notes are filed, the right sources marked, nothing left behind
       that should have moved
  3. **Implement**: n/a — validation only.
  4. **Validate**: record the outcome, the item count and the observed Kado call count in
     `docs/evolution/inbox-cost-log.md`, and compare the base count against the expected 2.
  5. **Success**:
     - [ ] A note in a subfolder is triaged, filed, and its source marked — end to end in a
           real vault `[ref: PRD/Success Metrics]`

- [ ] **T6.5 Phase Validation and close-out** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Walk the SDD Quality Requirements table and confirm each row has a passing measurement.
  - Walk the PRD's 40 acceptance criteria and confirm each maps to something green.
  - Write the handoff to the sibling component describing the widened bare-name ambiguity in
    its own matching, aimed at the wire builder `[ref: spec 034 README, Hashi decision]`.
  - Set the spec to `Implemented` via `xdd-meta finalize` — only after T6.4 passes. A spec left
    on `Ready` after shipping is the failure this step exists to prevent.
