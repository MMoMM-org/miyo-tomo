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

- [ ] **T3.1 The typed-name check** `[activity: domain-modeling]` `[parallel: true]`

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
     `lib/render_actions.py:836`, which a remedy-chosen destination reaches by
     design (`:831-835`). So this module takes **one argument** and stays a pure
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

- [ ] **T3.2 The move builder consumes the verdict** `[activity: backend-api]`

  1. Prime: read `_build_move_asset_actions` (`render_actions.py:691`), its rename
     branch (`:825-830`), and the existing `skipped_assets` kinds (`no_basename`,
     `vault_collision_held`, `collision`).
  2. Test: a refused name emits **no** `move_asset` for that attachment and **one**
     `skipped_assets` entry of the new kind carrying the reason; a usable typed
     name emits the move against the typed destination; a Tomo-computed name
     behaves exactly as today. **Plus one case this task confirms rather than
     builds** (owner ruling 2026-10-01, where F3's fourth criterion landed): a
     typed name that is usable as a string but collides with a destination another
     action in the same run already claimed is refused by the **existing** check at
     `:836` with `kind: "collision"`. Assert it — the guarantee lives only in a
     comment (`:831-835`) today, and a check inserted before `_asset_dest_join`
     is exactly the kind of edit that could bypass it.
  3. Implement: call the check before `_asset_dest_join`; add the new kind. Do
     **not** touch `_asset_dest_join` `[ref: SDD/CON-4]`.
  4. Validate: the 037 suite stays green — particularly the degraded-rename path
     (`proposed_name` null still degrades to `keep_in_inbox`).
  5. Success:
     - [ ] A refused name emits no move and one records entry `[ref: PRD/F3]`
     - [ ] The computed-name path is unchanged `[ref: PRD/F3]`
     - [ ] `_asset_dest_join` is byte-identical to before `[ref: SDD/Acceptance Criteria]`

- [ ] **T3.3 The owning note is held** `[activity: backend-api]`

  1. Prime: read `suppress_moves_for_unfiled_attachments` (`render_actions.py:1410`)
     including the docstring explaining why `vault_collision_held` is **excluded**,
     and 037's `requirements.md:374-382` where that exclusion was measured rather
     than assumed.
  2. Test: a refused typed name holds the owning note — and assert this
     **specifically**, because the exclusion list is exactly where 037 had to make
     the opposite choice explicit, and a new kind silently added to that list would
     be invisible `[ref: SDD/Acceptance Criteria]`.
  3. Implement: the new kind is **not** added to the exclusion list. That is the
     whole change; the pass's default behaviour does the rest `[ref: SDD/ADR-6]`.
  4. Validate: the 037 test that `vault_collision_held` does **not** hold the note
     stays green — the two kinds must diverge, and both directions need proof.
  5. Success:
     - [ ] A refused name holds the owning note `[ref: PRD/F3]`
     - [ ] `vault_collision_held` still does not `[ref: SDD/ADR-6]`
     - [ ] The mutation — adding the new kind to the exclusion list — turns the
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
     the bullet — the new kind needs one too, and that line is where "what to do
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
     T3.1's module via the new kind, and the run-local collision from the existing
     `kind: "collision"` path. Decide whether a collision on an owner-**typed**
     name reads differently from one on a Tomo-computed name — the existing reason
     string says "already claimed by" and never mentions that a name was typed,
     which under F3's sixth criterion ("records that the typed name could not be
     used") may not be enough.
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

  - Run the full suite and `ruff`. Write the `docs/tomo/scripts/lib/` WHY entries
    for the new module and the two modified functions — **now, not in Phase 5**.
  - Re-read every assertion added in this phase and ask of each: *which mutation
    turns this red?* Run the ones you can name. Spec 037 produced nine assertions
    that could not bite `[ref: plan/README.md; the standing warning]`.
  - Success: suite green; `ruff` clean; WHY entries written; every new assertion
    has a named, executed mutation `[ref: PRD/F3]`.
