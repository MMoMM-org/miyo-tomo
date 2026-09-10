---
title: "Phase 2: Detect — diff, classify, and the gate"
status: pending
version: "1.0"
phase: 2
---

# Phase 2: Detect — diff, classify, and the gate

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Complex Logic]` — the gate algorithm
- `[ref: SDD/Implementation Examples]` — both traced walkthroughs
- `[ref: SDD/Architecture Decisions; ADR-3, ADR-4]`
- `[ref: PRD/Feature 1]`, `[ref: PRD/Feature 2]`, `[ref: PRD/Feature 7]`
- `tests/test_instruction_render_wire_hygiene.py` — the vacuous check being replaced

**Key Decisions**:
- **ADR-4** — classification is **read from the manifest**, never kept as a parallel rule table.
- **ADR-3** — a stale manifest fails. Regeneration is always explicit; never automatic.
- The classification has two independent triggers: a property added to a **closed** node, and a
  **type change** anywhere. The second does not depend on openness.

**Dependencies**:
- **Phase 1 complete.** Both functions read manifests.

**This is where an unannounced shape change stops being possible.**

---

## Tasks

Turns the recorded shape into a gate.

- [ ] **T2.1 `diff_shapes` names what moved** `[activity: domain-modeling]`

  1. Prime: read the two traced walkthroughs — the 034 drift and the live garden-audit drift
     `[ref: SDD/Implementation Examples]`.
  2. Test: an added property is reported with its pointer and name; a removed property likewise; a
     `required` change is reported distinctly from a property change; an openness change is its own
     kind; a **type change** is its own kind; a node added or removed wholesale is reported once, not
     as N property changes; identical manifests produce an empty list.
  3. Implement: `diff_shapes(recorded, observed) -> list[ShapeChange]` in `wire_shape.py`. Pure.
  4. Validate: unit tests pass; ruff clean.
  5. Success:
     - [ ] A change is named by document, pointer and property `[ref: PRD/F1-AC1]`
     - [ ] `required` and `additionalProperties` changes are detected `[ref: PRD/F1-AC2]`
     - [ ] An unchanged pair produces nothing `[ref: PRD/F1-AC5]`

- [ ] **T2.2 `classify` decides whether the consumer is obliged** `[activity: domain-modeling]`

  The rule was measured against the consumer's own validator across eight change classes. Encode
  what was measured, not what versioning theory suggests.

  1. Prime: read the eight-class matrix `[ref: PRD/Supporting Research]` and ADR-4.
  2. Test — one per measured class:
     - property added to a **closed** node → affecting;
     - property added to an **open** node → **not** affecting *(this is the live garden-audit case;
       getting it wrong makes the detector cry wolf on the one drift that is fine)*;
     - **required** field removed → affecting;
     - **optional** field removed → not affecting;
     - **enum value added** → affecting *(counter-intuitive; a consumer validating the old set
       rejects the new value)*;
     - type changed → affecting, **regardless of the node's openness**;
     - a declared-optional field starting to be emitted → not affecting;
     - prose changed → not affecting (and produces no change at all, per T1.1).
  3. Implement: `classify(change, observed) -> bool`, reading `closed` from the manifest.
  4. Validate: unit tests pass; ruff clean.
  5. Success:
     - [ ] Closed-node addition is affecting `[ref: PRD/F2-AC1]`
     - [ ] Open-node addition is not `[ref: PRD/F2-AC2]`
     - [ ] Enum addition is affecting `[ref: PRD/F2-AC3]`
     - [ ] Required removal is affecting; optional removal is not `[ref: PRD/F2-AC4]`

- [ ] **T2.3 The gate, and a message that says what to do** `[activity: backend-api]`

  1. Prime: read the gate algorithm `[ref: SDD/Complex Logic]` and the error-handling table
     `[ref: SDD/Error Handling]`.
  2. Test:
     - affecting change **and** version unmoved → **fail**, and the message names the pointer, the
       property, and both expected actions (move the version, hand over);
     - affecting change **with** the version moved → pass;
     - non-affecting change → fail, and the message asks **only** for manifest regeneration and does
       **not** demand a version move;
     - no change → pass silently;
     - unparseable schema → fail, never treated as "no change";
     - two wires changed in one edit → both reported, each against its own counter.
  3. Implement: the check in `tests/test_035_wire_shape.py`, iterating the three published wires.
  4. Validate: unit tests pass; ruff clean.
  5. Success:
     - [ ] Affecting + unmoved version fails; moved passes `[ref: PRD/F2-AC5]`
     - [ ] The failure names the expected next steps `[ref: PRD/F7-AC1]`
     - [ ] A non-affecting change does not demand a version move `[ref: PRD/F7-AC2]`

- [ ] **T2.4 Replace the vacuous comparison in the existing wire-hygiene test** `[activity: backend-api]`

  The existing upstream check builds its surface from `$defs` entries carrying an `action` property
  and iterates their intersection. On a `$defs`-free schema that is zero iterations — it passes while
  the schema is drifted.

  1. Prime: read the current comparison and confirm the vacuity for yourself before changing it —
     the claim is measured, but an implementer who has not seen it will not trust the replacement.
  2. Test: the replacement compares structurally to full depth; a root-level property difference is
     now detected (it is not today); **every existing test in the file still passes**; the network
     test still skips offline.
  3. Implement: swap the comparison surface for `describe_shape` + `diff_shapes`. Leave
     `SNAPSHOT_AHEAD_OF_UPSTREAM` in place — ADR-7 makes the vendored copies a report, so it needs no
     extension.
  4. Validate: **full suite green** — the gate for this task is the pre-existing tests.
  5. Success:
     - [ ] Root-level differences are detected `[ref: PRD/F1-AC1]`
     - [ ] A `$defs`-free schema is compared non-vacuously `[ref: PRD/F1-AC3]`
     - [ ] Existing wire-hygiene and parity tests unchanged `[ref: SDD/Implementation Boundaries]`

- [ ] **T2.5 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean.
  - Prove the counterfactual: add `item_key` to a copy of the pre-034 suggestions wire and confirm
    the gate **fails**. That is the drift that cost two specs; the mechanism is only worth having if
    it catches it.
  - Prove the inverse: the live garden-audit `detail` additions classify as **not** affecting, so the
    detector does not demand a version move for a change that obliges nobody. **Both proofs need a
    scratch manifest** built from the pre-change schema — the committed manifests already record the
    current state, so neither drift is reproducible against them. That is the manifest working as
    designed, not a gap.
