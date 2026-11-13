# WHY: lib/review_templates.py

> Rationale for decisions in `tomo/scripts/lib/review_templates.py`.
> The module owns the two questions `review-session.py match` can leave open
> for the setup dialogue (spec 045 F1-AC7, ADR-8): which template the
> periodic note of a kind uses when `templates.mapping` names none, and at
> which heading the review section sits when no template heading can be
> proposed.

## WHY This Left `review-session.py`

WHY: the script stood at 482 lines before the live-walk fix and the
Constitution caps dense files at ~300–500 LOC. Listing candidates and
reading the headings of recent periodic notes are two small rules with no
argparse and no proposal logic in them; the script keeps the precedence
(flag > mapping > candidates) and the output shape. What a template's
headings propose (`template_anchor_candidates`, `propose_anchor`,
`daily_sections_from`) and the join of a name onto `templates.base_path`
(`template_vault_path`) moved with them: they are template rules, and the
script stays under the cap with them gone. Fix round 1 (`--template none`,
`--anchor`) pushed the script to 511 lines, so the resolution itself —
read and classify the named template, or list the candidates once, with the
two hint sentences for an unreadable template and a `kado-none` templates
folder — moved here as `resolve_template`; the script keeps the precedence
(`none` > flag > mapping) and appends the hint the function returns.

## WHY the Candidates Come From a Listing, Not a Guess

WHY: the live walk (container session 5b959432): the owner's instance config
maps `daily`, `map_note`, `atomic_note`, `project` and `source` but not
`weekly` or `monthly`, while the templates folder holds `t_week.md`,
`t_week_privat.md`, `t_week_work.md` and their `t_month*` siblings. `match`
read the template only from `templates.mapping.<granularity>`, proposed
`template: null`, and — because the anchor comes from the template's headings
— `place.anchor: null`, a proposal `setup-input` rejects (`/place/anchor` is
a required trimmed string). The first draft's WHY said "no template search
is attempted when the mapping is absent: a guessed file would have to be
confirmed by the user anyway"; the walk showed the opposite cost — the user
cannot name a file the dialogue never showed. So `match` lists
`templates.base_path` once (the same `list_notes` call the periodic folder
gets, two levels deep, because template folders hold subfolders too) and
keeps the notes whose file name fits the kind: `week` or `woche` for a week,
`month` or `monat` for a month, case-insensitive. The words cover the
owner's English file names and German ones; a vault that names its templates
otherwise gets an empty list and the plain note, as before. The word is
looked for in the file name alone, never in the folders above it: a
templates subfolder called `weekly/` or `Monatlich/` says what its notes are
for, not which of them is the periodic template, and listing every note in
it would offer `weekly/t_notes` as a week template (code review round 1 of
the fix pinned this; the filter had matched the basename all along but no
test failed when a mutation matched the whole relative stem). Inside the file
name the word matches as a substring, so `t_weekend` and `Monatsabschluss`
are listed too: the match is a recall filter for a numbered question the
user answers with `0 none` last, and a stricter rule (a word boundary, a
prefix) would hide a vault's real template names — `Wochenplan`,
`Monatsübersicht` — to spare the user one wrong entry in a list of four. The candidates
are sorted case-insensitively so the numbered question is the same on every
run and the user's "2" means the same file next time. Names are the path
below `base_path` without `.md` — what the user sees in Obsidian — and
`--template` takes that name with or without the extension; the proposal
and the saved mapping carry it with `.md`, as every other mapping entry.

The listing costs one Kado call and is spent only when neither the mapping
nor `--template` names a template; a `kado-none` answer (empty, or the key
does not reach the folder) gives an empty list and a hint that names the
folder, never "there are no templates" (Rule 6). No candidate is read before
it is chosen: reading three or four templates to show their headings would
spend reads on files the user is about to reject.

## WHY `--template` Refuses a `..` Segment, `\`, a Line Break and a Leading `/`

WHY: the name is joined to `templates.base_path` and read through Kado. A
name that climbs out of the folder would read a note outside the templates
folder and save that path into `templates.mapping`. The refusal is the
argparse type (exit 2, a bad invocation), the same class as a bad `--kind`,
so the skill shows the usage error and the user types another name. A `/`
inside the name is allowed: the candidates list subfolder entries as
`archive/Wochenplan alt`. `..` is refused as a path segment (`../t_week`,
`archive/../t_week`, the bare `..`), not as a substring: only a whole
segment climbs, and a template called `t_week..old` is a name below the
folder like any other (code review round 1; the first version refused the
substring and with it that name). A line break is refused with the same
error: a name is one line, and a `--template` value with a second line would
save a two-line path into `templates.mapping` — the same rule `anchor_text`
applies to `--anchor`.

## WHY `template_choice` Knows `none` and `anchor_text` Trims One Line

WHY: fix round 1 of the live-walk fix (the WHY of the rerun problem itself:
`docs/tomo/scripts/review-session.md`, "WHY `--template none` and `--anchor`
Carry the Answers on Every Rerun"). `template_choice(text)` is
`template_name` with one reserved word: the bare value `none` is the
`0 none` answer and returns the `NO_TEMPLATE` sentinel, so the script can
tell "the user chose no template" from "no flag was given" — the two look the
same in the proposal (`template: null`) but only the second lists the
candidates. The value is trimmed before the word is compared, as
`template_name` trims every other value (code review round 1: the first
version compared the raw text, so ` none ` would have become the template
`none.md` while ` t_week ` became `t_week`); the word is then reserved
lowercase and exact, `None` is not a spelling a literal model produces from
the skill's `none`. The consequence is deliberate: a template file called
`none.md` cannot be chosen by its bare name — `--template none` is always
the "no template" answer — and is reached with the extension, `none.md`,
which `template_name` keeps as it is. `anchor_text(text)` is the
`--anchor` rule: the answer is trimmed (a copied heading carries whitespace)
and must be one non-blank line — a heading is one line, and `setup-input`
requires a non-blank `place.anchor`, so refusing a blank or multi-line value
at the flag (`ValueError`, exit 2 through the script's argparse wrapper)
keeps the refusal where the user typed it. Leading `#` are not stripped: the
candidates are offered as text without them, and an anchor that does not
match a heading is caught by `review-instructions.py preview` as
`place-missing` with the headings to pick from, which is a better place to
learn it than a silent rewrite of the answer.

## WHY `template_has_frontmatter` Is the Merge's Own Rule

WHY: the month live walk of 2026-11-13 (Phase 6): a raw Templater template
whose opening `---` is rendered by an include has no block at line 1 for
`doc_frontmatter.merge_tomo_block_into_markdown`, which prepends its own,
and the rendered note carried two frontmatter blocks. The setup now asks
when the chosen template has no block (WHY of the question and the carried
answer: `docs/tomo/scripts/review-session.md`, "WHY `template_frontmatter`
Is Reported"). `template_has_frontmatter(text)` decides "has a block" with
the merge's own test, `body_after_frontmatter(text) != text`: that helper
strips the first leading `---` … `---` block and returns the text unchanged
when the first line is not `---` or the fence is unclosed — exactly the two
cases in which the merge prepends or refuses. Reusing it instead of a second
line scan means the check and the merge cannot drift apart: whatever the
merge will treat as a block, the setup reports as one, and an unclosed fence
is "no block" here as it is a `FrontmatterMergeError` there (Pass 2 falls back
to the plain note for it). No YAML is parsed: the question is about the
fence, not the keys, and the template's Templater tokens inside the block are
none of the setup's business.

## WHY `needs_anchor` Reads the Two Most Recent Periodic Notes

WHY: `setup-input` requires an anchor, and the owner decided that the
dialogue asks for one rather than letting the proposal fail validation
after Confirm. Without a template heading to propose from — no template,
`0 none`, a template whose only heading is the title — the only headings
that exist before any review is written are those of the user's own
periodic notes. `match` reads the two notes with the latest period under
the proposed format and rule (one `read_note` each, two calls at most, spent
only when no anchor could be proposed) and lists their level-2-and-deeper
headings, most recent note first, document order, duplicates dropped. Two
notes, not one: the latest note may be a thin one the user has not filled
yet; not eight: the week inference already reads up to eight frontmatters,
and headings rarely change between weeks. A note whose read fails (the key
may not reach it) contributes nothing; an empty list still carries
`needs_anchor: true`, and the skill asks the user to type the heading. The
headings reach stdout by design — they are the structure of the user's
notes, the same text `review-instructions.py preview` prints as `headings`
for the place pick, and `tests/test_review_privacy.py` names the field.
