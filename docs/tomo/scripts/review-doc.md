# WHY: review-doc.py

> Rationale for decisions in `tomo/scripts/review-doc.py`.
> The script owns the review document of `/review` in the inbox (spec 045,
> T3.6 `write`, T3.7 `parse` and `replace`): it turns the read period and
> the model's `proposals.json` into `<period> Review.md`, writes it through
> Kado, records the Pass 1 counts and removes the content files; later it
> reads the edited document back for Pass 2 and, on a confirmed start-over,
> writes a new document over its own.

## WHY One Script With Subcommands

SDD Internal API Changes names `review-doc.py write | parse | replace`. One
argparse parser with subparsers holds the three without a second script or
a second exception handler; the parser carries the shared `--config`,
`--profiles-dir` and `--tmp` options at the top level, and every subcommand
takes `--stem`, so the one `Refused` / `Stopped` handler in `main` can name
the stem for all of them.

## WHY `parse` Reads the Document From `meta.json`'s Path

`parse --stem S` has only the stem. The document's path was decided by
`write` (the inbox path of `<period> Review.md`) and recorded in the
content-free `meta.json`, so `parse` reads it there; the skill may hand in
`--doc-path` from the `start` listing instead (that listing finds documents
by frontmatter, renamed ones included). No `meta.json` and no `--doc-path`
is `not-found`, like a document that is gone from its path: the skill
offers to start over (SDD Error Handling). One Kado read, `kado-read
note`, is the whole cost; the document is parsed by `lib/review_doc_parse`.
Since T4.2 the read and the parse — path lookup, the note read, the
`pass1_links` map handed to the parser — live in `lib/review_doc_read`,
shared with `review-instructions.py preview` and `deliver`, so the three
commands cannot disagree on `edited` and `deleted`
(docs/tomo/scripts/lib/review_doc_read.md).

## WHY `parse` Prints Counts Only and Writes No File (ADR-9)

The skill needs counts, the Approved state and the warnings. stdout is the
skill's — and the transcript's — so it carries `items` as `{id, origin,
kept, edited}`, the four counts, `approved`, `nothing_to_deliver` and the
warnings, never a line of the document. `parse` writes nothing: no
`approved.json`, no change to `meta.json`. The first version wrote the
ApprovedReview record (kept items with their verbatim text) to the stage
for Phase 4 to read; it was dropped because the vault document is the
source of truth and may change between the parse that reports counts and
the delivery that lands text — the user ticks one more box, Obsidian
Sync brings a later edit — and a landed stale copy would contradict "Pass
2 lands what the user left". So Phase 4 reads the document fresh through
Kado at preview and at deliver time and calls the lib's
`ParsedDoc.approved_review()` in-process (SDD ENTITY ApprovedReview). A
second gain: `tomo-tmp` holds no extra content file beyond those ADR-9
already accounts for, and nothing has to delete it on a rewrite. One
`kado-read note` is the whole cost of a `parse`.

## WHY `edited` Comes From `pass1_links` in `meta.json`

`write` stores, per Tomo item id, the ordered list of `[[stem]]` source
links as rendered (`pass1_links`) next to `pass1_counts`; `parse` compares
the item's current link stems with it, as an ordered, de-duplicated list.
The rationale — why a text digest was rejected (a templated habit line is
recoverable by enumerating its values), why presence is `in` and not
truthiness (a habit's entry is `[]`), and the accepted limit that a retyped
text keeping its links reads as unedited — is in
`docs/tomo/scripts/lib/review_doc_parse.md`. `pass1_links` also gives
`deleted` its exact id set. A `meta.json` from the digest version carries
`pass1_items` and no `pass1_links`; it is read like a `meta.json` without
the map: `edited` False everywhere, `deleted` from the `pass1_counts` sum.

## WHY `replace` Has Three Answers (`needs-confirm`, `--confirm`, `--abort`)

F6-AC1: starting over names the document that will be replaced and asks
again. `replace --stem S` alone answers `needs-confirm` with the
`doc_path`, computed the way `write` computes it (the kept `read.json`'s
period under the setup's inbox) — no Kado call, nothing written, the skill
asks the question. `replace --confirm` is `render_and_write` with
`allow_overwrite_review=True`: the same check, render and write as `write`,
from the `read.json` and `proposals.json` that `write` kept on
`review-exists` (the default `--proposals` is the stage copy), so no
second read and no second model pass. A success is reported as `replaced`;
`meta.json` is rewritten by the same path (`steps_done` empty, fresh
counts and link stems — the reset); the stage content files go away as
after `write`; a non-Tomo file at the path is still `doc-name-taken`,
because the overwrite flag covers Tomo's own document and nothing else.

`replace --abort` is the user declining to start over: the run that
produced the kept `read.json` and `proposals.json` is over, and ADR-9 says
content does not linger for a run that is not going anywhere. Both files
are deleted; the document and `meta.json` stay untouched, because the
existing review goes on exactly as it was. `--confirm` and `--abort` are
mutually exclusive on the parser so a mixed call is exit 2, not a guess.

## WHY the Script Does the Kado Calls and the Lib Does Not

`lib/review_doc.py` is pure: it checks and renders. The script owns the
probes and the write, so the lib is testable without a vault and the Kado
budget is visible in one place. A `write` costs at most five calls: the
flat target path, the year-subfolder path (skipped when the flat one
exists), a `byName` search when neither exists (the user may have moved the
note; F6 edge case "targets it where it is"), the document-name probe and
the write itself.

## WHY the Target Is Probed Before Writing

F4-AC1: the document states the target note and whether it exists or will
be created. The two candidate paths come from `Period.note_paths` (flat,
then the year subfolder, the same rule the reader uses). When neither
exists, one `byName` search for `<name>.md` finds a note the user moved;
only an exact filename match counts, and the document then names that path
as the target (`target_found_elsewhere`) instead of proposing a second note
beside it.

## WHY `write` Never Overwrites (`doc-name-taken`, `review-exists`)

The inbox is the user's folder too. The document-name probe reports three
outcomes, not a boolean: nothing at the path, a file that is not Tomo's
review (no `tomo.doc_type: review`), or Tomo's own review of this period.
Only the first is written. A non-Tomo file is the user's and gives
`doc-name-taken` (SDD Error Handling). Tomo's own review gives
`review-exists` with its `doc_path` — `write` never overwrites, because it
cannot tell a confirmed start-over from a second `/review` on the same
period; the skill asks before a start-over (F6-AC1), and only
`replace --confirm` (T3.7) writes over Tomo's document, from the kept
`read.json` and `proposals.json`. That is why a refused `write` keeps both
files and leaves `meta.json` as it was: the confirmed second attempt needs
no second read and no second model pass.

The render-and-write path is one function with an explicit
`allow_overwrite_review` flag; the `write` subcommand always passes False.
`replace` (T3.7) reuses the same path with True instead of a second render
and write of its own, so the overwrite decision lives in one line that the
tests can read.

## WHY a Failed Write Is `stopped` With Nothing Reported

A refused or failed Kado write leaves the vault unchanged; the script says
`status: stopped`, `kado-write-failed`, names no `doc_path` and keeps
`read.json`, `proposals.json` and the previous `meta.json` so the skill can
retry without a second read. Only after Kado accepted the write are the
content files removed and the counts recorded.

## WHY `read.json` and `proposals.json` Are Deleted Here (ADR-9)

Both hold journal content. The document in the inbox is the only copy the
user needs after Pass 1; the counts Pass 2 reports against (`pass1_counts`)
go to the content-free `meta.json`. Deleting after the write, not before,
means a failed write never loses the model's work.

## WHY the Exit Codes and the Bare Class Name on stderr

Repo rule for agent-called scripts and ADR-9: 0 for every outcome the skill
can act on (`status`, `problems`, `error`), 2 for a bad invocation
(argparse, an unsafe `--stem`), 1 only for an unexpected exception, where
stderr carries the exception class name and nothing else — never a path, a
proposal or a line of the document. An unsafe `--stem` is what
`lib/review_state.safe_stem` refuses — empty, whitespace, `.`, `..`, or
carrying `/` or `\` — the same guard `review-read.py` and `read_meta` use;
`.` in particular would make `write` stage and delete files in
`tomo-tmp/review` itself (docs/tomo/scripts/lib/review_state.md, "WHY One
Stem Guard").

## WHY `--run-id` Is Optional

The skill may mint a run id before Pass 1 (as `/inbox` does) and pass it,
so the document, the cost log and the meta share one id; without it the
script mints one through `lib/run_id.generate`, the same format.
