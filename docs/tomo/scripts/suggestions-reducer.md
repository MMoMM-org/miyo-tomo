# WHY: suggestions-reducer.py

> Rationale for decisions in `tomo/scripts/suggestions-reducer.py`.
> The script reduces per-item result JSONs into a suggestions-doc, and (in
> `--moc-proposal-mode`) renders a DiscoveryReport into a MOC proposal-doc.

## Orphan Overflow Footer + MOC-Uplink Heading (ADR-12, T6.4)

WHY: A whole-vault scan can legitimately surface hundreds of note orphans
(verified real on the live vault — empty `up::` placeholders + notes with no
`up`). moc-discovery caps the rendered set at `orphan_display_cap` and reports
`orphan_overflow`. `_render_orphan_section` renders a footer when `overflow > 0`
so the doc is honest about truncation and points the user at a scoped re-run —
silent truncation would read as "these are all the orphans" when they are not.

`check_mode` (report `mode == "check-moc-uplinks"`) relabels the H1 and the
orphan section as a "MOC Uplink Check" — the same renderer serves both the
notes-discovery proposal and the on-demand MOC-parentage audit, because a
check-mode report is just a DiscoveryReport with no clusters and MOC-kind orphan
suggestions. The cap/overflow live in moc-discovery (config-driven); the reducer
only renders what the report carries (`orphan_overflow`), staying a pure
`(report, config) -> (filename, body)` function with no Kado access (CON-3).

## Orphan Section is Check-Mode-Only (ADR-13 D1, T7.5)

WHY: After ADR-13 D1 the cluster path in moc-discovery no longer populates
`orphan_suggestions` — it always emits `[]`. The reducer gate
`if orphan_suggestions:` (at ~line 707) therefore never fires for cluster-mode
reports, so `## Orphan Notes & MOCs` and its `### Oxx` sub-sections never appear
in a cluster proposal-doc. No change was needed in the reducer itself — the
existing gate is the correct mechanism.

`_render_orphan_section` is check-mode-only as of T7.5. It is NOT removed because
`check-moc-uplinks` reports still carry MOC-orphan suggestions and rely on this
renderer. Any future use case that needs to surface note orphans in a proposal-doc
must explicitly populate `orphan_suggestions` in the DiscoveryReport — the renderer
will pick it up automatically. The renderer stays; only the cluster producer changed.

## N atomic notes per source — C1/C2 (F-41, XDD 016)

WHY: F-41 lets one inbox item emit N `create_atomic_note` actions (one per
conceptual thread — see `docs/tomo/dot_claude/agents/inbox-analyst.md` Step 7.5
and the wire-format ADR-2). The reducer is the first consumer that renders those
atomics for the user, and it had two N=1 traps that silently dropped threads
2..N.

WHY iterate ALL atomics in coexistence enforcement (C1): `_enforce_coexistence`
fetched the atomic action with `next(a for a in actions if kind ==
create_atomic_note)` — only the FIRST. The atomic-vs-`log_entry` coexistence
rules must be evaluated per atomic, so the single-fetch is replaced by iteration
over every `create_atomic_note`. With one atomic this is identical to before
(CON-2); with N it stops discarding the rest.

WHY key section titles per-atomic (C2): the title bookkeeping used
`section_titles[section_id] = title`, a scalar keyed by section. N atomics share
one source section, so the last title overwrote the earlier ones before
`_enrich_proposed_mocs` could use them — the per-atomic MOC enrichment then
operated on the wrong (or a single) title. Keying per-atomic (by index, or a
list) lets all N titles survive into enrichment.

WHY N independent Accept blocks under one source heading, not nested checkboxes
(OQ5): the reducer renders each atomic as its own per-item Accept block with its
own `**Source:** [[stem]]` line and its own `[ ] Approved` toggle, so the user
reviews and approves each thread independently. The per-source `### SNN — title`
heading is emitted by the orchestrator (not the reducer); the per-block
`source_stem` makes a single shared heading acceptable — the user can mentally
group the blocks without visual nesting. Renders stay scannable at the typical
N=2-3 and are designed for N=5 as the realistic upper bound.

## Pass-1 missing-daily-note surfacing — I38 (#58 sibling)

WHY the reducer reaches Kado at all: the reducer was a pure offline reduce over
local `result.json` files. I38 surfaced that an `update_log_entry` /
`update_tracker` / `update_log_link` dated to a daily note the user never
created is unappliable — Hashi MODIFIES daily notes, it does not create them
(see `domain_hashi_modifies_never_creates`; contrast `create_moc` / `move_note`,
which create their targets). PR #58 added the Pass-2 backstop
(`instruction-render.filter_missing_daily_notes`), but that only surfaces the
skip in `instructions.md` — *after* the user already accepted the entry. The
daily-log decision is made in the Pass-1 SUGGESTIONS doc (the
`### [[<date>]]` Daily-Notes-Updates block), so the existence warning belongs
there too. `annotate_daily_note_existence` does one deduplicated Kado read per
unique daily-note path and flags `exists=False`; the heading then renders the
`⚠️ daily note doesn't exist` warning. Symmetric with #58, not a replacement —
#58 stays as the Pass-2 drop.

WHY fail-open: a None client (offline / `--no-kado` / no Kado config) or any
error other than a definitive `KadoNotFoundError` keeps `exists=True`. A false
"missing" warning on a note that actually exists is worse than silence — it
would push the user to recreate a note they already have. A transient Kado
hiccup must never produce that, so only a definitive not-found flags the note.

WHY `daily_note_path` is held in a side map, not on the entry: the output
suggestions-doc schema is `additionalProperties: false` on daily-notes-updates
entries, so the path used for the Kado read cannot live on the entry dict. It is
collected into `daily_path_by_stem` for the duration of the existence check and
discarded — only the already-schema'd `exists` boolean reaches the output.

WHY skip the check in `--fan-resolve`: the Force-Atomic resolve doc wipes
`daily_notes_updates` immediately after, so checking existence there would spend
Kado reads on a block that is discarded. The check is gated off for that variant.

WHY on by default with `--no-kado` escape (not opt-in): an opt-in flag would
have to be threaded through the `suggest-handling` SKILL.md invocation — a
second touch point that drifts. On-by-default keeps the surfacing automatic in
real Pass-1 runs; `--no-kado` keeps tests and offline runs deterministic.

## Persist Pass-1 placement anchor into suggestions-doc (spec 022/023)

WHY `persist_candidate_anchors` writes `candidate_mocs: [{path, anchor}]` onto
each create_atomic_note action: the rendered `**Placement:**` line is for the
human, but Pass-2 (suggestion-parser) needs the STRUCTURED anchor as the
apply-time default — the line cannot always round-trip (last-resort tier carries
no anchor; `alt_headings` and exact `new_section` spacing are line-lossy). The
schema field was added FIRST (`additionalProperties:false` would otherwise strip
it silently — the exact spec-schema-consumer drift class that caused the original
bug). The persisted shape is slim (`path` + the item-result `anchor` object only)
— score/pre_check stay out; the checkbox state is re-read from the markdown at
Pass-2 because the user may tick/untick.

WHY persistence is check-state-agnostic: every candidate with a structured
anchor is written, not just pre-checked ones. The reducer cannot know the final
checkbox state (the user edits the markdown between Pass-1 and Pass-2); the
parser is the authority that binds anchors only to MOCs that are still `[x]` at
apply time. Persisting all anchors keeps the default available if the user ticks
a previously-unchecked MOC.

## Version 1.11.0

WHY: Bumped for the spec 022/023 anchor persistence
(`persist_candidate_anchors`, `candidate_mocs` on rendered create_atomic_note
actions). `update-tomo.sh` skips unchanged versions silently.

## Structure-Aware Preview + Fallback Warning (spec 025 T6.1/T6.2)

### Mode descriptor (ADR-11 / FR-20)

WHY `_OUTPUT_FORMAT_*_LABELS` maps and the `**Format:**` field line: when a
group-result carries `output_format`, the user sees a one-line human-readable
summary (e.g. "table row · newest first · per item") next to the verbatim
preview rows. The labels are the only surface — no executor-internal names
(no "Hashi", no action-type, no script name) may appear in the rendered text.
This is the no-executor-internals rule (Marcus 2026-06-13, "das mit hashi
rausnehmen") applied to the new structure-aware path. The descriptor sits in
the field-lines block (before the blank line + composed_block), consistent with
the existing `**Handler:**` / `**Marker:**` field style. When `output_format`
is absent the function renders byte-identically to before (backward compat).

### Fallback ⚠️ + Approve-box gating (ADR-8 / FR-19)

WHY the Approve box is retained on fallback: a fallback means the structure
helper could not match the target section and composed a plain prose block
instead. That prose block is still a valid, safe update — the user approves
it knowingly (proposal-first model). Dropping the Approve box would silently
discard the composed content, forcing the user to re-trigger the whole flow.
The ⚠️ line names the handler, target, and a plain-language reason so the user
understands why the preview is prose, not a table row.

WHY hard guards take priority over fallback: `target_missing` and
`marker_missing` represent structural problems in the vault — the target does
not exist or the target heading is absent. Even a prose fallback cannot be
applied without a target. Hard guards always drop the Approve box; the presence
of a `fallback` key does not change that.

WHY `_FALLBACK_REASON_LABELS` maps reason codes to plain English: reason codes
like `cell_count_mismatch` are internal; the user sees "the section's columns
don't match the configured cells — falling back to a text note". All three
schema enum values (incl. `marker_missing`) are mapped; any unmapped/future
reason falls through to `_FALLBACK_REASON_DEFAULT`, a neutral phrase — never the
raw snake_case key (a raw key in user-facing text is itself an internals leak).

### target_missing guard rewording (T6.1 no-executor-internals cleanup)

WHY reworded from "Hashi modifies notes, it does not create them" to "The
target note must exist before this update can be applied": the old phrasing
named Hashi (an executor internal). The new phrasing is executor-neutral and
states the constraint directly without naming the mechanism.

## Tag-handler "Keep source files" checkbox (v1.19.0 → renamed v1.21.0)

WHY the tag-handler decision block carries a Keep-source option: approving a
group now deletes its consolidated inbox captures by default (instruction-render
branch 4). The `- [ ] Keep source files` box lets the user retain the source
notes when they want them to stay in the inbox. It sits under Approve and
defaults unchecked (delete is the default).

WHY the redundant `- [ ] Skip` line was dropped from every decision block
(v1.28.0 reducer / v0.13.0 render): the spec-027/ADR-4 "Skip is redundant —
un-approving IS skipping" ruling (see the two-box atomic section below) was only
applied to the atomic block at the time. The tag-handler, per-source
link_to_moc / create_moc / modify_note / update_daily blocks, and the aggregated
`## Proposed MOCs` section still rendered a decorative Skip box. Every parser
site reads ONLY the Approve/Accept checkbox — `_walk_tag_handler_decisions`,
`parse_section` ("Skip is the implicit inverse of Accept"), and
`parse_proposed_mocs` ("only the checked one matters") never inspect a Skip box —
so removing it changes no behaviour on either the markdown-parse or JSON-only
(wire) path. The change makes the whole document consistent with the atomic
model: Approve is the sole decision control.

WHY the wording avoids executor internals: the line reads "leave the captured
inbox notes in place after consolidating" — a user-visible effect — not
"suppress the delete_source action". Naming the action type or the executor
would leak internals into user-facing text. The parser keys the opt-out on the
block's `group_id`.

WHY renamed from "Keep origin" to "Keep source files" (spec 027 / ADR-4,
v1.21.0): "origin" was internal pipeline vocabulary; "source files" matches the
user-facing language used in the per-atomic block, making the vault consistent.

## Two-box atomic decision block (spec 027 / ADR-4, v1.21.0)

WHY the per-atomic block was reduced from four controls (Approve, Keep origin,
Skip, Delete source) to two (Approve + Keep source files): "Skip" is redundant
— un-approving IS skipping, and having both confused users into thinking they
served different purposes. "Delete source" as a per-atomic option was equally
redundant — the source is deleted by default on approval; the only meaningful
extra intent is KEEPING it. The new two-box layout makes that intent explicit
without offering choices that don't add information.

WHY "Keep source files" not "Keep origin": aligns with the terminology the user
already sees in the section heading and tag-handler block; avoids leaking the
internal "source_inbox_item" wire-field name into user-facing text.

## Voice source rendered as a file set (spec 027 / ADR-1, v1.21.0)

WHY render_create_atomic_note checks action.get("audio_peer"): voice notes
produce two artefacts — the transcript (.md) and the recording (.m4a). Showing
only [[transcript-stem]] would hide the audio file the user may want to keep or
link. The set form [[stem]] + [[peer.m4a]] makes both visible in the review UI.

WHY peer_name uses rsplit("/", 1)[-1] (basename only): the audio file lives in
the same vault-relative directory; a wikilink needs only the filename, not the
full path. The extension (.m4a) is intentionally preserved — coercing it to .md
would generate a broken wikilink to a non-existent note.

WHY the audio_peer field is additive and optional: non-voice items have no peer;
the renderer defaults to the existing `[[stem]]` line. Phase 3 plumbs the
audio_peer value from the analyst; Phase 2 only renders the shape, tolerant of
None.


## Sub-0.5 atomic suppression — kept in inbox (#88, v1.20.0)

WHY render lives here, not in the analyst: the analyst keeps EMITTING the sub-0.5
`create_atomic_note` (with its worthiness + source_stem) so the reducer has the
data; the reducer is the single deterministic gate that decides what the user
sees. Relying on the LLM analyst to "emit as an alternative vs a full action"
produced a self-contradicting spec that the LLM resolved by emitting a full
proposal (the #88 bug — a 0.4-worthiness run-log got a full atomic proposal).

WHY the `has_log_entry` early-return was the bug: `_enforce_coexistence`
previously dropped sub-worthy atomics ONLY when a daily `log_entry` coexisted
(`if not has_log_entry: return actions`). With a `log_link` or no daily, the
sub-worthy atomic survived and was rendered as a FULL proposal. The early-return
is removed; sub-worthy atomics are now resolved regardless of daily coexistence.

WHY flag `suppressed` instead of dropping: a section only renders when its action
list is non-empty. Dropping a daily-less sub-worthy atomic would make the item
VANISH from the doc — the user could neither see the worthiness nor Force-Atomic
it. So the sub-worthy atomic is KEPT and flagged `suppressed`; the main loop
renders a LIGHT "kept in inbox" block (`render_suppressed_atomic`) — worthiness +
a Force Atomic Note checkbox, no template/location/MOC/Approve framing — and skips
both `persist_candidate_anchors` and the Proposed-MOC cluster seed (a sub-worthy
note must not seed a MOC). The never-lose invariant is now "surfaced as
low-worthiness, kept in inbox," not "always emit a full atomic note."

WHY item-level force_atomic is propagated onto the action before
`_enforce_coexistence`: `_atomic_survives` reads `force_atomic`/worthiness off the
ACTION, but the FAN / fan-resolve flow sets `force_atomic` on the ITEM (the action
may carry neither). Without propagation, removing the early-return suppressed
force-resolved atomics and dropped their proposed MOCs. The reducer now copies the
item's `force_atomic` onto each create_atomic_note action first.

## Content preview — `**Summary:**` line (b, content-preview gap)

WHY atomic suggestion sections gained a `**Summary:**` line (reducer v1.29.0):
sub-worthy / kept-in-inbox items rendered only Source + Suggested name + worthiness,
so the user could not tell what a note was *about* without opening it — a real gap
once the inbox held concept notes that are neither daily-log entries nor promoted
atomics. `render_create_atomic_note` and `render_suppressed_atomic` now render an
optional `**Summary:**` (a one-sentence gist) directly under Suggested name. The
gist is authored by the analyst (`inbox-analyst`), not the reducer — the reducer is
deterministic and never had the note content. Threaded through the structured `item`
so `suggestions-render._wire_note` mirrors it into the wire (`summary`), giving the
Hashi editor the same preview. Optional field — legacy items without it render and
validate unchanged (schema_version stays "1").

## Stale tag-handler group drop — `filter_stale_tag_handler_groups` (B)

WHY the reducer drops tag-handler groups whose `source_paths` are ALL missing
(v1.30.0): `tomo-tmp/tag-handler-groups/` is per-run staging, but — unlike `items/`,
which the reducer filters by `run_id` (#116) — a group-result JSON carries NO run_id.
The LLM interpreter step (suggest-handling SKILL 3b) is gated on `handled[]` being
non-empty, so a run with no tag-handler-tagged inbox notes never overwrites the dir,
and `tag-handler-writer` never clears it. Result: a group whose sources were consumed
by an earlier run leaked into the next suggestions doc and rendered a live Approve box
(the existing `annotate_tag_handler_group_guards` only checks the TARGET note, not the
sources — so a stale group with a still-present target passed the guard). A group with
no live sources has nothing to consolidate, so it is unappliable — dropped before the
guard pass. Fail-open mirrors the daily-existence check: None client (`--no-kado`/test)
keeps everything; a source counts as missing ONLY on a definitive `path_exists → False`
(NOT_FOUND); any propagated error counts it present, so a Kado hiccup never drops a live
group. Drops are logged (`tag_handler_stale_dropped=N` + per-group stderr line) — no
silent truncation. Paired with the primary fix: `reset-tomo-tmp --pass1` now also clears
the staging dir + `tag-handler-group-stubs.json` (v0.3.0), so the leak is closed at both
the reset path and defensively at render time.

## WHY the `--fan-resolve` branch clears `tag_handler_updates` (v1.31.0)

WHY: the fan-resolve doc is **force-atomic-only** — it resolves the atomics the
user ticked *Force Atomic Note* on, and nothing else. The `if args.fan_resolve:`
branch already blanks `daily_notes_updates`, `rendered_daily_updates_md`, and
`needs_attention` for exactly this reason, but originally forgot
`tag_handler_updates`. Those are collected from the persistent
`tomo-tmp/tag-handler-groups/` staging dir (`collect_tag_handler_groups`), which
survives from the primary Pass-1 run into the fan-resolve run — so the fan
reducer re-read the *same* groups and wrote them into the fan doc too. Result:
a tag-handler-consolidated source (e.g. a Tsukai capture routed to a Dev Log via
its tag handler) appeared in **both** the suggestions doc and the fan doc, and
would be applied twice. The fix blanks `tag_handler_updates` +
`rendered_tag_handler_updates_md` in the fan-resolve branch, mirroring the
sibling clears. Tag-handler groups are owned by the primary doc; the companion
merge at Pass 2 pulls the primary's groups, never the fan's.

## Structural-heading gate backstop — `demote_structural_anchors` (#71, spec 023 ADR-6, v1.32.0)

WHY: Spec 023's confidence gate keeps content notes off structural/template
headings (`## Content`, `## Structure`, …) by routing low-confidence heading fits
to a new section. But the gate is a *pure LLM instruction* in `inbox-analyst.md` —
no code enforces the `fit_confidence >= 0.6` comparison. A live run (2026-06-17,
"Asakusa Senso-ji") let the LLM score "Content" ≥0.6 and slip the gate, landing the
note under `## Content` — the exact anti-pattern 023 targets. An LLM compliance slip
has no floor without a deterministic net.

`demote_structural_anchors(action, stem)` is that net. Called once per
`create_atomic_note` action, it walks `candidate_mocs[].anchor` and rewrites any
tier-1 heading anchor whose heading is in `lib/structural_headings.py` to a tier-2
anchor: `{type: callout, value: null, placement: before, new_section: <note topic>,
alt_headings: [<rejected heading>, …]}`. `new_section` is the note's own topic
(`suggested_title`, else `stem`); the rejected structural heading is prepended to
`alt_headings` so the user keeps a one-click override (ADR-3).

WHY it runs in the reducer (Pass-1), not at Pass-2 apply: the suggestions doc is the
review surface. If the gate slips, the user must SEE "new section `## <topic>`" at
review time — not approve "under `## Content`" and have it silently land elsewhere.
Demoting at apply would violate the review contract.

WHY no Pass-2 change is needed: the demoted anchor is shape-identical to a genuine
analyst tier-2. It is mutated in place on `action["candidate_mocs"]` BEFORE both
consumers read it — `render_create_atomic_note` (the `**Placement:**` markdown) and
`persist_candidate_anchors` (the wire) — so both surfaces agree. Downstream, the
Pass-2 markdown reverse-parser (`suggestion-parser.parse_placement_line`) and the
JSON-only wire path both recover the same tier-2 anchor a real tier-2 would produce;
`render_resolve` then resolves the actual insert spot from the live MOC. The
round-trip is pinned by `test_demoted_anchor_roundtrips_as_tier2`.

The structural list is the SSoT in `lib/structural_headings.py`, shared with the
offline tuning aid `scripts/analyze-placement-confidence.py` (which still reads the
RAW analyst `fit_confidence`, so a persistent flag there stays the #64 tuning signal
for the 0.6 threshold). A metadata-only stderr line reports the demotion count per
run — never note content or heading text.

## Attachment filing — review surface + the resolved-attachments merge (spec 031)

### `**Attachments:**` / `**Unresolved embeds:**` lines are source-only (Phase 3, T3.2)

WHY the per-item `**Attachments:**` line renders ONLY the resolved source path(s),
never a destination: AC-F3.1 reads as if the destination belonged next to each
attachment, but the destination (`concepts.asset`) is a single value for the WHOLE
RUN, not a per-attachment fact — and at the point this line renders, the reducer has
no config access at all (no `--config`/`--vault-config` flag, unlike
`instruction-render.py`). Repeating one folder on every item's line would also be
noise the user has to read past N times. The destination half of AC-F3.1 is a
separate, RUN-LEVEL preamble (below); the per-item line's job is narrower: let the
user sanity-check WHICH file resolution picked, via the full vault-relative path in
backticks — not a wikilink, because the existing `**Source:**` line already encodes
up to two wikilinks POSITIONALLY (`suggestion-parser.py:712` reads `wikilinks[1]` for
`audio_peer`), so a 0..N attachment list cannot share that slot without colliding
with the audio-peer encoding.

WHY this per-item format was frozen BEFORE the run-level preamble existed, not
designed together with it: the destination gap (AC-F3.1) was discovered mid-Phase-3,
after `attachments` was already threading through all four `suggestion-parser.py`
sites (T3.4) matching the `audio_peer` precedent exactly. A per-item destination
element — even one left blank as a placeholder — would have forced every one of
those four sites to be re-touched when the destination was later added, because the
line's SHAPE would have changed. Freezing the per-item line to "backticked source
paths, nothing else" meant the eventual preamble (Phase 5) could be added as a
document-level addition that touches zero parser sites — it is not itself part of
any per-item field the parser round-trips.

WHY `**Unresolved embeds:**` (Should-have) is rendered but never parsed back: it is
diagnostic, one-way, display-only — there is no user decision attached to an
unresolved/ambiguous embed (no checkbox, nothing to edit), so it does not belong to
the CON-5 both-channels-in-lockstep guarantee that `attachments` does. Accordingly
it was never added to the structured `item` mirror or to `suggestions-wire.schema.json`
— an undeclared-but-unprojected field is fine; a declared-but-never-populated one is
noise the next reader has to disprove. It IS declared on `item-result.schema.json`
(`unresolved_embeds: [{embed_target, status, candidate_count?}]`) because the
analyst-facing contract needs `additionalProperties:false` to accept it once
inbox-triage's resolver populates it — declaring the analyst-side contract and
projecting a field into the review UI are different questions with different
answers here.

### The resolved-attachments map is a FILE, not in-memory state (Phase 6 gap fix)

WHY `attachments`/`unresolved_embeds` were declared, rendered, and round-tripped for
two full phases before anything ever produced them: the original SDD's ADR-2
assumed extraction could run "on bodies the pipeline already has" — but
`inbox-triage.py` (the process that resolves embeds against the inbox index) never
reads note bodies; only the analyst SUBAGENT does, per-item, and ADR-2 explicitly
keeps embed detection OUT of the analyst (deterministic extraction, testable
without an LLM in the loop). So there was no code that had both a note body and a
place to put a resolved list.

WHY the fix is a sibling JSON file (`tomo-tmp/resolved-attachments.json`, keyed by
vault-relative source path) rather than an in-memory data structure passed to the
reducer: `inbox-triage.py` and `suggestions-reducer.py` are SEPARATE PROCESSES,
invoked by the orchestrator as two independent script runs — there is no shared
Python heap between them. `inbox-triage.py` already writes `routing-plan.json` and
was, at one point mid-spec, attaching `attachments`/`unresolved_embeds` directly onto
its own `new_sources` entries in memory — but `suggestions-reducer.py` never reads
`routing-plan.json` at all (verified: zero references), and `routing-plan.json`'s
`fresh_sources` is scoped by NEWNESS, not by "has attachments" — the reducer
processes every DONE stem from `state.jsonl`, which on a Pass-2 or re-run is a
different set entirely. Keying the merge to `fresh_sources` would silently drop
items that were new on a PRIOR run. A dedicated, path-keyed file that both processes
independently open is the only channel that actually crosses the process boundary
correctly. This is exactly the kind of thing a future "simplification" back to
in-memory passing would silently break — there is no shared process to pass it in.

WHY merge by source PATH, not by stem: every `{stem}.result.json` already carries a
`path` field (required by `item-result.schema.json`), so the reducer looks it up
directly at the point it loads the result — no derivation needed. `inbox-triage.py`
already has full vault-relative paths from Kado's `listDir`; deriving a stem
(stripping folder + extension) would be a lossy transform BOTH sides would have to
agree on exactly, and paths are unique across the vault where stems are not
guaranteed to be.

WHY `merge_resolved_attachments` applies the resolved map to EVERY
`create_atomic_note` action on one result, not just the first: F-41 lets one inbox
item emit N atomic notes (one per conceptual thread). The embeds live in the ONE
shared source note body — an attachment embedded in that note belongs to every
thread derived from it, not to whichever thread happens to be first in the list.

WHY the resolved map OVERRIDES an analyst-supplied value instead of merging with it
(union) or preferring the analyst's: ADR-2 keeps the analyst from ever producing
`attachments`/`unresolved_embeds` — so a value already present on an action when the
merge runs is not a legitimate alternate source, it is unexpected. Treating the
deterministic map as authoritative and logging a stderr WARNING (naming the stem)
when an analyst value is overridden makes the disagreement visible without crashing
the run — the map is deterministic and testable; an LLM producing this field would
not be.

### The destination is a run-level preamble line, not a per-item fact (Phase 5)

WHY `render_attachments_preamble` renders one line ONCE for the whole document
("Attachments will be filed to `<folder>`.") instead of decorating each item's
`**Attachments:**` line with a destination: `concepts.asset` is a single flat
folder for the ENTIRE run — every attachment in every item goes to the same place.
Rendering it per item would repeat the identical string N times for no added
information; a single preamble line satisfies AC-F3.1's actual intent ("see the
full consequence before you approve") more directly than N repetitions would.

WHY the line appears ONLY when at least one item in the document carries
attachments: a run with none must look byte-identical to a pre-attachments run
(the standing near-MVP additive-only constraint). `render_attachments_preamble`
scans every `create_atomic_note` action's `item.attachments` before deciding to
render anything — the scan, not a config flag, is the gate.

WHY the folder value is threaded through `shared-ctx.json` (a channel the reducer
already opened for the field→section map, since removed with #162) rather than the
reducer reading `vault-config.yaml` directly: the reducer has never had a
`--config`/`--vault-config` CLI argument — only `instruction-render.py` does. Adding
a second, independent config reader to the reducer would duplicate
`instruction-render.py`'s `load_config`/`CONFIG_DEFAULTS` machinery for one string.
`shared-ctx-builder.py` already reads `vault-config.yaml` once per run and already
writes an envelope the reducer already loads; adding `asset_folder` to that
envelope (`shared-ctx-builder.md`'s `build_asset_folder`) reuses the existing
channel instead of building a parallel one.

WHY `load_asset_folder` fails open to `DEFAULT_ASSET_FOLDER` (imported from
`lib.render_actions`, never restated as a literal) on a missing/unreadable/malformed
`shared-ctx.json` or an absent/blank key: this mirrored the fail-open shape of
`load_field_sections` (removed with #162; the same shape now lives in
`instruction-render.load_tracker_fields`), and a missing default here would mean the
preamble either crashes the run or renders an empty backtick pair — both worse than
falling back to the same default `_asset_dest_join` (`render_actions.py`) uses when
it actually resolves the destination at instruction-render time. The two functions
sharing one canonical constant is what keeps the preamble text and the real move
target from silently disagreeing.

WHY `load_resolved_attachments` distinguishes a MISSING file (silent) from an
EXISTING-but-broken one (a loud stderr `WARNING` naming the path): both failure
modes fall back to `{}`, and every item then gets `attachments: []` — but they mean
opposite things. A missing file is the normal state before inbox-triage's producer
has run, or on a run with genuinely no attachment-bearing embeds; treated the same
way as a malformed/unreadable file, the two become indistinguishable from stderr
alone, and "the feature silently does nothing" would read identically to "this
inbox had no attachments" — exactly the class of failure this whole spec exists to
close (a note files, its attachment doesn't, and nothing looks wrong). The non-dict
JSON case (a syntactically valid file that parses to e.g. a list) is checked
separately from the JSON-decode/OSError case, because a `json.loads` success with
the wrong top-level shape needs its own WARNING naming the actual type found — it is
not caught by the `except` clause at all.

## Suppressed items carry the embed warning but not the attachment list (spec 031 T6.5, v1.36.0)

WHY `render_suppressed_atomic` emits `**Unresolved embeds:**` but deliberately
omits `**Attachments:**`, when the full renderer (`render_create_atomic_note`)
emits both: the two lines answer different questions, and only one of them is
still true for an item that stays in the inbox.

A suppressed item is not promoted. `suggestion-parser` never puts it in
`confirmed_items`, so it never reaches the manifest, so
`_build_move_asset_actions` never sees its attachments and Pass 2 emits no
`move_asset`. Rendering `**Attachments:** \`100 Inbox/Images/x.jpg\`` there
would name a file and imply a filing action that the pipeline has already
decided not to take — the user would look for the image in the asset folder
after applying and find it still in the inbox. That is a promise the render
layer is not entitled to make.

An unresolved or ambiguous embed is not a statement about what Tomo will do.
It is a statement about the vault: two files share a basename, or an embed
points at nothing. The user has to fix that by hand, and it is equally true
whether or not the note is ever promoted. Dropping it costs the user a real
signal.

This gap was found by spec 031's T6.5 live validation, not by the offline
suite: three of the four test fixtures scored below the 0.5 worthiness
threshold and took this renderer, so `Dresden.md`'s
`ambiguous — 2 candidates` was resolved correctly, written to
`tomo-tmp/resolved-attachments.json`, and then silently dropped at render.
Spec 031 never mentions suppressed items anywhere — the feature was designed
against the promoted path, and `render_suppressed_atomic` (#88) predates it.
The interaction was unspecified rather than mis-implemented, which is why no
offline test caught it: nothing had ever asserted what the second renderer
should do with these fields.

Note that the merge itself needed no change. `merge_resolved_attachments`
already applies to *every* `create_atomic_note` action regardless of
suppression, so the data was present on the action all along — the fix is
purely in the render layer.

## The ADR-2 analyst override is load-bearing, not defensive theatre (spec 031 T6.5)

WHY `merge_resolved_attachments` overrides rather than merges when an action
already carries `attachments` or `unresolved_embeds`, and warns to stderr:
ADR-2 says the analyst never produces these fields, so the branch reads like
a paranoid guard against something that cannot happen. It happened on the
first live run.

`Bautzen.result.json` from spec 031's live run 2 came back from the analyst
carrying `unresolved_embeds: [{"embed_target": "bautzen-turm.jpg", "status":
"unresolved"}]` — a field it was never asked for, with a verdict that was
wrong (the file resolves cleanly to `100 Inbox/Images/bautzen-turm.jpg`). The
override replaced it with the deterministic map's answer and the run produced
the correct single attachment. Had this branch merged instead of overridden,
or trusted the action's existing value, the user would have seen a spurious
"unresolved" warning for a file that was sitting right there.

Keep the override, and keep the stderr warning: it is the only signal that
the analyst is emitting fields ADR-2 says it must not.

## render_update_daily, its RENDERERS entry, and load_field_sections were dead (#162, v1.37.0)

WHY three things were removed rather than repaired: none of them could run.

`2db4a0f` ("drop duplicate daily blocks per-item") acted on the 2026-04-22 UX
decision that the per-item `**Daily update:**` block should not repeat what the
aggregated `## Daily Notes Updates` block already shows. From then on
`update_daily` was handled by its own branch in the dispatch loop, which sets
`rendered = None` and collects into `daily_groups`. `RENDERERS` is consulted in
exactly one place — the `else` arm of that same chain — so the
`"update_daily": render_update_daily` entry became unreachable and the function
with it. `load_field_sections` existed only to feed that function's
`field_sections` parameter, and its return value was discarded at the call site,
which is how #162 was noticed.

The removal was not taken on a reading of the control flow alone. The function
body was replaced with a bare `raise` and the full suite run: 3232 tests passed,
including the fixtures carrying `update_daily` actions and the tests covering
the aggregated block. Nothing reached it. That check is worth repeating for any
future "this looks dead" removal — a static argument about an `elif` chain is
easy to get wrong, and this codebase cannot be exercised end to end in the test
vault on demand.

What replaces it: nothing here. The field→section map was never the reducer's
to apply — the values are consumed at Pass 2, so the lookup now lives in
`instruction-render.load_tracker_fields`, reading the same `shared-ctx.json`
key. See `docs/tomo/scripts/instruction-render.md`.

`--shared-ctx` stays on this script: `load_asset_folder` still uses it.

A permanent structural guard asserts `"update_daily"` is absent from
`RENDERERS` and that neither removed function has come back. It is structural
rather than behavioural because code that never executes cannot fail a
behavioural test — the same reasoning as spec 033's `ast.parse` guard.
