---
title: "Phase 2: Thread the key through the pipeline"
status: in_progress
version: "1.0"
phase: 2
---

# Phase 2: Thread the key through the pipeline

## Phase Context

**GATE**: read these before starting.

**Specification References**:
- `[ref: SDD/Building Block View; Directory Map]`
- `[ref: SDD/Integration Points; inter_stage]`
- `[ref: SDD/Constraints; CON-4, CON-5]`
- `[ref: PRD/Feature 2, Feature 3]`
- `[ref: PRD/Business Rules 6-9]`
- `docs/XDD/specs/034-recursive-inbox-discovery/README.md` — the blast-radius table

**Key Decisions**:
- Every join, dict key, set membership and filename uses `item_key`.
- `stem` keeps its display job and **only** that job.
- What Hashi receives does not change — `render_helpers._stem()` already flattens at the
  emission boundary `[ref: SDD/CON-4]`.
- Both derivation paths — the daily-log `source_stem` path and the primary/resolve-doc
  `source_path` path — must go through **one** function, or #165's defect returns in a form
  its regression test will not catch `[ref: SDD/Implementation Gotchas]`.

**Dependencies**: Phase 1 complete.

**Visible effect**: none, still. The inbox is flat until Phase 3, so no collision can occur
yet. This phase makes the pipeline *ready* for one.

---

## Tasks

Replaces bare-filename identity with `item_key` at every site that joins, keys or names. The
blast-radius table in the spec README is the checklist; a site left behind fails silently
rather than loudly, which is why T2.8 exists.

- [x] **T2.1 `inbox-triage` emits `item_key` per item** `[activity: backend]`

  1. **Prime**: Read `discover_files` (`inbox-triage.py:167-193`) and how items flow into the
     routing plan. Read `[ref: SDD/Integration Points]`.
  2. **Test** (RED):
     - every discovered item carries both `item_key` (its path) and `stem` (its filename)
     - the key is the path verbatim, not normalised, lowercased or slugged
     - a flat-inbox run produces the same items as before, plus the new field
  3. **Implement**: populate `item_key` via `lib.item_key.derive` wherever an item is built.
  4. **Validate**: unit tests pass; `ruff` clean; routing-plan output validates against the
     Phase-1 schema.
  5. **Success**:
     - [ ] Downstream stages receive an identity they can use `[ref: SDD/inter_stage]`

- [ ] **T2.2 The analyst contract carries the key** `[activity: prompt-engineering]`

  **BLOCKING, added 2026-09-06 — the runtime pipeline is broken until this task lands.** T2.4 made
  `--item-key` a **required** argument of `state-update.py`. `inbox-analyst.md` invokes that script
  at four sites — `:53`, `:91`, `:742`, `:750` (Step 0, Step 2b, and both branches of Step 11) —
  and **none of them pass it**. Every analyst dispatch now dies at argparse. Nothing in pytest
  catches this: these runtime files are LLM-loaded markdown, not collected by the suite, so the
  break is invisible until a live `/inbox` run.

  This task must therefore also:
  - Add `--item-key "<path>"` at all four call sites. No new plumbing is needed — the agent's IO
    Contract already receives `path`, and `derive()` is the identity function, so the item key **is**
    that value. Do not reconstruct it from `stem`.
  - Add `item_key` to the IO Contract input list (`:24-33`), which currently names only `stem`,
    `path`, `shared_ctx_path`, `state_path`, `items_dir`, `run_id`, `force_atomic`.
  - Verify no *other* runtime file under `tomo/dot_claude/` or `tomo/skills/` invokes
    `state-update.py` without the flag. Grep, do not assume — the four above were found by grep
    after an earlier sweep missed them.

  `suggestion-conductor.md` was checked and needs no change: the analyst already receives `path`,
  so nothing new has to be handed down.

  1. **Prime**: Read `tomo/dot_claude/agents/inbox-analyst.md` at `:28` (defines stem), `:37`
     (output path), `:43` (forbids writing elsewhere) and `:613-616` (stamps `source_stem`).
     Read `[ref: SDD/CON-5]` — this file is LLM-loaded verbatim and carries imperatives only.
     Read the existing `docs/tomo/dot_claude/agents/inbox-analyst.md`.
  2. **Test** (RED):
     - a fixture analyst result written to the new filename is found by the reducer
     - the contract file contains no rationale prose — only the instruction
     - `docs/tomo/dot_claude/agents/inbox-analyst.md` gains a WHY section explaining the
       identity split; the runtime file does not
  3. **Implement**: update the output-path instruction and the `item_key` stamping in the agent
     file. Write the WHY counterpart **first**, then strip nothing from the runtime file that
     the counterpart has not captured `[ref: SDD/CON-5]`.
  4. **Validate**: tests pass; the agent file is still imperative-only.
  5. **Success**:
     - [ ] The analyst writes where the reducer reads `[ref: SDD/inter_stage]`
     - [ ] No rationale leaked into a runtime file `[ref: SDD/CON-5]`

- [ ] **T2.3 The reducer reads by key, displays by stem** `[activity: backend]`

  **Extended 2026-09-06 — two runtime skills still instruct the old filename, and the interim
  window is live.** T2.2 changed `inbox-analyst.md` to write its result under
  `lib.item_key.to_filename(item_key)`. But the two skills that build the analyst's dispatch prompt
  still say `tomo-tmp/items/<stem>.result.json` — `suggest-handling/SKILL.md:86` and
  `force-atomic-handling/SKILL.md:78`. The agent contract and the dispatching skill now contradict
  each other, and because both are LLM-loaded verbatim, that produces **nondeterministic**
  behaviour rather than an honest failure — worse than either being consistently wrong.

  Until this task lands, the analyst writes where the reducer cannot read, and
  `suggestions-reducer.py:1716` **silently `continue`s** past a missing result file, so an item
  simply vanishes from the run. That is the failure this task's own RED case ("a missing result
  file is reported, not skipped") exists to close — it is not hypothetical, it is the current state
  of the branch.

  So in addition to the read-side change, this task must:
  - Update both SKILL.md dispatch instructions to the new filename. Imperatives only, CON-5; write
    the `docs/tomo/` counterparts first if any rationale needs recording.
  - Delete `tests/test_034_t2_2_analyst_contract.py::test_reducer_lookup_is_not_yet_item_key_aware`,
    or convert it to a positive assertion. T2.2 wrote it as `xfail(strict=True)` against the literal
    `items_dir / f"{stem}.result.json"` at `:1677` and `:1715`, precisely so that removing that
    pattern turns the xfail into a hard failure and forces you to deal with it. That is by design —
    do not simply loosen the strictness.

  **Added 2026-09-06 — a second state-replay reader nobody owned.** `last_state_per_stem` is
  **duplicated**: `suggestions-reducer.py:78` (called at `:1652`) and `mark-captured.py:44`
  (called at `:108`). Both replay `inbox-state.jsonl` with `out[stem] = obj`, last-wins per bare
  filename. T2.4 keyed `state-update.py`'s writer and reader on `item_key`, but these two readers
  were left behind and no task named the reducer's copy. Once Phase 3 lands, one item's
  `done`/`failed` status masks its namesake's and that item silently drops out of the work list —
  PRD Feature 2's failure mode.

  Two divergent copies of one replay is also how #165 happened, so do not simply patch both in
  place. **Extract a single shared helper into `tomo/scripts/lib/` keyed on `item_key`** and route
  the reducer's call site through it. Leave `mark-captured.py` alone — T2.5 consumes the same
  helper and must run after this task. Add a test proving two entries sharing a `stem` but
  differing in `item_key` both survive the replay with their own status.

  1. **Prime**: Read `suggestions-reducer.py:1638→1715` (the result-file read) and the display
     sites. **Enumerate the display sites yourself** — grep `or stem` and `[[{stem}]]`; a first
     draft of the SDD undercounted them by half `[ref: SDD/Implementation Gotchas]`.
  2. **Test** (RED):
     - the reducer finds `items/<encoded key>.result.json`
     - a **missing** result file is **reported**, not skipped — today `:1715-1717` skips in
       silence, which is how an item vanishes `[ref: SDD/Error Handling]`
     - every display site still renders the bare filename; no rendered title or link contains a
       path-derived key `[ref: PRD/AC Feature 2]`
     - two items sharing a filename each read their own result file
  3. **Implement**: derive the filename through `lib.item_key.to_filename`; leave every display
     site on `stem`; turn the silent skip into a report.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] No result file can be overwritten by another item `[ref: PRD/AC Feature 2]`
     - [ ] A vanished item is now audible `[ref: PRD/Risks]`

- [ ] **T2.3b The wire projection carries the key** `[activity: backend]`

  **Extended 2026-09-06 — this task owns the consumer too, not just the producer.** T2.6 re-keyed
  the Force-Atomic reconciliation onto `item_key` at 13 sites, but could not reach
  `suggestion-parser.py`'s `_stem_lower` (`:251`), which serves `build_from_wire`'s ADR-026
  wire-edit path and joins on the wire's deliberately bare `stem`. `_stem_lower` does
  `rsplit("/")[-1]` **and** `.lower()` — the full collapse — and drives `stem_to_id` member-id
  binding at `:388`, `:395`, `:397`. Two same-named notes therefore bind a MOC member to the wrong
  item: the exact defect T2.6 fixed, surviving in the one path it had no key for.

  T2.6 was correct to leave it — the wire carried no `item_key` until this task. Now that it does,
  **this task must re-key that consumer**:
  - Route `:388`, `:395`, `:397` onto the wire's `item_key` via the module-level `_item_key_of`
    T2.6 hoisted. Do not write a second derivation — one function, per the SDD gotcha.
  - Add a test proving a MOC member binds to the source that justified it, not to a namesake,
    **through the wire path** specifically.
  - Leave the wire's `stem` bare and untouched: CON-4, it is what Hashi joins on.
  - If `_stem_lower` has no remaining caller afterwards, remove it; if it still serves display, keep
    it and say which uses remain.

  Adding `item_key` to the wire without re-keying its consumer would leave a field nothing reads —
  the spec 031 failure this plan is sequenced to avoid.

  Added 2026-09-06 at the Phase 2 boundary. `suggestions-render.py` is a live pipeline stage
  (`suggest-handling/SKILL.md:108`, `force-atomic-handling/SKILL.md:92`) that projects the
  suggestions document to `suggestions-wire.json`, but it is named in no SDD directory-map row
  and no task. T2.8's gate requires the key at the **wire** boundary, so the phase cannot pass
  without it.

  1. **Prime**: Read `suggestions-render.py:277` (`_wire_note`) and `:314`
     (`build_wire_payload`). Note `_wire_note` builds `{"id": sid, "stem": section["stem"], ...}`
     and projects no identity field beyond `stem`.
  2. **Test** (RED):
     - a wire suggestion carries the `item_key` of the section it was projected from
     - two sections sharing a `stem` project to two wire suggestions with distinct `item_key`
     - the wire validates against `suggestions-wire.schema.json` `[ref: SDD/Data Storage Changes]`
     - `stem` is still present and still the bare filename — the wire is what Hashi joins on
       `[ref: SDD/CON-4]`
  3. **Implement**: project `item_key` from the section in `_wire_note`. Change nothing else
     about the wire's shape.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] These three known-red tests go green:
           `test_031_t3_3_attachments_wire_projection.py::test_build_wire_payload_carries_attachments_and_validates`,
           `test_suggestions_wire_emit.py::test_wire_conforms_to_schema`,
           `test_suggestions_wire_emit.py::test_fan_doc_wire_conforms_to_schema`
     - [ ] What Hashi joins on is unchanged `[ref: SDD/CON-4]`

- [x] **T2.4 Run state joins on the key** `[activity: backend]` `[parallel: true]`

  1. **Prime**: Read `state-update.py:39,52,76,82` — `inbox-state.jsonl` is an append-only log
     on disk, replayed last-wins per key.
  2. **Test** (RED):
     - two items with the same filename record independent state entries
     - replay returns each item's own last entry, not one masking the other
     - existing single-item behaviour is unchanged
  3. **Implement**: write and join on `item_key`.
  4. **Validate**: tests pass; entries validate against `state-entry.schema.json`.
  5. **Success**:
     - [ ] One item's status can no longer hide another's `[ref: PRD/AC Feature 2]`

- [ ] **T2.5 The captured mark targets the right note** `[activity: backend]`

  **Depends on T2.3.** T2.3 extracts the shared `item_key`-keyed state-replay helper into
  `tomo/scripts/lib/` (replacing the duplicated `last_state_per_stem` in
  `suggestions-reducer.py:78` and here at `mark-captured.py:44`). **Use that helper — do not write
  a third copy.** If it is not present when you start, stop and report `BLOCKED` rather than
  duplicating the logic.

  1. **Prime**: Read `mark-captured.py:44-49` (`last_state_per_stem`, last-wins) and `:161`
     (`client.write_frontmatter`). This is the only path in the spec where a collision mutates
     the user's vault `[ref: SDD/External Interfaces]`.
  2. **Test** (RED):
     - with two same-named notes and only one approved, frontmatter is written to the approved
       note and the other is untouched `[ref: PRD/AC Feature 3]`
     - when the source cannot be addressed unambiguously, **nothing is written**
       `[ref: PRD/Business Rule 7]`
     - the existing single-note path is unchanged
  3. **Implement**: key the replay on `item_key`; keep writing to the entry's own stored path.
  4. **Validate**: tests pass; the write path is exercised against a fake client, never a live
     vault `[ref: SDD/CON-7]`.
  5. **Success**:
     - [ ] Zero wrong-note writes in a clash scenario `[ref: PRD/Success Metrics]`
     - [ ] The decline-rather-than-guess branch has its own test, not just the happy path

- [x] **T2.6 The parser derives identity once** `[activity: backend]`

  1. **Prime**: Read `suggestion-parser.py:1971` (`_stem_of`) and the ~20 stem-keyed sites in
     the Force-Atomic reconciliation, including branch (b) added by #165. Read
     `docs/tomo/scripts/suggestion-parser.md` for why that branch exists.
  2. **Test** (RED):
     - two same-named sources produce two independent confirmed items
     - `already_in` / `seen_pending` no longer let one suppress the other
     - a proposed MOC binds to the source that justified it, not to a namesake
     - **the #165 case still passes**, and its fixture now uses a **subfolder** source path —
       the existing regression test does not exercise one `[ref: SDD/Implementation Gotchas]`
     - the daily-log path and the primary/resolve-doc path derive identity through the same
       function; a test asserts they agree for a path-qualified source
  3. **Implement**: one derivation helper; every join site uses it.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] Two namesakes never merge into one bucket `[ref: PRD/AC Feature 2]`
     - [ ] #165 stays fixed, proven against a subfolder path `[ref: SDD/ADR-2]`

- [x] **T2.7 The coverage audit stops collapsing items** `[activity: backend]` `[parallel: true]`

  1. **Prime**: Read `instructions-diff.py:105-111` (its own duplicated `_stem()`), `:281`
     (`derive_expected`) and `:397` (`summarize_actual`). Both sides flatten identically today,
     so a collision produces a false **pass** rather than a caught mismatch.
  2. **Test** (RED):
     - two same-named items produce a count of two on both sides
     - a genuine mismatch is still caught — the change must not blunt the audit
     - existing single-item audits are unchanged
  3. **Implement**: key both sides on `item_key`.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] The audit can no longer report full coverage by merging two items
           `[ref: PRD/AC Feature 2]`

- [ ] **T2.8 Phase Validation — prove the key is carried end to end** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - **The gate that matters**: trace `item_key` from `inbox-triage` to the emitted instruction
    set with real data, not per-stage unit tests. Spec 031 shipped five phases against a field
    nothing populated, and every one of those tasks passed both review gates because each
    correctly implemented its own local contract `[ref: spec 034 README, decision log]`.
    Run the pipeline over a fixture inbox and assert the key is present and correct at every
    artefact boundary: routing plan → per-item result → suggestions doc → wire → parsed
    suggestions.
  - Confirm CON-4: the emitted instruction set is byte-identical to what the same input
    produced before this phase. Nothing Hashi sees may change.
  - Confirm the flat-inbox suggestions document is unchanged.
  - Bump `# version:` on every modified file, including the two runtime LLM files.
