# WHY: garden-audit-parser.py

> Rationale for decisions in `tomo/scripts/garden-audit-parser.py`.
> The script is the Pass-2 READER for the garden-audit skill (spec 030).
> Two-artifact split: `--file <md>` carries human DECISIONS, `--wire <json>` carries
> machine STRUCTURE (always read), joined by the F-id in each `### F<id>` heading.
> The result is a `{"confirmed_items": [...]}` envelope printed to STDOUT.

## Version 0.7.0 — dead_link removal UNLINKS instead of deleting (2026-07-22, user-confirmed)

WHY both dead_link → edit_note_text sites (`_confirmed_item_from_wire_finding` and `build_from_wire`)
now emit `replace = dead_target` (the inner text) when the resolved replace target is EMPTY, instead
of `replace = ""`: a dead-link "removal" should DE-LINK — drop the `[[ ]]` brackets but keep the word
(`[[Ohne Tippfehler]]` → `Ohne Tippfehler`) — not delete the link text entirely. A non-empty target
still repoints (`replace = "[[<new>]]"`). The wire convention is UNCHANGED (`decision.replace: ""` =
remove intent); only the parser's TRANSLATION of empty-replace into the action changed, so no schema
change. broken_up removal (`match = "up:: [[X]]"`, `replace = ""`) is intentionally UNCHANGED —
deleting the whole broken `up::` line is correct there. Hashi's edit_note_text executor needs no
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
placeholder means "remove the broken line" (`garden_action=edit_note_text`, `replace=""`,
`match` reconstructed from the WIRE's `up_target`). This keeps the two legitimate resolutions
(repoint vs remove) behind one clean discriminator the user controls by typing or not typing.

## Dead-Link Match Uses `[[target]]` Wrapping (ADR-3)

WHY the parser wraps the wire's bare `dead_target` in `[[ ]]` when building `match`:
`edit_note_text` does a literal string match against the note body, where dead links appear
as `[[Missing Note]]`. The wire's `detail.dead_target` is the bare stem (from graph_audit);
the parser wraps it once when building the confirmed_item. `occurrence="all"` because a dead
wikilink is typically repeated; broken-`up::` removal uses `first` (one `up::` line per note).

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
location (same as add_relationship), separator-safe link removal, delete-line-when-empty,
skip-and-report on no-match. `_up_link_stem` normalizes the wire's up_target defensively
(str | legacy list | dirty list-repr → first bare stem). The wire's `decision.action` value
stays "edit_note_text" — Hashi's editor contract is unchanged; only Tomo's Pass-2 output moved.
The former up_line renderer-parity concern is void — the two-artifact split removed the
structural comment, and now the remove path no longer uses up_line at all (docstring fixed).
