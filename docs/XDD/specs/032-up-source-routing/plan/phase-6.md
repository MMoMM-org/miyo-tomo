---
title: "Phase 6: Integration, regression and documentation"
status: in_progress
version: "1.0"
phase: 6
---

# Phase 6: Integration, regression and documentation

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Quality Requirements]` — the table is this phase's checklist
- `[ref: SDD/Deployment View]` — the cache-refresh ordering note
- `[ref: PRD/Success Metrics]`
- `[ref: CON-7]` body-resident output byte-identical; `[ref: CON-3]` zero added Kado calls
- Live population — **CORRECTED 2026-09-02**, the original figure came from `discovery-cache.yaml`
  (64 entries) while `garden-audit.py:550` actually loads `moc-structure-cache.yaml`. Measured
  there: **346 entries, 22 property-resident, 29 broken — and one is BOTH broken and
  property-resident**: `Atlas/202 Notes/Aristotle and Metaphor - Seeing the similarity between
  things..md` → `Philosophy MOC (kit)`. So a live test does **not** need a deliberately broken
  note: a real one exists. Prefer it — a naturally occurring case proves more than a synthetic
  one, and it avoids editing the user's vault to manufacture a fixture.

**Key Decisions**:
- The headline metric is behavioural, not self-reported: **a property-resident fix, once approved, changes the note.** Today it does not.
- Batch everything needing a live run into **one** cycle `[ref: memory: minimize live-test cycles]`.
- Cache-refresh ordering matters: `/explore-vault` must run before the audit, or every property finding is correctly withheld and the live test proves nothing.

**Dependencies**: Phases 1–5.

---

## Tasks

Proves the chain and leaves the repo and the sibling repo in a consistent state.

- [ ] **T6.1 End-to-end routing test** `[activity: integration-testing]`

  1. **Prime**: Drive the public entry point, not the helpers `[ref: memory: mock at orchestrator, not helper]`.
  2. **Test** (RED) — one scenario, mixed by construction:
     - a fixture vault with one inline-declared and one property-declared note, both with broken parents
     - after approval of both, the instruction set contains **one** body action and **one** `edit_frontmatter`
     - the set validates against `instructions.schema.json` `[ref: PRD/AC-F2 family]`
     - `instructions-diff` reconciles with no mismatch `[ref: PRD/AC-F5.1]`
     - `instructions-dryrun` exits 0 `[ref: PRD/AC-F5.4]`
     - the `edit_frontmatter` carries `expected` equal to the fixture's observed value, order intact
  3. **Implement**: fixture and test. No production code should be needed; if it is, an earlier phase was incomplete.
  4. **Validate**: passes without touching a live vault.
  5. **Success**: the two declaration styles produce two different, correct actions from one uniform approval flow

- [ ] **T6.2 Regression: body-resident unchanged** `[activity: integration-testing]` `[parallel: true]`

  1. **Prime**: `[ref: CON-7]`. This is a routing addition, not a rewrite.
  2. **Test** (RED):
     - an all-inline fixture produces an instruction set **byte-identical** to the pre-change golden, except where the new kind shifts action IDs
     - the report for such a run is byte-identical — no warning line, no split line changes to existing wording
     - `remove_up_link` and `add_relationship` emission is untouched
  3. **Implement**: regenerate goldens **only** where an ID shift explains the diff. Any other difference is a defect.
  4. **Validate**: full suite green.
  5. **Success**: no behavioural change for the 18 inline-declared notes `[ref: CON-7]`

- [ ] **T6.3 Cost verification** `[activity: integration-testing]` `[parallel: true]`

  1. **Prime**: `[ref: CON-3]`. The design's central claim is that this costs nothing at audit time.
  2. **Test** (RED):
     - the audit issues the **same** number of Kado calls before and after this change
     - the count does not vary with the number of property-resident findings
     - the `broken_up` check still triggers no `graph_audit` `[ref: CON-5]`
  3. **Implement**: assertions only.
  4. **Validate**: passes.
  5. **Success**: zero added calls, enforced by test rather than by argument

- [ ] **T6.4 Documentation and sync** `[activity: documentation]`

  1. **Prime**: the WHY-layer rule in `CLAUDE.md`; `[ref: SDD/Deployment View]`.
  2. **Implement**:
     - `docs/instructions-json.md` — `edit_frontmatter` as an **emitted** kind: the shape, the `expected` guard, list-order significance, the `expected`/`expected_absent` exclusivity, and the comment-loss cost
     - `docs/tomo/scripts/garden-audit-parser.md` — WHY the routing branch exists and why the fallback is forbidden
     - `docs/tomo/scripts/lib/up_parse.md` (or its existing counterpart) — why `raw_value` is `None` for inline
     - `docs/XDD/backlog.md` — record that the `remove_up_link` guard was deliberately **not** requested of Hashi, and that this spec is the alternative
     - verify every touched `tomo/scripts/` file has a bumped `# version:` — grep, do not assume `[ref: CON-8]`
  3. **Validate**: `scripts/update-tomo.sh` dry run lists every intended file as changed; an unchanged file means a missed bump.
  4. **Success**: the instance would receive every change

- [ ] **T6.5 Live validation** `[activity: validate]`

  1. **Prime**: one batched cycle. Order matters: `update-tomo` → `/explore-vault` (so the cache gains `up_value`) → `/garden-audit`.
  2. **Test**: against the real vault, with one property-resident note deliberately given a broken parent:
     - the report marks it as a property fix and shows the comment-loss warning
     - the split line reports at least one property-resident finding
     - after approval and apply, **the note's property is actually changed** — the headline metric `[ref: PRD/Success Metrics]`
     - an inline-declared broken note in the same run is fixed as before
     - confirm on a pre-refresh cache that property findings are **withheld with the remedy**, not mis-routed `[ref: PRD/AC-F6.1]`
  3. **Validate**: record the outcome and the observed Kado call count in `docs/evolution/inbox-cost-log.md`.
  4. **Success**: a property-resident fix, once approved, changes the note `[ref: PRD/Success Metrics]`

- [ ] **T6.6 Notify Hashi** `[activity: documentation]`

  1. **Prime**: Hashi left `remove_up_link` unguarded on our recommendation and recorded the decision in their spec-002 (PR #128), explicitly awaiting this routing. We promised to tell them when it shipped.
  2. **Implement**: a handoff in `_outbox/for-hashi/` stating that routing has shipped, that the mis-routed case is now unreachable rather than merely rare, and that the guard remains correctly unbuilt.
  3. **Validate**: the handoff names the version and the behaviour, not just the fact.
  4. **Success**: the open cross-repo loop is closed on our side `[ref: spec README decisions log]`

- [ ] **T6.7 Phase Validation** `[activity: validate]`

  - Full suite green; `ruff` clean. Walk the SDD Quality Requirements table and confirm each row has a passing test. Walk the PRD acceptance criteria and confirm each maps to a green test — including the vacuously-satisfied `expected_absent` criterion, which must be covered by an assertion that it is never emitted. Update the spec README to `Implemented` via `xdd-meta finalize`.
