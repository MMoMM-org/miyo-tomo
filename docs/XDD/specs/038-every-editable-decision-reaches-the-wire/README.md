# Specification: 038-every-editable-decision-reaches-the-wire

## Status

| Field | Value |
|-------|-------|
| **Created** | 2026-09-29 |
| **Current Phase** | SDD |
| **Decomposition tier** | {{DECOMPOSITION_TIER}} |
| **Last Updated** | 2026-09-30 |

## Documents

| Document | Status | Notes |
|----------|--------|-------|
| requirements.md | completed | v1.0, 38 acceptance criteria; both open questions answered by the consumer 2026-09-29 |
| solution.md | completed | v1.0, 8 ADRs all confirmed; CON-8 records a live L2 obligation |
| plan/ | pending | |

**Status values**: `pending` | `in_progress` | `completed` | `skipped`

**Decomposition tier**: `Direct` (no plan) | `Incremental` (phase plan). Set by the classifier at the decomposition step and confirmed by the user; leave the placeholder until then. Read back by `spec.py --read`, which treats anything it does not recognise as absent.

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-29 | Spec opened | Spec 037 shipped an editable decision that reaches no wire. Its consumer found the resulting data-loss path on merge day, and a second instance (`delete_source`) surfaced in the same week. The fix is consumer-coordinated, so it gets its own spec rather than a fix branch. |
| 2026-09-29 | Scope is three artefacts, not one (a fourth was added 2026-09-30) | Owner rulings 2026-09-29: the wire must carry the attachment-conflict remedy; the rename target must be editable on both surfaces; and the parity inventory ships as a vendored JSON file rather than as prose in handoffs. |
| 2026-09-29 | An unusable typed name is **rejected and reported**, never sanitised | Owner, after research showed the only existing helper (`sanitize_stem`) *substitutes* rather than rejects — including `/` → `-`. Rejection covers the silent truncation `_asset_dest_join` performs today (`../../x/passwd` → `passwd`, with nothing reported) and is the only reading that fits "no silent substitution". Cost accepted: a typo costs another run. |
| 2026-09-29 | The "no free name available" line becomes typeable too | Owner. Pass 1 only searches the ` (n)` pattern, so "no free `(n)` name" does not mean no free name exists. Leaving it read-only would make the case that most needs a rename the only case without one. |
| 2026-09-29 | Wire-over-markdown precedence is **documented, not changed** | Owner. ADR-026 already makes an edited wire authoritative for every editable field; 038 adds one more field, it does not create the rule. Detecting divergence would require reading the markdown on the wire path, which is precisely what ADR-026 forbids. Goes into `usage.md` and the inventory file as a stated rule. |
| 2026-09-30 | Everything ships in one release — the inventory does **not** go early | Owner, declining the consumer's request to ship it first. Their argument was sound (the inventory's value is the rows neither side knows about, and every day it is absent is a day an already-wrong row stays invisible). Overruled in favour of one coordinated delivery, because the release is forced to be coordinated anyway by the version move, and a second partial handoff costs more than it buys. |
| 2026-09-30 | The release includes a runnable test setup for the consumer | Owner. Their QA vault cannot exercise what they just built: its only suggestions run has **one** worthy card, the other six are suppressed and render only Force Atomic, and no run either side holds carries `delete_source: true` — so the tri-state's delete leg and the stale-flag render path are reachable only by hand. We hold a vault with a real conflict fixture, so we send the run rather than describe it. Precedent: `_archive/outbox/2026-09/2026-09-14_tomo-run-fixture-three-buckets_suggestions.json`. |
| 2026-09-30 | The inventory row carries a stable opaque `id`; `editable` stays for retired controls | Consumer's request, accepted — and the reasoning is theirs: `markdown_control` is prose and prose gets reworded (our own warning bullet changed wording four times in two days), which their join would read as one row deleted plus one added, silently dropping that row's coverage claim. `wire_field` is `null` for exactly the rows that matter, so it cannot be unique. `editable: false` on a retired row becomes their signal to remove a control rather than keep one writing a field we no longer honour. |
| 2026-09-30 | The wire carries the occupied destination and byte-identity; the owning notes are derived | Consumer's answer to the PRD's open question. Neither is a preference: the wire carries only the profile's *name*, so the destination is not derivable; and their vault port has no binary read at all — a UTF-8 round trip through it corrupts a binary — so byte-identity would cost them a binary path in a shared abstraction plus per-conflict I/O in the editor. The owning notes they derive from the run. |
| 2026-09-29 | The conflict row is keyed by `source`, not `item_key` | Research finding, not a reversal: the `item_key` agreement with Hashi concerns **note** identity after the spec 034 namesake collision. An attachment conflict is keyed by **attachment** identity — `_build_move_asset_actions` already builds `remedies_by_source`, and `detect_attachment_conflicts` dedups by exact source path so one attachment keeps one decision across several owning notes. Must be said explicitly to Hashi, since "item_key agreed" was written to them in plain language. |

## Context

**The invariant being restored** is written in our own schema, and spec 037
violated it: `suggestions-wire.schema.json` says *"every editable decision the
markdown offers is carried here."*

### Why this is a spec and not a patch

The change is consumer-coordinated. Hashi vendors our suggestions wire schema
and builds editor controls against it, so a field we add alone is a field they
cannot read. Their issues [#140](https://github.com/MMoMM-org/miyo-tomo-hashi/issues/140)
and [#141](https://github.com/MMoMM-org/miyo-tomo-hashi/issues/141) are the
consumer side of this work.

### The deliverables

1. **The wire field for the attachment-conflict remedy.** Today
   `suggestion-parser.py:492` hardcodes `"attachment_conflict_remedies": []` in
   `build_from_wire`, so an `emit_digest` mismatch (ADR-026) silently converts
   the owner's chosen remedy into `ignore` — the most destructive of the three.
   Reproduced in `tests/test_037_remedy_lost_on_the_wire_path.py`.
2. **An editable rename target, on both surfaces.** Today neither surface can
   rename; ours is worse, because it renders the computed name inside a checkbox
   label and then discards anything typed over it
   (`tests/test_037_typed_rename_target_is_ignored.py`). Needs validation that
   **rejects and reports** rather than sanitises, a freeness check, and a defined
   answer when the typed name is also taken. Explicitly forbidden: falling back
   to the computed name.
3. **The parity inventory, as a vendored file.** One row per editable markdown
   decision with its wire field — or `null` — each keyed by a stable opaque `id`.
   Hashi vendors it and joins it to their own coverage map in CI, so a row their
   map does not mention fails their build. `wire_field: null` is the signal
   neither side had at 037's design time.
4. **A runnable test setup for the consumer**, shipped with the same handoff.
   Not a documentation nicety: their QA vault cannot reach the paths their new
   tri-state control covers, so without a run from us the editor side of this
   spec is verified only by unit tests. We hold the conflict fixture; they do not.

### Decided before this spec opened — do not re-derive

| Decision | Source |
|---|---|
| Validation is split: Hashi validates in the editor for immediate feedback; Pass 2 checks, surfaces, and **records in the instruction document — nothing more**. No repair, no substitution, no blocking. | Owner 2026-09-29; Hashi agreed, same reasoning as their destination check |
| Pass 2 must **never** fall back to the computed name when the typed one is unusable | Owner 2026-09-29 — that is the defect being fixed, wearing a different hat |
| Join on `item_key`, not on a stem — **for note identity**. The attachment-conflict row is keyed by `source` instead; see the decisions log. | Hashi, after the spec 034 namesake collision |
| The remedy enum defaults the way the markdown pre-ticks it | Hashi's shape, accepted |
| The inventory excludes read-only fields and per-field docs | Hashi's request, accepted |

### Known-good facts this spec can build on

- `(decision, keep_source, delete_source)` semantics are measured, not inferred —
  `tests/test_delete_source_flag_triple.py`. `delete_source` is the **skip** leg
  and is inert under `approve`; `(skip, keep_source, delete_source)` all true
  **deletes**, because `build_from_wire` never copies `keep_source` into a
  skipped entry.
- The two Pass-2 paths normalise `delete_source` differently — the markdown
  parser forces it `False` on approve, `build_from_wire` does not. Inert only
  because nothing reads a confirmed item's copy.
- An absent remedy source is byte-identical to an explicit `ignore`
  (`_build_move_asset_actions`), which is why the loss is silent on both sides.

### Research findings that are load-bearing (2026-09-29, five parallel agents)

**The release is coordinated and cannot be split.** Hashi's vendored suggestions
schema sets `additionalProperties: false` at the root and every nested object,
compiled with ajv and fatal on failure: `ObsidianSuggestionsDoc.load()` throws
and `SuggestionsEditorView.loadAndRender()` drops the document to an error
screen. Their copy also pins `schema_version` to `"2"`. So both the new field
**and** the version bump would break their editor — and only on runs that have a
conflict, which is the case this spec exists to serve.

**The version bump is a gate, not paperwork.** `load_changed_wire`
(`suggestion-parser.py:270-278`) *rejects* a wire whose `schema_version` does
not match and silently falls back to the markdown. `wire_gate.classify()` treats
an added property on a **closed** node as consumer-affecting, and
`/properties/suggestions/items` and the top level are both closed — so this is
`ACTION_MOVE_VERSION` + `ACTION_HANDOVER`: suggestions wire **2 → 3**, both
schema copies, a regenerated `shapes/suggestions-wire.shape.json`, and a handoff.

**This is the first owner-typed string to become a vault write destination
anywhere in the codebase.** `_asset_dest_join` (`render_actions.py:560-575`)
deliberately does *not* sanitise — correct while `proposed_name` could only ever
be Tomo-computed, and reachable for the first time once it is typed. Known gaps
at that point: `/` and `../` are truncated silently rather than refused;
`: * ? " < > |` and `\` pass through untouched; `" "` slips the existing
emptiness guard (`not " "` is `False`); no length cap, no Unicode normalisation.

**An editable free-text field on this wire is precedented — the guard is not.**
`suggestions[].title` is already an owner-editable string, so the rename target
is not a new capability class. But `title` reaches a destination through
`_dest_join`, which **does** call `sanitize_stem`; the rename target reaches one
through `_asset_dest_join`, which does not. Reading "free text is already
allowed here" as "no new guard is needed" would be exactly the presence-is-not-
safety inference that produced both of this spec's parent defects.

**Extend the existing trust model rather than adding one.** The markdown's ticks
are already authoritative over the JSON; the *name* should be read the same way.
On an untouched document the backtick text **is** the computed name, so the
common case stays byte-identical and no "was this edited?" flag is needed.

**Deferred to the SDD, deliberately:** the wire field's shape (with or without
read-only context for Hashi's card) and the markdown layout (inline backticks
vs. a split parameter line). The open question behind the first is one only
Hashi can answer — whether their editor can derive `destination`,
`owner_source_items` and `same_file` itself — and it rides the next handoff.

**`instructions-diff.py` needs no change.** Verified: it consumes
`instructions.tomo.skipped_assets`, the *output* of remedy processing, never the
remedies list. It is paired with `render_actions.py`'s output, not with this wire
field.

### Full brief

`docs/XDD/backlog.md`, entry *"spec 037's remedy does not survive Pass 2's
JSON-only path, and silently becomes `ignore`"* — including the parity audit
table, the two gaps and how they differ, and both corrections Hashi's reply
earned.

---
*This file is managed by the xdd-meta skill.*
