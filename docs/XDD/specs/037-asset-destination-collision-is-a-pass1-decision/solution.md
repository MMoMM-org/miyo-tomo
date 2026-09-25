---
title: "An occupied asset destination is a Pass-1 decision — Solution Design"
status: draft
version: "2.0"
---

# Solution Design Document

> **v2.0 supersedes v1.0.** Two ADRs in the first draft asked the owner to
> choose between defensive postures — fail-closed on a failed check, and holding
> every note that embeds an unresolved attachment. Both dissolved under the
> owner's scoping principle: the gap between Pass 1, Pass 2 and apply is not
> modelled, and the only guarantee is that nothing overwrites data. What remains
> is smaller and has no open decisions.

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] Every PRD requirement maps to exactly one owning component
- [x] No two components share a responsibility
- [x] Every interface between components is documented
- [x] All architecture decisions recorded as ADRs with trade-offs
- [x] No ADR awaits confirmation
- [x] No [NEEDS CLARIFICATION] markers remain

### QUALITY CHECKS (Should Pass)

- [x] Design reuses documented patterns rather than inventing siblings
- [x] Error paths are specified, not implied
- [x] Cost is bounded and stated in the units the repo already measures
- [x] Every new field traces to a consumer that reads it
- [x] Existing runs without conflicts behave identically

---

## Output Schema

### SDD Status Report

| Field | Value |
|-------|-------|
| specId | 037-asset-destination-collision-is-a-pass1-decision |
| status | COMPLETE |
| components | 5 touched, 0 new files |
| adrs | 5, none open |
| newWireFields | 0 |
| externalComponentsChanged | 0 (Hashi untouched) |
| clarificationsRemaining | 0 |

### ArchitectureSummary

Everything this spec needs is already built, for the other file class.
`suggestions-reducer.py` checks note destinations against the vault (spec 034
T5.2) using a cached, case-folded, cost-counted per-folder listing, and adjusts
the proposal *before the owner reads the document*. Spec 037 points that same
machinery at attachments and renders the result as a decision instead of a
silent adjustment.

The audit side needs nothing: `_subtract_skipped_assets` already lowers the
expected `move_asset` count for every entry the renderer deliberately did not
file. A withheld attachment that lands in that existing list is accounted for
without touching the paired consumer.

### SectionStatus

| Section | Status |
|---------|--------|
| Implementation Context | COMPLETE |
| Solution Strategy | COMPLETE |
| Building Block View | COMPLETE |
| Runtime View | COMPLETE |
| Cross-Cutting Concepts | COMPLETE |
| Architecture Decisions | COMPLETE — 5 ADRs, none open |

### ADRStatus

| ADR | Decision |
|-----|----------|
| ADR-1 | Detection lives in the reducer, not `inbox-triage.py` |
| ADR-2 | Extend the existing folder cache rather than add a sibling |
| ADR-3 | Reuse `skipped_assets` instead of a new records list |
| ADR-4 | Rename is pre-ticked; a cleared default means *ignore* |
| ADR-5 | No wire field, no Hashi change, no instructions-document change |

---

## Constraints

- Kado is the only vault surface (MiYo Constitution, Privacy & Security L1).
- `instructions-diff` is a paired consumer; an unaccounted source aborts Pass 2.
- Near-MVP, additive only: a run with no conflicts behaves byte-identically.
- Hashi modifies, never creates.
- The gap between passes is not modelled (PRD, scoping principle).

## Implementation Context

### Required Context Sources

| Source | What it establishes |
|---|---|
| `tomo/scripts/suggestions-reducer.py:1946-2016` | The Kado client opened once for Pass-1 vault checks; `_folder_cache`, `_vault_folder_notes`, `folder_listing_calls`, and the T5.2 clash pass for notes |
| `tomo/scripts/suggestions-reducer.py:1363` | `load_asset_folder(shared_ctx_path)` — the reducer already reads the configured destination |
| `tomo/scripts/suggestions-reducer.py:1452` | `render_attachments_preamble` — the document already has an attachments voice to extend |
| `tomo/scripts/lib/render_actions.py:691-782` | `_build_move_asset_actions`: in-run collisions, `skipped_assets`, `kind`, `owner_source_items` |
| `tomo/scripts/lib/render_actions.py:509` | `_asset_dest_join` — the only place a destination is computed |
| `tomo/scripts/instructions-diff.py:858-883` | `_subtract_skipped_assets` — the audit already lowers expected `move_asset` per skipped entry |
| `tomo/scripts/lib/kado_client.py:313,176` | `path_exists`, `read_file_bytes` — probed live on a PNG, 2026-09-15 |

### Implementation Boundaries

**In scope:** attachment destinations; the suggestions document's new decision
section; the parser reading those ticks and carrying them onto its output;
`instruction-render.py` transporting them into Pass 2 and rewriting the embed on
a rename; `render_actions` honouring the remedy.

**Out of scope:** note destinations (T5.2 owns them); the instructions document;
Hashi; any wire-format change; overwrite as a remedy; note-holding — a filed note
keeps its move even when its attachment is held (`requirements.md:374-382`).

### External Interfaces

| Interface | Direction | Change |
|---|---|---|
| Kado `list_dir(folder, depth=1)` | Tomo → Kado | One more folder key in the existing cache |
| Kado `read_file_bytes(path)` | Tomo → Kado | New, only for a name that actually collides |
| `suggestions-doc.json` | reducer → parser | New `attachment_conflicts[]` block |
| Rendered suggestions Markdown | Tomo → owner | New decision section, rendered only when non-empty |
| `instructions.tomo.skipped_assets[]` | Pass 2 → `instructions-diff` | Existing field, one new `kind` value |
| Hashi instruction set | Tomo → Hashi | **None** |

### Cross-Component Boundaries

Hashi is unchanged and must stay so. Remedy *ignore* depends on its current
behaviour: a `move_asset` whose destination is occupied is refused and reported.
That is a dependency on observed, documented behaviour, not a request for a
change — and it is the reason no `on_conflict` field appears on the wire.

### Project Commands

```bash
./venv/bin/python -m pytest tests/ -q
./venv/bin/python -m ruff check tomo/scripts/
bash scripts/reset-tomo-tmp.sh --pass1 --instance <path>/tomo-tmp
```

## Solution Strategy

Point the existing note-clash machinery at attachments; render the finding as a
decision rather than applying it silently; express every outcome through fields
the downstream already reads. No new file, no new wire field, no second
subtraction in the audit.

## Building Block View

### Components

| Component | Responsibility | Change |
|---|---|---|
| `suggestions-reducer.py` | Detect the occupied destination, classify it, put the decision in the document | extended |
| Suggestions document (Markdown + JSON) | Carry the conflict and the owner's tick | extended |
| `suggestion-parser.py` | Read the tick back off the reviewed document **and emit it on the parsed output, joined to its `proposed_name`** | extended |
| `instruction-render.py` | **Carry the remedies from the parsed output into `build_actions`; rewrite the embed on a rename** | extended |
| `render_actions.py` | Honour the remedy; record a withheld move in `skipped_assets` | extended |
| `instructions-diff.py` | Account for the withheld move | **none** — ADR-3 |

The MECE split follows what each component already owns: detection needs config
and Kado (reducer), reading ticks is parsing (parser), moving the result between
the two passes and assembling note bodies is `instruction-render.py`, emitting
actions is rendering (render_actions).

**`instruction-render.py` was added to this table on 2026-09-25**, before Phase 3
was dispatched. The original table named no transport between the parser and
`_build_move_asset_actions`, and the Pass-2 flow below jumped straight from one to
the other. In the code there is no such edge: `parse_attachment_conflict_remedies`
(T2.4) had no production caller at all, and `_build_move_asset_actions` is reached
only through `instruction-render.py:600`. The embed rewrite lands here for the same
reason — `render_actions.py` assembles action dicts and never touches a note body,
while the rendered body is built at `instruction-render.py:550-610`.

### Interface Specifications

#### `attachment_conflicts[]` in `suggestions-doc.json`

Written by the reducer; read by the renderer and the parser.

| Field | Meaning |
|---|---|
| `source` | The incoming attachment's vault path |
| `destination` | The computed, occupied destination |
| `same_file` | `true` · `false` · `null` when the comparison could not be made (S1) |
| `owner_source_items` | Every note embedding this attachment, as resolved paths |
| `proposed_name` | The free **basename** a rename remedy would use — not a path (C1). The folder is invariant and already carried in `destination`; a consumer composes the two with `_asset_dest_join`. `null` when no candidate is free within 99 attempts. |
| `remedy` | Filled by the parser: `rename` · `keep_in_inbox` · `ignore` |

`owner_source_items` deliberately matches the field `_build_move_asset_actions`
already records, so both collision sources describe residue the same way.

`remedy` is never null after parsing — Rule 3 resolves an empty or contradictory
entry to `ignore` in the parser, so no downstream consumer has to re-derive it.

#### `skipped_assets[]` — one new `kind`

Existing shape, unchanged fields. `kind` gains `vault_collision_held`: the owner
chose *keep in inbox*, so the renderer deliberately did not file it. That is
precisely what `_subtract_skipped_assets` documents itself as counting.

*ignore* produces **no** `skipped_assets` entry — the move is emitted normally
and the audit counts it as any other move. Only Hashi later refuses it.

## Runtime View

### Primary Flow — Pass 1

1. The reducer loads `asset_folder` from shared-ctx (already does).
2. It opens the Kado client once for Pass-1 vault checks (already does).
3. For every distinct attachment on the confirmed items it computes the
   destination through `_asset_dest_join` — the same helper Pass 2 uses, so the
   two cannot disagree about what the destination is.
4. It asks the folder cache whether the name is taken; the asset folder is one
   more key in `_folder_cache`.
5. For a taken name only, it reads both files' bytes to set `same_file`.
6. It records the conflict and renders the decision section with rename ticked.

### Primary Flow — Pass 2

1. The parser reads the ticks into `remedy`, applying Rule 3 and Rule 4.
2. The parser joins each remedy to its `proposed_name` from `attachment_conflicts[]`
   in the structured suggestions-doc JSON it already loads (`--suggestions-doc`,
   with `_default_doc_path` as fallback) and emits the pairs on its output. The
   join is on `source`, matching T1.5's grouping key. `proposed_name` is **not**
   re-read from the rendered markdown: that would be a third render/parse coupling,
   and the backlog already carries two.
3. `instruction-render.py` reads that key off the parsed suggestions JSON and passes
   it to `build_actions`, which forwards it to `_build_move_asset_actions`.
4. `_build_move_asset_actions` consults `remedy` before claiming a destination:
   - `rename` → move to `_asset_dest_join(asset_folder, proposed_name)`. `proposed_name`
     is a BASENAME: using it directly as a path would write to the vault root.
   - `keep_in_inbox` → emit nothing, record `kind: vault_collision_held`
   - `ignore` → emit the move unchanged against the occupied destination
5. On a rename, `instruction-render.py` rewrites the embed target in every owning
   note's rendered body, so no filed note names a file the run did not file.
6. The coverage audit subtracts held entries through the existing path.

#### `vault_collision_held` does not hold the owning note

`suppress_moves_for_unfiled_attachments` (`render_actions.py:1331`) keeps an owning
note in the inbox for **every** `skipped_assets` entry, so a new `kind` is held back
by default rather than by choice. `vault_collision_held` is excluded from that pass:
the note is filed and only the file stays behind.

This is the standing ruling, recorded in `requirements.md:374-382` before
implementation began — *keep in inbox* names the attachment, not the note, and the
scoping principle puts the residue with Hashi rather than widening the remedy. The
exclusion is therefore written deliberately and asserted by a test; it is not the
absence of a behaviour. Re-confirmed by the owner on 2026-09-25 when the interaction
with ADR-6 was measured rather than assumed.

The accepted cost is the one the PRD's Context section opens with: a filed note whose
embed reaches back into the inbox. F3-AC2 still holds — nothing *fails* at apply.

### Error Handling

| Condition | Behaviour | Why |
|---|---|---|
| No Kado client (`--no-kado`, no config) | Check does not run; today's behaviour | The T5.2 pass is already gated the same way |
| The asset-folder listing raises | No conflict raised; run proceeds | Matches the sibling's recorded posture — *"an error is not a collision"*. The scoping principle makes Hashi the guard |
| `read_file_bytes` raises | `same_file: null`; remedies unchanged | A comparison that did not happen is not evidence either way |
| Destination is a folder | Conflict; rename remains the default | The only remedy that can succeed |
| No remedy ticked / rename cleared | `ignore` | ADR-4 |
| Two remedies ticked | `ignore` | Rule 4 — a contradiction is not a first-wins race |
| The conflict is gone by Pass 2 | The plain move is emitted | A stale conflict changes nothing |
| A conflict appears only at apply | Hashi refuses and reports | Not modelled, by the scoping principle |

### Complex Logic — `same_file`

The comparison is content, never size. The 2026-09-15 pair is the argument: both
files are 69 bytes and they are different pictures. A size check would have
reported them identical and produced a warning that steered the owner away from
the one remedy that preserves both.

`same_file` changes no remedy and no default. It changes one sentence in the
document — and that sentence is what stops an owner from accepting a rename that
gives them two copies of one image.

## Cross-Cutting Concepts

### Cost

- **`base_kado_calls` is unaffected.** It is measured inside `inbox-triage.py`
  between two snapshots of the client's counter; the reducer is a separate
  process. The spec 034 T6.4 baseline of `2` stands.
- **`folder_listing_calls` gains at most one**, and only on a cache miss for the
  asset folder. It is already carried in the output document for the
  cost-history entry, so the increase appears where the existing numbers do.
- **Content reads are bounded by the number of distinct colliding SOURCE
  paths**, not by attachment count. Phase 1 T1.5 groups conflict entries by
  the exact source path rather than the case-folded destination, so N
  distinct sources that collide on the same destination are N separate
  comparisons, each reading both sides — 2N reads for that destination,
  against 2 for the pre-T1.5 destination-keyed code. N is bounded only by
  the run's attachment count; spec 034's recursive inbox discovery plus
  repeat camera/scanner default filenames make N > 2 realistic, not a
  two-element edge case. A shared destination-side cache was considered and
  rejected — not because N is usually small, but because it would be wrong
  at any N: `same_file` is a property of the (source, destination) pair,
  and caching one verdict per destination would hand every source after
  the first another source's answer.

### Fail direction

The repo has both postures, each justified by what a wrong guess costs, and this
spec takes the sibling's:

- `reconcile_map_notes_against_vault` fails **open** — a ghost MOC link beats
  dropping a live one.
- The T5.2 note-clash pass fails **open** — *"an error is not a collision"*.
- This check fails **open** too. v1.0 argued for closed on the grounds that
  attachments have no later guard inside Tomo. They have one outside it, and the
  scoping principle says that is enough.

### Security and privacy

`read_file_bytes` pulls attachment content into memory to compare it. Nothing is
persisted — not the bytes, not a digest, not to the run log or the cost history.
Constitution L2 restricts audit records to metadata, and a content hash of a
user's file sits closer to content than to metadata. The document says *"the same
file"* or *"a different file"*, never a digest.

## Architecture Decisions

### ADR-1 — Detection lives in the reducer, not `inbox-triage.py`

**Choice:** Put the vault check in `suggestions-reducer.py`.

**Rationale:** Triage looks like the natural home — it already resolves
attachments and writes `resolved-attachments.json`. It is the wrong one:
`inbox-triage.py` contains no reference to `asset_folder` and never computes a
destination. The reducer already loads the asset folder, already opens a Kado
client for exactly this kind of check, and owns the document the decision must
appear in.

**Trade-offs:** The check runs later in Pass 1 than it theoretically could. In
exchange it needs no new config plumbing, leaves triage's measured call budget
untouched, and sits beside the pass that does the same job for notes.

### ADR-2 — Extend the existing folder cache rather than add a sibling

**Choice:** Generalise `_vault_folder_notes` so the caller supplies the filter
and the join, instead of writing a parallel `_vault_folder_assets`.

**Rationale:** The existing helper caches per folder, case-folds, counts its own
round trips, and recomposes keys through `_dest_join` so both sides of the
comparison are built by one helper. An attachment needs all of that, differing
only in which names it keeps and that it joins through `_asset_dest_join`. Two
near-identical helpers drift; the repo has a memory entry about exactly that
shape of duplication.

**Trade-offs:** Touching a function spec 034 validated. Mitigated by the shape —
a predicate and a join passed in, with the note call keeping its current
arguments.

### ADR-3 — Reuse `skipped_assets` rather than introduce a new records list

**Choice:** A held attachment is a `skipped_assets` entry with a new `kind`.

**Rationale:** `_subtract_skipped_assets` already describes itself as counting
"one path the renderer deliberately did not file", and already lowers expected
`move_asset` for each. A held attachment is that fact with a different cause.
A new list would mean a second subtraction, a second place to forget it, and the
Pass-2 abort this repo has already lived through once.

**Trade-offs:** `kind` now spans in-run and vault causes. Acceptable — the field
exists because "the two cases need different remedies", and a third value keeps
that promise rather than breaking it.

### ADR-4 — Rename is pre-ticked, and a cleared default means *ignore*

**Choice:** The rename remedy ships ticked. An entry with nothing ticked, or
with more than one ticked, resolves to *ignore*.

**Rationale:** Two decisions in one, and they pull the same way. Pre-ticking
reverses this repo's usual habit because a safe obvious answer exists here:
renaming overwrites nothing, loses nothing, and is what the owner would pick
almost every time. Requiring a tick would charge attention for the common case.

The default for a *cleared* entry is the opposite kind of choice. An owner who
deliberately cleared the box has signalled that they want to handle it, so the
right outcome is the loudest one — the move goes out, Hashi refuses it, and the
run log carries the report. Resolving silence to *keep in inbox* would be
quieter and would hide the unresolved conflict behind an attachment that simply
never moved.

**Trade-offs:** A pre-ticked box can be accepted without being read, producing a
rename the owner did not think about. S1's warning on an identical file is the
mitigation, and the outcome is in any case reversible — a renamed copy beside
the original, never an overwrite.

**Exception added 2026-09-23 — when `proposed_name` is `null`, *keep in inbox*
is pre-ticked instead.** After 99 taken variants there is no name to rename to,
so the rename remedy is rendered but unavailable and cannot be the default. The
rule above says a cleared entry resolves to *ignore*, and that rule is right for
an owner who cleared it deliberately — but nobody cleared this one, and *ignore*
would send out a move Hashi is certain to refuse, which is exactly the late
failure this spec exists to remove. Pre-ticking follows ADR-4's own reason:
tick when a safe obvious answer exists. Here that answer is *keep in inbox* —
the file and its note stay where they are and nothing moves. T2.4 parses this
state explicitly rather than inferring it.

### ADR-5 — No wire field, no Hashi change, no instructions-document change

**Choice:** Pass 2 emits ordinary actions. The instructions document is
untouched. Hashi is untouched.

**Rationale:** Remedy *ignore* relies on Hashi's existing refusal, which is
already correct — the owner's explicit instruction was to leave it alone and let
the run log carry the problem. Adding an `on_conflict` field would ask Hashi to
resolve something it has no authority to decide, and this repo has the live
counter-example: spec 036's `depends_on` is specified, unimplemented, and has no
consumer.

**Trade-offs:** A collision appearing after Pass 2 can only be refused, not
resolved. That is the intended behaviour and the second journey in the PRD.

## Open Questions

Carried from the PRD; neither blocks implementation.

- [x] The rename scheme for `proposed_name` (C1). **Decided 2026-09-23**: `{stem} ({n}){ext}`,
      n from 2, first free name wins — the scheme `resolve_destination_clashes` already ships
      for note clashes, with the counter moved before the extension because an attachment's
      basename carries its own suffix. Computed in the reducer (Phase 2 T2.1), not the
      renderer. The note that this question "does not block implementation" was wrong: T2.2
      renders the field.
- [ ] Whether *keep in inbox* should also suppress the owning note's filing. The
      owner has ruled it need not, on the scoping principle; recorded because it
      is the question most likely to return after living with it.
