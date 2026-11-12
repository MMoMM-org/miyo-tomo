# WHY: periodic-review (skill)

> Rationale for `tomo/dot_claude/skills/periodic-review/SKILL.md`.
> Spec 045 (issue #31, `docs/XDD/specs/045-weekly-monthly-review/`). ADR numbers and F-AC ids refer to its
> `solution.md` and `requirements.md`. Entry point: [review](../commands/review.md). Precedent:
> [note-from-template](note-from-template.md) (spec 044), whose shape this skill copies.
> The scripts' own WHY: [review-session](../../scripts/review-session.md), [review-read](../../scripts/review-read.md),
> [review-doc](../../scripts/review-doc.md), [review-instructions](../../scripts/review-instructions.md),
> [vault-config-writer](../../scripts/vault-config-writer.md).

## Why the Skill Owns the Order and Scripts Own Every State Change (ADR-1)

WHY: `/review` has the 2-pass shape of `/inbox` and `/note`: Pass 1 writes a document the user edits, Pass 2 turns
the edited document into an instruction set. The PRD forbids a black box (every item editable before it lands) and
Constitution L1 demands that the domain behaviour is testable without an AI. So the skill holds only the dialogue
order — start, setup, read, propose, write the document, continue, preview, deliver — and every read of the vault,
every write, every rendering and every state decision is a script call with one JSON object on stdout. The model does
exactly one creative step: it reads `read.json` and writes `proposals.json` (ADR-12). The skill writes two local files
itself and nothing else: `proposals.json` and the confirmed-setup JSON that `review-session.py setup-input --confirmed`
reads. Everything the skill tells the user comes from a script's output; it never reads the vault directly and never
composes YAML, markdown documents or instruction sets by hand. The price is more scripts than an LLM-driven flow and a
skill whose prose is outside the eval gate (see "Why There Is No Eval Gate").

## Why /review Runs in the Main Session, Not as a Subagent

WHY: The skill asks the user at the setup confirmation, the week question, start over, Deliver or Abort, resume or
drop, and the place question. Subagents cannot ask the user and cannot use the Agent tool (Anthropic platform
constraint), so the command shim loads the skill in the main session and no step dispatches a subagent. Revisit if
the platform changes.

## Why Every Question Is Plain Text and the Turn Ends There

WHY: Spec 044 learned this live, three times (sessions c573b7b7, afc60d6c, 2e8fb1d3 in
[note-from-template](note-from-template.md#why-questions-about-a-draft-or-a-list-are-plain-text)): calling
`AskUserQuestion` after printed content fails on claude-sonnet-5-5 — the model treats its own tool output as shown to
the user and calls the dialog straight after a Read, with no visible text, and the user approves what they never saw.
`claude plugin eval` never offers `AskUserQuestion` either, so the paid evidence can only prove the typed path. Every
question of this skill is therefore the same message as the content it refers to: the content, then one numbered
option line as the last line (`1 Deliver · 2 Abort`, `1 Confirm · 2 Correct · 3 Abort`, `1 Resume · 2 Drop`,
`1 Continue · 2 Start over · 3 Abort`, `1 Replace · 2 Keep it`, `1 Start over · 2 Abort` — also for the marker
without a heading above it, see Pass 2 — and for a heading choice the numbered `headings` list with
"Which number, or 0 Abort?" so every listed number stays valid), and the turn ends.
The next user message is the answer, mapped to an option by number or by word; anything else is asked again in plain
text. There is no second channel: the message the model writes is the one the user reads. The numbers follow spec
044's 0.2.9 decision (one key instead of a typed word) and stay consecutive. The preview-in-dialog form of `/note`
0.2.11 is not used here (owner decision at T5.2): the review section is the user's own approved text and short, so a
plain reprint costs little, and the `/note` form is still unproven in Hashi's session view. `AskUserQuestion` is
therefore not in the skill's `allowed-tools` and not named in its text at all. Revisit if the platform shows tool
inputs to the user or the model reliably prints before a tool call.

## Why Session Start Is a Script

WHY: `review-session.py start --args` parses `$ARGUMENTS` verbatim (`--args='<text>'` in single quotes, each `'`
written as `'\''`, so a request beginning with `-` is not read as an option and nothing in the user's text is
expanded by the shell). It resolves the period under the configured week rule and name formats, reports the setup per
kind (`present` / `missing`) and lists the open reviews with their state. A prose "if the argument has a W in it"
depends on the model; the script's answer is deterministic and tested. An unusable argument comes back as
`error.kind` with `expected` and one `example` (`invalid-period`, `not-periodic-note`, `unknown-argument`, F2-AC5,
F2-AC7) or, for a period that has not ended, `unfinished-period` with `last_finished` (F2-AC6): the skill shows
exactly that and stops, and nothing is written. A week or month without a year (`W13`) is resolved to the most
recent finished one and `year_inferred` is true, so the skill names the year before reading (F2-AC4). `status:
stopped` with `kado-unreachable` or `kado-auth` is shown and ends the run before anything else, and
`problems: [inbox-not-configured]` means no Kado call was made at all. The skill never guesses a period from the
argument text.

## Why Open Reviews Come First (F2-AC1)

WHY: A review document in the inbox is the user's edited work, and a delivered set that Hashi has not applied is a
pending change to the vault. Starting a new period first would bury both, and an edited review could be lost to a
second document for the same period. So the skill handles every entry of `open_reviews` before the new request,
in the order `start` lists them (by period start), with the request itself last — the same precedence as `/note`'s
kept drafts. The state decides the offer, and the state comes from the script (`lib/review_state.stem_state`, ADR-6),
never from files the model inspects:

- `failed-delivery` → `1 Resume · 2 Drop`: resume reruns `review-instructions.py deliver` (steps already done are
  skipped, F5-AC10); drop runs `review-instructions.py drop` (see "Why drop Withdraws").
- `open` → `1 Continue · 2 Start over · 3 Abort`: continue is Pass 2 (see "Why Pass 2 Is parse, Then preview"); start
  over goes through `review-doc.py replace` (see "Why Start Over Asks Twice"); abort leaves the document as it is.
- `delivered` → one line: the set waits for Hashi or for the user to apply it by hand; no second set is delivered
  (F6-AC2, the script would refuse it as `set-exists` anyway).
- `move-refused` / `target-missing` → one line each: the target existed when Hashi applied the move, so the inbox
  copy is still there; or the target is gone since delivery (F6-AC4). Nothing to deliver; the user decides in
  Obsidian.
- `applied` → one line, listed once (`start` records `applied_reported`); `notices: [applied-not-recorded]` means the
  line will show once more next time.

`skipped_review_docs` (`frontmatter-unreadable`, `period-missing`, `stem-unsafe`) are named in one line each, never
dropped silently: a document Tomo cannot classify is still the user's file. When the request names the same period as
an open review, the open review is the request. Only after the list is handled does the skill turn to the new request.

## Why Setup Runs Before the First Read and the Request Continues in the Same Session (F1)

WHY: Nothing can be read before Tomo knows where the periodic notes live, how they are named, which daily sections
count and where the review goes. `start` reports `setup.week` / `setup.month`; when the requested kind is `missing`
(F2-AC8), or the request is `setup` (F1-AC2, `current` carries the saved values or their `invalid` pointers), the
setup dialogue runs for that kind: `review-session.py match --kind` previews the proposal against the existing notes
(folder, format, first day, min_days, template and its kind, heading, place, own sections, daily sections, language,
with `evidence.matched` and `evidence.unmatched` so the user confirms against real note names, F1-AC1), the skill
prints the proposal, the `evidence` and every line of `hints` (the script's own wording for a `kado-none` listing, a
folder without comparable notes and an unreadable template, so the access hint is never paraphrased) and asks
`1 Confirm · 2 Correct · 3 Abort`. A correction of the folder, the name format, the first day or the week-1 rule
reruns `review-session.py match --kind --folder --format --first-day --min-days` with the corrected value as its flag
and shows the new matches before asking again (F1-AC8) — the skill never computes matches in its head, because they
must come from the same code that will parse the names later. A correction of a value `match` takes no flag for
(heading, place, own sections, daily sections, language) is printed back in the proposal and carried in the confirmed
file; `setup-input` validates it there, so a wrong value is refused by the schema, not by the model. Confirm writes
the `proposal` object of the last `match` output, as it is, to `tomo-tmp/review/confirmed-<kind>.json` (with
`daily_path_fix` from the same output only when the user confirmed it, F1-AC9); `review-session.py setup-input --kind
--confirmed` validates the file against the schema and the format rules before the writer sees it (`status:
invalid` with pointers → `1 Correct · 2 Abort`, and Correct is the same correction branch), and `vault-config-writer.py review --input` saves exactly the keys
the input names, text-preservingly (ADR-5): the skill never composes YAML. No other setting changes. Both helper
files are removed after the save; they are not state.

After the save the skill reruns `review-session.py start --args` with the original argument and continues the
request in the same session (F1-AC9): the user asked for a review, not for a setup, and `start`'s period resolution
depends on the rule just saved. The open reviews it already handled are skipped on the rerun. Abort saves nothing and
writes nothing (F1-AC10): the writer is called only after Confirm, and no vault write happens before Pass 1's `write`.

`/review setup` (F1-AC2) runs the same dialogue for the week kind and then for the month kind, each starting from
`current.<kind>` as `start` reports it (the saved values, `null`, or `invalid` pointers, printed before the
proposal), and ends without a review: the user asked for the setup. Abort ends the setup; a kind already confirmed
and saved before the abort stays saved, because the writer ran at its Confirm — the same rule as `/note`'s saved
`note_include`.

## Why the Week Question Is Asked in Plain Words (ADR-7)

WHY: Which day starts a week and which week is week 1 decide which note a review targets; a wrong rule creates a
duplicate weekly note (PRD risk 1). `match` infers the rule from the dates the user's own weekly notes carry
(`journal-start-date`, day headings) and reports `evidence.week_rule` as `inferred`, `ambiguous` or `default`. Only
when it is `ambiguous` — the notes disagree or carry no dates — does the skill ask, in plain words, not in ISO
vocabulary: "Which day does your week start on? Is week 1 the week with 1 January, or the first week with at least
four days in the new year?" (F1-AC6). The answer is mapped to `(first_day, min_days)` — "Monday, four days" is ISO
`(Monday, 4)`, "Sunday, 1 January" is `(Sunday, 1)` — and passed back as `--first-day` and `--min-days` to `match`,
whose new matches show which existing notes the rule no longer fits (F1-AC5) before the user confirms. The Obsidian
periodic-notes plugin configuration is never read for this (owner decision: "wenn wir das nicht erkennen können
fragen wir den user"), because the plugin's setting and the user's actual notes can disagree, and the notes are the
truth. With `inferred` or `default` the rule is shown with the proposal and the ordinary Confirm covers it; asking
anyway would be a spurious question.

## Why `kado-none` and an Unreadable Template Are Never "Nothing There"

WHY: A Kado key without read access to a folder gets an empty listing, indistinguishable from an empty folder (Rule
6 of the SDD; memory: an empty Kado search hides a denial). So `evidence.folder_listing: kado-none` is reported as
"Kado returned none for this folder — it may be empty, or the key may not reach it", and the skill asks before
proposing to create notes there. The same wording applies to `template_kind: unreadable`: the skill says the
template may be unreadable because the key has no access, proposes a plain note (title and review section) and
continues (F1-AC7); `missing` proposes the plain note without the access hint. In Pass 1, `review-read.py`'s
`kado_empty` sources and the `check-key-access` advice are reported the same way (F3-AC9). The skill never says a
folder is empty or a note does not exist.

## Why the Period Read Is a Script and `status` Is Branched First

WHY: `review-read.py --period --kind` reads the whole period under the pacer — every daily, the day after for its
yesterday fields, the same-day linked notes, the task notes, a month's weekly notes, the vault growth — and writes
`read.json`. The model reading the vault itself would read other days through "On This Day" embeds, execute nothing
but follow Dataview blocks wrongly, and hit the rate limit with no accounting; the script owns the same-day rule, the
pacing and the report (F3-AC1 to F3-AC13). The skill branches on `status` before any other key: a `stopped` output
(`kado-unreachable`, `kado-auth`, `dailies-not-read`, `setup-missing`, `setup-invalid`, `daily-not-configured`)
never carries `nothing_to_review`, and reading `nothing_to_review` off a stopped output would turn a connection
failure into "your week was empty". With `status: ok` and `nothing_to_review: true` the skill says no daily of the
period holds content, adds the access hint (an empty result may also mean the key cannot read the folder) and stops;
nothing is written (F3-AC9). Otherwise the report is shown as the script prints it — per day which dailies were
found and in what state, which linked notes were missing or not readable — plus the pacing line: `retried`,
`waited_s`, `not_read` and the `raise-kado-limit` advice when Kado turned calls away (F3-AC12). The skill never
summarises the report into "everything was read" when `not_read` is non-empty; the document will name the missing
days at its top (F3-AC13) and the user must see that before approving.

## Why the Model Writes Only `proposals.json` (ADR-12)

WHY: Habits, vault growth and the link differences of a month are numbers and lists; computed by the script they are
deterministic and testable (F8), and the model gets them as facts in `read.json`. The model's job is the one thing a
script cannot do: read the period's text and propose the items — what got done, what stayed open, recurring themes,
and for a month what only the weekly notes hold and what they left out — in the review language, each with at least
one link to a daily inside the period (F4-AC3). It writes them to `proposals.json` in the schema
`tomo/schemas/review-proposals.schema.json` and nothing else: no document, no section, no frontmatter.
`review-doc.py write` validates the file; a `proposals-invalid` refusal names the pointers, the skill rewrites the file once, and a
second refusal ends the run — looping on a schema the model cannot satisfy would burn the user's time. The model
proposes only Tomo's own section, never text for the sections the setup names as the user's own (F4-AC7).

## Why the Review Language Is Read From the Config File

WHY: The proposals must be in the review language of the setup (F4-AC5) and `proposals.json` names it, but no script
of the ordinary path prints it: `start` reports the setup only as `present` / `missing`, `review-read.py` prints the
report and `read.json` carries the period's content, not the setup. The skill therefore reads the one key
`review.language` from `config/vault-config.yaml` — the instance's own configuration, not the vault, and a value the
user confirmed in the setup dialogue — before it writes `proposals.json`. The alternative calls (`start --args='setup'`
for `current.<kind>.language`, or `match` for a proposal) each cost Kado calls for a value that is already on disk.
Known gap, noted at T5.2: a `language` key on `review-read.py`'s output would remove the only config read of the
skill; until then the skill reads that key and nothing else from the file and never writes it.

## Why Pass 1 Ends With `write`, Deletes the Working Files and Ends the Turn (ADR-2, ADR-9)

WHY: `review-doc.py write --stem --proposals` is the only vault write of Pass 1: `<period> Review.md` in the inbox,
with the target note and whether it exists, the unticked Approved box and the grouped items (F4-AC1). The skill
reports `doc_path`, `target`, `target_exists`, the `counts` per group and `rejected` items, then ends the turn: the
user edits the document in Obsidian, and the next `/review` finds it as an open review (ADR-2: the open state lives in
the vault, not in `tomo-tmp`, because the user edits between passes). `write` deletes `read.json` and
`proposals.json` once the document is written (ADR-9): the journal content the model read has no job after that, and
the stage keeps only the content-free `meta.json`. The refusals are shown verbatim: `doc-name-taken` names the file
that is not Tomo's and nothing is overwritten; `review-exists` is the start-over case (next section);
`kado-write-failed` means nothing was claimed as written. Abort at any point before `write` deletes nothing in the
vault, because nothing was written there.

## Why Start Over Asks Twice (F6-AC1)

WHY: Replacing the review document destroys the user's edits in it. So when the user chooses Start over for an open
review, or `write` refuses with `review-exists` (Tomo's document for the period already exists and the stage files are
kept), the skill names the document that will be replaced (`doc_path`) and asks again, `1 Replace · 2 Keep it`.
`review-doc.py replace --confirm` writes the new document over Tomo's own from the kept `read.json` and
`proposals.json`; `review-doc.py replace --abort` deletes those two files and keeps the document. The script itself
answers `needs-confirm` when neither flag is given, so the skill cannot replace without the flag, and the decision
is recorded in the call. A rerun of the whole period (read again, propose again) is the same path: `write` refuses,
the user decides.

`replace --confirm` is `write`'s own path with the one refusal lifted, so it answers with `write`'s statuses — `refused`
(`doc-name-taken` when the file turned into a note that is not Tomo's between the two calls, `proposals-invalid`,
`read-missing`, `setup-invalid` and the rest), `stopped` (`kado-write-failed`, a reader stop) — and `replaced` where
`write` says `written`. The skill therefore branches on its `status` by the same list it has for `write`, with
`replaced` read as `written`; the first draft of the skill reported the output "as a written one" without a branch,
which would have read a `refused` or `stopped` answer for `doc_path` and `counts` it does not carry (T5.2 fix round).

## Why Pass 2 Is `parse`, Then `preview`, and Deliver Is a Plain-Text Question (F5-AC1, F5-AC2)

WHY: The document is the source of truth, so Pass 2 reads it fresh every time. `review-doc.py parse --stem` reads the
edited document back through Kado and prints counts and ids only — `approved`, `nothing_to_deliver`, the kept /
unticked / deleted / added counts and the warnings — and writes nothing; the skill reports the counts so the user sees
what their edits did. `status: not-found` means the document is gone or renamed beyond recognition: the skill says
so and asks `1 Start over · 2 Abort` — start over is Pass 1 again for that period, abort leaves everything as it is.
An unticked Approved box ends the turn with the box named (F5-AC1); `approved-line-missing`
says how to restore `- [ ] Approved` at column 0. The other parse warnings get one plain line each: `unknown-group` (a
heading the parser does not know; its items do not land), `duplicate-group` (the second heading of that name is
ignored), `frontmatter-broken` (the document's frontmatter could not be read; the period is taken from `meta.json`),
`item-outside-group` (an item above the first heading, filed under unknown). Then
`review-instructions.py preview --stem` builds the plan against the target note as Kado holds it now and prints `section_md` — the only note content
that ever reaches the console, on purpose: the user must see the section as it will land, with their own text and
the items they added — plus the `target`, `mode` (`insert`, `replace`, `new-note`) and `place`. The skill prints all
of that and asks `1 Deliver · 2 Abort`; a change is made by editing the document and continuing again (F5-AC2), never
by telling the model what to change, because the document is the only editing surface. Abort runs nothing and
writes nothing: the document stays open for the next `/review`.

The preview's `problems` refuse and `notices` inform, and the skill never confuses the two. The refusing names are
`lib/review_delivery.REFUSING`, and `tests/test_review_skill.py` reads that tuple and demands a stop line in the
skill's Pass 2 for every member — a token the scripts add without a skill line fails the suite, which is the gap
that let two members through the first time (T5.2 fix round). Refusing: `not-approved`, `approved-line-missing`
(the plan's gate refuses it before `not-approved` — `lib/review_actions._gate` — so `preview` and `deliver` can
answer it as well as `parse`; the skill says how to restore `- [ ] Approved` at the line start and stops),
`nothing-to-deliver` (everything unticked → Abort or start over), `place-missing` and `place-too-deep` with `mode`
`insert` or `new-note` (the configured place is not in the target or would push the review heading past level 5: the
skill lists the `headings` the note has and asks for one or Abort, then reruns `review-instructions.py preview
--place-anchor` with the chosen heading, F5-AC7), `user-heading-collision` with `mode` `insert` or `new-note` (a
same-named heading of the user's without the marker is never replaced, and the review never lands inside an own
section: another heading or Abort, offered once — see "Why the Heading Pick Is Offered Once"), `set-exists` (a set
for the stem waits for Hashi; nothing is delivered, F6-AC2).

The same three problems with `mode` `replace` are a different case. The Tomo marker was found in the target note, so
the plan is a `replace_section` on the heading directly above the marker, whatever the user chose at setup
(`lib/review_actions._existing_note`, marker branch): `--place-anchor` is never read there. The branch refuses in
three ways — no heading above the marker (`place-missing`, `place.anchor` null), the heading above it is one of the
user's own sections or an earlier heading of the same text shadows it (`user-heading-collision`), the heading is
level 6 so a review heading there would pass level 5 (`place-too-deep`) — and every one keeps `mode` `replace` and
the `headings` list. Offering the heading pick for any of them reruns `preview --place-anchor` into the same marker
branch and the same refusal, forever; the first fix round saw this for `place-missing` only, and the code review of
that round found the other two (second T5.2 fix round). The SDD's Error Handling rows for all three say "names the
problem; Start over or Abort" in replace mode, so the skill has one bullet for the three with `mode` `replace`, placed
before the heading-pick bullets, that says plainly what is wrong with the heading above the marker and asks
`1 Start over · 2 Abort` — start over is Pass 1 again for the period, abort leaves the document open; the user fixes
the note in Obsidian (moves the marker under a heading of Tomo's, renames the colliding heading, or lifts the
section). The heading-pick bullets name `mode` `insert` or `new-note` explicitly rather than "otherwise", so exactly
one bullet matches each (problem, mode) pair for a literal model.

## Why the Heading Pick Is Offered Once for a Collision (Third T5.2 Fix Round)

WHY: `user-heading-collision` with `mode` `insert` has two causes in `lib/review_actions._existing_note`, and only
one of them is cured by a heading pick. The first: the target note already holds a heading named like the review
heading, without Tomo's marker (`_first(headings, setup.heading)`, checked before `_insertion`). That check never reads
the anchor, so a rerun with `--place-anchor` refuses again whatever heading the user picks — the only cure is to rename
or remove that heading in Obsidian (or move the marker under it so the rerun becomes a `replace`). The second: an
`inside` placement into one of the user's own sections (`_insertion`), which is anchor-dependent, so a pick of a
heading that is not an own section lands. `new-note` mode has the second cause only (the template is not searched for
the review heading). The preview output cannot tell the two apart: both refuse through `_refuse` with the same
`problems`, the same `headings` list, `mode` `insert` and a `place` that still holds the constructor's `anchor` and
`placement` without `level`; nothing in the output names the configured review heading, and `section_md` is empty on
a refusal. `place.placement` `before` would prove the first cause, but `inside` proves nothing, so a branch on it would
leave the loop open. The owner chose a skill-only fix, no script change.

So the pick is made loop-safe instead of cause-aware: the first `user-heading-collision` in `insert` or `new-note` mode
lists the `headings` and asks for one; when the rerun with `--place-anchor` (from this bullet or from the
`place-missing` / `place-too-deep` pick) answers `user-heading-collision` again, the skill names the clash — the note
holds a heading named like the review heading, or the picked heading is an own section — tells the user to rename or
remove the clashing heading in Obsidian, asks `1 Start over · 2 Abort`, and never prints the list or asks for a number
a second time. The price is one wasted pick and one preview read for the first cause; the alternative, a model that
keeps offering the list, was the observed defect (the second fix round's review found it after the replace-mode fix).
The after-pick bullet stands before both pick bullets, and the first-collision bullet says "before any heading pick",
so exactly one bullet matches a literal model's rerun. Both pick bullets say to branch on the rerun by the same list,
so the after-pick bullet is reached rather than the pick repeated. Notices:
`heading-renamed` (the marker was found under a renamed heading; the section is replaced there, F6-AC3),
`target_appeared` (the user created the target since Pass 1; the plan targets it instead of a new note, F6-AC4),
`variant_missing` and `templater_hint` (the template's Tomo variant is gone or the template holds Templater code; the
readable instructions tell the user to run Templater after the move, ADR-8), `template_unmergeable` (a plain note is
built instead), `unlanded-items` (kept items under an unknown heading do not land; the count is named). A notice
is said in one line and the Deliver question still follows.

## Why `deliver` Is Branched on `status`, Then on `problems` or `failed_step`

WHY: `review-instructions.py deliver --stem` (with `--place-anchor` when the user chose one) writes, in order, the new
note (new-note mode only), the set JSON and the set MD through `lib/staged_delivery`, then marks the document delivered
with one write guarded by the `modified` the reader saw (ADR-11; steps `note → set_json → set_md → doc_mark`). The
skill never runs those steps itself. `status: delivered` or `resumed` is reported with the target, the place, the set
JSON and the set MD paths and the next step, apply in Hashi or by hand (F5-AC11). `status: refused` names the
`problems` and nothing was written: `name-taken` names `exists_path` (a note at a payload's path that is not Tomo's
identical text; never overwritten), the plan problems are the preview's. `status: stopped` carries `failed_step` and is
resumable: `doc-changed` means the document was edited or is open with unsaved edits since the preview; the skill says
to save it and run `/review` again, and the payloads already written count as done; `kado-write-failed` is a Kado
refusal or failure at that step. Either way the next `/review` lists the stem as `failed-delivery` with Resume / Drop
(F5-AC10). The skill reads `status` first because the same key `problems` appears under `refused` and `stopped` with
opposite meanings for the user: fix the document, or just try again.

## Why `drop` Withdraws and Abort Before Delivery Writes Nothing (ADR-13)

WHY: Abort at the Deliver question is free: nothing was written, the document stays open. Drop is offered only for a
`failed-delivery`, where files may already be in the inbox. Kado offers Tomo no delete, so
`review-instructions.py drop --stem` cannot remove them; it withdraws instead: once any delivery step began it writes the set JSON with an empty
`actions` list (schema-valid, nothing for Hashi to apply) and an MD that says withdrawn and names every file the
delivery left, a lone new note included, so the user can delete them in Obsidian; before any step began it removes
only the stage. The skill reports `status: withdrawn` with the `paths`, or `dropped` with `removed`. `already-applied`
is refused: Hashi applied an action, so the set is the vault's history now and nothing is withdrawn and nothing more
is delivered (the skill says so and offers nothing). `set-changed` means the set was edited between read and write;
the skill runs drop once more. A withdrawn review is never listed again.

`kado-write-failed` from `drop` is not "nothing was withdrawn" (the first draft of the skill said that; T5.2 fix
round): `drop` writes the withdrawn set JSON first and the readable MD second, and marks `meta.json` only after
both. A failure on the second write leaves the set already empty — nothing for Hashi to apply — while the MD in
the inbox still lists the actions and the stage still says a delivery failed. The skill therefore says the
withdrawal may be partly written and nothing else changed, and runs `drop` once more in the same turn: a rerun
reads the empty set back (not applied), rewrites it under the guard and writes the MD, then marks the stage. Once,
not until it works: a Kado that refuses every write would loop. The rerun has to happen in the session, because the
next `/review` would not offer it — `lib/review_state.review_state` lists no review whose set has an empty
`actions` list, so the half-withdrawn stem is invisible to `start` while its MD still names the actions. The second
failure is shown and the run stops; the user sees both inbox files in Obsidian. Closing that listing gap (a
`withdrawn` that reads `meta.json` only) is a script decision outside the skill.

## Why the Skill Does Not Call `status` in the Flow

WHY: `review-instructions.py status --stem` names one stem's state through the same `stem_state` function that
`start` runs per listed document, so the two cannot disagree. The skill gets every state it needs from
`start`'s `open_reviews` at the beginning of the run, and after `deliver` or `drop` the script's own `status` field
says what happened; a second call would cost one set read and the probes for a value already in hand. `status` is
the direct question — for a test, the owner, or a later skill step that must re-check one stem (for example a
`doc-changed` resume in the same session) — and it answers `applied` even after `start` reported it once, because the
"offered once" rule belongs to the listing. The skill as shipped at T5.2 does not call it at all: every state it acts
on is in `start`'s listing or in the `status` field of the script it just ran, and a `doc-changed` stop ends the
run with "save the document and run `/review` again", so no re-check is needed in the same session.

## Why the Privacy Boundary Is Documented in the Skill, Not Cleaned Up (ADR-9, F7)

WHY: Tomo's own records stay free of the journal: every review script prints counts, paths, dates and states only,
stderr carries an exception's class name and nothing else, and the cost log takes the numbers the skill reports
(F7-AC1, tested by `tests/test_review_privacy.py`). The skill keeps that boundary on the console: it prints the
scripts' reports and `section_md` — the user's own approved section — and never quotes `read.json`, a daily, a
journal answer or a tracker value into its reply. Where the content does rest — the session transcript in the
container home (the model read `read.json`), `tomo-tmp/review/<stem>/read.json` until `write` or `replace --abort`
deletes it (a session that ends without either leaves it until the next `/review` of that stem), the inbox document —
is named in `PRIVACY.md` with the advice to protect instance and home like the vault. No cleanup script and no
cleanup promise: the data is local anyway, a script would be forgotten or inflexible, and a promise Tomo cannot keep
for the transcript would be false. The skill tells the user nothing about this; the documentation does (F7-AC2).

## Why Script Errors Are Shown Verbatim

WHY: The review scripts write their `error.detail`, `expected` and `example` for the user and name only the problem
class, never a title, a path of a journal note or note text. A paraphrase would hide the cause ("something went
wrong" for `unfinished-period`) and could add what the script left out on purpose. Exit 2 (a bad invocation) and
exit 1 (an unexpected exception, class name on stderr) are shown as they are and end the run; nothing the user could
type cures them.

## Why Scripts Run From the Working Directory, Not the Skill Directory

WHY: The same observed deviation as `/note`: the Skill tool result begins "Base directory for this skill: …", and
with "run every script from the instance root" the model cd'd into the skill's base directory, so `python3
scripts/…` exited 2 and three calls were spent finding `scripts/`. The sentence names the session's working directory
and forbids the skill's base directory.

## Why STRICT Is Rare

WHY: Per the repo rule, a `STRICT` block with a one-line `Why:` is only for a deviation actually observed in a run.
The runtime text holds imperatives only; every rationale lives in this file. The skill ships without a `STRICT`
block (decided at T5.2): the deviation spec 044 observed was a dialog called after a bare Read, and this skill has no
dialog to call — `AskUserQuestion` is not in its tools and every question is the plain-text form. A `STRICT` is
added only when a `/review` run shows a deviation of its own.

## Why There Is No Eval Gate

WHY: ADR-1's trade-off: the skill's prose is not covered by the CLAUDE.md eval gate, because gating every later edit
would cost a paid run each time. No eval case exists under `evals/` for `/review` (paid evals are owner-instructed;
an owner-run case for the open-review-first order and the plain-text Deliver / Abort turn end stays an option).
Later edits are reviewed by hand and by the static tests of `tests/test_review_skill.py`: every `python3
scripts/review-*.py` call in any `tomo/dot_claude/skills/**/SKILL.md` parses with the called script's own argparse
parser (prefix abbreviations refused), every subcommand and flag named in a backtick mention exists in the parsers,
every Error Handling row of the SDD has its user message in the skill, every `parse` warning has its line, `status`
is branched before any other key, and the option lines this document names appear in the skill verbatim. The same
parser-derived contract (`tests/review_cli_contract.py`) is what `tests/test_review_why_docs.py` applies to this
document, so the three cannot drift apart silently.

## Why the Runtime Details Look the Way They Do

WHY: The stem is `<period>_review` (`2026-W13_review`), given as `--stem` to every Pass 1 and Pass 2 call,
`review-read.py` included, because `start` names the period and one explicit stem keeps one review's stage apart
from another's and from the script's default. `--today` is a suppressed test flag and never passed by the skill. The
confirmed-setup JSON is `tomo-tmp/review/confirmed-<kind>.json`, read by `setup-input`, whose `--output` defaults to
`tomo-tmp/review/setup-<kind>.json`, the file the writer's `--input` takes; both are helper files, not state, and
removed after the save. The skill pins no `model`: the proposals are the model's work (ADR-12), so it runs on the
session's model. `user-invocable: true` and an `argument-hint` make the skill itself show in the `/` menu beside the
shim, as `/note` does. The description carries `MUST BE USED` per the authoring rules, with a `NOT for` clause that
keeps inbox triage with `/inbox` and single notes with `/note`. `allowed-tools` holds Bash, Read and Write
(`proposals.json`, the confirmed-setup file; Read for `read.json` and the one config key) and nothing that reaches the
vault: every vault access goes through the scripts and Kado. The skill's body follows the `/note` precedent (a Rules
list, then numbered steps) rather than the authoring plugin's Persona / Interface / Constraints layout: the repo rule
for runtime files allows imperatives only, and a persona or an interface block would be prose the model does not act
on.
