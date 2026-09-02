---
title: "Phase 5: Report surface"
status: in_progress
version: "1.0"
phase: 5
---

# Phase 5: Report surface

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Cross-Cutting Concepts; User Interface & UX]` — the three rendered lines, verbatim
- `[ref: SDD/Architecture Decisions; ADR-4]`
- `[ref: PRD/Feature 4]`, `[ref: PRD/Feature 6]`, `[ref: PRD/Should-have: routing split]`
- Source to read: `garden-audit-render.py` — the `broken_up` finding block and the report preamble

**Key Decisions**:
- The comment-loss warning belongs at **approval time**. A post-hoc note is too late by construction: the comments are already gone.
- **ADR-4** — the split line was accepted into scope; it is the observability whose absence let this defect class stay invisible.
- A withheld finding must render its **remedy**, not just its reason. "Cannot fix" without "run `/explore-vault`" is a dead end.

**Dependencies**: Phase 2 (the finding must carry the fields). Independent of Phases 3 and 4.

---

## Tasks

Makes the routing visible to the person approving it.

- [ ] **T5.1 Property-edit disclosure** `[activity: frontend-ui]`

  > **Verbatim string — DO NOT PARAPHRASE** (`solution.md` UI & UX section):
  > ```markdown
  > - **Fix target:** note property `up` — editing YAML properties.
  >   ⚠️ Comments inside this note's property block will not survive the edit.
  > ```
  > The property name is **derived** from the action, not hardcoded to `up` (ADR-6). Assert the
  > wording exactly, including the ⚠️ character.
  > **Prerequisite the task text omits:** `tests/test_garden_audit_render.py`'s
  > `_make_broken_up_finding()` fixture has no `up_source`/`up_value` parameters, so nothing can
  > currently distinguish a property-resident finding from a body-resident one. Extend the
  > fixture first, or no test here can go RED.

  1. **Prime**: Read the UX section `[ref: SDD/Cross-Cutting Concepts]`. The warning is not decoration — a successful property edit drops YAML comments, and that is irreversible.
  2. **Test** (RED):
     - a property-resident finding renders a line naming the property and stating that the fix edits note properties `[ref: PRD/AC-F4.1]`
     - it renders the comment-loss warning `[ref: PRD/AC-F4.2]`
     - a body-resident finding renders **neither**, and its wording is byte-identical to today `[ref: PRD/AC-F4.3, CON-7]`
     - the property name shown is the derived one, not a hardcoded `up` `[ref: ADR-6]`
  3. **Implement**: the conditional lines in the finding renderer.
  4. **Validate**: render tests pass; `ruff` clean; `# version:` bumped.
  5. **Success**: the user learns the cost **before** approving `[ref: PRD/Feature 4]`

- [ ] **T5.2 Unroutable findings and their remedy** `[activity: frontend-ui]`

  > **Verbatim string — DO NOT PARAPHRASE** (`solution.md` UI & UX section):
  > ```markdown
  > - **Not fixable this run:** the discovery cache predates property routing.
  >   Run `/explore-vault` to refresh it, then re-run the audit.
  > ```
  > The remedy names a concrete command. A vague "refresh the cache" is a dead end and fails
  > PRD Feature 6, which requires the user be told **how** to refresh.
  > **Render shape (SDD, not open to reinterpretation):** the reason + remedy render **per
  > finding**; stderr also carries **one line per finding**, with the existing `[garden-audit]`
  > prefix, naming the note and the reason. The summary line is **in addition**, once per run.
  > **Measured first-run reality:** the live cache holds 346 entries, **0** carry `up_value`, and
  > 29 findings are `broken_up`. So on the first run after this ships, **every** finding is
  > withheld as `stale-cache` until `/explore-vault` runs. This is the default first experience,
  > not a rare degraded case — the summary line must make the collective remedy obvious without
  > the reader having to infer it from 29 identical blocks.

  1. **Prime**: `[ref: PRD/Feature 6]`. A withheld finding is a specified outcome; it must read as one, not as an error.
  2. **Test** (RED):
     - a stale-cache finding renders its reason **and** names `/explore-vault` as the remedy `[ref: PRD/AC-F6.2]`
     - it renders no fix checkbox — there is nothing to approve `[ref: PRD/AC-F6.1]`
     - a run with no unroutable findings renders no such line and no empty section
     - a summary line names how many findings were withheld and why `[ref: PRD/Should-have: unroutable summary]`
     - the same information reaches stderr with the existing `[garden-audit]` prefix `[ref: SDD/System-Wide Patterns]`
  3. **Implement**: the withheld-finding rendering plus the summary.
  4. **Validate**: render tests pass.
  5. **Success**: a withheld finding is actionable, not merely reported `[ref: ADR-5]`

- [ ] **T5.3 Routing split line** `[activity: frontend-ui]` `[parallel: true]`

  1. **Prime**: `[ref: SDD/ADR-4]`. One line, once per run.
  2. **Test** (RED):
     - a run with both kinds renders the split with correct counts `[ref: PRD/Should-have]`
     - a run with only body-resident findings still renders it — a zero is informative here, since "no property findings" and "routing broken" must be distinguishable `[ref: PRD/Tracking Requirements]`
     - a run with **no** broken-parent findings renders no line at all
  3. **Implement**: the summary line in the report preamble.
  4. **Validate**: render tests pass.
  5. **Success**: the population is visible to the user, not only to an audit `[ref: ADR-4]`

- [ ] **T5.4 Phase Validation** `[activity: validate]`

  - Full suite green. Render a fixture report containing one body-resident, one property-resident and one withheld finding, and read it as a user would: is it obvious which fix does what, and what to do about the withheld one? `ruff` clean.
