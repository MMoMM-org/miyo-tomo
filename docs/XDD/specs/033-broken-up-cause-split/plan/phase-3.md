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
- `[ref: SDD/Registration inventory]` — the operative list; thirteen sites: nine must-register, one
  should-register, three deliberately left alone
- `[ref: SDD/Architecture Decisions; ADR-4]` — what registering changes for existing exclusion
  configs
- `[ref: SDD/Quality Requirements; Q6]`

**Key Decisions**:
- This is its own phase on purpose. Spec 032 folded registration into an emission task and had to
  add a whole phase afterwards to recover it; spec 031's `move_asset` is still unregistered in three
  places for the same reason.
- The inventory itself was already corrected once, from six must-register sites to nine. All three
  misses were in `garden-audit-stats.py` — a stats-view surface that duplicates check-name knowledge
  rather than reading it from the checks that own it. The most severe (site 7, `_CHECKS`) is a
  module-scope `assert` that fails at **import**, before any test even runs.
- The **must-not-register** list carries equal weight. Site 11 (`_FIXABLE`) is one line away from
  undoing the entire spec.

**Dependencies**: none. This registers a name Phase 2 emits; the two meet in Phase 5. May run
concurrently with Phases 1–2.

---

## Tasks

- [ ] **T3.1 Register at all nine must-register sites, and fix the should-register drift**
  `[activity: integration]`

  1. **Prime**: read the SDD's Registration inventory in full and **restate the count in the
     implementation note** — nine must-register, one should-register, three to leave. A task that
     does not state its count is the task that misses a site.
  2. **Test** (RED), one assertion per must-register site so a single missing registration cannot
     hide behind a passing sibling:
     - `_TIER["parent_not_moc"] == "advisory"` (`garden-audit.py`)
     - `"parent_not_moc" in ALL_CHECK_NAMES`
     - a document containing a `parent_not_moc` finding validates against the **doc** schema
     - the same finding validates against the **wire** schema
     - `garden-audit-configure.py`'s `_VALID_CHECKS` accepts it, so an exclusion naming it is
       configurable rather than rejected
     - `_CHECK_LABEL["parent_not_moc"]` exists and contains neither "broken" nor "up::"
       `[ref: PRD/F2 criterion 3]`
     - `"parent_not_moc" in gas._CHECKS` (`garden-audit-stats.py:49`) — and importing the module does
       not raise; the module-scope `assert` at `:50` is the site's own enforcement, but the test must
       exercise the import itself, not just the set membership
     - rendering the stats area table with a `parent_not_moc`-bearing doc does not raise `KeyError`
       on `_COL_LABEL` (`:63-66`, indexed at `:119`)
     - an exclusion config naming `parent_not_moc` in its `checks` array validates against
       `garden-audit-exclusions.schema.json`, so the configure wizard can write it
       `[ref: SDD/Registration inventory site 9]`
  3. **Implement**: the nine additions. Also correct the should-register drift: add `parent_not_moc`
     to `garden-audit-stats.py`'s stats-local `_TIER` (`:53-57`) so it agrees with `garden-audit.py`'s
     `_TIER`, even though nothing currently depends on it (`:150` reads the finding's own `tier`
     first). Update the four schema **descriptions** that enumerate checks in prose
     (`doc.schema.json:63` `tier` / `:67` `fixable`, `wire.schema.json:59` `tier` / `:63`
     `fixable`) — they validate nothing, so no test will catch them going stale
     `[ref: SDD/Registration inventory]`.
  4. **Validate**: full suite; all three schemas (doc, wire, exclusions) re-validated against a real
     generated document / config.
  5. **Success**: nine must-register sites registered, the stats-local `_TIER` drift is closed, and
     the four prose descriptions match reality.

- [ ] **T3.2 Prove each registration, each deliberate omission, and that the inventory itself is
  complete** `[activity: validate]`

  1. **Prime**: `[ref: SDD/Quality Requirements; Q6]`. Spec 032 ran exactly this walk and found two
     sites whose "tests" passed with the registration removed. This spec's own inventory was proven
     incomplete once already, at SDD-review time, not by this walk — a walk over the table can only
     prove the sites *named in it* are covered, never that no others exist. T3.2 must not repeat that
     gap: it needs a check that does not depend on the table being right.
  2. **Test**:
     - **For each of the nine must-register sites**: remove that registration, run the named tests,
       confirm **red**, restore. A green run means the test does not cover the site — fix the test,
       not the walk. A collection **error** proves nothing about coverage and must be redone with a
       line-precise removal `[ref: SDD/Implementation Gotchas 3]`.
     - **For each of the three must-not-register omissions**: *add* the name to that site and confirm
       a test goes **red**. Adding `parent_not_moc` to `_FIXABLE` must fail loudly — that is CON-2's
       only automated defence.
     - **Completeness, independent of the table**: pick an existing check name that is already
       registered everywhere `parent_not_moc` now needs to be (e.g. `broken_up`), and
       `grep -rn '"broken_up"' tomo/scripts/ tomo/schemas/ tests/`. Classify **every** hit as either
       (a) a site where `parent_not_moc` now also appears, or (b) a site on the must-not-register
       list with its reason. A hit that is neither is a site the table missed — the same class of gap
       that hid `garden-audit-stats.py` from the first draft. This step is what makes the proof
       independent of the inventory instead of circular with it.
  3. **Implement**: a scratch walker script; restores in a `finally` block. The completeness grep can
     be a plain shell command captured in the implementation note — it does not need to be a
     persisted test.
  4. **Validate**: 9 red on removal, 3 red on addition, every `broken_up` grep hit classified with no
     leftover.
  5. **Success**: every site has a test that actually fails without it, every deliberate omission has
     one that fails **with** it, and the grep shows no fourteenth site exists outside the table. The
     grep is the novel part; 032, and this spec's own first SDD draft, only ever walked a table.

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
  - The T3.2 walk (9 red on removal, 3 red on addition, the `broken_up` completeness grep fully
    classified) re-run clean from a fresh checkout of the phase.
