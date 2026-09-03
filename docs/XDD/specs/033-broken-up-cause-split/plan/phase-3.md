---
title: "Phase 3: Register the new check"
status: pending
version: "1.0"
phase: 3
---

# Phase 3: Register the new check

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Registration inventory]` — the operative list; nine sites, six to register and three to
  deliberately leave alone
- `[ref: SDD/Architecture Decisions; ADR-4]` — what registering changes for existing exclusion
  configs
- `[ref: SDD/Quality Requirements; Q6]`

**Key Decisions**:
- This is its own phase on purpose. Spec 032 folded registration into an emission task and had to
  add a whole phase afterwards to recover it; spec 031's `move_asset` is still unregistered in three
  places for the same reason.
- The **must-not-register** list carries equal weight. Site 7 (`_FIXABLE`) is one line away from
  undoing the entire spec.

**Dependencies**: none. This registers a name Phase 2 emits; the two meet in Phase 5. May run
concurrently with Phases 1–2.

---

## Tasks

- [ ] **T3.1 Register at all six sites** `[activity: integration]`

  1. **Prime**: read the SDD's Registration inventory in full and **restate the count in the
     implementation note** — six to add, three to leave. A task that does not state its count is the
     task that misses a site.
  2. **Test** (RED), one assertion per site so a single missing registration cannot hide behind a
     passing sibling:
     - `_TIER["parent_not_moc"] == "advisory"`
     - `"parent_not_moc" in ALL_CHECK_NAMES`
     - a document containing a `parent_not_moc` finding validates against the **doc** schema
     - the same finding validates against the **wire** schema
     - `garden-audit-configure.py`'s `_VALID_CHECKS` accepts it, so an exclusion naming it is
       configurable rather than rejected
     - `_CHECK_LABEL["parent_not_moc"]` exists and contains neither "broken" nor "up::"
       `[ref: PRD/F2 criterion 3]`
  3. **Implement**: the six additions. Update the two schema **descriptions** that enumerate checks
     in prose (`doc.schema.json:63` `tier`, `:67` `fixable`) — they validate nothing, so no test will
     catch them going stale `[ref: SDD/Registration inventory]`.
  4. **Validate**: full suite; both schemas re-validated against a real generated document.
  5. **Success**: six sites registered, and the two prose descriptions match reality.

- [ ] **T3.2 Prove each registration and each deliberate omission** `[activity: validate]`

  1. **Prime**: `[ref: SDD/Quality Requirements; Q6]`. Spec 032 ran exactly this walk and found two
     sites whose "tests" passed with the registration removed.
  2. **Test**:
     - **For each of the six**: remove that registration, run the named tests, confirm **red**,
       restore. A green run means the test does not cover the site — fix the test, not the walk. A
       collection **error** proves nothing about coverage and must be redone with a line-precise
       removal `[ref: SDD/Implementation Gotchas 3]`.
     - **For each of the three omissions**: *add* the name to that site and confirm a test goes
       **red**. Adding `parent_not_moc` to `_FIXABLE` must fail loudly — that is CON-2's only
       automated defence.
  3. **Implement**: a scratch walker script; restores in a `finally` block.
  4. **Validate**: 6 red on removal, 3 red on addition, 9 for 9.
  5. **Success**: every site has a test that actually fails without it — and every deliberate
     omission has one that fails **with** it. The second half is the novel part; 032 only ever
     tested the first.

- [ ] **T3.3 Exclusion behaviour change is documented, not discovered** `[activity: documentation]`

  1. **Prime**: `[ref: SDD/ADR-4]`. Two real consequences, opposite in sign.
  2. **Test**:
     - a `checks: all` exclusion covers `parent_not_moc` without config changes
     - an exclusion listing `broken_up` explicitly does **not** cover it — assert the reappearance
       rather than leaving it to be reported as a bug
  3. **Implement**: record both in the spec README decisions log and in `docs/XDD/backlog.md` if a
     release note is owed.
  4. **Validate**: run the real exclusion loader against the live config and report which of the two
     applies to this vault.
  5. **Success**: the first user to see a "reappeared" finding finds a written answer.

- [ ] **T3.4 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - The 9-for-9 walk from T3.2 re-run clean from a fresh checkout of the phase.
