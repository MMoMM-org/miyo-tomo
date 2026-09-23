---
title: "Phase 2: The decision in the document"
status: in_progress
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

- [ ] **T2.2 The conflict renders as a decision with three remedies** `[activity: frontend-ui]`

  1. Prime: Read `render_attachments_preamble` `[ref: suggestions-reducer.py:1452]` for the document's existing attachment voice, and a rendered suggestions document for how other decisions present their checkboxes
  2. Test: one conflict renders an entry naming source, destination and every owning note `[ref: PRD/F2-AC1]`; exactly three remedies appear — rename, keep in inbox, ignore — with rename ticked `[ref: PRD/F2-AC2]`; an attachment embedded by three notes renders **one** entry `[ref: PRD/F2-AC3]`; a run with no conflicts renders **no section at all** `[ref: PRD/F2-AC4]`; the rename remedy names the destination it would use `[ref: PRD/C1]`
  3. Implement: render the section from `attachment_conflicts[]`, including `proposed_name`
  4. Validate: full suite; `ruff`; byte-compare a zero-conflict document against the pre-change render
  5. Success: every F2 rendering criterion has a named test; the owner can act without opening JSON `[ref: PRD/Personas, primary]`

- [ ] **T2.3 The entry says whether it is the same file** `[activity: frontend-ui]` `[parallel: true]`

  1. Prime: Read `same_file` in `[ref: SDD/Interface Specifications]` and the three S1 criteria
  2. Test: `same_file: true` renders the sentence saying so **and** the warning that renaming creates a second copy `[ref: PRD/S1-AC1]`; `false` renders that a different file holds the name `[ref: PRD/S1-AC2]`; `null` renders that the files could not be compared, with the remedies unchanged `[ref: PRD/S1-AC3]`
  3. Implement: branch the entry's wording on `same_file`; never render a digest `[ref: SDD/Security and privacy]`
  4. Validate: full suite; `ruff`; grep the rendered fixture output for any hex digest and assert none
  5. Success: the wording changes, the remedies and the default do not `[ref: SDD/Complex Logic]`

- [ ] **T2.4 The parser reads the tick back, and resolves the awkward cases** `[activity: domain-modeling]`

  1. Prime: Read `tomo/scripts/suggestion-parser.py` checkbox parsing for an existing decision block; read Business Rules 3 and 4 `[ref: PRD/Detailed Feature Specifications]`
  2. Test: rename left ticked yields `rename`; keep-in-inbox ticked alone yields `keep_in_inbox`; ignore ticked alone yields `ignore`; **rename cleared with nothing else ticked yields `ignore`** `[ref: PRD/F2-AC5, ADR-4]`; **two remedies ticked yields `ignore`** `[ref: PRD/Rule 4]`; `remedy` is never null after parsing `[ref: SDD/Interface Specifications]`; an entry where rename stays ticked and the owner also ticks ignore is a contradiction, not a rename
  3. Implement: parse the three boxes into `remedy`, applying Rules 3 and 4 in the parser
  4. Validate: full suite; `ruff`; prove the cleared-default test RED by inverting the resolution to `keep_in_inbox`
  5. Success: an unresolved entry is loud, not quiet `[ref: SDD/ADR-4 rationale]`; S2's statement in the entry names what will happen `[ref: PRD/S2-AC1]`

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
