---
title: "Phase 1: Detection in the reducer"
status: pending
version: "1.0"
phase: 1
---

# Phase 1: Detection in the reducer

## Phase Context

**GATE**: Read all referenced files before starting this phase.

**Specification References**:
- `[ref: SDD/Architecture Decisions; ADR-1]` — the check lives in the reducer
- `[ref: SDD/Architecture Decisions; ADR-2]` — generalise the folder cache
- `[ref: SDD/Runtime View; Primary Flow — Pass 1]`
- `[ref: SDD/Cross-Cutting Concepts; Cost]`
- `[ref: PRD/F1]`, `[ref: PRD/S1]`

**Key Decisions**:
- The reducer, not `inbox-triage.py`: triage has no `asset_folder` and never
  computes a destination. The reducer already loads both the folder and a Kado
  client.
- `_vault_folder_notes` is generalised rather than copied. Two near-identical
  folder caches would drift.
- The check fails **open** — a listing that raises is not a collision. Same
  posture as the note pass it sits beside.
- `same_file` is decided on content. The live pair is two different 69-byte
  PNGs; a size comparison would call them identical.

**Dependencies**: none. This phase is the foundation for 2 and 3.

---

## Tasks

Establishes the capability to know that a destination is taken, and whether the
file already there is the same one.

- [x] **T1.1 The folder cache serves attachments as well as notes** `[activity: domain-modeling]`

  1. Prime: Read `tomo/scripts/suggestions-reducer.py:1966-1996` — `_vault_folder_notes`, its `_folder_cache`, the case-folded keys recomposed through `_dest_join`, and `folder_listing_calls` `[ref: SDD/Required Context Sources]`
  2. Test: **the cache-reuse sequence in one test** — prime a folder through the NOTE caller (whose map holds only `.md` entries), then look the SAME folder up through the ATTACHMENT caller and find the attachment, with `folder_listing_calls` incremented exactly once across both `[ref: PRD/F1-AC3]` `[ref: PRD/F1-AC4]`. This ordering is the test, not a detail: a cache that stores the *derived* map instead of the raw listing serves the second lookup from a `.md`-only map and finds nothing — **silently**, which is the failure mode this spec exists to remove. A test that exercises the attachment caller on a fresh folder passes under that implementation and proves nothing.
     Also: a name differing only in case is found `[ref: PRD/F1-AC4]`; and the note path is unchanged **against a concrete anchor** — assert the generalised helper called with the note caller's arguments returns a dict equal to the one the pre-change hardcoded body produces for the same listing, and confirm the spec 034 T5.2 tests are green by node id. "Unchanged" with no anchor is an intention, not an assertion.
  3. Implement: parameterise the helper on the file predicate and the join, so the attachment caller passes `_asset_dest_join` and keeps non-`.md` names, while the note caller's arguments are unchanged
  4. Validate: `./venv/bin/python -m pytest tests/ -q`; `ruff` clean; the spec 034 T5.2 tests still pass untouched
  5. Success: one listing per folder regardless of caller `[ref: PRD/F1-AC3]`; the note path is behaviourally identical `[ref: SDD/Constraints, additive only]`; `folder_listing_calls` counts the asset folder `[ref: SDD/Cost]`

> **Deviation recorded 2026-09-22 — T1.1's test list sharpened before implementation.**
> The TDD guardian blocked the task as written. Three findings, all upheld:
> (1) *"a folder listed once serves two lookups without a second call"* counts Kado calls and
> never inspects the cache, so it passes under the derived-map implementation while attachment
> lookups silently return nothing — the fork the task text left open;
> (2) *"a note lookup keeps its current behaviour unchanged"* carried no anchor and was therefore
> unfalsifiable;
> (3) *"a listing that raises yields an empty map and still counts its round trip"* is **already
> true today** — `suggestions-reducer.py:2021-2029` sets `found = {}` in the `except` and
> increments through the `else 1` fallback — so it is evidence of existing error handling, not of
> this task, and was removed rather than kept as false coverage.
> The design fork itself is deliberately left to the implementer; the test now detects the wrong
> branch instead of the plan mandating the right one.

- [x] **T1.2 An occupied destination becomes a recorded conflict** `[activity: domain-modeling]`

  1. Prime: Read `_build_move_asset_actions` for how attachments are deduplicated globally and how `owner_source_items` is accumulated `[ref: render_actions.py:691-782]`; read `load_asset_folder` `[ref: suggestions-reducer.py:1462]`. **Both refs corrected 2026-09-22** — the plan's originals (`640-728`, `1363`) predate specs 034–036 and point at neighbouring code.
  2. Test:
     - **A free destination leaves the emitted document unchanged**, anchored: render a
       zero-conflict fixture, and assert the resulting document equals the one the pre-change
       reducer emits for the same input `[ref: PRD/F1-AC1]`. Decide and state which shape the
       key takes when empty — **absent**, like `tag_handler_updates`, rather than an empty list —
       because an unconditional `attachment_conflicts: []` is itself a change to every document
       and would make "unchanged" false by construction.
     - **An occupied destination produces one conflict** naming source, destination and every
       owning note `[ref: PRD/F1-AC2]`.
     - **Dedup is by DESTINATION, not by path**: one attachment embedded by three notes yields
       **one** conflict carrying three owners. The mutation this must catch is the plausible wrong
       one — accumulating per source path and emitting three conflicts with one owner each.
     - **No Kado client, and a listing that raises, each produce no conflicts and no error**
       `[ref: PRD/F1-AC5]` `[ref: SDD/Error Handling]`. **Both are already true of shipped code**
       — `_vault_folder_lookup` is `None` without a client (`suggestions-reducer.py:2078`) and
       `_VaultFolderLookup._entries` already fails open to `[]` (T1.1). They are therefore written
       as **regression pins with a named mutation each**: "call `.assets()` unconditionally,
       without the `is not None` guard" and "let `_entries` propagate instead of returning `[]`".
       A fail-open assertion that names no mutation is a restatement of T1.1, not coverage of this
       task.
  3. Implement: compute each distinct attachment's destination through `_asset_dest_join` — the same helper Pass 2 uses — and record `attachment_conflicts[]` entries into the suggestions-doc structure
  4. Validate: full suite; `ruff`; assert on a fixture with zero conflicts that the emitted document is unchanged from the pre-change render
  5. Success: every PRD F1 criterion has a named test; the destination is computed by the same helper as Pass 2, so the two cannot disagree `[ref: SDD/Runtime View, step 3]`

  **Scope boundary settled 2026-09-22 — two adjacent collision kinds are NOT this task's.**
  A *vault* collision is what 037 exists for: the destination is occupied by something already in
  the vault. Two neighbours look similar and are out of scope, recorded here so the implementer
  does not discover them mid-task and guess:
  - **Intra-run collision** — two different inbox attachments whose source paths resolve to one
    destination basename. Already handled, in Pass 2, by `_build_move_asset_actions`' `claimed`
    dict (`render_actions.py:761-774`), which emits a skip entry of `kind: "collision"`. The PRD
    does not mention it. Do not merge it into `attachment_conflicts[]`; two mechanisms reporting
    one concept under two names is the drift this repo keeps designing out.
  - **Self-collision** — a source that already sits at its own destination. Not reachable through
    the inbox→asset-folder move this builder performs, so no test is owed. Stated rather than left
    silent, because "we did not test it" and "it cannot happen" look identical in a diff.

- [ ] **T1.3 The conflict knows whether it is the same file** `[activity: domain-modeling]` `[parallel: true]`

  1. Prime: Read `KadoClient.read_file_bytes` `[ref: kado_client.py:176]` and the live probe recorded in `README.md` — two 69-byte PNGs with different digests
  2. Test:
     - **Byte-identical files set `same_file: true`**, differing files set `false` `[ref: PRD/S1-AC1]` `[ref: PRD/S1-AC2]`.
     - **Two files of identical size and different content set `false`** — the live 2026-09-15 pair, and the regression a size check would fail `[ref: SDD/Complex Logic]`.
     - **A raising read sets `null` for ITS conflict and leaves the others intact**: a run with two
       colliding destinations where `read_file_bytes` raises for one returns entries for **both**;
       the raising one carries `same_file: null`, the other its own computed `true`/`false` — not
       `null`, not omitted `[ref: PRD/S1-AC3]`. The single-conflict form of this test cannot tell a
       caught exception from one that abandons the rest of the run.
     - **A destination occupied by a folder sets `false`**, not `null` `[ref: SDD/Error Handling]`.
     - **Reads are bounded by collisions, not attachments**: with N attachments of which K collide,
       `read_file_bytes` is called **at most 2·K** times — source side plus destination side per
       entry — and never for the N−K that do not collide; K=0 performs none `[ref: SDD/Cost]`.
     - **A destination shared by several owning notes is still one comparison**: two notes embedding
       one attachment yield one entry and at most two content reads, not one read per owner
       `[ref: SDD/Cost]`.
  3. Implement: read both sides only for a name already known to be taken, compare content, set `same_file`
  4. Validate: full suite; `ruff`; the read-count assertions in step 2 carry the cost claim — a bare "zero reads when there are no collisions" does not, because the shipped code reads no content under **any** input
  5. Success: content decides, never size `[ref: PRD/S1]`; reads are bounded by collisions, not attachments `[ref: SDD/Cost]`; nothing derived from the content is persisted anywhere `[ref: SDD/Security and privacy]`

> **Deviation recorded 2026-09-22 — T1.3's test list sharpened before implementation.**
> The TDD guardian blocked the task. Two findings upheld, one corrected, one case added:
> (1) *"a read that raises sets `null` and does not abort"* bundled a checkable claim with an
> unanchored one. "Sets `null`" alone already forces a `try`/`except`, but an implementation that
> catches the exception and abandons the remaining conflicts still passes it. The two-conflict
> fixture is the test; the single-conflict form is not.
> (2) *"a run with no collisions performs zero content reads"* is **already true today** under every
> input, not merely the no-collision one — `detect_attachment_conflicts` reads no content at all,
> so the assertion cannot turn red on any plausible T1.3 implementation. Replaced by the
> discriminating form: N attachments, K collisions, reads bounded by K.
> (3) **The guardian's replacement was itself wrong** — it said "exactly K calls". The comparison
> has two sides (`SDD/Runtime View` step 5 reads *both* files), so K would be the wrong bound and
> the test would fail a correct implementation. Corrected to **at most 2·K**.
> (4) The multi-owner bound is new, for the reason the guardian gave: dedup is by destination, so an
> implementation looping over `owner_source_items` passes every other case while quietly breaking
> the cost claim.
