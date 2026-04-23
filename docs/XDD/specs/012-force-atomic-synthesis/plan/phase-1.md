# XDD 012 — Phase 1 Implementation Plan

**Scope:** single implementation phase. All 5 code changes land in one
commit on `feat/inbox-tagging-fixes`. Tests run green before merge.

## Tasks

### T1 — `scripts/suggestion-parser.py`: FAN-without-section → pending list + resolve-doc merge

- [ ] Add `--fan-resolve-file PATH` argparse option.
- [ ] If `--fan-resolve-file` given, parse that doc's `items[]` into a
      `{stem → atomic_section}` map. Reuse existing per-item section
      parser — fan-doc uses the same schema.
- [ ] Replace the current "warning + skip" branch for FAN-without-primary-
      section (lines 829-844 in current code) with a 3-way lookup:
      (a) primary per-item section → existing promote path;
      (b) resolve-doc section → new promote path, mark
          `from_resolve: true` on confirmed_item;
      (c) neither → append to `pending_fan_resolutions[]`.
- [ ] Emit `pending_fan_resolutions` as a new top-level key in the output
      (empty list when nothing pending). Do NOT change existing keys.
- [ ] Keep the `force_atomic: synthesized` warning only for branch (c)
      and only when no resolve doc is available (branch (b) hit OR
      resolve doc passed but stem not found there).
- [ ] Version bump: `scripts/suggestion-parser.py` header (find current
      version, bump minor).

### T2 — `dot_claude/agents/inbox-analyst.md`: `force_atomic` param

- [ ] Document a new input param `force_atomic: true | false` (default
      false) in the IO Contract section.
- [ ] At Step 7: if `force_atomic=true`, skip the 0.5-score gate and
      ALWAYS emit `create_atomic_note`. Preserve the computed score in
      `atomic_note_worthiness` for transparency.
- [ ] Add `force_atomic` passthrough into result.json (already falls out
      naturally — just document the field).
- [ ] Version bump (currently 0.7.0).

### T3 — `scripts/suggestions-reducer.py`: `--fan-resolve` flag

- [ ] Add `--fan-resolve` argparse flag.
- [ ] When set, filter input items to only those with
      `force_atomic=true` in result.json (inbox-analyst should write this
      field when dispatched with the flag; verify this plumbing and add
      it if missing).
- [ ] When set, produce a suggestions-doc with:
        `daily_updates: []`,
        `tag_changes_by_prefix: {}` (empty),
        `proposed_mocs: []`,
        `items: [...only FAN atomics...]`,
        title/description carrying "Force-Atomic Resolve" wording.
- [ ] Confirm output still validates against
      `tomo/schemas/suggestions-doc.schema.json`.
- [ ] Version bump.

### T4 — `dot_claude/agents/instruction-builder.md`: Step 2.5 subflow

- [ ] Insert new Step 2.5 between current Step 2 and Step 3, exactly per
      the block in `solution.md` §3.3.
- [ ] Extend Step 2's parser invocation to pass `--fan-resolve-file`
      whenever a companion `tomo-tmp/suggestions-fan.md` exists.
- [ ] Extend Step 2 pre-flight (document staging): when the inbox
      contains both `<date>_suggestions.md` AND a
      `<date>_suggestions-fan.md`, the builder must `kado-read` BOTH and
      stage them as `tomo-tmp/suggestions.md` and
      `tomo-tmp/suggestions-fan.md` before invoking the parser.
- [ ] Update the "What you never do" section: builder still never assembles
      markdown; the render + reducer scripts remain the authority.
- [ ] Version bump.

### T5 — `commands/inbox.md`: companion-doc auto-detect

- [ ] In the auto-detect section, when scanning for approved
      `*_suggestions.md`, ALSO scan for `*_suggestions-fan.md`. If BOTH
      are approved and share an inbox directory, hand both to the builder
      as a pair.
- [ ] Document the new pairing rule in the "How It Works" section.
- [ ] Version bump.

### T6 — Unit + integration tests

- [ ] `tests/test_suggestion_parser_fan_resolve.py` (new):
  - fixture A: FAN + no resolve doc → assert `pending_fan_resolutions`
    non-empty, `confirmed_items` excludes the pending stem.
  - fixture B: FAN + resolve doc with matching stem → assert
    `confirmed_items` includes it with `force_atomic=true,
    from_resolve=true`, `pending_fan_resolutions` empty.
  - fixture C: FAN + primary section with matching stem (legacy path) →
    assert existing promote behaviour intact, no `from_resolve` marker.
- [ ] `tests/test_suggestions_reducer_fan_resolve.py` (new):
  - minimal item with force_atomic=true → assert `--fan-resolve` output
    has that item in `items`, empty `daily_updates`, "Force-Atomic
    Resolve" in title.
- [ ] Run full Python suite: `./venv/bin/python3 -m pytest tests/ --tb=short`
      — expected 85+ passed / 1 skipped.

### T7 — Sync + smoke test + commit

- [ ] `echo K | bash scripts/update-tomo.sh` (with sandbox disabled) to
      propagate source → instance.
- [ ] Run shared-ctx smoke from tomo-instance to confirm no regressions.
- [ ] `git add` the 5 source files + 2 new tests + this spec dir.
- [ ] Single commit message: `feat(force-atomic): synthesize atomics via
      resolve doc (XDD 012)`.

## Sequencing notes

- T1 and T2 are independent — can be done in parallel.
- T3 depends on T2 (reducer filters on a field that analyst must emit).
- T4 depends on T1 + T3 (builder calls both).
- T5 is a small doc change, last.
- T6 can be written before T4/T5 — just against the scripts.

## Done criteria

- All acceptance criteria A1-A7 from requirements.md hold against the new
  code.
- Full test suite green.
- Source-to-instance sync succeeds.
- Commit lands on `feat/inbox-tagging-fixes`.
- Spec README.md status flips to "Code-complete — awaiting live validation".

## Open questions (resolved during design)

- **Q: Do we need a `fan-pending.json` scratch file?**
  A: No. `parsed-suggestions.json.pending_fan_resolutions` carries the
  same info, lives where the builder already reads. One less file.

- **Q: Should Pass 2 auto-run the resolve subflow or ask the user?**
  A: Auto-run. The FAN tick IS the user's approval to proceed. Prompting
  again would be redundant. If the user didn't mean it, they uncheck FAN.

- **Q: Two docs at once — how to pair?**
  A: By co-existence in the same inbox directory. The fan-doc's filename
  carries `-suggestions-fan.md` so it's unambiguous. Timestamps don't
  need to match.

- **Q: What if the user approves the fan-doc but leaves some atomic
  suggestions unchecked?**
  A: Parser merges only approved atomics. The unapproved ones remain
  pending and will re-trigger a fresh resolve-doc write. To exit this
  loop, user must either approve them or remove the FAN tick on the
  primary doc. Document in error-handling.
