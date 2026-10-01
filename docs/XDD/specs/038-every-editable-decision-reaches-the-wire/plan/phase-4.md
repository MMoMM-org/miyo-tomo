---
title: "Phase 4: The name becomes a value"
status: pending
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

  1. Prime: read `render_attachment_conflicts_block`
     (`suggestions-reducer.py:1438-1535`), specifically the rename line at `:1518`
     and the `RENAME_IMPOSSIBLE_MARKER` branch at `:1521-1522`
     (`lib/attachment_conflict_states.py:19`).
  2. Test: an ordinary conflict renders **byte-identically to today**; the
     no-free-name case renders the line with empty backticks rather than no
     parameter at all.
  3. Implement: the single change is the impossible branch. The ordinary branch is
     untouched `[ref: SDD/ADR-4]`.
  4. Validate: every existing 037 render test stays green — this task should break
     nothing.
  5. Success:
     - [ ] An ordinary conflict's markdown is unchanged `[ref: PRD/F2]`
     - [ ] The no-free-name line carries empty backticks `[ref: PRD/F2]`

- [ ] **T4.2 The parser reads the name from the markdown** `[activity: backend-api]`

  1. Prime: read `_walk_attachment_conflicts` (`suggestion-parser.py:2268`), the
     prefix match at `:2343`, `parse_attachment_conflict_remedies` (`:2355`), and
     `_join_attachment_conflict_remedies` (`:2370-2392`) where `proposed_name` is
     currently read from the structured doc by `source`.
  2. Test: an overtyped name is returned; an untouched default resolves to the
     computed name **byte-identically** (this flips
     `tests/test_037_typed_rename_target_is_ignored.py`'s strict xfail and deletes
     `test_the_typed_name_is_discarded_today` with it); a half-edited line with no
     closing backtick, and one with empty backticks on an ordinary conflict, both
     resolve to a refusal rather than to a fallback or a different remedy.
  3. Implement: extract the backtick content on a ticked rename line and carry it
     as `proposed_name`. **Remove the structured-doc read for this value** — do not
     leave both in play, or a stale doc wins over the owner's keystrokes
     `[ref: SDD/Implementation Gotchas]`.

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
       doc (`_load_json_doc(_own_doc_path)`, `:2998`). The wire path keeps `True`
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
