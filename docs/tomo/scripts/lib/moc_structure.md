# WHY: lib/moc_structure.py

> Rationale for decisions in `tomo/scripts/lib/moc_structure.py`.
> The module is a pure, IO-free MOC-structure parser: heading discovery,
> footer-boundary detection, and editable-callout scanning over raw MOC body
> strings (spec 022, T1.1). Updated to v1.1.0 with `parse_moc_inventory` and a
> public `strip_gt_prefix`.

## Why footer_set / editable_set Are Caller-Supplied, Never Hardcoded (spec 022 / #35 / F-55)

WHY: What counts as a "footer" callout (e.g. `video`, `calendar`, `puzzle`, `compass`)
and what counts as an "editable" callout (e.g. `blocks`, `other`, `connect`) is vault
policy, not a property of markdown. Different vaults — and different config generations —
carry different sets. If this library baked those names in, every vault whose footer
callouts differed would silently mis-detect the footer boundary and place notes wrong.
So every entry point (`footer_index`, `parse_headings`, `parse_editable_callouts`,
`parse_moc_inventory`) takes the relevant set as a parameter and the library holds no
default. The one hardcoded list — `FOOTER_CALLOUTS` — stays in `instruction-render.py`
per spec 022 / #35 / F-55, because that is the render-time policy owner; the library
receives it as data, it does not own it. This keeps the structural parser policy-free and
testable in isolation.

## Why the Regexes Mirror instruction-render.py Exactly — and Must Stay in Sync

WHY: `instruction-render.py` does its own callout/heading matching at render time, and this
library does the same matching at build time (via moc-tree-builder) and as a render-time
fallback. If the two disagreed on what a heading or a callout-opening line *is*, a MOC's
inventory built at one stage would not match the structure resolved at another — the
classic producer/consumer drift that no-ops silently. The module's `_CALLOUT_RE` and
`_HEADING_RE` are therefore lifted verbatim from `instruction-render.py` (the header
comment cites the source lines), and the contract is: if the regexes change in one place,
they change in both. There is no shared import for the regex itself because the two scripts
are hyphenated CLI entry points that cannot import each other (see below) — so the sync is
a maintenance discipline, anchored by the comment, not an enforced dependency.

## Why moc-tree-builder and instruction-render Both Import This Lib

WHY: Both `moc-tree-builder.py` (build-time cache producer) and `instruction-render.py`
(render-time consumer / fallback) need to agree on heading/footer/editable-callout
structure. They are hyphenated script filenames (`moc-tree-builder.py`,
`instruction-render.py`) — not valid Python module names — so neither can `import` the
other directly. Extracting the shared, pure parsing logic into an underscore-named module
(`moc_structure`) gives both scripts one importable source of truth. The module is kept
IO-free and Kado-free precisely so it can be imported from either side without dragging in
network or filesystem dependencies, and so it can be unit-tested over plain strings.

## Why parse_moc_inventory Exists — Single-Split Performance (review M5)

WHY: A caller that needs more than one fact about the same MOC body (headings AND editable
callouts AND footer presence) would otherwise call `parse_headings`,
`parse_editable_callouts`, and a footer check separately — each of which calls
`body.splitlines()` again, splitting the same body three times. `parse_moc_inventory`
splits once and computes all three facts in a single pass, returning
`{"headings", "editable_callouts", "has_footer"}`. It is behaviourally equivalent to the
three separate calls (same regexes, same footer cutoff, same `editable_set`-empty
short-circuit) — it exists purely to avoid the redundant splits when building the cache
over many MOCs (spec 022/023 review M5). Callers needing only one fact can still use the
single-purpose functions.

## Why strip_gt_prefix Became Public in v1.1.0

WHY: Stripping the leading blockquote `> ` from a callout line is shared logic that
external callers (and `parse_moc_inventory` itself) need. It was promoted from the private
`_strip_gt_prefix` to the public `strip_gt_prefix`; the private name is kept as a
backwards-compatible alias so pre-1.1.0 callers do not break. The strip handles leading
whitespace then a single `>` so it works on both `> [!note]` and bare `>[!note]` forms.
