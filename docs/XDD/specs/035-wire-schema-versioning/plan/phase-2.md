---
title: "Phase 2: Detect — diff, classify, and the gate"
status: in_progress
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
- `tests/test_instruction_render_wire_hygiene.py` — the check being replaced. It is **vacuous on the suggestions wire** (zero `$defs` → zero iterations); on the instructions wire it does iterate 18 shared defs, but compares no root-level fields

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
     a `required` change is reported distinctly from a property change **and distinctly by
     direction** — `required_added` when a field joins the list, `required_removed` when one
     leaves; an openness change is its own
     kind; a **type change** is its own kind; a node added or removed wholesale is reported once, not
     as N property changes; identical manifests produce an empty list.

     **Enum values are diffed too** `[ref: SDD/Application Data Models; ShapeChange]`. Added
     2026-09-10 with ADR-2's extension, and not optional: Phase 1 records `values` per property, but
     if nothing diffs them then `classify` never sees an enum change and **PRD F2-AC3 remains
     unreachable** — the criterion would be satisfiable only by hand-building a `ShapeChange`, which
     is the vacuous-pass pattern this spec exists to eliminate. Test: a value added to a property's
     enum is reported as `added_enum_value` with its pointer, the property name and the value; a
     value removed is reported as `removed_enum_value`; a property gaining an enum where it had none
     is reported; a `const` widened to an `enum` containing it reports the added values and nothing
     else, because Phase 1 records `const: X` as `[X]`.
  3. Implement: `diff_shapes(recorded, observed) -> list[ShapeChange]` in `wire_shape.py`. Pure.
  4. Validate: unit tests pass; ruff clean.
  5. Success:
     - [ ] A change is named by pointer and property — **the document name is not in scope at
       this layer**. `diff_shapes` receives two node maps and never learns which file they came
       from, so F1-AC1's "names the document" half is discharged by T2.3, which iterates the
       wires and knows the filename. Do not add a `document` parameter here to satisfy a
       criterion that belongs to the caller `[ref: PRD/F1-AC1 — pointer and property half]`
     - [ ] `required` and `additionalProperties` changes are detected `[ref: PRD/F1-AC2]`
     - [ ] An unchanged pair produces nothing `[ref: PRD/F1-AC5]`
     - [ ] Enum value additions and removals are reported as distinct kinds `[ref: SDD/Application Data Models; ShapeChange]`

- [ ] **T2.2 `classify` decides whether the consumer is obliged** `[activity: domain-modeling]`

  The rule was measured against the consumer's own validator across eight change classes. Encode
  what was measured, not what versioning theory suggests.

  1. Prime: read the classification rules `[ref: PRD/Detailed Feature Specifications; Business Rules]`
     — seven rules covering the measured change classes — and ADR-4. (`PRD/Supporting Research`
     mentions the matrix but does not tabulate it.)
  2. Test — one per measured class:
     - property added to a **closed** node → affecting;
     - property added to an **open** node → **not** affecting *(this is the live garden-audit case;
       getting it wrong makes the detector cry wolf on the one drift that is fine)*;
     - **required** field removed → affecting;
     - **optional** field removed → not affecting;

       **Write these two through `diff_shapes`, never by hand-building a `ShapeChange`.**
       Removing a required property yields TWO changes (`removed_property` **and**
       `required_removed`); removing an optional one yields a single `removed_property`. So
       the distinction lives in the change *set*, and the gate's `any(classify(c) ...)` is
       what separates them — a lone `removed_property` classifies identically in both cases
       and always will. An implementer who hand-builds one change, sees the 'wrong' answer
       and 'fixes' `classify` by giving it the recorded manifest has broken the SDD's
       signature to solve a problem that does not exist. Driving every test through
       `diff_shapes` also removes the hand-built-fixture vacuity this spec keeps finding;
     - **enum value added** → affecting *(counter-intuitive; a consumer validating the old set
       rejects the new value)*;
     - **enum value removed** → **not** affecting — the mirror of the above, and the reason the two
       are separate kinds. We then emit a subset of what their vendored set already accepts, so
       their validator does not reject. Note the limit honestly: their *handling* code may still
       switch on a value that stopped arriving. That is a prose obligation for the handover table,
       not something the validator-measured rule can see — the same boundary ADR-2 draws for
       descriptions;
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
     - [ ] The failure names the **document**, the location and the property `[ref: PRD/F1-AC1]`
           — the half T2.1 structurally cannot deliver
     - [ ] The failure names the expected next steps `[ref: PRD/F7-AC1]`
     - [ ] A non-affecting change does not demand a version move `[ref: PRD/F7-AC2]`

- [ ] **T2.4 Replace the vacuous comparison in the existing wire-hygiene test** `[activity: backend-api]`

  The existing upstream check builds its surface from `$defs` entries carrying an `action` property
  and iterates their intersection. On the instructions wire that is 18 real comparisons; on a
  `$defs`-free schema it is zero, so the check passes while the schema is drifted. It also compares
  no root-level fields on either document — root parity today is coincidence.

  1. Prime: read the current comparison and confirm the vacuity for yourself before changing it —
     the claim is measured, but an implementer who has not seen it will not trust the replacement.
  2. Test: the replacement compares structurally to full depth; a root-level property difference is
     now detected (it is not today); **every existing test in the file still passes**; the network
     test still skips offline.
  3. Implement: swap the comparison surface for `describe_shape` + `diff_shapes`.

     **The exemption registry cannot survive a full-depth walk unchanged.** Corrected 2026-09-10 by
     validation: `SNAPSHOT_AHEAD_OF_UPSTREAM`'s three entries also appear in the snapshot's root
     `properties/actions/items/oneOf`, and a full-depth walk reaches those pointers. Keyed by
     def-name, the registry cannot filter them — so the pre-existing tests this task names as its
     gate **would fail**. Two ways out, and the task must pick one explicitly rather than discover
     this at implementation:
     a. **Make this comparison a report too**, consistent with ADR-7 — the upstream check then stops
        being a gate and the exemption question dissolves. Preferred: it is the same reasoning ADR-7
        already applied to the vendored copies, and applying it in one place and not the other is
        the inconsistency that would need explaining later.
     b. Key the exemption by JSON pointer prefix instead of def-name, so an ahead-action's `oneOf`
        branch is excluded alongside its `$def`. Keeps the gate, costs a registry redesign — the
        redesign 036's validation already flagged as pending.
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
