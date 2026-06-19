# WHY: instruction-render.py

> Rationale for decisions in `tomo/scripts/instruction-render.py`.
> The script is deterministic Pass-2 rendering: it reads `parsed-suggestions.json`
> (from `suggestion-parser.py`), templates each approved note, and emits the
> canonical `instructions.json` (consumed by Tomo Hashi) plus a human-readable
> `instructions.md` — both rendered without any LLM assembly.

## Filename collision guard — C5 (F-41, XDD 016, ADR-7)

WHY this exists: F-41 lets one inbox item produce N atomic notes. The filename
for each note is derived deterministically as `date_prefix + slugify(title)`.
With N atomics from a single source, two threads can slugify to the same
filename (identical or near-identical titles, or two notes on the same date with
titles that collapse to the same slug). The pre-F-41 code wrote each rendered
note to its derived path unconditionally — a second note with the same filename
would silently overwrite the first. That is a data-loss class: a thread the user
approved would vanish before it ever reached the vault.

WHY a stable `_NN` suffix rather than a hash or timestamp (`_disambiguate_filename`):
the disambiguator must be deterministic and reviewable. A user scanning
`instructions.md` should see `…my-topic.md` and `…my-topic_01.md` and understand
the relationship at a glance; a hash suffix would be opaque and a timestamp would
make the same input render to a different filename on every run (defeating any
diff-based review). The guard appends `_01`, `_02`, … in the order callers
present collisions, within a per-run `used_filenames` set.

WHY it errors instead of silently overwriting when exhausted: the guard caps at
99 attempts and raises rather than wrapping or overwriting. Silent overwrite is
the exact bug C5 fixes — degrading back to silent overwrite on an edge case would
re-introduce it. A loud failure surfaces the (pathological) collision to the
maintainer instead of losing a note. The common case — distinct titles already
producing distinct filenames — returns the base filename unchanged, byte-
identical to pre-F-41 output (CON-2).

## Source-deletion completion gate — C6 (F-41, ADR-6, OQ6)

WHY this replaced paired-delete-after-first: the pre-F-41 code emitted a
`delete_source` for an origin as soon as it saw the FIRST `move_note` derived
from that origin (a `paired_seen`-after-first dedup). Under F-41, one origin
produces N move_notes (one per atomic). Deleting after the first move_note would
remove the source inbox item before atomics 2..N were captured in the vault —
losing every thread but the first. This is precisely the data-loss scenario
PRD C4 / OQ6 guards against, and the triggering incident behind the whole
feature (a multi-thread voice memo whose second thread was dropped).

WHY a per-origin completion gate keyed on an expected count: the fix groups
move_notes by origin stem and emits the single `delete_source` only when the
number of rendered move_notes for that origin equals the number of approved
atomics expected for it (`expected_by_stem`, counted from `confirmed_items`), AND
any accepted `update_daily` for that stem has been handled. Until then it defers
— the source is preserved until every derived thread it produced is captured
(OQ6). `source_stem` (ADR-4) is what makes the grouping reliable: it gives a
single explicit key to count expected atomics against, rather than inferring
origin membership from note paths.

WHY a `keep_origin` opt-out short-circuits the gate: if ANY confirmed atomic from
an origin carries the user's "Keep origin" decision, the origin is never deleted
regardless of the count. The user's explicit intent to retain the source
overrides the automatic completion gate — the gate's job is to PREVENT premature
deletion, not to FORCE deletion the user declined.

WHY a rejected thread does not block deletion but an un-actioned one does: the
gate counts approved atomics. A thread the user rejected was never going to
become a note, so it is not part of the "expected" denominator and must not
deadlock the gate forever. An approved-but-not-yet-rendered thread legitimately
defers the delete. This keeps the source alive until exactly the set of threads
the user chose to keep have landed.

## Version 0.21.0

WHY: Bumped across the F-41 work for the C5 filename collision guard
(`_disambiguate_filename`) and the C6 source-deletion completion gate
(per-origin expected-count gate replacing paired-delete-after-first).
`update-tomo.sh` skips unchanged versions silently — the bump is required for the
edit to ship to the Docker instance.

## link_to_moc internal-field lifetime

WHY `new_section` / `fit_confidence` (and the defensive `alt_headings` guard)
live on the action object only between two well-defined points:

- They are LIFTED onto the action in `_build_link_to_moc_actions._emit` from the
  Pass-1 anchor. They are deliberately TOP-LEVEL action fields, not nested in
  `anchor` — the `instructions.schema.json` `anchor` object is
  `additionalProperties:false {type,value}`, so anything extra inside it would
  be rejected (anchor no-leak contract).
- They are CONSUMED in-place by the pipeline: `_serialize_new_sections` bakes
  `new_section` into `line_to_add`; `_emit_resolution_telemetry` reads
  `fit_confidence` for per-placement scoring.
- They are REMOVED by `_strip_internal_link_fields`, which MUST run after
  serialize + telemetry. They never reach Hashi — the link_to_moc wire schema
  is also `additionalProperties:false`, and leaving them on makes Hashi's
  un-discriminated `oneOf` fall through to `move_note` with a misleading
  "must have required property source" error.

The one-line comment at `_emit` records this lifetime at the lift site; this
section is the full rationale. Parity-locked with the wire-hygiene contract
(see `reference_link_to_moc_wire_hygiene`).
