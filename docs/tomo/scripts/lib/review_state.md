# WHY: lib/review_state.py

> Rationale for decisions in `tomo/scripts/lib/review_state.py`.
> The module is the only owner of the open-review states of `/review`
> (spec 045, SDD Complex Logic `review_state`, ADR-2, ADR-6): the canonical
> state list, the one function that classifies a review document, the
> content-free `meta.json` reader, the probe-and-classify step one stem goes
> through, and the listing `start` prints.

## WHY One Function Owns the States

WHY: SDD Internal API Changes names six canonical states (`open`,
`failed-delivery`, `delivered`, `applied`, `move-refused`, `target-missing`)
and three readers of them: `review-session.py start` (the listing),
`review-instructions.py status` (one stem) and the skill's offers. A state
computed in two places drifts: `start` would call a review "open" while
`status` calls the same stem "failed-delivery". `review_state` is the single
function; `STATES` is the single list; every caller imports both and never
spells a state itself.

## WHY `stem_state` Is the One Probe-and-Classify Step (T4.3)

WHY: `review_state` is pure — it takes the document, the meta, the set JSON
and two probe answers and returns a state. Someone has to read the set JSON
and run the probes through Kado, and that someone was about to exist twice:
once in the `start` listing, once in `status`. Two copies would decide
differently which documents to probe, how to read a Kado failure and which
path to ask for. `stem_state(vault, doc, meta, stem, inbox)` is the one
function: it computes the set path, reads the set when the document is
approved, runs the probes the set needs, and calls `review_state`.
`open_reviews` calls it per document; `status` calls it for its stem with
the same five inputs. A test records the calls of both scripts and asserts
they are identical for the same vault, document and meta.

## WHY Steps 3–7 Read `applied` From the Set JSON (ADR-6)

WHY: Hashi never sets `tomo.state: applied` on anything. Its
`executor/jsonAppliedWriter.ts` rewrites `<stem>_instructions.json`
atomically and monotonically with `applied: true` on each action it
executed (per action id, batched once per source after the run). The set
JSON in the inbox is therefore the only place that says whether the review
landed, and `applied` per action is the only field to read. The document's
own state (`approved`) says "delivered", not "applied"; `meta.json` is
Tomo's record of its own writes and knows nothing of Hashi.

`move-refused` is read from what a refused move leaves behind: Hashi's
`actions/moveNote.ts` returns `failed` with "Inconsistent state — both
source and destination present" when the destination already exists, and
touches neither file. So an unapplied `move_note` whose `source` (the staged
copy in the inbox) and `destination` (the periodic note) both exist is the
refusal (step 5). A copy that is gone while the move is unapplied is a move
done by hand or a copy the user deleted: `delivered`, never a guess beyond
that. `target-missing` (step 6) is an unapplied `insert_under_marker` or
`replace_section` whose `target_path` no longer answers: the user moved or
deleted the periodic note after delivery, and Hashi would fail on it.

## WHY Withdrawn Is Tested Before the Begun-Delivery Reading

WHY: coordinator decision 2026-11-12. The SDD numbers the steps 1 (a begun
delivery, or approved without a set → `failed-delivery`), 2 (no set →
`open`), 3 (withdrawn → not listed). Read in that order, every dropped
review is listed as `failed-delivery` forever: `drop` after a partial
delivery keeps `meta.json` with its `steps_done` and `withdrawn: true`
(ADR-13 — Kado offers Tomo no delete, so the record of what was written
must stay), and that record satisfies step 1. The function therefore tests
step 3 first — `meta.withdrawn`, or a set JSON whose `actions` list is empty
(what `drop` writes over a delivered set) — and only then step 1. Where the
SDD's numbering and this order disagree, this order is the one implemented;
the step names in the code keep the SDD's numbers so the two can be read
side by side.

A withdrawn meta also costs no probe: the answer is fixed before the set is
read, so `stem_state` returns before touching Kado.

## WHY a Begun Delivery Is Read Through `ReviewMeta.started()`

WHY: coordinator decision 2026-11-12, from the T4.2 fix round. The SDD's
step 1 says "`meta.failed_step` set". A delivery killed after a recorded
non-final step — `steps_done: ["note"]`, `failed_step: ""`, the kill landed
between `record(note)` and the in-flight mark of `set_json` — has no
`failed_step`, and under the SDD's wording it reads `open`: the next
`/review` offers a fresh Pass 1 on a review whose new note already sits in
the inbox. `lib/review_delivery.ReviewMeta.started()` (a step done or one
in flight) is the reading `drop` and `preview` already use for the same
question, so `review_state` reuses it rather than carrying a third
definition of "began": a begun delivery without `doc_mark` in `steps_done`
is `failed-delivery` (resume or drop), whatever the document and the set
say. A complete delivery (`doc_mark` recorded) falls through to the set.

### WHY `review_state` Imports `review_delivery` and the Cycle Was Broken in `note_meta`

`review_delivery` imported `META_FILE` from this module; this module now
imports `ReviewMeta` from `review_delivery`. The constant was the only
reason for the back edge, and it is not this module's: `meta.json` is the
file name of every staged delivery, `/note`'s as much as `/review`'s, and
`lib/note_meta.META_FILE` already owns it for `staged_delivery`. Both
modules now take it from there (this module re-exports it, so
`review-doc.py` keeps its import). The alternative — a function-local
import inside `review_state` — hides a dependency that a reader of the
import block should see. The module is no longer stdlib-only; the three
scripts that import it already load the delivery libs.

## WHY the Probe Answers "Absent" Only on `KadoNotFoundError`

WHY: an empty Kado answer may hide a denial (memory rule, SDD Rule 6). Each
probe — the set JSON, the move's source, the insert's target — reads
"absent" only when Kado says NOT_FOUND. A refused key stops the run as
`kado-auth`, any other failure as `kado-unreachable`, through
`review_vault.kado_stops`, the same mapping every Pass 2 reader uses. The
alternative, reading a failed probe as "not there", would turn a key that
cannot reach the inbox into `failed-delivery` for every approved review
(offering resume and drop on sets that exist) and a key that cannot reach
the periodic notes into `target-missing`. `KadoClient.path_exists` is not
used for the same reason: it is correct, but a probe that catches only
NOT_FOUND inside `kado_stops` says the rule in one place.

## WHY Only Approved Documents Are Probed, and the Step 5/6 Probes Are Lazy

WHY: ADR-6 and the coordinator's cost decision 2026-11-11. A set JSON can
exist only for a document that went through `deliver`, and `deliver`'s last
step marks the document `approved`; a pending document therefore costs no
read. A begun delivery on a pending document (`steps_done` non-empty, the
mark not yet written) is caught by step 1 from the meta alone, so skipping
its probe loses nothing. The step 5/6 probes run only for a set that is
present, not withdrawn and not fully applied, and only for the paths the
set's one action names: a `move_note` probes its `source` first and its
`destination` only when the source still exists (a gone source is
`delivered` whatever the destination says); an `insert_under_marker` or
`replace_section` probes its `target_path`. The paths come from the set
JSON, not from `meta.json` or the document, because the set is what Hashi
executes — if the two disagreed, the set would be the one that failed.

Kado calls of one listing: one `byFrontmatter` query, one frontmatter read
per hit (T2.3), plus per approved document with an open meta one
`read_file` of the set, plus for a set that waits one probe (insert or
replace) or one to two (move). A closed meta (withdrawn) costs none.

WHY `stem_state` checks `withdrawn` before the set read although
`review_state` checks it again: the early return exists to skip the Kado
read of the set, not to classify. A withdrawn review is never listed
whatever its set says, so reading the set would spend a call (and risk a
`Stopped` on a refused key) for an answer already known. The repeated check
in `review_state` is the classifier's own rule for callers that hand it a
set directly; neither check replaces the other.

## WHY `applied` Is Offered Once, and the Listing Applies It, Not the Classifier

WHY: SDD step 4: "applied (reported once: `meta.applied_reported`)". The
review is finished; the user should hear it once and not on every later
`/review` while the document and the set linger in the inbox. The
classifier stays pure: `review_state` returns `applied` whenever every
action carries `applied: true`, and `status` therefore keeps answering
`applied` for the stem — the truthful answer to a direct question.
`open_reviews` is the offer, so it is the listing that drops an `applied`
review whose meta carries `applied_reported`; `review-session.py start`
writes the flag for every `applied` review it listed, after the listing,
because the script that reports is the one that knows it reported. A
missing meta (a cleaned `tomo-tmp`) gets a minimal one with the flag, or the
review would be offered on every start.

## WHY `review_state` Returns None for "Not Listed"

WHY: the canonical list has six states and "a withdrawn set is not listed"
is not one of them. A seventh name would leak into `start`'s output and
the skill's offers; None is the honest value for "nothing to offer", and
`open_reviews` drops it. `status` on a withdrawn stem prints `state: null`
for the same reason.

## WHY an Unreadable Set JSON Reads as `delivered`

WHY: a file at the set path that is not JSON, not an object, or whose
`actions` is not a list of objects exists and is not Tomo's withdrawal.
`failed-delivery` would offer resume (which refuses: `set-exists`) and drop
(which overwrites a file Tomo cannot read); `applied` would claim what
nobody verified. `delivered` — waits for Hashi or by hand — is the state
under which the user looks at the inbox, and Hashi's validator will say what
is wrong with the file. An empty `actions` list alone is the withdrawal
signature, because only `drop` writes one: `nothing-to-deliver` refuses
before a set is built.

## WHY an Unsafe `review_stem` Is Skipped, Never Read as Meta-Absent

WHY: `read_meta` returns None for a stem that fails `safe_stem`, and until
T4.3 the listing classified such a document as if its meta were absent —
`open` or `failed-delivery`, with a stem the skill would then pass to
`review-read.py --stem`, which exits 2. A document whose `review_stem` (or,
without the key, whose `review_period`) is not a plain folder name is
listed under `skipped_review_docs` with reason `stem-unsafe`: visible, never
offered, never probed. The vault is the source of truth and a corrupted
record must stay visible (design-for-corruption rule), but it must not
become an offer no later step can act on.

## WHY the Document Is the Source and `meta.json` Only Adds

WHY: ADR-2: the open state lives in the vault. The review document finds
itself by `tomo.doc_type=review` even when renamed, and its top-level
`review_period`, `review_kind` and `review_stem` keys say which review it
is. `meta.json` under `tomo-tmp/review/<stem>/` is content-free and may be
gone (a cleaned `tomo-tmp`, a new container home); it adds Tomo's own
record — `steps_done`, `failed_step`, `withdrawn`, `applied_reported` —
nothing more. A missing or unparsable `meta.json` therefore counts as
absent, never as an error: an approved document with no meta and no set is
`failed-delivery`, which offers resume or drop — the honest answer when the
delivery's record is lost — while an approved document with no meta but a
set in the inbox is whatever the set says. A document whose frontmatter
Kado cannot read or that carries no `review_period` is listed under
`skipped_review_docs` with its reason rather than dropped.

## WHY the Stem Falls Back to `<period>_review`

WHY: SDD Data Storage Changes fixes the stem as `<period-name>_review`.
A document written before `review_stem` existed, or one whose key the user
removed, still names its period; deriving the stem from it keeps `meta.json`
and the set JSON reachable instead of listing a review no later step can
act on.

## WHY One Stem Guard (`safe_stem`) Lives Here

WHY: a stem names a folder *under* `tomo-tmp/review/`, and three callers
joined it onto that root — `read_meta` here, `review-read.py --stem` and
`review-doc.py --stem`. Each had its own copy of the check, and the copies
drifted: `review-read.py` refused `.` while `review-doc.py` did not, so
`review-doc.py write --stem .` would have staged, written and then deleted
files in `tomo-tmp/review` itself, beside every other review's folder, and
`read_meta(root, ".")` read `tomo-tmp/review/meta.json` as if it were a
stem's. One predicate, `safe_stem`, now refuses what cannot be a plain
folder name — empty or whitespace, `.`, `..`, anything carrying `/` or
`\` — and the three callers call it; the CLIs keep their argparse
`type=` wrappers only to turn `False` into exit 2. It lives in this module
because this module already owns the stem's shape (`STEM_SUFFIX`) and the
stage layout (`<root>/<stem>/meta.json`); a guard beside the layout it
guards cannot drift from it. The check is a substring test on purpose: a
`..` anywhere (`a..b`) is refused although it is a legal folder name, since
no `<period>_review` stem ever contains it and the cost of a false refusal
is one exit 2.

## WHY the Listing Is Ordered by Period Start

WHY: SDD `OUTPUT: list ordered by period`. Weeks and months interleave
(`2026-W09`, `2026-03`, `2026-W13`), so the order is the period's first day
under the configured week rule **and the configured name formats**, name as
the tie-breaker; a period name no format parses sorts last so the listing
never hides it. The sort is stable across runs, which lets the skill number
the offers.

`open_reviews` takes `formats` (merged over `period.DEFAULT_FORMATS`, the
same merge `period.parse_args` does) because the first version ordered with
the defaults alone, and the default week format `GGGG-[W]WW` carries ISO
tokens: `period.parse_name` applies the ISO rule to upper-case week tokens
whatever `rule` says (`iso-tokens-need-iso-rule`), so the configured rule
was silently ignored. Under a confirmed Sunday/1 setup with `gggg-[W]ww`,
`2027-W01` starts 2026-12-27 and belongs before the month `2027-01`; ordered
with `GGGG-[W]WW` it starts 2027-01-04 and lands after it. The T2.3 code
review caught this; `start` now passes `review_config.configured_formats`
together with the rule, so the listing counts weeks the way the request does.

## WHY the Kind Is Inferred by Parsing, Not by a Letter

WHY: a document without `review_kind` (written before the key existed, or
the key removed by the user) still needs a kind for the listing and for the
format its period is parsed with. The first version guessed `week` when the
name contained a `W`; that letter is an artefact of the default format, not
of the kind — a week named under `gggg.ww` (`2027.01`) carries no `W` and
was listed as a month, parsed under `YYYY-MM` and sorted last. The kind is
now the first kind, in `KINDS` order (week before month), whose configured
format parses the name; a name no format parses falls back to the letter
guess so the listing still shows a kind for it. Week first because a name
that parses under both (a week format `gggg-ww` and the month format
`YYYY-MM` both accept `2027-01`) is an ambiguity the frontmatter normally
settles; the fallback only has to be deterministic, and the SDD's listing
puts weeks first.
