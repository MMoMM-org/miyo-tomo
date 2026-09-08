---
title: "Phase 6: Cost history, integration and live validation"
status: in_progress
version: "1.0"
phase: 6
---

# Phase 6: Cost history, integration and live validation

## Phase Context

**GATE**: read these before starting.

**Specification References**:
- `[ref: PRD/Feature 6]` and `[ref: PRD/Success Metrics]`
- `[ref: SDD/Data Storage Changes; cost_history]`
- `[ref: SDD/Quality Requirements]`
- `[ref: SDD/Constraints; CON-1, CON-7]`

**Key Decisions**:
- The container cannot see `docs/`, so the run writes its cost entry into the instance's own
  persistent state. Transcribing a notable run into the repository's cost log stays a
  deliberate host-side act.
- Live validation is the user's to run. No task here may attempt it `[ref: SDD/CON-7]`.

**Dependencies**: Phase 5 complete.

---

## Tasks

- [x] **T6.0 The three destination keys Phase 5 did not fold** `[activity: backend]`
      — **Accepted 2026-09-08.** First task of Phase 6, ahead of T6.1.

  Phase 5 folded case into three destination comparisons and left three more, each found by a
  shape-grep and recorded rather than fixed because folding them changes behaviour rather than
  addressing. They are collected here because they are one shape, and because two of them are
  an emitter and its paired consumer — the exact pairing that cost this spec a task of its own
  when T5.0b moved and T5.0c did not.

  All three are live on HEAD under **CON-6**, which records this filesystem as case-insensitive,
  *verified on this host*.

  | # | site | what happens today |
  |---|---|---|
  | 1 | `_build_create_moc_actions`'s `by_dest` | `Travel (MOC)` and `travel (MOC)` both emit a `create_moc`; the second overwrites the first on apply, **dropping the first's children** — the `#67` failure that guard exists to prevent |
  | 2 | `render_resolve.py:213`'s `create_moc_by_dest` | keys the same composed destination by exact string; the paired consumer of (1) and must fold with it |
  | 3 | `_build_move_asset_actions`'s `claimed` | `A/Ufer.jpg` and `B/ufer.jpg` both emit a `move_asset`; the second overwrites the first, and **no skip is recorded — so T5.4's suppression never fires** and both notes are filed |

  **(3) is the one to weigh first.** It is not merely an unfolded key: T5.4 built a guard whose
  trigger is a recorded skip, and this path records none. The feature has a blind spot exactly
  where CON-6 says the filesystem will bite, and the user sees nothing — the notes file, the
  attachment is overwritten, no report mentions it.

  **Why folding is right here, same asymmetry as T5.3**: on a case-insensitive filesystem, not
  folding loses data and cannot be undone; on a case-sensitive one, folding costs a rename and
  can. That reasoning is recorded in T5.3's block and applies unchanged.

  **`seen` is not a fourth site — fold `claimed` only. Added 2026-09-08 while reading site (3).**
  `_build_move_asset_actions` keeps two exact-string collections and they are not the same shape.
  `claimed` keys the **destination**, and folding it is right for the reason above. `seen` keys the
  **source path**, and the T5.3 asymmetry inverts there:

  - Not folding `seen`, on a case-insensitive filesystem: `100 Inbox/Ufer.jpg` and
    `100 Inbox/ufer.jpg` are one file seen twice. The first moves; the second now meets a folded
    `claimed` and is **recorded as a collision skip**, so T5.4 keeps its note in the inbox. Wrong
    about the cause, conservative in effect, and *reported* — the user reads a line naming both
    paths and renames one.
  - Folding `seen`, on a case-sensitive filesystem: two genuinely distinct files collapse to one.
    One moves, the other is **dropped with no skip recorded at all** — the exact silence T5.4's
    guard exists to break, re-created one layer up.

  So: fold `claimed`, leave `seen` exact. That ordering is what makes the second bullet
  unreachable, and it is only safe *because* `claimed` folds — do not fold one without the other.
  A test must pin this pair, not just the collision.

  1. **Prime**: read `docs/tomo/scripts/lib/render_actions.md` — the T5.3 sweep records sites
     (1) and (2) with their reachability, the T5.4 section records (3). Read T5.3's
     `validate_destinations` and T5.2's `resolve_destination_clashes` for the folding form
     already in use (`casefold()`, not `.lower()` — `ß` folds to `ss` and these are German
     notes) `[ref: SDD/CON-6, ADR-4]`.
  2. **Test** (RED): each site's collision, proven red by reverting to exact comparison. For
     (3), additionally assert that a skip IS now recorded and that T5.4's suppression
     consequently fires — the point is not the fold but the guard it re-arms.
  3. **Implement**: fold (1) and (2) **together**; a fold on one without the other re-creates
     the emitter/consumer divergence this spec has already paid for twice. Reuse
     `lib/source_link.py`'s collision helpers where they fit rather than adding a fourth copy.
  4. **Validate**: tests pass; `ruff` clean; neither action golden re-recorded — if a no-clash
     run changes, that is a real regression, not a fixture to refresh.
  5. **Success**:
     - [x] Two MOC proposals differing only in case cannot silently drop one's children
     - [x] An attachment collision differing only in case records a skip, so T5.4's guard fires

  **Closed 2026-09-08** — `1afc14d` folds, `b9d34e1` reverts a fourth site that was tried and
  measured as redirecting rather than addressing. 11 tests; suite 3625 → 3636, ruff clean, both
  action goldens byte-identical. The fold's one downstream consequence — a case-only MOC pair
  now hard-fails `instructions-diff` instead of silently dropping children — is T6.0c.

- [ ] **T6.0b An atomic and a MOC can claim the same path, and nothing compares them**
      `[activity: backend]` — **PROPOSED 2026-09-08, not yet accepted.**

  Kept separate from T6.0 deliberately: this is not an unfolded key but a **missing comparison
  across two action kinds**, and closing it cascades.

  An atomic named `Travel (MOC)` filed into the MOC folder composes the same destination as a
  `create_moc` for `Travel (MOC)`. `_build_create_moc_actions` dedups create_moc against
  create_moc; `_build_move_note_actions` has no guard at all; T5.2's Pass-1 check compares
  atomics against atomics; T5.3's `validate_destinations` groups `move_note` only. No pass sees
  both kinds.

  Why it is its own task: dropping a `create_moc` cascades into the `link_to_moc` and
  up-preservation actions that target it. That is a behaviour change with its own blast radius,
  not an addressing fix, and it wants its own design rather than being folded into a
  case-folding sweep. Recorded by T5.2 in `docs/tomo/scripts/suggestions-reducer.md` and by
  T5.3 in `render_actions.md`.

- [x] **T6.0c The merge upstream of both folds still keys on the exact title**
      `[activity: backend]` — **Added 2026-09-08, accepted. Runs before T6.1.**

  **Inherited context — read this before the steps.** T6.0 folded three destination keys. It did
  not touch `_merge_proposed_mocs_by_name` (`suggestion-parser.py:1114`), which collapses approved
  Proposed MOCs resolving to one Name and keys `merged[name]` by the **exact** title. That function
  is upstream of every site T6.0 touched, and leaving it exact has a measured consequence T6.0
  introduced:

  `derive_expected` (`instructions-diff.py:278`) counts one expected `create_moc` per confirmed
  item with no destination comparison. Two confirmed items titled `Travel (MOC)` and
  `travel (MOC)` yield `counts['create_moc'] == 2`, while T6.0's folded `by_dest` emits **one**.
  The audit prints `create_moc expected=2 actual=1 [DIFF]` plus a per-item `[MISSING]` row, both
  of which set `hard_fail`, and `synthesis-conductor.md` step 3e is STRICT: stop and report the
  diff verbatim.

  **This is a change in failure mode, not new data loss.** Before T6.0 the run completed and
  dropped the merged proposal's children on apply. After it, the run stops — but the user reads
  what looks like Tomo drifting from its own instruction set, not "two of your MOC names collide",
  and cannot finish that run until they rename one proposal. Recorded at
  `docs/tomo/scripts/lib/render_actions.md` §"Found While Folding, Recorded Not Fixed".

  **Why upstream is the right place**: folding the merge removes the case-only pair before any
  consumer sees it. `by_dest`'s fold then becomes defence-in-depth (which is what its own comment
  already claims to be), and `derive_expected` counts what is actually emitted without needing a
  destination comparison of its own.

  **One claim this task must test, not inherit.** T6.0's implementer asserted the upstream fold
  "also closes the `in_set` bullet loss" — the case in which a `link_to_moc` targeting the losing
  spelling finds no in-set create_moc, keeps `target_moc_path: null`, and is dropped by
  `filter_unappliable_relationships` with the note's up-bullet. **That claim is unverified and the
  orchestrator doubts it**: `resolve_target_moc_paths`'s `in_set` keys the *survivor's* spelling,
  so a link minted from a user-written losing spelling still misses an exact lookup. Establish
  which is true by running it. If the bullet is still lost, say so and record it — do not fold
  `in_set`, which T6.0 measured as redirecting bullets into a different folder's MOC and reverted
  for that reason (`b9d34e1`).

  **Three call sites, and the two parser paths do not match.** `:411` is the wire path and
  merges once. The markdown path merges **twice** — per-document inside `parse_proposed_mocs`
  (`:1111`), then again over primary + fan proposals (`:2282`). The fold must be idempotent
  across that double merge, and the test must cover the path `derive_expected` actually
  consumes; it reads `confirmed_items` from `tomo-tmp/parsed-suggestions.json`, i.e. post-merge.

  **The merge must say what it did — added 2026-09-08, after T6.0c's fold shipped.** The fold
  widened what gets absorbed, and the merge is mute: no `[warn]`, no needs-attention line, no
  audit row. Every sibling guard in this spec surfaces its decision. Under **CON-2** the user
  approves on what the suggestions document says, so a run that emits one MOC where two were
  approved must say so. Raised by T6.0c's implementer as the assumption its diff could not verify.

  **Model it on the record that already exists, do not invent one.** `validate_destinations`
  (`render_actions.py:1030`) carries `case_only: bool` beside `kind`, and `_CASE_NOTE`
  (`:827`) is appended to the reason when it is set. `render_md.py:592-611` renders that as a
  lead section before the action list. Reuse that struct and that structural pattern.

  **Do not reuse T5.5's "Not filed" wording.** Nothing is withheld here — the MOC *is* created,
  once instead of twice, with the absorbed proposal's tags and items unioned in. "Not filed"
  would misdescribe the outcome, which is the exact class of defect T5.5 was written to remove.
  Take the shape (lead section, before the actions, names both spellings, cause plus remedy),
  not the words.

  **The plumbing crosses a process boundary, and that is where this will break.** Unlike
  `destination_clashes` and `attachment_suppressions`, which are computed inside
  `instruction-render.py` itself, this record is born in `suggestion-parser.py` and must survive
  a JSON round-trip. Three sites beyond the merge function, none of them a call site of it:

  | # | site | change |
  |---|---|---|
  | 1 | `suggestion-parser.py:434` | wire-path output dict — carry the record |
  | 2 | `suggestion-parser.py:2589` | markdown-path output dict — same |
  | 3 | `instruction-render.py:284` | read it back beside `confirmed_items` — **this is only a local variable** |
  | 4 | `instruction-render.py:832` | add it to the literal dict passed as `render_instructions_md`'s second argument, beside `destination_clashes` and `attachment_suppressions` |

  **(3) without (4) is a silent no-op.** `render_md.py` calls `metadata.get(...)` on the literal
  dict at `instruction-render.py:819-835` and never sees anything read at `:284`. Reading the
  record into a local and forgetting to add it to that dict raises no error, fails no
  renderer-level unit test, and simply never renders the section. The first BLOCK on this task
  caught this shape one level up; this is the same shape one level down.

  **The record must be reentrant across the two merge calls, or the fixture below cannot pass.**
  "Group per surviving name" solves collision *within* one call. The markdown path calls the
  function **twice**, and the second call has no memory of the first: stage 1 merges
  `Travel (MOC)` + `travel (MOC)` into one record, then stage 2 merges that already-merged
  one-entry list against the fan's `TRAVEL (MOC)` and — called fresh — emits a *second*
  independent record for the same survivor. Two records where the fixture asserts one, failing
  for a reason nothing in the plan names.

  The function already solves this for its own data, one line away from the problem.
  `member_stems` and `topic` ride as internal fields on the moc dict across repeated merge calls
  and are popped only at the end (`suggestion-parser.py:429-430` wire, `:2585-2586` markdown) —
  the merge site's own comment about "a name merged from multiple topics" is exactly this
  reentrancy. Give the record the same treatment: **carried as an internal field on the survivor
  moc, extended in place when a later call absorbs another spelling into an already-merged
  survivor, and lifted into the output at the same two sites where `member_stems` and `topic`
  are stripped.**

  **Strip test and paired-consumer count, but no schema test.** The internal field owes a test
  that it is popped like `member_stems` and `topic`, and a count that fails when a second
  consumer forgets it. It does **not** owe a schema test, and the gate cut one this plan
  originally asked for: `instructions.schema.json` closes each action `$def` and the top level,
  but exempts the `tomo` block by design (`:35` — "kept permissive... so Tomo can evolve the
  block without a coordinated round-trip"), which is where `destination_clashes` and
  `attachment_suppressions` already live. The record is popped before its dict becomes a
  `create_moc`, its lifted destination is a plain Python dict never schema-checked, and
  `suggestion-parser.py` calls no validator at all. A schema assertion here would assert a
  property of the schema file, true whatever the implementer does — the same true-by-construction
  shape Phase 5 shipped once. The strip test earns its place on consumer clarity, not validation.

  **Append in encounter order; do not dedup with a set.** The absorbed spellings list is built by
  append, matching the `tags` and `member_stems` folds it sits beside (`if tag not in
  head["tags"]: head["tags"].append(tag)` — ordered, unsorted) and `validate_destinations`'
  `dropped: [...]`. Because `primary_pmocs + fan_pmocs` puts primary first, encounter order is
  `travel (MOC)` then `TRAVEL (MOC)`, deterministically — **but only if the coalescing appends.**
  A `set()` is the natural instinct for "do not record the same absorption twice" and would make
  the order implementation-defined, which the two-stage fixture is the only case that exposes.

  **The record is a group per surviving name, not a pair.** `validate_destinations` already
  carries `dropped: [...]` inside one clash record (`render_actions.py:1034`) rather than one
  record per dropped claimant. Follow that: survivor plus a **list** of absorbed spellings. A
  pairwise `(survivor, absorbed)` tuple is the more natural first guess and it breaks the
  two-stage fixture below — a three-way collapse would emit two records where the plan asserts
  one.

  **A test that calls `render_instructions_md()` with a hand-built metadata dict proves the
  renderer and nothing else.** Build a real `suggestions.json` and drive `instruction-render.main()`,
  on the template of `_drive_render` in `tests/test_034_t5_4_attachment_clash_suppression.py:468`.
  This spec has been bitten five times by a shape with more copies than the plan named; the fifth
  was this very gap, caught by the gate before code.

  **Concrete assertions, not "distinguishable":**
  - the case-only pair records `case_only` true; an exact repeat records it false. Name the field
    and the value per scenario — "the two records differ" passes on any two records.
  - idempotence across the double merge needs a two-stage fixture: `Travel (MOC)` and
    `travel (MOC)` in the primary document (collapsed by the first merge), `TRAVEL (MOC)` in the
    fan document (only the second merge can see it). Assert one surviving `create_moc`, all three
    supporting-item sets unioned, and **one** record — not three, not two.

    **That fixture covers only half the reentrancy — corrected 2026-09-08 by mutation, after
    this plan and its gate had both approved it alone. A second, FOUR-way fixture is required;
    do not trim it back to three.** In the three-way case the stage-1 survivor is the first moc
    stage 2 encounters, so it *seeds* the merge carrying its own list and the third spelling is
    appended in place. The other half is the moc being **absorbed** itself being a survivor:
    both documents merge internally first (`Travel (MOC)` + `travel (MOC)` in the primary,
    `TRAVEL (MOC)` + `TrAvEl (MOC)` in the fan), so the fan's survivor arrives in stage 2
    carrying its own group, and only the carry-over line moves it across. Deleting that line
    left the three-way fixture **green**. Without it the fan pair's losing spelling vanishes
    from the report while its supporting item is still merged into the MOC — a silent
    under-report, the same CON-2 defect the record exists to fix, one level down. Assert the
    four-way fixture's absorbed list exactly: `["travel (MOC)", "TRAVEL (MOC)", "TrAvEl (MOC)"]`.
  - assert rendered markdown by substring, matching how the T5.3 and T5.4 tests check fields.
    Full-paragraph pinning breaks on the next copy edit.
  - a run with no merge renders no such section, and neither action golden is re-recorded.

  1. **Prime**: read `_merge_proposed_mocs_by_name` (`suggestion-parser.py:1114`) and its
     2026-06-17 decision comment — merge on Name only, first occurrence's parent kept. Read
     T6.0's block above for the folding form (`casefold()`, never `.lower()`) and the fail-safe
     asymmetry `[ref: SDD/CON-6, ADR-4]`. Read `b9d34e1`'s reverted-fold comment in
     `render_resolve.py` before considering any change there.
  2. **Test** (RED):
     - two approved Proposed MOCs titled `Travel (MOC)` and `travel (MOC)` merge into one, with
       `supporting_items`, `tags` and `member_stems` unioned — the same semantics the exact-name
       merge already has, so this is a merge and not a drop
     - the survivor keeps the spelling its author wrote; nothing folded is written back
     - `derive_expected` over the merged confirmation counts `create_moc == 1`, so the audit
       completes instead of hard-failing — assert the audit's own outcome, not just the count
     - the `link_to_moc` up-bullet (see the claim above). **The TDD gate traced this at HEAD
       `5acfffc` and the loss persists**: `in_set` keys `_moc_stem(title)` with no fold, so a
       link carrying the losing spelling verbatim misses the survivor's exact key, keeps
       `target_moc_path: null`, and is dropped by `filter_unappliable_relationships`. Pin it
       with a **hard-coded** assertion — `assert action["target_moc_path"] is None`, or the
       resolved path if the trace is wrong — never a branch that passes either way. Add a
       one-line comment naming the finding. Do **not** fold `in_set` to make it pass; a guard
       test goes RED if anyone does, and `b9d34e1` records why.
     - proven RED by reverting the merge key to the exact string
  3. **Implement**: fold the merge key. Do **not** fold `in_set`.
  4. **Validate**: full suite green; `ruff` clean; neither action golden re-recorded.
  5. **Success**:
     - [x] A case-only MOC pair completes a run instead of hard-failing its audit
     - [x] The up-bullet's fate is established by test rather than assumed either way

  **Closed 2026-09-08** — `1ec8b6e` folds the merge key, `b2ff78e` makes the merge report what it
  absorbed, `935d8f2` twin-writes that record like every sibling record. 19 tests; suite
  3636 → 3655, ruff clean, both goldens byte-identical, no schema or `instructions-diff` change.

  **The up-bullet verdict: it is lost, and that is now asserted rather than assumed.** T6.0's
  claim that this fold would close it was wrong — `in_set` keys the survivor's spelling, so a
  link minted from the losing one misses regardless. Pinned hard-coded at
  `target_moc_path is None`, with `in_set` untouched. The fix belongs to T6.0d, which also owns
  the larger finding that such a link renders as a tickable instruction rather than being dropped.

  **Reentrancy has two halves, and the plan's own fixture only reached one.** The three-way
  fixture cannot exercise the carry-over line — there the stage-1 survivor seeds stage 2 and its
  list is extended in place, so `.extend()` always receives `[]`. The four-way fixture, where the
  absorbed proposal is itself a survivor carrying its own group, is the only one where that line
  does work. Found by the implementer after four gate rounds had approved the three-way fixture as
  sufficient; verified by the compliance review by hand-tracing both paths. **Do not trim it.**

- [ ] **T6.0d A link to a MOC that will never exist renders as a normal instruction**
      `[activity: backend]` — **Added 2026-09-08, accepted. Runs before T6.1.**

  **Inherited context — read this before the steps.** Found by T6.0c's implementer while tracing
  a claim in T6.0c's own task text, and traced from the code rather than inferred. The task text
  said an unresolvable `link_to_moc` is dropped by `filter_unappliable_relationships`. **It is
  not** — that filter only touches `add_relationship` actions carrying `error`. What actually
  happens is worse.

  `resolve_target_moc_paths` has two tiers: an in-set `create_moc` lookup, then Kado
  `search_by_name`. When both miss, `target_moc_path` stays `null` and the action continues
  through every gate:

  | gate | behaviour on a null target |
  |---|---|
  | `render_md.py` `link_to_moc` branch | renders `### Add link to [[X]] — <note>` with `- [ ] Applied`. **Only the `- **Path:**` line is suppressed.** The anchor falls to its "unresolved" branch, instructing the user to *open the MOC* and find an editable callout |
  | `instructions.schema.json` | `target_moc_path` is `["string","null"]` and **not** in `required`. Validates clean |
  | `instructions-dryrun.py` | `REQUIRED_FIELDS_BY_KIND["link_to_moc"]` omits the field; `describe()` prints only `target=[[…]]` |
  | `instructions-diff.py` | link coverage matches on the `target_moc` **stem**, never the path. Counted `[OK]` |

  So the user reads an ordinary to-do asking them to open a MOC that does not exist and will never
  be created, and ticks it. **This violates CON-2**: the user approves on what the document says.

  **The asymmetry that shows the intended design.** `add_relationship` **requires**
  `target_moc_path` in both the schema and the dryrun whitelist, and has
  `filter_unappliable_relationships` as its guard — because a null there is rejected by the wire
  schema downstream. `link_to_moc` was given a nullable field and no guard. One kind is defended,
  its sibling is not.

  **Not case-specific, and not caused by this spec.** It fires whenever both resolution tiers
  miss. Spec 034 surfaced it because case-only MOC pairs make it reachable on ordinary input; the
  defect predates the spec. Weigh the fix accordingly — this is a repair to an existing path, not
  a feature of recursive discovery.

  **A null target has three causes and only one of them means "does not exist" — added
  2026-09-08 while grounding the gate.** `resolve_target_moc_paths`'s tier 2 returns `None` when:

  | cause | line | what it means |
  |---|---|---|
  | `client is None` | `render_resolve.py:562` | Kado was never available — nothing was checked |
  | `except Exception: return None` | `:566-568` | the Kado call **failed**, swallowed silently |
  | `not hits` | `:570-572` | Kado answered, and the MOC genuinely does not exist |

  **Withholding on a bare null conflates all three.** A transient Kado failure, or an offline run,
  would silently withhold every MOC link in the run and report each one as a MOC that will never
  exist — which is false, and worse than the defect being fixed: the user would rename or
  re-create MOCs that are already there. Distinguish the causes at the point where they are known;
  do not reconstruct them later from a null. Only the third cause warrants "this MOC will not
  exist"; the first two warrant "this could not be checked", which is a different sentence to the
  user and possibly a different decision about whether to emit at all.

  **The precedent to follow is `filter_unappliable_relationships` (`render_resolve.py:730`)**, not
  a new shape: it returns `(kept, skipped)`, is a pure function, and its skipped items reach the
  user through stderr and the instructions.md Skipped section — the same pattern as
  `filter_missing_daily_notes`. Its docstring also records *why* `add_relationship` needed it:
  Hashi's wire schema is `additionalProperties: false` with no `error` field, so one error-bearing
  action makes Hashi reject the entire instruction set. `link_to_moc` escapes that only because
  its null is a legal schema value — which is why it was never caught.

  1. **Prime**: read `resolve_target_moc_paths` (`render_resolve.py`) for both tiers and what a
     miss leaves behind. Read `filter_unappliable_relationships` for the guard `add_relationship`
     already has, and `$defs/add_relationship` vs `$defs/link_to_moc` in
     `tomo/schemas/instructions.schema.json` for the required-field asymmetry. Read T5.5's
     "Not filed" sections in `render_md.py` — they are the precedent for telling the user why an
     action was withheld `[ref: SDD/CON-2, CON-4]`.
  2. **Test** (RED):
     - a `link_to_moc` whose target resolves through neither tier does **not** render as an
       appliable `- [ ] Applied` instruction
     - the user is told why, naming the MOC that could not be resolved — assert the rendered
       markdown, following T5.5's precedent rather than a new shape
     - a `link_to_moc` that **does** resolve is unaffected — assert this, or the fix is a
       feature regression dressed as a repair
     - **all three causes asserted through the rendered document, not through the resolver.**
       The gate blocked a plan that would have allowed a unit test calling
       `resolve_target_moc_paths` (or a new filter) in isolation and checking a returned string:
       that passes even if the cause never reaches `render_md.py`'s Skipped section — the
       identical shape T6.0c was blocked on twice. Drive `instruction-render.main()` over a real
       fixture, on the `_drive_render` template
       (`tests/test_034_t5_4_attachment_clash_suppression.py:468`), and assert the rendered
       markdown for each of the three causes.

       **The cause needs plumbing this plan does not yet name.** `resolve_target_moc_paths`
       returns an `int` and collapses all three causes to a bare `None` (`render_resolve.py:565-572`).
       Threading a cause out of it is new plumbing; name every site it must cross before writing
       code, the way T6.0c's four-site table does.

       **The gate traced the withhold-and-report shape at seven sites** — the resolver threading a
       cause; a new `(kept, skipped)` filter; its call site beside `instruction-render.py:660`/`:675`;
       the `instructions.json` `tomo` block twin-write beside `:781-796`; the
       `render_instructions_md` metadata-dict literal at `:849-856`; a new `render_md.py` Skipped
       block parallel to `:691-746`; and the `instructions-diff.py` subtraction wired into
       `run_diff`. **Site 4 is the trap**: `instructions-diff` reads `instructions.json`, not the
       dict handed to the renderer, so skipping it leaves the audit wrong even when everything
       else is right — T6.0c's "(3) without (4)" no-op, one level down.

       **That count is contingent on the design choice, not a fixed number.** Emit-with-marker has
       a different shape entirely: the schema and the dryrun's `REQUIRED_FIELDS_BY_KIND` join the
       list, the filter split disappears, and `render_md.py`'s existing `link_to_moc` branch grows
       a case rather than gaining a sibling block. Produce the table for the design you choose;
       do not inherit seven as a target.
     - the dryrun and the coverage audit agree with the renderer. **"Not counted `[OK]`" is not
       specific enough and the gate blocked it**: a raw `[DIFF]` hard-fail also satisfies that
       wording, and it is the wrong answer — it would misdiagnose an intentional withholding as
       drift, the exact failure mode T6.0c's audit narrative warns about. Use the **subtraction
       pattern**, which is the established design language of that file: `_subtract_skipped_daily`
       (`instructions-diff.py:709`), `_subtract_withheld_moves` (`:737`) and
       `_subtract_skipped_assets` (`:813`) each subtract the withheld item from the expected count
       and report the reason through the Skipped section, leaving the audit clean. Add the
       matching subtraction for a withheld `link_to_moc`.

       **But only for one of the three causes.** The gate blocked a uniform "audit completes
       clean" and was right: all three existing siblings subtract for causes that are
       **permanent and user-actionable** — a missing daily note, a withdrawn move, an unfileable
       attachment. `rc == 0` there correctly means "handled, nothing further". `client is None`
       and the swallowed `Exception` mean **nothing was checked this run**. Subtracting those to a
       clean `rc == 0` makes an offline run indistinguishable from one where Kado confirmed the
       MOC absent — the same CON-2 conflation this task removes from the renderer, reintroduced
       one layer down in the audit. So:

       | cause | audit outcome |
       |---|---|
       | `not hits` — Kado answered, MOC confirmed absent | subtract, audit completes, `rc == 0` |
       | `client is None` — Kado never available | soft **observation**, not silence |
       | swallowed `Exception` — the Kado call failed | soft **observation**, not silence |

       `instructions-diff.py` already has this vocabulary: `observations` is a separate
       non-blocking channel returned beside the exit code (`:647`, `:706`), documented at `:21`
       as "Observations (soft, non-blocking)" and at `:37` as compatible with exit 0. Use it
       rather than inventing a third state. Assert the outcome per cause — not merely that the
       count changed, and not one outcome for all three.
       `derive_expected` counts `link_to_moc` per `parent_mocs` independent of resolution
       (`:270-296`), so withholding upstream without this produces a spurious hard-fail
       `[ref: SDD/CON-4]`
     - proven RED against HEAD, where the unresolvable action renders as an ordinary checkbox
  3. **Implement**: decide and state whether the action is withheld and reported, or emitted with
     an explicit unresolved marker the schema requires. **Do not fold `in_set`** to make targets
     resolve — T6.0 measured that as redirecting one MOC's bullets into a different folder's MOC
     and reverted it (`b9d34e1`); a guard test goes RED if anyone re-folds it.
  4. **Validate**: full suite green; `ruff` clean; neither action golden re-recorded. If a
     no-clash run changes, that is a real regression.
  5. **Success**:
     - [ ] No instruction asks the user to act on a MOC the run knows will not exist
     - [ ] Whatever the renderer withholds, the audit and the dryrun agree it was withheld

- [ ] **T6.1 The run records its own cost** `[activity: backend]`

  **Added 2026-09-06 by the Phase 3 gate — the number this task is about to make durable cannot
  detect its own regression.** `_count_kado_calls` (`inbox-triage.py:1863`) hardcodes the base as a
  literal `2`. The gate proved the consequence rather than arguing it: when it mutated
  `build_attachment_index(all_files)` back to a second `client.list_dir(...)` call, the fake client
  recorded **3** base calls while the estimator still printed `kado_calls=9`. Nothing in the suite
  observed the true count until that gate ran.

  ADR-3's whole claim is that recursion makes discovery *cheaper* — base calls 3 → 2 — and this
  task writes that figure into a permanent history. A history whose source is a constant records
  the intent, not the behaviour, and would keep reporting 2 through any future change that
  reintroduces a listing.

  **T5.2 added a second kind of listing — expect the observed count to move, and say why.**
  Added 2026-09-07. `_vault_folder_notes` (`suggestions-reducer.py`) issues one cached
  `list_dir(location, depth=1)` per distinct **destination** folder, to check whether a proposed
  name is already taken. Two things follow, and neither is a defect to fix here:

  - It is not an inbox listing, so F9's first criterion ("directory listings **of the inbox**")
    is untouched. Do not count it against that.
  - It is a real per-run cost that scales with the number of distinct destination folders in the
    run, and it is currently **unmeasured**. F9's second criterion asks for the actual figure to
    be recorded, and its user story is "recursion does not make my runs more expensive". Record
    it as its own line rather than folding it into the base — a single number that mixes a fixed
    pipeline cost with a content-scaling one tells the user nothing about either.

  Precedent for treating it as outside the base bucket: the pre-existing I38 daily-note existence
  probe is already a per-item, content-scaling Kado cost and has never been counted as a base
  call. T5.2's listing follows that pattern. Surfaced by T5.2's compliance review, which judged
  the literal text not violated and flagged the tension here rather than failing the task.

  So this task must also:
  - Derive the recorded base count from the run's **observed** Kado calls, not a literal. If the
    client cannot report its own call count today, add that capability rather than keeping the
    constant.
  - Report the destination-folder listings separately from the base count, with the folder count
    that produced them, so a future reader can tell a pipeline regression from a busy run.
  - Add a test that **fails** when a second base listing is reintroduced — the exact mutation the
    gate ran. The plan already states the principle for T3.4: *"the estimator is the thing under
    test, so it cannot also be the evidence."* The same holds once the estimator's output is being
    persisted.
  - If the count genuinely cannot be observed without disproportionate change, say so and record
    the constant as a known limitation **in the history's own schema**, so a later reader knows the
    figure is declared rather than measured.

  1. **Prime**: Read `[ref: SDD/Data Storage Changes; cost_history]`. Read
     `mark-captured.py:78-79`, whose `state/moc-squelch.json` default is the precedent — a small
     persistent registry in the instance state, addressed cwd-relative. Read
     `_count_kado_calls` (`inbox-triage.py:1738-1778`), whose base term changes from 3 to 2 in
     Phase 3.
  2. **Test** (RED):
     - a completed Pass 1 appends one entry with its timestamp, run id, item count and call
       counts `[ref: PRD/AC Feature 6]`
     - several runs accumulate — an entry is never overwritten by a later one
     - clearing the working directory leaves earlier entries intact
     - an unwritable history warns and the run continues; measurement must never fail a run
       `[ref: SDD/Error Handling]`
  3. **Implement**: append-only JSONL in the instance's persistent state directory.
  4. **Validate**: tests pass; `ruff` clean.
  5. **Success**:
     - [ ] A history accumulates without anyone remembering to record it
           `[ref: PRD/AC Feature 6]`

- [ ] **T6.2 Integration across the whole pipeline** `[activity: test-strategy]`

  1. **Prime**: Read `[ref: SDD/Runtime View]` and `[ref: SDD/Quality Requirements]`.
  2. **Test**:
     - end to end over a fixture inbox containing: a root note, a subfolder note, a nested
       note, two namesakes in different subfolders, a namesake pair of attachments, a note with
       no embed, and an audio file with a namesake elsewhere
     - assert at every artefact boundary, not only at the end — routing plan, per-item results,
       suggestions document, wire, parsed suggestions, instruction set
     - assert the instruction set is byte-identical for the flat-inbox subset `[ref: SDD/CON-4]`

     **Give the wire/markdown parity golden a collision fixture — added 2026-09-08.**
     `tests/test_suggestions_wire_golden.py` exists to catch the two parser paths diverging,
     and every fixture in it uses single stems (`memo`, `S01`) with no two items sharing a
     filename. So it is blind to divergence that only appears on a collision — which is the
     only kind this spec can produce. T5.1 proved that concretely: its first cut took the
     wikilink *target* instead of the alias, diverging the two paths precisely on the collision
     case, and the parity golden stayed green. Six other tests caught it, by luck of what they
     happened to assert. Add a two-namesake fixture to that golden so the test covers the case
     it was written for.
  3. **Implement**: n/a — test only.
  4. **Validate**: full suite green; `ruff` clean.
  5. **Success**:
     - [ ] Every PRD feature has a passing end-to-end assertion, walked one by one against the
           feature list `[ref: PRD/Feature Requirements]`

- [ ] **T6.3 Prepare the live-validation fixtures** `[activity: validate]`

  1. **Prime**: Read `[ref: SDD/CON-7]`. Read the spec 031 T6.5 entry in
     `docs/evolution/inbox-cost-log.md` — its first run produced nothing because the fixtures
     sat in a subfolder that discovery could not see. That failure is this spec's subject, so
     the same fixtures should now work; do not assume it, check it.
  2. **Test**: n/a — preparation.
  3. **Implement**: place fixtures in the test vault covering the cases in T6.2, and state in
     the phase notes exactly what each one proves and what the expected output is, so the
     result can be read against an expectation rather than interpreted after the fact.
  4. **Validate**: a host-side dry run of the resolution chain over the real fixture layout
     agrees with the expectation before anything live is attempted.
  5. **Success**:
     - [ ] Every fixture has a written expected outcome `[ref: PRD/Success Metrics]`

- [ ] **T6.4 Live validation** `[activity: validate]` — **the user's to run, not the
      implementation's.** Not skipped, not forgotten.

  1. **Prime**: `./scripts/update-tomo.sh --yolo` first — the bare form stalls without copying,
     and an unchanged `# version:` ships nothing. Grep the instance afterwards to confirm the
     files actually arrived.
  2. **Test**: run `/inbox` in the container against the prepared vault and check:
     - the subfolder note appears in the suggestions document
     - two namesakes appear as two suggestions with distinguishable links
     - a destination clash halts both and says so
     - an attachment clash keeps its note in the inbox
     - after apply: the right notes are filed, the right sources marked, nothing left behind
       that should have moved
  3. **Implement**: n/a — validation only.
  4. **Validate**: record the outcome, the item count and the observed Kado call count in
     `docs/evolution/inbox-cost-log.md`, and compare the base count against the expected 2.
  5. **Success**:
     - [ ] A note in a subfolder is triaged, filed, and its source marked — end to end in a
           real vault `[ref: PRD/Success Metrics]`

- [ ] **T6.5 Phase Validation and close-out** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Walk the SDD Quality Requirements table and confirm each row has a passing measurement.
  - Walk the PRD's 40 acceptance criteria and confirm each maps to something green.
  - Write the handoff to the sibling component describing the widened bare-name ambiguity in
    its own matching, aimed at the wire builder `[ref: spec 034 README, Hashi decision]`.
  - Set the spec to `Implemented` via `xdd-meta finalize` — only after T6.4 passes. A spec left
    on `Ready` after shipping is the failure this step exists to prevent.
