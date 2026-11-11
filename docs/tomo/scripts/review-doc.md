# WHY: review-doc.py

> Rationale for decisions in `tomo/scripts/review-doc.py`.
> The script owns the review document of `/review` in the inbox (spec 045,
> T3.6 `write`; `parse` and `replace` follow in T3.7): it turns the read
> period and the model's `proposals.json` into `<period> Review.md`, writes
> it through Kado, records the Pass 1 counts and removes the content files.

## WHY One Script With Subcommands

SDD Internal API Changes names `review-doc.py write | parse | replace`. One
argparse parser with subparsers lets T3.7 add `parse` and `replace` without
a second script or a second exception handler; `write` is the only
subcommand in T3.6 and the parser already carries the shared `--config`,
`--profiles-dir` and `--tmp` options at the top level.

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

## WHY an Existing Non-Tomo Document Refuses (`doc-name-taken`)

The inbox is the user's folder too. A file named `<period> Review.md` that
carries no `tomo.doc_type: review` is the user's and is never overwritten
(SDD Error Handling). A document that is Tomo's review of the same period
is overwritten: the skill asks before a start-over (F6-AC1), and `replace`
(T3.7) is the confirmed path; `write` cannot tell a confirmed start-over
from an unconfirmed one, so the confirmation stays with the skill.

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
proposal or a line of the document.

## WHY `--run-id` Is Optional

The skill may mint a run id before Pass 1 (as `/inbox` does) and pass it,
so the document, the cost log and the meta share one id; without it the
script mints one through `lib/run_id.generate`, the same format.
