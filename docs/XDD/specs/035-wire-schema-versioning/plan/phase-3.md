---
title: "Phase 3: Version integrity and document identity"
status: completed
version: "1.0"
phase: 3
---

# Phase 3: Version integrity and document identity

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-5, ADR-6]`
- `[ref: SDD/Implementation Examples; Reading the version instead of asserting it]`
- `[ref: PRD/Feature 3]`, `[ref: PRD/Feature 5]`
- `tomo/scripts/{suggestions-render,instruction-render,garden-audit-render}.py`
- `tomo/scripts/garden-audit-configure.py:49` — the precedent for resolving a schema at runtime

**Key Decisions**:
- **ADR-5** — a renderer **reads** its version from its schema. The divergence F3 describes stops
  being possible rather than being caught.
- **ADR-6** — the Hashi-facing contract keeps the canonical `$id`; the producer copy takes a distinct
  one and says which role it plays.

**Dependencies**:
- **None.** This phase shares no files with Phases 1 and 2 — it touches the three renderers and the
  two instruction schemas; those touch `wire_shape.py`, the manifests and the test files. Verified by
  file overlap, not assumed.

---

## Tasks

Removes two ways the mechanism could be defeated from underneath.

- [x] **T3.1 Renderers read their version instead of declaring it** `[parallel: true]` `[activity: backend-api]`

  Today each renderer writes a free string literal. Nothing ties it to the schema it claims to
  conform to, so a bump can land in one and not the other, in either direction.

  1. Prime: read all three emission sites and the runtime-resolution precedent
     `[ref: SDD/Constraints; CON-8]`. Confirm schemas ship to the instance
     (`scripts/install-tomo.sh:1262-1264`) before relying on it.
  2. Test:
     - each renderer emits the version its own schema declares;
     - changing the schema's declared version changes what the renderer emits, with no code edit;
     - a missing schema at runtime raises with the path, matching the existing treatment of that
       failure — it must not fall back to a literal or emit an empty version;
     - the regression assertion (emitted equals declared) passes for all three, and **would fail** if
       a literal were reintroduced.
  3. Implement: a shared helper reading the declared `const`; call it from all three renderers.
  4. Validate: unit tests pass; ruff clean; the three emitted documents are byte-identical to before
     — the values do not change, only their source does. **The regression assertion lives in
     `tests/test_035_wire_shape.py`, not in `test_instruction_render_wire_hygiene.py`** — T2.4
     rewrites that file, and two phases editing one file is how the independence claim would stop
     being true.
  5. Success:
     - [x] Each renderer emits its schema's declared version `[ref: PRD/F3-AC1]` — this box's
       wording predates T3.3's correction of F3-AC1, which under ADR-5 makes a version literal the
       defect rather than a disagreeing literal. Traced against the corrected wording in
       `../close-out.md`
     - [x] Every producer agrees with its schema `[ref: PRD/F3-AC2]`
     - [x] ~~Divergence in **either** direction is caught by the regression guard~~ `[ref: PRD/F3-AC3]`
       — **superseded.** T3.3 corrected F3-AC3: under ADR-5 the reverse direction cannot occur,
       because the code carries no version to bump. Ticked against the corrected criterion (a
       version moved in the schema alone is followed by the renderer with no code edit), not the
       struck wording

- [x] **T3.2 The two instruction documents stop sharing an identity** `[parallel: true]` `[activity: data-architecture]`

  Both declare `$id` `https://miyo.tomo/schemas/instructions.schema.json` with identical title and
  description, while differing structurally — the contract carries a `replace_section` definition the
  producer copy lacks. This is the mechanical cause of the consumer diffing the wrong file and
  reporting drift that did not exist.

  1. Prime: confirm the collision and the structural difference for yourself
     `[ref: SDD/Implementation Gotchas]`.
  2. Test:
     - the two `$id` values differ;
     - each document's title or description states its role — contract, or producer copy;
     - **the existing parity test still passes** — they remain structurally equivalent where they are
       meant to be;
     - nothing in the repo resolves the old `$id` to the producer copy (verify by search, not by
       assumption).
  3. Implement: give the producer copy a distinct `$id`; leave the contract's canonical.
  4. Validate: unit tests pass; ruff clean; full suite green.
  5. Success:
     - [x] The two identities differ `[ref: PRD/F5-AC1]`
     - [x] Each states its role `[ref: PRD/F5-AC2]` — narrowed by owner decision to the producer
       copy; T4.4's re-vendor would have erased an annotation in the mirror, as predicted
     - [x] The parity check still passes `[ref: PRD/F5-AC3]`

- [x] **T3.3 Phase Validation** `[activity: validate]`

  - Full suite green, ruff clean.
  - Confirm the emitted `schema_version` values are unchanged in all three documents — this phase
    changes where the number comes from, never what it is.
  - Confirm a reader given either instruction schema alone can tell which one they hold.
