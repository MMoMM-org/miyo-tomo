# WHY: scripts/tag-handler-resolve.py

> Rationale for decisions in `tomo/scripts/tag-handler-resolve.py`.
> Deterministic tag-handler resolver: loads the registry, matches inbox item tags
> against registered handlers, binds capture segments, pulls frontmatter fields,
> and resolves the target note path. No LLM, no network beyond the registry read.
> Spec: docs/XDD/specs/024-tag-handler-framework/ (requirements.md, solution.md §3–4).

## Why Pure / Deterministic (No LLM, No Network)

WHY: The resolver's job is mechanical matching and binding — it does not require
model judgment. Keeping it pure (no LLM calls, no network calls beyond loading the
local registry JSON files) makes the cold path cheap, fully testable with no mocks,
and safe to call on every new inbox source without worrying about latency or token
cost. The LLM work (composing the merged status update) belongs in the
`tag-handler-interpreter` skill, which is loaded only when a match has already been
found. The resolver is the fast gate; the interpreter is the expensive step.

## Why Schema Validation at Load Time (Not at Match Time)

WHY: A malformed or schema-invalid handler config is detected when the registry is
loaded, not when the first item tries to match it. This makes the failure visible
immediately (a WARNING is logged for each skipped file) rather than silently on the
first matching note. An invalid handler is skipped exactly like a disabled one — the
run continues with the remaining valid handlers (additive-safety, AC-5 from spec 024
requirements). A missing or empty registry directory returns an empty list without
error, so a zero-handler run is byte-identical to today.

## Matching Contract: First-Prefix-Wins, Lexical-by-id Order

WHY: The resolver iterates registered handlers in lexical order by `id` (guaranteed
by `load_registry`). For each handler, it checks whether any of the inbox item's tags
starts with the handler's `tag_prefix`. The first handler whose `tag_prefix` is a
prefix of any tag wins — matching stops there. This deterministic order eliminates
ambiguity when two handler prefixes could both match the same tag (e.g. if someone
registered `MiYo/Tsukai/` and `MiYo/`). Lexical-by-id is predictable and
reproducible without any user-visible configuration knob; a collision is flagged as a
WARNING at load time so the user knows the ordering matters.

## Binding `capture_segments` from the Tag Suffix

WHY: After a prefix match, the resolver strips the prefix from the matched tag and
splits the remaining path by `/`. The declared `capture_segments` list names each
position in order (e.g. `["repo"]` binds the first segment to `vars["repo"]`). This
is a positional, not named, binding — the segment names are the handler author's
declaration, not embedded in the tag itself. Extra suffix segments beyond the declared
list are silently ignored; missing segments produce no binding for that name (the key
is absent from `vars`). The design avoids any tag-format negotiation between the
producer (e.g. Tsukai) and the framework: the handler declares what it cares about.

## Pulling `read_fields` from Frontmatter

WHY: The resolver copies only the explicitly declared `read_fields` from the inbox
item's frontmatter into the resolution output. This keeps the interpreter's view of
the item narrow (only the fields the handler said it needs) and avoids accidentally
forwarding sensitive or irrelevant frontmatter to a compose call. Fields declared in
`read_fields` but absent from the actual frontmatter are silently omitted from
`fields` (no error) — the interpreter and compose directive must handle missing fields
gracefully.

## Target Resolution: `target.map[vars[target.by]]` — Unmapped → null, Not Crash

WHY: The target note path is resolved by looking up `vars[target.by]` in the handler's
`target.map`. If the captured segment value is not in the map (e.g. a new repo that the
user hasn't mapped yet), `target_path` is set to `null` in the resolution output and
surfaced to the interpreter as a "create it first" or "add it to the map" signal. The
resolver does NOT crash, skip the match, or log an error — a partial resolution is
valid. The guard against a null target is in the Pass-1 reducer (FR-11 / AC-4): it
surfaces a warning checkbox rather than emitting an instruction without a target.

## Action Registry v1 Decision: `insert_under_marker` Only

WHY: The v1 action registry ships exactly one action (`insert_under_marker`). The three
others (`route_to_folder`, `link_to_moc`, `enrich_frontmatter`) are declared in the
SDD (§4) so future handler JSON can reference them without a schema change, but the
resolver rejects them at runtime with a clear "not yet implemented" `ValueError`. This
fail-loud behaviour (rather than silently skipping the handler) ensures that a handler
authored for a deferred action does not silently vanish — it surfaces immediately so
the user knows the action is not available yet. Entirely unknown action strings are
rejected with the same mechanism. The registry table in SDD §4 is the single extension
point; adding a new action requires updating the table AND removing it from
`_DEFERRED_ACTIONS` (or adding it as a new shipped action).

## Additive-Safety / AC-5 Byte-Identity Rationale

WHY: AC-5 from spec 024 requirements states that a `/inbox` run with no registered
handlers must be byte-identical to current behaviour. The resolver enforces this at
three levels:

1. **Empty/missing registry dir** — `load_registry` returns `[]` without error.
2. **All handlers disabled or schema-invalid** — same result: `[]`.
3. **No item matches any handler** — `resolve_item` returns `None`.

When triage calls the resolver and gets `None` for every new source, it emits no
`handled[]` key in `routing-plan.json` (an empty array is not emitted — SDD §5
schema-change note). The conductor's interpreter-loading gate checks for the absent or
empty key and skips the interpreter entirely. Net result: zero additional writes, zero
additional LLM calls, zero token cost delta — the run is operationally identical to a
run without the framework code present.
