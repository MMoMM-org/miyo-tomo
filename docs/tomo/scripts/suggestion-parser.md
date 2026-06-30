# WHY: suggestion-parser.py

> Rationale for decisions in `tomo/scripts/suggestion-parser.py`.
> The script parses an approved Tomo suggestions document (the markdown the user
> ticked `[x] Approved` on) and emits `parsed-suggestions.json` — the list of
> confirmed items + per-action decisions that `instruction-render.py` consumes.
> It also reconciles the Force-Atomic-Note (FAN) resolve doc back into the same
> confirmed-items stream.

## N atomic blocks per source — C3 (F-41, XDD 016, ADR-8)

WHY this matters: F-41 makes one inbox item able to produce N atomic notes (one
per conceptual thread). The reducer renders those N atomics as N independent
Accept blocks under a SINGLE `### SNN` source heading (OQ5 → per-item blocks,
source visible in each). The parser is the first downstream consumer that has to
honour that cardinality, and it had two distinct N=1 traps.

WHY an intra-section split, not just a dict→list change: `split_into_sections`
splits the document only on `### SNN` headings. Because the renderer keeps all N
atomic blocks under ONE heading, a naive `parse_section` would walk every line of
that section and let the LAST `**Suggested name:**` / `**Source:**` pair win —
silently dropping atomics 1..N-1. So the fix is two-layered: the parser must
first split a single section's lines into N per-block items (detected by the
repeated `**Source:**` / `**Suggested name:**` boundary markers the renderer
emits), each carrying the shared `source_path`. A single-block section (the
overwhelming common case) yields exactly one item, byte-identical to pre-F-41
output (CON-2 regression gate).

WHY `sections_by_stem` became `dict[str, list[dict]]`: even after the intra-
section split produces N items, the old `sections_by_stem[stem] = item`
assignment overwrote on the second item sharing a stem — the same silent N-1
loss one level up. Keying the map to a LIST and appending (`setdefault(stem,
[]).append(item)`) is the minimal change that preserves all N. `source_stem`
(ADR-4) is the grouping key: every atomic now carries its origin item's stem
explicitly, so the parser can group N atomics back to one source without
inferring it from the note path (which is ambiguous once N>1).

WHY a stem is lowercased before matching (`_stem_of`): `source_path` and
`source_stem` arrive from different producers (renderer-emitted markdown vs
analyst JSON) with inconsistent casing. Normalising to lowercase before using the
stem as a dict key prevents the same origin splitting into two buckets — which
would re-introduce a partial collapse by the back door.

## FAN resolve doc — N entries per source — C4 (F-41, ADR-8, T4.2)

WHY the same dict→list fix applies to the resolve doc: the Force-Atomic-Note
subflow (XDD 012 / F-33) lets the user tick "Force Atomic Note" on a log_entry
the analyst judged sub-worthy. When that source is multi-thread, the resolve doc
now carries N atomic proposals under one heading — exactly the same layout as the
primary suggestions doc. `resolve_sections_by_stem` had the identical scalar-
overwrite trap (`resolve_sections_by_stem[stem] = item`) and gets the identical
fix: `dict[str, list[dict]]`, append, and the Force-Atomic reconciliation loop
iterates the list rather than reading a single `.get(stem)` scalar.

WHY this is a separate collapse point from C3 (not "fixed for free"): the primary
doc and the resolve doc are parsed by two different code paths over two different
input files. Fixing the primary path leaves the FAN path silently dropping
threads 2..N — exactly the bug the C3/C4 split in the survey caught. Both paths
must promote every not-already-confirmed block per stem, so the
confirmed-items stream can contain multiple entries sharing one `source_path`;
downstream (render) keys per-entry, never per-stem.

## Version 0.10.0

WHY: Bumped for the F-41 C3/C4 cardinality changes (intra-section split,
`sections_by_stem` / `resolve_sections_by_stem` → `dict[str, list[dict]]`, FAN
resolve N-entry parsing). `update-tomo.sh` skips unchanged versions silently —
the bump is required for the edit to ship to the Docker instance.

## Pass-1 placement anchor → Pass-2 apply (spec 022/023)

WHY `candidate_mocs: [{path, anchor}]` is emitted per checked MOC: the Pass-1
LLM resolves an insertion anchor for each pre-checked thematic MOC
(`candidate_mocs[].anchor` in the item-result — heading/callout/line + placement
+ new_section). That decision was dropped between Pass-1 and Pass-2, so applied
links silently fell back to instruction-render's `_pick_anchor` heuristic
(FPT → "Core Concepts" instead of "Thinking Frameworks"; Beppu collapsed to a
`[\!blocks]` callout instead of a new `## Japanische Geographie` section). The
parser now re-attaches the anchor so `instruction-render._build_link_to_moc_actions`
→ `_find_candidate(item, parent_stem).get("anchor")` stamps the real decision.

WHY "BOTH" (doc-JSON default + Placement-line override): the rendered
`**Placement:**` line IS the anchor by default, so reverse-parsing it
(`parse_placement_line`) round-trips to the same anchor when unedited and yields
the user's edit when changed. The structured doc-JSON anchor
(`load_doc_anchor_map` over the reducer's `suggestions-doc.json`) is the fallback
when the line is the last-resort "under the note title" form or otherwise
unparseable — it also carries `new_section`/`alt_headings` the line can't fully
express. Override wins; default fills the gap. `_bind_candidate_anchor` is the
single precedence point.

WHY each checked MOC binds to the FOLLOWING Placement line (not a single
per-item line): `moc_link_line` renders checkbox + its own Placement (+ Other
sections) per candidate, so a multi-MOC item has N interleaved blocks. The
parser tracks `pending_moc` and binds the next `**Placement:**` to it; the
`placement` / `other sections in this moc` field keys are skipped so they do not
close the MOC checkbox region (which would misread the next `- [x] [[MOC]]` as a
Decision box).

WHY `--suggestions-doc` defaults to the sibling / `tomo-tmp/suggestions-doc.json`
and fails open: the conductor invokes the parser with only `--file <cache>`; the
structured doc always lives at `tomo-tmp/suggestions-doc.json` relative to the
instance cwd. An absent/unreadable doc → empty map → Placement-line parsing
alone (back-compat), never a crash.

## Version 0.11.0

WHY: Bumped for the spec 022/023 placement-anchor threading (`candidate_mocs`
on confirmed items, `parse_placement_line`, `load_doc_anchor_map`,
`--suggestions-doc`). `update-tomo.sh` skips unchanged versions silently.

## Tag-handler Keep-source extraction (v0.17.0 → label updated v0.19.0)

WHY a second extractor instead of a tuple return: `parse_tag_handler_groups`
already has many callers (production + tests) that depend on its `list[str]`
contract. Rather than churn them all, the section is walked once by a shared
private `_walk_tag_handler_decisions` that yields `(group_id, approved,
keep_source)` per block; the existing `parse_tag_handler_groups` and the new
`parse_tag_handler_keep_source` are thin filters over it. Additive, no contract
break (the project is near-MVP — additive-only on hot paths).

WHY keep_source is reported independent of approval: only an approved group has a
paired `delete_source` to suppress, so a stray keep-source tick on a skipped
group is harmless downstream. The output key `tag_handler_keep_source_group_ids`
feeds instruction-render's delete branch 4.

WHY the label match changed from `"keep origin"` to `"keep source"` (v0.19.0,
spec 027 / ADR-4): the rendered checkbox label was renamed from "Keep origin" to
"Keep source files" for vocabulary consistency. The matcher uses substring match
(`"keep source" in label.lower()`) so "Keep source files" resolves correctly.
Both the atomic and tag-handler parsers now use the same substring.

## Atomic keep_source label update (spec 027 / ADR-4, v0.19.0)

WHY the atomic checkbox matcher (parse_section line ~410) was updated from
`"keep origin" in text_lower` to `"keep source" in text_lower`: the rendered
per-atomic decision block now emits "- [ ] Keep source files" instead of
"- [ ] Keep origin". The old match silently produced keep_source=False for any
checked "Keep source files" box, which would have deleted sources the user
explicitly asked to keep — a silent data-loss bug. The "Delete source" branch
(line ~412) is intentionally unchanged; the skipped-items delete_source flow is
separate and still round-trips.

## Per-item Force Atomic on suppressed light blocks (#88, v0.18.0)

WHY a per-item `force_atomic` parse path: pre-#88 the only Force-Atomic checkbox
was rendered under a daily `log_entry`, and the reconcile gathered force-atomic
stems exclusively from `daily_updates[].log_entries[].force_atomic_note`. A
suppressed low-worthiness item has a `log_link` or no daily at all, so its escape
hatch was unreachable. `parse_section` now reads a section-level "Force Atomic
Note" checkbox into `result["force_atomic"]`.

WHY route section-level force-atomic to `pending_fan_resolutions` (branch c), not
direct promotion (branch a): the light block carries no template / location / MOC
— promoting the parsed section would create an incomplete atomic. Routing to the
resolve subflow rebuilds the full atomic from source, identical to the
daily-log_entry path. The section pass runs AFTER the daily loop so `already_in` /
`seen_pending` de-dup, and the stem is dropped from `skipped_items` (it is being
force-atomic'd, not skipped).
