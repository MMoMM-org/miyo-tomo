---
title: "Phase 4: The name becomes a value"
status: in_progress
version: "1.0"
phase: 4
---

# Phase 4: The name becomes a value

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: PRD/F2]` — seven acceptance criteria
- `[ref: PRD/Detailed Feature Specifications; Feature F2]` — business rules and six edge cases
- `[ref: SDD/ADR-4]` — inline shape, parser trusts the backtick text
- `[ref: SDD/Runtime View; Primary Flow — Pass 2, markdown path]`
- `[ref: SDD/Implementation Gotchas]` — two of the three apply here

**Key Decisions**:
- The markdown's shape does **not** change. The parser reads the backtick content
  unconditionally, with no "was this edited?" flag: on an untouched document that
  text *is* the computed name, so the common case stays byte-identical
  `[ref: SDD/ADR-4]`.
- The "no free name available" line gains **empty backticks**, so the owner has
  somewhere to type in the case that most needs a rename — owner ruling
  2026-09-29 `[ref: README/Decisions Log]`.
- An unreadable name is a **refusal**, never a fallback and never a different
  remedy. The label prefix still matches, so the entry is never mis-routed
  `[ref: SDD/ADR-4 trade-offs]`.

**Dependencies**: **Phase 2** (the wire must carry `proposed_name` before both
surfaces can be proven to converge) and **Phase 3** (the guard must exist before
the input does).

---

## Tasks

Delivers the capability the owner asked for: naming the file themselves, on either
surface, landing into an already-guarded path.

- [x] **T4.1 The markdown offers a place to type** `[activity: frontend-ui]`

  1. Prime: read `render_attachment_conflicts_block` in `suggestions-reducer.py`,
     specifically its pre-ticked **rename line** (`lines.append(f"- [x] Rename to
     `{rename_target}`")`) and its **`RENAME_IMPOSSIBLE_MARKER` branch**
     (`lines.append(f"- [ ] Rename — {RENAME_IMPOSSIBLE_MARKER}")`). The marker
     itself is `RENAME_IMPOSSIBLE_MARKER` in `lib/attachment_conflict_states.py`.

     **Grep for those two statements rather than trusting a line number** — this
     task edits the file they live in, so any number here is stale the moment you
     start. As of 2026-10-02 they were at `:1518` and `:1521`, and the function at
     `:1438`; the citation convention adopted that day (see
     `docs/ai/memory/general.md`) is that the symbol is authoritative and the line
     is a dated hint, because every `suggestion-parser.py` reference in this phase
     had already gone stale by 19 lines when T3.2 grew the file above them.
  2. Test: an ordinary conflict renders **byte-identically to today**; the
     no-free-name case renders the line with empty backticks rather than no
     parameter at all.
  3. Implement: the single change is the impossible branch. The ordinary branch is
     untouched `[ref: SDD/ADR-4]`.

     **Keep `RENAME_IMPOSSIBLE_MARKER` on the line** — the owner should still see
     why the rename was impossible at the point of deciding. That is only safe
     because of T4.2's narrowed `rename_impossible`, ruled 2026-10-02; without it
     this task's empty backticks are inert. Measured before the ruling, on today's
     parser, with the real section heading and source-line shapes:

     ```
     - [x] Rename to `Atlas/290 Assets/295 Attachments/karte-2.png`
         remedy: rename                        (ordinary conflict, the control)
     - [x] Rename to `…karte-2.png` — no free name available
         remedy: ignore   <-- the typed name silently discarded
     ```

     So do **not** treat the marker as cosmetic and do not reorder the two tasks:
     if T4.1 ships before T4.2's condition is narrowed, the box this task adds
     accepts a name and throws it away, which is worse than not offering it.
  4. Validate: every existing 037 render test stays green — but **"green" is not
     the bar for one of them, and this is the task's real risk.** Measured
     2026-10-02, before dispatch.

     `tests/test_037_fix_render_parse_round_trip.py::test_render_parse_round_trip_pins_semantic_mapping`
     is the **only** test pinning the owner's 2026-09-23 decision that a
     ticked-but-impossible rename resolves to `ignore` rather than falling through
     to `rename`. It renders the null-`proposed_name` case through the real
     renderer, then edits it with a helper, `_toggle(md,
     tick_contains="Rename —", untick_contains="Keep in inbox")`.

     After this task the rendered line reads ``Rename to `` — no free name
     available``, so **`"Rename —"` no longer appears in it** and `_toggle`'s
     matcher misses. `_toggle` has no else and raises nothing — it returns the
     document unchanged for that line. So the rename box is never ticked, `Keep in
     inbox` is still unticked, and the entry reaches the parser with **zero ticks**,
     which Rule 3 also resolves to `ignore`. Executed both ways:

     ```
     today      remedy=ignore  ticks=1   - [x] Rename — no free name available
     post-T4.1  remedy=ignore  ticks=0   - [ ] Rename to `` — no free name available
     ```

     **The assertion passes in both cases, and in the second it is testing a
     different rule.** The test stops guarding "ticked-but-impossible → ignore" and
     starts guarding "zero ticks → ignore", which nothing in this spec is changing.
     T4.2 then narrows the 2026-09-23 decision with no guard watching it. This is
     spec 031's disarmed-`kind`-guard shape with one difference that makes it worse:
     **nobody has to edit the test.** It disarms itself, and a green suite reports
     success.

     So this task owns two fixes to that file, and they are not optional:
     - Update `_toggle`'s `tick_contains` to match the new line.
     - **Make `_toggle` fail loudly when a matcher misses** — raise, or assert that
       each matcher hit exactly one line. One definition, one call site, one file
       (counted 2026-10-02), so the change is contained. Without it the next reword
       of that line repeats this silently, and the helper's own docstring promises
       it "models an owner editing the actual rendered document" — an owner who
       ticks nothing is not that.

     Prove the repair: assert the tick count, or show the test RED when
     `tick_contains` is wrong. A test that cannot fail on a missed matcher is the
     defect, not the matcher.
  5. Success:
     - [x] An ordinary conflict's markdown is unchanged `[ref: PRD/F2]`
     - [x] The no-free-name line carries empty backticks `[ref: PRD/F2]`
     - [x] `test_render_parse_round_trip_pins_semantic_mapping` still ticks the
           rename box — asserted by tick count, not inferred from a green run
     - [x] `_toggle` fails loudly on a missed matcher, shown by an executed RED

- [x] **T4.2 The parser reads the name from the markdown** `[activity: backend-api]`

  1. Prime: in `suggestion-parser.py`, read `_walk_attachment_conflicts`, its
     **`rename` label prefix match** (`if label.startswith("rename"):`),
     `parse_attachment_conflict_remedies`, and
     `_join_attachment_conflict_remedies` — the last being where `proposed_name` is
     currently read from the structured doc by `source`, in the
     `proposed_names = {c.get("source"): c.get("proposed_name") ...}` comprehension
     and consumed just below it. **That comprehension is the structured-doc read
     step 3 tells you to remove**; the old text pointed at the function but never
     located the read itself.

     **Grep for the symbols, do not trust a line number here.** This task edits
     this very file, and every line number in this Prime was already wrong before
     the phase opened: T3.2 added `name_is_owner_supplied` above all of them, so
     the stated `:2268`, `:2343`, `:2355` and `:2370-2392` were short by 19, and
     the `:2998` cited below was short by 21.

     **The line numbers that stood here have been removed rather than refreshed**
     (2026-10-02, after T4.2 shipped as `c1a8ef2`). All seven had moved again, and
     two of the landmarks no longer exist as they were described: the
     structured-doc read is **gone** — removing it was this task — and
     `name_is_owner_supplied` is no longer `False` unconditionally. Refreshing the
     numbers would have been wrong twice over, and T4.3 edits this same file next,
     which would have forced a fourth sweep of the same landmarks. Grep the
     symbols: `_walk_attachment_conflicts`, its `label.startswith("rename")`
     match, `parse_attachment_conflict_remedies`,
     `_join_attachment_conflict_remedies`, `_resolve_attachment_remedy`. See
     `docs/ai/memory/general.md` for the convention and why three sweeps in Phase 3
     produced it.
  2. Test: an overtyped name is returned; an untouched default resolves to the
     computed name **byte-identically** (this flips
     `tests/test_037_typed_rename_target_is_ignored.py`'s strict xfail and deletes
     `test_the_typed_name_is_discarded_today` with it); a half-edited line with no
     closing backtick, and one with empty backticks on an ordinary conflict, both
     resolve to a refusal rather than to a fallback or a different remedy.

     **Three more cases, from the 2026-10-02 ruling, and the first is the one that
     matters**: on the no-free-name line, (a) ticked with a typed name resolves to
     `rename` carrying that name — this is the case that fails today; (b) ticked
     with the backticks still empty resolves to `ignore`, unchanged from today; and
     (c) left unticked with `Keep in inbox` pre-ticked resolves to
     `keep_in_inbox`, also unchanged. Assert (b) and (c) as well as (a): a change
     that only made (a) pass could do so by dropping the override entirely, which
     would hand Pass 2 a destination-less move in case (b).
  3. Implement: extract the backtick content on a ticked rename line and carry it
     as `proposed_name`. **Remove the structured-doc read for this value** — do not
     leave both in play, or a stale doc wins over the owner's keystrokes
     `[ref: SDD/Implementation Gotchas]`. The read to remove is the
     `proposed_names = {c.get("source"): c.get("proposed_name") ...}` comprehension
     in `_join_attachment_conflict_remedies` and the line that consumes it.

     **Also narrow `rename_impossible` — owner ruling 2026-10-02, and this is the
     task that makes T4.1's empty backticks work at all.** Today it is
     `rename_impossible = RENAME_IMPOSSIBLE_MARKER in label`, and
     `_resolve_attachment_remedy` turns `rename_ticked` plus `rename_impossible`
     into `ignore`. So the owner ticks the box T4.1 adds, types a name, and the
     name is discarded — proven on today's parser before the ruling:

     ```
     - [x] Rename to `…karte-2.png`                      -> rename   (control)
     - [x] Rename to `…karte-2.png` — no free name available -> ignore
     - [x] Rename to `` — no free name available           -> ignore   (correct)
     ```

     Set it to **marker present AND no usable name extracted**. The narrowing is
     faithful rather than a reversal: the 2026-09-23 decision that this state
     resolves to `ignore` rests on a reason stated in
     `_resolve_attachment_remedy`'s own docstring — *"passing `rename` through with
     no `proposed_name` would hand Pass 2 `_asset_dest_join(asset_folder, None)`, a
     move with no destination, breaking Rule 6"*. That reason cannot arise once a
     name has been typed, because there **is** a `proposed_name`. Empty backticks
     left untouched still resolve to `ignore`, exactly as today — which is the
     third line above, and it must stay that way.

     **Update that docstring in the same commit.** It currently states the
     unconditional rule, and a WHY text left asserting the old behaviour is the
     failure spec compliance FAILed T3.2 for twice. Say that the override is about
     the absence of a name, not the presence of a marker.

     **One more line in the same file, found by T4.1's review sweep (2026-10-02)**:
     `_resolve_attachment_remedy`'s docstring also quotes the rendered line as
     *the "Rename — no free name available" line* — the pre-T4.1 shape. T4.1 made
     it ``Rename to `` — no free name available``. Correct the quotation while you
     are in that docstring; it is the sentence a reader checks the new condition
     against, so a stale quote there is worse than one in a doc.

     And **replace the old-shape parser fixtures**:
     `tests/test_037_t2_4_parse_remedy.py`'s `RENAME_IMPOSSIBLE_TICKED` and
     `RENAME_IMPOSSIBLE_UNTICKED` are hand-built markdown of the pre-T4.1 line.
     They are green and will stay green, because the parser still accepts the old
     shape — which is exactly the trap: they test a document the renderer no longer
     produces. This repo has recorded that fixture-drift failure before ("mirror
     live renderer output"). Add new-shape fixtures; keep an old-shape one only if
     you deliberately want to pin backward tolerance, and say so in its name.

     **And set `name_is_owner_supplied` here — T3.2 added it, and this task is
     where the markdown side stops being `False`.** The rule is NOT `True`
     unconditionally, and getting that wrong re-opens the behaviour change the
     owner avoided on 2026-10-01. Compare against the **rendered** form of the
     computed name, **not the bare name** — step 3b below specifies the
     comparison and carries the measured table. Reasoning, measured during
     T3.2's amendment:
     - After this task every markdown `proposed_name` comes from the rendered
       text, an untouched pre-ticked default included. Flagging all of them
       `True` would make T3.2's check refuse an untouched default whose computed
       name carries an Obsidian-forbidden character — and `* " | < > \` are all
       legal in macOS filenames, so `foo*bar (2).png` is a real computed name.
       That is precisely the "check every name" option the owner rejected, and it
       would also contradict this task's own test that an untouched default
       resolves to the computed name **byte-identically**.
     - The comparison is **free here** and only here: this path already loads the
       doc — `parse_attachment_conflict_remedies(text), _load_json_doc(_own_doc_path)`
       at the sole `parse_attachment_conflict_remedies(text),
       _load_json_doc(_own_doc_path)` call site in `main` — grep that pair; the
       line numbers two drafts of this sentence carried were both stale within a
       day. The wire path keeps `True`
       unconditionally because it deliberately does not load the doc — Phase 2's
       T2.5 measured the JSON-only path working with `--file` plus
       `--suggestions-json` and no `--suggestions-doc`, and re-coupling it would
       undo that.
     - The asymmetry is therefore not an inconsistency: each side uses what it
       has. It does mean an untouched unusable default is refused on the wire and
       permitted in the markdown. Acceptable because the wire path ships to the
       consumer for the first time in Phase 5, so no deployed behaviour changes —
       but say so in the handoff rather than letting them discover it.
  3b. **The markdown renders a PATH, the doc carries a BARE NAME, and that
     changes three things in step 3. All measured 2026-10-02, before dispatch,
     through the real renderer.**

     `render_attachment_conflicts_block` puts `_asset_dest_join(asset_folder,
     proposed_name)` in the backticks — a full destination path. The structured
     doc's `attachment_conflicts[]` record carries `proposed_name` as a bare
     basename. So on an **untouched** default:

     ```
     extracted         = 'Atlas/290 Assets/295 Attachments/karte (2).png'
     doc proposed_name = 'karte (2).png'
     extracted != doc proposed_name  ->  True    <-- on an UNTOUCHED default
         -> name_is_owner_supplied True -> check_typed_name
         -> REFUSED separator_present
     ```

     **(a) Compare like with like.** The operand is the rendered default, which
     costs no new field: the record's `destination` is
     `_asset_dest_join(asset_folder, source)`, so the folder is
     `destination.rsplit('/', 1)[0]` and the rendered default is that folder
     joined with `proposed_name` through the same helper. Measured: equal, so
     `name_is_owner_supplied` is `False` and the byte-identical criterion holds.
     `_asset_dest_join` normalises a trailing slash, so the folder form the doc
     happens to carry does not matter — the 037 fixture uses the trailing-slash
     variant and agrees.

     **(b) Un-render the folder prefix — owner ruling 2026-10-02.** Because the
     markdown shows a path, the natural owner edit is to change the filename and
     leave the folder, and that contains a separator, which T3.1 refuses. The
     two 037 fixtures already encode the answer and neither can be satisfied any
     other way: `_markdown()` prepends the asset folder to whatever it is given,
     while `test_the_untouched_default_resolves_to_the_computed_name` asserts a
     **bare** `COMPUTED` and the strict xfail asserts a **bare** `TYPED`.
     **Do not read those two fixtures as the proof, and do not read them as
     coverage.** An earlier draft of this paragraph claimed no implementation could
     satisfy them without un-rendering. That is false, measured 2026-10-02 by
     applying the mutation: a plain `rsplit("/", 1)[-1]` returns `karte (2).png`
     for the untouched default and `karte-dresden-1938.png` for the typed one,
     which is exactly what each fixture asserts. Under a `basename()` the whole of
     `tests/test_037_typed_rename_target_is_ignored.py` stays green, and so do both
     overtyped-name cases — `1 failed, 12 passed`, the single failure being
     `test_a_different_folder_typed_is_refused_separator_present`.

     So what rules out `basename()` is the **`Archive/` row of (d)** — the row the
     TDD gate added — and not the 037 fixtures at all. The fixtures establish only
     that the output must be a bare name; the `Archive/` row establishes *how* it
     may become one. A reader who takes the fixtures as sufficient evidence will
     also take them as sufficient coverage, and skip the row doing the real work.
     So the
     parser strips the prefix the renderer itself wrote, then judges the
     remainder. **This is not sanitising and does not touch ADR-5**: what is
     removed is the renderer's own join, not owner input. Strip **only** an exact
     match for that record's folder — a folder the owner typed themselves does
     not match, so it still refuses. Measured table:

     ```
     case                      owner?  remainder                   verdict
     untouched default         False   'karte (2).png'             guard skipped
     filename edited in place  True    'karte-dresden-1938.png'    OK
     folder deleted too        True    'karte-dresden-1938.png'    OK
     a different folder typed  True    'Archive/karte-…938.png'    REFUSED separator_present
     forbidden char, in place  True    'karte|1938.png'            REFUSED forbidden_character
     empty backticks           True    ''                          see (c)
     folder left, name deleted True    ''                          see (c)
     ```

     F3-AC1 keeps its teeth: the only separator that stops being refused is one
     this program printed. Say this in the `docs/tomo/` entry (T4.4) — a reader
     comparing F3-AC1 to the code will otherwise read it as a contradiction.

     **(c) The marker branch must be evaluated BEFORE the guard, and this is the
     one that fails silently if you get it backwards.** An emptied set of
     backticks yields remainder `''`, and `check_typed_name('')` is
     `REFUSED blank` (measured; `blank` is one of the three `REFUSAL_REASONS`).
     Two lines reach that state and they must NOT resolve alike:
     - **Ordinary conflict, backticks emptied** — no marker, so the narrowed
       `rename_impossible` is `False`. Carry `""` with the flag `True`, **not**
       `rename` with a null name.

       **Correction, 2026-10-02.** An earlier draft of this bullet said "nothing
       else stops it, so it would fall through to `rename` with `proposed_name`
       `None` and hand Pass 2 `_asset_dest_join(folder, None)`". That was wrong,
       and it was wrong in the implementer's brief too. Something does stop it:
       `_build_move_asset_actions` tests `remedy == "rename" and not
       remedy_entry.get("proposed_name")` (`render_actions.py:848-849` as of
       2026-10-02) — a **falsy** test, so `""` takes it as well as `None` — and
       that branch precedes the `name_is_owner_supplied` gate at `:902` by 53
       lines. The destination-less move has been unreachable on this route since
       037's T3.1; the degrade to `vault_collision_held` is the documented
       "a rename that lost its name" path.

       So the owner reads the `vault_collision_held` sentence, not a refusal.
       Both withhold the move; only the wording differs. Measured through
       `_build_move_asset_actions` with the flag `True` on every row:

       ```
       proposed_name=''              -> skipped vault_collision_held
       proposed_name=None            -> skipped vault_collision_held
       proposed_name='   '           -> skipped typed_name_refused  blank
       proposed_name='Archive/x.png' -> skipped typed_name_refused  separator_present
       ```

       Row 3 is the sharp one: `blank` **is** reachable, but only for a truthy
       whitespace-only name. For `""` it is not reachable at all, because the
       value that would trigger the refusal is the same value that triggers the
       degrade one branch earlier.
     - **The no-free-name line, backticks still empty** — marker present and no
       name, so the narrowed condition holds and it resolves to `ignore`,
       unchanged from today. If the guard runs first it becomes
       `typed_name_refused` instead, and T3.4 then renders a refusal bullet for a
       name the owner never typed. Nothing in the suite asserts the absence of
       that bullet, so assert it: the test for case (b) in step 2 must check the
       remedy is `ignore` **and** that no `typed_name_refused` is emitted.

     **(d) Every row of the table above is a required test case, and every
     refusal assertion names its `reason`.** Added after the TDD gate BLOCKed
     this task on exactly these two gaps (2026-10-02).

     The un-rendering is load-bearing and nothing in the suite exercises it: an
     implementation that omits the strip, or that mishandles the trailing-slash
     form the doc may carry, leaves every test green while the natural owner
     edit silently refuses. So assert, each as its own case:

     | owner edit | expected |
     |---|---|
     | filename edited in place, folder left | `rename`, `proposed_name` the bare typed name |
     | folder deleted too | `rename`, same bare typed name |
     | a **different** folder typed | refusal, `reason` `separator_present` |
     | forbidden character, folder left | refusal, `reason` `forbidden_character` |
     | folder left, filename deleted | ordinary conflict: `proposed_name` `""`, flag `True`, and `check_typed_name` verdicts it `blank` |
     | folder left, filename deleted | no-free-name line: `ignore`, no refusal |

     **Row 6's "no refusal" half must be asserted on the RECORD, not on the
     rendered bullet — the bullet assertion is vacuous.** Measured 2026-10-02 by
     removing the override's veto on provenance: no `typed_name_refused` bullet is
     emitted under the mutation either, because `''` is falsy and the degrade at
     `render_actions.py:848-849` fires before provenance is ever consulted. The
     refusal bullet for a name nobody typed is unreachable today for **structural**
     reasons, not because the ordering is right — so a test written only against
     the bullet, which is what (c) above literally asks for, passes the mutation
     silently. Assert the exact record (`proposed_name` and
     `name_is_owner_supplied` both) and keep the bullet check as a second,
     weaker line. With the record asserted, the mutation kills two tests:
     `…ticked_but_still_empty_stays_ignore` and
     `…left_alone_keeps_the_attachment_in_the_inbox`, the latter because the record
     claims an owner-supplied `''` for a line the owner never touched.

     **And check that your own fixture can tell the conditions apart.** T4.2's
     implementer found their first version of the typed-name case survived
     `marker_unconditional` — restoring `RENAME_IMPOSSIBLE_MARKER in label` — at
     `13 passed`, because the fixture had replaced the whole rename line and
     deleted the marker prose with it. `rename_impossible` was then `False` under
     both forms of the condition and the test could not tell which one it was
     running against: right outcome, wrong document. Type **between the
     backticks** and leave the marker standing. This is the third test in this
     spec that could not fail for the reason its name gave, and the first one its
     own author caught.

     Row 5 is asserted **at this task's boundary**, not end-to-end: see the
     correction in (c). No parser-only change can make Pass 2 report
     `typed_name_refused` with `refusal_reason: blank` for an emptied line. Pin
     `vault_collision_held` as today's surfaced answer alongside it, and name the
     mechanism in the test docstring so the pin reads as a measurement rather
     than an endorsement. Changing which sentence the owner reads needs
     `render_actions.py`, which is not this task's file — if it is wanted, it is a
     backlog entry, not a widening of T4.2.

     The first two must yield the **same** `proposed_name` — that is what proves
     the strip is a prefix match and not a `basename()`.

     **Name the reason, never just the polarity.** "Resolves to a refusal" is
     true before and after the change for different reasons, so it distinguishes
     nothing: a broken strip leaves the full path in the remainder and refuses
     `separator_present`, where the correct behaviour on an emptied line refuses
     `blank`. Both are refusals. This is the same shape as the guard T4.1 nearly
     disarmed — an assertion that keeps passing while testing a different rule —
     and it is why `REFUSAL_REASONS` carries three members rather than a boolean.

  4. Validate: full suite; the 037 baseline test
     (`test_the_untouched_default_resolves_to_the_computed_name`) is the regression
     floor and must stay green.
  5. Success:
     - [x] A typed name reaches Pass 2 `[ref: PRD/F2]`
     - [x] An untouched default is byte-identical to today `[ref: PRD/F2]`
     - [x] The strict xfail is **removed**, not left passing — zero `xfailed`
           in the suite, which was its only one
     - [x] An unreadable name is a refusal, never a fallback `[ref: PRD/F2]` —
           with the `reason` named per case, not merely the polarity
     - [x] The structured doc is no longer consulted for this value `[ref: SDD/Implementation Gotchas]`

  6. **Measured 2026-10-02, and worth a decision inside this task: the markdown
     invites the refusal.** The ordinary line renders the FULL destination path in
     its backticks — `_asset_dest_join(asset_folder, proposed_name)` — so the
     natural owner edit is to change the filename and leave the folder. Run through
     T3.1's check:

     ```
     'Atlas/290 Assets/295 Attachments/karte (2).png'   REFUSED separator_present  (untouched default)
     'Atlas/290 Assets/295 Attachments/karte-scan.png'  REFUSED separator_present  (the natural edit)
     'karte-scan.png'                                   OK                         (a bare name)
     ```

     The first line is why this task's `extracted != computed` rule is load-bearing
     rather than a nicety: without it, every untouched default is refused. The
     second is the gap. **The behaviour is correct and already ruled** — ADR-5, a
     typed name is rejected and never sanitised, and F3-AC1 refuses a separator
     rather than truncating to the last segment. Do **not** strip a leading folder
     to be helpful; that is the option ADR-5 closed.

     What is open is only the **remedy wording**. `_typed_name_refusal_reason`'s
     separator sentence says the name *"contains a path separator, which is not
     allowed in a filename"* — true, and no use to someone the document just showed
     a path to. Consider having T3.4's `typed_name_refused` remedy line say to type
     the filename only, not the folder. That is a change to a sentence Phase 3
     shipped, so raise it rather than edit it silently, and keep it out of this
     task's production diff if it widens scope `[ref: PRD/F3, SDD/ADR-5]`.

- [x] **T4.3 Validate before the embed is rewritten** `[activity: backend-api]`

  1. Prime: read `rewrite_renamed_embeds` (`lib/embed_rewrite.py:91`) and note the
     ordering stated in its docstring — it runs **before**
     `_build_move_asset_actions`, so it recomputes the new basename from
     `proposed_name` directly rather than reading it back from a move action
     `[ref: SDD/Implementation Gotchas]`.
  2. Test: a **refused** typed name leaves every owning note's embed untouched.
     Without this ordering the embed is rewritten to a name the move then refuses,
     leaving bodies pointing at a file that was never created.

     **This is a live defect, not a hypothetical. Measured 2026-10-03, before
     dispatch, by running both halves of the pipeline on the same remedy record.**
     `rewrite_renamed_embeds` gates on `remedy == "rename"` plus a truthy
     `proposed_name` and consults neither `name_is_owner_supplied` nor
     `check_typed_name`:

     ```
     case               guard                       embed rewritten  move
     accepted           ok=True                     yes              actions=1
     refused separator  ok=False separator_present  YES              0, typed_name_refused
     refused pipe       ok=False forbidden_character YES             0, typed_name_refused
     refused blank      ok=False blank              YES              0, typed_name_refused
     ```

     So for every refusal the body **is** rewritten and the move is **not** made:
     the attachment stays in the inbox under its old name while the note points
     somewhere else. **T3.2 created this divergence** — it added the refusal to the
     move builder without touching the rewrite — and it is reachable in production
     now, because the wire path carries `name_is_owner_supplied: True`
     unconditionally; T4.2 opened the markdown path to it as well. Treat this task
     as closing a defect, not as adding a nicety.

     **There are three failure modes and this task's sentence above describes only
     one of them.** Measured bodies, from `![[karte.png]]`:

     | typed | body becomes | what it is |
     |---|---|---|
     | `Archive/karte-…938.png` | `![[Archive/karte-…938.png]]` | dangling, **and** hard-codes a path |
     | `karte\|1938.png` | `![[karte\|1938.png]]` | **not** dangling — see below |
     | `   ` | `![[   ]]` | an embed of whitespace |

     The middle row is the one that justifies the priority. `|` is Obsidian's
     **alias separator**, so `![[karte|1938.png]]` is not a broken link — it is an
     embed of a *different* note named `karte`, displayed as `1938.png`. If such a
     note exists the owner sees real content from the wrong file, with nothing
     visibly wrong. A dangling embed announces itself; this does not. A second
     occurrence carrying its own size suffix becomes `![[karte|1938.png|300]]`.

     **And the function's own docstring already promises what the code does not
     do**: *"the OLD basename is replaced by the BARE new basename … never the new
     full path (which would hard-code the asset folder into every rewritten
     body)"*. `new_name` is used verbatim with no basename step, so that guarantee
     holds only for names that pass the guard, and nothing enforces it today. Fix
     the claim or the code in the same commit — do not leave the docstring
     asserting a property the code lacks, which is the failure spec compliance
     FAILed T3.2 for twice.

     **Coverage today is zero**: `grep -c name_is_owner_supplied
     tests/test_037_t3_3_embed_rewrite.py` → `0`. Nothing in that file's nineteen
     cases involves a typed name at all.
  3. Implement: the rewrite must skip a refused entry.

     **Scope correction (2026-10-03): the first half of this step is already
     done.** It read "ensure the verdict from Phase 3's check is available before
     the rewrite runs" — it is available. The remedy record reaching
     `rewrite_renamed_embeds` already carries both `proposed_name` and
     `name_is_owner_supplied`, and `lib/typed_name_check.py` imports nothing at all
     (stdlib only), so there is no circular-import obstacle; `embed_rewrite.py`
     already imports from `lib.attachment_index`. Nothing needs plumbing. Only the
     skip needs building.

     **Put the gate in `rewrite_renamed_embeds` itself, not in the
     `instruction-render.py` caller.** The guarantee that is being broken is stated
     in that function's docstring, the function is the one T4.4's convergence
     criterion is about, and a gate in the caller leaves the library wrong for the
     next caller. Gate on the same condition `_build_move_asset_actions` uses —
     `name_is_owner_supplied` truthy, then `check_typed_name`.

     **State the cost in the docstring, because it is real**: `check_typed_name`
     is then called from two places that must keep agreeing, and nothing in the
     type system makes them. That agreement is testable and the test is cheap —
     one case that feeds a refused name to **both** halves and asserts the move
     builder emits `typed_name_refused` **and** the body comes back byte-identical.
     Write that test; it is the one that fails if the two conditions drift apart,
     which no per-half test can catch.

     The single-verdict alternative — compute the refusal once upstream and carry
     it on the record so both consumers read a field instead of re-deciding — is
     better in principle and **out of scope**: it changes the wire contract and
     would need a Hashi handoff. Recorded in `docs/XDD/backlog.md`; do not build it
     here.
  4. Validate: the 037 embed-rewrite tests stay green; the new test fails if the
     ordering is reversed — **construct that reversal and run it**.
  5. Success:
     - [x] A refused name rewrites no embeds `[ref: PRD/F2, PRD/F3]` — all three
           classes, each asserting its own `reason`
     - [x] An accepted typed name rewrites every owning note's embed, as 037
           already does for a computed name `[ref: PRD/F2]`
     - [x] The ordering mutation turns the test red, demonstrated — and the
           mutation chosen was stronger than the one asked for: the gate was moved
           BELOW the assignment rather than deleted, so the verdict is computed and
           then ignored. That proves the gate runs **in time**, not merely that it
           runs. 4 of 8 tests die; the 29 pre-existing cases are blind to it.

- [ ] **T4.5 A withheld attachment reaches the shell** `[activity: backend-api]`

  Owner direction 2026-10-03, and it closes the reopened half of `[ref: PRD/C1]`.
  **Execution order: this task runs BEFORE T4.4**, which validates the phase.

  1. Prime: read spec 036's withheld-delete relay end to end, because this task
     re-applies it rather than inventing anything. The writer emits
     `tomo-tmp/withheld-deletes.md` — one pre-sanitised, user-facing line per
     withheld delete, and **nothing else**: no run id, no header, no internals.
     `tomo/dot_claude/agents/synthesis-conductor.md`'s **Step 4 — Report** `cat`s
     it and appends its lines **verbatim**, only when the file exists, and is
     explicitly forbidden from substituting the raw stderr block or the JSON.
     Read why it is built that way: the sanitising lives in a script, where it is
     testable, instead of asking the LLM to summarise internals.

     Then measure the gap. Step 4's report lists the doc count, the coverage
     audit, drift warnings and withheld deletes. **Skipped assets are absent**,
     and a skip is not an error — `instruction-render.py` exits 0, which Step 3b
     treats as plain success. Measured 2026-10-03.
  2. Test: a run with at least one withheld attachment writes a relay file whose
     lines name each withheld attachment; a run with none writes **no file at
     all** (the delete relay's contract — Step 4 keys on existence, so an empty
     file would print an empty section). Cover every `kind` that withholds a
     move: `typed_name_refused`, `vault_collision_held`, `collision`,
     `no_basename`. Assert whole lines.
  3. Implement, and **the first step is an extraction, not a write** — measured
     2026-10-03, before dispatch.

     **(a) The delete relay's whole trick is that its sentence is already a
     function.** `_render_withdrawn_delete_notice(withdrawal) -> str` lives in
     `render_md.py`, and `instruction-render.py` calls it a **second** time to build
     the relay. The comment at that call site states the reason outright: *"this
     calls the same function a second time rather than re-deriving them, so the two
     surfaces cannot drift apart."*

     **The asset bullet is not a function.** It is built inline inside
     `render_instructions_md`'s loop: a per-`kind` `if`/`elif` chain assigning
     `remedy`, then one `body_parts.append(f"- ⚠️ **Attachment not filed:** …")`.
     So **extract it first** — a `_render_skipped_asset_notice(entry) -> str`
     beside the delete one, called from the loop *and* from the relay. Skip the
     extraction and "one source, two surfaces" is unachievable: you would be
     re-deriving the sentence, which is the drift this spec has spent four tasks
     paying for.

     **(b) Reuse the relay WRITER as it stands; do not write staleness logic.**
     `sync_withheld_deletes_file(path, run_id, notices)` (in
     `instruction-render.py`) already takes an arbitrary list of notice strings,
     and its subtlety is the part you would get wrong. `--output-dir` is
     overwritten per entry, which made an earlier grep-and-remember relay lose
     entries 1..N-1 of an N-entry run; the fix is a `.run_id` sidecar that
     distinguishes same-run append from new-run rewrite. A half-present state is
     always staleness. `run_id is None` is a no-op. A new run with no notices
     removes **both** files, which is what gives you the "no file when there is
     nothing to say" behaviour for free.

     Its name is delete-specific. Generalising it serves one mechanism with one set
     of staleness semantics and is preferred, but it touches 036's call site and
     `tests/test_instruction_render_withheld_deletes_relay.py` — if you generalise,
     keep that test green and say so; if you add a thin sibling instead, say why.

     **(c) Markdown in the relayed line is the established shape — do not invent a
     plainer one.** The delete notice is `- ⚠️ **Not deleted:** <ref> — <detail>`
     and Step 4 relays it verbatim. The asset bullet is `- ⚠️ **Attachment not
     filed:** \`<source>\` — <reason>. <remedy>.` — same marker, same register.
     Reuse it as it is.

     **(d) Where to write it.** `skipped_assets` is final where `build_actions`
     returns it and is never extended afterwards —
     `suppress_moves_for_unfiled_attachments` takes it read-only and returns
     `(kept_actions, suppressions)`. So write the relay beside the delete relay,
     after both fatal-abort guards, matching that call's own rule: *a run that
     aborts before this point writes nothing*.

     **(e) One inherited wart, named so nobody silently "fixes" it.** The per-`kind`
     chain ends in a deliberate loud fallback — `(No remedy defined for skip kind
     '…' — check render_md.py)` — which the relay will now put in the shell. It is
     deliberate: an unrecognised kind must not inherit another kind's instruction.
     Leave it loud. If you think a filename in a user-facing line is wrong, raise it
     rather than softening it.

     Then add the `cat` and the relay instruction to Step 4, alongside the delete
     relay.

     **One line per withheld attachment, never a count** `[ref: PRD/C1]`. The
     no-count ruling is argued twice in `render_md.py` and T3.4's undercount is
     the evidence; the line-per-item shape satisfies C1's intent without
     re-opening it.

     Each line must say what was withheld, which attachment, and what the owner
     can do — the document's per-`kind` remedy sentences already exist and are
     owner-reviewed, so reuse them rather than writing new prose. Do **not** put
     a path the owner cannot act on, a `kind` token, or a refusal code in the
     line: those are internals, and the delete relay's contract excludes them.
  3c. **Four test requirements from the TDD gate (2026-10-03), which BLOCKed this
     task until they were written in.** Two were gaps, one was already required,
     one was disputed and substituted — the reasoning is kept because the
     substitution is the kind a later reader would otherwise reverse.

     **(i) Name the byte-identity test, and write it BEFORE the extraction.**
     `test_extraction_preserves_rendered_document_byte_identical`, with the four
     kinds' notice strings as whole-string literals. The gate proposed comparing
     against "the document generated by the old inline code" — **not achievable**,
     because after the extraction that code no longer exists to compare with. The
     achievable form is the TDD order: capture today's output at `HEAD` as literals
     first, then extract. Then the literals *are* the pre-extraction behaviour and
     the test genuinely pins byte-identity rather than pinning whatever the new
     function happens to emit.

     **(ii) Prove the two surfaces share one code path, by mutation.** This is the
     gate's answer to a question this task could not answer itself: a test that
     compares the document's bullet to the relay's line passes when the relay
     *independently* builds the same string, so it cannot catch someone later
     re-deriving it. So **mutate `_render_skipped_asset_notice` to emit broken
     output and assert the mutation fails BOTH the document test and the relay
     test.** If it fails only one, the surfaces were never linked and the whole
     design of this task is absent while its tests are green. Run it and report
     which tests died.

     **(iii) The "no file" test must exercise staleness REMOVAL** — already
     required above, restated because the gate independently arrived at it. A
     fresh directory where no file ever existed proves nothing: the contract is a
     file **and** its `.run_id` sidecar left by a previous run, both of which the
     new run must remove. Assert both are gone.

     **(iv) The agent instruction gets a wiring guard, NOT an output test.** The
     gate asked for a test that "captures the synthesised report output from Step
     4" and asserts the relay lines appear. **Declined, and the reason is
     structural**: `tomo/dot_claude/agents/synthesis-conductor.md` is an LLM-loaded
     runtime prompt, not code. There is no Step 4 output for pytest to capture,
     because the report is produced by a model following a prompt at runtime. This
     repo has already recorded that an agent definition's rules are not what the
     LLM does and that the verification for it is a **live run** — Phase 5's T5.3,
     which this task's relay must therefore appear in. Asserting the instruction
     text exists in the file is a test that a string is in the file someone just
     wrote it into.

     What is worth building instead is a **wiring guard**: assert the runtime file
     references the same relay path the writer writes, so the instruction cannot be
     deleted while the writer stays, or drift to a different filename. This repo
     has precedent for that class — a CLI contract change needs a sweep of
     `dot_claude/` that pytest is otherwise blind to. One assertion, one direction:
     the path, not the prose.

  4. Validate: full suite; and confirm by reading `synthesis-conductor.md` that
     the new instruction cannot be satisfied by summarising stderr — the delete
     relay needed an explicit prohibition to stop exactly that. **Reading is the
     right verification here, not a test** — see 3c(iv); the executable check is
     the live run in Phase 5.

  4b. **Why requirement (ii)'s mutation test earns its place — measured, after it
     was nearly argued away.** Keep this; it is the reason the test must not be
     deleted as redundant later, and it was established by running the mutation
     that matters rather than the one that was easy.

     A relay that re-derives its line by **copy-pasting** the notice function's
     body — so both surfaces emit **byte-identical** strings today — kills **only**
     the mutation test. The two comparison tests pass, the byte-identity pin
     passes, the whole-line relay test passes: `1 failed, 7 passed`. An earlier
     mutation that differed by one character was caught by the comparison tests,
     which is why the mutation test briefly looked redundant — but that is a
     *divergent* duplicate, the easy case. **The realistic regression is a
     duplicate that agrees today and drifts when one copy is edited**, and every
     test that compares the two surfaces is blind to it, because they genuinely
     agree.

     In one line: **comparing two surfaces proves they agree; only mutating their
     shared source proves they cannot disagree.** That is the property T4.5 was
     asked to establish.

     | test | divergent duplicate | identical duplicate | the sentence regressing |
     |---|---|---|---|
     | `…relay_lines_are_the_documents_own_bullets` | catches | **blind** | blind |
     | `…a_new_run_replaces_a_previous_runs_notices` | catches | **blind** | blind |
     | `…mutating_the_notice_function_moves_both_surfaces` | catches | **catches** | blind by design |
     | `…extraction_preserves_rendered_document_byte_identical` | blind | blind | catches |

     Four tests, four distinct columns, no two fully overlapping, and the mutation
     test owns a column alone.

  4c. **An unattributed intermittent failure, recorded rather than closed.**
     `test_mutating_the_notice_function_moves_both_surfaces` failed **once** in a
     full-suite run (`1 failed, 4512 passed, 4 skipped`), before the hardening in
     `786d746`. It passes alone and in its own file. **Not reproduced in nine
     subsequent clean full-suite runs** (totals 4517 every time), and the
     assertion text was never captured.

     Ruled out: no `pytest-randomly`, no `pytest-xdist`, nothing in
     `pyproject.toml` affecting order — so collection order is deterministic and
     this is **not** an ordering dependency. No stray relay artifacts; the relay
     path is per-test under `tmp_path`. Only one `render_md.py` exists on disk; no
     test evicts, reloads or reassigns `sys.modules["lib.render_md"]`. Both T4.5
     test files sort adjacently and share one fixture, so pollution upstream of
     both would have taken the byte-identity pin down too — one failure, one test
     body.

     **The `__globals__` fragility fixed in `786d746` is NOT offered as the
     explanation.** It is a real defect, proven in isolation — a
     `monkeypatch.setattr` on the module could silently miss the document surface,
     because a name resolves through the calling function's globals while `import`
     resolves through `sys.modules`, and the two are not guaranteed to be the same
     dict — and it was removed on its own merits. Nine clean runs at the observed
     one-in-three would be a 2.6% outcome, which says the rate is lower than
     observed or the trigger is environmental. Neither is "fixed".

     If it returns: make it deterministic, or quarantine it **loudly**. Do not
     delete it on the theory that the other tests cover it — per 4b they do not.
  5. Success:
     - [ ] A withheld attachment appears in the shell report, named `[ref: PRD/C1]`
     - [ ] A run with no withheld attachment writes no relay file and adds no
           section to the report
     - [ ] The shell lines and the document's bullets come from the same
           `skipped_assets`, so they cannot disagree
     - [ ] No count is introduced anywhere `[ref: PRD/C1]`
     - [ ] The document is byte-identical across the extraction, asserted against
           literals captured BEFORE it, for all four kinds
     - [ ] A mutation of the shared notice function fails **both** surfaces' tests,
           demonstrated — this is what proves they share one code path
     - [ ] A relay file and sidecar left by a previous run are **removed** when the
           new run has nothing to say

  6. **Not in this task.** The owner's related idea — telling Tomo in prose
     *"rename the target file for note X's attachment to Karte2.jpg"* and having
     it edit the **already-generated** files — is explicitly **not a must-have**
     (owner, 2026-10-03), because editing `instructions.md` and re-running
     `/inbox --pass2 --force` already does it. Recorded in
     `docs/XDD/backlog.md`; do not build it here.

- [ ] **T4.4 Phase validation — the two paths converge** `[activity: validate]`

  **Run this task LAST in the phase — after T4.5**, regardless of the numbering.

  **`docs/tomo/scripts/lib/embed_rewrite.md` has a literal task list, from T4.3's
  code quality review (2026-10-03).** That file exists and covers only 037's T3.3.
  T4.3 left its function's docstring at ~45 lines against a ~35-line body, which is
  a **pre-migration state, not a violation** — this repo's rule is that WHY moves to
  `docs/tomo/` *before* it leaves the runtime file, never the reverse. Do the move,
  in this order, then trim. Target ~15–18 lines left in the docstring.

  **Keep in the docstring** — a maintainer editing that function needs it in front
  of them:
  - the two-mechanism explanation (Tomo-computed vs owner-typed) for why "bare
    basename, never a path" holds — it is the direct rationale for the
    `name_is_owner_supplied` branch;
  - **one line** that this gate and `_build_move_asset_actions`'s gate must keep
    agreeing, since nothing in the type system enforces it;
  - **one line** naming the known gap (`collision` / `no_basename` uncovered).

  **Move to `docs/tomo/scripts/lib/embed_rewrite.md`** — history, pointers and
  design asides, which the routing rule in `CLAUDE.md` assigns there:
  - the "Until spec 038 T4.3 added that gate … asserted a property the code did not
    have" paragraph — that is what broke *before* the fix, not what the code does;
  - the named test-file pointer and its case description;
  - the backlog aside about deciding the refusal once upstream;
  - the full elaboration of the `collision` / `no_basename` divergence, including
    the `claimed`-map mechanics and that they predate T4.3.

  **`docs/tomo/scripts/instruction-render.md` also owes a T4.5 section — it has
  none, and the renamed test file's own docstring already points at it as the home
  of `sync_notice_relay_file`'s full rationale.** Code quality named one paragraph
  to lift there (2026-10-03): `TestSharedCodePathUnderMutation`'s explanation of
  why the mutation patches each call site's `__globals__` rather than
  `monkeypatch.setattr(lib.render_md, …)` — **`from X import Y` binds a reference
  into the importing module's own namespace while `import X` resolves through
  `sys.modules`, and the two can diverge.** That is generalisable Python semantics,
  not a fact about this test, and it is the reason the earlier form could silently
  miss the document surface. Ask the T4.5 implementer which half a reader of the
  test still needs in front of them before moving all of it — they wrote it and
  that judgement is theirs.

  That file also owes: the relay's **one source, two surfaces** rule and why the
  extraction was a precondition rather than a tidy-up; the four-column table from
  step 4b, because it is the standing reason the mutation test must never be
  deleted as redundant; and the unattributed flake from step 4c with its ruled-out
  list, so the next person to see it starts where this one stopped rather than
  re-deriving it.

  Two things belong in that file that are **not** in the docstring at all, and both
  are measured: that the owner is *told* about a withheld move in the document
  ("Attachments still in the inbox") while the staged note's body has already been
  rewritten — an inconsistency, not data loss, and the distinction matters because an
  earlier draft of mine overstated it; and that only notes Pass 2 **creates** are
  affected, since the rewrite is reached solely for items with a template.

  - The load-bearing test of this phase and Phase 2 together: drive the **same**
    decision through the markdown path and through the wire path and assert the
    emitted `move_asset` destination is identical, for a computed name and for a
    typed one. This is F1's and F2's shared criterion stated as one assertion
    `[ref: PRD/F1, PRD/F2]`.
  - Run the full suite and `ruff`. Write the `docs/tomo/` WHY entries for the
    parser and reducer changes.

    **Two of those entries are corrections, not additions — found by T4.1's review
    sweep (2026-10-02) and left for this task deliberately.** Both describe the
    pre-T4.1 line as current:
    - `docs/tomo/scripts/suggestions-reducer.md` — says *"this renderer now builds
      the line as `f"- [ ] Rename — {RENAME_IMPOSSIBLE_MARKER}"`"*, quoting code
      that no longer exists. This is the worst of the three, because it quotes the
      literal and reads as authoritative.
    - `docs/tomo/scripts/suggestion-parser.md` — refers to *the "Rename — no free
      name available" line*.

    Derive the full list from the phase diff rather than this list:
    `git diff --name-only <T4.1^>..HEAD -- tomo/` names every runtime file the phase
    changed and each owes a `docs/tomo/` counterpart. Phase 3's equivalent list was
    hand-maintained and undercounted **twice**; the rule that replaced it is in
    `plan/phase-3.md`'s T3.5 and it applies here too.

    When correcting a claim, ask whether it was false or merely **narrower than it
    looked** — the repo's own guidance (`docs/ai/memory/general.md`) is that
    deleting a correct warning because the code now contradicts it is the same move
    as editing a test to match an implementation. Here both are plainly false and
    should be corrected rather than split.
  - Success: suite green; `ruff` clean; both paths proven to converge on identical
    output for identical decisions `[ref: PRD/F1]`.
