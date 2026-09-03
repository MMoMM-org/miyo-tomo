# WHY: lib/up_parse.py

> Rationale for decisions in `tomo/scripts/lib/up_parse.py`.
> The module is the SSoT for "does this note declare a parent?" — a single parser
> for both `up::` inline (Dataview-style) and `up:` frontmatter values.

## Single Parser for Both `up` Forms (ADR-2, spec 021 T1.1)

WHY: Inline `up::` and frontmatter `up:` coexist in Marcus's vault — some
notes use the Dataview convention, others use plain YAML. Before this module,
two separate regex sites existed (moc-tree-builder.py `UP_RE`, moc-discovery.py
`_UP_MARKER_RE`). They drifted: one handled anchors, the other did not; one
accepted scalars, the other assumed lists. A diverged dual-path meant the same
note could resolve its parent differently depending on which code path was
running.

The single parser, `parse_up_from_content`, establishes one canonical answer
per note, regardless of which caller reads it. Both moc-tree-builder.py and
moc-discovery.py import it once the retrofits land.

## Inline Wins Over Frontmatter (ADR-2)

WHY: Inline `up:: [[X]]` is the Dataview-native, visible-in-reading-mode form;
the user places it deliberately in the note body. Frontmatter `up:` is often
produced by automated writes (Tomo, or an Obsidian template). When both are
present — typically a stale frontmatter value that was never removed after the
user added an inline field — the inline value expresses the user's current
intent. ADR-2 codified this as the canonical priority. The implementation
simply runs the inline regex first and returns early if it matches.

## Frontmatter Parsed Locally — No Extra Kado Round-Trip (C1)

WHY: The SDD constraint C1 required that parsing the `up` relationship must not
cost an additional Kado call. The caller already has the full raw note content
from a single `read_note()` call. `parse_up_from_content` receives that raw
string and splits the YAML frontmatter block inline using `_split_frontmatter`
— the same `---...\n---\n` delimiter pattern used by moc-tree-builder.py's
`parse_frontmatter`. A local copy (rather than an import from
moc-tree-builder.py) keeps this module dependency-free; moc-tree-builder.py is
a sibling script, not a library.

## Returns `{target, source}` Only — Caller Resolves `up_state` (M1)

WHY: `up_state` — "absent" / "valid" / "broken" — requires knowledge of which
notes currently exist in the vault (the MOC stem set). That knowledge lives with
the caller (moc-tree-builder.py `build_entries`, moc-discovery.py
`phase65_resolve_up`), not inside the parser. Embedding the stem-set lookup
here would force every test to fabricate a full vault state and would tangle the
parser's concerns with the discovery context. M1 (SDD spec 021 Phase 1 T1.1)
explicitly states: "parse_up_from_content does NOT emit up_state; the caller
derives it." Keeping the return shape to `{target, source}` preserves that
contract and makes unit-testing the parser trivial.

## `raw_value` is `None` for an inline declaration, deliberately (spec 032, ADR-1)

WHY `UpParseResult.raw_value` stays at its dataclass default (`None`) on the inline-wins return
path (`parse_up_from_content`'s branch 1): a body-resident `up:: [[X]]` declaration has no
frontmatter property to guard — there is nothing for a caller to compare an `expected` value
against before editing. Carrying the property's value through anyway (if the note happened to
ALSO have a stale, unused `up:` frontmatter key) would invite a caller to construct an
`edit_frontmatter` guard for a property the fix never touches — exactly the class of
wrongly-routed edit spec 032 exists to prevent (see `docs/tomo/scripts/garden-audit-parser.md`
ADR-5). `None` here
means "not applicable to this declaration", a distinct meaning from a frontmatter property that
exists and legitimately holds nothing.

ADR-1 (spec 032, confirmed 2026-09-01) is what promoted `raw_value` from an internal detail to a
field on `UpParseResult`: `parse_up_from_content` already read the frontmatter value at `:210`
to resolve `target`, so extending the dataclass kept the single parse as the one place a caller
can obtain both the resolved stem AND the property's observed shape — no second read, no second
parser.

**The empty-property case funnels into the SAME `None`, for a different reason.** An empty or
absent frontmatter property (`up:` with no value, `up: []`, or the key missing entirely) never
reaches the frontmatter return statement at all — `_first_wikilink` returns `None` for it, the
`if target:` guard fails, and execution falls through to the branch-3 "absent" return
(`UpParseResult(target=None, source=None)`), which — like every `UpParseResult` — carries
`raw_value` at its dataclass default. So `raw_value is None` is true for three different
situations (inline declaration, empty property, no property at all) that share nothing except
"no guardable value observed here". A caller cannot distinguish them from `raw_value` alone —
correctly so, since none of them yield a frontmatter-declared parent to route.

**Consequence downstream: test key ABSENCE, never `raw_value is None`.** `moc-tree-builder.py`
persists `raw_value` into the moc-structure cache as `up_value` (`:424`); `garden-audit-parser.py`
reads that field back via `detail.get("up_value", _MISSING)` — a sentinel object, not `None` —
specifically because `up_value: None` is itself a legitimate OBSERVED value once the cache is
fresh (e.g. a frontmatter property that is present but empty). Testing `up_value is None` would
conflate "the cache never wrote this key" (a pre-spec-032 / stale cache — must be withheld,
ADR-3) with "the key is here and the observed value happens to be null" (a normal, routable
case). Only presence-vs-absence of the dict key tells them apart; `_MISSING` is how that
distinction survives the JSON round-trip, where a missing key and an explicit `null` are
otherwise easy to blur.

## Stringified list-repr in `up:` frontmatter (spec 030 FIX 2, 2026-07-21)

WHY `_first_wikilink` yaml.safe_loads a `raw` that starts with `[` but is not a
`[[wikilink]]`: empirically, some moc-structure caches persisted a frontmatter
`up:` list as its Python str repr — e.g. the literal string `"['020 Active MOC']"`
— for a non-trivial fraction of notes (32/339 in the live vault). Treated as a
bare stem, that string became a garbage target AND falsely flagged the note as
`broken_up` (its "parent" resolved to a stem no MOC has). The guard is narrow —
`raw.startswith("[")` and NOT matched by `_WIKILINK_RE` (handled above) — so real
wikilinks and bare stems are untouched; only a bracketed non-wikilink string is
parsed back to a list and recursed on (first non-empty element). A parse failure
falls through to the old bare-stem path, so nothing regresses. This is the ROOT
fix (fresh caches are clean after re-explore); the renderers additionally unwrap
defensively so a still-dirty cache renders clean until re-explored.
