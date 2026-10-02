---
title: "Phase 3: Refusal, before anything can be typed"
status: in_progress
version: "1.0"
phase: 3
---

# Phase 3: Refusal, before anything can be typed

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F3]` — nine acceptance criteria
- `[ref: PRD/Secondary User Journey (error path)]`
- `[ref: SDD/ADR-5]` — reject, never sanitise; its own module
- `[ref: SDD/ADR-6]` — reuse `skipped_assets`, and **hold** the owning note
- `[ref: SDD/Complex Logic — why the check cannot live inside `_asset_dest_join`]`
- `[ref: SDD/CON-4, CON-6, CON-7]`

**Key Decisions**:
- The check is a **pure function on a string** and lives in its own module, so one
  rule serves both read paths. A rule inside the move builder is reachable from
  neither path independently `[ref: SDD/ADR-5]`.
- It **rejects**. `sanitize_stem` substitutes — including `/` → `-` — and reusing
  it would file `a/b.png` as `a-b.png` with nothing reported, which is the defect
  this spec closes wearing a different hat `[ref: SDD/ADR-5]`.
- A refused name **holds the owning note**. 037 excluded `vault_collision_held`
  from the holding pass because the owner *chose* to leave the attachment; a
  refused name is the opposite `[ref: SDD/ADR-6]`.
- `_asset_dest_join` is **not** changed. What stays as defence in depth is
  **basename extraction**, not truncation — `source_path.rsplit("/", 1)[-1]`
  (`lib/render_actions.py:571`). So an unguarded typed `a/b.png` yields
  `<asset_folder>/b.png` today: the prefix is silently dropped, which is a wrong
  name rather than a traversal. The PRD states this correctly at
  `requirements.md:515` — "the existing helper already discards everything before
  the last separator, so refusal closes the reporting gap rather than a traversal
  hole". Measured 2026-10-01. The SDD describes the mechanism correctly at
  `solution.md:321` and then calls it "the truncation" as shorthand at `:330` —
  same thing, no contradiction; just do not go looking for a length limit
  `[ref: SDD/CON-4]`.

**Dependencies**: none on Phases 1–2. **This phase precedes Phase 4 on purpose**:
no commit on the branch should ever have an owner-typed string reaching a
destination unguarded.

---

## Tasks

Delivers the guard and its consequences, fully tested, before the markdown can
produce a typed name at all.

- [x] **T3.1 The typed-name check** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: read `lib/obsidian_filename.py`'s `sanitize_stem` (`:36-44`) — to
     understand precisely what is **not** being reused and why — and
     `_asset_dest_join` (`render_actions.py:560-575`) to see what the string would
     otherwise flow into.

     **Measured 2026-10-01 (T2.5) — the control an owner edits renders a full
     path, not a filename.** `suggestions-reducer.py:1517` emits the Rename line
     as ``- [x] Rename to `{_asset_dest_join(asset_folder, proposed_name)}` ``,
     which on a real run reads ``Rename to `Atlas/290 Assets/295 Attachments/karte (2).png` `` — while the wire field `attachment_conflicts[].proposed_name`
     holds the bare basename `karte (2).png`. So the separator refusal this task
     specifies will reject the **most natural edit there is**: retyping the stem
     and leaving the folder prefix where the renderer put it. **The PRD already
     settles what to do about it** — F3's first criterion refuses a separator
     "not truncated to its last segment", and ADR-5 forbids rewriting — so
     stripping the folder the renderer itself wrote is not an option, however
     tempting. What stays open is only the refusal reason's wording, which T3.4
     owns and the existing `separator present` class already covers. Flagged
     here because the collision is real and a reader of this task alone could
     reasonably invent the strip.
     Confirmed absent today, so the task is building something real: the parse
     site lowercases the label and branches on `startswith("rename")`
     (`suggestion-parser.py:2350-2354`) and never reads the backtick-quoted text
     at all. D25's `markdown_control` calls it "the backtick-quoted filename",
     which understates the control — worth amending in the same breath.
  2. Test: one case per refusal class and one acceptance case. Separator present
     (`a/b.png`, `../../x.png`, `/abs.png`); forbidden character (each of
     `: * ? " < > |` and backslash); blank and whitespace-only (`""`, `" "` —
     note `not " "` is `False`, so **two** existing truthiness guards each let it
     through, both measured 2026-10-01: `lib/render_actions.py:788`'s
     `not remedy_entry.get("proposed_name")`, which is why `" "` does **not**
     degrade to `keep_in_inbox` the way a `None` does, and `_asset_dest_join`'s
     `if not basename` at `:572`, which is why it then returns a destination
     ending in a bare space instead of raising. The check must precede both).
     **Three classes, not four** — owner ruling 2026-10-01, after this task was
     blocked for specifying an untestable one. `taken` is a property of the run,
     not of the string, and the run already decides it at
     `lib/render_actions.py:927`, which a remedy-chosen destination reaches by
     design (`:922-926`). So this module takes **one argument** and stays a pure
     function on a string; do not add a `taken`/`claimed` parameter, and do not
     reach for a vault listing — there is none on this path (`path_exists` appears
     nowhere in `render_actions.py` or `render_md.py`). Plus: a usable name is
     returned **unchanged**, never
     rewritten. One addition to the character list, measured: `FORBIDDEN_CHARS`
     (`lib/obsidian_filename.py:32`) has **ten** members — the eight named above,
     plus `/` which the separator class already covers, plus **NUL**, which this
     list never named. Refuse it too, so "each of" means the whole set.
  3. Implement: `tomo/scripts/lib/typed_name_check.py`. Returns a verdict plus a
     refusal reason from a **closed set** so the renderer can phrase each without
     parsing a string `[ref: SDD/Interface Specifications]`.
  4. Validate: unit tests green; `ruff` clean; the module has no import from
     `render_actions` (it must be usable from the parser side too).
  5. Success:
     - [ ] Each of the **three** refusal classes refuses `[ref: PRD/F3]`
     - [ ] A usable name is returned unchanged — the check never rewrites `[ref: PRD/F3]`
     - [ ] `" "` is refused, closing the gap the two existing truthiness guards leave
     - [ ] NUL is refused, so "every forbidden character" means all ten
     - [ ] The signature takes **one** argument — no run state, no vault listing
     - [ ] Both acceptance **and** rejection are proven, per Constitution L1 `[ref: SDD/CON-5]`

- [x] **T3.2 The move builder consumes the verdict** `[activity: backend-api]`

  1. Prime: read `_build_move_asset_actions` (`lib/render_actions.py:691`), its
     rename branch (`:825-830`), and the existing `skipped_assets` kinds
     (`no_basename`, `vault_collision_held`, `collision`).

     **This task grew on 2026-10-01, by owner ruling, and now touches
     `suggestion-parser.py` as well.** The reason is measured: `proposed_name`
     carries **no provenance**. `detect_attachment_conflicts` builds every record
     in one literal of five keys (`suggestions-reducer.py:735-741`) and none of
     them says whether the owner typed the name or Pass 1 computed it. So "the
     computed-name path is unchanged" cannot be met by branching on anything that
     exists today, and it is not satisfied by accident either: `_propose_asset_name`
     rebuilds `f"{stem} ({n}).{ext}"` from the raw basename
     (`suggestions-reducer.py:573-577`) and sanitises nothing — `FORBIDDEN_CHARS`
     appears nowhere in that module. Measured by running T3.1's check over names
     the reducer would compute: **five of seven** realistic macOS filenames are
     refused, because `* " | < > \` are all legal on macOS and all forbidden by
     Obsidian.

     ```
     inbox basename        Tomo computes          verdict
     karte.png             karte (2).png          OK
     foo*bar.png           foo*bar (2).png        REFUSED (forbidden_character)
     quote"name.png        quote"name (2).png     REFUSED (forbidden_character)
     a|b.png               a|b (2).png            REFUSED (forbidden_character)
     note<draft>.png       note<draft> (2).png    REFUSED (forbidden_character)
     back\slash.png        back\slash (2).png     REFUSED (forbidden_character)
     Q&A notes.png         Q&A notes (2).png      OK
     ```

     So add **`name_is_owner_supplied`** to the remedy record, in both producers —
     both internal to `suggestion-parser.py`, so this is **not** a schema or wire
     change and Phase 2's version question stays closed:
     - `build_from_wire`'s projection (`:494`, built in T2.2) — **`True`**. The
       consumer's editor can change this field, and Tomo cannot tell whether it
       did, so "could have been edited" is the semantic.
     - the markdown join (`:2997`, `_join_attachment_conflict_remedies` over
       `_load_json_doc`) — **`False`** today, because the name comes from the
       structured doc and the rendered text is never consulted for it. **Phase 4
       flips this** when a typed name actually arrives; see `phase-4.md`.

     Considered and not chosen: comparing the wire's `proposed_name` against the
     doc's computed one, which would be more precise — it would spare a consumer
     who never touched the name. It was rejected because it re-couples the
     JSON-only path to the doc, and Phase 2's T2.5 measured that path working
     without it (`--file` plus `--suggestions-json`, no `--suggestions-doc`).
  2. Test: a refused name emits **no** `move_asset` for that attachment and **one**
     `skipped_assets` entry of kind **`typed_name_refused`** carrying the reason;
     a usable typed
     name emits the move against the typed destination; a Tomo-computed name
     behaves exactly as today. **Both sides of the flag need a case, and one of
     them is the whole point**: the SAME unusable string — take `foo*bar (2).png`
     from the table above — must be **refused** when `name_is_owner_supplied` is
     `True` and must behave **exactly as today** when it is `False`. A test that
     only covers the refusal would pass against an implementation that checks
     every name, which is the behaviour change this ruling exists to prevent. **Plus one case this task confirms rather than
     builds** (owner ruling 2026-10-01, where F3's fourth criterion landed): a
     typed name that is usable as a string but collides with a destination another
     action in the same run already claimed is refused by the **existing** check at
     `:836` with `kind: "collision"`.

     **Correction, 2026-10-01.** This bullet first claimed the guarantee "lives
     only in a comment (`:831-835`)". That was false, and a coverage claim made
     without an exhaustive search — the same mistake as spec 038 Phase 2's, in
     the same test file. It lives in
     `tests/test_037_t3_1_remedy_outcomes.py:280-312`,
     `test_a_remedys_destination_still_goes_through_the_claimed_check`, which (the
     `:831-835` inside that quotation is pre-T3.2 numbering and is left as
     quoted; that comment block is now `:922-926`)
     renames `other.png` onto `orig.png`'s destination and asserts
     `kind == "collision"`, with its mutation named in its own docstring. **That
     test is the regression anchor and must pass UNCHANGED** — it supplies no
     flag, so the check must not fire for it.

     What it cannot cover is the combination that needs the new field: a
     **usable** typed name, `name_is_owner_supplied` `True`, colliding
     run-locally — which must come back `collision`, **not**
     `typed_name_refused`. That is the case to add, and it is the one a check
     inserted before `_asset_dest_join` could bypass.
  3. Implement: set `name_is_owner_supplied` in both producers; in the rename
     branch call the check **before** `_asset_dest_join` and **only when the flag
     is `True`**; add the new `skipped_assets` kind **`typed_name_refused`**. Do
     **not** touch `_asset_dest_join` `[ref: SDD/CON-4]`. The literal is fixed in
     ADR-6, not chosen here — T3.3 asserts it and T3.4 branches on it, so do not
     rename it `[ref: SDD/ADR-6]`.
  4. Validate: the 037 suite stays green — particularly the degraded-rename path
     (`proposed_name` null still degrades to `keep_in_inbox`,
     `render_actions.py:787-789`). Note that guard is a truthiness test, so `" "`
     does **not** degrade; it reaches the rename branch and is refused there when
     the flag is `True`.
  5. Success:
     - [ ] A refused name emits no move and one records entry `[ref: PRD/F3]`
     - [ ] The computed-name path is unchanged, **proven on a string that the
           check refuses** — not merely on a name that happens to pass
           `[ref: PRD/F3]`
     - [ ] `name_is_owner_supplied` is `True` on the wire path and `False` on the
           markdown path, each asserted `[ref: PRD/F3]`
     - [ ] No schema file and no wire field changed — the flag is internal
     - [ ] `_asset_dest_join` is byte-identical to before `[ref: SDD/Acceptance Criteria]`

- [x] **T3.3 The owning note is held** `[activity: backend-api]`

  1. Prime: read `suppress_moves_for_unfiled_attachments` (`render_actions.py:1516`)
     including the docstring explaining why `vault_collision_held` is **excluded**,
     and 037's `requirements.md:374-382` where that exclusion was measured rather
     than assumed.

     **Measured 2026-10-02, before dispatch: this task has no production code
     left, and two of its three success criteria are already evidenced.** Read
     this before briefing anyone, or the brief will ask for work that is done.

     - **There is no exclusion *list*.** The exclusion is a single equality at
       `render_actions.py:1569` — `if entry.get("kind") == "vault_collision_held":
       continue`. So a new kind is never excluded by construction; it falls through
       to the suppressing default with no edit at all. Step 3's "that is the whole
       change" is literally a no-op, not shorthand for a small change. The task
       text's phrase "the exclusion list" is kept below because it is what the
       mutation creates, but nothing in the tree matches that shape today.
     - **Criterion 1 is already green.** `tests/test_038_t3_2_typed_name_refusal.py`
       builds a `typed_name_refused` skip, runs the suppression pass, and asserts
       `move_notes == []` plus the exact owner-facing suppression sentence.
     - **Criterion 2 is already green**, in 037 and unchanged by Phase 3:
       `tests/test_037_t3_1_remedy_outcomes.py:158`,
       `test_vault_collision_held_owning_note_is_still_filed`, which asserts
       `vault_collision_held` produces no suppression at all.
     - **Criterion 3 has now been run** — see step 4 below. It was the only one of
       the three that was outstanding, and it is the reason this task was not
       simply ticked on existing evidence.

     **So what remains is one real deliverable**, and it came out of running the
     mutation rather than reading the plan: the guard that caught it is named
     `test_owner_facing_suppression_sentence_names_no_inbox_path_and_no_refusal_code`
     — a name about the suppression *sentence*. The holds-the-note assertion is a
     passenger inside it. A future reader asking "does a refused typed name hold
     its owning note?" cannot find that answer by name, and a future edit that
     narrows that test to its sentence concern would take the data-loss guard with
     it silently. Give the assertion its own named test. That is the deliverable;
     the production tree needs nothing.
  2. Test: a refused typed name holds the owning note — and assert this
     **specifically**, because the exclusion list is exactly where 037 had to make
     the opposite choice explicit, and `typed_name_refused` silently added to that
     list would
     be invisible `[ref: SDD/Acceptance Criteria]`. **"Specifically" now means in a
     test whose NAME is about holding the note** — the assertion already exists but
     rides inside a test named for the suppression sentence, which is not findable
     and not safe from a future narrowing edit. The existing assertion may stay
     where it is; this adds a named one, it does not move it.
  3. Implement: `typed_name_refused` is **not** added to the exclusion list. That is the
     whole change; the pass's default behaviour does the rest `[ref: SDD/ADR-6]`.
  4. Validate: the 037 test that `vault_collision_held` does **not** hold the note
     stays green — the two kinds must diverge, and both directions need proof.

     **Criterion 3's mutation was executed 2026-10-02** in a throwaway `git
     worktree` at `HEAD` (`0c3059e`), never in the working tree. Baseline in that
     worktree: 11 passed. The mutation the criterion names — the single equality at
     `:1569` widened to
     `in ("vault_collision_held", "typed_name_refused")` — turned it red:

     ```
     FAILED tests/test_038_t3_2_typed_name_refusal.py::
       test_owner_facing_suppression_sentence_names_no_inbox_path_and_no_refusal_code
     AssertionError: the owning note must be held, not filed:
       [{'action': 'move_note', 'source': '100 Inbox/2026-01-01_0900_karte.md',
         'destination': 'Atlas/202 Notes/Some Note.md', ...}]
     1 failed, 10 passed
     ```

     The failure is worth reading rather than just counting: the note is filed to
     `Atlas/202 Notes/Some Note.md` while the attachment it embeds stays in the
     inbox — the exact separation this task exists to prevent. The worktree was
     removed with `rm -rf` plus `git worktree prune`, and the working tree's
     `:1569` was re-verified unmutated afterwards.
  5. Success:
     - [ ] A refused name holds the owning note `[ref: PRD/F3]`
     - [ ] `vault_collision_held` still does not `[ref: SDD/ADR-6]`
     - [ ] The mutation — adding `typed_name_refused` to the exclusion list — turns the
           T3.3 test red. **Run it.**

- [ ] **T3.4 The instruction document reports it** `[activity: frontend-ui]`

  1. Prime: read `lib/render_md.py`'s skipped-**assets** block at
     **`:1079-1095`** and `_render_unresolved_conflict_bullet` at **`:740`**, for
     the established register: a heading stating the outcome, a bold lead sentence
     stating the effect, then `- ⚠️ **<Label>:**` bullets. All three references
     were wrong as first written and are corrected here, measured 2026-10-01:
     `~:1046-1051` is the *unresolved_conflicts* block — a different block with its
     own heading and its own passive-voice history; `:797` is 57 lines past the
     one and only definition of that helper. The real block already carries the
     register at `:1084-1092`, and gives each kind its own `remedy` line beneath
     the bullet — `typed_name_refused` needs one too, and that line is where "what to do
     about it" belongs. For CON-6 read
     **`docs/tomo/scripts/lib/render_md.md:502-510`** ("ADR-11 Reaches the Existing
     Loop Too"), which is about this exact bullet — the one `no_basename` and
     `collision` already share, and where the owner ruled on 2026-09-27 that the
     `` `move_asset` → `` wire-action prefix had to go. `:328-330` only cites
     ADR-11 in passing inside another ADR's argument `[ref: SDD/CON-6]`.
  2. Test: a refused name produces a bullet naming the attachment and the reason
     class; the text contains **no** function name, module name, wire action name
     or id; the sentence asserts only what was verified. Note the reasons reach
     this renderer from **two** sources after the 2026-10-01 ruling: three from
     T3.1's module via `typed_name_refused`, and the run-local collision from the existing
     `kind: "collision"` path.

     **That question is now closed — do not re-open it, and do not touch the
     collision sentence** (owner ruling 2026-10-02). It had asked whether a
     collision on an owner-**typed** name should read differently from one on a
     Tomo-computed name, since the shared string
     (`render_actions.py:935`) says *"destination collision: it also resolves to
     `<dest>`, already claimed by `<claimant>`"* and never mentions that a name
     was typed. The ruling: F3's sixth criterion covers the **three string
     classes** T3.1 decides, not the fourth criterion's run-local collision, and
     the PRD now records that scope beside the criterion itself.

     So **this task renders one new bullet shape, not two.** `typed_name_refused`
     gets a bullet and a `remedy` line; the `collision` bullet is untouched, for
     typed and computed names alike. Measured before the ruling, in case a later
     reader wants the cost: the skipped entry carries no provenance at all
     (`{source, destination, reason, kind, owner_source_items}` —
     `render_actions.py:938-941`), so either alternative needed a new field or a
     forked string, and the owner already knows they typed the name because the
     document is rendered from the run in which they typed it.
  3. Implement: one bullet per refusal, in the existing skipped block. Also the
     Could-have count in the summary `[ref: PRD/C1]`.
  4. Validate: assert on the **exact** rendered string, not on presence — spec 037
     shipped four defective sentences precisely because every assertion checked
     presence `[ref: SDD/Risks]`.
  5. Success:
     - [ ] The refusal is reported, naming the attachment `[ref: PRD/F3]`
     - [ ] No executor internals in the text `[ref: SDD/CON-6]`
     - [ ] No sentence predicts a future outcome or infers owner intent — the
           specific trap 037 fell into four times `[ref: SDD/CON-6]`
     - [ ] Nothing implies the owning-note list is exhaustive `[ref: SDD/CON-7]`

- [ ] **T3.5 Phase validation** `[activity: validate]`

  - Run the full suite and `ruff`. Write the `docs/tomo/` WHY entries — **now, not
    in Phase 5**. The list below replaces "the new module and the two modified
    functions", which undercounted what Phase 3 actually changed (corrected
    2026-10-01, after T3.2 grew twice):
    - `docs/tomo/scripts/lib/typed_name_check.md` — new. Why rejection rather than
      `sanitize_stem`'s substitution; why a separate module; why three string
      classes and not four; why one argument and no vault listing.
    - `docs/tomo/scripts/lib/render_actions.md` — `_typed_name_refusal_reason`,
      the `name_is_owner_supplied` gate and why a computed name is never checked,
      and `_attachment_suppression_reason`'s third branch. State how the three
      fields divide: `kind` is what renderers branch on, `reason` is prose for a
      human and must never be parsed, `refusal_reason` is a second-level
      machine-readable discriminator under one kind. That division is already the
      documented convention for the dropped-sources report
      (`docs/tomo/scripts/instruction-render.md:383-387`) — say that this follows
      it rather than inventing it, since T3.2's first attempt broke it by putting
      the bare code in `reason`.
    - `docs/tomo/scripts/suggestion-parser.md` — why the flag is set in two
      producers with different values, and why the wire path cannot compare
      against the doc.
    - `docs/tomo/scripts/instruction-render.md` — **already written** during T3.2
      (the `kind` reversal); verify it rather than rewriting it.
  - Re-read every assertion added in this phase and ask of each: *which mutation
    turns this red?* Run the ones you can name. Spec 037 produced nine assertions
    that could not bite `[ref: plan/README.md; the standing warning]`.
  - Success: suite green; `ruff` clean; WHY entries written; every new assertion
    has a named, executed mutation `[ref: PRD/F3]`.
