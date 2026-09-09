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

- [x] **T6.0b An atomic and a MOC can claim the same path, and nothing compares them**
      `[activity: backend]` — **PROPOSED 2026-09-08, never accepted into this spec. Carried to spec 036 on 2026-09-09.**

  **Not fixed here — reopened as its own spec.** Following the chain to its end on 2026-09-09 showed it does not stop at two claims on one path. Hashi fails the second claim correctly, but its dependency map has no edge from `delete_source` to `move_note`, so the paired delete runs and the user's inbox note is removed while its atomic was never filed. That is data loss, not a missing comparison, and the fix generalises beyond `move_note`: three of the four `delete_source` emission sites are conditional on a different action succeeding. See `docs/XDD/specs/036-delete-outlives-its-justification/`.

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

- [x] **T6.0d A link to a MOC that will never exist renders as a normal instruction**
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
       | `not hits` — Kado answered, MOC confirmed absent | subtract; its own aggregated note |
       | `client is None` — Kado never available | subtract; its own aggregated note |
       | swallowed `Exception` — the Kado call failed | subtract; its own aggregated note |

       **Corrected 2026-09-08, after implementation.** This table first said only `not hits`
       subtracts and the other two are "observations, not silence". That was internally
       inconsistent and the implementer caught it: `run_diff` compares every count category and
       sets `hard_fail` on any mismatch, with no observe-only path — so withholding an action
       *without* subtracting its expected count produces exactly the `[DIFF]` this same paragraph
       calls the wrong answer. All three therefore subtract. **The distinction the table exists to
       draw survives in the note text, not in the subtraction**: three separately-worded aggregated
       observations, so an offline run still cannot read as a confirmed-absent one. Verified by the
       compliance review by tracing `run_diff` rather than by argument.

       `instructions-diff.py` already has this vocabulary: `observations` is a separate
       non-blocking channel returned beside the exit code (`:647`, `:706`), documented at `:21`
       as "Observations (soft, non-blocking)" and at `:37` as compatible with exit 0, and printed
       unconditionally when non-empty (`:1044-1049`, `[WARN]`-prefixed) — visible on a clean exit,
       not dead code. Use it rather than inventing a third state. Assert the outcome per cause —
       not merely that the count changed, and not one outcome for all three.

       **One aggregated note per cause, never one per link.** `client is None` is a single
       condition set once for the whole run (`render_resolve.py:562`), so every tier-2 miss in
       that run shares it — a run with Kado down could emit a dozen near-identical lines, burying
       the one fact that matters. Every withholding observation in this file already aggregates:
       `destination_clashes` (`:957-972`), `attachment_suppressions` (`:974-987`),
       `n_assets_skipped` (`:989-997`), `n_daily_skipped` (`:999-1006`) each emit **one** note
       carrying a count plus a pointer to the itemised detail in `instructions.md`. Follow that
       template. The per-link detail belongs in the Skipped section, which the rendering bullet
       above already requires. Keep the two causes as **two** aggregated notes — merging them
       re-collapses the distinction this table exists to draw.

       **The fixture needs at least two links under one cause, or the test cannot see the
       difference.** With a single affected `link_to_moc`, an aggregating implementation (one
       note, count 1) and a per-link one (one note, because there is only one link) render
       identically — an assertion true regardless of implementation. Put **two or more**
       `link_to_moc` actions under the same cause in the RED fixture and assert the **count the
       note reports**, not merely that a note exists. Same trap as T6.0c's three-way fixture,
       which could not reach the line it was meant to prove; do not trim this one back to one
       link.
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
     - [x] No instruction asks the user to act on a MOC whose existence the run could not
           confirm — all three causes withheld from the appliable checkbox, not only the
           confirmed-absent one
     - [x] Whatever the renderer withholds, the audit and the dryrun agree it was withheld

  **Closed 2026-09-08** — `5b52681` (RED, seven failing assertions through
  `instruction-render.main()`), `0001e2e` (the fix). 10 tests; suite 3655 → 3665, ruff clean,
  both action goldens byte-identical, no wire-schema change.

  **Withhold-and-report, over eight sites — not the gate's seven.** The extra one is
  `_strip_internal_link_fields`: the cause marker is a Tomo-internal field on a wire action, so it
  owes the strip-before-wire guard even though `filter_unresolvable_moc_links` removes every action
  carrying it. Emit-with-marker was rejected on a reason the plan did not name — the marker would
  have to be honoured by Hashi's `additionalProperties: false` schema, making `target_moc_path`
  required is a breaking cross-repo contract change owed a Kokoro migration note, and Hashi could
  not apply the action anyway (it modifies, never creates: there is no MOC to write into).

  **The filter runs beside the resolver, not beside the other two filters.** The gate placed the
  call site at `instruction-render.py:660`/`:675`. Four passes sit between resolution and that
  point and all four read `link_to_moc` — anchor resolution (one Kado read per target MOC), the #70
  same-section merge, the existing-heading rewrite, new-section serialization. A withheld action
  must not be merged into a surviving one, and a Kado read for a MOC nobody will open is waste.

  **All three causes subtract; only the sentences differ.** The plan's table read as "subtract the
  confirmed-absent one, observe the other two". Withholding without subtracting produces
  `[DIFF]` — the hard fail the same paragraph calls the wrong answer — so the count table subtracts
  for all three and the three aggregated observations carry the distinction. The count table answers
  "did the renderer emit what the document promised"; under every cause it did not.

  **The garden-audit branch was outside the plan and inside the blast radius.** A garden
  `file_note` whose File-under value is a user-typed stem leaves the parser with
  `target_moc_path: None` (`garden-audit-parser.py:462`) and is resolved by the same tier-2 lookup
  in the same `main()`. `run_diff_garden` keeps its own count table and its own per-item coverage,
  so both had to learn about the withholding independently — proven by reverting the garden half
  and observing `link_to_moc expected=2 actual=0 [DIFF]` with two `[MISSING]` items on a correct
  set.

  **Report-only, found by the shape-grep and NOT fixed here.** The `add_relationship` that a garden
  `file_note` emits alongside its link writes `up:: [[<MOC>]]` into the child note, and its
  `target_moc_path` is the CHILD's path — so the null-target guard never sees it and the up-link
  is still written pointing at a MOC that may not exist. Same CON-2 class, different action kind,
  and not made worse by this task: both halves were emitted before it. Belongs with T6.0b's
  cross-kind work or its own task.

  **Code quality returned FAIL, on this task's own defect for the third time.** The shared intro
  above all three bullets said "an instruction to open a MOC **that is not there** is one you
  cannot carry out" — true only for `absent`, and sitting two lines above the `probe-failed`
  bullet that says "this is *not* evidence the MOC is missing". The intro and a sibling bullet
  contradicted each other in one rendered block, and the user reads both. Fixed at `bee3889`
  (`render_md.py` 0.16.1, +2 tests): the intro is now cause-neutral and its remaining claim —
  "a bullet is only ever written into a MOC the run has located" — was traced to be **true of the
  shipped pipeline**, not merely unfalsifiable. Suite 3665 → 3667.

  **WHY nine tests, a five-round gate and a compliance review all passed it**: every one exercised
  the causes *separately*. A per-cause test structurally cannot see a contradiction between an
  intro and a sibling bullet. The guard is now a test that renders **all three causes together**
  and asserts the intro is byte-identical across the three single-cause renders and the combined
  one — so a cause-specific intro fails the moment two causes co-occur. This is T5.5's lesson from
  a new direction: it is not enough to read the document as prose, the fixture must contain the
  neighbours.

  **A fourth candidate was raised and judged not a defect.** The enclosing heading
  `## Skipped — un-appliable actions` covers five blocks, and its established sense across the
  four pre-existing ones is "not appliable *in this run*, pending some condition" — a missing daily
  note, an unfileable attachment, an unreachable source. `unchecked` and `probe-failed` fit that
  sense exactly. Left unchanged, by agreement between the orchestrator and the code-quality review
  against the implementer's reading.

  **Known limitation, accepted 2026-09-08, not a defect to fix in Tomo.** `absent` is inferred
  from Kado returning an empty result, and Kado returns an empty result for a note that exists but
  lies outside Tomo's permitted paths — `filterItemsByScope`
  (`Kado/src/obsidian/search-adapter.ts:91-97`) drops out-of-scope items silently, and `FORBIDDEN`
  is raised only for *tag* permissions. So for a permission-scoped MOC the instructions say "MOC
  not found — create it" about a note the user already owns. Recovering the distinction would mean
  Tomo re-deriving its own ACL, duplicating what Kado knows, and no fixture here can exercise it —
  the fake client *defines* `[]` as absence. Surfaced as the implementer's unverifiable assumption,
  then checked against the Kado source rather than left open. Recorded in
  `docs/tomo/scripts/lib/render_actions.md` under the cause table.

- [x] **T6.1 The run records its own cost** `[activity: backend]`

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

  **Amended 2026-09-08 after the TDD gate blocked the first cut. Three decisions are now made;
  do not re-open them.**

  **1. The parity test already exists — do not write it again.**
  `tests/test_031_t6_3_cost_verification.py::test_reported_count_matches_observed_at_several_note_counts`
  (added `92ef32d`, the day of the Phase 3 gate) already goes RED on the exact mutation this task
  cites: the gate reproduced it by hand and saw `reported=9 observed=10`. So the *suite* does
  observe the true count; what is still a literal is `_count_kado_calls`' **implementation**, which
  agrees with reality by parity rather than by derivation. T6.1's new work is to make the
  implementation derive its number. The existing test becomes regression cover for that change,
  not a thing to duplicate.

  **2. Both literals are replaced, via a dedicated counter — not `_req_id`.**
  `_count_kado_calls` hardcodes `2` (base) **and** `7` (byFrontmatter). `query_frontmatter`
  (`inbox-triage.py:340-367`) makes exactly seven unconditional `search_by_frontmatter` calls, so
  the `7` is the same shape as the pre-ADR-3 `3` — a fixed count baked into a formula. The task's
  own argument ("a history whose source is a constant records intent, not behaviour") applies to it
  word for word, so it goes too.

  The counter is a **dedicated attribute on `KadoClient`**, incremented in `_call_tool`
  (`kado_client.py:621`) — the single choke point every read, write, search and graph-audit passes
  through. **Not `_req_id`**: that is a JSON-RPC request identifier whose meaning the client does
  not own, and keying a permanent history to it breaks silently the moment anything else
  increments or resets it. Every fake client in this suite already tracks its own `self.calls` —
  a dedicated counter is the established convention here, and it costs one integer.
  Increment **before** the request, as `_req_id` does, so a call that raises still counts: it
  consumed a round trip, and `_count_kado_calls`' own docstring already names that under-count as
  a known flaw it could not fix.

  **3. The folder-listing counts go into the history, and the SDD was amended to hold them.**
  `cost_history` gained `folder_listing_calls` and `distinct_destination_folders` (`1d8c80e`).
  Reporting them only to stderr was rejected: the point of a history is comparability across runs,
  and a number that is not in it cannot be compared. **Assert a positive value** — a specific
  non-zero folder count at a named location. "Reported separately, never folded into the base" is
  satisfied by reporting nothing at all, and the gate flagged that wording as vacuous.

  **The plumbing crosses a process boundary, and an ordering constraint falls out of it.**

  | # | site | change |
  |---|---|---|
  | 1 | `kado_client.py:621` `_call_tool` | the dedicated counter, incremented before the request |
  | 2 | `inbox-triage.py:1835` `_count_kado_calls` | derive from the checkpoints; both `2` and `7` go |
  | 2b | `discover()` — two new `TriageState` checkpoint fields | snapshot the counter **at boundaries**, see below |
  | 3 | `suggestions-reducer.py:1944-1965` `_vault_folder_notes` | count listing calls and distinct folders — today `_folder_cache` is purely local and emits no metrics at all |
  | 4 | the reducer's output dict (`suggestions-doc.json`) | carry both counts across the process boundary |
  | 5 | wherever the history is appended | read triage's own metrics back from `routing-plan.json["metrics"]` and combine |
  | 6 | `solution.md` `cost_history` | done at `1d8c80e` |

  **The ordering constraint**: the entry **cannot** be appended by `inbox-triage.py` for the paths
  that reach the reducer. Triage writes `routing-plan.json`, then `suggest-handling` invokes
  `suggestions-reducer.py`, so the folder counts do not exist when triage finishes. Site 4 is the
  trap this spec has now hit five times: a number produced in one process and never wired to where
  it is read raises no error and fails no unit test.

  **A running total cannot be decomposed after the fact — hence site 2b.** The counter on
  `KadoClient` is one lifetime total across `discover_files` → `resolve_inbox_attachments` →
  `query_frontmatter` → per-item reads. Reading it once at the end yields **one** number, and the
  SDD's schema needs **two** (`base_kado_calls` and `total_kado_calls`). So snapshot it at two
  boundaries inside `discover()` — after `resolve_inbox_attachments` returns, closing out the base;
  after `query_frontmatter` returns, closing out byFrontmatter — and thread each out as a
  `TriageState` field, exactly the shape `tag_handler_reads` and `wire_sibling_reads` already use
  (`inbox-triage.py:130-134`), whose own comment says they exist because they are *"per-item Kado
  call counts that TriageState's other aggregate fields cannot reconstruct after the fact"*. Same
  reason, same solution. Without the checkpoints, "derive from the counter" reads as a one-line
  change at `:1835` and produces a single total that cannot fill the schema.

  **Not a risk, checked**: another code path calling `search_by_frontmatter` cannot escape the
  count — `_call_tool` is the sole choke point and nothing bypasses it. The decomposition above is
  the only real hazard.

  **Site 5 is five sites, one of which does not exist yet.** The append cannot simply be bolted to
  `mark-captured.py`: that script is called from **`suggest-handling` only** (grepped across every
  skill), and `force-atomic-handling` ends at a Report message with no state-writing step at all.
  Meanwhile `idle`, `synthesize` and `transcribe` never reach the reducer — yet they still make
  base and byFrontmatter calls, and item 4's own success criterion is *"a history accumulates
  without anyone remembering to record it"*, which is false for four of five paths if only the
  `suggest` path is wired.

  **The rule, decided — do not re-open it.** Every triage run appends **exactly one** entry, tagged
  with its action. `folder_listing_calls` and `distinct_destination_folders` are present only on
  the paths where the reducer actually ran; on the others they are absent, not zero — zero would
  assert a measurement that was never taken. The append logic lives in **one shared helper**, not
  copied per skill, so the four call sites cannot drift apart.

  **Superseded 2026-09-08, after implementation — the append moves into the reducer.** The table
  below placed the `suggest` and `fan-resolve` appends in a script invoked from a SKILL.md step.
  T6.1's implementer named the flaw as the assumption its diff could not verify: **no test can see
  a markdown instruction.** For the two highest-traffic actions the entry would depend on an LLM
  executing one line, and this task's own criterion is "a history accumulates **without anyone
  remembering** to record it". That guarantee cannot live in a step someone has to remember.

  The fix is available and deterministic: `suggestions-reducer.py` already runs on **both** those
  paths as a Python process, already holds the folder counts, and `routing-plan.json` — carrying
  triage's own metrics — sits in the same `tomo-tmp/` directory it already writes into. It simply
  does not read it today. Appending from the reducer removes the LLM step entirely and makes the
  criterion literally true rather than conditionally true.

  This also matches the standing repo principle that deterministic work does not belong in an
  LLM-executed step. The cost is that the reducer gains a second output responsibility; it already
  writes `suggestions-doc.json`, so this is a second file, not a change of category.

  The per-action rule is otherwise unchanged — one entry per run, tagged with its action, folder
  fields absent rather than zero where the reducer never ran, and the triage-side guard still
  required so triage does not double-append on the two reducer paths.

  | action | reducer runs? | where the entry is appended |
  |---|---|---|
  | `suggest` | yes | **in `suggestions-reducer.py`** — superseded; was a SKILL.md step |
  | `fan-resolve` | yes (`--fan-resolve`) | **in `suggestions-reducer.py`** — superseded; was a SKILL.md step |
  | `synthesize` | no | terminates in triage; folder fields absent |
  | `transcribe` | no | terminates in triage; folder fields absent |
  | `idle` | no | terminates in triage; folder fields absent — an idle run still spends base calls, and a history that omits them cannot show what idling costs |

  **Test each path.** A suite that exercises only `suggest` passes while every `fan-resolve` run
  silently records nothing — the same shape as T6.0c's (3)-without-(4), one level further out.

  **And guard the triage-side call, which fails the other way.** `inbox-triage.py` calls the helper
  for `idle`/`synthesize`/`transcribe` but must **not** for `suggest`/`fan-resolve` — those defer to
  the downstream script so the folder fields can be included. Missing that guard does not silently
  no-op like every other trap in this task; it **double-appends**, writing an incomplete entry
  before the downstream script writes the real one. Assert it directly: a `suggest` run produces
  **exactly one** history entry, not two.

  **The helper is `tomo/scripts/lib/cost_history.py`**, on the shape of `lib/squelch_persist.py` —
  a `lib/` module with a public append function, stdlib-only, called from `mark-captured.py` at
  archival time. All three callers reach `lib/` identically (`SCRIPT_DIR` + `sys.path.insert`, as
  `mark-captured.py:44-50` and `inbox-triage.py:30-33` both do), so there is no split to design
  around.

  **Checked, not a risk**: every action outcome sees a fully-measured `state`. `determine_action`
  runs strictly after `discover()` completes, `discover()` has no early return that skips
  `query_frontmatter`, and `_build_idle_reasons` makes no Kado calls of its own. So `idle`'s two
  return sites and `synthesize`'s three differ in *why*, never in *what was measured* —
  "absent, not zero" stays scoped to the folder fields. A `discover()` that raises `KadoError`
  aborts before metrics or append are reached, so it is not a partial entry but a run that never
  completed.

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
     - [x] A history accumulates without anyone remembering to record it
           `[ref: PRD/AC Feature 6]`

  **Done 2026-09-08.** Both literals are gone: `_count_kado_calls` derives its
  base and byFrontmatter terms from `KadoClient.call_count`, snapshotted at
  three points inside `discover()` and threaded out as
  `TriageState.base_kado_calls` / `.frontmatter_kado_calls`. The counter's
  before-the-request placement is pinned by four tests in
  `test_kado_client_retry.py` — a call that raises still counts, a retry chain
  counts once, and the count survives a `_req_id` reset. The reducer counts its
  destination-folder listings the same way and carries both figures in
  `suggestions-doc.json`. `lib/cost_history.py` owns the record's shape;
  `inbox-triage.py` appends for `idle`/`synthesize`/`transcribe` (guarded by
  `DOWNSTREAM_COST_ENTRY_ACTIONS`) and `suggestions-reducer.py` appends for
  `suggest`/`fan-resolve` with the folder fields, per the supersession above.
  `record-run-cost.py` and its two SKILL.md steps were removed; the script is
  in `RETIRED_SCRIPTS`. `tests/test_034_t6_1_cost_history.py` (24 tests) covers
  all five paths, a reducer-CLI subprocess run proving no orchestration step is
  involved, the "exactly one entry" guard, and an unwritable history.

  **One thing the task surfaced that its own table did not name.** The history's
  `state/` default is cwd-relative (mark-captured's precedent), and host tests
  run from the repo root — so 24 existing `inbox-triage.main()` argv sites across
  five test files, and (once the append moved) two reducer-driving gate files,
  began appending into the repo working tree. Every site was scoped to
  `tmp_path`, and `tests/conftest.py` gained an autouse guard that fails the
  offending test by name. The guard found the `test_018_pipeline.py` helper
  (11 failing tests) that a file-by-file bisect had missed — and then, once its
  baseline was moved from per-test to per-session, two more files whose
  module-scoped fixtures had been setting up *before* the guard sampled.

  **A second trap the suite could not have shown.** The reducer's `--routing-plan`
  first landed as a literal `tomo-tmp/routing-plan.json`. The repo root carries a
  gitignored `tomo-tmp/routing-plan.json` from an old session, so every reducer
  test would have read **a different run's plan** — green, and wrong. It now
  derives from `--output`'s own directory: correct in production, inert in tests.

  **Why the drift was unobservable rather than merely unobserved.** Before this
  task `routing-plan.json`'s `metrics.kado_calls` had no reader anywhere in the
  repo. A write-only number cannot regress visibly, so `2 + 7` was not a figure
  nobody checked — it was a figure nothing *could* check.

  **The action-classification test derives, it does not restate** (`af5b49f`).
  Code-quality flagged the first form as near-tautological: a literal in the test
  against a literal in the source, which would stay green when a sixth action was
  added without being classified. It now parses `determine_action`'s source with
  `ast`, collects every returned action, and fails naming the unclassified one —
  proven by adding an unreachable `return "reconcile", []` and observing
  `unclassified action(s): {'reconcile'}`. A broken parse yields an empty set and
  fails, so the test cannot pass by not working.

- [x] **T6.2 Integration across the whole pipeline** `[activity: test-strategy]`

  **Amended 2026-09-08 after the TDD gate blocked three of the four items.**

  **Scope against `test_034_t2_8_end_to_end_key_trace.py` — it already owns part of this.** That
  file walks this spec end to end in 26 tests, hop by hop (routing plan → state → item results →
  suggestions doc → wire → confirmed_items → derive_expected → build_actions), on **both** parser
  paths, for two namesake notes in different one-level subfolders and for a space-and-mixed-case
  subfolder. It has **zero** attachment fixtures, **zero** audio fixtures, no root-level note and
  no depth beyond one subfolder.

  So the fixture list below is genuinely uncovered — but **do not re-assert item_key identity or
  re-trace the hops for two namesake notes.** T2.8 owns that case; a second file repeating it
  doubles the maintenance and leaves nobody able to say which is authoritative. Scope the new
  assertions to what T2.8 does not touch: attachment collision (T6.0's `claimed` fold plus T5.4's
  suppression), audio peered by note rather than by name (Feature 5's actual defect surface), the
  no-embed note as a negative control, and root-level plus multi-level placement. Give the new
  file a docstring that states this boundary, the way T2.8's own docstring scopes itself against
  the seven other e2e files.

  1. **Prime**: Read `[ref: SDD/Runtime View]` and `[ref: SDD/Quality Requirements]`. Read
     `test_034_t2_8_end_to_end_key_trace.py` in full **before writing anything**, and
     `tests/fixtures/034-t3-4-flat-golden/` for the golden conventions — volatile fields are
     replaced with `<NORMALISED>`, not left to drift.
  2. **Test**:
     - end to end over a fixture inbox containing: a root note, a nested (two-level) note, a
       namesake pair of attachments, a note with no embed, and an audio file with a namesake
       elsewhere — plus the two namesake notes **only** as context for the attachment and audio
       cases, not as a re-trace of T2.8
     - assert at every artefact boundary, not only at the end — routing plan, per-item results,
       suggestions document, wire, parsed suggestions, instruction set
     - **the instruction-set golden, with its baseline named.** No pre-034 instruction-set golden
       exists; `034-t3-4-flat-golden` is a Pass-1 *suggestions document*, and the two action
       goldens are mid-Phase-5 JSON. Record a new one from **`ee44cb3`** (pre-Phase-1), mirroring
       T3.4's choice, driven through the real `instruction-render.py`, and write a README beside
       it naming the commit and the reason — every other golden in this spec does.
       **"Flat-inbox subset" means its own fixture** — plain root-level notes, no collisions —
       not a subset carved out of the big fixture after the fact `[ref: SDD/CON-4]`.

       **`ee44cb3` is verified as a clean baseline, not assumed.** Every commit touching a Pass-2
       file between it and HEAD — 20 of them across `instruction-render.py`, `suggestion-parser.py`
       and the three `lib/render_*.py` — is a `fix(034)` or `feat(034)`. No other in-flight spec
       touched Pass 2 in that range, so the golden pins this spec's changes and nothing else. The
       whole Pass-2 chain exists at that commit, so a self-consistent old pipeline is producible;
       fixture the approval as pre-ticked checkboxes in the recorded suggestions document, as any
       other suggestion-parser input does.

       **Use `git worktree add`. Do NOT extract files with `git show`.** Producing pre-034 output
       means running pre-034 code, and `git checkout` is forbidden in this worktree — a stale
       `stash@{0}` must never be applied and the tree must stay clean. But per-file `git show`
       extraction is worse than inconvenient here: `instruction-render.py` at `ee44cb3` imports
       from `lib/*.py` and validates against `tomo/schemas/*.json`, so one missed transitive
       dependency runs the **old renderer against HEAD's schema or a HEAD helper** — producing a
       golden that is neither old nor new, and silently. That is the missed-site shape this spec
       has hit four times. `git worktree add <scratch> ee44cb3` checks the whole tree out
       consistently and removes the failure mode. Tear it down afterwards. Never check *this*
       worktree out to another commit.

       **Ship a `record.py` beside the golden.** T5.3's and T5.4's fixtures each carry one plus a
       README and are re-derivable from the repo; T3.4's carries neither and however it was
       produced is now unreproducible. A recording that reaches into a *different commit* needs
       that more, not less. The script creates the scratch worktree, runs the full old chain over
       the fixture inbox, writes `instructions.md`, and tears the worktree down; the README names
       the commit, the reason, and the exact reproduction command.

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
     - [ ] **A Feature-N → test mapping exists as data, and a test walks it.** Not a markdown
           table in a docstring — that rots silently the moment a referenced test is renamed or
           deleted, and nothing notices. Encode it as a module-level list of
           `(feature_id, description, test_module, test_name)` near the top of the file, covering
           all ten PRD features `[ref: PRD/Feature Requirements]`, each row pointing either at a
           new assertion here or at the existing test that already owns it (T2.8, T3.4, T5.1,
           T5.4 and others). Add one test in the same file that walks the list and confirms every
           referenced test **currently passes** — not merely that it collects. Collectibility
           alone would accept a row pointing at a test since marked `xfail` or `skip`, which
           collects cleanly and proves nothing; asserting the pass costs a node-id run of a test
           the suite already runs.

           **Name the residual limit in the file's docstring, in one sentence**: this mapping
           proves the referenced test exists and currently passes; it does **not** prove that test
           still asserts the claimed feature. Someone gutting a body to `assert True` under an
           unchanged name defeats it, and nothing short of re-deriving the proof would catch that
           — disproportionate for a table whose job is to point at evidence rather than re-prove
           it. Semantic drift stays a review responsibility at the moment that test is edited.
           This matches how the spec already treats proof: established at authoring time by
           RED-before-fix, not claimed as a standing mechanical guarantee.

  **Two limits of the instruction-set golden, recorded 2026-09-08 rather than closed.**

  **It pins three of roughly fifteen action kinds.** A flat inbox emits `move_note`,
  `link_to_moc` and `delete_source`; the other twelve (`move_asset`, `create_moc`,
  `insert_under_marker`, `add_relationship`, the three daily kinds, `skip`, `edit_note_text`,
  `remove_up_link`, `resolve_dead_link`, `edit_frontmatter`) are unreachable from one without
  inventing daily updates and skips a flat inbox has no reason to carry. So the golden proves
  "no regression in three sections", **not** "no Pass-2 regression on a flat inbox" — widening the
  fixture would make it less representative, not more. **T6.5 owes the question of where the other
  twelve are pinned**, when it walks the SDD Quality Requirements table; do not assume they are.

  **`DELIBERATE_DELTAS` cannot tell a reviewed change from one added to make the test pass.**
  Only the pinned count and review of the list itself stand behind it — an author can edit the
  golden's expectation and the exception list in one commit. The gain over re-recording is real
  but narrow: **the deviation is visible in the diff, where a re-record is not.** That is the
  whole of the guarantee; do not read more into it.

  **Closed 2026-09-08.** `efde457`, `3312f08`, `18e5450`. Suite 3695 → 3735, ruff clean, no
  production code, both action goldens untouched, scratch worktree torn down.

  **The parity golden was blind, and the proof is that the old tests stayed green.** Reverting
  T5.1's alias fix now fails exactly one test — the new two-namesake fixture — while the two
  pre-existing parity tests pass. That green is the finding: the file existed to catch the two
  parser paths diverging and could not see the only divergence this spec produces. Reproduced
  independently by the compliance review rather than taken from the report.

  **A golden's exception list is only as strong as its patterns.** The first cut matched
  `Delete source note: .+` — shape, not content — so a regression mangling the note name passed
  while the file's docstring claimed it "differs only where this spec meant it to". Found by the
  code-quality review injecting `!!!WRONG!!!` and watching the suite stay green. The entries now
  **derive** the expected line from the golden's own untouched `- **Source:**` line rather than
  hardcoding a stem, and a test proves the mangled name is rejected instead of asserting it.

  **Two of the three concerns had nothing to do with subfolder discovery**, which is why the file
  split three ways: the boundary walk keeps the T6.2 name; the flat-inbox golden became
  `test_pass2_flat_instruction_golden.py` — **the phase deliberately dropped from its name**,
  because it guards every future Pass-2 change and nobody touching Pass 2 in a year would look
  inside a T6.2 file; the ten-row map became `test_034_feature_coverage_map.py`, spanning seven
  files. The golden's file now also asserts its own reach (three of ~fifteen action kinds), so
  widening it is visible rather than assumed. **"Walk the list and confirm" is not a deliverable**; it has no failure mode.
           A row whose answer is honestly "not covered here" carries an explicit `None` and a
           one-line reason — that is a fact, not a claim, and needs no proof.
     - [ ] Features 9 (no extra vault listing — a call-count claim) and 10 (the two file-type
           checks agree) are **not** natural fixture-boundary assertions. Point their rows at
           wherever they are really covered, or say plainly that they are not, rather than
           inventing a weak end-to-end assertion to fill the row.

- [x] **T6.3 Prepare the live-validation fixtures** `[activity: validate]`

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
     - [x] Every fixture has a written expected outcome `[ref: PRD/Success Metrics]`

  **Prepared 2026-09-08. Vault: `Privat-Test` (`/Volumes/Moon/Coding/MiYo/temp/Privat-Test`).**

  **The vault already contained two of this spec's headline cases, unintentionally.** Before any
  fixture was written, a filesystem walk showed 8 files visible at `depth=1` and 13 recursively —
  five that this spec newly discovers, among them `Images/Test.md` and `assets/Test.md`: a
  **namesake pair the user created and Tomo could not see**, and `Images/karte.png` +
  `Scans/karte.png`, an attachment namesake pair left from spec 031. Real content, not a
  constructed case. Both are left in place and carried into the run.

  **21 run artefacts were cleared from the inbox** (suggestions, instructions, garden-audit and
  Hashi run-log documents from 2026-08-31 to 09-05), on the user's word that they were test
  residue. **Moved, not deleted** — the vault is not under git, so deletion would be
  irreversible; they sit in `temp/Privat-Test-inbox-archive-2026-09-08/`, outside the vault so
  nothing scans them. Nothing pre-existing in the inbox was modified.

  **Five fixtures written**, each targeting one thing the offline suite cannot prove:

  | Fixture | Case | Expected outcome |
  |---|---|---|
  | `Reise/Tschechien/Prager Burg.md` | two levels deep | discovered at all; source path `100 Inbox/Reise/Tschechien/Prager Burg.md`; bare `[[Prager Burg]]` link — the name is unique |
  | `Notizen/Elbe.md` | namesake, no embed | own suggestion; source link **path-qualified** `[[100 Inbox/Notizen/Elbe\|Elbe]]` (T5.1) |
  | `Reise/Elbe.md` | namesake, no embed | own suggestion; qualified the same way. Pass 1 renames the second to `Elbe (2)`; **un-rename it by hand to make the destination clash fire** (T5.2/T5.3) — then both are withheld and the document says why |
  | `Bilder/Hafen.md` | embeds `Images/karte.png`, path-qualified | its attachment collides with `Scans/karte.png` on one destination; the attachment is withheld **and the note stays in the inbox** (ADR-6 / T5.4) |
  | `Fotos/Kai.md` | embeds `Scans/karte.png` | same, with a different note name so only the attachment clash fires and not a second destination clash on the notes |

  Pre-existing and still carried: `Meissen.md` (no embed — the CON-8 control), `Bautzen.md`,
  `Dresden.md`, `DoubleTest.md`, and the user's own `Test.md` pair.

  **The host-side dry run agrees with the table** — run against the real vault layout through the
  production helpers, no Kado and no writes. `source_link_targets` qualifies exactly the two
  namesake groups (`Elbe`, `Test`) and leaves the other eight bare; the casefolded destination
  check reports `karte.png` as the single attachment clash and `elbe`/`test` as the two note
  clashes. Every row above was predicted before the run and matched after it.

  **Deliberately NOT placed: the audio-namesake fixture.** T6.2 covers it offline. Placing one
  live would put the run through the transcription pipeline, which is model-gated (the suite's
  one standing skip) and carries a known infinite-loop failure mode when an audio stem and its
  transcript sibling disagree on sanitisation. That is a different subsystem's risk to take on a
  validation run for *this* spec. Recorded as a gap in live coverage rather than run blind.

  **T6.4 is the user's to run.** No agent may attempt it `[ref: SDD/CON-7]`.

- [x] **T6.4 Live validation** `[activity: validate]` — **the user's to run, not the
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
     - [x] A note in a subfolder is triaged, filed, and its source marked — end to end in a
           real vault `[ref: PRD/Success Metrics]`

  **Closed 2026-09-09.** Six runs on 2026-09-08 reached every guard; three defects they found
  (T6.4a, T6.4b, T6.4c) were fixed, and a seventh run on 2026-09-09 re-validated the last of
  them against the same approved suggestions document. Hashi then applied that instruction set:
  **11 of 11 actions applied, 0 failed, 0 skipped.**

  The success criterion is met three times over — `Notizen/Elbe.md`, `Reise/Elbe.md` and
  `Bilder/Hafen.md` are all subfolder notes, all filed, all sources deleted. `Fotos/Kai.md`
  stayed in the inbox with its move withheld, exactly as T5.4 promises, and nothing was left
  behind that nobody would move.

  Cost recorded in `docs/evolution/inbox-cost-log.md`: `base_kado_calls: 2` on all seven runs.

  One defect found in the applied vault is **out of scope and not a regression**: the MOC
  template delegates its opening `---` fence to a Templater include, which
  `docs/template-syntax.md` (Rule 1) already forbids by name. Recorded in `close-out.md`.

- [x] **T6.4a The fan document was never joined back to its own identity map**
      `[activity: backend]` — **Found by the T6.4 live run, 2026-09-08. Blocks T6.4's completion.**

  **Inherited context — this is a regression this spec creates in its own new capability.**
  Before spec 034 a note in an inbox subfolder was never discovered, so it could never reach the
  Force-Atomic path. Making subfolders visible opened that path, and the identity join was wired
  for the primary document only.

  **What happens**, traced from the live artefacts:

  | artefact | `item_key` |
  |---|---|
  | `suggestions-fan.json` (the wire the reducer wrote) | `"100 Inbox/Fotos/Kai.md"` — correct |
  | `parsed-suggestions.json` | **`null`**, with `source_path: "Kai"` |
  | `instruction-render.py` | probes `100 Inbox/Kai.md`, which does not exist, and gives up |

  **The mechanism.** `_default_doc_path` (`suggestion-parser.py:595`) always resolves to
  `suggestions-doc.json` — the **primary** structured document — and never to
  `suggestions-fan-doc.json`. So when the markdown path parses a *fan* document, it binds section
  ids against the wrong map: `doc_item_keys = item_keys_by_section_id(_load_json_doc(_primary_doc_path))`
  (`:2243`), consumed by `bind_section_item_key` at `:2272`. The fan doc's own sections are absent
  from that map, the key is left unset, and the render falls back to reconstructing a root path
  from the display stem.

  The comment at `:2239` states the intent this misses: *"spec 034: the rendered document carries
  a display stem only, so identity is joined back from the structured doc **it was rendered
  from**"*. The fan document is rendered from `suggestions-fan-doc.json`, and that is the document
  its identity must come from.

  **Consequence for the user**: any subfolder note taken through **Force Atomic Note** cannot be
  filed, and the coverage audit hard-fails the run on every retry. The markdown path is the one
  that matters here precisely because the user edited the document — that is what makes it
  authoritative over the wire.

  **Why 3735 offline tests do not see it.** No test drives the fan path end to end with a note in
  a subfolder. T2.8 covers both parser paths, but for items in the *primary* document; T6.2's
  walk covers subfolders, but not through Force Atomic. **The missing test is the point of this
  task as much as the fix is** — this is the sixth time in this spec that one of two paths got a
  fix and the other did not, and the first that only a live run could reveal.

  **Three things the gate established — do not re-derive them.**

  **The provenance already exists; the fix needs no new plumbing.** `_extract_tomo_doc_type(text)`
  (`suggestion-parser.py:1261`) reads `tomo.doc_type` from the document's own frontmatter and is
  already used for exactly this kind of dispatch (`_is_moc_proposal_doc`, `:1301`). And
  `suggestions-render.py:31-33` already stamps fan-companion markdown with
  `doc_type: 'suggestions-fan'`, distinct from `'suggestions'`. So the parser can read what it is
  looking at. A fourth document type declares its own value and costs one branch, not a mechanism.
  Note also that the standalone-fan invocation (`synthesis-conductor.md:117`) passes **no**
  `--suggestions-doc`, so `_default_doc_path` runs unconditionally there.

  **The wire path does NOT share the defect — do not test it.** `build_from_wire` (`:292`) reads
  `item_key = w.get("item_key") or stem` straight off the wire and never touches
  `_default_doc_path` or `item_keys_by_section_id`; `build_from_wire_companion` has the same
  shape. A test there would be redundant.

  **`garden-audit` is structurally exempt, not a counter-example.** `garden-audit-parser.py` never
  calls any of these functions, and its branch always passes `--wire` explicitly, resolving
  identity from the wire as `build_from_wire` does.

  **A stale primary doc cannot bind the WRONG key** — worth knowing so nobody adds a fifth
  defensive test. If a leftover `suggestions-doc.json` sits in `tomo-tmp/` while a fan doc is
  approved standalone, an `S01` id could collide across two independently-numbered documents; the
  stem cross-check at `:1913` rejects the mismatched entry before assignment, so the failure
  degrades to the same `None` the tests already assert. Test 3 exercises that guard.

  **Scope widened 2026-09-08, after the first fix landed — the companion path is on the critical
  path, not beside it.** The first cut fixed the standalone-fan invocation
  (`synthesis-conductor.md:117`) and reported the companion loop (`:2427`, reached via
  `synthesis-conductor.md:111` with `--fan-resolve-file`) as a report-only sibling. Checking the
  live run's own routing plan showed that reading was wrong for the case that matters: **when a
  primary document and an approved fan document both exist — which is exactly what Force Atomic
  produces — the conductor takes the companion path.** So the user's validation run cannot
  complete either way:

  **A correction to how this was first framed.** The orchestrator initially read
  `synthesis-conductor.md:113` as forcing a JSON-only merge whenever both entries *carry* a
  `wire_cache_path`, and concluded that a hand-edited markdown name would be silently discarded.
  **That was wrong**, and the gate traced why: the real gate is a digest comparison in
  `load_changed_wire` (`:219-249`), not field presence. Passing the JSON flags for a wire nobody
  touched is harmless — the digest matches, `load_changed_wire` returns `None`, and both companion
  branches fall through to the markdown parse. The conductor's prose states the field-presence
  check as though it were the edited-check; the behaviour is correct and the looseness is
  documentation only. **Do not "fix" it here.**

  So one column of that matrix was real, not two: the markdown *is* read, and what breaks is the
  subfolder note's `item_key` at `:2427`.

  **The companion loop has the same defect in a starker form.** At `:2430` it calls
  `parse_section(section_id, lines)` and keys the result by `_item_key_of(item.get("source_path"))`
  — a **bare display stem** — and never calls `bind_section_item_key` at all. Not a wrong document
  to join against: **no join attempted.**

  **The fix is mechanical reuse — the code already knows where the document lives.**
  `force-atomic-handling/SKILL.md:88` renders the resolve markdown from the same basename that
  `_STRUCTURED_DOC_BY_TYPE["suggestions-fan"]` already maps to; `suggestions-render.py:28-34`
  stamps `doc_type: "suggestions-fan"` on any document whose structured input carries
  `doc_variant == "fan-resolve"`, so `_extract_tomo_doc_type` reads it off `resolve_text` exactly
  as off `text`; and that filename is **already hardcoded three lines above the bug**, at `:2364`,
  for `fan_members`. Resolve the path, build the map, and thread the anchor into the
  `parse_section` call that currently omits it. No new mechanism, no new naming problem.

  **Also close the anchor-map gap the first fix left untested.** `load_doc_anchor_map` shared the
  hole and was fixed by the same rename to `_own_doc_path`, but **no test asserts it**, because the
  fan fixture's `candidate_mocs` carry no anchor and the map is empty either way. That one is worse
  than the item-key case if it regresses: it has **no stem cross-check**, so a colliding `S01`
  across two documents could bind a *wrong* placement anchor rather than degrading to none.

  **The fixture must be paired, not isolated.** An anchored fan doc on its own proves only
  empty-versus-populated — the weaker claim. Follow the shape the shipped
  `test_a_fan_doc_beside_a_stale_primary_doc_binds_no_primary_key` already establishes: a
  **coexisting stale primary doc that also carries an anchor** for an overlapping section id, with
  a **different value**, and assert the fan parse returns the fan's anchor rather than the
  primary's. Only a coexisting wrong answer proves "read from the correct document" instead of
  "read from *a* document".

  1. **Prime**: read `_default_doc_path` (`:595`), `item_keys_by_section_id` (`:1855`),
     `bind_section_item_key` (`:1893`) and the call site at `:2243`/`:2272`. Read T5.0b and T5.0c
     in `plan/phase-5.md` — the same emitter/consumer split, one document earlier
     `[ref: SDD/ADR-1, ADR-2]`.
  2. **Test** (RED):
     - a fan document whose item lives in a subfolder parses with its `item_key` intact,
       **driven through the real parser on the markdown path**, not the wire
     - the resulting instruction set files that note to its destination rather than probing a
       root path — assert the emitted action, not just the parsed key
     - a **primary** document still binds from the primary doc, unchanged — the fix must not
       redirect the path that already works
     - proven RED against HEAD, where the fan item's key is `null`
  3. **Implement**: give the fan document its own structured-doc resolution. Prefer making the
     document's own provenance decide, rather than adding a second special case beside the first —
     a third document type later must not need a third branch.
  4. **Validate**: full suite green; `ruff` clean; neither action golden re-recorded.
  5. **Success**:
     - [x] A subfolder note taken through Force Atomic is filed to its destination — **on both
           the standalone and the companion path**
     - [x] A test fails if either document type loses its identity join
     - [x] A test fails if the anchor map is resolved from the wrong document

  **Closed 2026-09-08.** `9c84b1b` (standalone, 10 tests), `0c280ef` (companion + the paired
  anchor fixture, 5 more). Suite 3735 → 3750, ruff clean, no golden re-recorded,
  `synthesis-conductor.md` untouched as the plan required.

  **This is the one defect in the whole spec that only a live run could find.** Six earlier
  one-of-two-paths misses were caught by gates, reviews or shape-greps. This one needed a real
  vault: no offline test drove the fan path with a note in a subfolder, and the case did not exist
  before this spec made subfolders visible.

  **The companion loop was the worse half.** The standalone path joined against the wrong
  document; the companion loop (`parse_section` with no anchor, no `bind_section_item_key`)
  attempted **no join at all**. It was first reported as a report-only sibling — correct against
  the plan as it then stood — and only the live run's own routing plan showed it is the path a
  Force-Atomic run actually takes.

  **The anchor map shared the hole and regresses worse than the identity join.** It has no stem
  cross-check, so a wrong document binds a *wrong* placement anchor instead of degrading to none.
  It shipped fixed but untested in the first cut, because the fixture carried no anchors — the
  implementer reported that gap itself rather than leaving it to review.

  **One correction on the record.** The `import os` removed alongside the `:2364` hardcode did
  shadow the module-level import for all of `main()` (Python scopes per function), but the
  compliance review checked both revisions and found no `os.` use earlier in the body — so no
  reachable path would have raised. Tidied, not defused; the first framing overstated it.

  **The eighth occurrence was closed before it happened** (`b3fa089`). `_STRUCTURED_DOC_BY_TYPE`
  fell back to the primary document for any type not in the table — correct for the three types
  that reach it today, and a silent wrong join for the next render type whose entry someone
  forgets. That is this spec's own defect, pre-built and waiting. An unlisted-but-present
  `doc_type` now warns to stderr naming the type and the document it fell back to;
  `None` and `""` stay silent, because a legacy document's fallback is its correct answer.

  The implementer improved on the instruction: `suggestions` and `moc-proposal` are now **listed
  explicitly**, both resolving to the primary. So an absent entry means *nobody decided*, not
  *primary is right* — the table is exhaustive by intent rather than by coincidence. Suite
  3750 → 3757.

- [x] **T6.4b The audit compares a sanitised title against a raw one**
      `[activity: backend]` — **Found by the T6.4 live run, 2026-09-09.**

  **Inherited context.** `instructions-diff.py`'s link coverage matches exactly (`:634`,
  `a.get("source_note_title") == stem`). The **emitter** writes the *sanitised* title into
  `link_to_moc.source_note_title`; `derive_expected` uses the *raw* one. Any title containing a
  character `sanitize_stem` replaces — `\ / : * ? " < > |` — never matches, and the audit
  **hard-fails a run whose instruction set is correct**.

  Observed live:

  | | value |
  |---|---|
  | emitted (`I07`) | `Elbe-Schifffahrt`**`-`**` Tschechischer Pegel bei Usti nad Labem …` |
  | expected (`S01`) | `Elbe-Schifffahrt`**`:`**` Tschechischer Pegel bei Usti nad Labem …` |

  The link was emitted correctly and points at the right MOC — only the audit's join fails. Two
  sibling items in the same run passed **solely because their titles carry no forbidden
  character**. A colon in a title is not exotic: the analyst produced this one unprompted.

  **Fix at the emitter, not the audit.** Under **ADR-2** `source_note_title` is a **display**
  field; carrying a sanitised *filename* in it is the category error. Making the audit compare
  sanitised forms on both sides would hide the confusion and make the field mean different things
  to different readers. Same class as T6.0d: an audit that hard-fails a correct run reads to the
  user as Tomo drifting from its own instruction set.

  **A caution for the diagnosis.** The in-container orchestrator read this as an HTML-entity
  mismatch (`&amp;` vs `&`) after seeing the MOC name `Elbsandstein & Tschechien 2026 (MOC)` in
  the failure line. That was a rendering artefact of its own terminal — **no `&amp;` exists
  anywhere** in the artefacts or the vault. Reproducing the audit directly is what showed the real
  cause. Do not chase the entity theory.

  1. **Prime**: read `instructions-diff.py:516` and `:634` for the join, `derive_expected` for
     where the raw title comes from, and every site that sets `source_note_title` on a
     `link_to_moc` `[ref: SDD/ADR-2]`. Read `lib/obsidian_filename.py` — `sanitize_stem` is a pure
     per-character substitution over `\/:*?"<>|`, no transliteration.
  2. **Test** (RED):
     - a title containing `:` produces a `link_to_moc` whose `source_note_title` is the **raw**
       title, and the audit reports `links=[OK]` for it — **assert the audit's own outcome**, not
       just the field
     - a title with **no** forbidden character is unchanged — the fix must not move the two cases
       that already pass
     - the rendered document still shows whatever it showed before for both — the emitted
       *filename* must stay sanitised; only the display field changes
     - proven RED against HEAD, where the colon title yields `links=[DIFF … got=[]]`
  3. **Implement**: carry the display title where a display title belongs.
  4. **Validate**: full suite green; `ruff` clean; no golden re-recorded.
  5. **Success**:
     - [x] A title with a filesystem-forbidden character does not fail its own audit
     - [x] The emitted filename is still sanitised

  **Closed 2026-09-09.** The field was split: `source_note_title` carries the raw display
  title, `source_note_stem` the sanitised vault key, stripped before the wire. The three
  withholding joins moved onto the stem; the report record kept the title alone and
  `_links_for` derives the key, so no internal field crosses the `tomo`-block surface.

  Three things the diff found that the task did not name:

  - **The sanitised value was load-bearing** (`#69`), and three passes joined on it. "Fix at
    the emitter" therefore meant splitting the field, not changing its value.
  - **A second failure path from the same cause**: `_subtract_unresolvable_links` (`:902`)
    joins the same two forms, so a withheld link for a colon-titled note was also counted as
    missing. Covered, and proven RED by reverting the emitter.
  - **The garden branch must NOT carry the new field.** `gen-garden-audit-hashi-example.py`
    calls `_build_garden_audit_actions` directly and embeds its output in a Hashi handoff
    document, never running `_strip_internal_link_fields`. Adding it there broke
    `test_garden_audit_hashi_example.py` at once — the triad's schema half doing its job.

  Two existing tests were inverted rather than deleted, both recorded in `docs/tomo/`:
  `test_instruction_render_wire_hygiene.py:436` encoded the defect; spec 031's byte-identity
  guard was **sharpened** rather than loosened — it now names the post-031 field explicitly
  and still requires every other key to be identical to the pre-031 module.

  Both action goldens re-recorded via their own `record.py`, after a script proved the delta
  was exactly seven added `source_note_stem` keys with nothing removed or changed. Suite
  3757 → 3769, `ruff` clean.

- [x] **T6.4c A withheld clash leaves its staging notes in the inbox**
      `[activity: backend]` — **Found by the T6.4 live run, 2026-09-09.**

  **Inherited context.** Pass 2 renders each approved atomic into the inbox as a staging note
  (`doc_type: rendered-note`, `state: pending-move`) **before** `validate_destinations` runs. When
  the clash guard then withholds both claimants (T5.3), their staged files are already written and
  remain, waiting for a move that will never be emitted. Observed live: two
  `2026-09-08_1813_elbe-schifffahrt-…` files, one per withheld claimant.

  **Not a loop and not data loss.** `pending-move` is excluded from fresh-source discovery, so
  nothing re-ingests them, and the guard's own promise — "every source note below is untouched in
  the inbox" — holds. But nothing clears them either: `detect_orphaned_state` covers *captured
  source items whose downstream docs vanished*, a different case. The remedy the document prints
  ("give one of them a different name and re-run Pass 2") renders a **fresh pair each time**, so
  the residue accumulates once per clash per re-run.

  **Two directions, and they are not equal.** Rendering *after* validation is the larger change and
  would also stop paying Kado writes for notes that are then withheld — but it moves a step whose
  ordering other passes may depend on. Alternatively the clash record carries its withheld staging
  paths so something can clean or reuse them. **Weigh both and state the choice**; do not assume
  the first is available.

  1. **Prime**: read `validate_destinations` (`lib/render_actions.py`) and where Pass 2 writes
     staged notes relative to it. Read `detect_orphaned_state` (`inbox-triage.py:1438`) to see why
     it does not cover this. Read T5.3's block in `plan/phase-5.md` for what the clash record
     already carries `[ref: SDD/ADR-4]`.
  2. **Test** (RED):
     - a run whose destination clash withholds both claimants leaves **no** orphaned
       `pending-move` note behind — assert the vault/write surface, not an internal list
     - a run with no clash is byte-identical to today — both action goldens unchanged
     - re-running after the user renames one item does not accumulate a second pair
     - proven RED against HEAD, where the pair remains
  3. **Implement**: whichever direction you chose, and say why in the `docs/tomo/` mirror.
  4. **Validate**: full suite green; `ruff` clean; neither action golden re-recorded — a no-clash
     run must not change.
  5. **Success**:
     - [x] A withheld clash leaves nothing behind that nobody will move
     - [x] A no-clash run is unchanged

  **Closed 2026-09-09.** Neither direction as written was the one taken, because the prime
  read found the premise wrong: `instruction-render.py` never writes a staging note to the
  vault. It renders locally and lists each file in `manifest.json`; a **separate process**,
  `upload-rendered.py`, writes one vault note per entry. The residue is produced there.

  So the manifest is rewritten after both guards, and the upload never sees the withheld
  entry. No step's ordering moved, `upload-rendered.py` was not touched, and the Kado write
  the larger direction hoped to save is saved as a side effect — the note is never uploaded.

  Direction (a) as the task worded it — "render after validation" — is unavailable, not
  merely risky: `build_actions` is built **from** the manifest, so rendering cannot follow a
  validation that consumes its output.

  Three things the diff found that the task did not name:

  - **The clash record cannot be joined to the manifest at all.** Its `dropped` entries carry
    the action `id`, which is a fresh `_next_id` counter value. `rendered_file` is the only
    key both sides hold, so the pass works from the surviving actions instead of from either
    withholding report.
  - **A second site of the same shape.** `suppress_moves_for_unfiled_attachments` withholds
    `move_note` through the same `_drop_moves_with_paired_deletes` helper and leaves the same
    residue. Covered by the same pass, with its own RED test.
  - **"No surviving claim" is not "withheld".** The first implementation compared only the
    post-guard actions and emptied the manifest of any run whose action building produced
    nothing — three existing tests that stub `build_actions` caught it. `claimed_before`
    (the pre-guard claim set) is what makes the pass precise; `test_entry_never_claimed_by_an_action_is_kept`
    pins it.

  Not covered, deliberately: the by-Name `create_moc` merge drops its duplicate **inside**
  `build_actions`, so the absorbed entry has no pre-guard claim either. That path is
  defense-in-depth for a merge `suggestion-parser.py` already performs, and it emits no
  record. Recorded in `docs/tomo/scripts/lib/render_actions.md`.

  Assertions are taken at the vault write surface — the targets `upload-rendered.py` hands to
  Kado — not at an internal list. Suite 3768 → 3773, `ruff` clean, no golden re-recorded.

- [x] **T6.5 Phase Validation and close-out** `[activity: validate]`

  - Full suite green, `ruff` clean.
  - Walk the SDD Quality Requirements table and confirm each row has a passing measurement.
  - Walk the PRD's 40 acceptance criteria and confirm each maps to something green.
  - Write the handoff to the sibling component describing the widened bare-name ambiguity in
    its own matching, aimed at the wire builder `[ref: spec 034 README, Hashi decision]`.
  - Set the spec to `Implemented` via `xdd-meta finalize` — only after T6.4 passes. A spec left
    on `Ready` after shipping is the failure this step exists to prevent.
