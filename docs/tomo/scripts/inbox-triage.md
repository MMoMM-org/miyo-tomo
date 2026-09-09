# WHY: scripts/inbox-triage.py

> Rationale for decisions in `tomo/scripts/inbox-triage.py`.
> Deterministic inbox triage: partitions inbox files into frontmatter-state
> buckets, computes the routing action, and writes `routing-plan.json` for the
> conductors. Only non-obvious decisions are recorded here.

## `--recover` Folds `captured_hits` Into `fresh_sources` (not just the action)

WHY: `--recover` means "treat captured items as fresh — re-process them". Two
places must honour that, and originally only one did:

1. `determine_action` returns `"suggest"` on `recover and captured_hits`.
2. `build_routing_plan` builds the `fresh_sources[]` dispatch list.

The conductor (`suggest-handling` skill) dispatches **`fresh_sources[]` only**.
Before the fix, `build_routing_plan` populated `fresh_sources` from
`new_sources` exclusively — so `--recover` flipped the action to `"suggest"`
but handed the conductor an **empty** list: the run reported "suggest" and
dispatched nothing. The flag silently did nothing, and the only test
(`test_recover` in `test_inbox_triage.py`) checked the action decision, not the
dispatch list, so it passed while the feature was broken. Surfaced during spec
021 T4.3 live validation (2026-06-09): `/inbox --recover` produced
`fresh_sources: 0` and no new dispatch.

Fix: `build_routing_plan` now appends `captured_hits` to the dispatch sources
when `state.recover` is set. `new_sources` and `captured_hits` are disjoint by
construction (`compute_new_sources` excludes every frontmatter bucket, captured
included), but the fold dedupes by path so a future overlap can't
double-dispatch. Regression coverage:
`test_recover_folds_captured_into_fresh_sources` (must appear) +
`test_no_recover_excludes_captured_from_fresh_sources` (must not leak without
the flag).

Note: this is a pre-021 latent bug, fixed during 021 validation because that is
when a clean-vault re-process surfaced it.

## Discovery-Cache Staleness Warning (#36 / F-21)

WHY: The discovery cache (`config/discovery-cache.yaml`) is rebuilt by
`/explore-vault`, never by `/inbox`. So an `/inbox` run can silently rely on a
months-old vault map (MOC list, tag prefixes, structure) without the user
knowing. Step 8c reads the cache's `last_scan` and, when it is older than
`--stale-cache-days` (default 7), appends a `stale_cache` drift_indicator — the
same user-facing, non-blocking channel the conductors already surface ("surface
each warning but continue"). The message points the user at `/explore-vault`.

WHY a drift_indicator (not the statusline): the drift channel fires at the exact
moment the user is about to act on the cached map, is already surfaced by every
conductor, and is deterministically testable. It required one additive enum
value (`stale_cache`) in `routing-plan.schema.json` — backward-compatible, so
existing plans still validate.

WHY fail-open (missing / malformed / timestamp-less / future-dated → no
warning): a fresh install mid-setup has no cache yet and must not be nagged, and
a corrupt cache must never crash triage. Only a genuinely old, parseable
`last_scan` surfaces a warning. A `last_scan` in the future (clock skew) is
treated as fresh. The staleness check is `discovery_cache_staleness_drift`;
coverage in `tests/test_triage_cache_staleness.py`.

## Fan-resolve trigger reads the edited wire (ADR-026 JSON-only)

WHY triage extracts force-atomic items from the wire, not just the markdown
(v0.21.0): the fan-resolve routing (determine_action branch 5) fires on
`force_atomic_items`, which `_extract_fan_items` scraped from `- [x] Force Atomic
Note` checkboxes in the markdown body. Under ADR-026 JSON-only, Hashi edits the
`_suggestions.json` and writes a MINIMAL markdown envelope (frontmatter + `- [x]
Approved` only) — the force-atomic decisions live solely in the JSON. So the
markdown scrape found nothing, `force_atomic_items` was empty, and an approved doc
with force-atomic'd items routed to `synthesize` instead of `fan-resolve` — the
items surfaced in `build_from_wire`'s `pending_fan_resolutions` but nothing
consumed them, so they were silently dropped (neither created nor resolved).

`_load_edited_wire` mirrors `suggestion-parser.load_changed_wire` (present +
schema_version "1" + digest mismatch) so triage and Pass-2 agree on whether the
JSON is authoritative. When edited, `_extract_fan_items_from_wire` reads the
force-atomic set from the JSON (suppressed `force_atomic` suggestions + daily
`force_atomic_note` log entries, deduped by stem) and the markdown body is ignored
entirely — the JSON flow behaves exactly like the markdown flow. Unedited/absent
wire → the markdown scrape stays authoritative (byte-identical to prior behaviour).

NOTE (downstream, not yet done): the fan-resolve render
(`force-atomic-handling/SKILL.md`) emits the suggestions-fan doc WITHOUT a
`--json-output` wire, so the 2nd (fan) round is markdown-only — Hashi cannot yet
resolve it in JSON. Full Hashi parity needs the fan doc to emit + publish its own
wire, mirroring suggest-handling.

## Fan-doc wire caching (ADR-026 Piece 2)

WHY triage also caches the `_suggestions-fan.json` wire sibling and sets
`wire_cache_path` on the `approved_fan` entry (v0.22.0): for the JSON flow to work
exactly like the markdown flow, the SECOND (fan) round must be Hashi-editable too.
The fan-resolve render now emits + publishes a fan wire (force-atomic-handling
SKILL); triage caches it like the primary, and the synthesis-conductor threads
`--suggestions-json` for the standalone-fan path so a Hashi-edited fan resolves
JSON-only (build_from_wire). Fan docs carry no force-atomic re-opt-in, so the fan's
own force-atomic extraction stays markdown. LIMITATION: the fan-COMPANION merge
(primary + fan in one run) still parses the fan markdown — it is not the Hashi
standalone-fan path (primary already applied → fan approved in a later run).

## `.base`/`.canvas` inbox files are deliberately NOT triaged (#93, won't-do-yet 2026-07-18)

WHY `discover_files` partitions only `.md` + audio and drops everything else,
including `.base` / `.canvas`: these are **terminal artifacts**, not raw material
for the 2-pass pipeline. The companion authoring path (`inbox-author` skill,
spec 026, shipped) can compose `.base`/`.canvas` and write them into the inbox for
the user's direct use — dashboards, canvases — finished products, not notes to be
triaged, linked, or moved.

The lifecycle is 100% frontmatter-driven: every managed doc carries a `tomo:` block
(`lib/doc_frontmatter.py`) whose `state` field drives the state machine
(`captured` → `pending-approval` → `approved` → …). `.base` is YAML and `.canvas`
is JSON — neither carries (nor should carry) a `tomo.state`. So they structurally
cannot enter the state machine without a sidecar-metadata scheme, which would be a
large change contradicting the "terminal artifact" stance.

**Decision (2026-07-18, issue #93):** keep them parked. The producer is shipped but
opt-in and not yet writing artifacts at scale, so no documented trigger has fired.
Rather than surface them, the deliberate skip is now DOCUMENTED at the code site and
PINNED by a test (`test_inbox_triage.py::test_mixed_file_types_partitioned_correctly`
asserts `.base`/`.canvas` are excluded) so a future reader never mistakes it for a
silent bug. **Revive** (surface them informationally, or design a metadata scheme)
only when `.base`/`.canvas` genuinely land in inboxes at scale and users need `/inbox`
to acknowledge them.

## garden-audit gates on markdown Approved OR wire approved:true (Tomo-Editor Q1, 2026-07-22)

WHY the garden-audit branch now caches the wire sibling FIRST (into `garden_wire_cache`), then gates
`approved = bool(_RE_APPROVED.search(body)) or _wire_approved(garden_wire_cache)`: the Tomo-Editor
works from the JSON (Hashi's channel), so it flips a top-level `approved: true` in the wire instead
of ticking the markdown box. Reading only the markdown would leave an editor-approved doc stuck in
`pending`. `_wire_approved` reads the cached wire's top-level flag; absent/unreadable → False, so
`.md`-only users are unaffected (back-compat). The sibling is cached once and REUSED in the approved
branch (no double fetch). Pinned by `test_inbox_triage.py::TestGardenAuditApprovalGate` (markdown-only,
wire-only, neither). NOTE: this supersedes the markdown-only gate below for the WHETHER-picked-up
decision — the `approved:true`-forces-JSON-path routing itself lives in `garden-audit-parser`.

## garden-audit gates on a top-level Approved box (ADR-1 revised, 2026-07-21)

WHY the garden-audit approval branch is `approved = bool(_RE_APPROVED.search(body))`
rather than an unconditional `True`: ADR-1 originally accepted every pending-accept
garden-audit doc unconditionally (the wire digest was the only edit signal). The live
retest reversed that — the user wanted a document-level review gate, like suggestions.
garden-audit now reuses the exact same `_RE_APPROVED` top-level `- [x] Approved` pattern
as suggestions/suggestions-fan; an unticked doc stays `pending-accept` and is never routed
to `approved_garden_audits[]`. Per-finding Apply ticks + the wire still choose WHICH fixes
apply (garden-audit-parser, Pass-2); this branch only decides WHETHER the doc is picked up.
Pinned by `test_inbox_triage.py::TestGardenAuditAsUpstreamType::test_unticked_garden_audit_stays_pending`.

## wire_cache_path is set unconditionally (spec 030 two-artifact split, 2026-07-21)

WHY the garden-audit branch sets `entry["wire_cache_path"]` UNCONDITIONALLY (to the cached
path, or `null` when the sibling is genuinely absent) rather than only when the sibling
exists: the wire is now the STRUCTURE source, always read by `garden-audit-parser` and joined
to the markdown decisions by F-id — so the synthesis-conductor must ALWAYS pass `--wire`. The
render always writes the wire sibling, so this resolves to a real path in normal operation; a
`null` only occurs for a malformed doc with no sibling, and the parser then degrades to empty
`confirmed_items` (warn, no crash). The routing-plan schema types `wire_cache_path` as
`["string", "null"]` for garden-audit to allow the rare null. Pinned by
`test_entry_carries_real_wire_cache_path_when_sibling_present`.

WHY this depends on the vault FILENAME convention (2026-07-21 fix): `_cache_wire_sibling`
derives the wire as `report_vault_path[:-3] + ".json"` — the report's `.json` sibling. The
agent must therefore write the wire as `<ts>_garden-audit.json` (the `.json` sibling of
`<ts>_garden-audit.md`), NOT a `garden-audit-wire-<epoch>.json` name. Before the dated-filename
rename the agent wrote `-wire-<epoch>.json`, which was never the sibling → the wire was never
found → the "resolves in normal operation" claim above was FALSE and the whole apply path
silently no-op'd. The rename to the dated inbox convention makes it true; `_cache_wire_sibling`
itself was NOT changed (the rename aligns to what it already expects). Pinned by
`test_wire_is_report_json_sibling_by_convention`.

## Attachment detection/resolution, and why the resolved map is a FILE (spec 031)

WHY `build_attachment_index` (Step 2b) was ORIGINALLY a second, independent `listDir`
call (spec 031): the partition listing (Step 1) was shallow — direct children only —
and existed to bucket inbox files by type, while resolving an embed correctly requires a
RECURSIVE view of the whole inbox subtree, since the observed real-world case is a note in
one subfolder embedding an attachment in another (`100 Inbox/Places/note.md` →
`100 Inbox/Images/karte.jpg`). Widening the partition call would have changed its depth
semantics for every existing caller, so a separate call kept both contracts unchanged at a
cost of exactly one extra call per run, independent of note or embed count.

WHY it is now ONE shared listing (spec 034, ADR-3, 2026-09-06): that "changed depth
semantics for every existing caller" objection was the whole POINT of spec 034 — making
discovery recursive is the feature, not a side effect. Once the partition recurses too,
the two calls fetch byte-identical data, and the second one is pure waste.
`discover_files` makes the single call and returns the raw listing (folders and every
suffix included, deliberately — `build_inbox_index` does its own filtering);
`build_attachment_index` takes that listing instead of a client. Base Kado calls fall
3 → 2. The precondition was spec 034 T3.1: the two consumers used to disagree about what
a `listDir` entry naming a file is, and had to be unified on `is_file_entry` before they
could safely read the same input.

WHY the attachment index no longer fails open on a `KadoError` (also spec 034 ADR-3):
while the index had a listing of its own, losing it cost only attachment resolution — the
partition had its own call and the run carried on degraded. That call is now the run's
ONLY inbox listing, so losing it leaves no partition either. Degrading to an empty listing
would report an EMPTY INBOX rather than an outage — strictly worse than failing, and
invisible to the user. So the error propagates and `main()` exits 1, exactly as the
partition's own listing failure always did. Pinned by
`test_kado_error_on_the_listing_aborts_the_run` and
`test_kado_error_on_the_listing_exits_1_rather_than_reporting_an_empty_inbox`.

WHY recursion does NOT change the `#93` partition: that decision is by SUFFIX — a `.png`
is a terminal artifact outside the frontmatter-driven lifecycle wherever it sits. Recursion
changes WHERE files are found, never WHAT counts as an item, so a subfolder `.png` is
classified exactly as a root-level one. Pinned by
`test_subfolder_png_is_classified_exactly_as_a_root_png`, which asserts both in the same
run so the test states the invariant rather than two separate facts.

WHY embed extraction (Step 2c, `resolve_inbox_attachments`) calls
`client.list_notes(inbox_path, fields=["links"])` rather than
`lib.attachment_index.extract_attachment_embeds`'s regex, reversing the
original SDD's ADR-2: ADR-2 assumed the regex could run "on bodies the
pipeline already has" — but `inbox-triage.py` never reads a note's fresh body
for any of the notes it triages; only the per-item analyst SUBAGENT does, and
ADR-2 deliberately keeps embed detection out of the analyst (deterministic,
testable without an LLM in the loop). So the regex had a correct
implementation with nowhere in this process to run it against real data.
`list_notes(fields=["links"])` needs no body at all — Kado's own
metadataCache already discriminates `kind == "embed"` from a plain link
(including cases a regex cannot see, like a fenced code block containing
`![[x.jpg]]`) — so it became the actual extraction path once that gap
surfaced. `attachment_index._is_attachment_target` and
`_strip_alias_and_anchor` are reused as-is to classify and clean each
`list_notes` target; `extract_attachment_embeds` itself keeps zero callers in
the pipeline but remains a correct, tested library function (see
`docs/tomo/scripts/lib/attachment_index.md`).

WHY the resolved map (`attachments[]` + `unresolved_embeds[]` per source path)
is written to a sibling file, `<output_dir>/resolved-attachments.json`, rather
than attached in-memory to a `routing-plan.json` entry:
`inbox-triage.py` and `suggestions-reducer.py` are SEPARATE PROCESSES,
invoked as two independent script runs by the orchestrator — there is no
shared Python heap to pass a data structure through. The reducer never reads
`routing-plan.json` at all (zero references, verified), and even if it did,
`routing-plan.json`'s `fresh_sources[]` is scoped by NEWNESS, not by "has
attachments" — the reducer processes every DONE stem from `state.jsonl`,
which on a Pass-2 or later re-run is a different stem set than whatever was
"fresh" on the run that first resolved the embeds. Keying the hand-off to
`fresh_sources` would silently drop attachments for items that were new on a
PRIOR run. A dedicated, path-keyed file that both processes independently
open and close is the only channel that actually crosses the process
boundary correctly. **Two agents independently reached for
`routing-plan.json` as the join point before this was pinned down** — if a
future refactor considers passing this in-memory again, there is no shared
process on the other end to receive it. The reducer-side half of this
contract (how `merge_resolved_attachments` consumes the file, and why by
path rather than by stem) is documented in
`docs/tomo/scripts/suggestions-reducer.md`.

## Suggest-before-approve gate (garden-audit, 2026-07-24)

WHY the garden-audit branch now clears `approved` when `_garden_suggest_pending(body, wire)` is true:
a user can tick "Suggest targets" AND approve in the same pass, but applying then silently skips the
candidates they explicitly asked for. The gate is MAINLY for the .md-only path — a Hashi editor
blocks approve itself using the top-level wire `suggest_pending`, but a markdown-only user has no
such block. Two detection channels (either → pending): the wire's top-level `suggest_pending: true`
(editor), and a markdown `- [x] Suggest targets` block carrying no `Pick one` pick list / no
`No suggestions found` note (--suggest hasn't enriched it). When pending, triage logs a clear reason
and leaves the doc in pending-approval; once `--suggest` runs, the signal clears and it applies on the
next /inbox.

## Audio pairing keys on folder + stem, not stem alone (spec 034, T3.3)

WHY `check_audio` compares `(containing folder, stem)` pairs instead of bare stems
(v0.34.1): spec 034 / T3.2 made inbox discovery recursive, so a note like
`100 Inbox/Archive/memo.md` is discovered for the first time. Before this fix,
`md_stems` was built by dropping the folder entirely, so that unrelated Archive
note satisfied a root-level (or any other folder's) `memo.m4a`, `check_audio`
returned `False`, and `has_audio` (which gates the `transcribe` routing decision
directly) silently skipped transcription. The user drops a voice memo, a namesake
note exists anywhere else in the tree, and the transcript never appears — no
error, no explanation. Before T3.2 this was unreachable; after it, reachable on
any inbox with subfolders.

Only the audio-side stem is run through `sanitize_stem` before comparison; the
markdown side stays raw. This asymmetry is deliberate, not an oversight — Obsidian
already forbids the offending filename characters (`:` etc.) in note filenames,
while a recorder happily produces them (e.g. `Rec 2026-01-02 14:30.m4a` pairs with
`Rec 2026-01-02 14-30.md`). **Do not symmetrise or drop this sanitisation** — audio
to transcript sibling matching has already broken here once on exactly a raw `:`
vs `-` mismatch, and the consequence was an infinite transcribe loop.

## Force-Atomic items are resolved to their own note (spec 034, T4.1)

WHY `_extract_fan_items` / `_extract_fan_items_from_wire` resolve a path at all
(v0.35.0): `force_atomic_items[*]` is consumed by
`force-atomic-handling/SKILL.md`, which dispatches `inbox-analyst` against the
note the checkbox names. It used to rebuild that path as `<inbox_path>/<stem>.md`
— correct only while the inbox was flat, and a file that does not exist for every
subfolder note once discovery went recursive. The path now comes from here, where
the run's inbox listing is in scope, instead of being guessed at the far end of
the pipeline.

WHY `_resolve_fan_note` calls `attachment_index.narrow_candidates` instead of
narrowing for itself: these are the same problem (a wikilink that may or may not
be path-qualified, resolved against one listing), and a second derivation of one
rule is how PRD Business Rule 9 gets violated. The first version of this fix DID
hand-copy the rule, and it drifted inside the same commit — the copy stripped the
alias and the heading anchor but not the block anchor, so `[[Dresden^abc123]]`
failed against an index that plainly contained `Dresden.md`. Three copies existed
at that point (`resolve_attachments`, `_candidate_count`, `_resolve_fan_note`);
all three now route through the one helper. Sharing it also means the resolver
accepts the path-qualified `[[100 Inbox/Places/Dresden|Dresden]]` form T5.1 will
start emitting, for free.

WHY the `.md` suffix is a parameter of the shared helper rather than something
this site appends first: a note wikilink omits the extension, a file embed
carries it, so the two callers genuinely differ — but only in that one input.
The ORDER (strip the alias and anchors, THEN append) is part of the rule, not
part of the caller: appending first would search the index for
`Dresden|Alias.md`. Putting `default_extension` inside `narrow_candidates` keeps
that ordering in the one place that owns it.

WHY zero matches and two matches both decline rather than pick: with two
same-named inbox notes, `Source: [[Dresden]]` genuinely does not say which one is
meant, and first-match-wins would silently rebuild the collision this spec exists
to remove — writing a proposal from the wrong note's content. PRD Business Rule 7
governs: decline rather than choose. Zero matches means the note is gone (moved,
renamed, consumed), and inventing a path for it is where this defect started.

WHY the decline is printed to stderr with the `[triage]` prefix rather than
dropped: an approved item that is never built, with nobody told, is the same
class of defect as building the wrong one. The line names the review document,
the reference and the candidate count, so the user can rename a note or
path-qualify the link. Same channel, same prefix as the unresolved/ambiguous
attachment-embed reports above.

WHY the wire path prefers a suggestion's own `item_key` over resolution:
`suggestions-wire.schema.json` already requires it, and it is exact — two
suppressed suggestions sharing a stem stay two items, where any stem-keyed join
would collapse them. Only a daily `log_entries[]` entry, which carries just
`source_stem`, needs resolving; it joins to a suggestion of that stem when
exactly one exists (keeping #165's invariant that the daily-log path and the
suggestion path yield one identity) and falls back to the listing otherwise.
Deduplication moved from the stem to the resolved path for the same reason.

## The Run's Kado Cost Is Observed, Never Declared (spec 034 T6.1)

`_count_kado_calls` used to open with the literals `2 + 7`: two base calls (the
one recursive listDir plus the `listNotes(fields=["links"])` embed extraction)
and seven `search_by_frontmatter` queries. Both now come from the client's own
round-trip counter (`kado_client.observed_call_count`).

WHY the literals had to go: T6.1 writes the base figure into a permanent cost
history, and a history whose source is a constant records the intent, not the
behaviour. The Phase-3 gate proved it — with a second base listing reintroduced
by hand, the fake client recorded 3 base calls while the estimator still
printed `kado_calls=9`. The `7` is exactly as exposed: `query_frontmatter`
makes seven unconditional calls, and nothing tied the formula to that number.

WHY a dedicated counter on `KadoClient` and not `_req_id`: `_req_id` is a
JSON-RPC request identifier whose meaning the client does not own, so keying a
permanent record to it breaks silently the moment anything else increments or
resets it. `_call_tool` is the sole choke point every read, write, search and
graph-audit passes through, so nothing can escape the count.

WHY three snapshots rather than one read at the end: the counter is one
lifetime total across `discover_files` → `resolve_inbox_attachments` →
`query_frontmatter` → per-item reads, and a running total cannot be decomposed
after the fact. Reading it once yields one number where the history's schema
needs two. `_calls_between` closes out the base after
`resolve_inbox_attachments` and byFrontmatter after `query_frontmatter`, and
both ride out on `TriageState` — the same shape, for the same reason, as
`tag_handler_reads` and `wire_sibling_reads`.

WHY a client that keeps no count leaves both at 0 rather than raising: an old
fake, or any compatible client, must produce an unmeasured run, never a failed
one.

## `DOWNSTREAM_COST_ENTRY_ACTIONS` — the Guard That Fails Loudly

Every triage run appends exactly one cost-history entry. `suggest` and
`fan-resolve` defer theirs to `suggestions-reducer.py`, which runs *after*
triage has written `routing-plan.json` — the destination-folder counts do not
exist yet when triage finishes, and the reducer is the process that measures
them.

WHY the guard is named and asserted rather than implied: every other plumbing
gap in this task no-ops silently. This one **double-appends** — an incomplete
entry from triage, then the real one from the reducer — so the test asserts a
`suggest` run produces exactly one entry, not two.

WHY `idle` records at all: an idle run still spends its base and byFrontmatter
calls, and a history that omits them cannot show what idling costs.

WHY `metrics` gained `item_count` and `base_kado_calls`: the reducer reads both
back out of `routing-plan.json` rather than re-deriving its own, so `suggest`
and `idle` cannot end up counting different things.
