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

### The Paired Consumer Still Collapses (open)

`instructions-diff.py`'s `derive_expected()` — its `confirmed_stems` set and the
`daily_only_seen` collision check inside it — derives the EXPECTED `delete_source` count
with the same shape this section removes: `confirmed_stems` and
`daily_only_seen` are stem-keyed, so a daily-only namesake's expected deletion
is suppressed by a same-named confirmed item. Its own `NOTE` calls this a
"residual collapse point until T2.3b", and T2.3b has since landed — the
justification is stale. Two of the four cases above (the daily-only pair, and
confirmed-plus-daily-only) now emit one more `delete_source` than that module
expects, so `/inbox` would report count drift on a correct instruction set.
Left out of T5.0b deliberately: it is a second module with its own key
semantics (`_keys_match` tolerates an inbox-prefix asymmetry that a set-equality
dedup does not), and it deserves its own task and its own RED test rather than
a mechanical copy of this one.
