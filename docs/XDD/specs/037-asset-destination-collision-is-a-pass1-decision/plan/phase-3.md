---
title: "Phase 3: Honouring the remedy in Pass 2"
status: in_progress
version: "2.0"
phase: 3
---

# Phase 3: Honouring the remedy in Pass 2

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-3]` — reuse `skipped_assets`
- `[ref: SDD/Runtime View; Primary Flow — Pass 2]`
- `[ref: SDD/Runtime View; vault_collision_held does not hold the owning note]`
- `[ref: SDD/Interface Specifications; skipped_assets kind]`
- `[ref: SDD/Building Block View; Components]` — the transport row added 2026-09-25
- `[ref: PRD/F3]`

**Key Decisions**:
- **The remedy has no transport yet.** `parse_attachment_conflict_remedies`
  (T2.4) has **zero production callers** — the parser's `main()` never calls it
  and its output dict never carries it. `_build_move_asset_actions` is reached
  only through `instruction-render.py:600`. T3.0 builds that edge; every other
  task in this phase is dead code without it.
- **`proposed_name` comes from the JSON, not the markdown.** The parser already
  loads the structured suggestions-doc (`--suggestions-doc`, with
  `_default_doc_path` as fallback) and `attachment_conflicts[]` carries
  `proposed_name`. Joining there costs nothing; re-parsing the rendered rename
  line would be a third render/parse coupling, and the backlog already carries
  two.
- **`keep_in_inbox` records `kind: vault_collision_held`** in the **existing**
  `skipped_assets`. `_subtract_skipped_assets` already lowers expected
  `move_asset` for each entry, so no new subtraction is written.
- **`vault_collision_held` must be EXCLUDED from
  `suppress_moves_for_unfiled_attachments`** (`render_actions.py:1331`). That
  pass holds the owning note for *every* skipped entry, so the standing ruling
  — the note is filed, only the file stays behind — is something this phase
  writes deliberately, not something it inherits. Recorded in
  `requirements.md:374-382`, re-confirmed 2026-09-25.
- `ignore` emits the move **unchanged** against the occupied destination and
  records **nothing** in `skipped_assets` — the audit counts it as any other
  move.
- **A rename rewrites embeds in `instruction-render.py`, not `render_actions.py`.**
  `render_actions.py` assembles action dicts and never touches a note body; the
  rendered body is built at `instruction-render.py:550-610`. No embed rewriter
  exists anywhere in the repo — `attachment_index.py:24` only reads `![[...]]`.
  A rename that does not rewrite is a failed criterion, not a partial one.
- ADR-3's claim that the paired consumer needs no change is **proven here**, not
  assumed. The repo has already lost a Pass 2 to a coverage mismatch.
- `_walk_attachment_conflicts` reads only the FIRST `## Attachment Conflicts`
  section in the document — a deliberate contract (T2.4), not a bug. T3.0 decides
  whether the transport surfaces that partial result or stays silent.

**Dependencies**: Phase 2 (`remedy` must be parseable before it can be honoured).
T3.0 blocks T3.1 and T3.3. T3.2 depends on T3.1.

---

> **Deviation recorded 2026-09-25 — Phase 3 rewritten before dispatch, and the SDD with it.**
> Traced the Pass-2 chain in the code before sending the first brief. Three findings,
> all structural, none visible from the task text as written:
> (1) **The transport does not exist.** The SDD's Pass-2 flow stepped from *"the parser
> reads the ticks into `remedy`"* straight to *"`_build_move_asset_actions` consults
> `remedy`"*, and its component table named no component between them. In the code there
> is no such edge at all. T2.4 shipped a function nobody calls. Added as T3.0, and the
> SDD component table gained `instruction-render.py` as a changed component (5 touched).
> (2) **T3.3 pointed at the wrong file.** It said to rewrite embeds in `render_actions.py`,
> which only builds action dicts. Re-homed to `instruction-render.py`.
> (3) **`keep_in_inbox` would have held the owning note by accident.**
> `suppress_moves_for_unfiled_attachments` acts on every `skipped_assets` entry
> regardless of `kind`, so the new kind inherits a behaviour the owner had already ruled
> against (`requirements.md:374`). The ruling now costs an explicit exclusion and a test.
> Two PRD Open Questions were closed in the same pass — both had been settled in code
> while still reading as open.

---

## Tasks

Establishes that the owner's tick is what the vault actually receives.

- [ ] **T3.0 The remedy reaches Pass 2 at all** `[activity: backend-api]`

  1. Prime: Read `suggestion-parser.py` `main()`'s `output` dict `[ref: suggestion-parser.py:2951-2971]` and its `--suggestions-doc` load `[ref: suggestion-parser.py:2400-2410, 1028]`; read `instruction-render.py`'s `build_actions` call `[ref: instruction-render.py:600-608]`; read `parse_attachment_conflict_remedies` `[ref: suggestion-parser.py:2349]` and confirm for yourself that nothing in `tomo/` calls it
  2. Test: the parser's JSON output carries one record per conflict entry, each with `source`, `remedy` **and** `proposed_name` joined from `attachment_conflicts[]` by `source` — **mutation: drop the join and emit `{source, remedy}` only, as `parse_attachment_conflict_remedies` returns it**, which leaves T3.1 no name to rename to; a document whose conflicts section is absent emits an **empty list, not a missing key** — **mutation: emit the key only when non-empty**, which makes a conflict-free run's output shape differ from a conflicted one; a `source` present in the markdown but absent from the JSON carries `proposed_name: null` rather than raising — **mutation: index the JSON dict directly and let `KeyError` escape**; `instruction-render.py` forwards the records to `build_actions` — **mutation: accept the argument and never pass it on**, which is invisible to every parser-side assertion; **a conflict-free doc parsed by `main()` produces an `output` dict equal by `==` to a captured pre-change literal** — not merely non-erroring, and likewise for `instruction-render.py`'s manifest on the same fixture — **mutation: emit the new key with a fabricated entry on a conflict-free run**, which no other bullet here catches. Follow `test_zero_conflict_run_still_emits_no_attachment_conflicts_key` (`tests/test_037_t1_5_one_entry_one_file.py:428`) and `test_no_withdrawals_source_deletions_byte_identical` (`tests/test_036_t4_3_withdrawal_reporting.py:800`): capture the literal, assert exact equality. *"Byte-identical" with no captured pre-change literal is an intention, not an assertion* `[ref: plan/phase-1.md:45]`
  3. Implement: parser `main()` calls `parse_attachment_conflict_remedies`, joins `proposed_name` from the already-loaded suggestions-doc, and emits the result on `output` under one new key; `instruction-render.py` reads that key and passes it through `build_actions` to `_build_move_asset_actions`, which accepts it and ignores it for now
  4. Validate: full suite; `ruff`; prove RED by reverting the parser's `output` line alone and showing the forwarding test fails
  5. Success: a conflict-free run's parsed output and instruction set are **byte-identical** to the pre-change version `[ref: SDD/Constraints, additive only]`; `parse_attachment_conflict_remedies` has a production caller `[ref: SDD/Runtime View; Pass 2 steps 2-3]`

- [ ] **T3.1 Each remedy produces its own outcome** `[activity: backend-api]`

  1. Prime: Read `_build_move_asset_actions` end to end `[ref: render_actions.py:691-782]` — the global `seen` dedup, the `claimed` map, the skip entries and their `kind`; read `suppress_moves_for_unfiled_attachments` `[ref: render_actions.py:1331-1362]`
  2. Test: `rename` emits a move to `_asset_dest_join(asset_folder, proposed_name)` — **mutation: use `proposed_name` as the destination directly**, which writes to the vault root and is the defect `SDD:215` was corrected for `[ref: PRD/F3-AC1, Rule 5]`; `keep_in_inbox` emits no move and one `skipped_assets` entry with `kind: vault_collision_held` `[ref: PRD/F3-AC2]`; **the owning note is still filed** — **mutation: omit the `vault_collision_held` exclusion from `suppress_moves_for_unfiled_attachments`**, which holds the note and is the behaviour the owner ruled against `[ref: requirements.md:374-382]`; `ignore` emits the move unchanged against the occupied destination and records **nothing** in `skipped_assets` — **mutation: make it behave like `keep_in_inbox`** `[ref: PRD/F3-AC3]`; a `rename` whose `proposed_name` is `null` cannot be emitted — assert which of the three it degrades to and why `[ref: SDD/ADR-4 exception]`; a conflict gone by Pass 2 emits the plain move — **mutation: treat an unmatched source as `keep_in_inbox`** `[ref: PRD/Scenario 5]`; the in-run collision path is untouched — **mutation: let a remedy short-circuit the `claimed` check** `[ref: PRD/F3-AC4]`
  3. Implement: consult `remedy` before claiming a destination; exclude `vault_collision_held` from the ADR-6 suppression pass; keep the in-run collision path untouched
  4. Validate: full suite; `ruff`; prove the `ignore` test RED by making it behave like `keep_in_inbox`
  5. Success: the strongest outcome any remedy produces is a move to a free name `[ref: PRD/Rule 6]`; the in-run collision behaviour is unchanged `[ref: SDD/Constraints, additive only]`

- [ ] **T3.2 The coverage audit needs no new arithmetic — proven** `[activity: testing]`

  1. Prime: Read `_subtract_skipped_assets` and its docstring `[ref: instructions-diff.py:858-883]`, and `derive_expected`'s `move_asset` count `[ref: instructions-diff.py:465-476]`
  2. Test: a run with one `keep_in_inbox` conflict passes the audit with expected == actual `[ref: PRD/F3-AC5]`; a run with one `ignore` conflict passes, the move counted as any other `[ref: SDD/Interface Specifications]`; a run with one `rename` passes — **and asserts the audit counts the RENAMED destination**, not the original, which is the one arithmetic ADR-3 could plausibly have missed; a run mixing all three passes; **`instructions-diff.py` is byte-identical to its pre-change version** — the assertion that ADR-3 held
  3. Implement: nothing in `instructions-diff.py`. If a change proves necessary, that is a deviation: stop, record it, and revisit ADR-3 before proceeding `[ref: plan/README.md; Deviation Protocol]`
  4. Validate: run `instructions-diff.py` against fixtures for all three remedies and assert exit 0
  5. Success: ADR-3 is demonstrated rather than asserted `[ref: SDD/ADR-3]`; the paired-consumer trap that aborted Pass 2 on 2026-09-15 is closed by evidence

- [ ] **T3.3 A renamed attachment takes its embeds with it** `[activity: backend-api]`

  1. Prime: Read where the rendered note body is assembled `[ref: instruction-render.py:550-610]` and how `![[...]]` is recognised today `[ref: lib/attachment_index.py:24-40]` — it only reads, there is no rewriter to extend; read the 2026-09-15 end state — `![[Scans/karte.png]]` in an Atlas note `[ref: README.md; Context]`
  2. Test: a renamed attachment's owning note embeds the **new** basename — **mutation: emit the move without the rewrite**, leaving the note pointing at a name the run did not file; a note embedding it twice has **both** rewritten — **mutation: `str.replace` with `count=1`**; a note embedding two attachments, one renamed and one not, keeps the untouched one verbatim — **mutation: rewrite every embed in the body rather than the matched target**; an embed carrying an alias or an anchor survives with alias and anchor intact — **mutation: replace the whole `![[...]]` span rather than its target portion**; a `![[...]]` inside a fenced code block is left alone — **mutation: rewrite without the fence guard** `[ref: attachment_index.py:24]`; a plain `[[...]]` link is left alone — **mutation: drop the `!` from the match** `[ref: attachment_index.py:24]`
  3. Implement: rewrite the embed target for every owning note when the remedy is `rename`, in `instruction-render.py`
  4. Validate: full suite; `ruff`; prove RED by emitting the move without the rewrite and asserting the note points at a name that no longer exists
  5. Success: no rendered note references a name the run did not file `[ref: PRD/F3-AC1]`; the basename survives verbatim where unchanged `[ref: render_actions.py:509 docstring]`

---

> **Deviation recorded 2026-09-25 — T3.0's success criterion anchored before implementation.**
> The guardian blocked the task I had just written to fix everyone else's under-specified
> task text, and the finding was the one this spec already names in its own words:
> *"'Unchanged' with no anchor is an intention, not an assertion"* (`plan/phase-1.md:45`).
> T3.0's "byte-identical for a conflict-free run" lived only in the Success line, with no
> matching bullet in the Test list and no captured comparison target — satisfiable by an
> implementer asserting little more than "the run does not raise". Moved into step 2 with a
> mutation of its own and two precedent tests named, both verified to exist. The guardian
> also confirmed the other four mutations turn their assertions red and found no no-op
> among them.
