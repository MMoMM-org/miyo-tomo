# WHY: instructions-diff.py

> Rationale for decisions in `tomo/scripts/instructions-diff.py`.
> Pass-2 coverage audit: parsed-suggestions.json vs instructions.json — the
> conductor's mandatory step 3e.

## Version 0.7.0 — dedicated garden-audit mode (2026-07-23)

WHY garden-shaped envelopes (confirmed_items carrying `garden_action`) route to
`run_diff_garden` instead of the suggestions math: `derive_expected` branches on
`item.action == "create_moc"` else counts a move_note — garden items carry
`garden_action`, not `action`, so EVERY garden fix was miscounted as an expected
move_note and the audit hard-failed (`move_note expected=N actual=0`) on any
garden-audit doc with confirmed items. Since the conductor's 3e is mandatory
("NEVER skip the coverage audit"), this pre-existing gap blocked every real
garden apply. The garden mode mirrors `render_actions.build_garden_audit_actions`
count math (edit_note_text→1, remove_up_link→1, add_relationship→1, file_note→
link_to_moc + add_relationship) plus path-anchored per-item coverage;
acked_advisories are displayed but expect no actions (they stamp the pushback
ledger, not instructions). Detection is shape-based (all items carry
garden_action) rather than a CLI flag so the conductor invocation stays unchanged.

## Version 0.8.0 — resolve_dead_link in the garden count math (2026-07-24)

WHY `_GARDEN_EXPECTED_KINDS` maps `resolve_dead_link → ("resolve_dead_link",)` (replacing the
`edit_note_text` entry) and `_garden_item_covered` anchors it on path + target: garden-audit's
dead_link fix moved from `edit_note_text` to the semantic `resolve_dead_link` action (see
garden-audit-parser.md 0.11.0), so the coverage audit must expect+match the new kind or every
dead-link fix would read as an uncovered item.

## Version 0.15.0 — the daily-only suppression joins on the note (spec 034 T5.0c)

WHY `derive_expected`'s `confirmed_stems` set and `daily_only_seen` loop were
re-keyed onto the note's identity: this module is the paired consumer of
`render_actions._build_delete_source_actions`, and T5.0b re-keyed that emitter's
six delete-bookkeeping collections onto the resolved vault-relative path
(ADR-1). The audit kept the removed shape — bare filename stems — so once
recursive discovery (Phase 3) let two inbox notes share a filename, the two
modules disagreed by one on two of T5.0b's four cases (two daily-only
namesakes; one confirmed plus one daily-only). Nothing was misdeleted and
nothing was missed: the instruction set was right and only the expectation was
stale. But `derive_expected` feeds `delete_source coverage: expected=N
actual=M`, which is the artefact the user reads to judge whether Pass 2 did the
right thing, so a correct run reported `[DIFF]`.

The stale `NOTE` that used to head that block deferred the work "until T2.3b",
which had already landed (`phase-2.md:153`) — a comment deferring to a closed
task reads as a live justification, which is why the collapse survived T2.3b's
own sweep.

### Why `_origin_key` Was Not Copied Across

`render_actions._origin_key` is not importable as the answer here, and copying
its shape mechanically breaks the mixed input. The emitter always holds
`inbox_path`, so it resolves EVERY key to one canonical spelling
(`resolve_source_path`) before comparing, and plain equality is then correct.
This module has no `inbox_path` — it reads only the parsed suggestions — so its
two sides can legitimately carry the same note in two spellings: a confirmed
item's full `item_key`, and a daily entry that fell back to its bare
`source_stem` because `enrich_daily_updates_with_item_keys` found the
discriminator ambiguous and declined to guess. Under set equality those two
split, the audit expects a deletion the emitter does not make, and the fix
would have moved the false `[DIFF]` rather than removed it — the direction that
bites hardest, because a note at the inbox ROOT is the common case.

`_same_note_as_any` is therefore `_keys_match` applied in BOTH directions.
`_keys_match` already encodes exactly the tolerance needed — a key may carry
one extra leading segment where the other was never inbox-joined — but it was
written for the move_note join, where the expected side is known to be the
unqualified one. Here either side may be, so the direction cannot be assumed.
The tolerance stays narrow in the way that matters: two qualified keys in
different inbox subfolders share no path suffix and remain distinct, which is
the collapse the task existed to remove. It remains deliberately tolerant for a
multi-segment `source_stem`, which ADR-2 says cannot occur — `source_stem` is
display text, a bare filename.

### The Appended Value Stays a Bare Stem

`expected_deletions` holds display stems, not keys, and the daily-only branch
still appends one — deliberately, not by omission. Only its LENGTH reaches the
coverage line, but source 4 (tag-handler groups) dedups against
`set(expected_deletions)` by comparing `_stem(source_path)`. Appending a full
path there would silently stop that dedup from matching a daily-only entry.
Sources 1, 3 and 4 all append stems; the collections that JOIN are keyed on
identity, the list that is merely counted is not. That split is the same one
source 3 (`paired_origins_seen`) already made.

## Guard-Withheld Moves Are Not Coverage Gaps (spec 034 T5.3)

`_subtract_destination_clashes` removes, from the expected tallies, the moves
the Pass-2 destination guard withheld and the paired deletes it withdrew with
them. Without it the audit reported `RESULT: FAIL — count or coverage mismatch`
on a **correct** instruction set — `move_note 2 → 0`, `delete_source 2 → 0`,
`file=[MISSING]` on both items — and `synthesis-conductor.md` step 3e makes a
mismatch fatal, so a destination clash would have halted the run with a message
blaming Tomo for drift rather than naming the clash.

Two details the shape does not make obvious:

- The move join is `_keys_match`, not set membership. A clash entry's
  `source_inbox_item` is the inbox-joined path a rendered action carries, while
  `by_item`'s key comes straight from `confirmed_items` and is never
  inbox-prefixed. This is the same asymmetry `_same_note_as_any` exists for.
- Deletions are matched by the raw path first, the bare stem second, because
  `derive_expected` appends an audio peer under its full path and an origin
  under its stem. Matching on one alone leaves the other counted.

The note counts moves and withdrawn deletes separately rather than implying one
delete per move — a kept-source item has none — which is only accurate because
`withdrawn_deletes` itself names real removals.

The withheld count is emitted as an observation naming the `Not filed` section
of `instructions.md`, so the audit points at the real report instead of
restating a number. See `docs/tomo/scripts/lib/render_actions.md`, "The Pass-2
Destination Guard".
