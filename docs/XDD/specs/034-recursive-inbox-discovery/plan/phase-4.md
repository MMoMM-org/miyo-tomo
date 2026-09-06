---
title: "Phase 4: Force Atomic in subfolders"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: Force Atomic in subfolders

## Phase Context

**GATE**: read these before starting.

**Specification References**:
- `[ref: PRD/Feature 4]`
- `[ref: SDD/Implementation Gotchas]` — the STRICT block and why it exists
- `docs/tomo/scripts/suggestion-parser.md` — #165's fix and the invariant it depends on

**Key Decisions**:
- The dispatcher must carry the item's real path instead of reconstructing it from a filename.
- The STRICT block guarding against using `source_path` stays. It is right — `source_path`
  there is the review document, not the note. The fix is to supply the real path, not to relax
  the guard.

**Dependencies**: Phase 2 complete. Independent of Phase 3 — different files, so the two can
run in parallel.

**Why this is separate from the collision work**: `<inbox_path>/<stem>.md` is wrong for **any**
subfolder note, with or without a name clash. It is a second, independent blocker, and the
issue that started this spec did not mention it.

---

## Tasks

- [ ] **T4.1 The dispatcher uses the item's real path** `[activity: prompt-engineering]`

  **Inherited from T2.1 — this task must correct it.** T2.1 populated
  `force_atomic_items[*].item_key` with the **review document's** path, because that is the only
  path available at `_extract_fan_items` (`inbox-triage.py:589`) and
  `_extract_fan_items_from_wire` (`:693`) — the FAN checkbox carries a bare `stem` via
  `Source: [[stem]]`, never a full path. The schema requires the field, so it could not be left
  out. Two consequences you must close:

  - The value violates ADR-1 in spirit: `item_key` is meant to be *the item's* vault-relative
    path, and it currently holds the path of the document the checkbox was ticked in.
  - Two FAN items in one suggestions document therefore share one `item_key`. Nothing joins on it
    today (`force_atomic_items` is consumed only by `force-atomic-handling/SKILL.md`, which
    iterates and dispatches), so no merge bug is live — but the moment anything does join on it,
    two distinct items merge silently.

  Carrying the item's real path through the routing plan is already this task's job. When you do,
  set `item_key` to that path and add a test asserting two FAN items in one document get
  **distinct** `item_key` values.

  1. **Prime**: Read `tomo/dot_claude/skills/force-atomic-handling/SKILL.md:55-70`. The STRICT
     block reads: *path MUST be `<inbox_path>/<stem>.md` (the ORIGINAL inbox note)*, with the
     `Why:` that the analyst reads the note at `path` via Kado and a wrong path makes it
     classify the review document instead. For `100 Inbox/Places/Dresden.md` the reconstruction
     yields `100 Inbox/Dresden.md`, which does not exist. Read `[ref: SDD/CON-5]` — imperatives
     only in this file.
  2. **Test** (RED):
     - a suppressed suggestion for a subfolder note dispatches with that note's real path
       `[ref: PRD/AC Feature 4]`
     - a root-level note dispatches exactly as before
     - the STRICT block still forbids using the review document's own path — the guard survives
       the change
  3. **Implement**: carry the item's path through the routing plan into the dispatch, and
     rewrite the instruction to use it. Update the STRICT `Why:` so it states the real failure
     mode rather than the old workaround. Write the `docs/tomo/` counterpart first
     `[ref: SDD/CON-5]`.
  4. **Validate**: tests pass; the runtime file is imperative-only.
  5. **Success**:
     - [ ] Force Atomic on a subfolder note builds from that note `[ref: PRD/AC Feature 4]`
     - [ ] The reconstruction is gone, not merely widened

- [x] **T4.2 #165's invariant holds under the new identity** `[activity: backend]`

  1. **Prime**: Read the Force-Atomic reconciliation in `suggestion-parser.py` and
     `tests/test_165_suppressed_force_atomic_resolve.py`. The invariant: the daily-log path and
     the primary/resolve-doc path must derive identity through the same function. If they
     diverge, an approved proposal parses cleanly into a lookup nothing reads — exactly the
     livelock #165 fixed, but this time invisible to its regression test, whose fixtures use a
     root-level path only.
  2. **Test** (RED):
     - extend the #165 fixtures to a **subfolder** source path; the promotion still works
     - a resolve-doc proposal for a subfolder note is consumed, not re-parked
     - two suppressed same-named notes, both force-atomic'd, promote independently
     - a test asserts both derivation paths agree for a path-qualified source
  3. **Implement**: only what the tests require — if T2.6 was done correctly this may be
     test-only. Do not assume that; run the tests first and let them say.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] The livelock cannot return through a re-keying seam `[ref: SDD/Implementation Gotchas]`

- [ ] **T4.3 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Mutation-prove T4.2: make the two derivation paths disagree, confirm the new subfolder test
    fails, restore. Verify the mutation actually landed before trusting a red result.
  - Bump `# version:` on every modified file.
