# WHY: lib/render_actions.py

> Rationale for decisions in `tomo/scripts/lib/render_actions.py`.
> Instruction-set action builders: turns the rendered manifest, confirmed
> items, and daily/skip inputs into the ordered `actions[]` list. Only
> non-obvious decisions are recorded here.

## `_asset_dest_join` Exists Because Neither Existing Path Helper Is Safe (spec 031)

WHY a third destination-join helper instead of reusing `_dest_join` or
`_ensure_md_extension`: both exist for NOTE paths, and both actively corrupt
an attachment path.

- `_dest_join` hardcodes a `.md` suffix (`f"{folder}{sanitize_stem(stem)}.md"`)
  — an attachment keeping its own extension (`.jpg`, `.m4a`, …) would come out
  as `karte.jpg.md`.
- `_ensure_md_extension` is the more dangerous trap because its failure mode
  looks like success on the obvious test case: for an extension already in
  `KNOWN_FILE_EXTENSIONS` (`lib/file_extensions.py`) — `.jpg` included — it is
  a silent NO-OP (`foto.jpg` → `foto.jpg`), so a fixture built around `.jpg`
  proves nothing. For any extension NOT in that allowlist — `.heic`, `.docx`,
  `.arw`, anything a phone or scanner produces that the note-path allowlist
  never anticipated — it silently appends `.md` (`scan.heic` → `scan.heic.md`).
  An earlier draft of this spec's own SDD had the hazard backwards (claimed
  `_ensure_md_extension` corrupted `.jpg` and no-op'd on everything else); the
  measured behaviour is the opposite. This is why `test_031_t2_1_asset_dest_join.py`
  pins the regression with `scan.heic`, not `.jpg` — the `.jpg` case cannot
  distinguish "safe" from "silently broken".

`_asset_dest_join` also does NOT run the basename through `sanitize_stem`
(unlike `_dest_join`): an attachment's filename already exists on disk and
the embed referencing it resolves by that exact name — rewriting it (even to
replace an Obsidian-forbidden character) would break the very embed the
feature exists to keep working.

`_asset_dest_join` raises `ValueError` when the source path has no basename
(empty, or ending in `/`) instead of silently returning a bare folder path.
This is reachable, not theoretical: `build_inbox_index` indexes a malformed
`listDir` entry like `{"path": "100 Inbox/Images/", "type": "file"}` — Kado
mistyping a folder as a file — under the key `""`, and `resolve_attachments`
returns index values verbatim, so a bad entry can reach this function.
`_check_path_shape` (the wire-level path validator, `:378`) has no basename
check, so nothing downstream would have caught a bare-folder destination
before it reached Hashi as an instruction to move a file *to* a directory.
`_build_move_asset_actions` catches the `ValueError` and routes that one
attachment through the same skip-and-report path as a destination collision
(below) rather than letting it abort the whole render.

## Global Dedup, Not Per-Item (spec 031)

WHY `_build_move_asset_actions`'s `seen` set spans the WHOLE manifest instead
of resetting per manifest entry, unlike the `audio_peer` precedent at `:927`
(`{mn.get("audio_peer") for mn in moves if mn.get("audio_peer")}`, which
dedups within one ORIGIN-STEM GROUP): an audio peer belongs to exactly one
origin note by construction, so per-group dedup is correct there. An
attachment has no such constraint — two entirely unrelated notes can embed
the same image — and PRD Feature 4 requires exactly one `move_asset` for it
regardless of how many notes embed it. Keying the `seen` set on the resolved
FULL PATH (never the basename) matters independently of dedup scope: two
different files sharing a basename in different folders must NOT collapse
into one entry (that is the destination-collision case below, a different
outcome). Tests exist for both failure directions — basename-keyed dedup and
per-item-scoped dedup — because each fails silently (no exception, just a
wrong count) if reintroduced.

## Destination Collision: Skip and Report, Never Overwrite (ADR-3)

WHY a destination-claim map (`claimed: dict[destination -> path]`) rather than
letting a second attachment silently overwrite the first at apply time: two
DIFFERENT source files can share a basename in different subfolders
(`Images/karte.jpg` and `Scans/karte.jpg`), and the flat asset folder gives
both the same destination filename. ADR-3 chose skip-and-report over
renaming (a Should-have, deferred) or failing the whole run: the first claim
wins, the second is skipped, printed as a `[warn]` to stderr, and returned in
`_build_move_asset_actions`' second return value (see below) so the user
sees it in the rendered document, not just in a log they may never read.

## `_build_move_asset_actions` Returns `(actions, skipped)`

WHY the function returns a tuple instead of always emitting an action (with
an `error` sentinel to be filtered post-hoc, the `filter_unappliable_relationships`
pattern used elsewhere in this codebase): that pattern exists because the
add_relationship failure (a missing or non-markdown child note) is discovered
at a LATER Kado-resolution step, after the action has already been built —
sentinel-then-filter is the only way to surface it. `_build_move_asset_actions`
knows whether an attachment is filable (basename present, no collision) at
build time, before it ever constructs an action dict, so it can simply not
emit the bad one and return the reason directly — no sentinel field ever
needs to reach (and then be stripped from) an action shaped for the wire.
`build_actions()` propagates this as its own second return value,
`skipped_assets`, which is why its signature changed from `-> list[dict]` to
`-> tuple[list[dict], list[dict]]` — every existing and new caller unpacks
the tuple.

`concepts.asset` is read via `cfg.get("concepts.asset", DEFAULT_ASSET_FOLDER)`,
not `cfg["concepts.asset"]` (unlike `cfg["concepts.inbox"]`, read by bracket
access a few lines above it): bracket access would `KeyError` on every
pre-existing test across the suite that builds a bare `cfg` dict for
`build_actions()` without that key — ten-plus call sites, most outside this
module's ownership. `DEFAULT_ASSET_FOLDER` is a module constant here
(`"Atlas/290 Assets/295 Attachments/"`) so `instruction-render.py`'s
`CONFIG_DEFAULTS["concepts.asset"]` can reference the SAME value instead of
restating the literal — two independent layers (`load_config()` for real
profile loads, this `.get()` for hand-built test cfgs) sharing one source of
truth rather than two copies that could silently drift apart.

## ADR-5 Makes an Attachment `delete_source` Structurally Impossible

WHY `_build_move_asset_actions` needed no `delete_source` guard code at all,
unlike `audio_peer` (which required an explicit exclusion elsewhere):
`_build_delete_source_actions` only ever reads `move_notes` (the list
`_build_move_note_actions` returns) as its source-of-truth for which origins
to delete — it never sees the manifest, and attachments never ride the
`move_note` action (ADR-5's `attachments` field lives only on `move_asset`,
built by a wholly separate function). There is no code path by which an
attachment path could reach `_build_delete_source_actions` at all, so ADR-6
("an attachment move never implies a deletion") holds by construction, not by
a filter someone could forget to update. `tests/test_031_t2_2_move_asset_emission.py`
pins this at the `build_actions()` level rather than merely assuming it —
mutation-tested by temporarily emitting a leaked `delete_source` for an
attachment path and confirming the test catches it.

## Every Inbox Path Goes Through One Resolver (spec 034 T5.0)

WHY the five sites that used to compose `<inbox>/<stem>` inline now all call
`render_helpers.resolve_source_path`: the composition was correct only while
inbox discovery ran at `depth=1`, which guaranteed every note sat at the inbox
root. Phase 3 made discovery recursive and removed that precondition — but not
the code, in four files that never adopted `item_key`. Five separate spellings
of the same assumption is how the same defect survives four task-level reviews:
each diff is locally correct and none of them shows the assumption.

The resolver takes `item_key` (the vault-relative path, verbatim — ADR-1) and
falls back to the reconstruction only when no key is present, so a suggestions
document produced before spec 034 still renders exactly as it did. Verified by
comparison against the pre-change builder: for a keyless input the emitted
action list is byte-identical; with a key, the action count and every action's
key set are unchanged and only path VALUES move (CON-4 — a correctness fix, not
a shape change).

`audio_peer` deliberately uses `resolve_sibling_path`, not `resolve_source_path`:
`item_key` is the note's path, and the audio file is not the note. Triage pairs
audio to a transcript by containing folder plus stem
(`inbox-triage.check_audio`), so the peer's folder is the note's folder — the
inbox root is wrong for it whenever the note is not at the root.

The tag-handler group site (source 4 of `_build_delete_source_actions`) routes
through the resolver too even though its `source_paths` are vault-relative by
contract and the fallback can never fire. One rule for every inbox path in the
module means there is no second spelling left to drift.

## `:967` Is the Site That Could Delete the Wrong Note (spec 034 T5.0)

WHY the daily-only `delete_source` gets a comment when the other four do not:
it is the only one of the five that emits a DELETE for a note the run never
rendered, and it had no bare-stem guard at all — it composed the inbox root
unconditionally. Reachability was established with a fixture before the fix
rather than assumed: a subfolder note whose content is fully captured in a
daily note produces exactly one `delete_source`, and on both parser paths it
named `<inbox>/<stem>.md`. With a same-named note at the inbox root that the
run did not include (one left over from an earlier run, say), that action names
the root note. Hashi executes instruction sets, so this is a wrong delete at
the CON-4 boundary.

A daily-only item gets no per-item section, so the display stem is the only
thing the rendered document carries for it — which is why its identity is
recovered from the structured doc rather than from the markdown
(`suggestion-parser.enrich_daily_updates_with_item_keys`).

## The Delete Bookkeeping Joins on the Note, Not the Filename (spec 034 T5.0b)

`_build_delete_source_actions` joins three inputs that describe the same inbox
note in three different spellings — a confirmed item (`source_path`, display
text), a move_note origin (`source_inbox_item`, already a resolved path) and a
daily entry (`source_stem`, display text). Six collections carried that join:
`confirmed_stems`, `expected_by_stem`, `keep_source_stems`, `seen`,
`daily_stems`, `moves_by_origin`. All six keyed on the bare filename stem, and
recursive discovery (Phase 3) lets two notes in different inbox subfolders
share one. Each collection therefore collapsed two distinct notes into one
bucket. They now key on `_origin_key` — the resolved vault-relative path
(ADR-1), which is per note.

`_origin_key` strips a trailing `.md` and nothing else. That is not cosmetic:
the three inputs disagree about exactly that one extension (a confirmed item's
`source_path` carries it, a daily entry's `source_stem` does not, a move_note
origin has been through `_ensure_md_extension`), and they must still land in
one bucket. Every other extension is significant — an `.m4a` origin and an
`.md` note of the same name are different files, and the old `_stem` (which
also stripped only `.md`) already treated them as such. Preserving that is what
keeps a `keep_source` on a voice source from suppressing a same-named note's
delete.

### What the OQ6 Denominator Now Counts

`expected_by_key` is the completion gate's denominator: the gate holds a
`delete_source` back until every approved atomic for an origin is represented
in `move_notes` (OQ6 / PRD/A9). It now counts **the approved atomics of one
specific note, identified by its path** — not of every note sharing that
filename.

That is the meaning the gate was always reaching for. The gate exists to answer
one question about one file: *is everything I am about to delete already
captured somewhere else?* A namesake in another inbox folder is a different
file, and how many atomics it produced, or whether they rendered, says nothing
about whether this one is fully captured. Sharing a denominator got that wrong
in both directions, and neither was a rounding error:

- **Under-count → permanent defer.** Two namesakes, two atomics from A (both
  rendered) and one from B (dropped before rendering): the shared denominator
  read 3 against a shared bucket of 2 moves, so `2 < 3` deferred — and it
  deferred A's delete, which was complete, on the strength of B's incomplete
  work.
- **Coincidental pass.** Two namesakes with one atomic each: the denominator
  read 2 against a bucket of 2, the gate passed, and `moves[0]` emitted a
  single delete — one origin deleted, the other silently left behind.

The re-key was not made to turn a test green; the two tests that pin these
(`test_oq6_denominator_counts_this_notes_atomics_only`,
`test_two_confirmed_namesakes_each_get_their_own_delete`) assert the meaning
above, and the emitted count differs from the old behaviour in both.

### The Reason Strings Are Part of the Fix, Not Cosmetics

Under CON-2 the user approves on what the rendered document says, so a reason
that is wrong about *which* note did what is a wrong basis for approval even
when the resulting action is safe. Two strings were:

- `"Origin consumed by N atomics."` named A while one of those atomics came
  from B (`moves_by_origin`).
- `"+ daily"` credited A with B's daily capture (`daily_stems`).

Both now derive from the same per-note key, so each names the note that caused
it. `test_daily_suffix_still_fires_for_the_note_that_earned_it` is the positive
control: re-keying must not make the suffix unreachable, only correctly
attributed.

### Fail-Safe Before, Correct Now

Every direction of the old collapse failed *safe* — the second note's source was
left undeleted and re-proposed next run; the wrong note was never deleted. That
is why T5.0 deliberately left this alone: re-keying the completion gate changes
that gate's logic, which is a behaviour change rather than an addressing fix,
and it did not belong inside a task about addressing. It is recorded here so
the reason the old code looked defensible is not lost: it was not a latent
data-loss bug, it was lost cleanup plus a mis-described review document.

### Reachability Dictated How Each Case Is Driven

`tests/test_034_t5_0b_delete_bookkeeping_item_key.py` drives the two
confirmed-namesake cases by calling `_build_delete_source_actions` directly,
because they are wire-path-only today: the `#116` filter
(`render_resolve.filter_missing_source_notes`) drops two confirmed items
carrying templates on the markdown path before `build_actions` ever runs. Put
through a markdown-path fixture those cases never reach the function and pass
vacuously against broken code. The two daily-entry cases are live on both
parser paths — T5.0 recovers `source_item_key` from the suggestions doc for
markdown and wire alike — so both are parametrised over both paths, and each
asserts the keys actually arrived before asserting the deletes.

### The Paired Consumer Collapsed Too — Closed by T5.0c

`instructions-diff.py`'s `derive_expected()` — its `confirmed_stems` set and the
`daily_only_seen` collision check inside it — derived the EXPECTED
`delete_source` count with the same shape this section removes: both were
stem-keyed, so a daily-only namesake's expected deletion was suppressed by a
same-named confirmed item. Two of the four cases above (the daily-only pair, and
confirmed-plus-daily-only) emitted one more `delete_source` than that module
expected, so `/inbox` reported count drift on a correct instruction set.

Why the old code looked defensible: its own `NOTE` called the stem key a
"residual collapse point until T2.3b" — a deliberate, dated deferral to a real
task. T2.3b had since landed, and nothing re-read the comment when it did, so a
stale justification kept reading as a live one.

T5.0b left it out deliberately rather than by oversight: it is a second module
with its own key semantics, and a mechanical copy of `_origin_key` breaks there.
The emitter always holds `inbox_path` and resolves every key to one canonical
spelling before comparing, so plain equality is correct here; the differ has no
`inbox_path` and must reconcile a full `item_key` against a bare `source_stem`
that names the same note. T5.0c closed it with `_same_note_as_any` — `_keys_match`
applied in both directions — rather than a set dedup. See
`docs/tomo/scripts/instructions-diff.md` (0.15.0).

## The Pass-2 Destination Guard (spec 034 T5.3)

`validate_destinations` is the binding half of PRD Feature 7. Pass 1
(`suggestions-reducer.resolve_destination_clashes`) proposes a distinct name
when two items would land on one path, but ADR-4 makes that advisory: the user
edits the suggestions document *after* Pass 1 has rendered, so nothing it
proposed can bind. This pass runs after `build_actions`, over the whole
assembled action list, and is the last point at which two `move_note` actions
claiming one destination can be stopped before Hashi executes them.

### Why Both Claimants Are Dropped

`_build_move_asset_actions` is the reporting shape this follows and the
resolution is deliberately inverted. There, the first attachment keeps the
destination and the second is skipped, because nothing is lost by skipping a
duplicate file — the note that embeds it still resolves. Here both names were
set by the user, so choosing between them would itself be a guess, and letting
emission order pick the loser leaves an approved item unfiled with no record of
why (ADR-4).

The two behaviours look alike in code and differ in exactly the place that
matters: `for claimant in claimants` versus `for claimant in claimants[1:]`. A
shape copied without noticing the inversion ships a guard that keeps one
claimant — a silent overwrite wearing the appearance of a working guard. Test
`test_two_items_claiming_one_destination_lose_both_moves` exists for that one
character; reverting it turns fourteen tests red.

### A Dropped Move Takes Its Paired Delete With It

This is the trap the task did not name and the reason the guard is not a pure
filter. `_build_delete_source_actions` emits `delete_source` for every origin
its atomics fully consume, plus one for the origin's audio peer. Dropping the
move while leaving those deletes would remove the user's inbox note *and* its
audio while refusing to file the rendered atomic — the guard would cause the
loss it exists to prevent, and on the CON-4 boundary where Hashi acts.

So the pass withdraws, for each dropped move, the `delete_source` whose
`source_path` is that move's `source_inbox_item` or `audio_peer`. The join is
the resolved vault-relative path (ADR-1), not a bare filename, so a namesake in
another inbox folder that the user explicitly marked for deletion keeps its own
delete.

`withdrawn_deletes` on the report names the deletes that were **actually**
removed, not every path a dropped move touched. An item the user marked "Keep
source files" has no paired delete, so listing its origin there would make both
the rendered report and the coverage audit claim a withdrawal that never
happened. The list is filled in after the filtering pass, from what the filter
actually took out.

The withdrawal is also correct for a *partial* drop. An origin with two atomics
of which one clashes is no longer fully consumed, which is exactly the
condition the OQ6 completion gate defers on (`len(moves) < expected`). The
surviving atomic is still filed; the origin keeps its source.

`link_to_moc` actions for a dropped note are deliberately **not** removed. The
bullet lands on the parent MOC as an unresolved forward link, which Obsidian
renders as such and which resolves the moment the user renames and re-applies.
Removing them would need a title join, and a third item filed to a different
folder under the same title would be dropped with them — a real loss traded for
a cosmetic one.

### The Vault Half Reads a Listing, Never a Probe

`make_folder_listing` issues one `list_dir(folder, depth=1)` per distinct
destination folder, cached for the life of the closure. This is not a style
preference. A per-name `note_exists` probe answers with whatever Kado's own
case semantics decide, and CON-7 forbids this spec from running against a live
vault to find out what those are — so a probe would make the guard's
correctness depend on an unmeasured behaviour. A listing returns the folder's
real filenames, which puts the fold in Tomo where a test can reach it, and
carries the vault's own spelling for the report.

It is the twin of `suggestions-reducer._vault_folder_notes`, which serves the
Pass-1 proposal: both compose through `_dest_join` and fold the same way, so the
proposal and the guard cannot disagree about what "the same place" means. They
are duplicated rather than shared on purpose — `docs/XDD/backlog.md` schedules
the extraction of the whole clash surface into a `lib/` module after Phase 5
closes, when T5.2, T5.3 and T5.4 have all landed, and moving the ground
mid-phase is what that entry declined.

The cache key is the folder `_dest_join` derives, not the raw string. T5.2
shipped a raw-`location` cache and fixed it in `00eb712`, where a trailing slash
listed one folder twice. The pass itself derives the folder from the already
composed destination, so it cannot reach `make_folder_listing` with an
unnormalised spelling — which is why
`test_one_listing_per_folder_however_the_folder_is_spelled` asserts on the
closure directly. Driven through the pass, that test passed against a
raw-keyed cache: it was vacuous, and the mutation sweep is what found it.

Kado failing is not a collision. An unreachable folder reads as empty, so the
vault half degrades and the run-internal half keeps working (ADR-4). The
alternative — treating an error as a clash — would drop two legitimate moves on
a transport blip.

### Folding Is Fail-Safe, Not a Claim About the Filesystem

Destinations compare `casefold()`-equal (CON-6). `casefold()`, not `.lower()`:
these are German notes and `ß` folds to `ss`, which `.lower()` leaves alone —
`Strasse` and `Straße` are one file on a folding filesystem and would otherwise
both be emitted.

CON-6 records this host as case-insensitive, verified. Tomo is not only run
here, and on a case-sensitive filesystem `Dresden.md` and `dresden.md` really
are two files, so folding invents a clash — and ADR-4 drops both claimants, so
a false positive costs two legitimate moves. Fold anyway, because the two
errors are not comparable: not folding on a folding filesystem loses a note
silently and unrecoverably; folding on a case-sensitive one costs a rename the
user can see and undo. CON-7 forbids resolving this by measurement, so the
asymmetry is the reason, not a guess about what is underneath.

Only the comparison folds. Every destination the report displays keeps the
casing its author wrote — the claimants' as the user named them, the vault's as
the vault holds it — and a case-only clash SAYS the difference is case. On a
case-sensitive filesystem those are two visibly different names, and "duplicate
name" alone would read as a bug in Tomo rather than a warning.

### The Report Leads the Document

`render_md` puts the clash block **first**, before every action section. Every
other report in that file is a skip the user can act on later; this is the only
place where an item the user approved was deliberately not filed, so it must be
read before the action list rather than after it. It names both claimants by
their source notes, states that those sources are untouched in the inbox, and
says the remedy: rename one and re-run Pass 2, no need to restart the run.

The same list reaches `instructions.json` under the permissive `tomo` block, so
Hashi ignores it and the wire schema is untouched (CON-4). Metadata only: ids,
titles, paths and the reason — never note content.

### The Paired Consumer, Fixed Here Rather Than Deferred

`instructions-diff.derive_expected` counts an expected `move_note` per confirmed
item and an expected `delete_source` per non-kept origin. A withheld move is
neither, so before `_subtract_destination_clashes` the audit reported
`RESULT: FAIL — count or coverage mismatch` on a **correct** instruction set:
`move_note 2 → 0`, `delete_source 2 → 0`, and `file=[MISSING]` against both
items. `synthesis-conductor.md` step 3e makes that fatal — STRICT, stop, report
the diff verbatim — so a clash would have halted the run with a message
blaming Tomo for drift instead of naming the clash.

T5.0b deferred an equivalent divergence to T5.0c and was right to: that one
pre-existed its diff. This one does not — the withholding is what T5.3 adds, so
the expectation it invalidates is T5.3's to repair. The subtraction mirrors
`_subtract_skipped_daily`, and the audit now emits a note naming how many moves
were withheld and pointing at the `Not filed` section.

The move join is `_keys_match`, not set membership: a clash entry's
`source_inbox_item` is the inbox-joined path a rendered action carries, while
`by_item`'s key comes from `confirmed_items` and is never inbox-prefixed — the
same asymmetry T5.0c had to respect one function over. Deletions match on the
raw path first and the bare stem second, because `derive_expected` appends an
audio peer under its full path and an origin under its stem.

### Found While Sweeping, Deliberately Not Fixed

A repo-wide grep for destination composition (`_dest_join`, `_asset_dest_join`,
`"destination":` writes) and claim tracking (`claimed`, `by_dest`, `seen`,
`used_filenames`) turned up three sites this guard does not cover. None is
fixed here; each is recorded so the next task does not have to re-find it.
**(1) and (3) were folded together by T6.0 — see "Three Keys Folded, One Left
Exact" below. (2) is still open and is now T6.0b.**

1. **`_build_create_moc_actions`'s `by_dest` compares destinations by exact
   string.** — **CLOSED by T6.0.** Two approved MOC proposals named
   `Travel (MOC)` and `travel (MOC)` in one folder both emit a `create_moc`,
   and the second overwrites the first on apply — dropping the first's
   children, which is the `#67` failure that guard was written for. The guard
   is real; it just does not fold, and CON-6 says this filesystem does.
   `validate_destinations` does not close it: it groups `move_note` only.
2. **An atomic and a MOC can compose the same destination** — an atomic named
   `Travel (MOC)` filed into the MOC folder. `_build_create_moc_actions` dedups
   create_moc against create_moc, `_build_move_note_actions` has no guard at
   all, and Pass 1's check compares atomics against atomics. T5.2 recorded this
   in `docs/tomo/scripts/suggestions-reducer.md`; T5.3's brief does not cover
   it either. Dropping a `create_moc` cascades into the `link_to_moc` and
   up-preservation actions that target it, which is a behaviour change, not an
   addressing fix.
3. **`render_resolve.py:213`'s `create_moc_by_dest`** keys the same composed
   destination by exact string. — **CLOSED by T6.0, in the same change as
   (1).** It is a paired consumer of (1) and would need the same treatment if
   (1) ever folds.

## An Attachment Clash Keeps Its Note in the Inbox (spec 034 T5.4)

`suppress_moves_for_unfiled_attachments` is the second post-pass over the built
action list, sibling to `validate_destinations` and wired beside it in
`instruction-render.py`. It **reverses spec 031 T2.4**
(`docs/XDD/specs/031-inbox-attachment-filing/plan/phase-2.md:85`), which
required that an attachment collision leave the note's own move alone. That
phase-2 line is left intact as the historical record; the reversal is recorded
here and in the inverted test's module docstring
`[ref: PRD/Feature 8, SDD/ADR-6]`.

WHY the reversal: a note filed into the permanent collection while the file it
embeds stays in the inbox depends on that file indefinitely. Moving a note does
not carry its attachments, and nothing is ever moved that was not instructed —
so "next run will file it" is false. T2.4's decision was correct while a flat
inbox made a basename clash unreachable; recursive discovery made it reachable.

### WHY a Post-Pass Rather Than an Inline Suppression

Inside `build_actions`, `_build_move_asset_actions` runs *before*
`_build_delete_source_actions`. The paired `delete_source` for a note's origin
and its audio peer therefore does not exist yet at the moment an attachment is
skipped, so an inline suppression has nothing to withdraw. Dropping the move
and leaving the delete standing is strictly worse than the bug being fixed: the
note stays in the inbox and its source is deleted anyway, losing the note
outright instead of filing it incompletely. The post-pass sees the finished
list and can withdraw both.

### WHY the Skipped Entry Carries `owner_source_items`

A skipped entry was `{"source", "destination", "reason", "kind"}` — nothing on
it named the note that embedded the attachment, so a post-pass receiving it
could not tell which move to suppress. The owner is recorded as the note's
**resolved source path**, derived through `resolve_source_path` +
`_ensure_md_extension`, exactly as `_build_move_note_actions` derives
`source_inbox_item`. One derivation, one helper: composing `<inbox>/<stem>.md`
by hand is what T5.0 caught silently dropping every subfolder note in Pass 2,
and here it would suppress the wrong note — proven by reverting the join to a
stem composition, which files the real owner (`100 Inbox/Reise/Elbe.md`) and
suppresses an unrelated root-level namesake (`100 Inbox/Elbe.md`) instead.

It is a **list**, not a single key: the global `seen` dedup examines each
attachment path once, but several notes can embed that one path. A link
recording only the first note leaves the others filed with an embed pointing
into the inbox — the same residue, one note over.

The field is invisible to both existing `skipped_assets` consumers:
`render_md.py` renders `source`/`reason`/`kind`, and `instruction-render.py`
projects `source`/`destination`/`reason` into the JSON. Neither changes.

### WHY the Withdrawal Mechanism Is Shared, Not Copied

`_paired_delete_candidates` and `_drop_moves_with_paired_deletes` were
extracted from `validate_destinations` and are used by both passes. The two
drop moves for different reasons and report them separately, but the withdrawal
itself is one behaviour. A second copy is the duplication `docs/XDD/backlog.md`
records twice for this file, and the drift a second copy produced in
`instructions-diff` cost T5.0c a task of its own.

`withdrawn_deletes` names deletes that actually existed. A `keep_source` item
has no paired delete, so listing its origin would make both the document and
the coverage audit claim a withdrawal that never happened — the over-claim T5.3
shipped and fixed in `76ae8be`.

### WHY the Two Passes Compose Without Double-Counting

`instruction-render.py` runs `validate_destinations` first and the attachment
pass over its output. A move that pass already dropped is simply absent, so it
is never withheld or reported twice, and its already-withdrawn delete cannot be
counted again. Suppressions whose `dropped` list is empty are not returned at
all: the attachment itself is already reported through `skipped_assets`, and an
empty entry would render a section heading over nothing.

### WHY Its Own Section in `instructions.md`

"Two items claim one destination" is fixed by renaming a **note**; "its
attachment could not be filed" by renaming a **file**. Under CON-2 the user
approves on what that document says, so a reader who cannot tell the two apart
cannot act on either. Hence a separate `## Not filed — an attachment could not
be filed with it` section rather than a second bullet kind under the clash
heading.

### The Paired Consumer, and a Pre-Existing FAIL Closed Here

`_subtract_destination_clashes` was renamed to `_subtract_withheld_moves` and
is now called for both withholding lists — one function over both, for the same
reason the emitter shares one withdrawal.

Measured on HEAD before this change, a skipped attachment **already** produced
`RESULT: FAIL` on a correct instruction set: `derive_expected` counts one
expected `move_asset` per distinct attachment path on the confirmed items,
while `_build_move_asset_actions` deliberately emits none for a refused one
(`move_asset expected=2 actual=1 [DIFF]`). That gap dates to spec 031 and was
unreachable until recursion made a basename clash possible. It is closed here
by `_subtract_skipped_assets`, not because T5.4 caused it, but because T5.4
makes the clash a normal outcome and `synthesis-conductor.md` step 3e halts the
run on a diff mismatch — a guard whose own audit stops the run is not
shippable.

### Found While Sweeping, Deliberately Not Fixed

The T5.3 sweep above listed three exact-string destination sites. The same grep
run against the **attachment** half turns up a fourth, previously unlisted:

4. **`_build_move_asset_actions`'s `claimed` dict keys on the exact destination
   string.** — **CLOSED by T6.0; see "Three Keys Folded, One Left Exact"
   below.** `100 Inbox/A/Ufer.jpg` and `100 Inbox/B/ufer.jpg` compose two
   different keys, so both emit a `move_asset` into the flat asset folder and
   the second overwrites the first on a case-insensitive filesystem (CON-6) —
   with no skip recorded, so T5.4's suppression never fires and both notes are
   filed. Same shape as (1) and (3), one function over. Not fixed here:
   folding this key changes which attachments are skipped, which changes what
   T5.4 suppresses, and that is a behaviour change rather than the join this
   task is about.

### An SDD Inconsistency, Recorded Not Resolved

`solution.md`'s "Complex Logic: the destination validation pass" walkthrough,
step 3, says that on an attachment clash "**neither** is emitted, and each
suppresses its own note's move". PRD Feature 8's second acceptance criterion
says the opposite and the plan repeats it: "the first note and its attachment
are filed normally — one note's clash does not hold up the other". The PRD is
the requirement of record and is what the code does; the attachment guard stays
first-claim-wins and only the refused claimant's note is held back.

## A Withheld Move Takes Its MOC Bullets With It (spec 034 T5.5)

Found by reading the rendered instruction document as prose, after 3596 tests
and six review gates had passed. Both Dresden moves were withheld by
`validate_destinations`, and the document still instructed the user to add
`- [[Dresden]]` to `Travel (MOC)` — a bullet pointing at
`Atlas/202 Notes/Dresden.md`, a path this run had just guaranteed would hold
nothing. The guard exists to stop one note overwriting another; it was writing
a dead link instead. T5.3 shipped naming this exact risk as the assumption its
diff could not verify ("that `link_to_moc` bullets for a dropped note are
harmless"); the T5.5 document is the counter-example.

### WHY Withdrawal, Not a Separate Report

The alternative was to leave the bullet and warn about it. That fails the
user's actual workflow: they apply the checklist top to bottom, and a warning
elsewhere in the document does not stop a checkbox from being ticked. It also
contradicts what the section already promises — "no move was emitted for the
items below, deliberately" — while emitting the move's consequence. Withdrawal
is the same treatment the paired `delete_source` already gets, for the same
reason: an action that only makes sense alongside a move must not outlive it.

### WHY the Join Is the Title, Not the Path (and Why That Is Not the ADR-1 Trap)

Everywhere else in this module an item is addressed by `item_key` / resolved
path, never by display stem — a stem is shared by two notes in different inbox
folders. A `link_to_moc` is the one exception, and deliberately: `_emit` dedups
by `(target MOC, source title)`, so one bullet can have **several** authors and
there is no single origin path to join on. Title is not a weaker proxy for the
link's identity here; it *is* the link's identity, the key it was minted under.

`_orphaned_link_titles` therefore withdraws on "no surviving author", not on
"some author was dropped": the dropped titles minus the titles still written by
a surviving `move_note` or `create_moc`. That subtraction is what answers the
question the brief asked — can a `link_to_moc` legitimately exist for a note
with no move? Yes, three ways, and each is protected by it:

1. **A `create_moc`'s own parent bullet.** A new MOC has no `move_note` at all.
   Blanket "no move ⇒ withdraw" would strip the up-link of every new MOC in
   every run that also happened to hit a clash.
2. **The garden-audit branch.** `build_garden_audit_actions`' `file_note`
   emits a `link_to_moc` for a note **already in the vault** and no `move_note`
   whatsoever. `validate_destinations` runs over that branch too.
3. **A surviving namesake.** A `create_moc` titled `Dresden` can be the
   remaining author of `- [[Dresden]]` after two atomic notes of that name
   clash with each other. The bullet stays; it now describes only the MOC.

### WHY It Lives in `_drop_moves_with_paired_deletes`

Both post-passes withhold moves, and the withdrawal is one mechanism with two
callers — the shape T5.0c had to repair one module over after a second copy
drifted. `_links_for` splits the run's withdrawn bullets between the two
reports on the same title key they were withdrawn under, so the two can never
disagree about which bullet belongs to which section.

### The Paired Consumer

`instructions-diff.derive_expected` counts one expected `link_to_moc` per item
per parent MOC. Withdrawing a bullet without subtracting it makes the audit
report `RESULT: FAIL — count or coverage mismatch` on a correct instruction
set and halts the conductor. `_subtract_withheld_moves` now subtracts the
withheld item's own `expected_links` alongside its `move_note`.

That subtraction was already owed **before** this change: two same-titled items
under one MOC expect 2 bullets and emit 1 (the emitter dedups, the audit does
not), so the pre-fix scenario failed the audit as well — a latent FAIL the
clash path had never exercised, because every existing fixture built its items
with `parent_mocs: []`. Deriving the subtraction from `expected_links` rather
than from the emitter's `withdrawn_moc_links` report lands correctly on both:
drop one of two authors and 1 is subtracted while the shared bullet survives;
drop both and 2 is subtracted while the bullet goes.

`withdrawn_moc_links` is still recorded on each report — it is what
`render_md` conditions its "withdrawn with it" sentence on, and it makes the
withdrawal visible in `instructions.json`. The audit deliberately does not read
it: an audit that trusts the emitter's account of itself is not an audit.

## The Vault-Collision Sentence Names Two Paths Only When They Differ (spec 034 T5.5)

`_destination_clash_reason`'s single-claimant branch rendered "a note already
exists at `Atlas/202 Notes/Elbe.md`, where this run would file
`Atlas/202 Notes/Elbe.md`". The two-path form was written for the case-only
collision (the vault holds `elbe.md`, the run would file `Elbe.md`), where the
user must see both spellings to know which name the vault actually holds. On an
exact match — the common case — it names one path twice and reads like a
rendering bug, which costs the sentence its credibility exactly where it is
asking the user to go rename something.

The branch keys on `vault_note == claim_dests[0]`, not on the `case_only` flag.
The flag is computed from a spelling count and answers a related but different
question; the sentence's own condition is whether it is about to print the same
string twice, so that is what it tests.

## A MOC Bullet Outlives the Run That Wrote It (spec 034 T5.5)

`link_to_moc`'s `line_to_add` was `- [[Dresden]]`. Unlike every other line in
the instruction document, this one is written **into the vault** and stays
there. It resolved on the day it was applied, because the destination guard had
withheld the two other Dresden claimants and only one Dresden existed.

It stops resolving the moment the user does what the guard's own report tells
them to do: rename one withheld claimant and re-run Pass 2. The other claimant
then files as `Atlas/202 Notes/Dresden.md`, a second Dresden exists, and the
already-applied bullet is permanently ambiguous — in a MOC nobody revisits. The
ambiguity arrives later than the instruction, which is what makes it easy to
miss and expensive to find.

### WHY Two Passes With Opposite Timings

The fix needs two facts that are only true at different points in the pipeline,
which is why it is a pass and not a choice made at emit time:

- **`contested_note_names`** runs on the action list as built, **before** the
  two withholding passes. The withheld twin is exactly the note that comes
  back, so the claim set must include it. Taken from the survivors, the set
  sees one Dresden and renders the bare link the guard's own outcome
  invalidates.
- **`qualify_contested_moc_links`** runs **after** both guards, over their
  output, because the path it writes has to be one that will exist. The first
  implementation qualified at emit time and named the *withheld* claimant's
  `Atlas/202 Notes/Dresden.md` — a bullet pointing at a note the guard had just
  guaranteed would not exist, which is worse than the bare link it replaced. A
  test caught that before it shipped.

It must also run before `_merge_new_section_links` and `_serialize_new_sections`
(#70 / ADR-3), while `line_to_add` is still one bare bullet.

### WHY the Display Text Comes From the Bullet, Not From `source_note_title`

`source_note_title` is the **sanitised** stem. Rebuilding from it would drop the
alias `_wikilink` writes for a forbidden-char title, so `[[Q- one|Q: one]]`
would become `[[…/Q- one]]` and the user would lose the name they typed. The
pass parses the existing bullet and keeps its display half, so the two alias
uses compose: `[[Atlas/202 Notes/Q- one|Q: one]]`.

### WHY Run-Scoped and Not Vault-Scoped

The brief asked this explicitly, because a bullet that outlives its run is a
weaker case for run-scoping than a transient document is. Run-scoped, for three
reasons and with one stated limit:

1. **The scenario is run-internal.** What makes the bullet go ambiguous is the
   run's own withheld claimant returning. Including the withheld claims covers
   it exactly.
2. **A vault answer is not cheaply available.** Kado has no basename index, so
   "does a Dresden exist anywhere" means listing folders this run never writes
   to — an unbounded scan (Constitution L1) for a display decision, and CON-7
   forbids this spec's tests from reaching a vault to calibrate against.
3. **A vault namesake in a folder this run writes to is already handled.**
   `validate_destinations`' vault half withholds that move outright, so no
   bullet is emitted for it.

**The limit, stated rather than hidden:** a namesake already sitting in a folder
this run does not touch is not seen, and its bullet renders bare. Closing that
needs a basename index Kado does not have; it is a Kado capability question, not
a render-time one.

### A Pre-Existing Limitation This Exposes But Does Not Fix

`_emit` dedups by (target MOC, source title), so two *surviving* notes with the
same filename and the same parent MOC produce ONE bullet — the MOC lists one of
them. `survivors.setdefault` therefore names the first, which is strictly better
than resolving to whichever the vault picks, but the missing second bullet is a
separate defect in the emitter's dedup key and is not this task's.

## Three Keys Folded, One Left Exact (spec 034 T6.0)

The T5.3 and T5.4 sweeps above recorded four exact-string sites and fixed none.
T6.0 folds three of them — sites (1), (3) and (4) — and deliberately leaves the
fourth shape, `seen`, exact. Site (2) is unchanged and is now T6.0b.

`casefold()`, never `.lower()`: `ß` folds to `ss` and these are German notes.

### WHY Fold at All

Same asymmetry T5.3 recorded and T5.2 acts on. On a case-insensitive filesystem
(CON-6, verified on this host), not folding loses data and cannot be undone. On
a case-sensitive one, folding costs a rename, and the user can undo it. The
fail-safe direction is the folding one.

Only comparison keys fold. `_CASE_NOTE` promises the user always reads the real
spelling, so no folded string reaches a `destination`, a `source`, a `title`, a
`reason`, or anything rendered. Every folded dict follows T5.2's shape: the key
is folded, the value is the string as its author wrote it.

### WHY `seen` Is Not a Fourth Site

`_build_move_asset_actions` keeps two exact-string collections and they are not
the same shape. `claimed` keys the **destination**; `seen` keys the **source
path**, and the asymmetry inverts there:

- Not folding `seen` on a case-insensitive filesystem: `100 Inbox/Ufer.jpg` and
  `100 Inbox/ufer.jpg` are one file seen twice. The first moves; the second
  meets a folded `claimed` and is recorded as a collision skip, so T5.4 keeps
  its note in the inbox. Wrong about the cause, conservative in effect, and
  *reported* — the user reads a line naming both paths and renames one.
- Folding `seen` on a case-sensitive filesystem: two genuinely distinct files
  collapse to one. One moves, the other is dropped with **no skip recorded at
  all** — the exact silence T5.4's guard exists to break, re-created one layer
  up.

The second bullet is what makes this a decision rather than an oversight, and it
is only unreachable *because* `claimed` folds. The pair is load-bearing: folding
`claimed` without `seen` is correct, folding both is not, and folding neither
leaves site (4) open. `test_case_differing_sources_in_one_folder_are_each_accounted_for`
pins the invariant that carries the argument — every attachment path leaves this
pass with either a move or a skip, never with nothing.

### Site (1) Has a Second Paired Consumer — Folded, Then Reverted

The T5.3 sweep named `render_resolve.py`'s `create_moc_by_dest` as *the* paired
consumer of `by_dest`. There are two. The second was found by grepping the shape
rather than visiting the named site, folded, and then reverted — the revert is
the part worth recording.

**`resolve_target_moc_paths`' `in_set`** is keyed by title stem and runs *before*
`resolve_section_names` in `instruction-render.py` (`:596` vs `:607`). Once
`by_dest` merges `travel (MOC)` into `Travel (MOC)`, a `link_to_moc` minted
against the merged spelling misses tier 1, misses tier 2 as well (the MOC does
not exist in the vault yet), and keeps `target_moc_path: null`. That action is
NOT dropped — see "What a Null `target_moc_path` Actually Does" below; the claim
that `filter_unappliable_relationships` intercepts it is wrong, and the real
consequence is worse.

Folding `in_set` fixes that and introduces something worse. `by_dest` keys the
full composed destination, so two create_moc whose titles differ only in case
survive it when they sit in **different folders**. A folded `in_set` collides
those two on one key, and `in_set[key] = dest` is last-write-wins. Measured:

    folded:  I03 target_moc='Travel (MOC)' -> 'Atlas/300 Other/travel (MOC).md'
             I04 target_moc='travel (MOC)' -> 'Atlas/300 Other/travel (MOC).md'
    exact:   I03 target_moc='Travel (MOC)' -> 'Atlas/200 Maps/Travel (MOC).md'
             I04 target_moc='travel (MOC)' -> 'Atlas/300 Other/travel (MOC).md'

The fold sends the first MOC's bullets into the second MOC. It also lets tier 1
pre-empt tier 2 for case-only matches, which redirects a bullet from an existing
vault MOC to a newly created one on a case-sensitive filesystem.

Redirecting an action is a behaviour change, not an addressing fix — the same
line T6.0b is held behind — so `in_set` stays exact and the cost is recorded
instead. `test_two_in_set_mocs_differing_only_in_case_keep_their_own_links`
guards the revert.

**The cost, stated plainly:** when two MOC proposals in ONE folder differ only in
case, `by_dest` merges them, and any `link_to_moc` minted against the merged
spelling loses its `target_moc_path`. The merged proposal's `supporting_items`
still reach the survivor, so its down-links survive; what is at stake is the
up-bullet. Closing this needs the collision handled, not the key folded — the
upstream fold at `_merge_proposed_mocs_by_name` (T6.0c, below) removes the
case-only pair before either consumer sees it, but does **not** recover the
up-bullet: a link minted from the LOSING spelling still misses the survivor's
exact key.

### What a Null `target_moc_path` Actually Does — Traced Under T6.0c

An earlier revision of this section said the unresolved `link_to_moc` "is dropped
by `filter_unappliable_relationships`". That is wrong, and the correction matters
because the real behaviour is worse than a dropped bullet.

`filter_unappliable_relationships` only inspects `add_relationship` actions
carrying a truthy `error` key. It never looks at `link_to_moc`. What actually
happens to a `link_to_moc` with `target_moc_path: null`:

- **It renders as a normal, actionable instruction.** `lib/render_md.py` emits
  `### Add link to [[<losing spelling>]] — <note>` followed by `- [ ] Applied`
  and `- **Target:** [[<losing spelling>]]`. The `- **Path:**` line is emitted
  only `if action.get("target_moc_path")`, so the null case is the same block
  minus one row. The anchor falls to its unresolved branch, which prints
  `- **Open the MOC**, find the first editable callout (e.g. `> [!blocks]`) or
  the matching section.` — instructing the user to open a MOC that will never
  exist. No warning, no degraded marker, no Skipped-section entry.
- **It validates clean.** In `tomo/schemas/instructions.schema.json`,
  `$defs/link_to_moc` requires `[id, action, target_moc, anchor, placement,
  line_to_add]`; `target_moc_path` is `{"type": ["string","null"]}` and is NOT
  required. The asymmetry is the whole reason one kind has a guard and the other
  does not: `$defs/add_relationship` **does** require `target_moc_path`, so a
  null there would be rejected by Hashi's `additionalProperties:false` wire
  schema — which is exactly why `filter_unappliable_relationships` exists for
  that kind and nothing equivalent exists for `link_to_moc`.
- **Every downstream gate passes it.** `instructions-dryrun.py`'s
  `REQUIRED_FIELDS_BY_KIND["link_to_moc"]` omits the field, and its `describe()`
  prints only `target=[[…]]`. `instructions-diff.py`'s coverage check matches on
  `source_note_title`, and `links_by_source` keys the `target_moc` **stem**,
  never the path — so the action is counted `[OK]`.

**This violates CON-2**: the user approves on what the document says. The document
says "add a link to this MOC", the checkbox invites them to tick it, and every
automated gate reports green — while the target does not and will not exist.

**Not case-specific, and pre-existing.** Nothing above depends on a case-only
collision. It fires whenever both resolution tiers miss — an unresolvable
`target_moc` of any origin. T6.0's fold and T6.0c's merge fold only made one more
route to it reachable; neither created it. Tracked as its own task, **T6.0d**.

### Found While Folding, Closed by T6.0c

**`derive_expected` counted a case-only MOC pair as two, and the fold emits one
— closed upstream.** `instructions-diff.py` counts one expected `create_moc` per
confirmed item and does no destination comparison, so two confirmed proposals
named `Travel (MOC)` and `travel (MOC)` expected two actions where the folded
builder emits one. The audit reported `create_moc expected=2 actual=1 [DIFF]`
plus a `[MISSING]` coverage row for the merged item, and `synthesis-conductor.md`
step 3e makes a diff mismatch fatal.

That was a change in failure mode, not a new data loss: before the fold the run
completed and dropped the merged proposal's children on apply; after it, the run
stopped and said so. Loud beats silent — but it was the same shape T5.4 had to
close with `_subtract_skipped_assets` ("a guard whose own audit stops the run is
not shippable"), so it was carried as T6.0c rather than left standing.

**Resolved 2026-09-08 by folding `_merge_proposed_mocs_by_name`**
(`suggestion-parser.py`), the first of the two candidate remedies recorded here
and the smaller, more honest one: it removes the divergence instead of teaching
the audit to tolerate it. The parser now confirms ONE item for a case-only pair,
so `derive_expected` and the builder agree and `by_dest` returns to being the
defence-in-depth its own comment claims it is. The rejected alternative was a
subtraction in `instructions-diff` mirroring `_subtract_skipped_assets`, which
would have needed the builder to report its merges on the wire — owing the usual
triad (strip-before-wire, paired-consumer count, schema test) for a divergence
that did not have to exist. Full rationale, including why `casefold()` rather
than `.lower()` and why the fold has to hold across the markdown path's double
merge, lives in `docs/tomo/scripts/suggestion-parser.md`.

**Still open: the losing spelling's up-bullet.** T6.0's implementer claimed the
upstream fold would also close the `in_set` bullet loss recorded above. T6.0c
traced it at HEAD and it does not. `in_set` keys the EXACT `_moc_stem(title)`
and stays exact by measurement (`b9d34e1`), so the merge survivor is indexed
under its own spelling only and a `link_to_moc` minted from the losing spelling
still misses it, keeping `target_moc_path: null` — Kado's `search_by_name` tier
cannot help either, because the MOC does not exist in the vault yet. Pinned
hard-coded in `tests/test_034_t6_0c_merge_proposed_mocs_case_folded.py`. Closing
it needs the different-folder `in_set` collision handled, not a fold.

What the null then does is the subject of "What a Null `target_moc_path` Actually
Does" above: the action is not dropped, it renders as an actionable `- [ ] Applied`
checkbox naming a MOC that will never exist, and every gate reports green. That
is a CON-2 violation, it is not case-specific, and it is tracked as **T6.0d**.

### Report-Only Sites From the T6.0 Shape-Grep

Two more destination-ish collections were examined and are **not** the same
shape:

- **`instruction-render.py:352`'s `used_filenames`** keys rendered filenames in
  `tomo-tmp/`, not vault destinations, and `slugify` lowercases its input — a
  case-only pair is already one key there. No fold needed.
- **`instructions-diff.py:454`'s `attachments_seen`** counts one expected
  `move_asset` per distinct attachment path, keyed exactly. It is the paired
  consumer of `_build_move_asset_actions`' `seen`, which stays exact — so the
  two still agree, and `_subtract_skipped_assets` already accounts for the extra
  skips the `claimed` fold produces.

## What the Null Does Now — Withheld, With Its Cause (spec 034 T6.0d)

WHY the action is **withheld** rather than emitted with an "unresolved" marker:
an emitted marker would have to be honoured by Hashi's wire schema, which means
making `target_moc_path` required on `link_to_moc` — a breaking change to a
cross-repo contract, owed a Kokoro migration note, for an action Hashi could not
apply anyway (Hashi modifies, never creates: there is no MOC to write the bullet
into). And a marked action still renders a `- [ ] Applied` checkbox unless the
renderer suppresses it, so the marker alone does not close the CON-2 gap it was
supposed to close. Withholding costs one wire field nothing and reuses the guard
`add_relationship` already has.

WHY the guard is `filter_unresolvable_moc_links`, shaped exactly like
`filter_unappliable_relationships`: both are pure functions over a marker set at
the point the cause is known, both return `(kept, skipped)`, and both surface the
skipped items through stderr and the instructions.md Skipped section. The
asymmetry that produced this defect — `add_relationship` defended, its sibling
not — is closed by giving the sibling the same shape rather than a new one.

### The Cause Is Recorded Where It Is Known, Never Reconstructed

`resolve_target_moc_paths`' tier 2 returns `None` for three reasons, and only one
of them means the MOC does not exist:

| cause | condition | what it means |
|---|---|---|
| `absent` | `not hits` | Kado answered; there is no such note |
| `unchecked` | `client is None` | no Kado client — nothing was asked |
| `probe-failed` | the call raised, or a hit carried no path | the lookup failed |

WHY they must not be collapsed into "unresolved": withholding on a bare null and
reporting every one as a MOC that will never exist would, on an offline run or a
transient Kado failure, tell the user that MOCs already sitting in their vault
are gone — and invite them to re-create or rename them. That is a worse outcome
than the defect being repaired. `client is None` is a single condition set once
for the whole run, so it is exactly the case where a wrong sentence would be
repeated for every link in the run.

WHY the cause is cached alongside the path, per stem, rather than derived at the
call site: two links to the same MOC must report the same reason, and a reason
derived a second time can differ from the first if Kado's state changes mid-run.

#### `absent` Cannot Distinguish "No Such Note" From "Not Permitted to Look"

**Known limitation, accepted 2026-09-08. Do not treat this as a defect to fix in
Tomo.**

`absent` is inferred from Kado returning an empty result, and an empty result has
two meanings Kado does not separate. `filterItemsByScope`
(`Kado/src/obsidian/search-adapter.ts:91-97`) drops out-of-scope items silently,
and returns `[]` outright when the caller has no scope patterns at all. Kado's
`FORBIDDEN` code is raised only for *tag* permission failures, never for path
scope. So a MOC that exists in the vault but sits outside Tomo's permitted paths
comes back from `search_by_name` as an empty list — byte-identical to a MOC that
genuinely is not there.

The consequence, stated plainly so nobody rediscovers it as a bug: for such a MOC
the instructions say **"MOC not found — create it"** about a note the user can see
in Obsidian and already owns. Following that advice creates a duplicate.

WHY it is left this way: the distinction lives in Kado's search contract, not in
Tomo. Tomo could only recover it by reading its own ACL and re-deriving what Kado
already knows — duplicating a sibling component's responsibility, which the MiYo
constitution's architecture rules exclude. Kado is not changing for this, and the
behaviour cannot be exercised from Tomo's test suite: the fake client *defines*
`[]` as absence, so no fixture here can tell the two apart.

Surfaced by T6.0d's implementer as the assumption its diff could not verify, then
checked against the Kado source rather than left open. The wording stays as it is;
this note is the record.

### The Marker's Lifetime

`UNRESOLVED_MOC_FIELD` (`unresolved_moc`) lives on the action from the resolver
until `filter_unresolvable_moc_links` removes the action carrying it — every
action stamped with it is withheld, so none survives to the wire. It is
nevertheless added to `_strip_internal_link_fields`' list as defence in depth,
for the same reason `alt_headings` is there: Hashi's `link_to_moc` schema is
`additionalProperties: false`, and a future change that moves or removes the
filter must not silently start shipping a Tomo-internal field.

### The Filter Runs Beside the Resolver, Not Beside the Other Two Filters

WHY it is called immediately after `resolve_target_moc_paths` rather than next to
`filter_missing_daily_notes` and `filter_unappliable_relationships`: four passes
sit between those two points and all four read `link_to_moc` — anchor resolution
(a Kado read per target MOC), the `#70` same-section merge, the existing-heading
rewrite, and new-section serialization. A withheld action must not be merged into
a surviving one, and spending a Kado read on a MOC nobody will open is waste.

## `source_note_title` Is Display Text, `source_note_stem` Is the Vault Key

**Spec 034 T6.4b**, found by the T6.4 live run on 2026-09-08.

`_emit` wrote `sanitize_stem(source_title)` into `link_to_moc.source_note_title`,
deliberately, for `#69`: every reference to a forbidden-char note had to
round-trip to the renamed file. Meanwhile `instructions-diff.py`'s coverage audit
joins that field against the item's **raw** title — its own comment at `:1056`
says so ("links carry source_note_title == item title"). Any title containing a
character `sanitize_stem` replaces (`\ / : * ? " < > |`) therefore never matched,
and the audit hard-failed a run whose instruction set was correct.

Observed live on `Elbe-Schifffahrt: Tschechischer Pegel bei Usti nad Labem`. Two
sibling items in the same run passed **only because their titles happened to
carry no forbidden character**. The analyst produced that colon unprompted, so
this fires on ordinary content, not on a constructed edge case.

**WHY the field was split rather than the audit taught to sanitise.** Under ADR-2
`source_note_title` is display text; a filename in it is the category error, and
making both sides of the audit compare sanitised forms would have hidden that
while making the field mean different things to different readers. But the
sanitised value is genuinely load-bearing — three passes join on it, and all
three compute `sanitize_stem` on their own side:

| site | joins against |
|---|---|
| `_orphaned_link_titles` / `_drop_moves_with_paired_deletes` | `sanitize_stem(action["title"])` of dropped moves |
| `_links_for` | `sanitize_stem(d["title"])` of a withholding's dropped set |
| `qualify_contested_moc_links` | `contested_note_names`, itself keyed on `sanitize_stem` |

So the value stays and gets an honest name. Two fields, two jobs, neither lying —
the same shape ADR-2 gave `item_key` and `stem` one layer up.

### Its Lifetime, and Why the Garden Branch Does Not Carry It

`source_note_stem` is emitted by `_emit`, read by the three passes above, cleared
alongside `source_note_title` when `_merge_new_section_links` folds a section
that spans several notes, and removed by `_strip_internal_link_fields` before the
wire. Identical to `new_section`'s lifetime.

**WHY `_build_garden_audit_actions`' `file_note` branch deliberately omits it**,
even though it emits `link_to_moc`: `scripts/gen-garden-audit-hashi-example.py`
calls that builder **directly** and embeds the result verbatim in a Hashi handoff
document, without `_strip_internal_link_fields` ever running. An internal field
there reaches Hashi, whose `link_to_moc` schema is `additionalProperties: false`,
and the action is rejected. Adding it broke
`test_garden_audit_hashi_example.py` immediately — the guard did its job. There is
also no consumer: the three joins act on `move_note` / `create_moc`, which that
branch never emits. A garden item is already in the vault, so its on-disk stem is
both its display name and its key.

### The Report Record Carries the Title Only

`removed_moc_links` entries are serialised into `instructions.json`'s `tomo`
block as `withdrawn_moc_links`, and rendered to the user by `render_md`. They
carry `source_note_title` alone — `_links_for` derives the key with
`sanitize_stem` the same way the dropped side does, so both halves of the join
agree by construction without an internal field crossing that surface.

### A Second Failure Path, From the Same Cause

`instructions-diff.py`'s `_subtract_unresolvable_links` (`:902`) joins a
withholding record's `source_note_title` against the item's raw title as well. A
colon-titled note whose target MOC could not be confirmed therefore had its link
withheld by the renderer and then counted as missing by the audit — a second hard
fail on a correct run, from one cause. Found while tracing this fix's blast
radius, not by the live run; covered by
`test_a_withheld_unresolvable_link_subtracts_for_a_colon_title`.

## T6.4c — Why a Withheld Move Also Withholds Its Staging Note

Found by the T6.4 live run on 2026-09-09: a destination clash withheld both
claimants and left two `2026-09-08_1813_elbe-schifffahrt-*` files in the inbox,
one per withheld claimant. Not data loss and not a loop — `pending-move` is
excluded from fresh-source discovery, so nothing re-ingests them — but nothing
clears them either, and the remedy the document prints ("rename one and re-run
Pass 2") renders a fresh pair on every attempt.

### WHY the Fix Lives at the Manifest, Not at the Render Step

The plan offered "render after validation" as the larger of two directions. It is
not available: `build_actions` is built **from** the manifest, so rendering
cannot follow a validation that needs its output. That is circular, not merely
risky.

What made a smaller fix possible is that `instruction-render.py` never writes a
staging note to the vault at all. It renders to a local directory and lists each
file in `manifest.json`; a **separate process**, `upload-rendered.py`, writes one
vault note per manifest entry. The residue is produced there. So the manifest is
rewritten after the guards, the upload never sees the withheld entry, and no
step's ordering moves. The Kado write the plan hoped to save is saved as a side
effect — the note is never uploaded in the first place.

`upload-rendered.py` is deliberately untouched: it reads the manifest it is
given, and that contract is what makes it the right place to steer from.

### WHY the Join Is `rendered_file`, Not the Action `id`

The clash record's `dropped` entries carry the action `id`, which is a fresh
`_next_id` counter value — it does not join back to the manifest entry the action
was built from. `rendered_file` is the only key both sides hold, and both action
builders copy it verbatim from the entry.

### WHY `claimed_before` Exists

The pass compares the claims **before** the guards against the claims after.
Without that first half, "no surviving action claims this file" and "no action
was ever built for this file" are the same observation, and a run whose action
building produced nothing would have its entire manifest emptied — the note
dropped rather than withheld. Three existing tests that stub `build_actions` to
return no actions caught exactly that during implementation. An entry no action
ever claimed is kept, because nothing withheld it.

### WHY Both Guards, When the Task Named One

`suppress_moves_for_unfiled_attachments` withholds `move_note` through the same
`_drop_moves_with_paired_deletes` helper and produces the same `dropped` record
shape, so it leaves the same residue. Working from the surviving actions rather
than from either withholding report covers both in one pass, and a third guard
would need no change here.

Not covered, and deliberately: the by-Name `create_moc` merge in
`_build_create_moc_actions` drops a duplicate claim **inside** `build_actions`,
so the absorbed entry has no claim in `claimed_before` either. That path is
defense-in-depth for a merge `suggestion-parser.py` already performs upstream, it
emits no record, and reaching it means the parser missed. If it ever becomes
reachable, the residue returns and needs its own record — this pass will not see
it.

### WHY `detect_orphaned_state` Could Not Have Covered It

`inbox-triage.py:1438` flags captured source items whose downstream docs have all
vanished. A withheld-clash run always uploads `instructions.md` and
`instructions.json`, so `state.instructions_hits` is non-empty and the detector
returns `[]` by design. Different case, not a gap in that detector.
