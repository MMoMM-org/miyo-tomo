# Specification: 034-recursive-inbox-discovery

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-05 |
| **Current Phase** | Ready |
| **Last Updated** | 2026-09-06 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | 10 features (8 Must, 1 Should, 1 Could), 40 acceptance criteria, 9 business rules, 12 edge cases, 0 open questions |
| solution.md | completed | 6 ADRs (4 user-confirmed, 2 corollaries), 7 constraints, traced walkthrough of the destination guard, 7 implementation gotchas |
| plan/ | completed | 6 phases, 29 tasks, 5 parallel, 101 spec references |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-05 | **Scoped as a feature (recursive discovery), not as an enabler (path-derived item key)** | The path-safe item key is the necessary enabler, but shipping it alone would repeat the failure spec 031 recorded on this same date: five phases built against a field nothing populated, every task passing both review gates because each correctly implemented its own local contract. An enabler with no consumer cannot be live-validated. Framing the spec around the user-visible behaviour gives the key rework something that exercises it. |
| 2026-09-05 | **Agent Team mode for research** | The question crosses the analyst contract, fan-out cost, parser reconciliation, and the first run over a long-ignored subfolder backlog — perspectives that can contradict each other and are better reconciled between researchers than after the fact. |
| 2026-09-06 | **Item key becomes path-derived AND the field is renamed** | No schema change is strictly required — `stem` is an unconstrained `{"type": "string", "minLength": 1}` in every schema that carries it, so a path-derived value validates today. The rename is chosen anyway: a field named `stem` holding `places__dresden` misleads every future reader, and two separate defects this week (#162's dead renderer, #165's unreachable branch) cost time precisely because a name no longer matched reality. Cost accepted: a schema-version bump across `item-result`, `state-entry`, `suggestions-doc`, `suggestions-wire`, `routing-plan`, plus `validate-result.py`'s `REQUIRED_TOP` and the analyst's written contract. |
| 2026-09-06 | **No volume cap — measure instead** | The unbounded-batch behaviour already exists today for a flat inbox with many untriaged files; recursion does not create it, it makes a hidden backlog visible. Adding a cap would be new user-facing behaviour justified by no measurement: the largest clean run on record is 21 items at ~$0.61/item, and nothing above that has ever been exercised. The spec logs items and cost per run instead, so a future cap can be set from data rather than from a guess. |
| 2026-09-06 | **All subfolders discovered, no exclusion mechanism** | No inbox exclusion mechanism exists today (`garden-audit-exclusions.yaml` is bound to `/garden-audit` only, zero references in `inbox-triage.py`), so building one is net-new surface for a problem that does not exist yet: attachment folders hold no `.md` files. YAGNI. Revisit if a subfolder ever needs to be hidden from triage. |
| 2026-09-06 | **Hashi gets a handoff, not an ADR** | The wire contract does not change: `render_helpers._stem()` (`:12-18`) flattens every emitted `source_stem`/`target_stem` to a bare filename at the emission boundary (`render_actions.py:857,873,888`), so Tomo's internal key never crosses. But two same-stem items still produce indistinguishable values there, and Hashi joins on that field (`forceAtomicSync.ts:47`) and renders it as a note link (`DailyTab.ts:229`). That is a behavioural consequence in a sibling component, which Constitution L2 says must be made visible — a `_outbox/for-hashi/` handoff, not an ADR-gated redesign. |
| 2026-09-06 | **Correction: this is not a cross-repo contract change** | Recorded because it was asserted as one mid-research before being checked. The schema researcher read the schemas and marked Hashi's TypeScript consumer unverified; the orchestrator read the consumer and not the schemas. Each half alone supported a wrong conclusion — the consumer join looked like a contract dependency, the schema alone looked like a non-issue. Only the emission-boundary flattening, which neither had looked at, settles it. Lesson for the SDD: a boundary question needs the producer, the schema, and the consumer read together. |
| 2026-09-06 | **Refinement: the field is split, not merely renamed** | `stem` turned out to carry two jobs that only look like one because a flat folder makes a filename unique: it is the join key at every site in the blast-radius table, and it is **display text** — `suggestions-reducer.py:390,489` fall back to it for the note title, and `:395,397,494,546,604` render it as `**Source:** [[{stem}]]`. Putting a path-derived value in that one field would title a note `places__dresden` and emit `[[100_inbox_places_dresden]]` into the vault: a visible wrong mutation in the same severity class as the `mark-captured.py` risk, and harder to catch because nothing errors. So the decision to rename stands, but its correct form is two fields — a path-derived identifier for addressing, a bare filename for anything a person reads. PRD business rules 4, 5 and 8 encode this. |
| 2026-09-06 | **Correction: the Hashi join is on the Pass-1 suggestions wire, not the instructions schema** | Recorded because it was cited wrongly in this session before being checked. `forceAtomicSync.ts:31,47` and `SuggestionsTab.ts:180-181` join on `suggestions-wire.schema.json`'s `stem`/`source_stem`, reached from live handlers (`SuggestionsTab.ts:693`, `DailyTab.ts:313`) — not dead code. On the Pass-2 instruction path, `action.source_stem` has **zero** consumers in Hashi's `actions/` and `executor/` — inert. `target_stem` is the exception: `updateLogLink.ts:47-48` composes it into a literal `[[…]]` written into the daily note. The conclusion is unchanged, but the handoff must point at the wire builder, not `render_actions.py`'s emission — the earlier citation would have sent someone to the wrong file. |
| 2026-09-06 | **Correction: the user does not use inbox subfolders today** | The PRD asserted the opposite, taken from an earlier scoping answer. Corrected on review. The justification changes from "this is broken for me now" to "the documents describe it, the tool silently cannot do it, and I want the freedom" — and the defect stands either way, since a note placed in a subfolder disappears without a word. Favourable consequence: there is no hidden backlog, so the first recursive run is uneventful and the no-volume-cap decision carries less risk than when this was unknown. The backlog risk row was downgraded from Medium to Low accordingly. |
| 2026-09-06 | **Source links are path-qualified only when two items collide** | A bare `[[Dresden]]` is not merely terse when two Dresdens exist — it is unusable. Obsidian resolves by name, so clicking or hovering either of two identical links opens whichever it picks, and the two suggestions look identical in the document, so the user cannot tell them apart at all. Adding the path everywhere would fix that at the cost of noise in every run of a document read daily. Conditional qualification keeps the common case clean; the renderer already sees every item, so it can detect the collision. This revises business rule 5, which as first written would have mandated exactly the unusable form. |
| 2026-09-06 | **Destination collisions are resolved in Pass 1 through the suggested name** | The target folder is flat, so two notes named Dresden cannot both be filed there. Nothing checks this: `_dest_join` builds the destination from the title with no guard, and `_disambiguate_filename` only compares within one render run, not against the vault. Rather than a new mechanism, the user's own observation supplies the answer — the suggestions document already shows `**Suggested name:**` and the user already edits it to change the destination. So Tomo proposes a distinct name on collision and the user overrides it there if they want. This moves detection from Pass 2 (where the question was originally framed) to Pass 1, where the name is presented. Pre-existing defect — two root notes could already collide on title — but recursion makes it likely rather than theoretical, so it is in scope. |
| 2026-09-06 | **Cost figures are appended to a durable history in the instance, not to the repo log** | The pipeline runs in a container that cannot see `docs/`, so an acceptance criterion requiring it to write `docs/evolution/inbox-cost-log.md` was unimplementable — caught on review. Writing into the instance's persistent state solves both halves: the run records its own figures, and they accumulate into a history readable later from the host, instead of depending on someone remembering. Follows the existing pattern of `state/moc-squelch.json`, a small persistent registry already written there by `mark-captured.py`. Transcribing a notable run into the repository's cost log stays a deliberate host-side act. |
| 2026-09-06 | **A Pass-1 check is advisory; the binding guard belongs in Pass 2** | Raised by the user reviewing Feature 7: what happens if they edit two suggestions to the same name? Feature 7 as first written put the whole safeguard in Pass 1 — but the user's edit comes *after* that, so the guard sat on the wrong side of the input. Verified that nothing catches it today: `_disambiguate_filename` (`instruction-render.py:457`) protects only the intermediate rendered file, while `_dest_join` (`render_actions.py:550`) builds the destination from the title with no comparison at all. The clash survives both passes and surfaces as a failed rename at apply time, after approval. Feature 7 now has two halves — a Pass-1 proposal so the common case never reaches the guard, and a Pass-2 validation of what the user actually wrote. Generalised as business rule 8, because it applies to every future rule about what reaches the vault. |
| 2026-09-06 | **On a destination clash, neither note is filed** | Chosen over first-claim-wins, which is what the attachment guard from spec 031 does. The cases differ: skipping a duplicate attachment loses nothing, whereas skipping one of two approved notes leaves an approved item unfiled and lets ordering decide arbitrarily which. Between two things the user explicitly named the same, picking a winner is itself a guess — so both stop and the clash is reported, recoverable by fixing one name and re-running Pass 2. Extended to names that clash with a note already in the target folder, since from the user's side that is the same failure: the note is not where they think it is. |
| 2026-09-06 | **An attachment clash keeps its note in the inbox — reversing a spec 031 decision** | Raised by the user: two different `Dresden.jpg`, one in `Places/` and one in `Reisen/`, both wanting the flat asset folder. Spec 031's guard already detects this correctly (`seen` handles the same file embedded twice, `claimed` handles two different files sharing a basename) and skips the second with a report. But `plan/phase-2.md:85` also required that a collision **not** suppress the note's own `move_note` — so the second note would be filed to Atlas while its image stayed in the inbox. That is precisely the residue spec 031 exists to eliminate, and the moved note's bare embed may then resolve to the other file of that name (unverified — Obsidian's resolution of an ambiguous bare name was not checked, and the note-without-its-image outcome decides it regardless). The old decision was correct while collisions were unreachable, which a flat inbox guaranteed; recursion makes them reachable. Now: an attachment clash suppresses that note's move too, so note and image stay together. `tests/test_031_t2_4_destination_collision_guard.py:121` asserts the old behaviour and must be inverted — named in the PRD so a red test is read as the intended change, not a regression. Context on the mechanism, corrected 2026-09-06 after the first wording was loose: moving a file rewrites the links that **point at** it, across the vault. It does not move anything else — a note's attachments never travel with it, and nothing moves that was not explicitly instructed. That is why the attachment needs its own action at all, and why an unfiled attachment stays unfiled indefinitely. The claim in this row that a moved note might resolve to the other file of that name was subsequently withdrawn — see the row below. |
| 2026-09-06 | **Withdrawn: the "moved note shows the wrong image" risk** | Raised by the user and checked against a real note in the test vault. When two files share a basename, Obsidian writes the link path-qualified with a display alias — `100 Inbox/DoubleTest.md` contains `[[100 Inbox/Images/Test\|Test]]` and `[[100 Inbox/assets/Test\|Test]]`, not a bare name. Confirmed the resolver handles exactly that form: `_strip_alias_and_anchor` drops the alias and keeps the path, and both links resolve to their own file, while a bare `Test.png` correctly reports `ambiguous`. So the input side was already safe, and an argument used in Feature 8's rationale — that a filed note might then display the other file of that name — is wrong and has been removed. Feature 8 stands on the ground actually chosen: a note in the permanent collection must not depend on a file left in the inbox. Recorded because the withdrawn argument was the more alarming of the two, and a reader who only remembers the alarm would mis-scope the fix. |
| 2026-09-06 | **Correction: nothing moves that was not instructed, and notes do not carry their attachments** | The user corrected a loose phrasing of mine ("a moved attachment takes its embeds with it"), which invites the wrong model. What actually happens: moving a file rewrites every link *pointing at* it; nothing else moves. Moving `DoubleTest` to Atlas leaves its embeds exactly as written — they are absolute vault paths and stay valid — and only moving the target file itself would rewrite them. Every move in this pipeline is an explicit instruction; the executor moves nothing on its own initiative. This matters twice: it is why an attachment needs its own action rather than riding along with its note, and it is why an unfiled attachment stays unfiled indefinitely, which is the whole basis of Feature 8. Also caught here: the withdrawn "wrong picture" argument was still standing in Feature 8's user story after being removed from its rationale — the same fix-one-site-miss-another pattern this repo has hit before. |
| 2026-09-06 | **ADR-2 refined during design: add `item_key`, keep `stem` honest** | The PRD decision was to rename the field. While drafting the SDD a cheaper form of the same intent appeared: add `item_key` for the path and let `stem` go back to meaning exactly what its name says — a bare filename, which is what its 16 display sites actually need. No field ends up holding something its name does not describe, and the rename sweep across five schemas, `validate-result.py` and the analyst contract is avoided. Confirmed by the user 2026-09-06. |
| 2026-09-06 | **ADR-5: the per-item filename is a readable stem plus a digest of the exact key** | Corollary of ADR-1 under a verified constraint: this filesystem is case-insensitive, so `Places/Dresden.md` and `places/dresden.md` would produce one file from a readable-only name — re-creating the very collision the spec removes. `sanitize_stem` cannot be used either; it is lossy by design and maps distinct paths onto one name. A pure digest would be unreadable in a pipeline whose intermediate state is read by hand, so the name carries both: a readable half to identify the item, a digest to guarantee distinctness. |
| 2026-09-06 | **Correction during SDD drafting: `stem` is display text at 16 sites, not 8** | A first draft of the implementation gotchas said eight. The real figure is 16 — six title fallbacks, six source links, four rendered headings. An implementer working from the wrong number would have fixed half of them and written item keys into vault-visible text at the rest. Corrected, and reframed: the gotcha now tells the reader to enumerate the sites themselves, because a count in a document goes stale while the instruction to grep does not. |
| 2026-09-06 | **Phase order is driven by one rule: recursion must not ship before the key is threaded** | Making `discover_files` recursive is a two-line change and the most dangerous one in the plan if taken first — the moment subfolder notes become items, two can share a filename, and every stem-keyed site starts merging distinct notes, including the one that writes to the vault. Phases 1 and 2 therefore land the identity with no user-visible change at all, and Phase 3 turns on the behaviour that needs it. Phase 2 ends with an end-to-end trace of the key through every artefact boundary rather than per-stage unit tests, because per-stage green is exactly what let spec 031 build five phases against a field nothing populated. Phases 3 and 4 touch different files and can run in parallel. |
| 2026-09-06 | **Phase 1 closes with 7 known-red tests, carried as Phase 2's worklist** | Phase 1's own gate asks for a green suite AND an inert phase, and those cannot both hold: T1.2 makes `item_key` a required field in five schemas while the producers that build those payloads do not emit it until Phase 2. Verified that no fixture edit can close them — the validated object is constructed in production code (`suggestions-reducer.py:1932` `sections.append`, `inbox-triage.py`'s `force_atomic_items` builder, `suggestions-render.py`'s `_wire_note`), reached through `_run_pipeline` / `_run_reducer` / `build_wire_payload`. Three options were weighed: declare `item_key` optional now and flip it to required in Phase 2 (green at every boundary, but contradicts the plan's explicit "required, not optional", weakens T1.3's guarantee for a phase, and edits five schemas twice); pull the three producer wirings forward (green today, but duplicates Phase 2 tasks T2.1/T2.3, performs that work outside their TDD structure, and breaks the inertness the sequencing rule depends on); or carry the 7 as an enumerated known-red set. The third was chosen: the failures are precisely the work Phase 2 already owns, and T2.8 ("prove the key is carried end to end") is the gate that closes them. The exact list is pinned below so any NEW failure during Phase 2 is visible immediately rather than hiding in a red suite. Phase 2 may not pass its gate until all 7 are green. |
| 2026-09-06 | **Plan gap closed: `suggestions-render.py` gains task T2.3b** | Found at the Phase 2 boundary. `suggestions-render.py` is a live pipeline stage — invoked from `suggest-handling/SKILL.md:108` and `force-atomic-handling/SKILL.md:92` — and its `_wire_note` (`:277`) / `build_wire_payload` (`:314`) produce `suggestions-wire.json`, which T1.2 made require `item_key`. The file appears in no SDD directory-map row and in no phase task. This is not cosmetic: T2.8's gate requires tracing the key "routing plan → per-item result → suggestions doc → **wire** → parsed suggestions", and the wire is produced by exactly this unassigned file, so as written Phase 2 could not pass its own gate and three of the seven known-red tests would never go green. Only one reading is sound — the file must change in Phase 2 — so the task was added rather than stalling the phase for a decision with no alternative. T2.3b is scoped to projecting `item_key` in `_wire_note` and nothing else; CON-4 still holds, since `stem` remains the bare filename Hashi joins on. |
| 2026-09-06 | **T2.1 leaves a placeholder `item_key` on `force_atomic_items`; T4.1 must close it** | The FAN checkbox carries a bare `stem` via `Source: [[stem]]` and no full path, so at `_extract_fan_items` (`inbox-triage.py:589`) and `_extract_fan_items_from_wire` (`:693`) the item's real path is simply not available yet — making it available is T4.1's job ("carry the item's path through the routing plan into the dispatch"). The schema requires `item_key`, so the field could not be omitted; T2.1 set it to the review document's path. That is a field holding something its name does not describe, which ADR-2 exists to prevent, and it means two FAN items in one document share one key. Verified the risk is latent, not live: `force_atomic_items` is consumed only by `force-atomic-handling/SKILL.md`, which iterates and dispatches — nothing joins on `item_key` there. Accepted as an intermediate rather than blocking Phase 2, because no alternative value exists at that call site. Recorded here and as an explicit obligation in T4.1 because this is exactly the shape of the spec 031 failure the plan warns about: a schema-valid placeholder that passes every review gate since each task correctly implements its own local contract. |
| 2026-09-06 | **Second plan gap closed: the duplicated state replay in `suggestions-reducer.py`** | Found by T2.4's implementer, which was asked to name any other consumer of `inbox-state.jsonl` still joining on the bare stem. `last_state_per_stem` turns out to be duplicated in two scripts — `suggestions-reducer.py:78` (called `:1652`) and `mark-captured.py:44` (called `:108`) — both replaying with `out[stem] = obj`, last-wins per filename. T2.4 keyed `state-update.py`'s writer and reader on `item_key`; T2.5 owns `mark-captured.py`; **no task named the reducer's copy**. Phase 2 references `suggestions-reducer.py` only for the per-item result-file read (T2.3) and Phase 5 for its display sites, so the state join fell between them. Left unfixed, Phase 3 would let one item's `done`/`failed` status mask its namesake's and drop that item from the work list silently — PRD Feature 2's exact failure. Assigned to T2.3, and deliberately as a **single extracted helper in `lib/` rather than two in-place patches**: two divergent copies of one identity computation is how #165 happened, and the SDD already warns that both parser derivation paths must share one function for the same reason. T2.5 now depends on T2.3 and consumes the same helper. |

### Phase 1 known-red tests (must be green before Phase 2 passes its gate)

Pinned 2026-09-06 at the Phase 1 boundary. These fail because `item_key` is required by the
schemas but not yet emitted by the producers; Phase 2 tasks T2.1 and T2.3 close them. Any
failure outside this list during Phase 2 is a regression, not inherited state.

```
tests/integration/test_018_pipeline.py::TestFanResolveActionFromForceAtomic::test_approved_with_fan_items_no_fan_doc_produce_fan_resolve
tests/integration/test_018_pipeline.py::TestRoutingPlanAllFieldsValid::test_full_routing_plan_validates
tests/test_031_phase5_attachments_preamble.py::test_end_to_end_doc_validates_against_suggestions_doc_schema
tests/test_031_t3_3_attachments_wire_projection.py::test_build_wire_payload_carries_attachments_and_validates
tests/test_suggestions_reducer_multi_atomic.py::test_t1_schema_validation_with_suggestion_id_field
tests/test_suggestions_wire_emit.py::test_wire_conforms_to_schema
tests/test_suggestions_wire_emit.py::test_fan_doc_wire_conforms_to_schema
```

Baseline at this boundary: **3287 passed, 7 failed, 1 skipped**, ruff clean.


## Context

Closes #163 and #164.

**The two halves of the inbox disagree about what it contains.** `discover_files`
(`tomo/scripts/inbox-triage.py:172`) calls `list_dir(inbox_path, depth=1)`, so only
inbox-root notes become sources. `resolve_inbox_attachments`, added by spec 031, uses
`list_notes(inbox_path, fields=["links"])`, which is recursive. A note in
`100 Inbox/Places/` therefore has its attachments resolved and is then never triaged —
the work is computed and discarded (#164).

Marcus confirmed on 2026-09-05 that he does put notes in inbox subfolders, so the
documents are right and the pipeline is too narrow. Spec 031's AC-F2.1 and SDD
walkthrough both use `100 Inbox/Places/Dresden.md` as a source note (#163).

**The blocker is the item key, not the depth.** `_stem_of`
(`tomo/scripts/suggestion-parser.py:1971`) is `src.rsplit("/", 1)[-1]`, `.md` stripped,
lowercased — the path is discarded. A flat inbox is a single namespace, so stems are
unique today by accident of layout rather than by construction. Recursing makes
`100 Inbox/Places/Dresden.md` and `100 Inbox/Reise/Dresden.md` the same key.

Consequences, worst first:

1. **The fan-out overwrites its own results.** Each analyst subagent writes
   `tomo-tmp/items/<stem>.result.json` (`inbox-analyst.md:37`, read back at
   `suggestions-reducer.py:1776`). Two same-stem notes means two subagents writing the
   same path in parallel — one silently clobbers the other. No error, no warning.
2. **Force-atomic and fan reconciliation collide.** `sections_by_stem`,
   `resolve_sections_by_stem`, `already_in`, `seen_pending`, `_stem_to_id` are all
   stem-keyed (21 sites in `suggestion-parser.py`). Same area as the livelock fixed in
   #165.
3. **Audio/transcript sibling matching** pairs by stem and would widen across folders.

The item key must become path-derived and threaded through the fan-out contract, the
per-item result filenames, the reducer, the parser's reconciliation, and the wire. The
analyst's written contract changes, so this is not purely deterministic-side work.

**Open questions for the PRD to settle**, not assumed here:

- What happens the first time a long-ignored subfolder backlog is triaged in one run.
  None of those notes carry `tomo.state`, so they all arrive as `new_sources` at once.
- Whether every subfolder is in scope, or whether some are structurally excluded
  (attachment folders such as `Images/`, `Scans/`, `assets/` hold no notes today, but
  an archive subfolder would be a different matter).
- How the standing "near MVP, additive only" constraint applies to an internal key
  change that is not additive.

---
*This file is managed by the xdd-meta skill.*

## Research findings (2026-09-06)

Four researchers: requirements, technical, performance, contracts. Every claim below was
re-verified against the source by the orchestrator before being recorded; anything that
could not be settled is marked **unverified** rather than smoothed over.

### Two independent blockers, not one

**B1 — the item key is a bare stem.** `_stem_of` (`suggestion-parser.py:1971`) is
`src.rsplit("/", 1)[-1]`, `.md` stripped, lowercased. A flat inbox makes stems unique by
accident of layout, not by construction.

**B2 — force-atomic reconstructs the note path from the stem.** A STRICT block in
`tomo/dot_claude/skills/force-atomic-handling/SKILL.md:55-60` mandates
`path = <inbox_path>/<stem>.md`. For `100 Inbox/Places/Dresden.md` that yields
`100 Inbox/Dresden.md`, which does not exist. **This breaks for a single subfolder note
with no name collision at all** — B2 is not a special case of B1. The STRICT block exists
because `source_path` there is the suggestions document, not the note; the stem was the
escape hatch, and it only works on a flat inbox.

### Blast radius of B1

| Site | What is keyed | Consequence of a collision |
|---|---|---|
| `suggestion-parser.py:1971` `_stem_of` | key derivation | root cause; all sites below inherit it |
| `suggestion-parser.py` × ~20 | `sections_by_stem`, `resolve_sections_by_stem`, `already_in`, `seen_pending`, `_stem_to_id` | two notes merge into one bucket; Force-Atomic promotes the wrong one; a MOC binds to the wrong source |
| `suggestions-reducer.py:1638→1715` | `items_dir / f"{stem}.result.json"` — a **filename** | two analyst subagents write the same path in parallel; one silently clobbers the other |
| `state-update.py:39,52,76,82` | `inbox-state.jsonl`, append-only, joined on `stem` | "last line wins" hides one item's real status |
| `mark-captured.py:44-49` → `:161` | `state[entry["stem"]] = entry`, then `client.write_frontmatter(...)` | **writes `tomo.state: captured` onto the wrong note in the vault** — the only consequence that mutates user data |
| `instructions-diff.py:105-111,281,397` | a locally duplicated `_stem()`, both sides of the coverage audit | both sides collapse identically, so the audit reports false *full coverage* rather than a mismatch |
| `inbox-triage.py:526-541` `check_audio` | `md_stems`, a flat set with no path component | an audio file is judged already-transcribed because an unrelated note elsewhere shares its stem |
| `validate-result.py:29` `REQUIRED_TOP` | validates `stem` present | second enforcement point for the same contract |

`mark-captured.py` is the one the key design must make impossible by construction, not
merely unlikely — everything else corrupts bookkeeping, that one corrupts the vault.

### Recursion is cheaper on discovery, not dearer

A recursive `list_dir` over the inbox **already runs in every pass**:
`build_attachment_index` (`inbox-triage.py:200-217`) calls `client.list_dir(inbox_path)`
with no depth, one call per run. `build_inbox_index`
(`lib/attachment_index.py:41-61`) consumes the same `[{path, type}]` shape that
`discover_files` partitions, so one listing could feed both — base Kado calls **3 → 2**.

Traced safe across every consumer of `discover_files`' output (`compute_new_sources`,
`check_audio`, `resolve_handlers`, `TriageState`). One thing to reconcile first: the two
file-type filters differ — `discover_files:178` is `(item.get("type") or "").lower()`
(case-insensitive, None-safe), `attachment_index.py:53` is exact-match. Kado emits
lowercase literals (`Kado/src/obsidian/search-adapter.ts:194,247`), so this is latent
robustness, not a live bug — but pick one filter before sharing a listing.

*Unverified:* whether the tag-handler registry's own matching makes any path-prefix
assumption. `resolve_handlers` matches on frontmatter, so this is low-risk, not confirmed.

### Cost

`_count_kado_calls` (`inbox-triage.py:1738-1778`) = 3 base + 7 byFrontmatter + per-item
reads. The `kado_calls=20` figure for spec 031's 4-item run is consistent with it.

The counter is **script-level only** — an analyst subagent's own `kado-read` (one per item,
`inbox-analyst.md:69`) is made over MCP by a different agent and is invisible to it. What
scales with recursion is fan-out, not discovery: one `Agent()` dispatch per item, batched
`tomo.suggestions.parallel` (default 5) concurrently, batches sequential. Measured
**$0.59–0.67 per item**; largest clean run on record 21 items at $0.61/item.

### No cap anywhere

`_search_all` (`kado_client.py:583-619`) follows every cursor page and merges them into one
unbounded in-memory list; `limit` is page size only. `determine_action` has no size branch.
`suggestions-render.py` has no size guard. The only throttle in the pipeline is
`tomo.suggestions.parallel`, which limits concurrency, not volume.

The eager merge is a consumer-side memory risk. It is **not** a Constitution L1 violation —
that rule binds the component *producing* a large result set, and Kado paginates correctly;
Tomo's client flattens it for its own convenience.

### Hashi

The Pass-2 instruction path never sees the internal key: `render_helpers._stem()`
(`:12-18`) flattens every emitted `source_stem`/`target_stem` to a bare filename at the
emission boundary (`render_actions.py:857,873,888`). On that path `source_stem` has zero
consumers in Hashi; `target_stem` is used, composed into a literal `[[…]]` line written
into the daily note (`updateLogLink.ts:47-48`).

The live join is elsewhere — on the **Pass-1 suggestions wire**
(`tomo/schemas/suggestions-wire.schema.json`). `forceAtomicSync.ts:31,47` matches
`suggestion.stem === stem` and `entry.source_stem === stem`, and `SuggestionsTab.ts:180-181`
keys a second Map on `source_stem`; both are reached from real handlers
(`SuggestionsTab.ts:693`, `DailyTab.ts:313`). The wire's daily-log entries carry no id and
no suggestion id, so that string genuinely is the only link, as the file's own comment says.
Stems are also rendered as clickable links resolved through Obsidian
(`openNote.ts:24-25`), whose own comment already records bare-name ambiguity as an accepted
limitation of the current version.

So: no schema change, no contract change — but two same-stem items produce indistinguishable
values on that wire, widening a limitation the sibling component already knows it has. Hence
the handoff, aimed at the wire builder rather than the executor emission.
