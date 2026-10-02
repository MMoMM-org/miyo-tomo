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

- [ ] **T4.1 The markdown offers a place to type** `[activity: frontend-ui]`

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
     - [ ] An ordinary conflict's markdown is unchanged `[ref: PRD/F2]`
     - [ ] The no-free-name line carries empty backticks `[ref: PRD/F2]`
     - [ ] `test_render_parse_round_trip_pins_semantic_mapping` still ticks the
           rename box — asserted by tick count, not inferred from a green run
     - [ ] `_toggle` fails loudly on a missed matcher, shown by an executed RED

- [ ] **T4.2 The parser reads the name from the markdown** `[activity: backend-api]`

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
     the `:2998` cited below was short by 21. Measured 2026-10-02 with the file
     final, as dated hints only — `_walk_attachment_conflicts` `:2287`, the prefix
     match `:2362`, `parse_attachment_conflict_remedies` `:2374`,
     `_join_attachment_conflict_remedies` `:2389`, the doc read `:2410`,
     `name_is_owner_supplied: False` `:2419`. See `docs/ai/memory/general.md` for
     the convention and why three sweeps in Phase 3 produced it.
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

     **And set `name_is_owner_supplied` here — T3.2 added it, and this task is
     where the markdown side stops being `False`.** The rule is NOT `True`
     unconditionally, and getting that wrong re-opens the behaviour change the
     owner avoided on 2026-10-01. Set it to **`extracted != the doc's computed
     name`**. Reasoning, measured during T3.2's amendment:
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
       at the call site in `main` (`:3019` as of 2026-10-02; the old text said
       `:2998`, short by 21). The wire path keeps `True`
       unconditionally because it deliberately does not load the doc — Phase 2's
       T2.5 measured the JSON-only path working with `--file` plus
       `--suggestions-json` and no `--suggestions-doc`, and re-coupling it would
       undo that.
     - The asymmetry is therefore not an inconsistency: each side uses what it
       has. It does mean an untouched unusable default is refused on the wire and
       permitted in the markdown. Acceptable because the wire path ships to the
       consumer for the first time in Phase 5, so no deployed behaviour changes —
       but say so in the handoff rather than letting them discover it.
  4. Validate: full suite; the 037 baseline test
     (`test_the_untouched_default_resolves_to_the_computed_name`) is the regression
     floor and must stay green.
  5. Success:
     - [ ] A typed name reaches Pass 2 `[ref: PRD/F2]`
     - [ ] An untouched default is byte-identical to today `[ref: PRD/F2]`
     - [ ] The strict xfail is **removed**, not left passing
     - [ ] An unreadable name is a refusal, never a fallback `[ref: PRD/F2]`
     - [ ] The structured doc is no longer consulted for this value `[ref: SDD/Implementation Gotchas]`

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

- [ ] **T4.3 Validate before the embed is rewritten** `[activity: backend-api]`

  1. Prime: read `rewrite_renamed_embeds` (`lib/embed_rewrite.py:91`) and note the
     ordering stated in its docstring — it runs **before**
     `_build_move_asset_actions`, so it recomputes the new basename from
     `proposed_name` directly rather than reading it back from a move action
     `[ref: SDD/Implementation Gotchas]`.
  2. Test: a **refused** typed name leaves every owning note's embed untouched.
     Without this ordering the embed is rewritten to a name the move then refuses,
     leaving bodies pointing at a file that was never created.
  3. Implement: ensure the verdict from Phase 3's check is available before the
     rewrite runs, and that the rewrite skips a refused entry.
  4. Validate: the 037 embed-rewrite tests stay green; the new test fails if the
     ordering is reversed — **construct that reversal and run it**.
  5. Success:
     - [ ] A refused name rewrites no embeds `[ref: PRD/F2, PRD/F3]`
     - [ ] An accepted typed name rewrites every owning note's embed, as 037
           already does for a computed name `[ref: PRD/F2]`
     - [ ] The ordering mutation turns the test red, demonstrated

- [ ] **T4.4 Phase validation — the two paths converge** `[activity: validate]`

  - The load-bearing test of this phase and Phase 2 together: drive the **same**
    decision through the markdown path and through the wire path and assert the
    emitted `move_asset` destination is identical, for a computed name and for a
    typed one. This is F1's and F2's shared criterion stated as one assertion
    `[ref: PRD/F1, PRD/F2]`.
  - Run the full suite and `ruff`. Write the `docs/tomo/` WHY entries for the
    parser and reducer changes.
  - Success: suite green; `ruff` clean; both paths proven to converge on identical
    output for identical decisions `[ref: PRD/F1]`.
