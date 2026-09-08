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

## audio_peer: second-wikilink extraction from the Source set line (spec 027, v0.20.0)

WHY `audio_peer` is extracted by finding the SECOND wikilink in the `**Source:**`
value via `RE_WIKILINK.findall(val)` rather than a dedicated regex or a separate
field: the reducer renders the voice source set as `[[transcript-stem]] + [[audio.m4a]]`
— two wikilinks in one `**Source:** ` line. `RE_WIKILINK` (already defined) is the
canonical wikilink extractor used throughout the parser. `findall` gives all
matches; index 0 is the transcript stem (existing `source_path` behaviour,
unchanged), index 1 is the audio peer basename. A dedicated regex would duplicate
`RE_WIKILINK`'s semantics for no gain.

WHY the audio peer is stored as the BASENAME (e.g. `"recording.m4a"`) and not the
full vault-relative path: the rendered wikilink contains only the basename — the
reducer intentionally strips the directory when building the `[[wikilink]]` (rsplit
path). The parser cannot reconstruct the directory from the suggestions doc alone
(the inbox path is known only at render time, not parse time). The basename is
sufficient because `_build_move_note_actions` inbox-joins it to a full path before
the action is emitted — the same join logic used for `source_inbox_item`.

WHY `audio_peer` must be included in the explicit `confirmed_items` projection dict
(the `{...}` literal at the `confirmed_items.append(...)` call): the parser's
`result` dict is NOT passed through directly — the projection dict enumerates every
field that reaches the output JSON. Any new field on `result` that is omitted from
the projection is silently dropped. `audio_peer` was added to both `result` defaults
and the projection to ensure it survives to `instruction-render.py` as intended.

## Companion merge from two wires — build_from_wire_companion (ADR-026)

WHY the companion merge got a JSON-only path (parser v0.24.0): the markdown companion
defers the primary's force-atomic'd items to a fan doc and merges both by parsing the
fan MARKDOWN (`--fan-resolve-file`). Under Hashi the fan is resolved in the WIRE and the
fan markdown is a minimal envelope, so the markdown merge read nothing and silently
dropped every fan resolution — the primary synthesized alone while its force-atomic'd
items stayed stranded as `pending_fan_resolutions`. `build_from_wire_companion` closes
this by COMBINING the two edited wires and running `build_from_wire` once: the fan's ids
are re-namespaced (`F-` prefix, member_ids fixed) so they never collide with the
primary's; the primary's deferred (suppressed+force_atomic) suggestions are dropped and
replaced by the fan's resolved (un-suppressed) versions, so no `pending_fan_resolutions`
survive; proposed MOCs are concatenated (build_from_wire merges same-name across both);
daily_updates + tag_handler_groups come from the primary (the fan has none). Reusing the
single build_from_wire over the union gets member-stem→id binding and cross-wire MOC
membership for free. The parser fires this only when BOTH `--suggestions-json` and
`--fan-resolve-json` are edited wires; a single edited wire warns and falls back to the
markdown merge (mixed markdown/JSON authority across the two docs is unsupported).
Verified on the real Hashi wires: 22 confirmed (21 atomic + 1 MOC), 0 stranded.

## Attachment round trip — four sites, one delimiter bug (spec 031, T3.4)

WHY `attachments` was added to exactly four sites, matching `audio_peer`'s
established pattern site-for-site: the wire projection at the `build_from_wire`
`confirmed_items.append({...})` literal, the markdown-path defaults dict inside
`parse_section`, a new `elif key == "attachments":` branch in the field-line
dispatch chain (alongside `tags`), and the markdown-path projection at the parser's
own `confirmed_items.append({...})` call. Both projection dicts are the
explicit-enumeration silent-drop trap this file already documents for
`audio_peer`: `result`/`w` are never passed through wholesale, so a field present
on either but absent from its literal projection dict never reaches the output —
with no error. The site count was verified by `rg audio_peer
tomo/scripts/suggestion-parser.py` before implementing (four hits, same four line
numbers a hand-derived audit found), not assumed from the plan — this repo has a
standing, repeatedly-observed failure mode where a plan names one site and the code
has two.

WHY `unresolved_embeds` was NOT added to any of these four sites, despite riding
the same analyst contract as `attachments`: it is diagnostic and one-way (see
`suggestions-reducer.md`'s Should-have note) — there is no user decision to
round-trip, so it never reaches `confirmed_items` and needs no parser site at all.
Adding one would have been scope creep with no consumer.

WHY `_parse_attachments` extracts backtick-DELIMITED segments
(`re.findall(r"`([^`]*)`", value)`) instead of splitting the line on `","`: the
renderer emits `` **Attachments:** `path one`, `path two` `` — the backticks are
the actual field delimiter; the comma between entries is incidental formatting, not
a separator the format is built on. Splitting on `,` first, then stripping
backticks, silently fragments any ORDINARY filename that happens to contain a comma
(e.g. `"Screenshot 2026-01-01 at 10.30.15, edited.png"`) into two bogus paths that
do not exist in the vault. Those bogus paths would still round-trip cleanly through
every existing test — the renderer and parser AGREE on the split, they are just
both wrong together — and would ride the manifest into `move_asset` actions with
nonexistent sources; Hashi skips a source that doesn't exist, so the real
attachment silently never moves and the inbox silently does not empty, which is
precisely the failure this whole spec exists to close. This is why a round-trip or
golden test (render → parse → render, or build_from_wire == markdown-parse)
structurally cannot catch this class of bug: both halves of the contract were
written by the same author from the same assumption, so they are consistent with
each other and both wrong. Only a case derived independently of the renderer's own
output shape — a filename containing the format's incidental separator — breaks the
tie. A literal backtick in a filename is a known, accepted, unfixed limitation
shared with the render side (`suggestions-reducer.py` wraps each path in a single
unescaped backtick pair) — not worth an escaping scheme for a character this
specific to fix a case that has not occurred.

## The suppressed-block Force-Atomic path needs branch (b), not just (c) (#165, v0.26.0)

WHY the section-level Force-Atomic loop consults `resolve_sections_by_stem`
before parking a stem, duplicating logic the daily-driven loop above already
has: without it the loop parked unconditionally, and the resolve subflow it
was parking *for* could never complete.

The three-way lookup documented above the daily-driven loop — (a) primary-doc
section, (b) resolve-doc section, (c) neither, so park — was only ever wired
for stems that come from daily-note log entries. `force_atomic_stems` is built
exclusively from `daily_updates[].log_entries[]`. A suppressed low-worthiness
per-item block (#88) has no daily-note log entry, so it never entered that
loop at all and was handled instead by the section-level loop added for #88,
which had (c) and nothing else.

The result was a livelock. Pass 2 parked the stem and generated a
Force-Atomic Resolve doc; the user approved the proposal in it; the next Pass 2
parked the same stem again and regenerated the same doc. Forever. The approved
proposal parsed perfectly and landed in `resolve_sections_by_stem`, where
nothing read it. Worse, the run reported *"you left its Approve box unticked
in the fan doc"* — pointing the user at the one thing that was already correct.

Found by spec 031's T6.5 live validation, which force-atomic'd a suppressed
fixture to exercise the attachment path through the resolve route.

Two things to preserve if this loop is ever reworked:

- **The (c) branch must stay reachable.** Parking is the correct outcome
  the first time round, when no companion doc exists yet, and also when the
  resolve doc's own Approve box is genuinely unticked. Both cases are covered
  by tests; a fix that promotes unconditionally would consume proposals the
  user has not agreed to.
- **`resolve_promoted_ids` is shared with the daily-driven loop** and must
  stay shared. A stem reachable from both loops would otherwise be promoted
  twice, once per loop.

## _promote_entry omitted two fields of the canonical shape (#161, v0.26.0)

WHY `_promote_entry` carries `audio_peer` and `attachments`: it builds its
entry dict field-by-field rather than copying the section, and both fields
were missing from that list while being present in the canonical
confirmed-item shape assembled for a normally-approved section. A promoted
item therefore lost its audio peer and its attachments on the way to
`instruction-render`.

This was filed as a latent defect and became load-bearing the moment #165 was
fixed: wiring branch (b) into the suppressed-block path without this would
confirm the note, file it to its destination, delete the source — and leave
the image behind in the inbox. That is precisely the residue failure spec 031
exists to eliminate, so the two had to land together.

Note the failure mode is silent rather than loud: `instruction-render` reads
`item.get("attachments", [])`, so a missing key degrades to "no attachments"
rather than raising. That is why the test asserts the key is *present and
empty* for an item with no attachments, not merely that the populated cases
work — an absent key would otherwise pass every positive assertion by
accident.

## One derivation function replaces `_stem_of` (spec 034 T2.6, v0.27.0)

WHY `_stem_of` had to go: it lowercased and stripped every `source_path` /
`source_stem` down to a bare filename before using it as a join key —
`sections_by_stem`, `already_in`, `seen_pending`, the `force_atomic_stems`
match in the daily-log loop, and the final MOC-member → confirmed-id binding
all keyed on that bare, lowercased stem. Two notes with the same filename in
different subfolders collapsed to one key at every one of those sites: one
namesake's Force Atomic tick could silently sweep in or suppress the other,
and a proposed MOC's member binding could resolve to whichever namesake
happened to iterate last. Recursive inbox discovery (spec 034) makes that
collision reachable for the first time — a flat inbox can't have two notes
share a name.

WHY one module-level function, not a `main()`-local closure: `_stem_of` lived
inside `main()` purely as an implementation convenience — it has no closure
state. Hoisting `_item_key_of` to module scope makes both call sites
(the daily-log `source_stem` path and the primary/resolve-doc `source_path`
path) provably the same callable, which is the exact invariant #165's fix
depends on (see the section above): if the two paths ever compute identity
differently again, #165's livelock returns in a form the original,
flat-fixture regression test cannot see. `tests/test_034_t2_6_parser_single_
derivation.py` re-proves #165 against a subfolder source for this reason.

WHY the value is now the path verbatim, not a re-derived stem: ADR-1 (spec
034) defines the item key as the vault-relative path, unmodified — no slug,
no hash, no lowercasing. `_item_key_of` just guards `None`/empty and
delegates to `lib.item_key.derive`. A visible side effect: `pending_
fan_resolutions[].stem` and similar internal fields now carry the source's
original casing instead of a lowercased stem — existing tests asserting a
lowercased literal there were updated to match (they were pinning `_stem_of`'s
incidental lowercasing, not a documented contract).

WHY `_stem_lower` is gone (T2.3b): it was a byte-similar duplicate a few
hundred lines above, serving `build_from_wire`'s ADR-026 JSON-only path,
which joined on `w.get("stem")` — the wire's deliberately-bare display stem
(CON-4). T2.6 had to leave it: collapsing it into `_item_key_of` needed the
wire to carry `item_key` first. T2.3b added that projection
(`suggestions-render._wire_note`), so `build_from_wire` now resolves
`member_ids` through `id_to_item_key` and binds them via `_item_key_of`.
With its last three call sites re-keyed, `_stem_lower` had no caller left and
was deleted rather than kept as a second, divergent derivation — the exact
duplication #165 punished.

WHY `confirmed_items` gained a dedicated `item_key` field instead of
`source_path` being overwritten with the path: `source_path` is display text
(ADR-2) and feeds `render_actions`, which emits `source_stem`/`target_stem`
to Hashi. CON-4 fixes those as bare filenames; overwriting `source_path`
would push a path at that emission boundary and break a cross-repo contract.
A separate field lets identity and display coexist —
`instructions-diff.derive_expected` prefers `item_key` and falls back to
`source_path`, so the markdown path (which mints no `item_key`) is unaffected.

## Daily-Entry Identity Is Recovered From the Doc, Never Carried in the Wire (spec 034 T5.0)

WHY `enrich_daily_updates_with_item_keys` exists, and why it runs on BOTH
parser paths rather than the key simply riding in the wire:

A daily-only item — one whose content is fully captured in a daily note —
produces no per-item section, so the rendered document shows it only as a
daily-note entry with a bare display stem. Pass 2 nonetheless emits a
`delete_source` for it, so its identity has to survive the round trip through
markdown or that delete names a path composed from the inbox root.

The obvious fix — put `source_item_key` in the wire — is not available. The
wire's daily entries are `additionalProperties: false` and the wire is the
Hashi Suggestions Editor's contract, so widening it is a coordinated cross-repo
change (MiYo Constitution: cross-component interface changes are recorded in
Kokoro first). The key is therefore recovered from `suggestions-doc.json`,
which is Tomo-owned, on both paths: `main()` does it after
`parse_daily_updates`, and `_restore_daily_item_keys` does it after
`build_from_wire`. One mechanism, no wire change.

The join is on daily-note stem + bucket + the entry's own discriminating field
(tracker name / log content / link target), not on position: a user who deletes
a line from the document would shift every subsequent entry, and a positional
join would then silently rebind keys to the wrong notes. A discriminator that
maps to more than one distinct key is left UNSET rather than guessed — an
absent key falls back to the reconstruction, which may be wrong; a guessed key
names a specific wrong note, which is worse.

## `item_key` on `skipped_items` (spec 034 T5.0)

WHY the wire path's `skipped_items` gained `item_key` alongside `source_path`:
Pass 2 emits both a `skip` action and, for the "Delete source" disposition, a
`delete_source` for these items. Both addressed the note by display stem, so a
user ticking "Delete source" on a subfolder note asked to delete the inbox
root. `source_path` stays the display stem (ADR-2); `item_key` is the identity
(ADR-1). The markdown path mints no key here for the same reason it mints none
on confirmed items — the document carries no path (T5.1).

## The Markdown Path Recovers Identity From the Doc, Not the Markdown (spec 034)

WHY `item_keys_by_section_id` / `bind_section_item_key` exist, and why they are
not what T5.1 does:

The markdown path — `main()`, what `synthesis-conductor.md:105` invokes in the
normal flow — minted no `item_key`, so every subfolder note carrying a template
was dropped by the Pass-2 `#116` guard before it could be rendered. The premise
recorded for that gap was that the rendered document carries only a bare
display stem and a path cannot be recovered from one.

That premise is true of the markdown FILE and false of the markdown PATH. The
same invocation passes `--suggestions-doc tomo-tmp/suggestions-doc.json`, and
that document carries `sections[].item_key` keyed by the very id the heading
shows:

    markdown:  ### S01 — Bohnen aus Äthiopien      **Source:** [[Bohnen]]
    doc:       {"id": "S01", "stem": "Bohnen",
                "item_key": "100 Inbox/Places/Bohnen.md"}

So the key is joined back on the section id. Nothing about the rendered
document changes, and ADR-2 still holds — `source_path` stays the display stem,
which is what the note title is derived from.

**T5.1 would not have closed this.** T5.1 path-qualifies source links only for
same-filename GROUPS. A subfolder note with a globally unique filename keeps
its bare `[[Bohnen]]` link, so after T5.1 as specified it would still have had
no path to recover. The two tasks are independent: this one is identity, T5.1
is display — the user still cannot tell two `[[Dresden]]` links apart.

Three properties the join has to hold:

- **Both id spaces are registered.** F-41 gives a multi-atomic source several
  headings from one section, and the heading shows the flat `suggestion_id`,
  not the section id. Every atomic of one source shares that source's key, so
  the two id spaces cannot disagree.
- **The stem is cross-checked before binding.** The user owns this document and
  may retype the Source line. An id match alone is not evidence; on a mismatch
  the key is left unset and the item falls back to the reconstruction. A wrong
  key names a specific wrong note, which is worse than a fallback that finds
  nothing. Compared on the basename, so a path-qualified link (T5.1) still
  binds.
- **No doc means no key.** `synthesis-conductor.md:117` runs the parser bare,
  and `_load_json_doc` returns `{}` for anything it cannot read, so the lookup
  is empty and every item behaves exactly as it did before this existed. Note
  that `_default_doc_path` prefers a `suggestions-doc.json` SIBLING of the
  markdown before the cwd-relative fallback, and the pipeline writes the two
  side by side — so the bare invocation usually still finds the doc. Omitting
  the flag is therefore not enough to exercise the no-doc path in a test; the
  markdown has to live somewhere the doc does not.

One asymmetry deliberately left in place: `build_from_wire` falls back to
`w.get("item_key") or stem`, putting a display stem in an identity field when
the wire carries no key, while the markdown path leaves it None. Real documents
always carry the key (the doc schema requires it with `minLength: 1`), so the
two agree in practice; `tests/test_suggestions_wire_golden.py` strips the field
from both sides for its parity compare and says why.

## A Source Link's DISPLAY Text Is Parsed, Not Its Target (spec 034 T5.1)

WHY `_wikilink_display` exists beside `_extract_wikilink`, and why the two
Source-line sites use it: T5.1 path-qualifies a source link when two items in a
run share a filename, so the renderer now emits
`**Source:** [[100 Inbox/Places/Dresden|Dresden]]`. `RE_WIKILINK` captures the
TARGET and drops the alias, which would have put `100 Inbox/Places/Dresden`
into `source_path` and into a log entry's `source_stem`.

WHY that is wrong even though the value would have been more precise:

- `build_from_wire` records the bare `stem` in the same field, with the comment
  that identity lives in `item_key` and this field is display. Taking the
  target on the markdown path makes the two parser paths disagree exactly when
  a collision occurs — the one case they exist to handle — while
  `tests/test_suggestions_wire_golden.py` proves parity on a fixture that has
  no collision and so cannot see it.
- `test_034_t2_8_end_to_end_key_trace.py` asserts no confirmed item's
  `source_path` contains a `/`. That is ADR-2 applied to the parsed output, and
  it was written knowing T5.1 was coming.
- Identity was already solved: `main()` mints `item_key` by joining the
  suggestions doc on the suggestion id. A path in the display field buys
  nothing and costs the invariant.

The Force-Atomic join (`_item_key_of(source_path)` against
`_item_key_of(source_stem)`) keys both sides through the same display value, so
it continues to match. It also continues to collapse two namesakes onto one
join key — unchanged by this task, which is display-only, and noted here so it
is not mistaken for something T5.1 introduced.

An unaliased link is returned verbatim, so every pre-T5.1 document parses
exactly as it did. The site that genuinely wants the path — Force-Atomic
resolution in `inbox-triage.py` — reads the raw link and hands it to
`narrow_candidates`, which strips the alias itself and narrows on the path.
That site is unchanged and was already written for the qualified form.

### The `build_from_wire` Fallback: Reviewed Under T5.1, Deliberately Kept

T5.1 was asked to decide whether to make both paths agree on `None` rather than
inherit the asymmetry recorded above. The decision is to keep it, for reasons
that are about where the defect actually lives, not about effort:

- **The parser is not its origin.** `suggestions-render.py` writes
  `"item_key": section.get("item_key") or section["stem"]` into the wire, for
  "a section minted before item_key became required". So a stem reaches the
  `item_key` field one hop upstream. Returning `None` in `build_from_wire`
  would not remove the violation; it would only move where it becomes visible.
- **`None` and absent are not the same shape.** The markdown path omits the
  field; the wire path would set it to `None`. The golden parity test strips it
  from both sides either way, so the change buys no new assertion.
- **It flips an invariant every Pass-2 consumer relies on.** `item_key` is
  currently always truthy on `confirmed_items[]`, which is what T5.0's
  key-addressed Pass 2 was built against. Making it sometimes falsy inside a
  display task — with no test able to reach the branch through the real
  emitter, because the doc schema requires the key with `minLength: 1` — is how
  a silent regression gets in.

What this needs is a back-compat decision about pre-034 wires, taken where the
fallback is minted, with the Pass-2 consumers swept. That is a task; it is not
a rename in the parser.

## `_merge_proposed_mocs_by_name` Folds Its Key (spec 034 T6.0c)

WHY the by-Name merge compares case-folded: under CON-6 this filesystem is
case-insensitive, so `Travel (MOC)` and `travel (MOC)` are one file. The
2026-06-17 decision that shapes this function — merge on Name only, first
occurrence's parent kept — was written for exact same-name proposals, and left
a case-only pair intact. T6.0 then folded the downstream destination keys
(`_build_create_moc_actions`' `by_dest` and its paired consumer
`resolve_section_names`' `create_moc_by_dest`), so from that point the builder
emitted ONE `create_moc` for a pair the parser still confirmed as two.

WHY that mattered enough to be its own task: `derive_expected`
(`instructions-diff.py`) counts one expected `create_moc` per confirmed item and
does no destination comparison, so it expected two where one was emitted. The
audit printed `create_moc expected=2 actual=1 [DIFF]` plus a `[MISSING]`
per-item row, both of which set `hard_fail`, and `synthesis-conductor.md`
step 3e is STRICT: stop and report the diff verbatim. The user read that as Tomo
drifting from its own instruction set and could not finish the run without
renaming a proposal. Before T6.0 the same input completed and dropped the merged
proposal's children on apply — a change in failure mode, not new data loss, but
one that had to be closed either way.

WHY upstream rather than a subtraction in the audit: folding here removes the
case-only pair before any consumer sees it. `by_dest`'s fold then becomes the
defence-in-depth its own comment already claims to be, and `derive_expected`
counts what is actually emitted without needing a destination comparison of its
own. The alternative — teaching `instructions-diff` to subtract the builder's
merges, mirroring `_subtract_skipped_assets` — would have needed the builder to
report its merges on the wire, owing the usual triad (strip-before-wire, paired
consumer count, schema test) for a divergence that did not have to exist.

WHY `casefold()` and not `.lower()`: `ß` folds to `ss` under `casefold()` and is
left alone by `.lower()`. These are German notes, so `Straße (MOC)` and
`STRASSE (MOC)` are one destination on this filesystem. Same form as T5.2's
`resolve_destination_clashes` and T5.3's `validate_destinations`
`[ref: SDD/CON-6, ADR-4]`.

The key folds; nothing folded is written back. The survivor keeps the spelling
its author wrote in `title`, `destination` and `topic`, so the user always reads
back the name they typed.

### Idempotent Across the Markdown Path's Double Merge

WHY the tests cover the same fold three times: there are three call sites and
the two parser paths do not match. The wire path merges **once**
(`build_from_wire`, after building `wire_mocs`). The markdown path merges
**twice** — per-document inside `parse_proposed_mocs`, then again over
`primary_pmocs + fan_pmocs`. A case-only pair inside one document is collapsed
by the first merge; a third spelling arriving from the fan doc is only visible
to the second. The fold has to hold across both, and the covered path is the one
`derive_expected` consumes: `confirmed_items` from
`tomo-tmp/parsed-suggestions.json`, post-merge. This spec has already been
bitten by the two paths diverging (T5.1), so neither is assumed from the other.

### What the Fold Does NOT Recover: the Losing Spelling's Up-Bullet

WHY this is recorded rather than fixed: T6.0's implementer claimed the upstream
fold would also close the `in_set` bullet loss. Traced at HEAD under T6.0c, it
does not. `resolve_target_moc_paths`' `in_set` is keyed by the EXACT
`_moc_stem(title)` and stays that way by measurement — `b9d34e1` folded it, saw
two `create_moc` in *different* folders collide on one key and last-write-wins
redirect one MOC's bullets into the other's destination, and reverted. So the
merge survivor is indexed under its own spelling only, and a `link_to_moc`
minted from a note whose author wrote the parent as the losing spelling misses
that key. Tier 2 (Kado `search_by_name`) cannot help either: the MOC does not
exist in the vault yet. The action keeps `target_moc_path: null`.

Pinned hard-coded in `tests/test_034_t6_0c_merge_proposed_mocs_case_folded.py`
so the finding is recorded as an assertion rather than an assumption. Closing it
needs the `in_set` collision handled — a different-folder disambiguation, not a
fold — and that is not this task.
