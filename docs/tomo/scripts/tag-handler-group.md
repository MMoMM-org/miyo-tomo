# WHY: tag-handler-group.py

> Rationale for decisions in `tomo/scripts/tag-handler-group.py`.
> The script groups routing-plan `handled[]` items by (handler, target_path), provides
> a deterministic stable group id, and implements the mechanical field-template compose
> path (no LLM). Called by the tag-handler-interpreter skill before LLM compose.

## Why group by (handler, target_path)

WHY: Multiple inbox items can carry the same tag and therefore route to the same handler.
The one-block-per-group invariant (spec 024 §5 / spec 025 SDD §3) requires that all items
sharing a (handler, target_path) pair produce exactly one composed block for the user to
review. If each item were processed independently, the suggestions doc would have one block
per item — a proposal-first UX antipattern that forces the user to approve N nearly
identical blocks for the same target note. Grouping by (handler, target_path) lets the
interpreter skill either mechanically merge field values or issue a single LLM call over the
whole batch, and the reducer renders one `**Group:**` block per pair.

## Why `output_format` is taken from the FIRST item in the group (CON-1 three-way-drift)

WHY: All items that share a (handler, target_path) key come from the same handler config
file — one JSON file that defines one `output_format`. Therefore every item in a group
has an identical `output_format` value (or all lack it). Taking it from the first item is
safe and avoids a merge operation that would add complexity without value. This matters
because `output_format` is an `additionalProperties:false` field in both
`tag-handler.schema.json` (config side) and `tag-handler-group.schema.json` (group-result
side). CON-1 (spec 025 SDD §Constraints) is the three-way-drift risk: the field must flow
schema → producer → consumer or it is silently stripped before it reaches the reducer
and instruction-render. The stub carries `output_format` from the very first grouping step
so it is never dropped downstream.

## Why `group_id` uses slugified (handler, target_path) — not a hash or counter

WHY: The id is embedded verbatim as a suggestion-block marker in the suggestions doc so
Pass-2 (suggestion-parser) can map an approved group back to its group-result JSON. A
counter (group-0, group-1, …) would change when the routing-plan order changes, breaking
any doc the user partially edited before Pass-2. A hash is opaque and environment-dependent.
A slug of the handler name + target path is stable for the same logical group across runs
and human-readable in the markdown. The `th-<handler_slug>-<target_slug>` prefix avoids
collision with other suggestion-block markers. A null target_path (unresolved group)
slugs to `none` so the id is still well-formed.

## Why the mechanical field-template compose path lives here, not in the skill

WHY: When `compose` is an array of field names (not an LLM directive string), the output
is fully deterministic: for each capture, emit a bullet with its declared field values.
No model invocation is needed. Keeping this path in a testable Python function
(`compose_field_template`) rather than in the skill's markdown prose means it is covered by
unit tests and is not subject to LLM paraphrase or improvisation. The interpreter skill
calls `compose_field_template` for the mechanical path and only falls through to an LLM
call when `compose` is a string directive — the boundary between deterministic and
AI-assisted logic is explicit and enforced by code, not convention.

## Why deterministic sort order (lexical handler + target_path, None last)

WHY: The suggestions doc order must be stable across runs so the user sees the same block
ordering when reviewing a batch that was partially approved in a previous session. An
insertion-order dict (accumulated in handled_list order) would vary by inbox-triage
output, which can change if the vault changes between runs. Lexical sort by handler then
target_path gives a canonical order independent of the triage traversal sequence. None
(unresolved target) sorts after non-None strings within the same handler — consistent with
the expectation that unresolved groups are an edge case that sorts to the end, not mixed
into the middle.

## Why `compose_mode` is derived here rather than decided by the skill

WHY: `compose_mode` is a PROVENANCE field — it records whether a group's
`composed_block` came from an LLM merge call or from a mechanical field join.
Until 2026-09-13 the tag-handler-interpreter skill carried it as a rule for the
model to apply while writing the group file: *"llm_directive if compose was a
string; field_template if compose was an array."*

The 2026-09-12 live run applied that rule backwards. It wrote `field_template`
for a block an LLM had just composed, then noticed and corrected itself in a
second edit. Nothing else would have caught it:

- both values are in the schema's `enum`, so validation passes either way;
- **no production code reads the field** — a repo-wide grep finds it only in
  the two schemas and in test fixtures;
- it never reaches the wire (`suggestions-wire.schema.json` does not declare it
  on `tag_handler_groups[]`, and that node is `additionalProperties: false`).

A provenance record that survives every automated check while asserting the
opposite of what happened is worse than no record: it is the kind of claim
someone later cites as evidence. And the answer was never a judgement call —
`group_handled` already holds `compose` and can see its type.

So the derivation moved into this function and the skill copies the value
verbatim. An unrecognised `compose` shape (absent, or neither string nor list)
omits the key rather than guessing — the schema does not require it, and an
absent provenance record is honest where a fabricated one is not.

Guarded by `TestComposeModeIsDerived` in `tests/test_tag_handler_group.py`,
which asserts both directions. The pair is what catches an inversion; a single
"the two shapes differ" assertion would stay green through exactly the mistake
the live run made.
