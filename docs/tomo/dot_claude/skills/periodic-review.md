# WHY: periodic-review (skill)

> Rationale for `tomo/dot_claude/skills/periodic-review/SKILL.md`.
> Spec 045 (issue #31, `docs/XDD/specs/045-weekly-monthly-review/`). ADR numbers and F-AC ids refer to its
> `solution.md` and `requirements.md`. Entry point: [review](../commands/review.md). Precedent:
> [note-from-template](note-from-template.md) (spec 044), whose shape this skill copies.
> The scripts' own WHY: [review-session](../../scripts/review-session.md), [review-read](../../scripts/review-read.md),
> [review-doc](../../scripts/review-doc.md), [review-instructions](../../scripts/review-instructions.md),
> [vault-config-writer](../../scripts/vault-config-writer.md).
> Spec 047 (issue #270, `docs/XDD/specs/047-review-chunked-read/`) replaced the main session's own read of the period
> with a stage and three agents: [review-digester](../agents/review-digester.md),
> [review-carryover](../agents/review-carryover.md), [review-proposer](../agents/review-proposer.md), planned and
> checked by [review-digest](../../scripts/review-digest.md). Sections that cite spec 047 use its ADR and F-AC ids.

## Why the Skill Owns the Order and Scripts Own Every State Change (ADR-1)

WHY: `/review` has the 2-pass shape of `/inbox` and `/note`: Pass 1 writes a document the user edits, Pass 2 turns
the edited document into an instruction set. The PRD forbids a black box (every item editable before it lands) and
Constitution L1 demands that the domain behaviour is testable without an AI. So the skill holds only the dialogue
order — start, setup, read, propose, write the document, continue, preview, deliver — and every read of the vault,
every write, every rendering and every state decision is a script call with one JSON object on stdout. The model does
exactly one creative step: it reads the period and writes `proposals.json` (ADR-12). Since spec 047 that step is
done by three agents the skill dispatches (digesters, carryover, proposer; ADR-7, ADR-8), each writing exactly its own
stage file. The skill itself writes one local file and nothing else: the confirmed-setup JSON that
`review-session.py setup-input --confirmed` reads. Everything the skill tells the user comes from a script's output;
it never reads the vault directly and never composes YAML, markdown documents or instruction sets by hand. The price is more scripts than an LLM-driven flow and a
skill whose prose is outside the eval gate (see "Why There Is No Eval Gate").

## Why /review Runs in the Main Session, Not as a Subagent

WHY: The skill asks the user at the setup confirmation, the week question, start over, Deliver or Abort, resume or
drop, and the place question. Subagents cannot ask the user and cannot use the Agent tool (Anthropic platform
constraint), so the command shim loads the skill in the main session. For the same reason the three review agents of
spec 047 are dispatched by the skill itself, from the main session (ADR-8): an orchestrating subagent could not start
them. Revisit if the platform ever allows nested Agent dispatch.

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
  (F6-AC2, the script would refuse it as `set-exists` anyway). A set Hashi applied in full is no longer `delivered`:
  the stem reads `applied`, and a rerun of the period (Start over) writes its new set over it — the skill has no line
  for that, because `deliver` answers `delivered` as for any first set (owner decision 2026-11-12, T6.1 fix round;
  docs/tomo/scripts/review-instructions.md, "WHY a Fully Applied Set Is Written Over").
- `move-refused` / `target-missing` → one line each: the target existed when Hashi applied the move, so the inbox
  copy is still there; or the target is gone since delivery (F6-AC4). Nothing to deliver; the user decides in
  Obsidian.
- `applied` → one line, listed once (`start` records `applied_reported`); `notices: [applied-not-recorded]` means the
  line will show once more next time.

`skipped_review_docs` (`frontmatter-unreadable`, `period-missing`, `stem-unsafe`) are named in one line each, never
dropped silently: a document Tomo cannot classify is still the user's file. When the request names the same period as
an open review, the open review is the request. Only after the list is handled does the skill turn to the new request.

An Abort at any question of an open review ends the whole run (Phase 5 drift round). The rule says "on Abort, run no
further script", but the first draft's step 1 said "continue with the next entry, then with the new request, after
each one ends" — read literally, an Abort at `1 Continue · 2 Start over · 3 Abort` ended that entry and the skill went
on to `parse` the next one and to `review-read.py` and `write` for the new request, after the user had said Abort.
The step now says that an Abort at an entry's question ends the run: no further entry, not the new request. The user
who wants the next entry handled runs `/review` again; the price is one extra call, the alternative is a vault write
after an Abort.

A bare `/review` while a review is listed starts no new period (Phase 6 live walk, container session 68459faa; owner
decision). `start` listed open `2026-W13` beside the default request `2026-W45`, and after delivering W13 the skill
read W45 — a week the user never asked for; they typed `/review` to pick up the open review. The decision is the
script's, not a prose rule (see [review-session](../../scripts/review-session.md), "WHY a Bare `/review` Carries No
Request While a Review Is Listed"): with a blank argument and any listed review, `start` returns `request: null` with
`request_withheld: open-reviews`. The step has one line for it — a bare `/review` starts no new period while a
review is listed; `/review <period>` or `/review month` names one — and ends the run after the last entry; the
routing by `request.kind` is reached only with a request. A named period keeps its request beside the listing (the
same-period rule above still applies), and so does `/review month`: the kind word is an argument. When nothing is
listed, a bare `/review` is the last finished week as before (F2-AC2).

## Why Setup Runs Before the First Read and the Request Continues in the Same Session (F1)

WHY: Nothing can be read before Tomo knows where the periodic notes live, how they are named, which daily sections
count and where the review goes. `start` reports `setup.week` / `setup.month`; when the requested kind is `missing`
(F2-AC8), or the request is `setup` (F1-AC2, `current` carries the saved values or their `invalid` pointers), the
setup dialogue runs for that kind: `review-session.py match --kind` previews the proposal against the existing notes
(folder, format, first day, min_days, template and its kind, heading, place, own sections, daily sections, language,
with `evidence.matched` and `evidence.unmatched` so the user confirms against real note names, F1-AC1), the skill
prints the proposal, the `evidence` and every line of `hints` (the script's own wording for a `kado-none` listing, a
folder without comparable notes and an unreadable template, so the access hint is never paraphrased) and asks
`1 Confirm · 2 Correct · 3 Abort`. A correction of the folder, the name format, the first day, the week-1 rule or the
template reruns `review-session.py match --kind --folder --format --first-day --min-days --template` with the corrected
value as its flag and shows the new matches before asking again (F1-AC8) — the skill never computes matches in its
head, because they must come from the same code that will parse the names later. A correction of a value `match` takes no flag for
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

## Why the Template and the Anchor Are Asked Before Confirm (Phase 6 Live Walk)

WHY: the live walk of `/review setup` (container session 5b959432) ended in a dead end. The owner's instance maps no
`weekly` or `monthly` template, while the templates folder holds `t_week.md`, `t_week_privat.md`, `t_week_work.md`
and the `t_month*` siblings; `match` proposed `template: null` and, since the anchor is proposed from the template's
headings, `place.anchor: null`. The user confirmed, `setup-input` answered `invalid` with `/place/anchor`, and the
Correct branch had no heading to offer. Owner decisions (2026-11-12): the dialogue asks for the template and for the
anchor before it offers Confirm; English in the dialogue is fine, the review documents stay in `review.language`.

So `match` lists `template_candidates` — the notes of `templates.base_path` whose name fits the kind — when neither
the mapping nor `--template` names a template (WHY of the words and the order: `docs/tomo/scripts/lib/review_templates.md`),
and the skill asks first, before it prints the proposal, because the answer changes the proposal: `1 <name> · 2 <name> · 0 none`,
numbered on one line in the plain-text form every other question has, `0 none` last so a user who keeps the plain
note types the one number that never shifts. A number reruns `review-session.py match --kind --template` with the name
and the flags of the last `match` call except `--template` and `--anchor` (why: the Template choice paragraph
below), so the chosen template takes the same path as a configured one (read, classified,
its headings proposing the anchor); `0` keeps the first output, whose `template` is null and whose `template_kind`
is `missing` — the plain-note line already covers it, and nothing is saved to the mapping (the writer removes a key
that is not there). The choice is saved through `setup-input` as `template`, the key `vault-config-writer.py review
--input` already writes to `templates.mapping.<weekly|monthly>`; no new writer key, no new schema key.

The answers are carried on every rerun as flags, not remembered by the model (fix round 1 of the live-walk fix,
spec review). The first version said "every later `match` call carries `--template` with the proposal's template
when it is set" — but after `0 none` the proposal's template is null, so the week-rule rerun and every Correct rerun
found no template and the script listed the candidates again; the typed anchor was lost the same way, `needs_anchor`
coming back on each rerun. So the skill defines `<template>` once — the chosen name in double quotes, or the word
`none` for `0`, or the proposal's template when no question was asked — and `<anchor>` as the answer to the anchor
question (or a corrected anchor), and the rule says that every later `match` call of the step carries
`--template <template>` and, once given, `--anchor "<anchor>"`; the week-rule rerun example and the Correct branch
spell both out, because a literal model copies the example and drops a flag the example lacks. A typed name
is an answer too (code review round 1 of the fix): the list is a recall filter — a substring match on the file
name, so `t_weekend` sits next to `t_week`, and a template named without the kind word is not on it at all —
and a user who knows the file types its name; the skill says that a typed name is `<template>` in double quotes,
the same form as a number's name, so the rerun is the same `match --template` call and the script's own
refusal of an unsafe name (exit 2, the usage error) is the only check. Without that line a literal model has no
rule for the typed answer and either asks again or guesses a number.
`review-session.py match --kind --folder --format --first-day --min-days --template --anchor` then answers
without the candidates and without `needs_anchor` (`--template none` lists nothing; `--anchor` sets
`place.anchor` and reads no note), so each question is asked once however often the dialogue reruns (WHY of the
flags: `docs/tomo/scripts/review-session.md`, "WHY `--template none` and `--anchor` Carry the Answers on Every
Rerun"). The `<template>` definition covers the no-question case on purpose: a mapped template is carried as
`"<proposal.template>"` (the flag equals the mapping, harmless), and an empty candidate list (no `base_path`) is
carried as `none`, so a literal model never meets an undefined placeholder.

The anchor: when `match` can propose none — no template, `0 none`, a template whose only heading is its title — it
marks the output `needs_anchor: true` and lists `anchor_candidates`, the headings of the two most recent periodic
notes of the kind. The skill prints them numbered and asks "Which heading, by number or typed?" after the week
question (whose rerun is the output the candidates come from) and before Confirm, puts the answer into
`place.anchor`, and never offers Confirm while the anchor is null: `setup-input` still validates, so the refusal
the walk met can only come from a typed heading that is blank, and the Correct branch then has the list to offer.
The candidates are the user's own headings and reach the console by design, like the `headings` of the Pass 2
place pick; `tests/test_review_privacy.py` names the field.

## Why Setup Asks When the Template Has No Frontmatter Block (Phase 6 Live Walk, 2026-11-13)

WHY: the month live walk chose the raw template `t_month_privat.md` (no `_tomo` variant). Its first line is a
Templater code block (`<%* … -%>`); the opening `---` of its frontmatter is rendered by
`<% await tp.file.include("[[x_frontmatter]]") -%>` and only the closing `---` is literal. Pass 2's `_new_note`
(`lib/review_actions.py`) runs `merge_tomo_block_into_markdown`, which looks for `---` at line 1, finds none and
prepends a fresh block; Templater then ran on file creation and the note carried two frontmatter blocks. A template
that starts with `---` (`t_note_tomo.md`, Templater only inside values) merges cleanly. Owner decision (2026-11-13):
the check and the question belong to the setup — the same step 2 that `/review setup` and a first-run setup inside
`/review week|month` share — and nothing in Pass 1 or Pass 2 asks or checks this: the user decides once, when the
template is chosen, not on every delivery.

So `match` reports `proposal.template_frontmatter` (true when the template's first line is `---` and a later line
closes it — the rule `merge_tomo_block_into_markdown` itself applies, taken from `body_after_frontmatter`, so the
check and the merge can never disagree; false otherwise; null without a template text, because `none`, the candidate
list, a missing and an unreadable template are already covered by the plain-note line) and marks the output
`needs_template_ok: true` when it is false and no answer was carried (WHY of the field and the flag:
`docs/tomo/scripts/review-session.md`, "WHY `template_frontmatter` Is Reported"). The skill asks once, after the
`template_kind` lines and before Confirm, in the plain-text form every other question has:
`1 Use it as it is · 2 I'll create a Tomo variant`. `1` keeps today's behaviour exactly (owner decision: Pass 1 and
Pass 2 unchanged; the raw template is used and Tomo prepends its block as before) and is carried on every later
`match` call of the step as `--template-frontmatter-ok <ok-template>`, the fourth flag of the carry rule — a flag,
not a memory, for the reason the section above gives (`review-session.py match --kind --template --template-frontmatter-ok`
then sets no `needs_template_ok`). The flag names the template the answer was given for, and the skill freezes that
name as `<ok-template>` when the answer is given, so a Correct to another template without a block asks again for
that template (the script honours the flag only when it names the resolved template), while a stale flag on a
template with a block is harmless. The Correct branch names the flag beside the other three and points back at the
question line, because a literal model that reruns `match` from the Correct branch otherwise never reads the
`needs_template_ok` of the new output. After `1` the skill continues with the proposal it already printed and runs
no `match`: the answer changes nothing in the proposal, and the flag only matters on a later rerun. It also names
no flag or field to the user. Both were added in #259: in the spec 045 live walk (session 269b1964, lines 83 and 142)
the model reran `match` after `1`, told the user that "`needs_template_ok` is no longer set", and printed the whole
proposal again. That cost one turn per kind and exposed a script field the user cannot act on. `2` is the Abort branch with one more sentence: nothing is saved for that
kind, and the user is told how the way out looks — a `_tomo` variant of the template next to it (`<template>` with
`_tomo` before `.md`, the `template_variant` convention of ADR-8) whose first line is `---` and whose frontmatter
is closed by `---`, then `/review setup` again and the variant chosen. A variant is the way out, not a code change,
because the owner handles the same template's `tp.file.move` by a variant too, and because only the user knows which
Templater lines of the frontmatter the variant may keep as literals.

## Why the Confirm Step Carries the Section Mapping Table (Spec 046 F2, F6, F7; ADR-8, ADR-9, ADR-13)

WHY: spec 046 lets the vault keeper say which sections of their own template receive review material. The PRD
asks for it in the confirm step that already exists (F2-AC2: "one table in the existing confirm step — no extra
question turn"), because a setup that already asks for the template, the anchor and the week rule must not grow a
question per heading. So the table is printed in the same reply as the proposal, after the template, frontmatter,
week and anchor questions (whose answers change which template the table is for) and before the one
`1 Confirm · 2 Correct · 3 Abort` question; the table block itself carries no option line and no "End the turn".

**The script owns the facts, the model the words (ADR-9).** `review-session.py match --kind --template --anchor`
returns `sections`: per template heading its `heading_key` (text, level, parent, occurrence), `state`, `reason`,
`flags`, `defaults` and the `saved` row. The skill builds the table from that list in its order and never decides
eligibility, reasons, keys, placements or caps itself: a model that judged "this heading holds a Dataview query"
would disagree with the analysis `setup-input` checks the rows against, and the user would meet a refusal for a row
the table offered. What the model adds is the wording ADR-9 leaves to it: a description of what to look for in the
period's notes (in `proposal.language`, the language the rows are stored and later searched in), keywords (the
schema's ≤ 12) and group hints. A saved row is shown as saved, so a second setup shows what the user confirmed
last time rather than a new wording (F2-AC10: descriptions are stored as the user confirmed them). A candidate
with `saved` set is a row even when it is `left-out`: an analysis row (placement `review`) is saved on an
`automatic` heading, and `match` shows it as a row too. The heading is shown with level and parent because the
same text can occur twice ("In my own words" at two levels, F2-AC5); `flags` (`mixed`, `container`, `under-own`)
are shown in brackets so the user sees why an offered heading may be a poor pick, without the skill naming what
the analysis looked at.

The group list is spelled out per kind (F2-AC7, the schema's `weekGroup` / `monthGroup` / `quarterGroup`), with
`habits` excluded by name: the habits are computed by a script and always stay in the "Tomo Review" section, and a
group the kind does not have would be refused by the schema at `setup-input`.

**Left-out headings get one line each (F2-AC3).** Every candidate that is not a row is printed as `—` with its
reason in words — Templater code, a link, a heading that repeats under per-period parents, an off-limits mark,
automatic content only — so the user is never left wondering why a heading is missing. `automatic` says it "can get
an analysis row" because that is the one left-out reason the user can act on (F2-AC12).

**Forward-looking sections (F2-AC6).** "I look forward to", "This will be challenging", "Goals and Wishes" ask for
what comes, not what was. The line tells the model to describe them as suggestions drawn from what the period
shows, so Pass 1 later proposes reminders with a source (F1-AC4) instead of inventing goals. The line names the
shapes of such a heading (what comes next, goals, wishes, start/stop/continue, challenges) rather than example
headings, so the model does not parrot the owner's template.

**Off-limits (ADR-8, F2-AC11).** The `Off-limits:` line shows the saved marks or `none`; nothing is marked by
default and no heading name is off-limits by itself. A mark is a correction like any other, heading only or with
its sub-sections, and a marked heading leaves the table because `setup-input` refuses a row on it
(`section-off-limits`).

**Corrections are plain text in the existing Correct step (F2-AC2, F2-AC4, F2-AC12).** The user names a row by its
`s<n>` or its heading and says the change ("s3 Beschreibung: …", "entferne s5", "füge ‚Planning' hinzu",
"Reflections tabu mit Unterabschnitten"). The step lists the operations — edit description / keywords / groups /
placement / cap, remove, add, mark and unmark off-limits — and what an added heading becomes: an `offered` one a row
with its `defaults`, an `automatic` one with a description an analysis row (`review`), any other left-out one is
refused with its reason (F2-AC4), and a heading not in the candidate list is not in the template (the script would
refuse it as `section-not-in-template`). A table correction reruns no `match`: nothing it changes is computed by
the script, and a rerun would cost a Kado round trip and a reprint. The script still has the last word — the rows
are checked by `setup-input` against the rows file `match` wrote — so a wrongly added row is refused, not saved.

A `match` rerun with the same template (a corrected folder, format or week rule) keeps the table changes, because
the rows of the template did not change; a changed template builds the table anew from the new output (F7-AC2: no
row from the earlier template remains).

**No mappable heading (F2-AC9).** `sections.mappable` false (no template, or none of its headings can take a row)
prints one line and no table; the confirmed file then carries neither `sections` nor `off_limits`, because the
writer stores rows under a named template and an absent key changes nothing.

**Confirm writes the rows into the confirmed file.** The skill already writes `tomo-tmp/review/confirmed-<kind>.json`
(the one setup file it may write); with a mappable template it adds `sections` (the table rows in order, with the
`heading_key` fields, description, placement, cap, and keywords / groups when set) and `off_limits` (the marks with
`with_subsections`), `[]` when there is none. `[]` is deliberate: the writer reads an empty list as "remove this
template's entry", so a user who removes every row saves no mapping, while the rows of another template stay
(F2-AC8). The skill writes no `id`: `review-session.py setup-input --kind --confirmed` gives every row the saved
row's id of its heading key or the next free one. The skill never writes `rows-<kind>.json`; `match` writes it and
`setup-input` deletes it on save (ADR-13, CON-1). A refusal's pointer `/sections/<i>` is the row at index `<i>`,
counted from 0, so the skill names the heading of that row instead of a JSON path the user cannot act on; the
`problems` themselves stay verbatim (the verbatim rule names the setup step's `errors`). The line says "starts
with" because `setup-input` also refuses at `/sections/<i>/placement` (the row's landing is off-limits), and it
names `/place` (the "Tomo Review" place lands off-limits) and `/template` (template not found) in words, the
other two pointers `review_setup_rows.py` returns (Phase 2 drift check).

**Template choice (F7, #267).** A typed or saved template Kado does not find comes back as `template_not_found`
with `template: null` and the candidates listed. The skill says the name was not found — the typed one, or the
saved one when `source` is `configured` — and the existing candidates question asks for another; the "no template
is saved" sentence is said only without `template_not_found`, because for a typed name it would be false.
`match` sets `template_not_found` independently of `template_candidates`, and the candidate list is empty when the
templates folder lists nothing; then no candidates question fires, and without its own line the flow would fall
through to `<template>` `none` without the user ever choosing a plain note. So the empty-list case asks in the same
reply for a typed name or `0` for none — the same single question turn the candidates path has, not an extra one
(owner decision 2026-11-15). Both template-choice reruns, the typed name and the picked candidate, add the flags of
the last `match` call except `--template` and `--anchor` (T2.3 code review): after a `template_not_found` the last
call carries the name that failed, and `match` keeps the last of two `--template` values (argparse's `store`
action), so the old name added after the new one would win and the same question would come back; an old
`--anchor` names a heading of the template it was given for, which the carve-out below keeps off a template change,
and the rerun sentence names both flags itself because it is the line a literal model follows at that point. A
table correction prints the whole table again with the change, so the user confirms what is actually saved, not a
remembered earlier version plus a described edit.

`sections.dropped` names the headings of the earlier mapping the template lacks: once after a template change
(the first `match` with the new template; the rows file is then rewritten, so a later rerun shows none), and on
every same-template run for saved rows whose heading the template lost (owner decision 2026-11-15). One line per
entry, so a typo never leaves the user believing a mapping still applies (F7-AC3). "Not kept" is said only with
`sections.mappable` true: `match` lists the saved rows the template lacks also when no heading can be mapped, but
then Confirm writes no `sections` key and the writer changes no row, so the line says the save leaves the saved
rows as they are (Phase 2 drift check).

**The `--anchor` carve-out (ADR-13).** The carry rule says never drop a flag from a rerun, so each question is
asked once. The anchor is the exception: a typed anchor names a heading of the template it was given for, and the
script now uses even the configured anchor only for the configured template. Carrying `--anchor` into a `match`
with another template would place the review under a heading the new template may not have. So when `<template>`
changes, the next `match` carries no `--anchor` and `<anchor>` is unset; the new output proposes the place from
the new template, and `needs_anchor` asks again when it cannot. The carry rule names the exception in place
("except `--anchor` by the next line"), because a literal model reading "never drop" otherwise keeps it.
`--template-frontmatter-ok` needs no carve-out: it names the template it was given for and the script ignores it
for any other.

**The quarter in the same flow (F6-AC1).** Step 2 runs for `quarter` exactly as for `week` and `month` (the week
question never fires for it; `match` proposes the folder, the `YYYY-[Q]Q` format or the one found, template, place,
language and rows). Step 1 sends a quarter request with `setup.quarter` `missing` into step 2 and reruns `start`
after the save, like the other kinds (F2-AC10: the request continues in the same session), and then on to step 3
like a week or a month (F6-AC6: a quarter's review applies "as for a month"). Until spec 046 T4.5 a quarter request
stopped there with one line that Tomo could not review a quarter yet, because `review-read.py` did not read one and
`review-doc.py write` could not load its split read; both now do, so the interim line and its pin are gone.
`/review setup` walks the quarter after the week and the month, like them, with no `setup.quarter` gate. The gate
(only when `setup.quarter` was `present`) kept a vault without quarterly notes out of a third dialogue while a quarter
could not be reviewed anyway; with the quarter a reviewable kind, "setup" means the setup of every kind, the same
way the week and the month are walked whether or not they were set up before — Abort at the quarter's confirm
question leaves it unsaved and the week and month saved. The command's and the skill's argument hints and
descriptions name the quarter (`quarter`, `2026-Q1`).

**Size.** The table, its corrections and the quarter routing grew the skill from 24,278 to 28,176 characters
(+3,898, `wc -c`; 220 → 233 lines) at 0.2.0; the T2.3 review fixes (the empty-candidates question, the table
printed again) brought it to 28,600 at 0.2.1 and the `--template` / `--anchor` exception of the two
template-choice reruns to 28,672 at 0.2.2, still 233 lines; the Phase 2 drift fixes (the `dropped` line by
`mappable`, the `/place` and `/template` pointers) to 28,885 at 0.2.3, still 233 lines. The SDD estimated about 1,000 characters for the sections; the estimate did not
count the per-reason words, the per-kind group list, the Correct operations and the confirmed-file shape, each
of which a literal model needs spelled out. The trim is #259. No `STRICT` block was added: no
run has shown a deviation in this step yet.

## Why the Week Question Is Asked in Plain Words (ADR-7)

WHY: Which day starts a week and which week is week 1 decide which note a review targets; a wrong rule creates a
duplicate weekly note (PRD risk 1). `match` infers the rule from the dates the user's own weekly notes carry
(`journal-start-date`, day headings) and reports `evidence.week_rule` as `inferred`, `ambiguous` or `default`. Only
when it is `ambiguous` — the notes disagree or carry no dates — does the skill ask, in plain words, not in ISO
vocabulary: "Which day does your week start on? Is week 1 the week with 1 January, or the first week with at least
four days in the new year?" (F1-AC6). The answer is mapped to `(first_day, min_days)` — "Monday, four days" is ISO
`(Monday, 4)`, "Sunday, 1 January" is `(Sunday, 1)` — and passed back as `--first-day` and `--min-days` to `match`,
whose new matches show which existing notes the rule no longer fits (F1-AC5) before the user confirms. That rerun
reports `week_rule` as `given` (final fix round of the live-walk fix): the notes still disagree after the answer, and
the first version reported their verdict on every call, so the rerun said `ambiguous` again and a literal model asked
the question a second time — and after every Correct rerun. The skill therefore acts on `ambiguous` alone, says so
beside the rerun, and carries `--first-day`/`--min-days` on every later `match` of the step exactly as it carries
`--template` and `--anchor` (the carry rule names all three), so a Correct that drops the answer cannot bring
`ambiguous` back (WHY of the value: `docs/tomo/scripts/review-session.md`, "WHY `week_rule` Is `given`"). The Obsidian
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
continues (F1-AC7); `missing` proposes the plain note without the access hint — after the template question above,
when the mapping named none. A `kado-none` listing of the templates folder itself gives an empty candidate list and
a `hints` line that names the folder, never "no templates". In Pass 1, `review-read.py`'s
`kado_empty` sources are reported with the access hint, and its `advice` `check-key-access` (`lib/review_period.
ADVICE_CHECK_ACCESS`, set whenever `kado_empty` is non-empty) has its own line: Kado answered with nothing for those
sources and the key may not reach those folders; the user checks its access (F3-AC9). The first draft had a line for
`raise-kado-limit` only, so the second advice token reached the console as a bare word (Phase 5 drift round);
`tests/test_review_skill.py` now reads the `ADVICE_*` constants of the two libs that produce the advice
(`lib/review_pacer`, `lib/review_period`) and demands a line per token. The
skill never says a folder is empty or a note does not exist.

`nothing_to_review` says the hint on the advice only (Phase 6 live walk, owner decision). The first version of the
step said "an empty result may also mean the Kado key cannot read the folder" on every empty period, and
`review-read.py` set `check-key-access` whenever nothing was to review; in the live walk a week after the test
vault's last daily (2026-09-12) got the access hint although Kado had listed the daily folder with notes for other
dates. The script now leaves the advice to the listings (`kado_empty`; see
[review-read](../../scripts/review-read.md), "WHY 'Nothing to Review' Writes Nothing and Says the Access Hint on
the Advice Only"), and the step says that no daily of the period holds content, names the days of `report.days`
(each with its dailies, so the user sees which dates were found and which were not), and adds the access line only
when `advice` holds `check-key-access`. A quiet period is reported as quiet; a folder Kado answered nothing for is
still never called empty.

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

## Why Step 4 Continues a Stored Read or Reads Anew (Spec 047 F6-AC4, F6-AC5)

WHY: since spec 047 `review-read.py` writes the stage `tomo-tmp/review/<stem>/` (day files, growth files, child and
previous notes, context, units, `manifest.json` last) and prints `stage`, `read_id` and `read_at` instead of a file to
read. A Pass 1 interrupted by the end of the session or a failed step leaves the stage behind; condensing a quarter
costs 15–17 agent runs, so reading Kado again and condensing from scratch would throw that away.

- **The continued read.** Without `--fresh`, when `manifest.json` names the current layout, period, kind and section
  mapping, the script reads nothing from Kado and prints `continued: true` with the stored `read_id` and `read_at`.
  The skill says in one line that it continues and when the read was made (F6-AC4): a continued read does not see
  vault edits made since, and the user must know how old the material is to decide whether that matters. Pass 1 then
  goes on with step 5 on the stored read; `plan` lists only what is not yet condensed. No question is asked: the
  user's way out is the existing Start over, which reads anew.
- **`--fresh` on every Start-over route.** `review-read.py --period --kind --stem --fresh` discards the stored
  material first and reads anew (F6-AC5: material from an earlier read is never used after a start over). The skill
  passes it on each route that means "read this period again": Start over of an open review, the start over after
  `review-exists`, and the answer to `read-stale`.
- **`read-stale`.** `review-digest.py plan`, `review-digest.py check` and `review-doc.py write` refuse `read-stale` when
  a stage file belongs to another read than `manifest.json` names (a half-replaced stage). Nothing on the stage can be
  trusted then, so the skill runs step 4 with `--fresh`, once; a second `read-stale` is shown and stops, because then
  something else writes the stage under the run.
- **A changed mapping reads anew.** The script compares the section mapping itself and reads anew
  (`discarded: sections-changed`); the skill needs no branch for it.
- **Kado unreachable stores nothing.** A `stopped` read writes nothing (with `--fresh` the old read was discarded
  first), so there is nothing to continue; the stopped rule applies as before.
- **The previous-note lines.** `report.previous` names each previous note with its state (found, read in part,
  missing, not set up, not read with its cause). Step 4 prints them with the report and the run report after `write`
  repeats them (F3-AC6), because the user approves the document knowing which follow-ups could not be made. A
  previous kind that is not set up is a state line, never a setup question (F3-AC8): the review the user asked for is
  not interrupted for a kind they did not ask about.

## Why the Model Writes Only `proposals.json` (ADR-12)

Since spec 047 the model that writes `proposals.json` is the `review-proposer` agent, and the rationale of what it
proposes (sources, habits, the user's own sections, the continuation line) moved with the rules to
[review-proposer](../agents/review-proposer.md) "WHY It Writes Only `proposals.json`". What stays with the skill: the
main session writes no proposals and reads no stage file; it dispatches the proposer with `plan`'s / `check`'s
`proposer.inputs` and runs `review-doc.py write --stem --proposals` on the file the agent wrote (see "Why Step 5 Is
Plan, One Message per Round, Check, Retry Once, Propose").

## Why Pass 1 Proposes by Section in the Same Model Pass (Spec 046 ADR-1, F1)

WHY: spec 046 ADR-1 kept one model pass that proposes by section beside the groups. Since spec 047 that pass is
the `review-proposer` agent, and every section rule with its rationale — the key copied, description and keywords,
a row's `groups` as starting point, reminders not finished text, the cap by merging, one place per finding, analysis
rows, the marks, the error-to-fix mapping of the rewrite — lives in [review-proposer](../agents/review-proposer.md)
"WHY the Section Rules" and "WHY the Rewrite Gets the Errors Verbatim".

**The rewrite-once loop stays the skill's.** `write` refuses a bad file as `proposals-invalid` with
`"<pointer>: <error>"` strings; the skill re-dispatches the proposer once with the errors verbatim, and a second
`proposals-invalid` is shown and no document is written (F6-AC3): looping on a schema the model cannot satisfy burns
the user's time. `sections-changed` is not the model's error: the setup's rows changed after the read, so the stage's
definitions are stale. The answer is to read the period again (step 4, which then reads anew: `discarded:
sections-changed`, F6-AC5) once; a second `sections-changed` is shown and stops, because then the config changes under
the run.

**Sections in the report.** `write`'s `counts` carry the section keys next to the groups and `rejected` names
`section` for a section item. Keys (`s1`) mean nothing to the user, so the report names a section by the `heading`
of the configured row with that `id`, read from `config/vault-config.yaml` (the file step 5 already reads for the
language) — never from a stage file, which the main session does not read and which `write` has deleted.

**The Pass 2 stop for a missing section checkbox (F3-AC6, Rule 7).** `review-doc.py parse` warns
`section-checkbox-missing` and prints `section_problems` (`key`, `restore`; no heading text, CON-3), and the plan's
gate refuses the same warning on `preview` and `deliver` (docs/tomo/scripts/lib/review_delivery.md). Step 6 names
each section by the configured heading of its key and gives the restore line verbatim — the user restores it under
the heading and runs `/review` again — and stops after the warnings: a delivery the parser cannot read without
guessing lands nothing. Step 7 reaches the token only when `parse` did not run first (a Resume goes straight to
`deliver`); the preview output carries no `section_problems`, so the line runs `parse` for them and says the step 6
line rather than adding the keys to the Pass 2 script's output.

**Size.** Proposing by section, the rewrite fixes, `sections-changed` and the two stop lines grew the skill from
28,885 to 31,122 characters (+2,237, `wc -c`; 233 → 243 lines) at 0.2.4 — about twice ADR-1's estimate of 1,000
for the whole Pass 1 side, because each rule the scripts cannot check needs its own imperative and the config path
of `<section heading>` is spelled out once. The trim is #259. No `STRICT` block: no run has shown a deviation in
these steps yet.

## Why a Quarter Is Read File by File in Step 5 (Spec 046 ADR-7, F6-AC6)

Since spec 047 T2.4 `review-read.py` writes the stage of `lib/review_stage` and prints `stage` instead of
`read_path` / `read_parts`; this section records the spec 046 step 5 that T6.3 rewrites for the stage.

WHY: the Read tool takes at most 256 KB per call, and a quarter measured 710 KB as one file (T3.4, 2026-Q1). So
`review-read.py` splits a quarter into `read-index.json` and one `read-<YYYY-MM>.json` per month and prints
`read_path` (the index) and `read_parts` (the month files, in order). Step 5 reads `read_path` — the same key for a
week and a month, where it is `read.json` — so the step names one file to start from instead of a path the skill
spells per kind; a quarter then reads each `read_parts` entry, one Read call each, in the listed order.

- **One after the other, not in parallel.** The index carries what no month owns (period, report, sections, open
  tasks, growth, `not_read`, the two mark lists) and is read first so the months are read knowing what to look for;
  the order of the parts is the quarter's order. Parallel Read calls give no order to rely on.
- **The parts stay in the conversation; nothing is merged on disk.** The model keeps what it read in the
  conversation, the way it keeps a month's one file, and writes `proposals.json` once, after the last part. It writes
  no intermediate file — the skill's opening line allows `proposals.json` and the confirmed setup only — so there is
  no joined copy of the journal on disk and nothing for the clean-up to miss. No visible running notes either: the
  privacy rule keeps read content out of the reply.
- **"`read.json` means all these files together".** Every later line of step 5 says `read.json` (the sources, the
  growth lists, the section keys, the rewrite fixes). One sentence maps the name onto the quarter's files instead of
  rewording each line, which keeps the growth small and the week/month lines and pins unchanged.
- **The quarter keys are named like the month's.** The groups line names, for the month, `weekly`,
  `only_in_weekly_links` and `dailies_not_in_weekly`; the quarter line names `monthly` (its entries' `month_text`),
  `only_in_monthly_links`, `dailies_not_in_monthly` and `report.monthly_status` — the groups only when a monthly note
  was found, which is the script's `no-monthly-notes` rule said up front. Step 4 prints `monthly_status` and
  `monthly_notes` like the weekly pair, so the user sees which monthly notes were not found (F6-AC5).
- **The script joins, the model does not.** `review-doc.py write` loads the whole read through `lib/review_stage.load`
  (spec 046: `lib/review_read_parts.load`, deleted in spec 047 T2.4), so a source from any month resolves, and its
  clean-up removes every stage content file
  (docs/tomo/scripts/review-doc.md). A missing or broken part is `read-invalid`, which step 5 already shows and stops
  on.

**Size.** The quarter branch, the quarter keys, the setup and step 1 changes and the wider descriptions took
the skill from 31,122 to 31,600 characters (+478, `wc -c`; 243 lines before and after) at 0.2.5. No `STRICT`
block: no quarter run has been observed yet.

## Why Step 5 Is Plan, One Message per Round, Check, Retry Once, Propose (Spec 047 ADR-4, ADR-8)

WHY: the period no longer fits one context (spec 046 close-out: a quarter of 717 KB, ≈ 390k tokens, against a Read
limit of 25k tokens per call). Spec 047 cuts it into units, condenses each unit with a `review-digester`, takes the
previous reviews into `carryover.json` with `review-carryover`, and builds the proposals over the whole period with
`review-proposer`; every proposal rule now lives in [review-proposer](../agents/review-proposer.md). The skill's
step 5 only orchestrates, and every decision of the orchestration is a script's:

- **`review-digest.py plan --stem`** lists the jobs still to run, ready-made: agent, files, `out`, `cap_bytes`, in
  rounds of at most `MAX_PARALLEL` (16) jobs ([review-digest](../../scripts/review-digest.md)). The skill decides
  nothing about content and starts no job `plan` did not list.
- **One message per round.** All jobs of a round go out as `Agent()` calls in ONE message, so the 14–16 digesters of a
  quarter and the carryover run at once and the step takes one agent's time, not sixteen. Each call names its
  `subagent_type` and `run_in_background: false`, and its prompt is the template the skill names: stem, unit,
  `read_id`, the file list, `out`, `cap_bytes`, the review language — paths, ids, dates and the language only, never
  note text (the main session has none to give). The reply is one line per agent.
- **`review-digest.py check --stem`** judges every file the agents wrote and spends one attempt per open job: the first
  failure comes back in `retry` with its errors, and its job — the one `plan` listed for that `agent` and `unit` —
  is sent again by its template unchanged, all retries in one message; the second is `failed`. Then `check` again.
  So a run is `plan` once, then `check` at most twice. The errors are not put into the retry prompt: `errors` is
  no field of the digester's or the carryover's `## Input` line (only the proposer's rewrite takes them), and an
  agent writes its file anew from the inputs on every run, so a fresh attempt is the retry; the errors are
  `check`'s to judge.
- **All rounds, then one `check`.** `check` spends an attempt on every open job, so it runs after the last round,
  never between rounds: a job of round 2 not yet sent would count as a failed first attempt. An empty `rounds` (a
  continued read whose units all passed) runs no agent and goes to the proposer with `plan`'s own `proposer`.
- **`stage-missing` / `stage-invalid` read again, once.** `plan` refuses them when the stage is gone or cannot be
  loaded (a session that ended mid-read, a hand-edited file). Step 4 without `--fresh` reads anew in both cases
  (no manifest, or a stage that does not load, is never continued); a second refusal means something else is
  wrong and is shown.
- **A proposer that wrote nothing stops the run.** Its reply `proposals.json not written: <reason word>` means no
  file exists for `write` to check; running `write` anyway would only refuse. The run stops with the reply shown
  and the stage kept: the next `/review` continues on the read and `plan` dispatches the proposer again.
- **`carried_moved` is a report line.** `write` moves the last carried items of a full section into the group of
  their mark (docs/tomo/scripts/review-doc.md); the run report names each move by the section's configured heading,
  so the user knows why a follow-up is not in the section it fits.
- **`plan` once per run.** `plan` resets every failed unit (and a whole-file failed carryover) to pending on each call,
  because it cannot tell a continued read in a new session from a repeat call in the same one (T4.3 review). Retries
  stay bounded only if the skill runs `plan` once per run; a second `plan` after a failed retry would offer the unit
  again and again. The step says so as an imperative ("once after each run of step 4": a step 4 rerun after
  `read-stale`, `stage-missing`, `stage-invalid` or `sections-changed` makes a new read, whose `plan` is its first);
  a STRICT follows only if a live run shows a second `plan`. So a unit
  that fails twice stays failed until the next session, whose `plan` offers it once more (the cause, often
  throttling or a model slip, may be gone by then).
- **Not condensed is named, never read instead.** A unit that failed its retry is in `not_condensed` with its days;
  the document's top and the run report name them like days Kado did not return (F6-AC1) and the review is built from
  the rest. The main session never reads the days of such a unit itself: that was the spec 046 fallback. When every
  taking-part unit failed, `check` answers `stopped` `nothing-condensed` naming every week, and the skill stops like a
  period with no content (F6-AC8); no document, the stage stays for a later run.
- **A failed carry is a line, not a stop.** `carry_failed` true (or one previous note failed) means the review goes on
  without the follow-up, the document's top says so (F6-AC2) and the run report names it; `proposer.carried` is then
  false and the proposer marks nothing as carried.
- **Then the proposer**, once, with `proposer.inputs` of the last `check` (only then are the passed digests known),
  and `review-doc.py write --stem --proposals`. `proposals-invalid` → one re-dispatch of the proposer with the errors
  verbatim, a second is shown and no document is written (F6-AC3; see "Why Pass 1 Proposes by Section").
- **`condense-incomplete`.** `write` refuses when `condensed.json` is missing or a unit is still pending — the skill
  skipped or cut short the condensing. The answer is step 5 again from `plan`, once; it is the one second `plan` of a
  run, bounded by "once", and the units that failed in this run are offered once more.

## Why Step 5's STRICT Blocks (Spec 047 ADR-8)

WHY: a `STRICT` block is only for a deviation actually observed (see "Why STRICT Is Rare"). Each block of step 5 names
one, and its `Why:` line is that failure mode in one line:

- **One message per round.** Failure mode: agents sent one per message run one after another, so a quarter's 16
  digesters take 16 agent times. Observed in the `/inbox` fan-out: `suggestion-conductor` 0.2.0 said "Dispatch all
  items in ONE message so they run concurrently", and Sonnet dispatched 18 analysts sequentially, one `Agent` call per
  turn; 0.3.0 added a STRICT that names the mechanism (all `Agent()` calls in one message run concurrently, one per
  message runs them one after another). The batch STRICT of `suggest-handling` (step "BATCH dispatch") is the pattern
  the review dispatch copies.
- **`subagent_type` on every call.** Failure mode: an `Agent()` call that names the agent only in its prompt or
  description starts a `general-purpose` agent, which has every tool (Kado included) and none of the review agent's
  rules. Observed in `/inbox`: see [suggest-handling](suggest-handling.md) "Why the dispatch template says
  `subagent_type`, not `name`".
- **`run_in_background: false`.** Failure mode: the CLI started a dispatched agent in the background without being
  asked (spec 043: `claude` 2.1.316 backgrounded the conductor, 3 of 307 traces), so the reply arrived as a later task
  notification and the run went on, or ended, before the file existed. `/inbox` passes the flag since then; step 5
  does the same.
- **Never read a stage file in the main session, never search day files with `grep` or Bash, never start an agent
  `plan` did not list; a unit without a passed digest is named as not condensed.** Failure mode: the spec 046 walk
  (2026-11-17/18): both round-3 quarter runs fell back to `grep` over parts of the read files and reported a partial read,
  and the 08:30 run handed the read to four `general-purpose` subagents it started itself ($2.83 of that run's
  $4.26). Either path reviews a sample of the period while claiming the whole; the not-condensed line is the honest
  alternative.

The write rule and the step 8 `STRICT` name the agents' files (digests, `carryover.json`, `proposals.json`) as the only
stage files written outside the scripts, each by its own agent, and the skill writes only `confirmed-<kind>.json`.
Without the carve-out the step 8 line ("never write a file under `tomo-tmp/` other than …") would contradict the
dispatch, and a literal model resolves a contradiction either way.

## Why a Pass 1 Abort Runs `replace --abort` and Nothing Else (Spec 047 ADR-10, F6-AC6)

WHY: the Rules say "on Abort at any question, run no further script and write nothing". Before spec 047 that left
nothing behind in Pass 1 worth deleting. Since spec 047 step 4 writes a stage that holds the period's journal content,
and a stage left behind is a read the next `/review` of the period continues on (F6-AC4) — the opposite of what the
user asked for. F6-AC6: an Abort during Pass 1 runs no further step, writes no document, deletes the material at once
(F7-AC1) and cannot be continued. So an Abort answered after step 4 wrote a stage and before step 5 wrote the document
runs `review-doc.py replace --stem --abort` and nothing else: the one exception to the abort rule. The call
discards the stage content through `review_stage.discard` and keeps only the content-free `meta.json` and
`payloads.json`; it writes nothing to the vault. An Abort before step 4 has no stage to discard, and an Abort after
`write` is Pass 2's Abort (unchanged).

## Why the Review Language Is Read From the Config File

WHY: The proposals must be in the review language of the setup (F4-AC5) and `proposals.json` names it, but no script
of the ordinary path prints it: `start` reports the setup only as `present` / `missing`, `review-read.py` prints the
report and the stage carries the period's content, not the setup. The skill therefore reads the one key
`review.language` from `config/vault-config.yaml` — the instance's own configuration, not the vault, and a value the
user confirmed in the setup dialogue — and passes it as `<language>` in every agent prompt of step 5 (the
carryover and the proposer write their text in it, F4-AC11). The alternative calls (`start --args='setup'`
for `current.<kind>.language`, or `match` for a proposal) each cost Kado calls for a value that is already on disk.
Known gap, noted at T5.2: a `language` key on `review-read.py`'s output would remove the only config read of the
skill; until then the skill reads that key and nothing else from the file and never writes it.

## Why Pass 1 Ends With `write`, Deletes the Working Files and Ends the Turn (ADR-2, ADR-9)

WHY: `review-doc.py write --stem --proposals` is the only vault write of Pass 1: `<period> Review.md` in the inbox,
with the target note and whether it exists, the unticked Approved box and the grouped items (F4-AC1). The skill
reports `doc_path`, `target`, `target_exists`, the `counts` per group and `rejected` items, then ends the turn: the
user edits the document in Obsidian, and the next `/review` finds it as an open review (ADR-2: the open state lives in
the vault, not in `tomo-tmp`, because the user edits between passes). `write` discards the stage content
(`review_stage.discard`: days, growth, child and previous notes, digests, carryover, proposals, context, manifest)
once the document is written (ADR-9, spec 047 ADR-10): the journal content the agents read has no job after that, and
the stage keeps only the content-free `meta.json` and `payloads.json`. The refusals are shown verbatim: `doc-name-taken` names the file
that is not Tomo's and nothing is overwritten; `review-exists` is the start-over case (next section);
`kado-write-failed` means nothing was claimed as written. Abort at any point before `write` deletes nothing in the
vault, because nothing was written there.

## Why Start Over Asks Twice (F6-AC1)

WHY: Replacing the review document destroys the user's edits in it. So when the user chooses Start over for an open
review, or `write` refuses with `review-exists` (Tomo's document for the period already exists and the stage files are
kept), the skill names the document that will be replaced (`doc_path`) and asks again, `1 Replace · 2 Keep it`.
`review-doc.py replace --confirm` writes the new document over Tomo's own from the kept stage;
`review-doc.py replace --abort` discards the stage content and keeps the document. The script itself
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
skill names `place.anchor` and `place.placement`, lists the `headings` the note has and asks for one or Abort, then
reruns `review-instructions.py preview --place-anchor` with the chosen heading, F5-AC7), `user-heading-collision` with `mode` `insert` or `new-note` (a
same-named heading of the user's without the marker is never replaced, and the review never lands inside an own
section: another heading or Abort, offered once — see "Why the Heading Pick Is Offered Once"), `set-exists` (a set
for the stem waits for Hashi and is not applied yet; nothing is delivered, F6-AC2). The skill's `set-exists` line says
"not applied yet" on purpose (0.1.6, T6.1 fix round), because the line must not claim that *any* set at the path
blocks the delivery. `lib/review_delivery.second_set` answers `set-exists` in two cases: a set this record did not
write sits at the path and any action in it waits (`set_applied` false), or this record's own delivery is already
complete (`doc_mark` done) or withdrawn — the `set_applied` flag is not consulted then. A fully applied set is written
over only by a *fresh* record: Start over (`replace --confirm`) resets `meta.json`, so the rerun's `deliver` meets the
set with `set_applied` true and no `doc_mark`. A completed delivery whose set Hashi applied later never reaches the
preview: `start` lists it as `applied` (step 1, line "the review was applied"), no branch of that entry goes to step
6 or 7, and once `applied_reported` is set it is not listed at all. No record with `doc_mark` done reaches
`preview`/`deliver` through the listing any more: until the Phase 6 pre-live-walk fix, a completed delivery whose set
the user deleted from the inbox by hand (Hashi marks actions `applied` and never deletes a set) was listed
`failed-delivery` by the "approved document whose set is gone" clause of `lib/review_state`, Resume → `deliver`
answered `set-exists`, and this line then said a set waits although none was at the path. Owner decision 2026-11-12:
such a stem is finished and not listed (state None, like `applied_reported` and withdrawn; SDD 1.11, step 3b;
docs/tomo/scripts/lib/review_state.md, "WHY a Complete Delivery Whose Set Is Gone Is Finished, Not Failed"). An
approved document without a set whose record lacks `doc_mark` stays `failed-delivery`, and Resume there delivers —
`second_set` is False with no set at the path — so the `set-exists` line is never printed for an absent set. The skill
text did not change: its `failed-delivery` entry and the `set-exists` line were already right for the cases that remain.

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

The heading-pick bullet names `place.anchor` and `place.placement`, not the anchor's level (Phase 5 drift round). The
SDD's `place-too-deep` row says "names the anchor and its level", but on a refused insert or new-note plan the preview
output does not carry the level: `lib/review_actions.build_review_plan` seeds `place` with `anchor` and `placement`
only, `_existing_note` and `_templated_note` assign the `level` key after `_insertion` succeeded, and `_refuse` copies
the `headings` as texts without their levels. Only the replace branch sets `place.level` before it refuses. So the
bullet names the two fields the output has — the heading the plan looked for and whether the review goes before or
inside it — and says the review heading would pass level 5 under it; a bullet that named `place.level` would send a
literal model looking for a key that is not there. Carrying the anchor's level in the refusal is a script change the
owner has not asked for; the test pins the seed shape so the bullet and the output cannot drift apart silently.

## Why a Replace Preview Says the Section Is Replaced (F6-AC3)

WHY: `mode` `replace` means the marker was found in the target note, so the plan is a `replace_section` and the
section the note holds now goes away when Hashi applies it. The first draft printed `mode` with the plan and said
"replaced there" only for the `heading-renamed` notice, so a replace under the configured heading — the common
rerun — told the user nothing about what happens to the section already in the note (Phase 5 drift round, F6-AC3).
The `ok` output has one line for `mode` `replace` now, before the notices: the note already holds Tomo's review
section; it is replaced, not added to. The line is a flag of the `ok` output, not a notice, because
`lib/review_delivery.NOTICES` is what the plan reports as notices and `mode` is not a problem of the plan.

## Why Steps 7 and 8 Carry One Line per Section Stop and Notice (Spec 046 T5.5)

WHY: spec 046 T5.5 added section stops (`section-missing`, `section-ambiguous`, `section-broken`, `section-moved`,
`block-in-review-section`, `landing-off-limits`), the refusals `choice-invalid` and `choices-needed`, and the notices
`block-replaced`, `block-moved-confirmed`, `review-section-kept`, `section-dropped` and `section-empty` to
`lib/review_delivery.REFUSING` / `NOTICES`. The skill's coverage test demands a branch for every refusing name and a
line for every notice, and a name the skill does not know reaches the user as a bare token — so each name got one
plain-language line in the existing lists the same task the script learned it, not one phase later. The lines name a
section by the heading of its `key` from step 5 (the script prints keys only, as for `section-checkbox-missing`).
In T5.5 the stop line ended the step; T5.6 replaced that end with the per-section dialogue (next section). The `block-replaced` line already says that edits inside Tomo's block are replaced and text
outside it is kept (F5-AC4): a re-run replaces the block whether or not T5.6 has landed. `sections` is printed in the
`ok` line, not as a bullet, because it is output, not a problem the step branches on (F4-AC6: heading, placement
from step 5, and the lines that land). `choices-needed` sends the user back through a fresh `preview` of step 7: the
choices are not recorded (keys and modes only), so they are asked again, and a different answer is caught as
`replan-differs`.

## Why Steps 7 and 8 Ask per Section in the Deliver Step (Spec 046 T5.6)

WHY: PRD F4-AC4 and F5-AC3 want every section stop named before anything is written, with a choice per section
(leave it out, put its items into "Tomo Review", or Abort), and the SDD's Interaction Design says "per-section choices
in the existing Deliver step" — no extra turn. So a preview whose `problems` hold only section stops is shown like a
clean preview (plan, per-section lines, the replace line and the notice lines, among them `block-replaced`'s replace
sentence: edits inside Tomo's block are replaced, text outside it is kept), and the stop lines come last, right before
the question, so the user reads what lands before deciding what does not. The stop dialogue replaces the
`1 Deliver · 2 Abort` question; it is never asked as well.

- **One plain-text question, not AskUserQuestion.** A choice per section across several sections does not fit one
  AskUserQuestion (at most four options), and a list printed before an AskUserQuestion call is not seen live (memory:
  print-before-ask fails live). The skill asks once in plain text: per listed section one of its `choices`, or
  0 Abort; the user answers in words, and Rule "when it is unclear, ask again" covers a garbled answer.
- **The offered choices come from the script, never from the skill.** Each `sections[]` entry with a `stop` carries
  `choices` (`lib/review_section_plan._stop` / `plan_section`, per case, not per stop name: a missing heading offers
  skip and review, but skip and confirm-moved when Tomo's intact block pair is still in the note and skip only beside
  a broken earlier block (a start or end marker alone, a duplicated pair); a heading there more than once offers skip
  and review, skip only beside any earlier block of the section (one block per section, T5.7 owner decision); a moved block's ambiguous landing heading skip only; broken and in-review offer skip; a moved
  block skip and confirm-moved, skip only when no heading stands above it; `landing-off-limits` none). A stop-name →
  choices table in the skill would be wrong for some of these. A stop without choices can only be aborted: the skill names it and stops without a
  question, because there is nothing to choose.
- **Naming.** A section is named by the configured heading of its `key` (step 5, the `review.<kind>.sections` row),
  never by a stage file: the main session reads no stage file (Rules), and a continued review (step 6) has no stage
  to read. The `placement` is named because the same heading can take the review before, under or
  at the end of it, and the user decides knowing where. The stop lines are said in `<language>`, the document's
  language (`review.language` of `config/vault-config.yaml`), because they name the review document's sections as the
  user just edited them. Step 7 defines `<language>` where it uses it and Reads the config: step 7 is normally reached
  by a later `/review` run (step 6) in which step 5 never ran, so step 5's definition is not in that run. The question
  after the stop lines (the choices, `0 Abort`) falls under the Rule "Ask in the language the user writes in", like
  every other question; when the two languages differ, the stop lines follow the document and the question the user.
- **Answers become flags; the same flags reach `deliver`.** `skip` / `review` are `--section-choice <key>=…`,
  `confirm-moved` is `--confirm-moved <key>` (SDD ADR-12). The skill reruns `preview` with them — the plan with the
  choices taken is what the user is told about — and branches on that rerun by the same list, as the heading pick does:
  an `ok` with empty `problems` goes through the `ok` bullet, prints the plan with the choices taken and asks
  `1 Deliver · 2 Abort`. The choice answer is not the decision to deliver: a `review` choice moves items into "Tomo
  Review" and `confirm-moved` replaces a block where it sits now, and the user sees that final content before anything
  is written (PRD F4-AC6: the preview is listed before asking Deliver or Abort; the project rule: never execute without
  user approval). An earlier version went to step 8 without asking again, so the final plan was never approved; the
  spec compliance review of T5.6 caught it. `deliver` gets exactly the flags of the last preview, since
  a differing set would plan a different set than the one shown. Beside any other problem only that problem's line
  applies: every other problem stops or asks first, and choices answer a plan that is otherwise deliverable.
- **`choice-invalid`** means a choice no longer answers a stop of its section: the note changed between the preview and
  the call. The skill says so and previews again without the choices; a preview without choices cannot be
  `choice-invalid`, so this cannot loop.
- **`choices-needed`** (a resume begun with choices, rerun without) is now reachable: the choices are never recorded
  (keys and modes only), so step 8 reruns the step 7 preview, the stops are asked again, and the rerun with the
  answers resumes; a different answer is caught as `replan-differs`.
- **`section-dropped` / `section-empty`.** F3-AC4 wants the user's own items lost with an unticked section counted in
  that line; F3-AC5 wants an empty ticked section named as empty. The lines say both in those words.
- **`name-taken` at a set step is not a foreign note.** `staged_delivery` reports `exists` when a step in flight finds
  other bytes at its path. With `step` `note` that is a note at the new note's path that is not Tomo's (spec 045). With
  `step` `set_json` or `set_md` it is an earlier instruction set of this review waiting at the path — the SDD case
  "Resume over an uploaded v3 set" — and "a note that is not Tomo's" was wrong. The skill offers a fresh delivery with
  the two cures `tests/test_046_t5_6_fresh_delivery.py` proves: the user applies that set in Hashi (an applied set is
  written over, `replaces_set`), or deletes it in Obsidian, then Resume delivers. At `set_json` the readable
  instructions beside it are deleted too, or Resume stops at `set_md`; at `set_md` the set JSON is this delivery's own
  and must stay. Drop is not offered: it would write a withdrawn set over the earlier set and leave the review
  unlisted with nothing delivered.

### Why the "Tomo Review" Place Landing Off Limits Has Its Own Line (Spec 046 T5.7)

WHY: `landing-off-limits` is two things. Per section it is a stop on a `sections[]` entry (`stop`, empty `choices`).
It is also a plan-level problem for the "Tomo Review" section itself: `lib/review_actions._insertion` (a new "Tomo
Review" would land in an off-limits section) and `_existing_note` (`review_off_limits`, an earlier one sits in one).
Then no `sections[]` entry carries a `stop`, and the stop bullet, which speaks per entry with a `stop`, would say
nothing and ask a question with nothing to choose. So a line of its own comes before the stop bullet: the "Tomo
Review" section, placed at `place.anchor` (the only place field both cases carry; `placement` is `replace` on a
re-run), would land in an off-limits section; the place is changed with `/review setup`; nothing is delivered (Rule 4:
no choice moves Tomo's text into an off-limits section). The drift check of T5.7 found the gap
(`tests/test_046_t5_7_place_off_limits.py` pins the script's output and the line). When a section stop stands beside
the plan-level problem, the stop bullet applies and names the sections only; the place problem is then reported by the
rerun after the section choices.

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
`problems` and nothing was written: `name-taken` names `exists_path` (a payload's path holding other bytes than
Tomo's identical text; never overwritten — a foreign note with `step` `note`, an earlier set with a set step, see
"Why Steps 7 and 8 Ask per Section in the Deliver Step"), the plan problems are the preview's. `status: stopped` carries `failed_step` and is
resumable: `doc-changed` means the document was edited or is open with unsaved edits since the preview; the skill says
to save it and run `/review` again, and the payloads already written count as done; `kado-write-failed` is a Kado
refusal or failure at that step. Either way the next `/review` lists the stem as `failed-delivery` with Resume / Drop
(F5-AC10). The skill reads `status` first because the same key `problems` appears under `refused` and `stopped` with
opposite meanings for the user: fix the document, or just try again.

### Why `doc-changed` Branches on `reason` and Names Obsidian for `open-unsaved` (Phase 6 Live Walk)

WHY: the live walk of 2026-11-13 stopped twice at the mark with `doc-changed` although the user had saved nothing
since the preview: the review document was open in Obsidian and the `update-time-on-edit` plugin had changed its
`Updated:` stamp in the editor buffer — unsaved — so Kado's dirty-editor guard refused the write. The skill said "edited,
or open with unsaved edits: save it and run `/review` again", which is true and did not help: the user had not typed
anything and did not know a plugin had. The script now names the cause in `reason` (`open-unsaved` for Kado's editor
refusal, `changed-since-read` for the write guard, `unknown` for a conflict with neither; docs/tomo/scripts/
review-instructions.md, "WHY the `doc-changed` Stop Carries a `reason`"), and the skill branches on it once: for
`open-unsaved` it says the document is open in Obsidian with unsaved changes, names a plugin that stamps the note on
edit as a possible cause, and says to save it (Cmd+S) or close it, then run `/review` and choose Resume — the two
actions that clear the editor buffer, and the step that retries the mark. After Cmd+S the live walk's Resume went
through. `changed-since-read` and `unknown` keep the earlier wording: for a stale stamp "save and run `/review` again"
is right, and for an unknown conflict nothing more specific is known. The reason is read from Kado's message in the
script, never shown: Kado's message names the document's path, and stdout carries problem classes only.

### Why a `stopped` Delivery Asks Retry, Drop or Abort in Place (Spec 046 T6.3 Live Walk)

WHY: the walk of 2026-11-18 stopped at the mark with `open-unsaved`, and the skill sent the user to "run `/review`
and choose Resume". In the two minutes before that Resume, something in Obsidian moved a file onto the target path,
and the Resume refused `place-missing` from a plan rebuilt against that vault. With no line telling it what to do, the
model hand-wrote the document mark through Kado and edited `meta.json`. Two changes answer it. First, the script now
resumes from the payloads its first attempt stored, so a rerun is safe whatever the vault did meanwhile
(docs/tomo/scripts/review-instructions.md, "WHY a Resume Uploads the Stored Payloads"). Second, every `stopped`
branch keeps its explanation (for `open-unsaved`: save or close the document first) and then asks
`1 Retry · 2 Drop · 3 Abort` in place. Retry reruns `deliver --stem <stem>` and branches by the same step 8 list;
Drop is step 9; Abort stops, and the next `/review` still lists the stem as `failed-delivery`, whose Resume is the
same `deliver` rerun. A round trip through the listing was the gap in which the vault changed. Asking in place keeps
the retry next to the cause the user has just fixed.

The step also carries the skill's one `STRICT` line: never write the review document, the instruction set, the new
note or a stage file other than `proposals.json` and `confirmed-<kind>.json` by hand; only the
review scripts write them. The line exists because this deviation was observed. A hand-written mark and a hand-edited `meta.json`
describe a delivery the script never made, so the next `deliver` or `drop` acts on a state that did not happen. The
owner's wording was "anything under `tomo-tmp/`". The line excludes the two files the skill's top paragraph tells
the model to write, so the two imperatives cannot contradict each other.

### Why a `resumed` Report Is the Plan the Delivery Wrote (Phase 6 Live Walk)

WHY: the skill repeats `target`, `place` and the `target_appeared` line from the `deliver` output as what Tomo did.
On a resume the script used to report the plan rebuilt against the vault now — the live walk's resume said `replace`
at `Tomo Review` with `target_appeared` after the first attempt had written a new note and a `move_note` set, because
Hashi had moved the note in between. The script now records the plan it writes with its first step and a `resumed`
output reports that record (docs/tomo/scripts/review-instructions.md, "WHY a Resume Reports the Plan It Recorded");
the skill's step 8 lines did not change, they only became true on a resume.

### Why a Resume Can Be Refused With `replan-differs` or `anchor-needed` (fix #258)

WHY: issue #258, owner decision 2026-11-13. A resume writes the undone set steps from the re-plan, so a vault that
changed between the stop and the resume could land a set that contradicts the note or the set the first attempt
already wrote. The script now compares the re-plan with the recorded plan before it writes and refuses
`replan-differs` (docs/tomo/scripts/review-instructions.md, "WHY a Resume Refuses a Re-Plan That Differs From the
Record"). The step 8 line says what that means in the user's terms — the vault changed since the stopped delivery,
the target note or its place is not what the first attempt wrote for — and that nothing more was written, then
offers Drop (step 9) or Abort: Resume from the listing would refuse again, because the re-plan is built from the
vault as it is now, and the half-written set is the user's to look at in Obsidian before anything else lands. Start
over is not offered here: the stopped delivery's files are still in the inbox, and `drop` is the step that withdraws
them.

The listing's Resume runs `deliver --stem` without `--place-anchor` — the heading picked in step 7 lives in the
conversation that stopped, and the record never holds a heading of the note's own (ADR-9). The script records that a
heading was picked and refuses `anchor-needed` with `headings` on a resume without it (docs/tomo/scripts/
review-instructions.md, "WHY a Picked Anchor Is Recorded as a Flag and Asked Again"). The step 8 line reuses the
step 7 pick: print `headings`, ask for a number, rerun `preview` with the heading as `--place-anchor` and branch by
the step 7 list, so Deliver reaches step 8 with the heading again. A new pick dialogue in step 8 was rejected: the
step 7 rerun shows the section at the chosen place before anything lands, and one pick flow keeps the "offered once"
rule of the collision case in one place. The refused branch names the two tokens before "Any other → the step 7
lines" so the precedence is explicit; step 7 has no line for either.

## Why `drop` Withdraws and Abort Before Delivery Writes Nothing (ADR-13)

WHY: Abort at the Deliver question is free: nothing was written, the document stays open. Drop is offered only for a
`failed-delivery`, where files may already be in the inbox. Kado offers Tomo no delete, so
`review-instructions.py drop --stem` cannot remove them; it withdraws instead: once any delivery step began it writes the set JSON with an empty
`actions` list (schema-valid, nothing for Hashi to apply) and an MD that says withdrawn and names every file the
delivery left, a lone new note included, so the user can delete them in Obsidian; before any step began it removes
only the stage. The skill reports `status: withdrawn` with the `paths`, or `dropped` with `removed`. `already-applied`
is refused: Hashi applied an action, so the set is the vault's history now and nothing is withdrawn and nothing more
is delivered (the skill says so and offers nothing). `set-changed` means the set was edited between read and write;
the skill runs drop once more. A withdrawn review — one whose `meta.json` says so — is never listed again.

`kado-write-failed` from `drop` is not "nothing was withdrawn" (the first draft of the skill said that; T5.2 fix
round): `drop` writes the withdrawn set JSON first and the readable MD second, and marks `meta.json` only after
both. A failure on the second write leaves the set already empty — nothing for Hashi to apply — while the MD in
the inbox still lists the actions and the stage still says a delivery failed. The skill therefore says the
withdrawal may be partly written and nothing else changed, and runs `drop` once more in the same turn: a rerun
reads the empty set back (not applied), rewrites it under the guard and writes the MD, then marks the stage. Once,
not until it works: a Kado that refuses every write would loop. The second failure is shown, the skill says the
next `/review` lists the review again and offers Drop, and the run stops; the user sees both inbox files in
Obsidian. That later offer exists since the Phase 5 cleanup (owner decision): `lib/review_state.review_state`
withdraws a stem only when `meta.json` says so, and lists a begun stem whose set was emptied without the mark as
`failed-delivery` — the state whose offer is `1 Resume · 2 Drop` (docs/tomo/scripts/lib/review_state.md, "WHY an
Emptied Set Withdraws Only Without a Begun Record"). Drop is the path that works there; Resume runs `deliver`,
which refuses `set-withdrawn` on an emptied set rather than resuming over it (it would skip the set as done and
mark the document; docs/tomo/scripts/review-instructions.md, "WHY an Emptied Set on a Begun Stem Is
`set-withdrawn`"), so the skill's `set-withdrawn` line says an earlier Drop emptied the set but did not finish
and asks `1 Drop · 2 Abort` — the one place Pass 2 routes from the deliver step into the drop step. The listing
cannot tell a half-withdrawn stem from any other failed delivery, and a seventh state for it was rejected (the
six are the SDD's canonical list); the refusal from `deliver` is where the two part, so the skill asks there.

`drop` refuses three more problems that are not its own: `setup-missing` and `setup-invalid` (with `errors`) from
`_setup`, which it needs for the inbox and the set paths, and `inbox-not-configured` when the inbox path is unsafe
(the `Refused(...)` raises in the `_setup` and `drop` bodies of the Pass 2 script; its header lists them under "every
subcommand"). The first draft's drop step had a line for `already-applied` only, so a drop on a broken setup reached
the model with no branch (Phase 5 drift round). The step reuses the `refused` line of the preview step — show
`problems` and `errors` verbatim and stop — rather than wording the three again: they are the same refusals with the
same cure (fix the setup, run `/review` again), and one wording cannot drift from the other. The test reads the
`Refused("<token>")` literals of those two bodies, so a fourth refusal added to the path fails the suite without a line.

## Why the Verbatim Rule Names Only What No Step Says in Its Own Words

WHY: The first rule list said to show `problems`, `warnings`, `notices` and `hints` verbatim and never paraphrase
them, while steps 6 to 8 give `warnings`, `notices` and the preview's `problems` one plain-language line each — a
contradiction a literal model resolves either way, printing the bare token and the line, or the token alone (Phase
5 drift round). The rule is narrowed to what no step reworks: `error`, `expected`, `example` and `errors` (the
scripts write them for the user, see "Why Script Errors Are Shown Verbatim"), the `hints` of the setup step (the
script's own access wording) and the `problems` of the read step (shown with the `report`). Everything else — a
`problems` entry, a `warnings` entry, a `notices` entry — is said by the line its step gives it, and without such a
line it is shown verbatim, so a token the scripts add before the skill has a line for it still reaches the user
unparaphrased. The steps that say "verbatim" themselves (`write`'s and `preview`'s `refused` branches, `drop`'s shared
refusals) are the fallback written out.

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
scripts' reports and `section_md` — the user's own approved section — and never quotes a stage file, a daily, a
journal answer or a tracker value into its reply. Where the content does rest — the session transcript in the
container home (the main one and the three review agents' own, which hold what they read), the stage `tomo-tmp/review/<stem>/` until `write` or `replace --abort`
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

Spec 047 adds the four `STRICT` blocks of step 5, each for a deviation observed in an earlier run (see "Why Step
5's STRICT Blocks"). The first `STRICT` it carried is in step 8 (spec 046 T6.3). The 2026-11-18 live walk observed the model hand-writing the
document mark and editing `meta.json` after a refused resume (see "Why a `stopped` Delivery Asks Retry, Drop or Abort
in Place").

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
removed after the save. The skill pins no `model`: since spec 047 the proposals are the `review-proposer`'s work
(`opus`, ADR-7), and the main session only orchestrates, so it runs on the session's model. `user-invocable: true` and an `argument-hint` make the skill itself show in the `/` menu beside the
shim, as `/note` does. The description carries `MUST BE USED` per the authoring rules, with a `NOT for` clause that
keeps inbox triage with `/inbox` and single notes with `/note`. `allowed-tools` holds Bash, Read and Write
(the confirmed-setup file; Read for the one config key), plus `Agent` since spec 047 for the three review agents
(ADR-8), and nothing that reaches the
vault: every vault access goes through the scripts and Kado. The skill's body follows the `/note` precedent (a Rules
list, then numbered steps) rather than the authoring plugin's Persona / Interface / Constraints layout: the repo rule
for runtime files allows imperatives only, and a persona or an interface block would be prose the model does not act
on.

## WHY the Stop Bullet of Step 7 Is a List of Short Sub-Bullets (spec 046 T6.4, SKILL 0.2.12)

The bullet for `section-missing`, `section-ambiguous`, `section-broken`, `section-moved`, `block-in-review-section` and
`landing-off-limits` was one sentence of about 1,100 characters: print the plan, then the stop line per section with
five named parts, then the beside-another-problem rule. The model followed it, but a reviewer could not see which
imperative belonged to which clause. It is now a head line (the problems that match) over sub-bullets: print the plan
without its question; one line per stopped section naming its heading, `placement`, reason and `choices`; the
beside-another-problem rule; then the two existing sub-bullets (empty `choices` ends, otherwise ask). No imperative and
no quoted string changed. `tests/test_046_t5_6_skill_choices.py` and `tests/test_review_skill_pass2.py` pin the new
layout (whitespace is collapsed by `_section`, so a raw-line test pins the nesting and the line length).
