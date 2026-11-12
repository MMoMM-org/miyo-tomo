# WHY: review-session.py

> Rationale for decisions in `tomo/scripts/review-session.py`.
> The script is the deterministic session start of `/review` (spec 045,
> ADR-1, ADR-5, ADR-7, ADR-8): `match` previews the setup of one period kind
> against the notes that exist (F1), `setup-input` turns a confirmed proposal
> into the writer input (T2.2); `start` parses the request, reports the
> setup per kind and lists the open reviews with their state (T2.3, F2).

## WHY the Setup Preview Is a Script

WHY: ADR-1 and ADR-5, the same shape as `/note`'s `note-session.py match`.
Listing a folder, matching names against a Moment-style format, reading
dates out of eight notes and deriving a week rule are rules, not judgement.
Done by the model they drift between runs (a format that matches on one run
and not the next, a week rule read off the Obsidian plugin settings). One
script makes the preview the same every time and testable on a fake vault
without a model in the loop (Constitution L1). Nothing is saved by `match`;
the writer (`vault-config-writer.py review`) runs only after the user
confirms, and `setup-input` is the only step between the two.

## WHY Every Actionable Outcome Exits 0

WHY: SDD Internal API Changes and the repo rule for agent-called scripts. The
skill acts on `status`, `error` and `errors`; a non-zero exit makes the model
re-run the script or improvise. Exit 2 is reserved for a bad invocation
(argparse: unknown subcommand, bad `--kind`, missing `--confirmed` file), exit
1 for an unexpected exception, where stderr carries the exception class name
and nothing else (ADR-9: stderr never carries note text, titles or paths).

## WHY the Kado Access and the Inference Live in `lib/`

WHY: T2.2 code review. With `match` and `setup-input` alone the script passed
600 lines, and T2.3 adds `start`, which needs the same Kado wrapper and the
same date helpers. The wrapper, the `Stopped` exception and the helpers that
read a weekly note's evidence are `lib/review_vault.py` (WHY:
`docs/tomo/scripts/lib/review_vault.md` — the error mapping, `kado-none`,
`journal-end-date` − 6, day headings as a full week); the week-rule
inference is `lib/week_rule_inference.py` (WHY:
`docs/tomo/scripts/lib/week_rule_inference.md` — never `.obsidian`, the
eight-note budget, the rule intersection, duplicated stems). The script
keeps what is specific to the subcommands: the precedence of flags, config,
inference and defaults, the name matching, the proposal, the writer input
and the argparse wiring.

The T2.3 code review found the script at 486 lines once `start` was in. The
helpers that only turn the config into a shape and need neither Kado nor
argparse — the configured name formats, the inbox folder, the current setup
of a kind and the request dict — moved to `lib/review_config.py`
(`configured_formats`, `inbox_folder`, `current_setup`, `request_dict`; WHY:
`docs/tomo/scripts/lib/review_config.md`). The script imports them; nothing
it prints changed.

## WHY the Config Beats the Inference

WHY: the documented order is flags > config > inference > defaults, and the
first draft had the inference ahead of the config. A `review.week` rule in
the config is a setup the user confirmed; the inference reads what the notes
look like today. If the notes were later renamed or an old year counted
differently sits in the folder, the inference changing silently would show a
proposal the user never confirmed, and `/review setup` would display a
guess instead of the current setup (the same reason every other configured
value wins over its proposal). `evidence.week_rule` still reports what the
notes showed when no week flag is passed (the config is not an answer the
user gave in this dialogue; see the next section for the flags), and a
configured rule the notes contradict puts those notes under `unmatched`, so
the skill can say so.

## WHY Two Notes With the Same Stem Are Both Listed

WHY: the first draft keyed the listing by stem, so a note in the folder and
its namesake in a year subfolder collapsed into one: `notes_checked`
undercounted, the hidden copy's dates never reached the inference, and
`matched`/`unmatched` showed one note where two exist. Every path is now
matched on its own dates, and a duplicated stem appears once per note in
the listing — the preview shows what the folder holds, and T2.3's `start`
meets the duplicate as a known case rather than a surprise.

## WHY `week_rule` Is `given` Once the Flags Are Passed, and Reports the Notes Otherwise

WHY: F1-AC5 and F1-AC8, and the final fix round of the live-walk fix (spec
review of 428822c3..73ed7348). When the skill re-runs `match` with
`--first-day` and `--min-days` from the user's answer or correction, the
proposal follows the flags and the matches are recomputed under them. The
first version kept `evidence.week_rule` at what the notes showed on every
call, "so the skill can show the notes the new rule no longer matches
without pretending the notes agreed" — but the skill keys the week question
on `ambiguous`, and notes that disagreed before the answer still disagree
after it: the rerun said `ambiguous` again and a literal model asked the
week question a second time, and once more after every Correct rerun. Now
`week_rule` is `given` whenever `--first-day` was passed: the flags are the
user's answer, and the answer stands. The notes' own verdict is not reported
beside it, because nothing reads it — the "no notes to compare" hint is
computed inside the script from the inference, and what the skill shows the
user is `matched`/`unmatched`, which still list the notes the answered rule
does not fit (the evidence the first version was keeping the verdict for).
Without the flags the field reports the notes as before (`inferred`,
`ambiguous`, `default`): a configured rule is not an answer given in this
dialogue, so a saved setup whose notes disagree still gets the question on
`/review setup`, and its answer then reruns with the flags. `--format` works
the same way as the week flags. The two week flags are
accepted only together; one alone is a usage error (exit 2). A week rule is
one answer — the user names the first day and how week 1 is counted in the
same breath, and the skill always passes both after that answer. Filling the
missing half from the inferred or configured rule would silently pair the
user's first day with a `min_days` the notes may never have supported, and
the proposal would then show a rule nobody stated. A dated note is `matched` only
when its name parses under the proposal's format and rule AND the resulting
week starts on the note's date; a name that parses with contradicting dates
is listed under `unmatched` (SDD walkthrough row 2026-03-01 under Sunday).
Notes beyond the eight checked are matched by name alone.

## WHY the Default Format Follows the Rule

WHY: `period.check_format` refuses upper-case week tokens under a non-ISO rule
(`iso-tokens-need-iso-rule`). The proposal therefore defaults to
`GGGG-[W]WW` for the ISO rule and `gggg-[W]ww` otherwise; months default to
`YYYY-MM`. A configured `naming.calendar_patterns.<kind>` or `--format` wins
over the default, and any problem `check_format` finds with the format in
use is listed in `evidence.format_problems` so the skill can say at preview
time what `setup-input` would refuse later. An unsafe format (`/`, `\`, `..`)
stops the preview before any Kado call with `error.kind = unsafe-format`: a
name that leaves its folder must not even be matched.

## WHY `kado-none` Is Never "No Notes"

WHY: PRD Rule 6, F3-AC9 and the memory rule that an empty Kado search hides a
denial. A listing that returns nothing or `Path not found` is reported as
`folder_listing: kado-none` with the access hint in `hints`; the skill asks
before proposing to create notes there. `found` with no name that parses
under the proposal's format (an empty `matched` while the week rule is
`default`, or a month folder with only non-periodic names) means the folder
answered, but with nothing to compare the format against — only then does
the script add the "no notes to compare" hint (F1-AC4), so the two wordings
can never appear for the same listing. The script puts the sentence in
`hints` rather than leaving it to the skill because the skill was observed
saying "no notes" for a `kado-none` listing; a hint the script chose is the
same on every run. Names that parse but fail their dates under a flagged rule
are notes to compare — they are listed under `unmatched` without the hint.

The folders come from `review_config.folder_for`, the same resolver `start`
and the reader use (config over profile, a disabled or blank entry is None),
so the preview and the session can never list two different folders.

## WHY the Template Is Classified by Reading It

WHY: ADR-8 and F1-AC7. Whether a template is Templater (`<%`) decides the
delivery path (variant or raw template with a Templater hint), so the
proposal names the kind. `missing` is a configured name Kado reports as not
found, or no mapping at all; `unreadable` is any other Kado failure on the
read (a tool error, a refused key) and the hint says the key may have no
access — Kado answers the same way for both. A broken connection is not
`unreadable`: it stops the whole preview as `kado-unreachable`, because the
listing that succeeded a moment ago would be stale evidence.

### WHY an Absent Mapping Lists Candidates and `--template` Names the Choice

WHY: the live walk (container session 5b959432, Phase 6). The first version
attempted no template search when the mapping was absent ("a guessed file
would have to be confirmed by the user anyway"). The owner's instance maps
no `weekly` or `monthly` template while the templates folder holds
`t_week*.md` and `t_month*.md`; the proposal came back with `template: null`
and, since the anchor is proposed from the template's headings, `place.anchor:
null` — a proposal `setup-input` rejects. Now `match` lists the templates
folder once when neither the mapping nor `--template` names a template, and
prints the notes whose file name fits the kind as `template_candidates`
(`lib/review_templates.py`; WHY: `docs/tomo/scripts/lib/review_templates.md`
— the words, the order, the names). The skill asks which one, with `0 none`,
and reruns `match` with `--template <name>`: the choice goes through the
same read and the same heading proposal as a mapping entry, so a chosen
template and a configured one can never produce different proposals.
`--template` wins over a mapping entry like every other flag; the proposal
carries the name with `.md` and `setup-input` passes it on as `template`, the
key the writer already saves to `templates.mapping.<granularity>`. `0 none`
keeps the first output: no rerun, `template` stays null, and the writer
removes a mapping key that is not there — nothing is saved to the mapping.
A mapping entry is used as before, without a listing and without a question.

### WHY `needs_anchor` Is Marked Instead of Left to `setup-input`

WHY: the same walk. The proposal must never carry an anchor the writer will
refuse without saying so first: `setup-input`'s `/place/anchor` pointer
after Confirm sends the user back into the Correct branch with no heading
to choose from. When no anchor can be proposed — no template, `0 none`, a
template without a heading below its title — the output carries
`needs_anchor: true` and `anchor_candidates`, the headings of the two most
recent periodic notes of the kind (two reads at most; the choice of two and
the order are in `review_templates.md`). The skill asks which heading before
it offers Confirm and puts the answer into the proposal; `setup-input` still
validates, so a typed heading that is blank is refused there. A configured
anchor or one proposed from the template leaves both keys out and costs no
read. The first `match` output carries the template candidates and the
anchor candidates together, so `0 none` needs no second call.

### WHY `--template none` and `--anchor` Carry the Answers on Every Rerun

WHY: the spec review of the live-walk fix (fix round 1). The dialogue reruns
`match` after both questions are answered — the week-rule rerun with
`--first-day`/`--min-days`, every Correct of the folder, the format, the rule
or the template — and the first version had no way to tell a rerun what the
user had already said. After `0 none` the proposal's `template` is null, so
the next call found neither a mapping entry nor `--template`, listed the
templates folder again and the skill asked the template question a second
time; the typed anchor was lost the same way, because `needs_anchor` came
back with the candidates and the model had nothing to pass. A prose rule
("carry the choice") puts the memory in the model; the fix puts it in the
call, where a literal model copies it: `--template none` is the `0 none`
answer — no listing, no `template_candidates`, `template` null and the plain
note — and `--anchor <heading>` is the picked or typed heading: `place.anchor`
is set from it, `needs_anchor` is not marked and the two periodic notes are
not read. Both are flags, so both win over the config like `--folder` and
`--format` do: `none` over a mapping entry (a Correct from a mapped template
to the plain note), `--anchor` over a configured anchor and over the heading
a template would propose (the user's answer stands even when a corrected
template has headings of its own; the template's headings are still listed
in `evidence.template_headings`). The word `none` is reserved as the bare
value only — `none.md` is a template file of that name — and the anchor is
trimmed and must be one non-blank line, refused as a usage error (exit 2)
like an unsafe template name, so a blank answer never reaches `setup-input`.
Both rules are `lib/review_templates.template_choice` and `anchor_text`
(WHY: `docs/tomo/scripts/lib/review_templates.md`); the script wraps them
into argparse types. The skill carries `--template <template>` on every
`match` call after the first, `--anchor "<anchor>"` once the anchor is
given and `--first-day <day> --min-days <n>` once the week question is
answered (the week flags make `week_rule` `given`; the section above), so
the script asks each question once however often the dialogue reruns.

## WHY the Place and the Daily Sections Come From the Templates

WHY: F1-AC1 asks for a proposal of the review heading, its place and the
daily sections, so that the user confirms rather than types. The template's
headings (level 2 and deeper, without Templater code) are the only source
that exists before any note is read; the proposed anchor is the last of the
shallowest headings with placement `before`, which keeps the review above the
user's closing section without guessing its name. The daily sections are the
daily template's headings (`templates.mapping.daily`) minus headings that
carry Templater code or links, because their text changes per day (the
Dayplanner embed). A configured value always wins: `/review setup` shows the
current setup, not a fresh guess. `evidence.template_headings` lists the
anchor candidates (the same headings the proposal chose from, with their
levels) so the skill can offer alternatives when the user corrects; the
title and Templater headings are left out because neither can be a place.

## WHY the Language Falls Back to the Notes' `locale`

WHY: SDD Data Storage Changes: the review language defaults to the
frontmatter `locale` of the dailies, else `en`. The weekly notes checked for
the rule carry the same key in the owner's vault, so no extra read is spent;
a month preview reads no note for the language (the two reads a `needs_anchor`
month spends are for headings, not `locale`) and falls back to the configured
language or `en` — the week setup normally runs first and has saved it by then.

## WHY the Daily-Path Fix Is Proposed Only When the Other Spelling Exists

WHY: F1-AC9. The instance config carries `Calendar/301 Daily/ ` with a
trailing space; proposing the trimmed spelling blindly would "fix" a path
that may not exist. The script probes the trimmed spelling through
`lib/vault_folder_lookup` (one `list_dir`) and proposes the fix only when
that folder is `listed`; `absent` and `unanswered` propose nothing. The
probe runs only when the configured path differs from its trimmed form, so a
clean config costs no call. Saving the fix is still the user's confirmation:
`setup-input` carries `daily_path_fix` only when the confirmed proposal does.

## WHY `setup-input` Validates Before the Writer Does

WHY: SDD Error Handling row for `setup-input`: an invalid confirmed input is
`status: invalid` with pointers and nothing saved. The writer validates
again, but the skill needs the pointers before it spends a writer call, and
the confirmed proposal is not the writer's shape: `template_kind` is dropped,
a month proposal's null `first_day`/`min_days` are dropped (the schema forbids
them for a month), and `daily_path_fix` is reduced to the found spelling.
Validation is `review_config.input_problems`, the writer's own check, so the
two cannot disagree. The input is written atomically to
`tomo-tmp/review/setup-<kind>.json` (`--output` overrides) and `input_path`
names it; the skill passes it to the writer and removes it, as `/note` does
with `note-include.json`.

## WHY `start` Parses the Argument Before It Reaches Kado

WHY: F2 (every argument form yields the request or one error with the
expectation and an example) and the Error Handling rows for `start`:
"nothing written". The argument is parsed by `lib/period.parse_args` under
the configured week rule (`review.week`, else ISO) and the configured name
formats (`naming.calendar_patterns`, else the defaults), so `/review` with
no argument names the last finished week the way the user counts weeks, and
`@<note>` recognises the user's own names. An argument error returns at
once with `error`, `setup` and an empty listing — no Kado call is spent on a
typo, the skill shows the expectation and the example, and the user's retry
lists the open reviews. The script carries `status: ok` with that `error`
so that one key (`status`) says whether Kado was reached, as in `match`;
`status: stopped` with `error.kind` `kado-unreachable` / `kado-auth` is the
only other shape.

## WHY the Request Carries Its First and Last Day

WHY: two week rules can name the same week number for different days (the
ISO week `2026-W45` and the Sunday-first `2026-W45` start a day apart), and
`/review` must say which seven days it is about before it reads anything.
`request.start` and `request.end` are the period's dates under the rule the
argument was parsed with; the SDD's `period` name stays the key the later
scripts take.

## WHY the Open Reviews Come From the Vault

WHY: ADR-2: the open state lives in the inbox document. `start` runs one
`byFrontmatter` query (`tomo.doc_type=review`, `filter.path` = the inbox —
the same call `inbox-triage.py` makes) and one `read_frontmatter` per hit,
because Kado's `byFrontmatter` returns an empty frontmatter; the document's
own keys (`review_period`, `review_kind`, `review_stem`, `tomo.state`) name
the review, so a renamed document is still found and listed. `tomo-tmp` is
consulted only for the content-free `meta.json` (`steps_done`,
`failed_step`, `withdrawn`, `applied_reported`) and never decides whether a
review exists. The listing and the state are `lib/review_state` (WHY:
`docs/tomo/scripts/lib/review_state.md`); the script only resolves the
inbox (config over profile) and passes the documents on with the vault,
together with the configured week rule **and** the configured name formats
— the same pair the argument was parsed with, so the listing orders
`2027-W01` by the day the request would give it (the first version passed
the rule alone, and the default ISO format overrode it). An inbox that
neither the config nor the profile names is reported as `problems:
[inbox-not-configured]` with an empty listing rather than a crash: the
request is still usable and the setup dialogue fixes the rest.

### WHY the Listing Probes the Set JSON (T4.3) and `start` Writes `applied_reported`

WHY: ADR-6: an approved document's state lives in `<inbox>/<stem>_instructions.json`,
where Hashi writes `applied` per action. The listing hands every document
to `review_state.stem_state`, which reads the set through Kado for an
approved document (a pending one cannot have a set and costs no read) and
probes the target and the inbox copy only for a set that waits — the same
function `review-instructions.py status` calls, so `start` and `status`
never disagree. A Kado failure on a probe stops the run like the
frontmatter query does (`kado-auth` / `kado-unreachable`), because reading
a refused key as "absent" would list every delivered review as
`failed-delivery` and offer resume and drop on sets that exist.

`applied` is reported once (SDD step 4). The classifier stays pure and the
listing drops an `applied` review whose meta says `applied_reported`; it is
`start` that writes the flag, after printing is decided, for every
`applied` review in the list — the script that reports is the one that
knows it reported. A review whose `meta.json` is gone (a cleaned
`tomo-tmp`) gets a minimal one with the flag, otherwise it would be offered
on every start. Nothing of the vault is written; `tomo-tmp` is the
instance's own stage.

#### WHY a Failed Flag Write Keeps the Listing and Adds `notices: [applied-not-recorded]`

WHY: the flag is bookkeeping about the listing, not part of it. The first
version wrote it unguarded after the result was built, so a read-only or
full `tomo-tmp` raised `OSError` into `main()`'s handler: the class name on
stderr, exit 1, and the whole listing — request, setup, every open review —
lost over a file whose only job is to silence a repeat. Now `_record_applied`
catches `OSError` per review (the `mkdir` and the `save_meta` alike) and
`start` still returns `status: ok` with the full listing; the only
consequence of a swallowed failure is that the applied review is offered
again on the next start, which is the pre-flag behaviour and harmless.

The failure is still told: the result carries `notices: ["applied-not-recorded"]`
(the key only when a write failed, the name once however many reviews it
hit), so the skill can add one line — the review will be shown again next
time — instead of leaving the user to meet the same "applied" twice without
a reason. `notices` is the non-refusing vocabulary `review-instructions.py
preview` / `deliver` already use, and a bare name keeps the key metadata
only: no path, no stem (the stem is already in `open_reviews`), no error
text. Nothing reaches stderr, because stderr's one meaning for this script
is "unexpected exception, exit 1" and a recorded, non-fatal failure is
neither.

## WHY `setup` Returns the Current Values

WHY: F1-AC10 (`/review setup` changes the setup) and the plan: the setup
dialogue must show what is saved before it proposes anything. For a `setup`
request the output carries `current.week` and `current.month`: the saved
values in the shape of `match`'s proposal (so the skill shows one table),
`null` for a kind without a setup, or `{"invalid": [pointers]}` when a
setup is present but `review_config` refuses it — the dialogue then names
the keys instead of silently proposing over them. `setup.week` /
`setup.month` (`present` / `missing`) are in every output so the skill runs
the setup first when the requested kind has none (F2).

## WHY the JSON Is Written ASCII-Escaped

WHY: as in `note-session.py`: `ensure_ascii=True` cannot fail on a non-UTF-8
stdout or a lone surrogate, and every reader decodes the escapes.
