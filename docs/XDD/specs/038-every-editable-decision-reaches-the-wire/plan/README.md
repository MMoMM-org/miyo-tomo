---
title: "Every editable decision reaches the wire"
status: draft
version: "1.0"
---

# Implementation Plan

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All `[NEEDS CLARIFICATION: ...]` markers have been addressed
- [x] All specification file paths are correct and exist
- [x] Each phase follows TDD: Prime → Test → Implement → Validate
- [x] Every task has verifiable success criteria
- [x] A developer could follow this plan independently

### QUALITY CHECKS (Should Pass)

- [x] Context priming section is complete
- [x] All implementation phases are defined with linked phase files
- [x] Dependencies between phases are clear (no circular dependencies)
- [x] Parallel work is properly tagged with `[parallel: true]`
- [x] Activity hints provided for specialist selection `[activity: type]`
- [x] Every phase references relevant SDD sections
- [x] Every test references PRD acceptance criteria
- [x] Integration & E2E tests defined in final phase
- [x] Project commands match actual project setup

---

## Output Schema

### PLAN Status Report

| Field | Value |
|-------|-------|
| specId | 038-every-editable-decision-reaches-the-wire |
| title | Every editable decision reaches the wire |
| status | `IN_REVIEW` |
| totalTasks | 23 |
| parallelTasks | 3 |
| specReferences | 125 |
| clarificationsRemaining | 0 |

### PhaseStatus

| Phase | Name | Status | Tasks | File |
|-------|------|--------|-------|------|
| 1 | The inventory, and what it reveals | `in_progress` | 4 | `phase-1.md` |
| 2 | The wire carries the decision | `pending` | 5 | `phase-2.md` |
| 3 | Refusal, before anything can be typed | `pending` | 5 | `phase-3.md` |
| 4 | The name becomes a value | `pending` | 4 | `phase-4.md` |
| 5 | Integration, the live path, and one handoff | `pending` | 5 | `phase-5.md` |

---

## Specification Compliance Guidelines

1. **Before each phase**: read the phase file's GATE section in full. Every phase
   references the SDD sections it depends on.
2. **During implementation**: cite the `[ref: ...]` in the code's docstring where
   a decision is non-obvious, and write the WHY into `docs/tomo/<mirrored-path>.md`
   as you go — not at the end.
3. **After each task**: the two-stage review chain (spec compliance, then code
   quality) runs per task, not per phase.
4. **Phase completion**: every PRD criterion the phase claims must map to a test
   that was **executed**, named by node id. "A test exists" is a weaker guarantee
   than usual on this spec — see the note on unbiteable mutations below.

### Deviation Protocol

1. Document the deviation with rationale in the phase file.
2. Obtain approval before proceeding.
3. Update the SDD when the deviation improves the design.
4. Record every deviation here for traceability.

#### Recorded deviations

| Date | Task | Deviation | Rationale |
|------|------|-----------|-----------|
| 2026-09-30 | T1.1 | T1.1 gains a test of its own: the inventory's JSON Schema is written first, then `tests/test_038_inventory_schema_validation.py`, before the inventory is authored. The task previously declared "Test: none yet". | The TDD guardian blocked the task on an internal contradiction: T1.1 claimed no test while carrying "a malformed row fails Tomo's tests" as a success criterion, which `[ref: PRD/F4]` requires. T1.2's join test proves *completeness*, never *row validity*, so as originally sequenced that PRD criterion was owned by no test in the plan. The guardian's distinction is the one that resolves it — a test for "what makes a row valid" is available immediately, a test for "which rows exist" is not. Approved by the owner 2026-09-30. |
| 2026-09-30 | — | The schema's `Editable` field count corrected from 23 to 21 in this file, `solution.md` ADR-7, and twice in `phase-1.md`. | Measured, not recalled: a walk over every schema description containing `Editable` returns 21, and returns 21 at `main`, so the schema had not drifted — the figure was wrong when written. Corrected before T1.1 was dispatched so no implementer is primed to count until it reaches a number that does not exist. Commit `de8da00`. |
| 2026-09-30 | T1.1b (new) | A task is added to Phase 1, between T1.1 and T1.2: mark `candidate_mocs[].selected` and `.anchor` `Editable` in the wire schema, add a `parser_label` key to the inventory, make the D22/D23/D24 notes self-contained, and correct the plan's two control counts. Phase 1 goes from 3 tasks to 4; the spec from 22 to 23. | Two owner rulings on T1.1's findings, both 2026-09-30. **First:** `build_from_wire` honours `selected` (it skips unselected entries) and `anchor`, yet neither description carries the `Editable` marker — so ADR-7's schema-side join is permanently blind to two fields the wire acts on, which is the exact blind spot this spec exists to close. **Second:** the parser-side join needs a key, and neither available field can serve — `wire_field` is `null` on D24, and `markdown_control` is prose whose provenance was deliberately stripped as consumer-facing. Without `parser_label` the mapping would live as a hand-written dict in the test, which is "a rule someone has to remember" — the mechanism ADR-7 names as what failed in 037. Both must land before T1.2 writes its join, and they share two files, so they ship as one task rather than three review cycles. |
| 2026-09-30 | T1.1b | The schema's `Editable` field count is corrected again, from 21 to **23**, in this file, `solution.md` ADR-7, and once in `phase-1.md`. The plan's "about seven" / "~7 recognised controls" estimate is replaced everywhere it appeared with a measured **34** distinct `parser_label` values across the inventory's 24 rows. | Both measured, not recalled. The 21→23 count follows directly from T1.1b step 3a marking `selected` and `.anchor` `Editable`, verified by a committed test that walks the wire schema. The label count is a plain `len(set(...))` over every row's `parser_label` array as authored from the parser source, derived per-decision rather than estimated — it was never a count of "controls" in the loose sense the original estimate meant, so the two numbers are not directly comparable, only the estimate's role (an approximation) is retired. |
| 2026-09-30 | T1.2 | Step 3 now mandates how the parser side is enumerated: a stdlib `ast` walk over string constants compared against the checkbox text or field key, inside named control-recognition functions, floored at 34. Step 5 gains notes that criteria 3 and 4 run on synthetic rows, and that this test's `>= 23` floor is not redundant with T1.1b's `== 23`. A residual limitation is documented: a control in a brand-new function stays invisible. | The TDD guardian blocked the task because it never said *how* the parser side is enumerated, and both unstated options fail differently — a hand-written list makes the criterion theatre (a control added to the parser and not the list fails nothing, which is the hole 037 shipped), while regex over Python source misreads multi-line calls and fails confusingly. The `ast` walk is the only option where a control added to an already-scanned function is caught with nobody remembering anything. Owner chose it 2026-09-30 over the cheaper hand-written list, accepting ~30 lines of walking in the test. The guardian also established the two count guards catch different mutations — deletion versus silent non-match — so a future reader is told not to remove either. |
| 2026-09-30 | T1.2 (superseding the row above) | The parser-side extraction is corrected by measurement: it filters by **what is compared** (the control subjects `text_lower`, `key`, `label`, `cb_text`, `text`, `stripped`), not by which function it sits in, and the floor is **61**, not 34. Every harvested literal must be in a row **or** in a justified-absence list with a stated reason — the consumer's own fail-closed pattern. | The previous row's mechanism was wrong on both counts and measurement caught it before dispatch. An unscoped walk harvests **78** literals against the inventory's 34; scoping to the five control-recognition functions still yields **~70**, so function scope is not what removes the noise; the subject filter yields **61**. The 31 not in rows are legitimately absent — structural markers, option values, and read-only field keys including `summary` and the dead `classification` branch — so the harvest is correctly finding non-editable fields. Four row labels (`—`, `after_last_line`, `before_first_line`, `force atomic note`) cannot be harvested by any AST filter, being a regex literal, set-membership against a module constant, and a call-chain comparison; they are in rows already and documented as unguarded rather than chased. Owner chose the fail-closed absence list 2026-09-30 over an advisory parser side. |
| 2026-10-01 | T2.1 | "The version move touches **three** artefacts" is corrected to **two** — the live schema and the shape manifest. The vendored `hashi-suggestions-wire.schema.json` is explicitly excluded and left to Phase 5, and the manifest's **two** internal version sites are named. | Settled by precedent, not preference. The last version move — `4338481`, spec 035 T4.3, garden-audit `1`→`2` — touched the live schema and the shape manifest only; the vendored copy was updated in a separate later commit, `f63b947` ("the consumer vendored"), once Hashi had confirmed. That file records the consumer's actual state, so stamping `"3"` into it at the move would make `snapshot_parity_delta` report a clean `[]` while Hashi's real copy still pins `"2"` and would reject every document we emit — hiding the obligation the Phase 5 handoff exists to carry. Owner ruled "leave untouched until Phase 5" 2026-10-01. |
| 2026-10-01 | T2.1 | Three factual fixes to the task text: `classify()` is at `wire_shape.py:582-725`, not `wire_gate.py:582-725`; the regeneration CLI is `scripts/wire-shape.py --regenerate`, not "`wire_shape.py`'s CLI"; and `attachment_conflicts` is pinned as joining the schema's top-level `required`. | All three measured before dispatch. `wire_gate.py` is **522 lines** and defines no `classify` at all — it imports it from `wire_shape.py` at `:48`, where the function does sit at `:582` and the file ends at `:725`, so the range was right and the file wrong. The CLI lives at `scripts/` (user-invoked), not under `tomo/scripts/lib/`. The required-ness was simply unstated, yet T2.2's "a conflict-free run carries an empty array" is only enforceable if the key is required; `tag_handler_groups`, `proposed_mocs` and `daily_updates` are all required-and-may-be-empty, so required is the consistent answer. |
| 2026-10-01 | T2.1 | A **fourth** artefact is added to the task: `tests/test_wire_snapshot_parity.py`'s `test_suggestions_comparison_a_is_clean_offline` (`:689`) must have its expectation re-measured to the new six-entry delta. A success criterion is added for it, and the Phase 5 record's "four structural changes" is corrected to **six**. | The tdd-guardian returned APPROVE but got criterion 5a's ownership backwards: it reported that this test *owns* "the vendored copy still reads 2". It does the opposite — it asserts `reportable == []`, so leaving the vendored copy alone (the owner's 2026-10-01 ruling) turns it **red**. Measured through the same code path the test asserts on: `partition_sanctioned(snapshot_parity_delta(...))` yields **six** reportable entries and zero sanctioned, and `reportable == []` fails. Left unamended, an implementer meeting a red parity test has one obvious "fix" — bump the vendored copy — which is precisely what the ruling forbids, and nothing downstream would notice. The sanction route is closed: `SANCTIONED_ASYMMETRIES`' own comment restricts it to "a standing cross-repo decision, not a lag awaiting a handoff", and `test_wire_snapshot_parity.py:810` pins the mapping to exactly one key because an exclusion on this wire "hides drift instead of scoping the comparison". Re-measurement is what the test's docstring already instructs, and the precedent is its own history: 0 → 8 → 0 across spec 035, standing at 8 while awaiting the consumer under requirements.md Rule 7. |
| 2026-10-01 | T5.2 → T2.1b | T5.2 "The inventory's remedy row moves off `null`" moves from Phase 5 into Phase 2 as **T2.1b**, and widens: a second row for `proposed_name` and both marked-count guards come with it. `totalTasks` stays **23** — the task moved, it was not added. T5.3–T5.5 keep their numbers. | The plan contradicted itself and T2.1 made the contradiction live. T5.2's own step 2 says the Phase 1 join "should fail until the row is updated, which is the mechanism working" — but T2.5, T3.5 and T4.4 each demand a green suite, so the join would have run red across three phase gates. Measured after T2.1: `25` schema fields marked `Editable` against `23` rows carrying a non-null `wire_field`, which is Phase 1's fail-closed guard doing exactly its job on the first wire change since it shipped. T5.2's only prerequisite — the wire field existing — was satisfied by T2.1, and it is `[parallel: true]`, so nothing argued for keeping it in Phase 5 except where it was first written. The widening is also measured: T5.2's text covers only the remedy row, but T2.1 added **two** editable fields (`remedy` and `proposed_name`), so one row update is not enough and `FLOOR_SCHEMA_MARKED_FIELDS` plus `test_wire_schema_marks_exactly_23_editable_fields` both need their number moved — updated, never collapsed, per the standing warning below. Owner ruled 2026-10-01. The inventory is Hashi-vendored either way, so moving the task does not change the release coupling. |
| 2026-10-01 | T2.5 | T2.5's recorded expected values gain a correction: state C's `proposed_name: null` is **not** part of the stale-wire rejection behaviour. And `scripts/update-tomo.sh` is recorded as deliberately **not** run for this step. | Both measured during the step itself. The `null` reproduces with `--file` alone and disappears when state C is re-run with `--suggestions-doc`, which returns `"karte (2).png"` — so it is an unsupplied input, not a behaviour, and the discriminator between the markdown and wire paths is the **remedy** alone. Left unrecorded, the next reader would cite the `null` as evidence of the rejection path and reach the opposite conclusion. The sync is unnecessary because the version stamp resolves against the schema beside the script (`wire_version.py`), so the repo copy stamps `"3"` with no sync; the instance's stale `"2"` artefacts are therefore untouched and remain a **T5.3** hazard, where the warning already stands. |
| 2026-10-01 | T5.4 | T5.4's Prime and one success criterion corrected: CON-8 is **already discharged**, not pending. Three obligations the gate and the suite will not raise are written into the task, and a second criterion added for the third of them. | Measured 2026-10-01 during T2.5. `_outbox/for-kokoro/2026-09-29_tomo-to-kokoro_four-specs-since-july-034-through-037.md` carries `status: done` and Kokoro replied with ADR-029/030/031, so the task's "both are written and unsent" was stale and would have sent a duplicate. The three carried obligations each have a reason the tooling cannot remind anyone: the gate stops emitting `handover` once the version move completes (so T2.1 silenced the one signal), and `snapshot_parity_delta` ignores `description`, so three already-divergent descriptions sit invisible behind a green suite. |
| 2026-10-01 | T3.1 | T3.1's Prime gains the measured shape of the control it guards: the rendered Rename line is a full destination path, while the wire field is a bare basename. | Measured 2026-10-01 during T2.5's live render. `suggestions-reducer.py:1517` renders `_asset_dest_join(asset_folder, proposed_name)`, so a live run shows ``Rename to `Atlas/290 Assets/295 Attachments/karte (2).png` `` against a wire `proposed_name` of `karte (2).png`. T3.1's specified separator refusal would therefore reject the most natural edit an owner can make — retyping the stem and leaving the prefix. The decision belongs in T3.1, where the refusal set is defined, not in T3.4 where it would surface as a phrasing problem. Also confirms the task is not redundant: `suggestion-parser.py:2350-2354` never reads the backtick-quoted text at all. |
| 2026-10-01 | Phase 3 (T3.1, T3.4, Key Decisions) | Three wrong references corrected and two loose claims sharpened, before any task was dispatched. `_render_unresolved_conflict_bullet` is at `render_md.py:740`, not `:797`; the "skipped block" is at `:1079-1095`, not `~:1046-1051`; ADR-11's substantive treatment is `docs/tomo/scripts/lib/render_md.md:502-510`, not `:328-330`. T3.1 now names **two** guards that miss `" "` and a tenth forbidden character; the Key Decisions call `_asset_dest_join`'s behaviour basename extraction rather than truncation. | The measurement habit Phase 2 established, applied before dispatch rather than after. Each of the three references is one an implementer follows literally: `~:1046-1051` would have primed them on the *unresolved_conflicts* block and its passive-voice history instead of the skipped-assets block they must extend, and `:328-330` gives three lines of a different ADR's argument where `:502-510` is about the very bullet T3.4 touches, including the owner's 2026-09-27 ruling on it. The two sharpenings are measured facts the plan stated loosely: the singular "existing emptiness guard" is two guards (`render_actions.py:788` and `:572`), which matters because they fail differently — one skips the degradation, the other declines to raise — and `FORBIDDEN_CHARS` has ten members where T3.1's "each of" enumerates eight. Nothing in the phase's intent changed; eleven other references and counts in the same text were checked and verified correct, including F3's nine criteria and the three `skipped_assets` kinds. |
| 2026-10-01 | T3.1, T3.2, T3.4, SDD Interface Specifications, PRD F3-AC4 | T3.1's closed set drops from four refusal reasons to **three** string classes; `taken` stays where it already works. The SDD's reason list loses `taken` and gains a paragraph saying why; F3's fourth criterion keeps its text and gains the reading that makes it true; T3.2 gains a case it confirms rather than builds; T3.4 is told its reasons now arrive from two sources. | The tdd-guardian BLOCKED T3.1 for specifying a refusal class no test could reach, and was right. Both options it proposed were then measured and neither survived. Passing in a set of taken names requires a data source that does not exist: `_build_move_asset_actions` takes `manifest, inbox_path, asset_folder, counter, attachment_conflict_remedies` and no listing, `path_exists` appears nowhere in `render_actions.py` or `render_md.py`, and the wire carries only `destination`, `same_file`, `proposed_name` (ADR-3). Moving the detection into T3.2 mis-describes the work, because there is nothing to move — the run-local check already exists at `:836-847` and the comment at `:940-944` was written specifically to guarantee a remedy-chosen destination reaches it. The finding underneath is larger than the signature question: F3's fourth criterion has two readings, and the vault-side one is undecidable in Pass 2 by any module, which the system already admits to the owner on the `Ignore` line after a 2026-09-28 owner catch. Owner ruled 2026-10-01: three string classes, one argument, no vault listing. |
| 2026-10-01 | T3.1 (review) | The code-quality review's one substantive suggestion — drop `_NON_SEPARATOR_FORBIDDEN_CHARS` and use `FORBIDDEN_CHARS` directly — was **declined**, with the code left as the implementer wrote it. | Both the implementer (who flagged it as possible ceremony) and the reviewer (who called it indirection that cannot change behaviour) argued it without testing it. The reviewer is right that it cannot change behaviour *as the code stands*, because the separator check returns before it. It is wrong under the one mutation this module is most likely to suffer. Measured by applying that mutation — forbidden-character check moved ahead of the separator check — `a/b.png` reports `separator_present` with the derived set and `forbidden_character` with bare `FORBIDDEN_CHARS`. So the derived set is a second, independent mechanism enforcing the same rule, which is exactly what the module's own comment claims ("rather than relying on ordering alone"). The ordering test would catch the reorder, but defence in depth here costs one derived frozenset. The review's second suggestion — that `test_nul_byte_is_refused` duplicates the loop's NUL case — is accepted as true and kept anyway: it is the executable record of the measured finding that the task's "each of" enumerated eight of ten characters and never named NUL. |
| 2026-10-01 | T3.2 (grows), T4.2 | T3.2 gains a provenance flag, `name_is_owner_supplied`, set in both producers inside `suggestion-parser.py`, and now checks a name only when it is `True`. The task grows from one file to two. T4.2 gains the rule for flipping the markdown side. | T3.2's own two requirements contradicted each other and neither could be dropped. "Call the check before `_asset_dest_join`" runs on every rename; "the computed-name path is unchanged" (F3-AC9, "this feature constrains typed names only") forbids that — and `proposed_name` carries no provenance to branch on, because `detect_attachment_conflicts` builds all five keys in one literal (`suggestions-reducer.py:735-741`) and none marks who supplied the name. It is not satisfied by accident either: `_propose_asset_name` rebuilds the name from the raw basename (`:573-577`) and sanitises nothing — `FORBIDDEN_CHARS` appears nowhere in that module. Measured by running T3.1's check over names the reducer would compute: **five of seven** realistic macOS filenames are refused, since `* " | < > \` are legal on macOS and forbidden by Obsidian. Owner ruled 2026-10-01: carry the flag. It is internal to one file, so no schema and no wire field change and Phase 2's version question stays closed. Rejected alternative: compare the wire's `proposed_name` against the doc's computed one — more precise, but it re-couples the JSON-only path to the doc, which T2.5 measured working without it. **The cross-phase half is the part that would have bitten**: after T4.2 every markdown name comes from the rendered text, untouched defaults included, so flagging them all `True` would refuse an untouched default whose computed name is unusable — the rejected option arriving one phase later, and a contradiction of T4.2's own byte-identical test. On that path the comparison is free, because `:2998` already loads the doc, so T4.2 sets the flag to `extracted != computed`. |
| 2026-10-02 | T4.1, T4.2 | `rename_impossible` narrows from "the marker is in the label" to "the marker is in the label **and** no usable name was extracted", so a name typed into T4.1's new empty backticks is honoured rather than discarded. | Measured on today's parser while priming Phase 4, before briefing anyone: T4.1's empty backticks are **inert**. `rename_impossible` is `RENAME_IMPOSSIBLE_MARKER in label` and `_resolve_attachment_remedy` turns `rename_ticked` plus that into `ignore`, so `- [x] Rename to \`…karte-2.png\` — no free name available` resolves to `ignore` while the identical line without the marker resolves to `rename`. The feature would have been absent from the case the plan itself calls "the case that most needs a rename", and a name typed there silently discarded. The narrowing is faithful to the 2026-09-23 decision rather than a reversal: that decision's stated reason is that `rename` with no `proposed_name` hands Pass 2 a destination-less move, which cannot arise once a name is typed. Empty backticks left untouched still resolve to `ignore`. Ordering now matters between the two tasks and both texts say so. |
| 2026-10-02 | PRD C1 | C1 closes as **satisfied by F3**, not dropped and not built: no count was added, and neither of `render_md.py`'s anti-counting rulings was re-opened. | C1's premise was measured false — there are no existing skip counts for a new one to appear alongside — and counting in that region is argued against twice in the file it would have touched (`:1031-1034`, `:871-874`), with the WHY at `render_md.md:493`. Its intent is met by F3's bullet. The owner chose *satisfied* over *withdrawn* because the capability was delivered, by a different mechanism than the criterion imagined; a close-out reading "dropped" would understate what shipped. T3.4's own undercount, found in review and fixed in `6c176ef`, is evidence those rulings are right: a singular count in that bullet contradicted the suppression block's correct plural one in the same document. |
| 2026-10-02 | PRD F3 (6th criterion), T3.4 | The shared collision sentence stays as it is, and F3's sixth criterion is scoped in the PRD to the **three string classes** T3.1 decides — not the fourth criterion's run-local collision. T3.4 therefore renders one new bullet shape, not two. | T3.4's step 2 carried a genuine open question: a typed name that is usable but collides is reported with a sentence that names no provenance (`render_actions.py:953`), so under a broad reading of the sixth criterion the document never records that *the typed name* could not be used. Measured: the skipped entry carries no provenance field at all, so honouring the broad reading meant either forking a sentence the owner reviewed on 2026-09-28 or adding a second reader-less field one week after `kind`'s reader-less field had to be argued for. The owner chose the narrow reading, and it is recorded beside the criterion rather than only in this table — the criterion is where the next reader will look. |
| 2026-10-02 | T3.3 | T3.3's production change is measured to be a **no-op** — the exclusion is a single equality at `render_actions.py:1569`, not a list, so a new kind is never excluded by construction. Criteria 1 and 2 were already green before the task opened; criterion 3's mutation was executed in a worktree and is recorded in the task text. The task is re-scoped to its one remaining deliverable: a test **named** for the holds-the-note guarantee. | The plan assumed an exclusion list and an edit to it. Neither exists. Ticking the task on existing evidence would have skipped criterion 3, which says "**Run it.**" — and running it surfaced the thing the plan could not see: the guard fires, but from inside a test named for the suppression *sentence*, so it is unfindable by name and a future narrowing edit would remove a data-loss guard silently. The same failure mode as spec 031's disarmed `kind` guard, one layer over. |
| 2026-10-01 | ADR-6, T3.2, T3.3, T3.4 | The new `skipped_assets` kind is named **`typed_name_refused`** in ADR-6, and the literal replaces "the new kind" in all six places across T3.2, T3.3 and T3.4. | The SDD said only "a new `kind`" and named it nowhere, while three tasks depend on the same string: T3.2 emits it, T3.3 asserts it is absent from `suppress_moves_for_unfiled_attachments`'s exclusion list, and T3.4 branches on it to render a bullet. Left to T3.2's implementer, the name would reach T3.3 and T3.4 through two review cycles and a reviewer's memory — and a mismatch there fails silently in the direction that matters, since T3.3's assertion is that the kind is **not** in a list, which a misspelled kind also satisfies. The name follows the existing kinds' shape and keeps ADR-6's own word, *refused*; the `typed_` prefix carries the 2026-10-01 provenance ruling, that a computed name is never checked. |
| 2026-10-01 | T2.1 | `attachment_conflicts[].same_file` is typed `["boolean", "null"]` rather than the bare `boolean` the dispatch brief specified. | The brief was wrong and the implementer checked the source instead of following it. `_same_file` (`tomo/scripts/suggestions-reducer.py:484`) is declared `bool | None` and its docstring names both null paths: no `content_reader` returns `None` without attempting a read, and a read that raises on either side also returns `None` — "a missing comparison CAPABILITY is not evidence either way". A bare `boolean` would have made the producer's own output fail its own schema the first time a conflict was detected without Kado read access: the "half-finished move ships quietly" failure this task exists to prevent, one field over. Recorded because the error was mine, in a brief that told the implementer to trust its measured values over their own first reading — the one instruction that could have suppressed the catch. |
| 2026-10-01 | T2.5 | The success criterion "verify the wire gate's classification is `ACTION_MOVE_VERSION` + `ACTION_HANDOVER`" is **unreachable** once T2.1 is complete, and is replaced by a scratch-copy reproduction plus a hand-recorded Phase 5 obligation. CON-2's mechanism is restated, and the Phase 5 handoff gains the three divergent descriptions. | Measured across all three states on a scratch copy of `tomo/schemas/`: property added with the version held back yields `['move_version', 'handover']`; version moved with a stale manifest yields `['regenerate_manifest']`; version moved and manifest regenerated yields `passed=True, actions=[]`. The demanded verdict therefore exists **only** in the half-finished state, so an implementer satisfying the criterion literally would have to leave the move incomplete — precisely the CON-2 failure the phase exists to prevent. Separately, spec 035's ADR-5 already removed the hard-coded literal from both ends (`suggestions-render.py:507` emits and `suggestion-parser.py:270` reads via `wire_schema_version`), so emitter and reader cannot diverge and the silent fallback cannot originate in code — what survives is a stale wire file on disk and fixtures pinning the old version, which is why T2.5's live proof must regenerate the run *after* the move. Finally, `snapshot_parity_delta` compares structure only and ignores `description`: the live-vs-vendored delta reads `[]` today while `candidate_mocs[].selected`, `candidate_mocs[].anchor` (Phase 1's own markings) and `proposed_mocs[].tags` all differ, invisible to the entire suite. |

### A standing warning carried forward from spec 037

Spec 037 produced **nine** instances of a named mutation that could not bite — a
test asserting something already true, or a claim about which test catches which
fault that nobody had run. Three of those survived two reviews and propagated into
plan text, docstrings and WHY docs.

So on this spec: **a claim about which test catches which fault is a measurable
claim.** Run the mutation before writing it down, and re-run any such claim a
reviewer or implementer reports. This is cheap and it is the single highest-yield
check available here.

## Metadata Reference

- `[parallel: true]` — tasks that can run concurrently
- `[ref: document/section; lines: N-M]` — links to specifications
- `[activity: type]` — activity hint for specialist selection

---

## Context Priming

*GATE: Read all files in this section before starting any implementation.*

**Specification**:

- `docs/XDD/specs/038-every-editable-decision-reaches-the-wire/requirements.md` — the PRD, 38 acceptance criteria across F1–F4, S1, C1–C2
- `docs/XDD/specs/038-every-editable-decision-reaches-the-wire/solution.md` — the SDD, 8 confirmed ADRs, 13 components
- `docs/XDD/specs/038-every-editable-decision-reaches-the-wire/README.md` — the decisions log; nine owner rulings, none to be re-derived
- `docs/XDD/backlog.md` — the originating entry, and the 2026-09-30 embed finding this spec must not contradict

**Key Design Decisions**:

- **ADR-1** — 037's ADR-5 is superseded. The suggestions wire moves `2` → `3`, and the move is a functioning gate, not bookkeeping: a mismatch makes Pass 2 fall back to the markdown **silently**.
- **ADR-2** — The conflict is a **top-level** `attachment_conflicts[]` array. Nesting it per suggestion reopens the multi-owner divergence 037 closed.
- **ADR-4** — The markdown keeps its inline shape; the parser trusts the backtick text unconditionally. An untouched document is byte-identical.
- **ADR-5** — A typed name is **rejected**, never sanitised. `sanitize_stem` is not reused on this path, and the check is its own module so one rule serves both read paths.
- **ADR-6** — A refused name **holds** the owning note, unlike `keep_in_inbox`. The owner asked to rename and we refused; that is `collision`-shaped, not choice-shaped.
- **ADR-7** — The inventory is hand-written, guarded by a join test in **both** directions.

**Implementation Context**:

```bash
# Tests (host; never inside the container)
./venv/bin/python -m pytest tests/ -q

# Lint
./venv/bin/python -m ruff check tomo/scripts/

# A single phase's tests
./venv/bin/python -m pytest tests/test_038_*.py -q
```

**Standing constraints for every task** — these are not advisory:

- **Never** `git stash`, `git reset --hard`, `git add -A`, or `git checkout --`.
  No `CLAUDE_ALLOW_DESTRUCTIVE_*` variables. Use `git worktree` for RED evidence
  and remove it with `rm -rf` plus `git worktree prune`; `--force` is blocked here.
- **`tomo-privat` is a LIVE environment — never touch it.** Any live work is
  `--instance tomo-instance`.
- Do **not** run `/capture-insight`, and do **not** write into any Obsidian vault.
- `/Volumes/Moon/Coding/MiYo/Hashi` is **read-only**. Never edit anything there.
- Bump `# version: X.Y.Z` on every edited file under `tomo/scripts/`.
- Write the `docs/tomo/<mirrored-path>.md` WHY entry **as you go**. A task was
  failed in spec 037 for omitting them.
- Commit messages end with the session's attribution lines.

---

## Implementation Phases

Each phase is defined in a separate file. Tasks follow red-green-refactor:
**Prime** (understand context), **Test** (red), **Implement** (green),
**Validate** (refactor + verify).

- [x] [Phase 1: The inventory, and what it reveals](phase-1.md)
- [x] [Phase 2: The wire carries the decision](phase-2.md)
- [x] [Phase 3: Refusal, before anything can be typed](phase-3.md)
- [ ] [Phase 4: The name becomes a value](phase-4.md)
- [ ] [Phase 5: Integration, the live path, and one handoff](phase-5.md)

### Why this order, and one thing it deliberately inverts

**The inventory is built first, though the owner ruled it ships last.** Those are
different decisions and both hold. The owner's ruling was about *delivery* — one
coordinated release, no partial handoff. Build order is free, and the consumer's
argument for going early was sound on its own terms: *"its value is the rows
neither of us knows about."*

Building it in Phase 1 collects that value without shipping early. The schema
already marks **23** fields `Editable` while the parser recognises 34 distinct
`parser_label` literals across its 24 decisions, so the join test is expected to
fail on its first run — and what it reveals may change the scope of Phases 2–4.
Finding that out first is strictly better than finding it out last.

**Phase 3 precedes Phase 4** — refusal lands before anything can type a bad name.
The check is a pure function on a string, so it is fully testable before the
markdown can produce a typed name, and this ordering means no commit on the branch
ever has an unguarded owner-typed string reaching a destination.

**Dependencies**: Phase 1 is independent of everything. Phase 2 → Phase 4 (the
wire must carry `proposed_name` before both surfaces can be proven to converge).
Phase 3 → Phase 4 (the guard exists before the input does). Phase 5 depends on all.

---

## Plan Verification

| Criterion | Status |
|-----------|--------|
| A developer can follow this plan without additional clarification | ⬜ |
| Every task produces a verifiable deliverable | ⬜ |
| All PRD acceptance criteria map to specific tasks | ⬜ |
| All SDD components have implementation tasks | ⬜ |
| Dependencies are explicit with no circular references | ⬜ |
| Parallel opportunities are marked with `[parallel: true]` | ⬜ |
| Each task has specification references `[ref: ...]` | ⬜ |
| Project commands in Context Priming are accurate | ⬜ |
| All phase files exist and are linked from this manifest | ⬜ |
