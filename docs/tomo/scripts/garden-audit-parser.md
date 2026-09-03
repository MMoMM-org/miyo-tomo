# WHY: garden-audit-parser.py

> Rationale for decisions in `tomo/scripts/garden-audit-parser.py`.
> The script is the Pass-2 READER for the garden-audit skill (spec 030).
> Two-artifact split: `--file <md>` carries human DECISIONS, `--wire <json>` carries
> machine STRUCTURE (always read), joined by the F-id in each `### F<id>` heading.
> The result is a `{"confirmed_items": [...]}` envelope printed to STDOUT.

## Version 0.14.0 — broken_up routes by declaration site, never falls back (spec 032, 2026-09-02)

WHY `_route_broken_up` exists as a discrete gate ahead of the existing repoint/remove branching
instead of the parser simply always emitting `add_relationship`/`remove_up_link`: those two actions
are body-oriented — Hashi's executor for both locates the fix by regex-scanning the note's `up::`
line. When a note's parent is declared in a **frontmatter property** instead, there is no such line
to find. Before this spec, a property-declared broken parent still routed to one of those two
actions, and the result was invisible-bad: `remove_up_link` finds no `up::` line and reports "nothing
to remove" — **silent success** on a fix that never happened. `add_relationship` hits Hashi's
`addRelationship.ts:21,70` guard and returns `failed` with "Marker not found" — at least loud, but
still the wrong action kind sent for the wrong declaration site. Verified live: of 29 `broken_up`
findings in `moc-structure-cache.yaml` (346 entries), 1 is frontmatter-sourced and was, before this
fix, hitting exactly this defect on a real note
(`Atlas/202 Notes/Aristotle and Metaphor - Seeing the similarity between things..md` →
`Philosophy MOC (kit)`).

`_route_broken_up` reads `detail.up_source` (populated by `lib/up_parse.py` → `moc-tree-builder.py` →
the moc-structure cache) and returns one of three garden_actions: `"frontmatter"` → `edit_frontmatter`
(new, spec 032); `"inline"` → `remove_up_link` / `add_relationship` (unchanged, pre-032 behaviour);
anything else (missing/unknown) is **withheld**, never guessed — appended to `unroutable` with a
reason (`"stale-cache"` when `up_value` was never observed at all, `"unsupported-shape"` for a
map-shaped `up_value` with no defined transform, `"no-declaration-site"` for the — believed
unreachable in practice — case of a broken finding with neither declaration site set).

**WHY the fallback is forbidden (ADR-5), not merely avoided as a nicety.** The SDD states the
reasoning directly: *"that fallback is not a degradation, it is a reproduction of the exact defect
this spec exists to remove. A withheld finding is visible and re-runnable after `/explore-vault`; a
wrongly-routed one is invisible and reports success."* The whole point of this spec is that Tomo
already has the data (`up_source`) to know which action is safe and chose not to use it. Falling back
to a body-oriented action when routing data is missing (e.g. an unrefreshed cache) would silently
reintroduce the identical failure mode under a different trigger — "the cache is stale" instead of
"the parser never checked" — and a user reading a report that claims success has no reason to
suspect anything is wrong. A withheld finding, by contrast, is visible in the report (see
`_render_withheld_block` / `_broken_up_withhold_reason` in `garden-audit-render.py`) and self-heals:
running `/explore-vault` populates `up_value` in the cache, and the very next `/garden-audit` run
routes correctly. This is why `_route_broken_up`'s three failure branches all end in `unroutable.append`
+ `return None`, never in a guessed action.

**Trap worth recording — `_up_link_stem` normalises, `up_value` must not.** `_up_link_stem` (used by
the `remove_up_link` branch) calls `unwrap_list_repr` on `up_target` to defensively unbox a dirty
cache's stringified list-repr before extracting the bare stem — correct there, because `up_target` is
only ever used as a **display/removal key**, never round-tripped back to Hashi as a guard value. The
same normalisation must **never** touch `up_value` on the `edit_frontmatter` path: `up_value` becomes
the wire `expected` guard (see `render_actions._construct_edit_frontmatter_fields`), and Hashi compares
it **deep-equal against the note's actual frontmatter**. If the parser silently reshaped a dirty
list-repr into a clean list before sending it as `expected`, Hashi's guard would compare a normalised
value against the note's actual (unnormalised) frontmatter and fail the write on every apply — the fix
would never land, and the failure would look like a vault-changed-since-report race rather than what it
actually is (a parser-side reshape of the guard value). The reason this is easy to get wrong silently:
`unwrap_list_repr` passes a real list straight through unchanged, so every normal test fixture — and
every healthy note — stays green either way. Only a dirty list-repr value flowing through the
`edit_frontmatter` path would expose the mistake, and that shape is rare enough that a superficial test
pass would not catch it. Pinned by the spec 032 test suite's routing tests, which assert `up_value` is
carried through `_confirmed_item_from_wire_finding` / `build_from_wire` byte-for-byte.

## Version 0.7.0 — dead_link removal UNLINKS instead of deleting (2026-07-22, user-confirmed)

WHY both dead_link → edit_note_text sites (`_confirmed_item_from_wire_finding` and `build_from_wire`)
now emit `replace = dead_target` (the inner text) when the resolved replace target is EMPTY, instead
of `replace = ""`: a dead-link "removal" should DE-LINK — drop the `[[ ]]` brackets but keep the word
(`[[Ohne Tippfehler]]` → `Ohne Tippfehler`) — not delete the link text entirely. A non-empty target
still repoints (`replace = "[[<new>]]"`). The wire convention is UNCHANGED (`decision.replace: ""` =
remove intent); only the parser's TRANSLATION of empty-replace into the action changed, so no schema
change. (broken_up removal's whole-line claim here is SUPERSEDED — see 0.9.0 below: it became the
link-only `remove_up_link` action on 2026-07-23.) Hashi's edit_note_text executor needs no
change (still a literal match/replace). Pinned by `test_garden_audit_parser.py`
(`test_dead_link_empty_replace_unlinks_keeps_text`, `test_dead_link_match_from_wire_empty_replace`,
`test_dead_link_typed_replace_repoints`) + the broken_up-removal guard
(`test_broken_up_removal_match_from_wire_up_target`).

## Version 0.6.0 — Tomo-Editor JSON channel (spec 030 extension, 2026-07-22)

WHY `_is_wire_edited` now uses `compute_garden_audit_digest` and additionally returns True when the
wire carries top-level `approved: true` (via `_wire_is_json_approved`): the digest reflects only user
apply-decisions (`selected`/`repoint`/`replace`/`file_under`), so `--suggest` writing display-only
`candidates` never routes to the JSON path falsely. The approved gate forces the JSON path
REGARDLESS of digest — the edge case is a user who approves via the editor but changed NO decision
(all defaults): the digest still matches emit, and without the override Pass-2 would route to
`build_from_report` and read an empty markdown, applying nothing. `approved: true` makes the JSON
channel authoritative so an all-default editor approval still applies the scan-candidate fixes.

WHY `build_from_wire`'s `file_note` branch now reads `decision.file_under` with precedence
`file_under > candidate_mocs[0] > skip` (mirroring the markdown `build_from_report` path): the
Tomo-Editor commits the filing target into `file_under`, and an explicit value must always win. The
wire's `decision.candidates` is DISPLAY-ONLY and is NEVER auto-applied — only the value the editor
commits into `file_under`/`repoint`/`replace` is read. `_wikilink_target` normalises `[[X]]`/`X`.

## Parser Emits confirmed_items, Not Actions (spec 030 SDD)

WHY the parser is a pure reader that emits SEMANTIC items (`garden_check` /
`garden_action`) instead of pre-built Hashi actions: the SDD mandates "no new apply
path… mirror /moc-propose". The suggestions and moc-proposal flows both hand
`confirmed_items` to `instruction-render.py`, which assembles actions via
`render_actions`. Garden-audit does the same. The action assembler lives in
`render_actions.build_garden_audit_actions`, which reuses the shared
`_build_edit_note_text_actions` builder (previously dead code) — wiring the fix
primitive into the one live builder path. An earlier design where the parser emitted
`{"actions": [...]}` directly was end-to-end broken: `instruction-render` reads
`confirmed_items`, so the actions were silently dropped and nothing rendered.

## Two Artifacts, Joined by F-id (spec 030)

WHY the parser reads BOTH `--file` (markdown) and `--wire` (JSON) and joins them by the
F-id in each `### F<id>` heading, rather than reading everything from one artifact: the
user approved a cleaner split where the markdown report is PURELY human-facing (Apply ticks
+ typed `Repoint to:` / `Replace with:` values) and the wire — the machine artifact that is
always generated and cached — is the STRUCTURE source (id, check, tier, target.path,
detail with dead_target / up_target / candidate_mocs). `build_from_report(md, wire)` parses
the markdown into a per-F-id decision map (`parse_decision_map`), then for each fixable wire
finding whose id is present-and-ticked in the map, builds the confirmed_item from the WIRE's
structure + the markdown's typed decision. This removed the fragile round-trip HTML comment:
the report no longer carries `<!-- garden-audit ... -->` at all, so there is no invisible
machine payload to keep in parity with the parser — the wire IS the machine payload.

## `--wire` is REQUIRED; wire ALWAYS read for structure

WHY `--wire` is required (not optional) and read regardless of digest: structure now always
comes from the wire, so without it there is nothing to build. `main()` loads the raw wire
ONCE (`_load_raw_wire`, digest-independent) and then decides the path with `_is_wire_edited`
on that already-loaded dict — NO second file read. This is deliberate: on the Docker
bind-mount the file could change between two reads, so routing on read-1's dict while building
from read-2's would be a TOCTOU bug (and a redundant parse). `_is_wire_edited` returns True for
an EDITED wire (schema-v1 + digest mismatch) → the Hashi-authored path `build_from_wire` (wire
fully authoritative, markdown decisions ignored); an unedited / unknown-schema wire supplies
structure to the markdown decisions → `build_from_report`. A missing/unreadable wire degrades
gracefully to empty `confirmed_items` (warn to stderr, never crash) — Tomo still does not assume
Hashi is installed, it just needs the always-generated wire sibling the renderer produces.
(`load_changed_wire` is kept as a thin path-loading wrapper over `_is_wire_edited` for callers
that only have a path, but `main()` no longer uses it.)

## Advisory / Unticked / Missing-id → Skipped

WHY three independent skip gates in `build_from_report`: (1) `fixable=False` wire findings
(duplicate_stem, stale_moc) never produce a fix — advisory only; (2) a finding whose F-id is
absent from the markdown decision map (no `### F<id>` heading — e.g. the user deleted the
block) is skipped, since the join key is missing; (3) a present-but-unticked `- [ ] Apply`
box means the user opted out. Only fixable + present + ticked findings become confirmed_items.

## Regexes Use re.MULTILINE

WHY `RE_APPLY_*` / `RE_REPLACE_FIELD` / `RE_REPOINT_FIELD` compile with `re.MULTILINE`:
they are `.search()`-ed against a whole multi-line finding block. Without `re.MULTILINE`
the `^` anchor only matches the start of the entire block string, so every field line
except the first would be missed (observed: repoint/replace values silently read as empty,
collapsing every fix to a removal).

## broken_up Discriminator: Repoint Value Present ⇒ add_relationship

WHY every `broken_up` block renders a `**Repoint to:**` field, and the parser branches on
whether the user typed a target: a non-empty Repoint value means "repair the `up::` to this
MOC" (`garden_action=add_relationship`, `up_line` built from it); an empty / untouched `[[]]`
placeholder means "remove only the broken link" (`garden_action=remove_up_link`, `link` =
bare broken stem from the WIRE's `up_target` — see 0.9.0/0.10.0 below; the earlier whole-line
`edit_note_text` removal is superseded). This keeps the two legitimate resolutions (repoint vs
remove) behind one clean discriminator the user controls by typing or not typing.

## Dead-Link Resolution (SUPERSEDED → resolve_dead_link, see 0.11.0)

WHY this section is historical: the parser USED to wrap the wire's bare `dead_target` in `[[ ]]`
to build a literal `edit_note_text` match. That silently no-opped on ALIASED links
(`[[target|display]]`) — a real bug hit in the first live round. As of 0.11.0 (2026-07-24) the
parser emits the semantic `resolve_dead_link` action carrying the BARE target + `replace`; Hashi
matches all forms (bare / aliased / embed) with body access. No literal match, no occurrence field
in the emitted item anymore.

## Filing Warns and Skips on No Candidate MOC

WHY a filing item is skipped (with a stderr warning) when no `target_moc` is present: a
filing action with an empty MOC stem would fail at apply time (Hashi cannot resolve or create
a MOC with an empty stem). An empty candidate list is a genuine "no good MOC found" signal,
not a parser error — the user handles the note manually.

## Suggest opt-in + ticked pick, typed-wins precedence (Phase 7, T7.3)

WHY `parse_decision_map` now also reads a `suggest` flag and a ticked `- [x] [[Candidate]]`
pick sub-checkbox: the two-artifact split means the markdown is the decision surface, and the
Suggest opt-in + the user's pick are decisions. `suggest` tells `--suggest` which findings to
enrich (it is read here so there is one decision-parsing home). The ticked pick becomes the
Replace/Repoint value.

WHY the precedence is typed field > ticked pick > empty (D4), resolved INSIDE `parse_decision_map`
rather than downstream: `_confirmed_item_from_wire_finding` already consumes the resolved
`repoint`/`replace` value and feeds it into the garden_action discrimination (non-empty →
add_relationship/replace, empty → removal). By resolving typed-or-pick in the decision map, that
downstream builder needs NO change — a ticked pick flows through exactly like a typed value. The
typed value winning matters because a user who both ticked a suggestion AND then typed a different
target clearly meant the typed one; the pick is only a convenience default.

## file_note target precedence: File-under > pick > scan candidate > skip (Change 2)

WHY the unparented/orphan `file_note` branch resolves `target_moc` as typed **File under:** >
ticked pick > scan `candidate_mocs[0]` > none (skip + warn), rather than always taking the scan
candidate: the scan often finds no candidate (or a weak/wrong one), so the user must be able to
override. `parse_decision_map` folds the typed-`File under:`-value and the ticked-pick into one
`file_under` field (typed wins over pick, same as repoint/replace), so the builder just checks
`decision.file_under` first, then the scan candidate, then skips. When the user chose a MOC by stem,
`target_moc_path` is left None — the resolved stem is what `build_garden_audit_actions` threads into
BOTH the `link_to_moc` bullet and the `up:: [[MOC]]` line, and instruction-render's
`resolve_target_moc_paths` fills the path via Kado. Skipping (not filing with an empty MOC) matches
the pre-existing "no candidate → skip" contract — a file_note with `target_moc=""` would fail at
apply time.

## Version 0.5.0

WHY: 0.5.0 (spec 030 structure suggestions) — `parse_decision_map` reads a `**File under:**` field
(`RE_FILEUNDER_FIELD`) into `file_under` (typed > pick precedence); the `file_note` branch resolves
`target_moc` as File-under > pick > scan candidate > skip, so a user-chosen MOC threads into both the
link_to_moc bullet and the up:: line. 0.4.1 (code-quality S1) — `parse_decision_map` uses
`RE_PICK_TICKED.findall` and warns to stderr when >1 pick sub-checkbox is ticked ("Pick one"), still
using the first.

## Version 0.4.0

WHY: 0.4.0 (spec 030 Phase 7 T7.3) — `parse_decision_map` reads the `- [x] Suggest targets`
opt-in (`suggest`) and a ticked `- [x] [[Candidate]] (score)` pick sub-checkbox, resolving
`repoint`/`replace` with D4 precedence (typed field > ticked pick > empty removal). No change to
`_confirmed_item_from_wire_finding` — the pick flows through as a resolved value.

## Version 0.3.1

WHY: 0.3.1 (code-quality review) — `main()` now routes on `_is_wire_edited(raw_wire)` (the
already-loaded dict) instead of re-opening the path via `load_changed_wire` — removes a
TOCTOU window + redundant parse. `load_changed_wire`'s warning strings updated ("routing to
build_from_report" not "using markdown"). 0.3.0 (spec 030 two-artifact split) — `build_from_markdown` replaced by
`build_from_report(md, wire)`: markdown = decisions, wire = structure (always read),
joined by F-id. The `<!-- garden-audit ... -->` round-trip comment is gone; structure is
sourced from the wire. `--wire` is now REQUIRED; a missing wire degrades to empty
confirmed_items. Earlier: 0.2.1 code-quality review (shared `up_line`/`bare_stem`,
`RE_GA_ATTR`→`RE_GA_COMMENT_ATTR`); 0.2.0 vertical fix (parser → confirmed_items,
action assembly in `render_actions.build_garden_audit_actions`). `update-tomo.sh` skips
unchanged versions.

## Version 0.8.0 — advisory ack channel + --stamp-pushback (2026-07-23)

WHY advisories now produce `acked_advisories` ({id, path, check}) from BOTH channels (markdown
`- [x] Acknowledge` tick in build_from_report, finding-level `ack: true` in build_from_wire):
spec 030 Feature 5a — one review buys a rest window. The ack flag is INCLUDED in emit_digest
(render_md projection) because acknowledging IS a user decision: an editor that ticks ack on an
otherwise-untouched wire must flip the digest, or Pass-2 would route to the markdown path and
drop the ack. Envelope key is additive — all downstream consumers read `confirmed_items` via
`.get()` and ignore unknown keys.

WHY stamping is behind `--stamp-pushback` instead of always-on: the parser is also invoked on
read-only paths (tests, diffs, dry parses) — writing a ledger there would push back advisories
the user never applied. Only the synthesis-conductor's Pass-2 apply invocation passes the flag.
Window days come from `--exclusions` settings (`advisory_pushback_days`, default 30); the ledger
write itself is `garden_exclusions.stamp_pushback` (upsert + prune — single owner of the format).

## Version 0.9.0 — broken_up empty=remove is link-only (remove_up_link, 2026-07-23)

WHY both broken_up remove branches now emit `{garden_action: "remove_up_link", link: <stem>}`
instead of the whole-line `edit_note_text` match/replace triple: the constructed match
(`up_line(up_target)` → `up:: [[Broken]]`) never literal-matched a real MULTI-link up:: line
(`up:: [[A]], [[Broken]]`) — Hashi's executor found no match and the fix silently no-opped
(Hashi handoff 2026-07-23). And even with matching, whole-line removal would have deleted
healthy links sharing the line. User decision (Tomo-Editor QA): remove ONLY the broken link;
the line is dropped only when it was the last one. The parser cannot construct that edit
literally (it never sees the note body) — so the semantic is delegated to Hashi via the new
`remove_up_link` action (path + bare link stem), executed with body access: marker-regex line
location (same as add_relationship), separator-safe link removal, and — CRITICAL, Hashi's exact
question — the up:: FIELD is PRESERVED when the removed link was the last one (`up:: [[X]]` →
`up:: ` emptied, never the line deleted; up:: is a required structural field and the emptied note
correctly resurfaces as unparented), skip-and-report on no-match. `_up_link_stem` normalizes the wire's up_target defensively
(str | legacy list | dirty list-repr → first bare stem). The wire's `decision.action` value
stays "edit_note_text" — Hashi's editor contract is unchanged; only Tomo's Pass-2 output moved.
The former up_line renderer-parity concern is void — the two-artifact split removed the
structural comment, and now the remove path no longer uses up_line at all (docstring fixed).

## Version 0.10.0 — advisory pushback is auto-on-approve (2026-07-23, same-day revision)

WHY `acked_advisories` now collects EVERY advisory in the doc instead of only ticked/`ack:true`
ones (0.8.0's per-finding channel, reverted the same day): the user rejected per-finding
acknowledgement. Approving a report = "I've seen these" for ALL its advisories. Safe because
triage only routes APPROVED garden-audit docs to Pass-2, and `--stamp-pushback` is passed only
by the conductor's apply invocation — so "all advisories" only ever get stamped post-approval.
`RE_ACK_TICKED` and the markdown/wire ack reads are gone; `_acked_advisory` and the ledger write
path are unchanged. A zero-fixable report the user approves just to dismiss advisories still
stamps them (the apply path runs on approval regardless of fixable count).

## Version 0.11.0 — dead_link → resolve_dead_link (alias-aware, 2026-07-24)

WHY both dead_link branches now emit `{garden_action:"resolve_dead_link", target, replace}` instead
of `edit_note_text` with a literal `match="[[dead_target]]"`: the first live garden-audit round hit a
note whose dead link was ALIASED — `[[X/…/SM - Passages Saved From iOS|SM - Passages Saved From iOS]]`
— and the bare `[[target]]` match is not a substring of the aliased form, so Hashi's literal
edit_note_text found no match → the unlink SILENTLY no-opped (same literal-match fragility class as the
broken_up multi-link bug). Even on a match, unlinking a path-based link would leave the ugly full path
as text instead of the display. The parser never sees the note body / display text, so — exactly like
`remove_up_link` — the resolution is delegated to Hashi: the action carries the BARE target + a
normalised `replace` (`''` = unlink, `'[[New]]'` = repoint), and Hashi handles bare / aliased / embed
forms, keeps the display on unlink, and preserves it on repoint. Both channels normalise `replace` via
`_wikilink_target` so report-path (bare stem) and wire-path (`[[New]]`) emit an identical shape.
`edit_note_text` now has no garden emitter (broken_up remove → remove_up_link, dead_link →
resolve_dead_link); it stays in the schema for Hashi's shipped surface. Pinned by the updated
`TestBuildFromWireDeadLink` / `TestBuildFromReport` dead_link tests + the hashi-example.
