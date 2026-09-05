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

WHY a `keep_source` opt-out short-circuits the gate: if ANY confirmed atomic from
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

## Branch 4 — tag-handler group source deletion (delete_source v0.35.0)

WHY tag-handler captures need an explicit delete at all: a tag-handler group is
consolidated into its target note via `insert_under_marker`, which *copies* the
captured content as a status block. Unlike `move_note` — which physically
relocates the inbox file, so the source vanishes for free — the copy leaves the
inbox capture behind. Without branch 4 the captures pile up in the inbox after
every run (the reported defect). Branch 4 restores parity with the move_note
origin gate: an APPROVED group's `source_paths` are deleted by default once the
content has been consolidated.

WHY keyed by `group_id`, not origin stem: tag-handler captures are not move_note
origins (no `confirmed_items` / `expected_by_stem` entries), so the completion
gate in branch 3 never sees them. Branch 4 keys deletion on the group's
`group_id` — the same id the suggestion-parser uses for the approval and
keep-origin decisions — so a group's sources are deleted iff the group was
approved and not kept. No per-thread count gate is needed: a group has exactly
one insert, so "consolidated" is a single boolean, not an N-of-M completion.

WHY Keep-origin is per-group here (vs per-stem for atomics): the suggestions doc
renders one Approve/Keep-origin/Skip decision *per group*, so the opt-out is
naturally group-scoped. A checked "Keep origin" box adds the group_id to
`tag_handler_keep_source_group_ids` (parser → `build_actions` →
`_build_delete_source_actions`), which short-circuits the per-source emit.

WHY ordering is safe without a depends_on field: Hashi applies actions in
positional array order. `build_actions` emits the group's `insert_under_marker`
(step 6) before any `delete_source` (step 7), so the captures are always copied
into the target before their sources are trashed. The `emitted` set in branch 4
also dedups against branches 1–3 so a source is never deleted twice.

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

## Block-anchor emission branch — spec 025 T5.1 / FR-16 / ADR-6

WHY resolved_anchor is passed through verbatim (SDD Boundary 1): the Phase 4
interpreter already resolved the exact multi-line anchor value by reading the
live vault note (Kado `kado-read`). Re-deriving it in instruction-render would
require a second vault read at render time, introducing a race condition (the
note could change between Phase 4 and Phase 5) and would de-duplicate the
anchor detection logic. The byte-exact `resolved_anchor.value` is the Phase
4→5 contract; instruction-render must not re-pretty-print it.

WHY block-anchor content MUST NOT receive the blank-line prepend (the critical
`no-leading-\\n` rule): the legacy heading-anchor path prepends `\\n` to
`placement="after"` content so there is a visual blank line between the heading
text and the first block line. For a table insertion this is catastrophic: the
blank line lands between the separator row (`| --- | --- |`) and the first data
row, which breaks the Markdown table — parsers and Obsidian both require the
data rows to immediately follow the separator with no intervening blank line.
The block-anchor branch therefore skips the `\\n` prepend entirely. Heading
anchors with `placement="after"` retain the legacy prepend unchanged.

WHY the routing condition is `resolved_anchor["type"] != "block"` rather than
inspecting `output_format.structure` or `order`: the `resolved_anchor` block is
the Phase 4 interpreter's authoritative decision about what kind of anchor was
found. Routing on its `type` field is the single source of truth — the same
condition that triggered block-anchor resolution in Phase 4 is what selects
the no-prepend path here, making the two phases symmetric and easy to trace.

## audio_peer: manifest threading + paired source-set deletion (spec 027, v0.35.5)

WHY `audio_peer` flows from confirmed item → manifest entry → move_note action
(not derived at render time): the analyst emits the full vault-relative path
(`"100 Inbox/recording.m4a"`) which the reducer uses ONLY for display
(rsplit to basename → `[[recording.m4a]]` in the Source set line). The parser
then extracts the second wikilink from that rendered line — a basename — and
attaches it to the confirmed item. From there it is carried verbatim into the
manifest entry and into the move_note action, where `_build_move_note_actions`
inbox-joins a bare basename to a full path (same pattern as `source_inbox_item`)
but WITHOUT `_ensure_md_extension` — the `.m4a` extension must be preserved
because it refers to an audio file, not a note.

WHY `_build_delete_source_actions` uses a set for audio peers rather than
taking `moves[0].get("audio_peer")`: the set-based dedup
(`{mn.get("audio_peer") for mn in moves if mn.get("audio_peer")}`) handles the
multi-atomic case (two atomics from one transcript both carry the same peer path
— the set collapses them to one) while also cleanly expressing the empty-set
fail-safe (no peer present → empty set → no audio delete emitted). The
`next(..., None)` alternative would be equivalent for 0/1 peers but silently
takes an arbitrary peer when two move_notes disagree — not the desired semantics.

WHY the audio peer delete is placed INSIDE the `for origin_stem, moves in
moves_by_origin.items():` loop, AFTER the existing transcript delete, and does
NOT have its own keep/gate guards: the `continue` at the top of the loop for
`keep_source_stems` and the gate `len(moves) < expected` ALREADY protect the
entire block. Placing the audio delete inside that block means keep_source=True
suppresses both, gate-not-satisfied defers both, and no-peer produces one delete
— all without duplicating the guard logic.

WHY the reason string is "Audio peer of consumed origin." (not "Voice recording"
or similar): the word "peer" captures the relationship precisely (the audio file
is a companion artifact of the same origin, not itself a source note), and
"consumed origin" aligns with the existing transcript reason string ("Origin
consumed by N atomic(s)"), making the two deletes read as a matched pair in the
instruction set.

## WHY resolve `Conventions` from `--config` and thread markers into `build_actions` (spec 028 T4.1)

WHY: the relationship markers `up::` / `related::` were hardcoded inside
`render_actions`. instruction-render is the render-time entry point that owns
`--config`, so it resolves the active profile's `Conventions` once
(`resolve_conventions(config_path=Path(args.config), profiles_dir=DEFAULT_PROFILES_DIR)`)
and threads `parent_marker` / `peer_marker` into the `build_actions(...)` call.
The library keeps `up::` / `related::` only as backward-compat default parameter
values, so a profile that omits the keys still renders today's output; `miyo`
resolves to exactly those defaults, keeping its rendered actions byte-identical
(CON-2). Per-script resolution (not shared-ctx) is ADR-1; `DEFAULT_PROFILES_DIR`
is caller-supplied from this script's own `SCRIPT_DIR` because the flattened
instance layout breaks deep default path resolution (ADR-2 / CON-4). See
`docs/tomo/scripts/lib/profile_conventions.md` for the resolver rationale.

## WHY emit `tomo.skipped_daily` into instructions.json (coverage-audit reconciliation)

WHY: `filter_missing_daily_notes` legitimately drops `update_tracker` /
`update_log_entry` / `update_log_link` actions whose target daily note does not
exist — Hashi *modifies* daily notes, it never *creates* them (#37/I38). Those
drops were surfaced only in `instructions.md` (human "Skipped" section) and on
stderr, never in the machine `instructions.json`. `instructions-diff` (the Pass-2
coverage audit, conductor step 3e) derives `expected` from the parsed suggestions
— which still count every accepted daily entry — so it saw `expected=N` vs
`actual=N-dropped` and failed with a **false** coverage mismatch. Per the
synthesis-conductor contract a mismatch = STOP, so any run with a missing daily
note stalled the whole Pass 2.

Fix: instruction-render now records the dropped actions under the permissive,
Tomo-owned `instructions.tomo.skipped_daily` block (metadata only —
`action`/`date`/`daily_note_path`, never note content, Constitution L2). Nesting
under `tomo` needs no schema round-trip and Hashi ignores it (its schema leaves
`tomo` open — `additionalProperties` unset). `instructions-diff` reads the block
and subtracts each recorded drop from both `expected["counts"]` and
`expected["expected_daily"]`, then surfaces a non-blocking observation. An
UNrecorded missing daily action still fails — the audit stays honest. This makes
instructions-diff a paired consumer of instruction-render for daily-note skips,
mirroring the delete_source paired-source contract.

## Manifest Entry Carries `attachments[]` (spec 031 T3.5)

WHY the per-item render loop reads `item.get("attachments", [])` and adds it
to the manifest entry dict, rather than deriving it later: the manifest entry
IS the only record `_build_move_asset_actions` (`lib/render_actions.py`) ever
sees per confirmed item — `build_actions()` never re-consults `confirmed`
for attachment data. Until this task, nothing populated `attachments` on a
manifest entry at all, which is why every one of T2.2's fixtures had to be
synthetic; this closes that gap for the first time, end to end.

WHY an instruction-only confirmed item (no `template`) loses its
`attachments` entirely: the per-item loop `continue`s at `:314` — before the
manifest entry is ever built — for any item with no template, since such an
item needs no rendered file. This is a DELIBERATE, PRD-documented limitation
(an item with no note move has nothing for an attachment to travel with,
matching the PRD's own out-of-scope note), pinned by
`test_instruction_only_item_produces_no_manifest_entry_attachments_dropped`
in `tests/test_031_t3_5_manifest_entry_attachments.py` rather than "fixed" —
there is no note move for the attachment to accompany in that case.

## `kind` Stays Out of `instructions.json`'s `tomo.skipped_assets`

WHY `tomo_block["skipped_assets"]`'s per-entry projection carries only
`source`/`destination`/`reason`, omitting the `kind` discriminator that
`lib/render_md.py` uses to pick a rendering-time remedy: nothing reads
`kind` from this JSON today — no Hashi consumer, no Tomo consumer, no test
outside the markdown-rendering path. The Constitution's L2 Performance rule
("trim unused fields aggressively, especially in JSON payloads") is the
concrete reason, not just a style preference: a field with no reader is pure
liability, and this one is also redundant — a `"no_basename"` skip never has
a `destination`, a `"collision"` skip always does, so a future JSON consumer
that needs the distinction can derive it from that alone. The omission is
pinned by a test asserting `kind` is absent from every JSON entry and that
`destination` correctly distinguishes the two cases, specifically so a later
"just add it back" change is a decision made against a red test, not a
change nobody notices.

