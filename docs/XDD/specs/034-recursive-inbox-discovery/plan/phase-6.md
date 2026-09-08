---
title: "Phase 6: Cost history, integration and live validation"
status: in_progress
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

- [ ] **T6.0 The three destination keys Phase 5 did not fold** `[activity: backend]`
      — **Accepted 2026-09-08.** First task of Phase 6, ahead of T6.1.

  Phase 5 folded case into three destination comparisons and left three more, each found by a
  shape-grep and recorded rather than fixed because folding them changes behaviour rather than
  addressing. They are collected here because they are one shape, and because two of them are
  an emitter and its paired consumer — the exact pairing that cost this spec a task of its own
  when T5.0b moved and T5.0c did not.

  All three are live on HEAD under **CON-6**, which records this filesystem as case-insensitive,
  *verified on this host*.

  | # | site | what happens today |
  |---|---|---|
  | 1 | `_build_create_moc_actions`'s `by_dest` | `Travel (MOC)` and `travel (MOC)` both emit a `create_moc`; the second overwrites the first on apply, **dropping the first's children** — the `#67` failure that guard exists to prevent |
  | 2 | `render_resolve.py:213`'s `create_moc_by_dest` | keys the same composed destination by exact string; the paired consumer of (1) and must fold with it |
  | 3 | `_build_move_asset_actions`'s `claimed` | `A/Ufer.jpg` and `B/ufer.jpg` both emit a `move_asset`; the second overwrites the first, and **no skip is recorded — so T5.4's suppression never fires** and both notes are filed |

  **(3) is the one to weigh first.** It is not merely an unfolded key: T5.4 built a guard whose
  trigger is a recorded skip, and this path records none. The feature has a blind spot exactly
  where CON-6 says the filesystem will bite, and the user sees nothing — the notes file, the
  attachment is overwritten, no report mentions it.

  **Why folding is right here, same asymmetry as T5.3**: on a case-insensitive filesystem, not
  folding loses data and cannot be undone; on a case-sensitive one, folding costs a rename and
  can. That reasoning is recorded in T5.3's block and applies unchanged.

  **`seen` is not a fourth site — fold `claimed` only. Added 2026-09-08 while reading site (3).**
  `_build_move_asset_actions` keeps two exact-string collections and they are not the same shape.
  `claimed` keys the **destination**, and folding it is right for the reason above. `seen` keys the
  **source path**, and the T5.3 asymmetry inverts there:

  - Not folding `seen`, on a case-insensitive filesystem: `100 Inbox/Ufer.jpg` and
    `100 Inbox/ufer.jpg` are one file seen twice. The first moves; the second now meets a folded
    `claimed` and is **recorded as a collision skip**, so T5.4 keeps its note in the inbox. Wrong
    about the cause, conservative in effect, and *reported* — the user reads a line naming both
    paths and renames one.
  - Folding `seen`, on a case-sensitive filesystem: two genuinely distinct files collapse to one.
    One moves, the other is **dropped with no skip recorded at all** — the exact silence T5.4's
    guard exists to break, re-created one layer up.

  So: fold `claimed`, leave `seen` exact. That ordering is what makes the second bullet
  unreachable, and it is only safe *because* `claimed` folds — do not fold one without the other.
  A test must pin this pair, not just the collision.

  1. **Prime**: read `docs/tomo/scripts/lib/render_actions.md` — the T5.3 sweep records sites
     (1) and (2) with their reachability, the T5.4 section records (3). Read T5.3's
     `validate_destinations` and T5.2's `resolve_destination_clashes` for the folding form
     already in use (`casefold()`, not `.lower()` — `ß` folds to `ss` and these are German
     notes) `[ref: SDD/CON-6, ADR-4]`.
  2. **Test** (RED): each site's collision, proven red by reverting to exact comparison. For
     (3), additionally assert that a skip IS now recorded and that T5.4's suppression
     consequently fires — the point is not the fold but the guard it re-arms.
  3. **Implement**: fold (1) and (2) **together**; a fold on one without the other re-creates
     the emitter/consumer divergence this spec has already paid for twice. Reuse
     `lib/source_link.py`'s collision helpers where they fit rather than adding a fourth copy.
  4. **Validate**: tests pass; `ruff` clean; neither action golden re-recorded — if a no-clash
     run changes, that is a real regression, not a fixture to refresh.
  5. **Success**:
     - [ ] Two MOC proposals differing only in case cannot silently drop one's children
     - [ ] An attachment collision differing only in case records a skip, so T5.4's guard fires

- [ ] **T6.0b An atomic and a MOC can claim the same path, and nothing compares them**
      `[activity: backend]` — **PROPOSED 2026-09-08, not yet accepted.**

  Kept separate from T6.0 deliberately: this is not an unfolded key but a **missing comparison
  across two action kinds**, and closing it cascades.

  An atomic named `Travel (MOC)` filed into the MOC folder composes the same destination as a
  `create_moc` for `Travel (MOC)`. `_build_create_moc_actions` dedups create_moc against
  create_moc; `_build_move_note_actions` has no guard at all; T5.2's Pass-1 check compares
  atomics against atomics; T5.3's `validate_destinations` groups `move_note` only. No pass sees
  both kinds.

  Why it is its own task: dropping a `create_moc` cascades into the `link_to_moc` and
  up-preservation actions that target it. That is a behaviour change with its own blast radius,
  not an addressing fix, and it wants its own design rather than being folded into a
  case-folding sweep. Recorded by T5.2 in `docs/tomo/scripts/suggestions-reducer.md` and by
  T5.3 in `render_actions.md`.

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

     **Give the wire/markdown parity golden a collision fixture — added 2026-09-08.**
     `tests/test_suggestions_wire_golden.py` exists to catch the two parser paths diverging,
     and every fixture in it uses single stems (`memo`, `S01`) with no two items sharing a
     filename. So it is blind to divergence that only appears on a collision — which is the
     only kind this spec can produce. T5.1 proved that concretely: its first cut took the
     wikilink *target* instead of the alias, diverging the two paths precisely on the collision
     case, and the parity golden stayed green. Six other tests caught it, by luck of what they
     happened to assert. Add a two-namesake fixture to that golden so the test covers the case
     it was written for.
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
