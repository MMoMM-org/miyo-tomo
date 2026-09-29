---
title: "Phase 2: The decision in the document"
status: completed
version: "1.0"
phase: 2
---

# Phase 2: The decision in the document

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-4]` — rename pre-ticked, cleared means ignore
- `[ref: SDD/Interface Specifications; attachment_conflicts[]]`
- `[ref: PRD/F2]`, `[ref: PRD/S1]`, `[ref: PRD/S2]`, `[ref: PRD/C1]`
- `[ref: PRD/Detailed Feature Specifications; Business Rules 1-6]`

**Key Decisions**:
- Rename ships **ticked**. This reverses the repo's usual habit deliberately:
  a safe obvious answer exists, and charging attention for the common case is
  the cost this spec exists to avoid.
- A **cleared** default resolves to `ignore`, not to `keep_in_inbox`. Clearing
  the box is itself a signal that the owner wants to handle it, so the outcome
  is the loudest of the three, not the quietest.
- The parser resolves `remedy` fully — empty and contradictory entries become
  `ignore` here, so no downstream consumer re-derives it.
- The section is rendered only when non-empty. A run without conflicts must
  produce an unchanged document.

**Dependencies**: Phase 1 (conflicts must exist before they can be rendered).

---

## Named risk carried in from Phase 1 — read before designing the render

**A conflict entry's `owner_source_items` may name a note whose attachment is not the entry's
`source`.** Recorded 2026-09-22 from T1.2's compliance review; T1.2 itself is correct and passed.

`detect_attachment_conflicts` groups by case-folded **destination**. That is the right key — it is
what makes one attachment embedded by three notes a single conflict with three owners. But when two
*different* inbox attachments share a basename (`100 Inbox/A/karte.png` and `100 Inbox/B/karte.png`)
and the vault already holds that name, both land in the **same** entry: `source` keeps whichever
path was seen first, and `owner_source_items` accumulates the owners of both.

For detection this is harmless — the destination genuinely is occupied, which is all Phase 1 claims.
It stops being harmless here. If this phase renders `owner_source_items` as "the notes that embed
this file", and Phase 3 applies a rename with an embed rewrite, **the second file's owning note is
told its embed was retargeted to a file it never owned.** The user approves a remedy for one file
and a different note is modified.

The intra-run half of this is deliberately Pass 2's (`_build_move_asset_actions`' `claimed` dict,
`render_actions.py:761-774`), and that boundary stands — this is not a request to detect it here.
What this phase owes is that its rendering and its remedies cannot mislead when an entry carries
owners of more than one source. Decide it explicitly: render per-source rather than per-destination,
split the entry, or state why the shape cannot reach a user.

**Decided 2026-09-22 — in the data, not the display. This phase owes nothing further.**
The third option was checked and refuted rather than assumed: `_asset_dest_join`
(`render_actions.py:571-575`) builds the destination from the asset folder plus the source's
basename, and spec 034 shipped recursive inbox discovery, so two attachments sharing a filename in
different inbox subfolders genuinely reach one entry. The owner chose to fix the key rather than
teach the renderer a special case — **Phase 1 T1.5** groups by exact source path, keeping the
case-folded destination only as the occupancy test. An entry therefore describes exactly one file
by the time this phase reads it, and `owner_source_items` names only notes embedding that file.

## Tasks

Establishes the surface the owner reads and the tick the pipeline reads back.

- [x] **T2.1 The rename proposal is part of the data** `[activity: domain-modeling]`

  Added 2026-09-23. `SDD/Interface Specifications` lists `proposed_name` as a field of
  `attachment_conflicts[]` and `SDD/Open Questions` left its scheme undecided, noting it
  "does not block implementation" — which stopped being true the moment T2.2 was asked to
  render it. Nothing in Phases 1-4 computed it, and the schema's `additionalProperties:
  false` would have rejected it. **Owner decision 2026-09-23**: mirror the scheme already
  shipped for note clashes — `{stem} ({n}){ext}`, n from 2, first free name wins.

  It belongs in the reducer, not the renderer: `SDD/Runtime View, Pass 2` has Phase 3 move
  the file to `proposed_name`, so the parser would otherwise have to recover it from
  rendered prose.

  1. Prime: Read `resolve_destination_clashes`' candidate loop — `f"{title} ({n})"`,
     `range(2, 101)`, first free wins, and the recorded decision that 99 taken names is not
     a situation a rename can rescue `[ref: suggestions-reducer.py:~466-478]`. Read
     `_asset_dest_join` `[ref: render_actions.py:560-575]`: an attachment's basename
     survives verbatim, extension included, or the embed stops resolving.
  2. Test:
     - **The counter goes before the extension**: `karte.png` proposes
       `karte (2).png` `[ref: PRD/C1]`. Mutation: append after the basename —
       `karte.png (2)` — which is no longer a PNG and whose embed cannot resolve. This is
       the single difference from the note scheme, where `_dest_join` appends `.md` itself.
     - **The stem is everything before the LAST dot**: `karte.tar.gz` proposes
       `karte.tar (2).gz`, not `karte (2).tar.gz`. Mutation: split on the first dot —
       correct for single-suffix names, so only a multi-dot fixture separates the two.
     - **A name with no dot takes the suffix at the end**: `README` proposes `README (2)`.
       Mutation: index into a missing extension and raise, or emit `README (2).` with a
       trailing dot. **Covers the leading-dot case too** (code-quality review advisory, owner
       decision 2026-09-23): a basename whose only dot is the LEADING one — `.hidden` — is not
       an extension separator, it is part of the name, so `.hidden` must take the same "no
       dot" path and propose `.hidden (2)`. `str.rpartition(".")` on `.hidden` yields an empty
       stem (`"", ".", "hidden"`), so the implementation must treat an empty stem the same as
       no separator at all — otherwise the candidate reassembles as `" (2).hidden"`, a leading
       space, and a name that is no longer hidden.
     - **An occupied proposal advances**: with `karte.png` AND `karte (2).png` both in the
       vault, the proposal is `karte (3).png`. Mutation: always propose `(2)` without
       testing the listing.
     - **The occupancy check FOLDS CASE.** **Fixture corrected 2026-09-23** — the version
       first written here ("`Karte.png` in the vault, `karte.png` proposes `karte (2).png`")
       cannot test this at all: `karte (2).png` differs from `Karte.png` under *any*
       comparison, so it only re-proves T1.2's initial-destination fold. The fixture must
       occupy a case-variant of the **candidate**: with `Karte.png` AND `Karte (2).png` in
       the vault, `karte.png` proposes `karte (3).png`. Mutation: drop `.casefold()` from the
       candidate key. Note it is NOT isolated to this test — `ASSET_FOLDER` itself carries
       uppercase, so an unfolded join matches nothing and four tests fail. Recorded rather
       than claimed as a single kill.
     - **A candidate is checked against the FOLDER set too**, not only the file listing
       `[ref: spec 037 T1.4]`: if `karte (2).png` names an existing subfolder rather than a
       file, it is rejected like any other taken name and the search advances to
       `karte (3).png`. Mutation: gate the candidate on `asset_listing` alone — that
       reproduces exactly the defect T1.4 fixed for the initial destination, one level down
       in the rename candidate, and every other bullet here still passes.
     - **Two conflicts in ONE run get DIFFERENT proposals** — `(2)` and `(3)`, never the
       same. Mutation: derive each proposal from the vault listing alone, ignoring what this
       run has already proposed; both get `(2)` and the rename collides with itself, which
       is the defect T1.5 removed from ownership re-appearing in naming.
     - **After 99 taken variants `proposed_name` is `null`**, and the conflict is still
       emitted. Mirrors the note scheme's give-up branch. Mutation: emit the 100th candidate
       unchecked, or drop the conflict entirely — the occupancy is real either way and the
       owner still needs to see it.
     - **Schema**: `proposed_name` is required and typed `["string", "null"]`, matching how
       `same_file` was added in T1.3. Mutation: leave it out of `required` — every existing
       document still validates and the field silently becomes optional.
  3. Implement: compute `proposed_name` per conflict entry in the reducer. A candidate is
     free only when it is absent, case-folded, from ALL THREE of: the asset folder's file
     listing, the folder-occupancy set (T1.4), and the names this run has already proposed.
     Extend the schema.

     **Out of scope, stated so its absence is not read as an oversight**: a source whose
     basename already matches `{stem} ({n}){ext}` — `karte (2).png` colliding — proposes
     `karte (2) (2).png`. That quirk is inherited verbatim from
     `resolve_destination_clashes`, which does the same to note titles today. Mirroring
     shipped behaviour is the decision; changing it would be a new one, and not this task's.
  4. Validate: full suite; `ruff`; the T1.2-T1.5 suites stay green — a new required field
     changes every conflict entry's exact-dict assertions, so report each edited assertion
     as `<test name>: field added, no other change`
  5. Success: PRD C1's first criterion has a named test `[ref: PRD/C1]`; a rename candidate
     is tested against everything the initial destination is tested against, so T1.4's fix
     is not undone one level down; the scheme matches
     `resolve_destination_clashes`' so the repo has one rename convention, not two; the
     second C1 criterion (the proposal itself occupied at Pass 2) stays Phase 3's
     `[ref: SDD/Runtime View, Pass 2]`

- [x] **T2.2 The conflict renders as a decision with three remedies** `[activity: frontend-ui]`

  1. Prime: Read `render_tag_handler_updates_block` and `render_daily_notes_updates_block`
     — both return `""` when empty so the caller omits the section — and their consumers in
     `tomo/scripts/suggestions-render.py`, which read the `rendered_*_md` field verbatim.
     That is the precedent: the reducer renders markdown into a doc field, the render script
     places it. Read `render_attachments_preamble` for the document's attachment voice.
  2. Test — **every bullet names the mutation it kills; T2.2 as first written named none:**
     - **The positive and negative cases are ONE red/green pair, not two bullets.** One
       conflict renders a section naming source, destination and every owning note
       `[ref: PRD/F2-AC1]`; zero conflicts render **no section at all** `[ref: PRD/F2-AC4]`.
       Mutation: a stub that unconditionally returns `""` must fail the first; a stub that
       unconditionally emits the header must fail the second. **Alone, the zero-conflict
       assertion is true of today's code** — nothing renders this section yet — so it proves
       nothing unless the positive case is asserted beside it.
     - **Exactly three remedies — rename, keep in inbox, ignore — with rename ticked**
       `[ref: PRD/F2-AC2]` `[ref: SDD/ADR-4]`. Mutation: render two remedies, or tick none.
     - **One entry per CONFLICT, not per owner** `[ref: PRD/F2-AC3]`. The reducer already
       dedups (T1.2, re-keyed in T1.5), so a renderer that emits one block per array element
       passes trivially — the fixture did the work, not the code. Mutation: iterate
       `owner_source_items` and emit one decision block per owner. The test must use an entry
       with THREE owners and assert one block carrying three names, not three blocks.
     - **The rename remedy names the FULLY COMPOSED destination** `[ref: PRD/C1]`:
       `proposed_name` is a basename, the folder comes from `destination`. Mutation: render
       `proposed_name` alone — a substring assertion on the basename passes while the owner
       is shown a name with no folder.
     - **`proposed_name: null` pre-ticks *keep in inbox*, not rename** `[ref: SDD/ADR-4,
       exception]`. The rename line still renders, unticked, saying no free name was found.
       Mutation: keep rename ticked — the owner accepts a rename that cannot happen; or drop
       the rename line entirely — the owner cannot see why the usual default is absent.
       **Owner decision 2026-09-23**; T2.4 must parse this state explicitly, so the two
       tasks cannot disagree about what a tick means here.
  3. Implement: `render_attachment_conflicts_block(conflicts, asset_folder) -> str` in the
     reducer, returning `""` when empty; a `rendered_attachment_conflicts_md` doc field; its
     consumer in `suggestions-render.py`; the schema entry for the new field
  4. Validate: full suite; `ruff`. The zero-conflict guarantee is a **committed golden file**
     for a named fixture, diffed byte-for-byte inside a test — not a manual pre/post
     comparison done once during implementation. "Byte-compare against the pre-change render"
     as first written named no fixture, no baseline location and no mechanism; it is the same
     unanchored shape the guardian rejected twice in Phase 1.
  5. Success: every F2 rendering criterion has a named test AND a named mutation; the owner
     can act without opening JSON `[ref: PRD/Personas, primary]`

- [x] **T2.3 The entry says whether it is the same file** `[activity: frontend-ui]`

  `[parallel: true]` removed 2026-09-23 — it was written when T2.2 and T2.3 were assumed
  independent. Both write into `render_attachment_conflicts_block`.

  1. Prime: Read `same_file` in `[ref: SDD/Interface Specifications]`, the three S1 criteria,
     and `render_attachment_conflicts_block`'s current tick logic — it keys on
     `proposed_name` ALONE and does not read `same_file` at all
     `[ref: suggestions-reducer.py:~1480-1503]`. Read the executor-internals guard test in
     `tests/test_037_t2_2_render_conflicts.py`: every sentence you add is subject to it.
  2. Test — **every bullet names the mutation it kills; T2.3 as first written named none.**
     Each branch asserts its OWN text present **and the other two branches' text absent** —
     three separate `in` assertions all pass against a stub that always emits one fixed
     sentence.
     - **`same_file: true`** renders the "same file" statement AND the second-copy warning
       `[ref: PRD/S1-AC1]`. Mutation: emit only one of the two clauses.
     - **`same_file: false`** renders that a different file holds the name
       `[ref: PRD/S1-AC2]`. Mutation: swap in the `true`-branch wording.
     - **`same_file: null`** renders that the files could not be compared
       `[ref: PRD/S1-AC3]`. Mutation: fall through silently, emitting no sentence.
     - **The remedies are byte-identical to the `same_file`-free baseline.** Diff the three
       checkbox lines against T2.2's existing fixture for the same `proposed_name`; only the
       new sentence may differ. Replaces "with the remedies unchanged", which named no
       comparison and was therefore unfalsifiable.
     - **`same_file: true` still ships rename TICKED** `[ref: SDD/Complex Logic]`. Mutation:
       untick rename, or pre-tick keep-in-inbox, when the file is identical. This is the
       bullet most likely to be "helpfully" broken: the warning exists to steer the owner
       away from rename, and the new sentence is written physically beside the tick logic.
       The SDD is explicit — `same_file` changes no remedy and no default. It informs; the
       owner decides.
     - **`same_file: true` AND `proposed_name: null` together** render BOTH the duplicate
       warning AND the "no free name available" line with keep-in-inbox pre-ticked; neither
       suppresses the other. The fields are independent (T1.3 and T2.1) and the combination
       is reachable. Mutation: one `if/elif` chain treating "what is special about this
       entry" as mutually exclusive, dropping a sentence when both hold.
  3. Implement: branch the entry's wording on `same_file`; introduce no digest and no
     content-derived value into the render path `[ref: SDD/Security and privacy]`
  4. Validate: full suite; `ruff`. **No digest grep** — nothing in this module computes one
     (`_same_file` returns only `True`/`False`/`None`), so "assert no hex digest appears"
     cannot fail under any implementation of this task, correct or broken. The constraint
     stays stated in step 3 as a design boundary, not as false coverage.
  5. Success: the wording changes with `same_file`; the remedies and the default do not, and
     that is proven by two named bullets rather than asserted in prose
     `[ref: SDD/Complex Logic]`

- [x] **T2.4 The parser reads the tick back, and resolves the awkward cases** `[activity: domain-modeling]`

  1. Prime: Read `tomo/scripts/suggestion-parser.py`'s checkbox parsing for an existing
     decision block and **confirm it matches lines by text, not by position** — several
     bullets below rely on that; if it matches positionally, say so rather than assuming.
     Read Business Rules 2-4 `[ref: PRD/Detailed Feature Specifications]` and **ADR-4's
     exception paragraph**, which assigns this task the null-`proposed_name` state by name.
  2. Test — **every bullet names the mutation it kills; T2.4 as first written named none,
     the same state T2.2 and T2.3 were blocked in.**
     - **Rename left ticked, nothing else** yields `rename`. Mutation: resolve the
       document's own default to `ignore`, making Rule 2 unreachable.
     - **Keep-in-inbox ticked alone** yields `keep_in_inbox`. Mutation: fold it into Rule 3's
       ignore branch.
     - **Ignore ticked alone** yields `ignore`. Mutation: return `None` for an explicit tick,
       relying on the caller's fallback.
     - **Rename cleared with nothing else ticked** yields `ignore` `[ref: PRD/F2-AC5]`
       `[ref: SDD/ADR-4]`. Mutation: resolve to `keep_in_inbox` — the quiet outcome ADR-4
       argues against, and the inversion step 4 names.
     - **Two remedies ticked — using keep-in-inbox + ignore, NOT a pair involving rename** —
       yields `ignore` `[ref: PRD/Rule 4]`. Mutation: first-wins instead of contradiction.
     - **Rename stays ticked AND ignore is also ticked** yields `ignore`, not `rename`. This
       is NOT a duplicate of the bullet above: it kills a different implementation — one that
       treats the pre-ticked rename as sticky, default-wins over a later contradiction. A
       two-tick test using a pair without rename cannot catch that.
     - **`proposed_name` is `null` and rename is ticked alone** yields **`ignore`**.
       **Owner decision 2026-09-23.** Passing `rename` through is not an option: Pass 2 would
       reach `_asset_dest_join(asset_folder, None)` with no name to move to, breaking Rule 6
       ("the strongest outcome it produces is a move to a free name"). Between the two
       survivors, `ignore` follows ADR-4's own reasoning — an owner who overrides the
       pre-selected answer gets the loudest of the three outcomes, not the quietest, and
       `keep_in_inbox` would discard a deliberate tick with no signal that it was discarded.
       Mutation: pass `remedy: rename` through with a null proposal.
     - **A conflict entry missing one or more checkbox lines** still yields one of the three
       strings, never `None`. This is where "`remedy` is never null after parsing"
       `[ref: SDD/Interface Specifications]` becomes falsifiable — stated alone it is true by
       construction of the exhaustive tick cases above and proves nothing. Mutation: leave
       `remedy` unset when a line is absent. A deleted line parses as an unticked line.
     - **No `## Attachment Conflicts` section at all** yields an empty list — not an invented
       entry, not an error. Mirrors T1.2's settled absent-not-empty decision. Mutation:
       fabricate a single empty entry when the section is missing.
     - **Out of scope, stated so its absence is not read as an oversight**: an owner who edits
       the proposed filename in the rendered rename line changes nothing. Pass 2 reads
       `proposed_name` from the Pass-1 conflict data, never from parsed markdown
       `[ref: SDD/Runtime View, Pass 2]`. The rendered name is display, not input.
  3. Implement: parse the three boxes into `remedy`, applying Rules 3 and 4 and the
     null-proposal resolution decided above
  4. Validate: full suite; `ruff`; prove the cleared-default test RED by inverting the
     resolution to `keep_in_inbox`
  5. Success: an unresolved entry is loud, not quiet `[ref: SDD/ADR-4 rationale]`.

     **`[ref: PRD/S2-AC1]` struck from this task and re-homed.** S2-AC1 is a RENDERING
     criterion — the entry must state what will happen when rename is not ticked — and a
     parser cannot render a sentence into a document it only reads. It is discharged by
     T2.2's static remedy text (the Ignore line's consequence clause and the keep-in-inbox
     label, present in every entry regardless of tick state), **but it is not currently
     asserted**: `test_exactly_three_remedies_with_rename_ticked` checks only
     `checkboxes[2].startswith("- [ ] Ignore")`, never the clause that names the outcome.
     Phase 2 must not close with a PRD criterion pinned by nothing, so **this task adds that
     assertion to `tests/test_037_t2_2_render_conflicts.py`** — the one piece of T2.4's work
     that lands in a sibling task's file, done here because T2.4 is the phase's last task.

> **Deviation recorded 2026-09-23 — T2.1's test list sharpened before implementation.**
> The TDD guardian blocked the task I had written. Two findings upheld, one confirmed as-is:
> (1) **the candidate check never folded case.** Every fixture I listed used same-case names,
> so a literal string comparison would have passed all of them while being wrong — the repo
> folds case in `resolve_destination_clashes` and in T1.5's occupancy test.
> (2) **the candidate was gated on the file listing only.** T1.4 exists because a destination
> can be held by a FOLDER; a rename candidate that ignores the folder set re-creates that
> exact defect one level down, invisibly to every other bullet.
> (3) The stem rule — counter before the LAST dot, `karte.tar (2).gz` — was challenged and
> held: it is what `os.path.splitext` does, and the file's real type is its final suffix.
> Recorded because it was a one-line decision that is cheap to reverse now and expensive later.

> **Deviation recorded 2026-09-23 — T2.2's test list rewritten before implementation.**
> The guardian blocked it, and the root finding is structural: **T2.2 named zero mutations**,
> where its sibling T2.1 names one per bullet. Every specific defect followed from that.
> (1) "a run with no conflicts renders no section" is **already true of shipped code** — the
> section does not exist — so it is evidence of nothing unless paired with the positive case
> as one red/green pair.
> (2) "an attachment embedded by three notes renders one entry" is decided by the REDUCER
> (T1.2/T1.5), not the renderer; as written the fixture proves it, not the code. Reworded to
> target render-time iteration granularity.
> (3) **`proposed_name: null` was unhandled**, and rename ships pre-ticked. The owner decided
> *keep in inbox* is pre-ticked instead; `SDD/ADR-4` carries the exception so T2.4 cannot
> contradict it.
> (4) The C1 bullet would have passed on a bare basename, showing the owner a name with no
> folder.
> (5) The zero-conflict byte-compare was prose, not a test.

> **Deviation recorded 2026-09-23 — T2.3's test list rewritten before implementation.**
> Blocked for the same structural reason as T2.2: **every bullet named an outcome, none named
> a mutation.** Four findings beyond that, all upheld:
> (1) *"grep the rendered output for a hex digest and assert none"* is **already true of
> shipped code** — no digest exists anywhere in the call graph — so it could not fail under
> any implementation. Dropped rather than kept as false coverage.
> (2) *"with the remedies unchanged"* named no comparison target. Anchored to T2.2's fixture.
> (3) **`same_file: true` must still ship rename TICKED**, and nothing pinned it. The SDD says
> `same_file` changes no default, but the new sentence lands beside the tick logic and an
> implementer could reasonably "help". Now a named bullet with a named mutation.
> (4) **`same_file: true` + `proposed_name: null`** is reachable and was untested. The risk is
> not reader confusion but an `if/elif` treating the two independent fields as exclusive.
> Also: `[parallel: true]` retired — it assumed T2.2 and T2.3 touch different code, which is
> false; both write `render_attachment_conflicts_block`.

> **Deviation recorded 2026-09-23 — T2.4's test list rewritten before implementation.**
> Blocked for the third time in this phase on the same structural defect: **zero bullets named
> a mutation.** T2.4 sat unrevised in exactly the state T2.2 and T2.3 were pulled out of.
> Findings beyond that, all upheld:
> (1) **The ADR-4 exception was unparsed.** The SDD says in as many words that T2.4 parses the
> null-`proposed_name` state — and the task, written before that exception existed, never
> mentioned it. The owner decided the open case (rename ticked alone with no name available →
> `ignore`); passing `rename` through would have handed Pass 2 a move with no destination.
> (2) The two-tick bullets are NOT duplicates and now say why: one kills first-wins, the other
> kills a sticky pre-ticked rename. A single test cannot do both.
> (3) *"`remedy` is never null after parsing"* was true by construction and therefore dead
> weight; it is now anchored to a malformed entry, the only input that can falsify it.
> (4) An absent section was untested — the parse-side mirror of T1.2's absent-not-empty rule.
> (5) **`PRD/S2-AC1` was misattributed to this task.** It is a rendering criterion, discharged
> by T2.2's static text, and — found while checking — **asserted by no test at all**. Re-homed
> with the assertion added here rather than left as the one PRD criterion Phase 2 closes
> without coverage.
