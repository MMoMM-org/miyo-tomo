---
title: "Phase 5: Display and destination guards"
status: pending
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

- [ ] **T5.0b The delete bookkeeping in `render_actions` still keys on the stem** `[activity: backend]`

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
  3. **Implement**: key the six collections on `item_key`. The OQ6 gate's denominator changes
     meaning — state what it now counts and why that is right, rather than making it pass.
  4. **Validate**: tests pass; `ruff` clean; the emitted shape is unchanged (CON-4).
  5. **Success**:
     - [ ] Two namesakes each get their own delete, or their own suppression, for their own reason
     - [ ] No reason string attributes one note's action to another

- [ ] **T5.1 Source links disambiguate on collision** `[activity: backend]`

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
     - a run with no collision produces a byte-identical document to before this task
  3. **Implement**: detect same-filename groups while rendering — the renderer already sees
     every item — and path-qualify only those.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] The user can tell two same-named suggestions apart, and each link goes to the right
           note `[ref: PRD/Business Rule 5]`

- [ ] **T5.2 Pass 1 proposes a distinct name on a destination clash** `[activity: backend]`

  1. **Prime**: Read `_dest_join` (`lib/render_actions.py:484`) — it builds the destination from
     the title with no collision check — and `_disambiguate_filename` (`:444`), which guards
     only the intermediate rendered file within one render run, not the vault destination.
  2. **Test** (RED):
     - two items whose names would produce one destination → the second gets a distinct
       proposed name `[ref: PRD/AC Feature 7]`
     - the user's own edit to that name is honoured — the proposal is a starting point
     - an item whose destination already exists in the target folder is surfaced too
     - a run with no clash proposes nothing new
  3. **Implement**: detect the clash while rendering the suggestions document and adjust the
     proposed name, leaving it editable exactly as any other suggested name.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] The common case never reaches the Pass-2 guard `[ref: SDD/ADR-4]`

- [ ] **T5.3 Pass 2 validates destinations** `[activity: backend]`

  1. **Prime**: Read `[ref: SDD/Complex Logic]` — the four-action walkthrough — and
     `_build_move_asset_actions` (`lib/render_actions.py:630-690`) as the reporting pattern to
     follow. Note the deliberate difference: that guard is first-claim-wins, this one drops both
     `[ref: SDD/ADR-4]`.
  2. **Test** (RED):
     - the user edits two approved items to one name → **neither** move is emitted, and the
       clash is reported prominently `[ref: PRD/AC Feature 7]`
     - a name clashing with a note already in the target folder → same treatment
     - the user corrects one name and re-runs → both are emitted normally, no need to restart
       the run
     - a run with no clash emits exactly the actions it emits today — whole-list comparison,
       not selected fields
  3. **Implement**: a validation pass over the built action list, run after `build_actions`,
     that removes clashing claimants and records a report. Check surviving destinations against
     the vault.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] A clash cannot reach the executor `[ref: PRD/AC Feature 7]`
     - [ ] The halt is recoverable by renaming and re-running Pass 2

- [ ] **T5.4 An attachment clash keeps its note in the inbox** `[activity: backend]`

  1. **Prime**: Read `[ref: SDD/ADR-6]`. Read `_build_move_asset_actions`, particularly the
     `seen` set (same file referenced twice — a duplicate, **not** a clash) versus `claimed`
     (two different files, one destination). Read
     `tests/test_031_t2_4_destination_collision_guard.py:121`, which asserts the behaviour being
     reversed.
  2. **Test** (RED):
     - two different files sharing a basename, each embedded by its own note → the second file
       is not filed **and neither is its note** `[ref: PRD/AC Feature 8]`
     - the first note and its attachment are filed normally — one clash does not hold up another
     - one file embedded by two notes → filed once, both notes move. Unchanged; this is a
       duplicate reference, not a clash
     - the user renames one file and re-runs → everything files normally
  3. **Implement**: link the attachment clash to its note's move. **Invert**
     `test_collision_does_not_suppress_the_notes_own_move_note` — a red test here is the
     intended change, not a regression in your own work `[ref: SDD/ADR-6]`.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] No note is filed into the permanent collection while depending on a file left in the
           inbox `[ref: PRD/AC Feature 8]`
     - [ ] The duplicate-reference path is provably untouched

- [ ] **T5.5 Phase Validation** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Read the rendered output as prose. Render a suggestions document containing every
    combination — no clash, a name clash, an attachment clash, a subfolder note, a namesake
    pair — and read it end to end as English. This finds a class of defect no test reaches;
    spec 033 found five that way after a 3000-test suite and two review gates had passed.
    An agent reporting "I read it and it is fine" reproduces the failure — render, then have
    the orchestrator or the user read it.
  - Mutation-prove each guard: disable it, confirm the specific test dies, restore.
  - Bump `# version:` on every modified file.
