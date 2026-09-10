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

- [x] **T2.1 `diff_shapes` names what moved** `[activity: domain-modeling]`

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
     - [x] A change is named by pointer and property — **the document name is not in scope at
       this layer**. `diff_shapes` receives two node maps and never learns which file they came
       from, so F1-AC1's "names the document" half is discharged by T2.3, which iterates the
       wires and knows the filename. Do not add a `document` parameter here to satisfy a
       criterion that belongs to the caller `[ref: PRD/F1-AC1 — pointer and property half]`
     - [x] `required` and `additionalProperties` changes are detected `[ref: PRD/F1-AC2]`
     - [x] An unchanged pair produces nothing `[ref: PRD/F1-AC5]`
     - [x] Enum value additions and removals are reported as distinct kinds `[ref: SDD/Application Data Models; ShapeChange]`

- [x] **T2.2 `classify` decides whether the consumer is obliged** `[activity: domain-modeling]`

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
     - prose changed → not affecting (and produces no change at all, per T1.1);
     - **a node that becomes closed → affecting; one that becomes open → not** `[ref: PRD/Business
       Rules; Rule 8]`. Direction is derivable here without splitting the kind, unlike `required` and
       `enum`: openness is a boolean, so if it changed and `observed` says closed, it was open.
       Read it from `observed`, never infer it from the `detail` string;
     - **a node added or removed wholesale → affecting** `[ref: PRD/Business Rules; Rule 9]`. Test
       the case that motivates it: a new `oneOf` branch, which emits a node addition **and nothing
       else** because its parent declares no `properties` and is not a recorded node. That is the
       shape of a new action kind on the instructions wire.

     - **a field joining `required` → NOT affecting** `[ref: SDD/Application Data Models]`. We now
       always emit something their older copy has declared and accepts. Stated because it is easy to
       get backwards: this wire runs producer → consumer, so the consumer never *sends* anything
       that could be missing a newly-required field. They only receive what we emit and validate it.
       A review has already reasoned the wrong way round on this exact question — derive direction
       from who emits and who validates, not from what "required" sounds like;
     - **a declared-optional field starting to be emitted** is **not classifiable here, by
       construction.** It is an emission-pattern change, not a schema change, so `describe_shape`
       sees nothing move, `diff_shapes` returns an empty list, and `classify` is never called. The
       measured class is still satisfied at the system level — the gate's `any(classify(c) for c in
       [])` is `False`, the correct answer — but there is no `ShapeChange` to hand it. Do not
       manufacture one to make the class look covered; record it as discharged by absence;
     - **prose changed** resolves the same way: T1.1 excludes descriptions from the record, so a
       prose-only edit produces no change and `classify` is never reached. Test it at the
       `diff_shapes` layer (empty list), never by hand-building a change.

     **Every kind `diff_shapes` can emit must have a rule.** There are ten. A kind with no branch
     falls through to whatever the default is, and a default that returns `False` means the detector
     stays silent on a change it detected — the failure this spec exists to eliminate, one layer
     further in. Assert the exhaustiveness directly. **Mechanism, so it is not left to invention:**

     a. Export a single `CHANGE_KINDS` constant from `wire_shape.py` — the vocabulary in one place,
        the same single-source rule `PUBLISHED_WIRES` follows. A test enumerating the ten kinds
        itself duplicates the vocabulary and can drift from the module's, leaving the exhaustiveness
        check passing against a list that no longer matches reality.
     b. `classify` **raises** on a kind it has no rule for. Silently returning `False` is the exact
        failure being guarded — the detector staying quiet about a change it successfully detected.
     c. One test iterates `CHANGE_KINDS` and asserts `classify` returns a bool for each. Adding an
        eleventh kind to the constant without writing its rule then fails this test.
     d. `_change` validates its `kind` argument against `CHANGE_KINDS`. This closes the direction the
        other three miss: a kind emitted by `diff_shapes` but never added to the constant would
        otherwise slip past (c) entirely, since (c) only ever sees what the constant lists.
  3. Implement: `classify(change, observed) -> bool`, reading `closed` from the manifest.
  4. Validate: unit tests pass; ruff clean.
  5. Success:
     - [x] Closed-node addition is affecting `[ref: PRD/F2-AC1]`
     - [x] Open-node addition is not `[ref: PRD/F2-AC2]`
     - [x] Enum addition is affecting `[ref: PRD/F2-AC3]`
     - [x] Required removal is affecting; optional removal is not `[ref: PRD/F2-AC4]`
     - [x] Closing a node is affecting; opening one is not `[ref: PRD/Business Rules; Rule 8]`
     - [x] A wholesale node addition is affecting `[ref: PRD/Business Rules; Rule 9]`
     - [x] Every kind `diff_shapes` emits has a rule, asserted exhaustively over `CHANGE_KINDS`
     - [x] A field joining `required` is not affecting `[ref: SDD/Application Data Models]`

- [x] **T2.3 The gate, and a message that says what to do** `[activity: backend-api]`

  **Module-split seam, decided at T2.2's code review (2026-09-10).** `wire_shape.py` is now 516
  lines and holds the walk, the manifest builder, the serializer, the registry, the diff, the kind
  vocabulary and the classifier. Reviewed twice for splitting and declined twice, because raw LOC is
  a poor proxy here — `classify`'s docstring alone is ~80 lines of rule-table prose, the branching
  logic is small, and everything shares one `NodeShape`/`ShapeChange` data model. **The trigger is
  not line count: it is whether this task's gate logic lands inside `wire_shape.py` or beside it.**
  Put the gate in the test module or its own file. If gate or CLI logic goes *into* `wire_shape.py`,
  split `classify` + `CHANGE_KINDS` + the kind constants out at that moment — the file stops being
  "one data model and three views of it" and becomes "the data model plus the thing that drives it",
  which is the seam. Same instruction applies to T4.1.

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
     - two wires changed in one edit → both reported, each against its own counter. **The gate
       iterates all three wires and reports every failure together; it must not stop at the first.**
       Stopping early would hide a second wire's obligation behind the first one's, and CON-4 exists
       precisely because the counters are independent;
     - **the non-affecting message must NOT demand a version move** — assert its absence, not merely
       the presence of the regeneration instruction `[ref: PRD/F7-AC2]`. A message that asks for both
       satisfies a presence-only test while telling the maintainer to do something the rule says is
       unnecessary, which is how a detector starts crying wolf.

     **Separate the decision from the rendering.** Four of this task's criteria are about what the
     failure *says*, and there are two bad ways to test that: assert exact prose (brittle — any
     rewording breaks the suite) or assert nothing (the message rots while the tests stay green).
     Neither is necessary. Have the gate produce a **structured result** — per wire: the document,
     the changes with their pointers and properties, whether any is affecting, the version
     transition, and which actions are demanded — and render the human message from it. Tests then
     assert against the structure, with one or two covering the rendering itself.

     This is the same rule already settled for `detail`, applied one level up: **a human-readable
     string is for humans and nothing may parse it.** It also pays forward — T4.1's `--obligations`
     needs one row per changed field, and a structured result means the CLI reuses the gate's output
     instead of scraping its message.
  3. Implement: the check iterating the three published wires. **Put it in its own file** —
     `tests/test_035_wire_gate.py` — consistent with the one-file-per-concern split the other 035
     test modules already follow, and it keeps the gate out of `wire_shape.py` as the module-split
     note above requires.
  4. Validate: unit tests pass; ruff clean. **The gate must be GREEN on the repository as it
     stands** — the committed manifests match the live schemas, so the honest answer today is "no
     change". That is also the trap: a gate that unconditionally passes is equally green right now,
     so every failure case has to be proven against a mutated scratch copy rather than against the
     real tree. **Never mutate a committed schema or manifest in place.**
  5. Success:
     - [x] Affecting + unmoved version fails; moved passes `[ref: PRD/F2-AC5]`
     - [x] The failure names the **document**, the location and the property `[ref: PRD/F1-AC1]`
           — the half T2.1 structurally cannot deliver
     - [x] The failure names the expected next steps `[ref: PRD/F7-AC1]`
     - [x] A non-affecting change does not demand a version move `[ref: PRD/F7-AC2]`

- [x] **T2.4 Replace the vacuous comparison in the existing wire-hygiene test** `[activity: backend-api]`

  The existing upstream check builds its surface from `$defs` entries carrying an `action` property
  and iterates their intersection. On the instructions wire that is 18 real comparisons; on a
  `$defs`-free schema it is zero, so the check passes while the schema is drifted. It also compares
  no root-level fields on either document — root parity today is coincidence.

  1. Prime: read the current comparison and confirm the vacuity for yourself before changing it —
     the claim is measured, but an implementer who has not seen it will not trust the replacement.
  2. Test — **and read this first, because the obvious gate for this task does not work.**

     The task's natural evidence is "every existing test still passes" and "full suite green". Both
     are satisfied by *not running the changed code at all*: `test_snapshot_matches_upstream_hashi`
     fetches over the network and **skips offline**, which it is doing in this environment right now.
     A replacement validated that way is indistinguishable from no replacement. Worse, converting the
     check to a report **removes its failure mode entirely** — after this change "nothing failed" is
     the expected outcome in every case, including the case where the comparison silently does
     nothing. That is the exact shape of the vacuous pass this spec exists to eliminate, so the
     evidence has to come from somewhere else.

     **The real gate is a set of offline fixture tests. Build these first:**

     a. **Non-vacuous on a `$defs`-free document.** Take `suggestions-wire.schema.json` (zero `$defs`
        — measured), copy it, add a property to a node, and assert the comparison reports it. The old
        `$defs`-keyed surface reports **nothing** here, which is why it could never have caught the
        drift that started this spec. `[ref: PRD/F1-AC3]`
     b. **Root-level differences are detected.** The old comparison never looked at root fields at
        all — root parity today is coincidence. Mutate a root-level property and assert it appears.
        `[ref: PRD/F1-AC1]`
     c. **The report's content today is known, so assert it exactly.** Deleting
        `SNAPSHOT_AHEAD_OF_UPSTREAM` means its three actions now show up in the delta — they are in
        our snapshot and not upstream, which is the whole reason they were exempted. Synthesise an
        "upstream" offline by copying `hashi-instructions.schema.json` and removing
        `edit_note_text`, `resolve_dead_link` and `remove_up_link`, then assert the report contains
        **exactly those three** and nothing else. This is the strongest available test: it runs
        offline, uses the real document's shape, and pins content rather than mere non-emptiness.
     d. **The report is a report.** Assert that a delta is produced AND that producing one raises
        nothing and fails nothing. Both halves — a function that fails on drift is still a gate, and
        one that never produces a delta is a no-op wearing a report's name.
     e. Every existing test in the file still passes, and the network test still **skips** offline
        rather than failing. Necessary, but explicitly not sufficient — see above.
  3. Implement: swap the comparison surface for `describe_shape` + `diff_shapes`.

     **DECIDED 2026-09-10: this comparison becomes a REPORT, not a gate.** Owner decision.

     ~~The exemption registry cannot survive a full-depth walk unchanged.~~ **That claim was wrong
     and is withdrawn.** It asserted that `SNAPSHOT_AHEAD_OF_UPSTREAM`'s three entries "also appear
     in the snapshot's root `properties/actions/items/oneOf`", so a def-name-keyed registry could not
     filter them. Measured instead: each ahead-action appears at exactly **one** pointer, its own
     `/$defs/<name>`. All 16 `oneOf` branches are pure `$ref` objects declaring no `properties`, and
     `describe_shape` only records a node where `properties` exists — so a `$ref` branch is never a
     recorded pointer. The registry would have survived a full-depth walk untouched. Noting this
     because the false claim was itself labelled "corrected by validation", which is how a wrong fact
     acquires the authority of a checked one.

     The decision therefore rests on principle rather than cost, where it always should have:

     - **ADR-7 already ruled that a vendored consumer copy is a report, never a gate**, because it is
       *supposed* to lag ours between handoff and confirmation. This snapshot is exactly such a copy.
     - `SNAPSHOT_AHEAD_OF_UPSTREAM` exists **only because we were gating something that should not be
       gated**. Its three entries are each a pending handoff where we are deliberately ahead. As a
       report, the registry is not redesigned — it is deleted.
     - It was already effectively a report: the test fetches over the network and **skips offline**,
       which it is doing in this environment right now. A gate that cannot run is not a gate.
     - Applying ADR-7 to two vendored copies (T4.2) and not this third one is the inconsistency
       someone would have to explain later.
  4. Validate: full suite green **and** the offline fixture tests above. **Before deleting
     `SNAPSHOT_AHEAD_OF_UPSTREAM`, grep the repository for it and for its three action names** and
     confirm nothing else depends on the registry or on those actions being exempt — a second
     consumer would turn a deletion into a silent behaviour change somewhere unrelated.

     Define what "report" means in code rather than leaving it to taste: follow T2.3's precedent —
     a **structured delta** plus a renderer that turns it into human text. `wire_gate.py` already
     has that shape, and reusing it keeps one reporting idiom in the spec rather than two.
  5. Success:
     - [x] Root-level differences are detected `[ref: PRD/F1-AC1]`
     - [x] A `$defs`-free schema is compared non-vacuously `[ref: PRD/F1-AC3]`
     - [x] Existing wire-hygiene and parity tests unchanged `[ref: SDD/Implementation Boundaries]`
     - [x] The upstream comparison reports a delta and never fails on one `[ref: SDD/Architecture Decisions; ADR-7]`
     - [x] `SNAPSHOT_AHEAD_OF_UPSTREAM` is removed, not re-keyed — a report needs no exemptions

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
