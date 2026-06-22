# WHY: lib/supporting_items.py

> Rationale for decisions in `tomo/scripts/lib/supporting_items.py`.
> The module is a pure, IO-free home for parsing and unioning `supporting_items`
> values (spec 022/023 review H5).

## Why This Module Exists — De-duplicating a Drifting Helper (review H5)

WHY: `_union_supporting_items` lived independently in both `instruction-render.py`
(a list-aware superset that also normalises SNN-ID/wikilink tokens) and
`suggestion-parser.py` (a string-only subset). Two functions with the same name,
divergent signatures, and divergent behaviour are a silent-drift hazard — a fix
to one would not reach the other. The single shared implementation now lives
here and both scripts import it (`union_supporting_items`, `parse_supporting_items`),
aliasing to their existing private names so call sites are unchanged.

## Why a Lib Module and Not a Shared Import Between the Scripts

WHY: `instruction-render.py` and `suggestion-parser.py` are hyphenated CLI entry
points — not valid Python module names — so neither can `import` the other. The
only way to share logic is a third, underscore-named module. The module is kept
IO-free so it can be imported from either side and unit-tested over plain values.

## Why the Union Is List-Aware (Returns List or String)

WHY: The two producer flows emit different shapes — the suggestion flow passes a
comma-separated string of SNN IDs (`"S02, S06"`), the moc-proposal flow passes a
list of stems. `union_supporting_items` returns a list when either input is a
list and a comma-joined string otherwise, so each caller gets back the same shape
it put in. The string-only call site in `suggestion-parser` (merging same-name
proposed MOCs) therefore behaves identically to the previous string-only helper.
