---
title: "Every editable decision reaches the wire"
status: draft
version: "1.0"
---

# Solution Design Document

> **This spec supersedes spec 037's ADR-5.** That ADR said "no wire field, no
> Hashi change" and was verified against Hashi's compiled validator. The
> verification was real; it was performed on the **instructions** wire while the
> feature lived on the **suggestions** wire. ADR-1 below records the supersession
> explicitly so the old ADR is never read as current.

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] Every PRD requirement maps to exactly one owning component
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Every architecture decision is recorded as an ADR and confirmed by the owner
- [x] No component owns another's domain logic
- [x] Runtime view traces both Pass-2 paths, not only the markdown one

### QUALITY CHECKS (Should Pass)

- [x] Existing patterns reused rather than new ones introduced
- [x] Fail direction stated for every new check
- [x] Cost of every new vault interaction accounted for
- [x] The consumer's side of each interface named, with what they must change
- [x] Acceptance criteria traceable 1:1 to the PRD's
- [x] Checked against the MiYo Constitution (no repo-level `Constitution.md`; L1 Privacy, L1/L2 Testing, L1 Code Quality and L1 Dependencies pass — L2 Architecture surfaced CON-8, an open obligation rather than a violation)

---

## Output Schema

### SDD Status Report

| Field | Value |
|-------|-------|
| specId | 038-every-editable-decision-reaches-the-wire |
| status | `COMPLETE` |
| adrsConfirmed | 8 of 8 |
| componentsAdded | 3 (a typed-name check, an inventory, its join test) |
| componentsModified | 10 |
| wireVersionMove | suggestions wire `2` → `3` |

### ArchitectureSummary

| Aspect | Decision |
|--------|----------|
| Where the conflict lives on the wire | A top-level `attachment_conflicts[]` array, not nested per suggestion |
| What the array carries | The decision (`remedy`, `proposed_name`) plus the context the consumer cannot derive (`destination`, `same_file`) |
| What it deliberately omits | The owning notes — derivable from the run |
| Markdown shape | Unchanged; the parser trusts the backtick text |
| Typed-name validation | A new check that **rejects**; `sanitize_stem` is not reused on this path |
| A refused name | Reuses `skipped_assets` with kind `typed_name_refused`, and holds the owning note |
| Inventory | Hand-written, guarded by a two-sided join test |

### SectionStatus

| Section | Status |
|---------|--------|
| Constraints | `Complete` |
| Implementation Context | `Complete` |
| Solution Strategy | `Complete` |
| Building Block View | `Complete` |
| Runtime View | `Complete` |
| Cross-Cutting Concepts | `Complete` |
| Architecture Decisions | `Complete` — 8 ADRs, all confirmed |
| Acceptance Criteria | `Complete` |
| Risks and Technical Debt | `Complete` |

### ADRStatus

| ADR | Name | Confirmed |
|-----|------|-----------|
| ADR-1 | 037's ADR-5 is superseded; the suggestions wire moves `2` → `3` | ✅ owner 2026-09-30 |
| ADR-2 | The conflict is a top-level array, not a per-suggestion field | ✅ owner 2026-09-30 |
| ADR-3 | Carry what the consumer cannot derive; omit what it can | ✅ owner 2026-09-30 |
| ADR-4 | The markdown keeps its shape; the parser trusts the backtick text | ✅ owner 2026-09-30 |
| ADR-5 | A typed name is **rejected**, never sanitised; `sanitize_stem` is not reused | ✅ owner 2026-09-29 |
| ADR-6 | A refused name reuses `skipped_assets` and **holds** the owning note | ✅ owner 2026-09-30 |
| ADR-7 | The inventory is hand-written with a two-sided join test | ✅ owner 2026-09-30 |
| ADR-8 | `attachments` becomes required on the wire | ✅ owner 2026-09-30 |

---

## Constraints

- **CON-1** — The release is coordinated. The consumer's vendored schema pins the
  version and rejects unknown properties, and treats a validation failure as
  fatal for the whole document. Nothing ships to a live wire before their copy is
  updated.
- **CON-2** — The version move is a functioning gate: `load_changed_wire`
  (`suggestion-parser.py:270-278`) rejects a wire whose `schema_version` does not
  match and falls back to the markdown **without failing**. A half-finished move
  produces no error, only a wire path that stops being used.
- **CON-3** — Additive only. Every conflict-free run's output stays
  byte-identical apart from the version stamp.
- **CON-4** — `_asset_dest_join` (`render_actions.py:560-575`) deliberately does
  not sanitise, because it must preserve a real attachment's basename verbatim.
  That stays true; the new check sits **before** it rather than inside it.
- **CON-5** — Constitution L1 (Testing): vault-mutating paths owe a happy path
  and a failure case; validation owes proof of both acceptance and rejection.
- **CON-6** — ADR-11: no executor internals in rendered text. The owner-facing
  wording states only what the renderer verified.
- **CON-7** — The owning-note list is complete **for the run only**. A note filed
  in an earlier run that embeds the same attachment is invisible to both sides
  (backlog, 2026-09-30), so no rendered text may imply the list is exhaustive.
- **CON-8** — **An open constitutional obligation, surfaced by running the
  check rather than citing it.** MiYo Constitution L2 (Architecture): *"Any change
  that affects interactions between MiYo components … must be reflected in MiYo
  Kokoro as an updated design note or ADR — **before or alongside the
  implementation**."* This spec is exactly such a change, and the Kokoro handoff
  that would satisfy it is **written but not yet sent**
  (`_outbox/for-kokoro/2026-09-29_…four-specs-since-july…`). So the obligation is
  live: the handoff goes out before or with the implementation, not after it. It
  already asks for the two ADRs this design assumes — the boundary-is-several-
  channels rule, and the producer-inventory/consumer-coverage-map mechanism that
  F4 builds.

## Implementation Context

### Required Context Sources

| Source | Why |
|---|---|
| `tomo/schemas/suggestions-wire.schema.json` | The live schema; carries the invariant this spec restores |
| `tomo/schemas/hashi-suggestions-wire.schema.json` | Tomo's copy of what the consumer vendors; must move in lockstep |
| `tomo/schemas/shapes/suggestions-wire.shape.json` | The committed manifest `wire_gate.py` diffs against |
| `tomo/scripts/suggestions-render.py` | `_wire_note` (:293), `build_wire_payload` (:422) — the emit side |
| `tomo/scripts/suggestion-parser.py` | `load_changed_wire` (:243), `build_from_wire` (:325, the `[]` at :492), `_walk_attachment_conflicts` (:2268), `parse_attachment_conflict_remedies` (:2355), `_join_attachment_conflict_remedies` (:2370) |
| `tomo/scripts/suggestions-reducer.py` | `detect_attachment_conflicts` (:582), `_propose_asset_name` (:521), `render_attachment_conflicts_block` (:1438) |
| `tomo/scripts/lib/render_actions.py` | `_build_move_asset_actions` (:691), `_asset_dest_join` (:560), `suppress_moves_for_unfiled_attachments` (:1410) |
| `tomo/scripts/lib/obsidian_filename.py` | `sanitize_stem` (:36) — read to understand why it is **not** reused here |
| `tomo/scripts/lib/embed_rewrite.py` | `rewrite_renamed_embeds` (:91) — consumes the resolved name |
| `tests/test_037_remedy_lost_on_the_wire_path.py` | Three tests change together; the strict xfail flips |
| `tests/test_037_typed_rename_target_is_ignored.py` | Strict xfail flips; one test is deleted with it |

### Implementation Boundaries

**In scope:** the suggestions wire schema and its two sibling artefacts; the emit
projection; both Pass-2 read paths; the typed-name check; the move builder's
rename branch; the note-holding pass; the instruction document's report; the
inventory file and its test; user documentation.

**Out of scope:** the instructions wire; the consumer's editor; the
`delete_source` control gap; any reverse index of which vault notes embed an
attachment; sanitising destinations Tomo computed.

### External Interfaces

| Direction | Interface | Change |
|---|---|---|
| Outbound | suggestions wire → consumer's editor | New top-level `attachment_conflicts[]`; `schema_version` `2` → `3`; `attachments` becomes required |
| Outbound | inventory file → consumer's build | New artefact; they vendor it and join it against their coverage map |
| Inbound | consumer's editor → suggestions wire | They may write `remedy` and `proposed_name`; every other field round-trips |
| Unchanged | instructions wire → executor | No change. The executor's own destination check stays the final guard |

### Cross-Component Boundaries

The consumer must, in the same coordinated release: vendor the new schema, add a
remedy control and a rename text field, and vendor the inventory. Their issue
#141 is the tracking item. Nothing here is deployable alone (CON-1).

### Project Commands

```
./venv/bin/python -m pytest tests/ -q
./venv/bin/python -m ruff check tomo/scripts/
```

## Solution Strategy

The spec restores one invariant — *every editable decision the markdown offers is
carried on the wire* — and it does so by extending existing mechanisms rather
than adding parallel ones. Four moves:

1. **Put the decision on the wire** as a top-level array, mirroring the shape
   `tag_handler_groups` already uses for a decision that is not per-suggestion.
2. **Make the markdown's name a value rather than decoration** by extending the
   trust model already in force: the ticks are authoritative over the JSON, so
   the name beside them is read the same way.
3. **Guard the new input at one place**, before the destination is assembled, and
   make its failure mode *refusal with a record* rather than repair.
4. **Publish what the markdown offers** as a file, so the next gap of this class
   is a build failure on the consumer's side rather than a defect report.

The through-line: every new behaviour is a narrowing of an existing path, not a
new path. The one genuinely new artefact is the inventory, which exists because
nothing today can answer "what does the markdown offer?" mechanically.

## Building Block View

### Components

| # | Component | Responsibility | Requirement |
|---|---|---|---|
| C1 | `detect_attachment_conflicts` (modified) | Produce the conflict records. Unchanged in behaviour; its output now also feeds the wire | F1 |
| C2 | `build_wire_payload` / `_wire_note` (modified) | Project the conflict records onto the wire; make `attachments` unconditional | F1, ADR-8 |
| C3 | The two producer schema artefacts (modified) | Declare the new array, move the version, regenerate the shape manifest. The vendored `hashi-` copy is **not** one of them — it records the consumer's state and moves in Phase 5, per the 035 precedent (`4338481` moved the pair; `f63b947` refreshed the vendored copy once Hashi confirmed) | F1, CON-1, CON-2 |
| C4 | `render_attachment_conflicts_block` (modified) | Render the remedy lines; the rename line's name becomes an editable value, and the impossible case gains one | F2 |
| C5 | `_walk_attachment_conflicts` / `_join_attachment_conflict_remedies` (modified) | Read the remedy **and** the name from the markdown | F2 |
| C6 | `build_from_wire` (modified) | Read the remedy and the name from the wire; the `[]` at `:492` becomes a projection | F1 |
| C7 | **`lib/typed_name_check.py` (new)** | Decide whether a typed name is usable, and say why not. One rule, both paths | F3 |
| C8 | `_build_move_asset_actions` (modified) | Consume a validated name; withhold the move and record a refusal | F3 |
| C9 | `suppress_moves_for_unfiled_attachments` (modified) | Hold the owning note for the new refusal kind | F3, ADR-6 |
| C10 | `render_md.py`'s skipped block (modified) | Report the refusal to the owner in the existing register | F3, CON-6 |
| C11 | **`tomo/schemas/suggestions-decision-inventory.json` (new)** | Declare every editable decision the markdown offers | F4 |
| C12 | **The inventory join test (new)** | Fail when the inventory disagrees with either the schema or the parser; the parser side harvests control literals by an `ast` walk over comparison subjects and fails closed on any literal that is neither in a row nor justifiably absent | F4, ADR-7 |
| C13 | `docs/usage.md`, `docs/troubleshooting.md` (modified) | State that the name is editable, what a refusal looks like, and which surface wins | S1 |

**Responsibility matrix — no requirement has two owners, none has zero:**

| Requirement | Owning components |
|---|---|
| F1 remedy survives the JSON path | C1 → C2 → C3 → C6 |
| F2 editable rename target | C4 → C5 (markdown), C2 → C6 (wire) |
| F3 refused and recorded | C7 (decide) → C8 (withhold) → C9 (hold note) → C10 (report) |
| F4 inventory | C11 (declare) → C12 (guard) |
| S1 documentation | C13 |
| C1 summary counts refused names | C10 (same renderer, the summary rather than the bullet) |
| C2 inventory row carries a note | C11 |

C7 owns the *decision*; C8 owns the *consequence*. That split is deliberate — the
same rule must serve both read paths, and a rule living inside the move builder
would be reachable only from one of them.

### Interface Specifications

**The wire array** (top-level, sibling of `tag_handler_groups`):

| Field | Editable by consumer | Why it is here |
|---|---|---|
| `source` | no | The key. One entry per attachment, however many notes embed it |
| `destination` | no | Context. Not derivable — the wire carries only the profile's *name* |
| `same_file` | no | Context. Not derivable — the consumer has no binary read at all |
| `remedy` | **yes** | The decision. Enum; defaults the way the markdown pre-ticks |
| `proposed_name` | **yes** | The parameter. Nullable — null means Pass 1 found no free name |

`owner_source_items` is **not** carried (ADR-3). The consumer derives it by
scanning `suggestions[].attachments` for the same path, which ADR-8 makes safe.

**`taken` is deliberately not one of C7's reasons** (owner ruling 2026-10-01).
The other three are properties of the string; `taken` is a property of the run,
and the run already decides it — `render_actions.py:836`'s claimed check, which a
remedy-chosen destination passes through by design (`:831-835`), emitting
`kind: "collision"`. Giving C7 a fourth reason would mean handing it run state,
duplicating a check that already fires. The vault-side reading of "taken" is a
different matter and is not decidable in Pass 2 at all: there is no vault listing
on this path, and the wire carries no occupancy set. See `requirements.md` F3's
fourth criterion, which records both readings.

**The typed-name check** (C7) answers one question and returns one of a closed
set of refusal reasons, so C10 can render each without interpreting a string:
separator present, forbidden character, blank. A usable name returns the
name unchanged — the check never rewrites.

**The inventory row**: `id` (stable, opaque), `markdown_control` (prose, for
humans — and consumer-facing, so it names the control as the owner encounters it,
carrying no Tomo source paths), `wire_field` (path or `null`), `editable` (`false`
only for a retired control), `parser_label` (the literal strings the parser
compares against to recognise this decision — an **array**, many-to-one, required
when `editable` is true and permitted absent when it is false), optional `note`.

`parser_label` was added in Phase 1 (T1.1b, owner ruling 2026-09-30) because the
parser-side half of ADR-7's join had no usable key: `wire_field` is `null` on the
attachment-conflict remedy, and `markdown_control` is prose. Without it the
mapping would have lived as a hand-written dict inside the test — "a rule someone
has to remember", which is the mechanism ADR-7 names as what failed in 037. It is
an array because the parser matches several literals for one decision: the
approve checkbox fires on either `accept` or `approve`, a field line accepts four
key spellings, and the remedy resolves from three separate labels.

## Runtime View

### Primary Flow — Pass 1

1. `detect_attachment_conflicts` runs as today: one folder listing per run, one
   entry per occupied destination, keyed by source path.
2. `render_attachment_conflicts_block` renders the three remedies with the
   computed name in the rename line's backticks — **unchanged output for every
   existing case**. When no free name was found, the line now carries empty
   backticks rather than no parameter at all, so the owner has somewhere to type.
3. `build_wire_payload` projects the same records into `attachment_conflicts[]`,
   with `remedy` defaulted exactly as the markdown pre-ticks it, and stamps
   `schema_version: "3"`.

Nothing consults the vault a second time. The conflict records are computed once
and rendered twice.

### Primary Flow — Pass 2, markdown path

1. `parse_attachment_conflict_remedies` resolves the tick state to a remedy, as
   today.
2. **New:** for a `rename` entry it also reads the backtick text as the name. On
   an untouched document that text is the computed name, so the result is
   identical to today's join.
3. `_join_attachment_conflict_remedies` no longer needs the structured doc for
   the name; it keeps using it for entries the markdown does not carry.
4. The typed-name check runs (C7). A usable name proceeds; a refused one produces
   a refusal reason.

### Primary Flow — Pass 2, wire path (the path this spec exists for)

1. `load_changed_wire` accepts the wire only when `schema_version` matches — so
   the version move must be complete or this path silently stops being taken
   (CON-2).
2. `build_from_wire` projects `attachment_conflicts[]` into the same
   `{source, remedy, proposed_name}` triple the markdown path produces. The
   hardcoded `[]` is gone.
3. The typed-name check runs — **the same check, on the same triple**. This is
   why C7 is its own component.

From step 3 onward the two paths are indistinguishable, which is F1's acceptance
criterion stated as a design property.

### Error Handling

| Situation | Behaviour | Fail direction |
|---|---|---|
| Typed name has a separator, a forbidden character, is blank, or is taken | No move emitted; a `skipped_assets` entry records the reason; the owning note is held | Closed — nothing is filed under a name we could not verify |
| Typed name unreadable (a half-edited line) | Treated as a refused name, never as a different remedy | Closed |
| `proposed_name` null and remedy `rename` | Degrades to `keep_in_inbox`, as today | Unchanged |
| Wire version mismatch | Markdown path is used; a warning on stderr | Open — the run proceeds, per ADR-026. CON-2 is why this is a risk rather than a safeguard |
| Vault listing unavailable in Pass 1 | No conflicts raised; run proceeds | Open, as 037 established |

### Complex Logic — why the check cannot live inside `_asset_dest_join`

`_asset_dest_join` takes the last path segment (`rsplit("/", 1)[-1]`) and joins it
to the asset folder. That makes a typed `../../x/passwd` **structurally harmless**
— it becomes `passwd` and cannot escape the folder. It also makes it **silent**,
which is the behaviour ADR-5 forbids.

The helper cannot be changed to refuse, because it is also the join for every
ordinary attachment, whose real basename must pass through verbatim (CON-4). So
the check sits before it and the helper stays exactly as it is. The truncation
remains as defence in depth: if a typed name ever reached the helper unchecked,
it would still not escape.

## Cross-Cutting Concepts

### Cost

No new vault interaction. The freeness check for a typed name reuses the Pass-1
listing the conflict records were built from — the same staleness window the
project already accepts, not a new one. Pass 2 still makes no vault calls.

### Fail direction

Every new check fails **closed** on the owner's data: when we cannot verify a
name, nothing is filed under it and the note stays with its attachment. The one
open-failing path is inherited (a version mismatch falls back to the markdown),
and CON-2 records that this is the risk to watch rather than a comfort.

### Security and privacy

This is the first owner-typed string in the codebase to become a vault write
destination. Traversal was already structurally contained; this spec adds the
report. No content is logged: a refusal records the attachment path and a reason
class, never the rejected name's content beyond what the owner already sees in
their own document — consistent with Constitution L2 on metadata-only traces.

## Architecture Decisions

### ADR-1 — 037's ADR-5 is superseded; the suggestions wire moves `2` → `3`

**Choice.** The suggestions wire gains a field, and its `schema_version` moves
from `2` to `3` across the live schema and the shape manifest. The vendored copy
is deliberately **not** moved with them: it records what the consumer actually
vendors, so stamping the new version there would make the parity comparison read
clean while their real copy still rejects every document we emit. It is refreshed
in Phase 5, once Hashi confirms — the sequence spec 035 followed (`4338481` moved
the producer pair, `f63b947` refreshed the vendored copy afterwards). Owner ruling
2026-10-01.

**Rationale.** 037's ADR-5 claimed no wire change was needed and verified it
against the consumer's compiled validator — on the **instructions** wire. The
check was rigorous and answered the wrong question. Recording the supersession
explicitly matters more than usual here: the old ADR reads as current and its
evidence looks conclusive.

The version move is not bookkeeping. `wire_gate.classify()` treats an added
property on a **closed** node as consumer-affecting, and both the root and
`suggestions[].items` are closed.

**Trade-offs.** Forces a coordinated release (CON-1) and a handover. The
alternative — an open node to avoid the move — would hide the change from the
gate that exists to catch exactly this.

**Confirmed** by the owner 2026-09-30.

### ADR-2 — The conflict is a top-level array, not a per-suggestion field

**Choice.** `attachment_conflicts[]` at the top level, beside
`tag_handler_groups`.

**Rationale.** One attachment has one decision however many notes embed it — the
invariant 037 established when it moved dedup from destination to exact source
path. Nesting the decision under each owning suggestion denormalises it and
reopens that bug class directly: two owners could carry divergent values, and an
owner whose own suggestion was skipped would take the only copy of the decision
with it.

**Trade-offs.** The consumer must join the array to its cards rather than find
the field on one. That join is `source` against `suggestions[].attachments`, which
ADR-8 makes reliable.

**Confirmed** by the owner 2026-09-30.

### ADR-3 — Carry what the consumer cannot derive; omit what it can

**Choice.** Carry `destination` and `same_file`. Do not carry the owning notes.

**Rationale.** Both inclusions are necessities the consumer established, not
preferences: the wire carries only the profile's *name*, so nothing tells them
where attachments are filed; and their vault port has no binary read at all —
a UTF-8 round trip through it corrupts a binary — so byte-identity would cost
them a binary path in a shared abstraction plus per-conflict I/O in an editor.
We have already compared the files. The owning notes they derive from the run,
and our own list is no better than theirs (CON-7).

**Trade-offs.** Two read-only fields on a closed node. Cheap, and both are the
answer to "why is this a conflict at all", which their card has to show.

**Confirmed** by the owner 2026-09-30.

### ADR-4 — The markdown keeps its shape; the parser trusts the backtick text

**Choice.** `- [x] Rename to \`<path>\`` stays as it is. The parser reads the
backtick content as the name, unconditionally, with no "was this edited?" flag.

**Rationale.** On an untouched document the backtick text *is* the computed name,
so the common case is byte-identical and needs no special case. This extends the
trust model already in force — the ticks are authoritative over the JSON — rather
than introducing a second one. A split parameter line would need both renderer
and parser to learn a new line form, and `_walk_attachment_conflicts` reads only
label lines today.

**Trade-offs.** Decision and parameter share a line, so a half-deleted backtick
makes the name unreadable. Handled: unreadable is a refusal (ADR-5), never a
silent fallback and never a different remedy — the label prefix still matches.

**Confirmed** by the owner 2026-09-30.

### ADR-5 — A typed name is rejected, never sanitised

**Choice.** A new `lib/typed_name_check.py` decides usability and returns a
closed set of refusal reasons. `sanitize_stem` is **not** reused on this path.

**Rationale.** `sanitize_stem` substitutes — `/` becomes `-`. Reusing it would
file the owner's `a/b.png` as `a-b.png` with nothing reported, which is the exact
defect this spec closes wearing a different hat. The standing ruling is that Pass
2 checks, surfaces and records; nothing more.

A separate module rather than a branch inside the move builder, because the same
rule must serve the markdown path and the wire path, and a rule inside the
builder is reachable from neither independently.

**Trade-offs.** A typo costs the owner another run. Accepted explicitly.

**Confirmed** by the owner 2026-09-29.

### ADR-6 — A refused name reuses `skipped_assets` and holds the owning note

**Choice.** A new `kind` on `skipped_assets` — **`typed_name_refused`** — and it
is **not** added to `suppress_moves_for_unfiled_attachments`'s exclusion list, so
the owning note is held with its attachment.

The literal was fixed here on 2026-10-01 rather than left to T3.2's implementer:
T3.2 emits it, T3.3 asserts it is absent from an exclusion list, and T3.4 branches
on it to render a bullet, so three tasks and three review cycles compare against
the same string. It follows the existing kinds' shape (`no_basename`,
`vault_collision_held`, `collision` — snake_case, naming why the move did not
happen) and keeps this ADR's own word, *refused*. `typed_` carries the part that
matters: a **computed** name is never checked, and the kind should not read as
though it could be.

**Rationale.** Reusing `skipped_assets` follows 037's ADR-3: a fourth records
list would need its own renderer, its own diff reconciliation and its own
audit path. Holding the note is the distinction that matters: 037 excluded
`vault_collision_held` because the owner *chose* to leave the attachment behind.
A refused name is the opposite — the owner chose to rename and we refused. That
is the same shape as `collision` and `no_basename`, which both hold the note.

**Trade-offs.** The note stays in the inbox until the owner fixes the name, which
is a stronger consequence than `keep_in_inbox` has. That is the point: the owner
asked for something that did not happen.

**Confirmed** by the owner 2026-09-30.

### ADR-7 — The inventory is hand-written, guarded by a two-sided join test

**Choice.** `suggestions-decision-inventory.json` is maintained by hand. A test
joins it in **both** directions: every schema field marked `Editable` needs a
row, and every editable control the parser recognises needs a row.

**Rationale.** A hand-written file with a review rule is precisely the mechanism
that failed in 037 — a rule someone has to remember. A declarative registry both
the renderer and the inventory read would make drift impossible rather than
merely detected, but it is a refactor across the reducer and the parser inside a
spec already carrying four deliverables and a wire version move, and it cuts
against additive-only so close to MVP.

The two-sided join is affordable because both sides are enumerable: the schema
already marks 23 fields `Editable`, and the parser recognises its controls
through a small set of label literals. It is also the mirror of the guard the
consumer just built, which is the strongest argument that the shape works.

**Trade-offs.** The test catches a missing row, not a *wrong* row — a row whose
`wire_field` names the wrong path passes. Accepted; the consumer's own join
catches that from the other side.

**Confirmed** by the owner 2026-09-30.

### ADR-8 — `attachments` becomes required on the wire

**Choice.** Add `attachments` to `suggestions[].items.required`.

**Rationale.** `_wire_note` (`suggestions-render.py:293`) already emits it
unconditionally, defaulting to `[]`. But the schema permits absence and the
consumer treats absent as "none" — so their derivation of the owning notes works
**by accident**, and an emitter change would silently hand them an empty list.
That is this spec's own defect class pointing the other way. The version is
moving anyway, so closing it costs nothing.

**Trade-offs.** None identified. It makes a guarantee out of current behaviour.

**Confirmed** by the owner 2026-09-30.

## Quality Requirements

| Quality | Requirement | How it is met |
|---|---|---|
| Correctness | Both Pass-2 paths produce identical remedies for identical decisions | Design: the paths converge on one triple before the check runs |
| Safety | Nothing is filed under an unverified name | ADR-5 + ADR-6, failing closed |
| Compatibility | Conflict-free runs stay byte-identical apart from the version stamp | The projection adds an empty array; existing goldens gain one key |
| Consumer integrity | No user sees a half-released wire | CON-1, one coordinated handoff |
| Traceability | Every refusal is visible to the owner | C10, in the existing skipped-block register |
| Honesty | No rendered sentence asserts more than the renderer verified | CON-6 and CON-7 |

## Acceptance Criteria

The PRD's 38 criteria are the contract. The SDD's additions are the ones only a
design can state:

- [ ] Given the version move, When either producer artefact — the live schema or
      the shape manifest — is left behind, Then the wire gate fails; and when the
      vendored copy is left behind (as Phase 2 intends), Then the vendored-parity
      comparison reports it. **Measured 2026-10-01:** these are two different
      mechanisms and neither substitutes for the other. `run_wire_gate` compares
      the schema against the manifest and never reads the vendored copy, so it
      returns `passed=True, actions=[]` on a complete move with the vendored copy
      still at the old version. The vendored copy is owned instead by
      `test_wire_snapshot_parity.py`'s
      `test_suggestions_comparison_a_is_clean_offline`, whose expectation is
      re-measured to the six-entry delta Phase 2 creates and returns to zero in
      Phase 5 — a half-finished move cannot ship quietly, but only because both
      guards exist
- [ ] Given a conflict-free run, When its wire is compared to the pre-change
      golden, Then the only differences are the version stamp and an empty
      `attachment_conflicts` array
- [ ] Given the typed-name check, When it is called from the markdown path and
      from the wire path with the same triple, Then it returns the same verdict
- [ ] Given a refused name, When the note-holding pass runs, Then the owning note
      is withheld — and a test asserts this specifically, because the exclusion
      list is where 037 had to make the opposite choice explicit
- [ ] Given the inventory, When a schema field marked `Editable` has no row, Then
      the join test fails
- [ ] Given the inventory, When a parser-recognised control has no row, Then the
      join test fails
- [ ] Given `_asset_dest_join`, When this spec ships, Then it is unchanged — the
      check sits before it

## Risks and Technical Debt

### Known Technical Issues

- **The version move is the silent failure mode.** A mismatch falls back to the
  markdown without erroring, so an incomplete move looks like success. The
  closing condition must include a run that proves the wire path is still taken.
- **The goldens are hand-built full payloads.** `test_suggestions_wire_golden.py`
  constructs expected dicts literally, so the new key is a mechanical edit across
  several fixtures — real work, easy to half-finish.

### Technical Debt

- **Accepted:** the inventory is hand-written. ADR-7 records the registry as the
  better design and why it is not this spec's.
- **Accepted, recorded 2026-09-30:** a rename breaks the embed in any note filed
  by an earlier run. Needs a reverse index we do not have; the cost is a vault
  query per conflicted attachment, which the Pass-1 design deliberately avoids.
- **Pre-existing:** the two Pass-2 paths normalise `delete_source` differently.
  Inert, tested, out of scope here.

### Implementation Gotchas

- `_join_attachment_conflict_remedies` currently reads `proposed_name` from the
  structured doc **by `source`**. The markdown now supplies it; do not leave both
  in play, or a stale doc wins over the owner's keystrokes.
- Three tests in `test_037_remedy_lost_on_the_wire_path.py` change together — the
  strict xfail flips and two defect-recording tests are deleted. The file's own
  docstring says the suite goes from `4 passed, 1 xfailed` to `3 failed` when the
  fix lands; that is the signal the change is working, not a regression.
- `rewrite_renamed_embeds` is called **before** `_build_move_asset_actions`, so it
  recomputes the new basename from `proposed_name` directly. A typed name must be
  validated before that point, or the embed is rewritten to a name that is then
  refused.

## Open Questions

None. The two the PRD carried were answered by the consumer on 2026-09-29 and
are now requirements in F1 and F4.

## Glossary

| Term | Meaning |
|---|---|
| Suggestions wire | `_suggestions.json` — the structured mirror of the review document, editable by the consumer's editor |
| Instructions wire | The Pass-2 output the executor applies. Untouched by this spec |
| `emit_digest` | The hash that tells Pass 2 whether the wire was edited; a mismatch makes the wire authoritative (ADR-026) |
| Remedy | One of `rename`, `keep_in_inbox`, `ignore` — the owner's answer to an occupied destination |
| Refusal reason | A closed set of three, all properties of the string: separator, forbidden character, blank. A run-local collision is refused separately, by the claimed check that already exists |
| Retired control | A markdown control that no longer exists; keeps its inventory row at `editable: false` |
