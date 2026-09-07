---
title: "Phase 5: Display and destination guards"
status: completed
version: "1.0"
phase: 5
---

# Phase 5: Display and destination guards

## Phase Context

**GATE**: read these before starting.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-4, ADR-6]`
- `[ref: SDD/Complex Logic]` — the traced walkthrough of the validation pass
- `[ref: PRD/Feature 2, Feature 7, Feature 8]`
- `[ref: PRD/Business Rule 5, Business Rule 8]`

**Key Decisions**:
- Source links are path-qualified **only** when two items in the run share a filename. A bare
  link is not merely terse in that case — the vault resolves by name, so clicking or hovering
  either of two identical links opens whichever it picks.
- A Pass-1 check is advisory. The user edits the document afterwards, so the binding guard
  belongs in Pass 2 `[ref: PRD/Business Rule 8]`.
- On a destination clash, **both** claimants are dropped. Choosing between two names the user
  set deliberately would itself be a guess.
- An attachment clash suppresses its own note's move, reversing spec 031.

**Dependencies**: Phases 3 and 4 complete.

---

## Tasks

- [x] **T5.0 Pass 2 reads `item_key` — the feature does not work without this** `[activity: backend]`

  **BLOCKING, added 2026-09-06 by the Phase 3 gate.** Recursion is live and the key is threaded
  through Pass 1, but **every subfolder note is silently dropped in Pass 2**, so nothing the
  recursion discovers reaches the instruction set. PRD Feature 1's acceptance criterion —
  "subfolder notes are triaged" — is not met end to end until this lands.

  **The mechanism.** `filter_missing_source_notes` (`lib/render_resolve.py:672-683`), called from
  `instruction-render.py:320`, reconstructs a path from the bare display stem:

  ```python
  if item.get("template") and source_path:
      full_path = source_path
      if "/" not in full_path:
          full_path = f"{inbox_path.rstrip('/')}/{full_path}"
      if not full_path.endswith(".md"):
          full_path += ".md"
      if not _exists(full_path):
          dropped.append(item)
  ```

  For `100 Inbox/Places/Kaffee.md` the item's `source_path` is `Kaffee`, so it probes
  `100 Inbox/Kaffee.md`, finds nothing, and drops the item. **This is the same
  `<inbox_path>/<stem>.md` reconstruction T4.1 removed from `force-atomic-handling/SKILL.md`**,
  living in a file no task pointed at. A second copy sits at `instruction-render.py:381-386`
  (the body read); subfolder items never reach it because they are already gone.

  **It is not a markdown-versus-wire problem.** Both parser paths emit a bare `source_path` by
  Phase 2's deliberate design — `item_key` carries identity, `source_path` stays display text
  (ADR-2). The defect is on the **consumer** side: the whole Pass-2 render stage never adopted
  the key.

  ```
  tomo/scripts/instruction-render.py     0 occurrences of "item_key"
  tomo/scripts/lib/render_resolve.py     0
  tomo/scripts/lib/render_io.py          0
  ```

  T2.3b landed `item_key` one hop short of the stage that needs it.

  **Blast radius: every subfolder note carrying a `template`** — every atomic-note suggestion —
  not only ones whose filename collides. The guard branches on `"/" not in source_path`, a plain
  "is this a bare stem" test with no collision awareness. Demonstrated on three globally unique
  filenames (`Kaffee`, `Level2`, `Root Note`): the two in subfolders were dropped, the root one
  kept, and every path the guard probed exists in the vault — it probed none of them.

  **T5.1 does not close this.** T5.1 path-qualifies source links *on collision*; this drops every
  subfolder note regardless. They are independent.


  **Three further facts from the gate, each of which changes how this must be fixed.**

  **(a) The guard fabricates the very stub it exists to prevent.** `_exists` returns `True` on
  *any* exception. So a transient Kado error does not drop the item — it **keeps** it, and the
  item then reaches the body read at `instruction-render.py:381`, reads an empty body, and
  fabricates a stub. `#116` exists precisely to stop that. The function therefore fails in both
  directions: it drops items whose notes exist, and on error it admits items whose notes it
  could not check. Fixing the addressing does not fix this; the fail-open branch needs its own
  decision, and "keep and read an empty body" is not it.

  **(b) The message misdiagnoses, and reaches no artefact.** `instruction-render.py:323-333`
  prints, to stderr only:

  ```
  [skip] 2 confirmed item(s) skipped — source note missing, not fabricating a stub:
    • S01 → Kaffee
    • S02 → Level2
  ```

  The note is **not** missing — it is one folder down. A user reading this looks for a deleted
  file. `dropped_missing_source` is referenced at `:320`, `:323`, `:329` and nowhere else: it
  reaches neither the instruction set, nor `needs_attention`, nor `instructions.md`, and the exit
  code stays **0** (`:739`, the drop never increments `errors`). Whatever this task does about the
  addressing, a dropped item must become visible in an artefact the user actually reads, and the
  wording must say what really happened.

  **(c) Inherited, not introduced — and that is why nobody looked.** `render_resolve.py:673-678`
  and `instruction-render.py:381-384` are **byte-identical at `ee44cb3`**. The reconstruction was
  correct while `depth=1` guaranteed every item sat at the root; Phase 3 removed the precondition,
  not the code. So this is a live defect on HEAD that no diff in this spec would ever show —
  which is why four task-level reviews, each correctly scoped to its own diff, could not have
  found it. Only walking the chain did.

  **Not in the spec at all**: `filter_missing_source_notes`, `render_resolve.py`, `render_io.py`,
  `render_actions.py` and `#116` appear nowhere in spec 034's plan, SDD or backlog.


  **(d) SEVEN sites, four files — and one of them emits a `delete` at the Hashi boundary.**

  Chasing the drop downstream found the same shape five more times, all in
  `lib/render_actions.py`, none behind the filter that hides the first two:

  | `file:line` | emits | guard | behind the drop? |
  |---|---|---|---|
  | `render_actions.py:592-593` | `move_note.source_inbox_item` | `if "/" not in ...` | yes — inert unless the filter fails open |
  | `render_actions.py:605-606` | `move_note.audio_peer` | same | yes — same |
  | `render_actions.py:947` | `delete_source` (skipped items) | `sp if "/" in sp` | **no** — walks `skipped` |
  | **`render_actions.py:967`** | **`delete_source` (daily-only stems)** | **none at all** | **no** — walks `daily_updates` |
  | `render_actions.py:1063-1064` | `skip.source_path` | `if sp and "/" not in sp` | **no** — walks `skipped` |

  All four Pass-2 files ignore the key entirely: `instruction-render.py`, `render_resolve.py`,
  `render_io.py`, `render_actions.py` — **0 occurrences of `item_key` in each.**

  **`:967` is the one to fix first, and the chain is fully traced.** It has no bare-stem guard to
  extend — it composes the inbox root unconditionally:

  ```python
  stem = _stem(entry.get("source_stem"))        # flattens to a bare filename
  "source_path": f"{inbox}{stem}.md",           # always root, no "/" test
  ```

  Provenance: `suggestions-reducer.py:1727` binds `for idx, (stem, item_key, _entry) in
  enumerate(done_items, ...)` — `stem` is the bare display name and **`item_key` sits unused right
  beside it**. It reaches `daily_updates[].log_entries[].source_stem` at `:1831`/`:1841`, then
  `render_actions.py:963`, then `:967`.

  So for a subfolder note whose content is fully captured in the daily note:
  - with no root note of that name, the emitted delete targets a path that does not exist — the
    real note survives in the inbox and is re-suggested next run;
  - **with a different note of that name at the inbox root, the emitted `delete_source` names the
    root note.** That is a wrong delete on the CON-4 boundary, and Hashi executes instruction sets.

  The destructive case needs exactly the basename collision this spec exists to handle, and
  recursion is what made it reachable. CON-2's two-pass review stands between the instruction and
  the vault — but the review document renders bare stems, so it reads `delete Dresden` without
  saying which. **Treat `:967` as the first obligation of this task**, and before fixing it,
  establish whether it is reachable today with a fixture rather than assuming either way.

  Bounded claim on completeness: these seven are every hit of a repo-wide grep for `"/" not in`
  and `inbox_path`-composition idioms across `tomo/scripts/` and `scripts/`. That grep does not
  catch a stem-keyed dict, an `os.path.join`, a `Path(...) /`, or a bare-basename comparison. The
  enumeration is complete for **this idiom**, not for the concern.

  1. **Prime**: Read `filter_missing_source_notes` (`lib/render_resolve.py:672-683`), its caller
     (`instruction-render.py:320`), and the body read at `instruction-render.py:381-386`. Read the
     `#116` rationale the guard exists for — it is right, it is only addressing the item wrongly.
  2. **Test** (RED):
     - a subfolder note with a globally unique filename survives Pass 2 and reaches the
       instruction set `[ref: PRD/AC Feature 1]`
     - a note nested two levels deep survives
     - a root-level note is unchanged
     - the `#116` guard still drops an item whose source note is genuinely gone — the guard must
       keep working, not be removed
     - no path is composed from a bare stem anywhere in the Pass-2 render stage
  3. **Implement**: address the item by `item_key`, falling back to the reconstruction only when
     the key is absent, so a document produced before this spec still renders. Fix both sites.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] A subfolder note reaches the instruction set `[ref: PRD/AC Feature 1]`
     - [ ] The `#116` guard still catches a genuinely missing source note
     - [ ] No `<inbox_path>/<stem>` composition survives in the Pass-2 render stage

- [x] **T5.0b The delete bookkeeping in `render_actions` still keys on the stem** `[activity: backend]`

  Added 2026-09-06 by T5.0's implementer, which found it while sweeping for the shape and then
  proved all four cases with fixtures against post-fix code rather than leaving them inferred.

  Six collections inside `_build_delete_source_actions` key on the bare stem, so two namesakes
  collapse into one bucket:

  | collection | consequence when two namesakes collide |
  |---|---|
  | `moves_by_origin` | one delete emitted for `moves[0]`; the second note's source survives |
  | `expected_by_stem` | the OQ6 gate denominator counts one bucket holding both — passes coincidentally here; with one atomic each and an item dropped it would under-count and defer |
  | `keep_source_stems` | `keep_source` on A suppresses B's delete too — **zero** deletes |
  | `seen` | the second daily-only namesake gets no delete |
  | `confirmed_stems` | B's daily-only delete is suppressed because A is confirmed |
  | `daily_stems` | mis-attribution only: A's reason reads `+ daily` because **B** had the daily entry |

  **Every direction fails safe.** The second note's source is left *undeleted*; the wrong note is
  never deleted. Both notes still move correctly — only the cleanup is lost, and recovery is
  automatic because the file stays in the inbox and is re-proposed on the next run. That is why
  T5.0 deliberately left it: re-keying the OQ6 completion gate changes that gate's logic, which is
  a behaviour change rather than an addressing fix, and it does not belong inside a task about
  addressing.

  **The part that reaches the user, and the reason this is not merely cosmetic.** Two reason
  strings mis-describe reality *in the document the user approves*:
  - `"Origin consumed by 2 atomics"` names A while one of those atomics came from **B**.
  - `"+ daily"` credits A with **B's** daily capture.

  Under CON-2 the user approves on what that document says. A description that is wrong about
  which note did what is a wrong basis for approval, even when the resulting action is safe.

  **Reachability by path**, proven: cases 1-2 need two confirmed items carrying templates, which
  the `#116` filter drops on the markdown path before `build_actions` — **wire path only today**.
  Cases 3-4 involve daily entries, whose keys T5.0 recovers on both paths — **both paths**.

  1. **Prime**: read `_build_delete_source_actions` in `lib/render_actions.py` end to end, and the
     OQ6 completion gate it depends on. Read `docs/tomo/scripts/lib/render_actions.md`, where T5.0
     recorded the four fixtures.
  2. **Test** (RED): each of the four proven cases — two confirmed namesakes; `keep_source` on one
     only; two daily-only namesakes; one confirmed plus one daily-only. Assert **both** sources are
     handled, and that each reason string names the note that actually caused it.

     **Reachability guardrail.** A test that cannot reach the defect is not RED. The reachability
     table above is not background — it dictates how each case must be driven. Cases 1-2 are
     wire-path-only today, so exercise them by calling `_build_delete_source_actions` directly
     (the established pattern in `tests/test_instruction_render_delete_source_completion_gate.py`)
     or through a wire-path fixture. Driven through a markdown-path fixture they never reach the
     function at all — the `#116` filter drops them first — and pass vacuously while the defect
     lives. Cases 3-4 are live on both paths and must be asserted on both. Prove every one of the
     four non-vacuous by reverting the fix and observing it fail; a self-reported "confirmed RED"
     without that revert is not evidence.
  3. **Implement**: key the six collections on `item_key`. The OQ6 gate's denominator changes
     meaning — state what it now counts and why that is right, rather than making it pass.
  4. **Validate**: tests pass; `ruff` clean; the emitted shape is unchanged (CON-4).
  5. **Success**:
     - [ ] Two namesakes each get their own delete, or their own suppression, for their own reason
     - [ ] No reason string attributes one note's action to another

- [x] **T5.0c The paired consumer still collapses** `[activity: backend]` `[parallel: true]`

  Added 2026-09-07 by T5.0b's implementer, which found it in its shape-grep, deliberately left it
  alone as out of scope, and recorded it in `docs/tomo/scripts/lib/render_actions.md`.

  `instructions-diff.py`'s `derive_expected()` derives the **expected** `delete_source` count with
  the exact shape T5.0b removed from the emitter: `confirmed_stems` is a set of bare stems, and the
  `daily_only_seen` loop suppresses a daily-only note's expected deletion on a stem match against
  it. Two of T5.0b's four cases — two daily-only namesakes, and one confirmed plus one daily-only —
  now emit one more `delete_source` than this module expects.

  **The user-visible consequence.** `derive_expected` feeds the coverage line
  `delete_source coverage: expected=N actual=M [DIFF]`. So `/inbox` reports drift on a **correct**
  instruction set. Nothing is misdeleted and nothing is missed — the instruction set is right and
  the differ's expectation is stale — but the report is the artefact the user reads to decide
  whether Pass 2 did the right thing, and it now says something false about a correct run.

  **Why this is scheduled here rather than backlogged.** T6.4 is live validation against the real
  vault — the first run in which subfolder namesakes actually occur. A spurious `[DIFF]` fires
  exactly there, during the one run that judges whether the spec worked.

  **The trap, named by T5.0b's implementer: do not mechanically copy `_origin_key`.** This module
  has its own key semantics — `_keys_match` tolerates an inbox-prefix asymmetry that a
  set-equality dedup does not. A key that compares equal under `_keys_match` can be unequal as a
  set member, so the mixed keyed/keyless case is where a naive port breaks. Work out what this
  module needs; do not assume the emitter's helper is it.

  Note that the other two cases are already parity-correct: the confirmed-namesake and
  `keep_source` paths dedup on `_confirmed_key`, which is item_key-based. The divergence is
  daily-side only.

  1. **Prime**: read `derive_expected()` end to end, `_keys_match`, and `_confirmed_key`. Read the
     "Paired Consumer Still Collapses (open)" section in
     `docs/tomo/scripts/lib/render_actions.md`, where T5.0b recorded the analysis
     `[ref: SDD/ADR-1, ADR-2]`.
  2. **Test** (RED): the two affected cases — two daily-only namesakes, and one confirmed plus one
     daily-only. Assert the derived expectation **matches** what the emitter actually produces for
     the same input, so the test pins the two modules against each other rather than against a
     hand-written number. Add a case for the mixed keyed/keyless input the `_keys_match`
     asymmetry makes dangerous. Prove each red by reverting the fix, not by self-report.
  3. **Implement**: key the two collections on the note's identity, in whatever form this module's
     comparison semantics actually require.
  4. **Validate**: tests pass; `ruff` clean. Delete the stale `NOTE` at `derive_expected`'s head —
     it defers this "until T2.3b", and `phase-2.md:153` shows T2.3b is `[x]`. Also correct
     `_confirmed_key`'s docstring, which still claims the markdown path mints no `item_key`; commit
     `2d06654` made that false.
  5. **Success**:
     - [x] A correct instruction set reports `[OK]`, not `[DIFF]`, for both affected cases
     - [x] No stale comment survives that defers this work to an already-closed task

- [x] **T5.1 Source links disambiguate on collision** `[activity: backend]` `[parallel: true]`

  **Caveat inherited from T5.0, recorded by its implementer.** The two parser paths disagree on
  what an absent key means: `build_from_wire` falls back to `w.get("item_key") or stem`, putting a
  **display stem into an identity field** when a wire carries no key, while the markdown path
  leaves it `None`. Real documents always carry the key, so they agree in practice, and the golden
  parity tests strip the field from both sides and say why. But the wire's fallback is an ADR-2
  violation in waiting — a field holding something its name does not describe — and this task
  changes what source links carry, so decide deliberately whether to make both paths agree on
  `None` rather than inheriting the divergence.

  **Superseded 2026-09-06 — T5.0 already closed the identity half of this.** This block used to
  say the markdown path minted no `item_key` and that T5.1 would fix it. That is no longer true and
  chasing it would redo solved work:

  - `suggestion-parser.py` `main()` now mints `item_key` at all four `confirmed_items.append` sites
    (`:2034`, `:2247`, `:2272`, `:2330`) by joining the suggestions document on the suggestion id.
    The rendered document is still lossy, but it is not the only input — `synthesis-conductor.md:105`
    already passes `--suggestions-doc`, and the doc carries the path keyed by the id the markdown
    heading shows.
  - T2.7's adversarial case now **passes through the markdown path**. T2.8's
    `TestKnownLimitMarkdownPathMintsNoKey` became `TestMarkdownPathAlsoCarriesTheKey`, a positive
    value trace asserting two `[[Dresden]]` namesakes bind **distinct** keys. It previously returned
    `RESULT: OK … RC=0` on that path; it does not any more.
  - The join **refuses to guess**: an edited `Source:` line whose stem no longer matches its id
    binds no key at all rather than binding the wrong one.

  **What remains for this task is the display half, and only that.** Identity is solved; two
  suggestions for two different `Dresden` notes still render as `[[Dresden]]` twice, so the user
  cannot tell them apart in the document they approve. That is what path-qualifying on collision
  fixes, and it is a `stem`-side, display-only change (ADR-2) — do **not** put a path into an
  identity field or take one out of `item_key` to achieve it.

  1. **Prime**: Read the display sites in `suggestions-reducer.py` — enumerate them yourself
     rather than working from a count `[ref: SDD/Implementation Gotchas]`. Read the verified
     evidence in the spec README: when two files share a basename the vault itself writes
     `[[100 Inbox/Images/Test|Test]]`, path plus alias.
  2. **Test** (RED):
     - one item with a given filename → its source link is the plain filename
       `[ref: PRD/AC Feature 2]`
     - two items sharing a filename → each link carries enough location to be distinct, and
       each resolves to its own note
     - the suggested name shown for a subfolder note is still `Dresden`, never a path-derived
       string `[ref: PRD/AC Feature 2]`
     - a run with no collision produces a byte-identical document — **the mechanism is the
       existing flat-inbox golden**, `tests/fixtures/034-t3-4-flat-golden/suggestions.md`,
       asserted whole-string by `tests/test_034_t3_4_phase3_gate.py`. Do not invent a new
       baseline: "before this task" is circular, because before the change there is no prior
       state to diff against. That golden was rendered by the pipeline at `ee44cb3` — the commit
       preceding Phase 1 — so it pins the stronger claim, byte-identical to before the whole
       spec. If path-qualification leaks into a no-collision run, that test goes red on the
       whole document string, not on selected fields.
  3. **Implement**: detect same-filename groups while rendering — the renderer already sees
     every item — and path-qualify only those.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] The user can tell two same-named suggestions apart, and each link goes to the right
           note `[ref: PRD/Business Rule 5]`

- [x] **T5.2 Pass 1 proposes a distinct name on a destination clash** `[activity: backend]`

  1. **Prime**: Read `_dest_join` (`lib/render_actions.py:484`) — it builds the destination from
     the title with no collision check — and `_disambiguate_filename` (`:444`), which guards
     only the intermediate rendered file within one render run, not the vault destination.
  **Amended 2026-09-07 after the TDD gate blocked the original four cases.** Two were
  untestable as written and one named no mechanism. The verified facts behind the amendment:

  - **The reducer already has Kado** (`suggestions-reducer.py:2104`, added for the I38 daily-note
    existence check). No new vault access is needed for the third case. But it **fails open** —
    no Kado config or an unreachable Kado leaves `kado_client = None` — and it is skipped entirely
    under `--fan-resolve` and `--no-kado`.
  - **`_dest_join` (`lib/render_actions.py:489`)** builds the destination from the title with no
    collision check, and **`_disambiguate_filename` (`:449`)** guards only the intermediate
    rendered file within one render run, never the vault destination. Both confirmed.

  Put the tests in `tests/test_034_t5_2_destination_clash_proposal.py`.

  2. **Test** (RED):
     - two items whose names would produce one destination → the second gets a distinct
       proposed name `[ref: PRD/AC Feature 7]`
     - an item whose destination already exists in the target folder gets the same treatment —
       a distinct proposed name AND the reason surfaced in the document. PRD says "surfaced
       there too"; matching the run-internal case is the reading that serves the user story,
       because a proposal they can accept unchanged beats a warning they must act on
     - **Kado absent or unreachable → the vault half of the check silently does not run, and the
       document renders exactly as it does today.** Not an error, not a fabricated collision.
       Pass 1 is advisory and T5.3 is the binding guard `[ref: SDD/ADR-4]`, so a Pass-1 check
       that cannot run costs a convenience, not a safety property. Assert this with
       `kado_client=None` and again with `--fan-resolve`
     - the proposed name is an ordinary editable suggested name — same field, same shape as any
       other, carrying no marker that would make Pass 2 treat it differently
     - a no-clash run is **byte-identical to `tests/fixtures/034-t3-4-flat-golden/suggestions.md`**,
       asserted whole-string by `tests/test_034_t3_4_phase3_gate.py`. Do not mint a fresh golden
       after the change — that is circular, and it is the exact shape T5.1's case 4 was blocked
       for. That fixture was rendered by the real pipeline at `ee44cb3`, before Phase 1

     **Relocated to T5.3, not dropped**: "the user's own edit to that name is honoured"
     `[ref: PRD/AC Feature 7, Pass-1 criterion 2]`. The criterion belongs to Pass 1 — the
     proposal must not bind — but it is only *observable* in Pass 2, because the user edits the
     document after Pass 1 has finished rendering. Asserting it here would test nothing: no edit
     has happened yet. T5.3 owns the assertion; T5.2 owns the property that makes it possible,
     which is the editable-field case above.
  3. **Implement**: detect the clash while rendering the suggestions document and adjust the
     proposed name, leaving it editable exactly as any other suggested name. The vault half
     reuses the existing `kado_client`; do not open a second one, and do not make the run fail
     when it is `None`.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [x] The common case never reaches the Pass-2 guard `[ref: SDD/ADR-4]`
     - [x] A missing Kado degrades the check, never the run

  **Retrofitted 2026-09-07** for the case-folding requirement `656cc68` added to T5.3, so both
  passes agree on what "the same place" means. Destinations compare `casefold()`-equal in both
  halves; only the comparison folds, and `_clash_reason` shows each destination spelled the way
  its author wrote it plus, on a case-only clash, the words "differs … only in case". The vault
  half reads one `list_dir(location, depth=1)` per destination folder rather than probing
  `note_exists` per destination — a probe would answer only what Kado's own case semantics
  decide, which CON-7 forbids this spec from measuring.

  **Out of scope, found while sweeping for destination-composition sites**: an approved
  atomic and an approved MOC proposal can compose the same destination (an atomic named
  `Travel (MOC)` filed into the MOC folder). `_build_create_moc_actions` dedups create_moc
  against create_moc only, `_build_move_note_actions` has no guard, and this Pass-1 check
  compares atomics against atomics. T5.3's brief does not cover it either. Recorded in
  `docs/tomo/scripts/suggestions-reducer.md`, not fixed here.

- [x] **T5.3 Pass 2 validates destinations** `[activity: backend]`

  1. **Prime**: Read `[ref: SDD/Complex Logic]` — the four-action walkthrough — and
     `_build_move_asset_actions` (`lib/render_actions.py:630-690`) as the reporting pattern to
     follow.

     **Copy its reporting shape, invert its resolution.** That guard is **first-claim-wins**: the
     first attachment keeps the destination and the second is skipped. This one drops **both**
     claimants `[ref: SDD/ADR-4]`, because choosing between two names the user set deliberately
     would itself be a guess. The two behaviours look alike in the code and differ in the one
     place that matters, so a shape copied without noticing the inversion ships a guard that
     keeps one claimant — which is the silent overwrite this task exists to prevent, wearing the
     appearance of a working guard.
  2. **Test** (RED):
     - the user edits two approved items to one name → **neither** move is emitted, and the
       clash is reported prominently `[ref: PRD/AC Feature 7]`
     - a name clashing with a note already in the target folder → same treatment
     - the user corrects one name and re-runs → both are emitted normally, no need to restart
       the run. **Test this as statelessness of the guard, not as an edit round-trip**: invoke
       the validation pass with clashing input and assert both are dropped, then invoke it again
       with corrected input and assert both are emitted. It must carry nothing between
       invocations — no memo of the earlier clash, no suppression that outlives the input that
       caused it. The markdown-edit path is already covered by the relocated case below; do not
       re-test the parser here, or this case ends up proving the parser works while saying
       nothing about the guard
     - a run with no clash emits exactly the actions it emits today — whole-list comparison,
       not selected fields.

       **Capture the baseline BEFORE writing any implementation, and commit it first.** There is
       no golden action list in this repo — the two earlier fixes in this phase both pointed at
       a rendered-document golden, and no equivalent exists for `build_actions`' output. So one
       must be made, and the order is what makes it evidence rather than a tautology:

       1. On the current HEAD, with no T5.3 code written, drive a no-clash fixture through the
          real `build_actions` and record the whole action list to a fixture file.
       2. Commit that fixture on its own, before the implementation.
       3. Implement, then assert the same fixture's action list is unchanged.

       Recording it after the change would pin whatever the new code happens to produce — the
       exact circularity T5.1's and T5.2's regression cases were blocked for. Note in the
       fixture's own header which commit produced it, as `tests/fixtures/034-t3-4-flat-golden/`
       does
     - **Two names differing only in case are a clash** — `Dresden` and `dresden` → neither move
       is emitted, same treatment as any other clash. Assert it for both halves: two items in
       the run, and an item against a note already in the target folder
     - the report for a case-only clash **says so** — the user must be told the two names differ
       only in case, not merely that they collide. On a case-sensitive filesystem those are two
       visibly different names, and "duplicate name" alone would read as a bug
     - **Relocated here from T5.2 on 2026-09-07**: the user's own edit to a Pass-1 disambiguated
       name is honoured `[ref: PRD/AC Feature 7, Pass-1 criterion 2]`. The criterion is Pass 1's —
       its proposal must be a starting point, not a decision — but only Pass 2 can observe it,
       because the edit happens after Pass 1 has rendered. Take a document where T5.2 proposed a
       distinct name, edit that name to something else, and assert Pass 2 uses the user's name
       verbatim: it must not re-disambiguate, revert to the proposal, or treat a
       Pass-1-adjusted name as special in any way. T5.2 proves the field is an ordinary editable
       one; this proves nothing downstream second-guesses it.
  **Case folding is fail-safe, not case-blind — added 2026-09-07.** T5.2's implementer named
  exact-string destination equality as the assumption its diff could not verify, and CON-6
  records this filesystem as case-insensitive, *verified on this host*. But Tomo is not only run
  here: on a case-sensitive filesystem `Dresden.md` and `dresden.md` really are two files, so
  folding invents a clash — and ADR-4 drops **both** claimants, so a false positive costs two
  legitimate moves.

  Fold anyway, because the two errors are not comparable:

  | | case-insensitive FS | case-sensitive FS |
  |---|---|---|
  | fold | correct — the overwrite is prevented | false clash → both dropped, reported, user renames — **recoverable** |
  | do not fold | **silent overwrite — unrecoverable** | correct |

  One column loses a note; the other costs a rename. That asymmetry, not a guess about which
  filesystem is underneath, is the reason. It also cannot be resolved by measurement: CON-7
  forbids any task in this spec from a live vault run, so nothing here may probe Kado's real
  case semantics. Do not try; assume the folding filesystem and say so in the report.

  3. **Implement**: a validation pass over the built action list, run after `build_actions`,
     that removes clashing claimants and records a report. Compare destinations
     case-insensitively per the block above, and keep the original casing in the report — a user
     told their name collides needs to see the name they actually typed.

     **Reach the vault the way T5.2 does: one cached `list_dir(folder, depth=1)` per distinct
     destination folder, never a per-name `note_exists` probe.** This is not a style preference.
     A probe returns whatever Kado's own case semantics decide, and CON-7 forbids this spec from
     running against a live vault to find out what those are — so a probe would make the guard's
     correctness depend on an unmeasured behaviour. A listing returns the folder's real
     filenames, which puts the fold in Tomo where a test can reach it, and supplies the vault's
     own spelling for the report. T5.2 arrived at this deliberately (`suggestions-reducer.py`,
     `_vault_folder_notes`); read it before choosing an approach here. If the proposal and the
     guard consult the vault differently, they will disagree about what is taken — which is the
     same drift that produced T5.0c one file over.

     Cache the listing per normalised folder, not per raw `location` string: T5.2 shipped that
     bug and fixed it in `00edb7e`, where a trailing slash produced two listings for one folder.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [x] A clash cannot reach the executor `[ref: PRD/AC Feature 7]`
     - [x] The halt is recoverable by renaming and re-running Pass 2

  **Closed 2026-09-07.** `validate_destinations` + `make_folder_listing` in
  `lib/render_actions.py`, wired in `instruction-render.py` between building and
  resolving. Baseline recorded first at `9afcf73` and committed alone
  (`tests/fixtures/034-t5-3-actions-golden/`). Every guarantee proven red by
  reverting it; one case was found vacuous that way and rewritten.

  **Two findings the next tasks need.**

  **(a) A dropped move had to take its paired `delete_source` with it** — the
  trap this task's brief did not name. `_build_delete_source_actions` emits a
  delete for every origin its atomics consume plus one for the audio peer.
  Dropping the move alone would have deleted the user's inbox note *and* its
  audio while refusing to file the rendered atomic — the guard causing the loss
  it exists to prevent, at the CON-4 boundary. The withdrawal joins on the
  resolved path (ADR-1) and is also correct for a partial drop: an origin with
  one clashing atomic of two is no longer fully consumed, which is exactly the
  OQ6 gate's defer condition.

  **(b) `instructions-diff` was repaired here, not deferred.** A withheld move
  is neither an expected `move_note` nor an expected `delete_source`, so the
  audit reported `RESULT: FAIL — count or coverage mismatch` on a correct
  instruction set, and `synthesis-conductor.md:3e` makes that fatal — the run
  would have halted blaming Tomo for drift instead of naming the clash. Unlike
  T5.0c's divergence, which pre-existed its diff, this one is created by T5.3,
  so it is T5.3's to repair (`_subtract_destination_clashes`, 0.16.0).

  **Out of scope, found while sweeping for destination composition and claim
  tracking** — recorded in `docs/tomo/scripts/lib/render_actions.md`, not fixed:
  `_build_create_moc_actions`'s `by_dest` compares destinations by **exact
  string**, so two approved MOC proposals differing only in case both emit and
  the second overwrites the first (the `#67` failure that guard exists to
  prevent, reachable again under CON-6); the atomic-vs-MOC composition T5.2
  already recorded; and `render_resolve.py:213`'s `create_moc_by_dest`, the
  paired consumer of the first.

- [x] **T5.4 An attachment clash keeps its note in the inbox** `[activity: backend]`

  1. **Prime**: Read `[ref: SDD/ADR-6]`. Read `_build_move_asset_actions`, particularly the
     `seen` set (same file referenced twice — a duplicate, **not** a clash) versus `claimed`
     (two different files, one destination). Read
     `tests/test_031_t2_4_destination_collision_guard.py:121`, which asserts the behaviour being
     reversed.

     **Three preconditions verified 2026-09-07 — do not re-derive, but do not assume they stay
     true if you change these files:**

     - `test_collision_does_not_suppress_the_notes_own_move_note` is still at
       `test_031_t2_4_destination_collision_guard.py:121`. The instruction points at real code.
     - `seen` and `claimed` are still distinct in `_build_move_asset_actions`
       (`render_actions.py:651-679`). T5.3 reworked this file heavily; the distinction survived.
     - **T5.3's `validate_destinations` does not touch attachments.** It filters on
       `action == "move_note"` and `delete_source` only, never `move_asset`. So the two guards
       do not collide — and that is exactly why the gap below exists.

     **The gap the two guards leave between them.** T5.3 withdraws a paired `delete_source`
     when *it* drops a move, via its own `withdrawn_paths`. You suppress a move for a different
     reason — an attachment clash — and T5.3's bookkeeping knows nothing about your suppression.
     So unless you withdraw the paired delete yourself, a note that stays in the inbox has its
     source deleted, and the note is gone. That is worse than the bug this task fixes: ADR-6
     exists so a note is never filed while depending on a file left behind, and deleting the
     source instead loses it outright. Neither task's text mentions the other, because T5.4 was
     written before T5.3 existed.
  2. **Test** (RED):
     - two different files sharing a basename, each embedded by its own note → the second file
       is not filed **and neither is its note** `[ref: PRD/AC Feature 8]`
     - the first note and its attachment are filed normally — one clash does not hold up another
     - one file embedded by two notes → filed once, both notes move. Unchanged; this is a
       duplicate reference, not a clash.

       **"Unchanged" needs a baseline, and the baseline must predate your code.** Same
       requirement, same reason, same precedent as T5.3: record a one-file/two-notes fixture
       through the real `build_actions` on current HEAD with no T5.4 code written, commit that
       fixture alone, then implement and assert it unchanged. See
       `tests/fixtures/034-t5-3-actions-golden/` for the shape, including a README naming the
       commit that produced it. Recorded afterwards it pins whatever your new code happens to
       do, which is what "provably untouched" must not mean

     - **a suppressed move withdraws its paired `delete_source`** — the note stays in the inbox,
       so deleting its source would destroy it. Assert the origin delete AND the audio-peer
       delete are both gone, and that a `keep_source` item (which has no paired delete) reports
       none rather than a phantom one
     - the user renames one file and re-runs → everything files normally. **Test this as
       statelessness**, the way T5.3's equivalent case was narrowed: invoke with the clashing
       input and assert the suppression, invoke again with the renamed input and assert
       everything files. Nothing may carry between invocations. Do not fabricate run state
  3. **Implement**: link the attachment clash to its note's move. **Invert**
     `test_collision_does_not_suppress_the_notes_own_move_note` — a red test here is the
     intended change, not a regression in your own work `[ref: SDD/ADR-6]`.

     **Where it goes — decided 2026-09-07, because the code structure forces it.** A TDD gate
     blocked this task for leaving the location open, and the ordering inside `build_actions`
     settles it rather than leaving it to taste:

     ```
     render_actions.py:1841   move_notes    = _build_move_note_actions(...)
     render_actions.py:1843   move_assets, skipped_assets = _build_move_asset_actions(...)
     render_actions.py:1852   out.extend(_build_delete_source_actions(...))
     ```

     The paired `delete_source` actions do not exist yet when `_build_move_asset_actions` runs.
     So suppression cannot withdraw them inline — there is nothing there to withdraw. Build it
     as a **sibling post-pass over the finished action list**, the same shape as
     `validate_destinations`:

     - It takes the built `actions` plus `skipped_assets`. Both already cross the boundary:
       `build_actions` returns `(actions, skipped_assets)` and `instruction-render.py:525`
       already unpacks them, so the routing needs no new plumbing.

     **But a skipped asset does not currently say whose note it is — and that is your first
     change.** Corrected 2026-09-07 after a gate caught the claim above overstating the case.
     A skipped entry is `{"source", "destination", "reason", "kind"}`
     (`render_actions.py:643-676`); nothing on it names the note that embedded the attachment,
     so a post-pass receiving it cannot tell which move to suppress.

     The information is already in scope and merely unrecorded. The loop is
     `for m in manifest: for path in m.get("attachments") or []:` — at the moment of skipping,
     `m` is the manifest entry, carrying `item_key` and `source_path`. So:

     - Record the owning note's **`item_key`** on each skipped entry. `item_key`, not the stem:
       it is the identity field (ADR-1, ADR-2), and two namesake notes in different subfolders
       can each embed an attachment. A stem-keyed link would suppress the wrong note's move —
       the exact defect this spec has spent six tasks removing.
     - Join it to the move by matching against `move_note.source_inbox_item`, which
       `_build_move_note_actions` derives from that same `item_key` via `resolve_source_path`
       (`:596-600`). Derive it the same way, through the same helper — do not compose
       `<inbox>/<stem>.md` by hand. That hand-composition is what T5.0 found silently dropping
       every subfolder note in Pass 2.
     - **Assert the join on a subfolder note**, where a naive inbox-root composition produces a
       different path and would silently match nothing. A test using only root-level notes
       cannot tell a correct join from a broken one.
     - `skipped_assets` is also rendered for the user today. Adding a field must not change that
       output; check its consumers before deciding the field name.
     - Wire it in `instruction-render.py` beside `validate_destinations` (`:542`), which is
       already the place where post-build passes drop moves and report.
     - **Share the delete-withdrawal mechanism with `validate_destinations`; do not copy it.**
       That function already withdraws an origin delete and an audio-peer delete for a move it
       drops. A second copy of that logic is the duplication `docs/XDD/backlog.md` already
       records twice for this file, and the drift it produced in T5.0c cost a task of its own.
     - Do **not** extend `validate_destinations` itself to consume `skipped_assets`. Its
       contract is destination contention between claimants; an attachment that could not be
       filed is a different cause with a different report, and merging them makes one function
       answer two questions.

     **The two passes must compose.** A note can be dropped by `validate_destinations` for a
     destination clash *and* own a skipped attachment. Withdrawing the same delete twice must
     not double-count in any report, and a note dropped by one pass must not be reported as
     newly dropped by the other. Assert one case where both apply to the same note.

     **The user must be able to tell the two reasons apart.** "Two items claim one destination"
     and "its attachment could not be filed" are different problems with different remedies —
     rename one note, versus rename one file. A reader who cannot tell which happened cannot
     act. Whether that is a second section or a distinguishable reason line is yours to choose;
     that it is distinguishable is not.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [x] No note is filed into the permanent collection while depending on a file left in the
           inbox `[ref: PRD/AC Feature 8]`
     - [x] The duplicate-reference path is provably untouched

  **Closed 2026-09-07.** `suppress_moves_for_unfiled_attachments` in
  `lib/render_actions.py`, a sibling post-pass wired beside `validate_destinations` in
  `instruction-render.py`. The baseline was recorded first at `1edaccd` and committed alone
  (`tests/fixtures/034-t5-4-duplicate-reference-golden/`). The withdrawal mechanism was
  extracted from `validate_destinations` (`_paired_delete_candidates`,
  `_drop_moves_with_paired_deletes`) and is shared, not copied. Every guarantee proven red by
  reverting it; reverting the join to a `<inbox>/<stem>.md` composition suppressed an unrelated
  root-level namesake and filed the real owner, and two assertions were found hollow that way
  and rewritten. `test_031_t2_4_destination_collision_guard.py:121` was inverted;
  `031/plan/phase-2.md:85` is left intact as the historical record.

  **Three findings the next tasks need.**

  **(a) A skipped attachment already broke the audit before this task.** Measured on HEAD:
  `derive_expected` counts one expected `move_asset` per attachment path on the confirmed
  items while `_build_move_asset_actions` emits none for a refused one, so a clash produced
  `move_asset expected=2 actual=1 [DIFF]` and `RESULT: FAIL` on a correct instruction set —
  and step 3e of `synthesis-conductor.md` makes that fatal. Spec-031-era, unreachable until
  recursion. Closed here (`_subtract_skipped_assets`) because T5.4 makes the clash a normal
  outcome. `_subtract_destination_clashes` was renamed `_subtract_withheld_moves` and is now
  called for both withholding lists.

  **(b) The SDD and the PRD disagree about the first claimant.** `solution.md`'s "Complex
  Logic" walkthrough, step 3, says that on an attachment clash "**neither** is emitted".
  PRD Feature 8's second acceptance criterion says the first note and its attachment are
  filed normally, and the plan repeats it. The PRD was followed. Recorded, not resolved.

  **Out of scope, found while sweeping for exact-string destination keys** — recorded in
  `docs/tomo/scripts/lib/render_actions.md`, not fixed: `_build_move_asset_actions`'s
  `claimed` dict keys on the exact destination string, so `A/Ufer.jpg` and `B/ufer.jpg` both
  emit and the second overwrites the first under CON-6 — with no skip recorded, so this
  task's suppression never fires. A fourth instance of the shape T5.3 recorded three of.

- [x] **T5.5 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Read the rendered output as prose. Render a suggestions document containing every
    combination — no clash, a name clash, an attachment clash, a subfolder note, a namesake
    pair — and read it end to end as English. This finds a class of defect no test reaches;
    spec 033 found five that way after a 3000-test suite and two review gates had passed.
    An agent reporting "I read it and it is fine" reproduces the failure — render, then have
    the orchestrator or the user read it.
  - Mutation-prove each guard: disable it, confirm the specific test dies, restore.
  - Bump `# version:` on every modified file.
