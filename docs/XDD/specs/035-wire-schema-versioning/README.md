# Specification: 035-wire-schema-versioning

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-09 |
| **Current Phase** | Ready |
| **Decomposition tier** | Incremental |
| **Last Updated** | 2026-09-10 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 9 features, 33 criteria, 4 open questions |
| solution.md | completed | 7 ADRs confirmed, 14 EARS criteria, all 8 features owned |
| plan/ | completed | Incremental — 4 phases, 17 tasks, 33/33 criteria referenced |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-10 | **Four phases; the last one cannot be completed in-session** | Phase 1 records the shape, Phase 2 turns it into a gate, Phase 3 (independent, verified by file overlap rather than asserted) removes two ways the mechanism could be defeated from underneath, Phase 4 makes it usable and closes the live drift. **T4.3 ends by writing a handoff and stopping**; T4.4 is blocked on the owner returning with the consumer's confirmation. The spec does not reach `Implemented` until they have — that is the WAIT rule applied to a plan rather than to a message. |
| 2026-09-10 | **The manifest and the vendored copy answer different questions — stated in the plan because conflating them is the likeliest misimplementation** | The manifest asks *did **we** change since last recorded* and correctly bakes our current state as baseline; the vendored copy asks *does the **consumer** accept what we emit*. The garden-audit drift is visible only to the second: our schema declares eight properties on `findings[].detail`, theirs declares six — measured on both sides. A reader who expects the manifest to surface that drift will conclude the mechanism is broken when it is working as designed. |
| 2026-09-10 | **F9 was missing entirely — the daily-side `source_item_key` had no feature and no task** | Found by validation. The widening was decided on 2026-09-09 (row below), **promised to Hashi in a handoff**, asserted in this spec's own SDD, and **consumed by 036's release task** — yet the PRD had no feature for it and the plan had no task. The PRD was drafted from the research findings and lost a decision that predated them. Added as F9, numbered out of sequence deliberately: renumbering would invalidate every plan reference, and the cost of the mistake should not be paid by the documents that got it right. The 28/28 coverage count had been arithmetically correct over an **incomplete requirement set** — counting mechanically does not help when the thing counted is missing a row. |
| 2026-09-10 | **One handoff carries the whole release; 036 supplies its half rather than sending its own** | Falls out of F9's recovery. Three documents move together — garden-audit disclosure, suggestions daily-side identity, instructions `depends_on` — and Hashi asked for one changed-fields list and one vendoring pass. Three separate handoffs is precisely the outcome that request exists to prevent. 035's T4.3 owns the handoff; 036's T4.5 hands it the instruction-wire row. Also settles the naming: **"obligation table"** wins over "changed-fields list", and 036 adopts it. |
| 2026-09-10 | **The manifest does not, and should not, report the garden-audit drift** | The SDD's Known Issues and the PRD's recovery journey both claimed the detection would surface it on first run. False: our schema already declares `up_source`/`up_value`, so the manifest records them as the baseline — correct for the question a manifest answers. The drift is visible only to the vendored-copy report, which does not exist until T4.2. The walkthrough showing `diff_shapes` yielding two changes for it is **counterfactual** and now says so; reproducing it in a test needs a scratch manifest built from the pre-032 schema. |
| 2026-09-10 | **Decomposition tier: Incremental** | Classifier recommended Incremental and it was accepted. Signals: `change_type=feature`, `feature_count=6`, `ac_count=28`, `component_count=2` (new code surface — the `wire_shape` library and the user-invoked CLI; the manifests are data, not components), `parallel_markers=false`. The word "parallel" does occur in `solution.md:210` but as *"a parallel list of rules that could drift"* — prose, not a work-stream marker. Recorded as false deliberately: a signal taken from a substring match rather than its meaning is the by-eye counting that went wrong twice in spec 036. Rule 1 fires on both clauses; `change_type=feature` means rule 2's escape never applied. |
| 2026-09-10 | **ADR-1: a committed shape manifest per wire is the baseline — detection and the obligation table are one mechanism** | The report must name document, pointer and property, which rules out a hash. It must work on a schema with no `$defs`, which is exactly the document that drifted. It must work offline, because the consumer's copy is deliberately stale during a wait. A structural manifest satisfies all three — and the diff printed when it is regenerated **is** the obligation table's raw material, so F1's detection and F4's handover cannot disagree with each other. |
| 2026-09-10 | **ADR-2: the manifest records types as well as names, `required` and openness — but never prose** | The first draft excluded types on churn grounds. Corrected before confirmation: the eight-class matrix measured a **type change as consumer-affecting** — emitting `null` where `string` is declared errors in Hashi's validator — so excluding types would have left a real breaking change invisible to the detector. Descriptions stay out, because that is where the churn actually is. The line is drawn where the noise is, not where the recording is cheapest. |
| 2026-09-10 | **ADR-5: renderers read `schema_version` from their own schema instead of declaring it** | Makes the divergence F3 describes **impossible** rather than merely detected. Feasible because schemas ship to the instance (`install-tomo.sh:1262-1264`) and `garden-audit-configure.py:49` is the existing precedent for a runtime script resolving one. The F3 assertion stays as a regression guard even though it becomes vacuous. |
| 2026-09-10 | **ADR-7: all three consumer copies are vendored, as a REPORT rather than a gate** | Owner decision, against the drafted recommendation to leave two wires uncovered. The consequence shaped the design: a vendored copy is *supposed* to lag ours during a wait, and the instructions wire handles that today with `SNAPSHOT_AHEAD_OF_UPSTREAM`, which is **keyed by action name** and therefore unusable for two schemas containing no actions. Rather than rebuild that registry pointer-by-pointer, the copies answer "what does the consumer accept right now" and the delta is reported, never failed. The gate stays the manifest, which describes our own schema and needs no wait-window exemption. |
| 2026-09-10 | **The existing drift check cannot catch this class of change — it passes vacuously** | Measured, not inferred. `test_snapshot_matches_upstream_hashi` builds its comparison surface from `$defs` entries carrying an `action` property. `suggestions-wire.schema.json` has **zero `$defs`** — every object is inline — so the diff loop runs **zero iterations** and the test passes while the schema is drifted. Pointing it at the drifted document would have changed nothing. Even on the instructions wire it compares no root-level fields: root parity today is coincidence, not enforcement. This retires the cheap version of this spec ("extend the existing test") before it was proposed. |
| 2026-09-10 | **Three published wires, not two — and a THIRD drift is live right now** | The garden-audit wire is vendored and compiled by Hashi (`garden-audit-validator.ts:12`), so it is a contract. `up_source` and `up_value` were added to `findings[].detail` by specs 032/033 (`33fb7d8`, `2111772`), never announced, never vendored, both sides still pinned at `"1"`. Verified against **every Hashi remote branch and `origin/main`** — not a working-tree artefact. It is non-breaking **only** because `findings[].detail` is the single open node in that document; root and `findings[]` are both closed. The pattern recurred while the spec about it was being written. |
| 2026-09-10 | **The bump rule is "is the node closed", not "did the shape change" — the README's own assumption was falsified** | Run against Hashi's compiled ajv and Hashi's own fixtures across eight change classes. Consumer-affecting: add to a closed node, remove a *required* field, **add an enum value** (counter-intuitive), widen a type. Not consumer-affecting: add to an open node, remove an *optional* field, start emitting a declared optional, prose. The live garden-audit drift is the standing proof that "any shape change" would cry wolf on exactly the case that is fine. Closed-node counts: suggestions 10/10, garden-audit 6/7, instructions 18/21. |
| 2026-09-10 | **No new handoff protocol — the round trip through the owner IS the lead time** | Owner instruction, overriding a researched proposal. Research had designed a two-phase commit over the protocol's `pending → in-progress → done` flow; the owner's correction: *"we don't need a new handoff protocol… when you need cross repo interaction you need to do the handoff and WAIT."* He carries material between sessions himself. F4-AC4 (do not emit the new version until the consumer confirms) is that rule applied to emission, not a construct. **No shared protocol document is edited by this spec.** |
| 2026-09-10 | **The changed-fields list is an obligation table, not a diff** | Hashi's own structural diff recomputes property sets, `required` and `additionalProperties` from the file — so enumerating changed fields adds nothing. What their diff **deliberately ignores is prose**, which carries every semantic. The list's value is meaning, which of their files must move, and breaking-ness. The decisive case: `depends_on` rejects every set immediately, while `source_item_key` rejects **nothing today** — all current runs have empty daily buckets — so an un-vendored consumer breaks silently on the first run with daily content. That is not derivable from the schema; it needs producer data. |
| 2026-09-10 | **Two adjacent defects pulled into scope: the `$id` collision and the free-floating version literals** | Both instruction schemas declare `$id` `https://miyo.tomo/schemas/instructions.schema.json` with identical title and description while differing structurally (the contract carries a `replace_section` def the producer copy lacks) — the mechanical cause of Hashi diffing the wrong file and reporting phantom drift. Separately, `schema_version` is a free-standing literal in three renderers (`suggestions-render.py:402`, `instruction-render.py:778`, `garden-audit-render.py:1283`) asserted against nothing, so a bump can land in the schema and not the emitter. Both would defeat the mechanism this spec builds; neither is worth a spec of its own. |
| 2026-09-10 | **Fifteen internal schemas stay out of scope** | `tomo/schemas/` holds ~18 files; exactly three are vendored by Hashi. The rest were grepped for across Kado, Kokoro, Seigyo, Tsukai and Hakobi — zero external references. Bringing them under the rule would fill the report with changes nobody can be broken by, and a detector whose report is never empty is one nobody reads. |
| 2026-09-09 | **Scoped as a versioning mechanism, not as a one-off schema fix** | Re-vendoring the two drifted fields closes the incident; it does not stop the third one. Two specs walked past the version gate without noticing, and the mechanism that should have caught them exists and is correct on the consumer's side. The spec is about when `schema_version` moves and how the consumer learns of it. |
| 2026-09-09 | **The consumer is consulted on the mechanism before it is picked** | Hashi vendors our schema and enforces it with `additionalProperties: false`. Any scheme that assumes they can read a field before they have re-vendored it is a scheme that breaks them again. The handoff of 2026-09-09 asks for their opinion rather than announcing a decision. |
| 2026-09-09 | **One strict wire, no compatibility window — Hashi's call, accepted** | Offered the optional-field route, Hashi declined it and vendored `item_key` as **required**. Their reasoning: two compatible schemas is a slower version of the same bug, and half-opening a document whose join key is missing reinstates the ambiguity `item_key` exists to remove. This retires question 3 (compatibility window) as a design option and turns question 2 (lead time) into the only lever left. |
| 2026-09-09 | **The daily-side `item_key` goes on the wire; the markdown recovery is retired with it** | `suggestion-parser._restore_daily_item_keys` keeps `source_item_key` off the wire *specifically* because widening a `additionalProperties: false` contract is a coordinated cross-repo change. Hashi has now asked for exactly that change, so the blocker its docstring names is gone. The recovery is lossy by design — it declines to guess on an ambiguous discriminator — so the wire field is strictly better than the mechanism it replaces, independently of Hashi. |
| 2026-09-09 | **Spec 036's route 2 rides this spec's release — two wire changes, two documents, one re-vendor** | 036 chose route 1 (Tomo-side guard, ships independently) plus route 2 (make a `delete_source` name the action that justifies it — a wire change). Batching it with the daily-side `item_key` means Hashi vendors once and re-runs their QA once. It also makes this spec's mechanism carry two unrelated changes on its first outing, which is the honest test of it: a changed-fields list that cannot describe two changes at once is not a mechanism. **Corrected 2026-09-09 after measurement**: this is not one bump. The two changes sit on different documents with independent counters — the suggestions wire is `schema_version "1"`, the instructions wire is `"2"` — so it is 1→2 on one file and 2→3 on the other. One changed-fields list and one Hashi release still hold; "one bump" did not. |
| 2026-09-09 | **No run has ever emitted a `log_link` — the daily-side widening ships without live coverage of one third of it** | Searched every `_suggestions.json` and `_suggestions-fan.json` still in existence: 0 runs with any `log_links[]` entry, 1 run with any daily content at all (pre-034, 0 of 21 suggestions carrying `item_key`), and 4 current-shape runs all with empty daily buckets. The intersection needed for a real fixture is empty. Declined to hand-build one — a fixture assembled from the schema agrees with our assumptions and nothing else. Recorded as a coverage gap rather than hidden: `log_links[]` is a code path neither repo has observed carrying data. |
| 2026-09-09 | **The versioning mechanism is per-document, not global** | Measured, not assumed: the suggestions wire and the instructions wire already carry different `schema_version` values, so a single repo-wide version number cannot describe either of them without lying about the other. Any mechanism this spec lands has to version each wire document on its own counter and say which document a changed-fields list belongs to. This was discovered by 036's integration research; it is a requirement, not a preference. |
| 2026-09-09 | **Every wire change ships the schema as a file plus a changed-fields list** | Hashi asked for both. The file removes the retyping step that already made them diff the wrong one of our two instruction schemas; the changed-fields list is the part a `schema_version` bump alone does not carry. This is the concrete candidate answer to question 5 — the enforceable artifact, not a rule. |

## Context

### What happened

Tomo's Pass-1 suggestions wire (`tomo/schemas/suggestions-wire.schema.json`) gained two fields in
`suggestions[]` across two specs, while `schema_version` stayed `"1"`:

| Field | Added by | Commit |
|---|---|---|
| `attachments` | spec 031 — file inbox attachments alongside the notes that embed them | `9847829` |
| `item_key` (in `required`) | spec 034 — schemas carry required item_key | `2a5c6d9` |

Hashi vendors its own copy of that schema and compiles it with ajv
(`src/schema/suggestions-validator.ts:9`). Every object in it is `additionalProperties: false`.

**Measured on 2026-09-09**, running Hashi's vendored schema and ajv options against a real
`_suggestions.json` from the 2026-09-08 run: eight validation errors, two per suggestion,
`item_key` and `attachments`. `validate()` returns `{ok: false}`, so `SuggestionsDoc` never builds
an `EditModel` and the Suggestions Editor registered at Hashi's `main.ts:628` cannot open any run
Tomo currently produces.

The drift is bounded: a property-set diff of the two schemas shows those two fields in
`suggestions[]` and **nothing else** — root, `proposed_mocs[]`, `daily_updates[]` and
`tag_handler_groups[]` are all in sync. The Pass-2 instruction schema
(`hashi-instructions.schema.json` vs Hashi's `instructions.schema.json`) is fully in sync too:
root plus all 20 `$defs`, no field drift, no required drift.

### Why the existing gate did not fire

Hashi's schema pins `"schema_version": {"const": "1"}` and its validator has prescribed wording for
a mismatch — `"Schema version mismatch — expected X, got Y"` — specifically to drive an "upgrade
Hashi" prompt. That path never ran, because the version never moved. The gate is built correctly
on the consumer side; the producer walked around it twice.

### The question this spec answers

Under `additionalProperties: false`, **an added field is not additive for the consumer.** So:

1. When does `schema_version` move — on any shape change, or only on a change that breaks a
   consumer? (The incident says those are the same thing here, but that should be stated, not
   assumed.)
2. How does a consumer learn a bump is coming, given they vendor the schema and ship on their own
   cadence? A bump with no lead time turns a silent break into a loud one — better, but still a
   break.
3. Is there a compatibility window, and what does Tomo emit during it?
4. Does the same rule apply to the Pass-2 instruction schema, which is in sync today and has more
   consumers-in-waiting? And to the garden-audit wire?
5. What stops the next spec from adding a field without noticing — a test, a checklist item in the
   XDD gates, or something that reads both schemas and fails?

Question 5 is the one that decides whether this spec is worth building. A rule nobody enforces is
what we already had.

### Hashi's reply (2026-09-09)

`_inbox/from-hashi/2026-09-09_hashi-to-tomo_wire-drift-fixed-and-the-rename-is-wrong.md`.
All five measured claims reproduced on their side. Verified here against their source rather than
taken on report:

| Their claim | Verified how |
|---|---|
| `item_key` + `attachments` vendored, `item_key` **required** | `origin/fix/suggestions-wire-item-key-attachments` commit `01921c6`; their `suggestions[].required` now carries `item_key`, `attachments` optional — matches ours field for field |
| The unknown-property notice now names the key, in all three validators | Read in the branch diff; `suggestions-validator.ts`, `validator.ts`, `garden-audit-validator.ts` |
| The `forceAtomicSync` namesake join is real | `src/suggestions/transforms/forceAtomicSync.ts` — `suggestion.stem === stem` and `entry.source_stem === stem`, both fanning out over every match |
| **Our §6 rename request was wrong** | `src/commands/registerCommands.ts:367-371` — ADR-6, the command id is unchanged and the label was changed *to* "Open Tomo editor" because it suffix-dispatches to **both** editors. `dispatchOpenSuggestionsEditor` routes on the active file: `_garden-audit.json` → Garden-Audit, `_suggestions.json` → Suggestions, neither → a merged picker. Renaming it to "Open suggestions editor" would misname it for every garden-audit run. **Withdrawn.** |

**Schema sync re-measured after their fix**: a structural diff of their branch copy against
`tomo/schemas/suggestions-wire.schema.json` — property set, `required` list and
`additionalProperties` at every nesting level — is identical. The drift is closed, measured rather
than assumed.

Their consumption constraint on the daily side: `item_key` **required** there too, and
`source_stem` stays as display text.

### The daily-side ask is three sites, not two

Hashi named `daily_updates[].log_entries[]` and `tracker_updates[]`. There is no top-level
`tracker_updates` on the wire; the array they mean is `daily_updates[].trackers[]`. And a third
bucket they did not name carries the same identity problem:

| Wire bucket | Source identity today | `source_item_key` in the doc schema |
|---|---|---|
| `daily_updates[].trackers[]` | `source_stem` (display text) | yes |
| `daily_updates[].log_entries[]` | `source_stem` (display text) | yes |
| `daily_updates[].log_links[]` | **none** — the wire carries `target_stem` only | yes |

`log_links[]` is the sharper case: the wire has no source field at all, so a consumer cannot join
it to its originating note by any means, ambiguous or otherwise. `instructions-diff.py:363` reads
`ll.get("source_stem", "")` and gets the empty string on the wire path.

Tomo already computes `source_item_key` for all three buckets. `suggestions-doc.schema.json`
declares it on `daily_notes_updates[].{trackers,log_entries,log_links}[]`, and
`suggestion-parser.enrich_daily_updates_with_item_keys` recovers it after the markdown round trip
by matching on `(daily-note stem, bucket, discriminating field)` — `_DAILY_DISCRIMINATOR` covers
all three. The recovery **declines to guess** when a discriminator maps to more than one key, so
an ambiguous entry silently keeps only its display stem. That lossiness is the Tomo-side cost of
the wire not carrying the field.

### Scope boundary

This spec does **not** re-vendor Hashi's schema — that is Hashi's file and their release. The
handoff `_outbox/for-hashi/2026-09-09_tomo-to-hashi_suggestions-wire-schema-two-specs-behind.md`
asked for it and offered to hold the wire steady until this spec lands; **Hashi has since shipped
the re-vendor**, so the incident is closed and only the mechanism is left.

The daily-side `item_key` widening is **in** scope for this spec — Hashi asked for it to ride the
versioning change rather than land as another silent field, and it is the first change the
mechanism has to carry.

Spec 036's route-2 field on `delete_source` is **also** in scope for the same reason, decided
2026-09-09. Two changes across **two** wire documents — the suggestions wire (`schema_version "1"`)
and the instructions wire (`"2"`), each on its own counter — bundled into one changed-fields list
and one Hashi release. The guard half of 036 (route 1) is independent of this spec and does not
wait on it.

The Hashi-facing instruction contract is `tomo/schemas/hashi-instructions.schema.json`, a verbatim
mirror enforced by `tests/test_tomo_schema_parity.py:95`; `tomo/schemas/instructions.schema.json`
is the producer copy. Hashi has already confused this pair once — naming which is which is part of
what a handoff must carry.

### Prior art in this repo

- `docs/XDD/specs/034-recursive-inbox-discovery/README.md`, decisions of 2026-09-06 — two
  corrections in a row about which wire Hashi actually joins on. The lesson recorded there ("a
  boundary question needs the producer, the schema, and the consumer read together") is the same
  lesson this incident teaches, one level up: it also needs the consumer's *vendored copy*.
- MiYo Constitution, Architecture L2: "Public interfaces between MiYo components … Breaking
  changes require explicit review for backward compatibility and a documented migration path in
  Kokoro."

---
*This file is managed by the xdd-meta skill.*
