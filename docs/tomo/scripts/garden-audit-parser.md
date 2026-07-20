# WHY: garden-audit-parser.py

> Rationale for decisions in `tomo/scripts/garden-audit-parser.py`.
> The script is the Pass-2 rebuild-from-wire for the garden-audit skill (spec 030 Phase 4).
> It mirrors `suggestion-parser.py`'s wire contract (ADR-4 / ADR-026): `load_changed_wire`
> gates on edit, `build_from_wire` reconstructs confirmed-fix Hashi actions from the
> edited wire without re-reading the markdown report.

## JSON-Only Path — No Markdown Re-Parse (ADR-4)

WHY Pass-2 reads only the wire JSON and never re-parses the markdown report: the wire
is the complete, structured serialization of all review decisions (ADR-4). After the user
edits checkboxes and fills `replace` slots in the wire, the wire is the authoritative
source of what was approved. Re-parsing the markdown would require a second round-trip
through the report format (which varies by finding type, tier, and rendering version) and
would produce inconsistencies if the user edited the wire but left the report unchanged.
The ADR-026 digest pattern enforces this: `load_changed_wire` returns `None` for an
unedited wire, which signals the markdown path is authoritative. When the wire is edited,
the JSON-only path is always taken.

## Advisory Findings Never Produce Actions (ADR-5 Semantic Gate)

WHY `build_from_wire` gates on `fixable=False` as an absolute skip before checking
`selected`: `duplicate_stem` and `stale_moc` are advisory — they surface information
for the user to act on manually, not automated Hashi actions. Even if the wire
mistakenly includes a `selected=True` decision on an advisory finding (e.g. from a
schema-invalid user edit), the `fixable=False` gate prevents a broken action from
reaching the instruction set. This matches the producer's intent (`garden-audit.py`
never sets `decision` on advisory findings) and prevents forward-compat hazards if new
advisory checks are added that look fixable to a version-skewed parser.

## Dead-Link Match Uses `[[target]]` Wrapping (ADR-3)

WHY `_dead_link_action` wraps `dead_target` in `[[` and `]]` before passing it as the
`edit_note_text` match: `dead_target` from `kado-graph-audit` is the bare wikilink
stem (e.g. `"Missing Note"`), not the markup. The `edit_note_text` action performs a
literal string match against the note body, where dead links appear as `[[Missing Note]]`.
Passing the bare stem would fail to match (or worse, match unintended occurrences in
regular prose). The wrapper is applied exclusively in the parser — not in the scan or
render — because the wire stores the raw target for use in the `replace` slot too (the
user writes `[[New Name]]`, not `New Name`).

## Dead-Link Occurrence is Always "all" (ADR-3)

WHY `_dead_link_action` always uses `occurrence: "all"` while the `edit_note_text`
default is `first`: a dead wikilink is typically repeated throughout a note (every
occurrence resolves to the same broken target). Replacing only the first would leave
subsequent occurrences broken — the note would still fail a graph-audit re-run for the
same finding. Broken `up::` removal uses `first` (there is at most one `up::` line per
note by design). The asymmetry is intentional and the source is this file's
`_dead_link_action` builder, not the schema default.

## broken_up Splits into Two Action Paths (ADR-3, ADR-5 Rule 7)

WHY `broken_up` findings dispatch on `decision.action` (either `add_relationship` or
`edit_note_text`) rather than having a single fixed action: the user's choice at review
time determines whether to repoint the broken `up::` to a valid MOC (`add_relationship`)
or simply remove the dangling line (`edit_note_text` with `replace=""`). Both are
legitimate resolutions; the user signals their intent in the wire by setting
`decision.action`. The parser does NOT interpret the choice — it executes the action
named. An unknown `action` value is silently skipped (forward-compat: a future action
type should not crash an older parser). The repoint path (`_broken_up_repoint_action`)
uses `add_relationship` because the marker-located replace semantics handle the structural
`up::` line correctly; the `edit_note_text` path would be fragile for repoint because
the match string would have to include the old broken target exactly.

## Filing Actions Warn and Skip on No Candidate MOCs

WHY `_filing_actions` emits `[]` and a stderr warning rather than a broken action when
`candidate_mocs` is empty: a filing action with `target_moc=""` would fail at apply
time (Hashi cannot find or create a MOC with an empty stem). The `orphan_link` scorer
may return an empty candidate list when the note has no thematic neighbours above the
scoring threshold — this is not an error in the parser, it is a genuine "no good MOC
found" signal. Skipping with a warning lets the user know to handle the note manually
rather than generating an action that silently fails on apply.

## Version 0.1.2

WHY: Bumped from 0.1.0 (initial) for the dead-link fix path correction (0.1.1: replace
read from `decision.replace`, not `detail.dead_target`) and the `applied: False` stamp
added to all emitted actions (0.1.2). `update-tomo.sh` skips unchanged versions.
