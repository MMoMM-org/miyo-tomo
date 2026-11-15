# WHY: lib/review_match.py

> Rationale for decisions in `tomo/scripts/lib/review_match.py`.
> The module holds the proposal behind `review-session.py match` (spec 045 F1;
> ADR-1, ADR-4), split out of the script in #260. The script keeps the
> argparse wiring, `start`, `setup-input` and the exit codes.

## WHY the Proposal Left the Script

`review-session.py` grew past the constitution's L2 band (about 300–500 lines
of dense logic) once the template choice, the anchor question and the
frontmatter gate joined `match` (532 lines). The split follows cohesion, not a
line count: `match` is one flow with its own inputs (the flags of one
subcommand, the config, a vault) and its own output (`proposal`, `evidence`
and the optional keys the skill asks about), and `start` and `setup-input` use
none of it but one helper. `propose(open_vault, config, profile, args)` is that
flow, moved whole; the output is byte-identical, pinned by
`tests/test_review_session.py`, `tests/test_review_session_templates.py` and
`tests/test_review_privacy.py` run unchanged.

## WHY `propose` Takes a Vault Factory, Not a Vault

The tests patch `KadoClient` on the script module (`monkeypatch.setattr(mod,
"KadoClient", fake)`), and `match` must not open a vault before it knows the
format is safe (the `unsafe-format` stop spends no Kado call). The script
therefore passes `lambda: Vault(KadoClient)`: the name stays looked up in the
script at call time, and the lib opens the vault at the same point the script
did, inside the `Stopped` handler. A `Vault` argument would have moved the
construction before the unsafe-format check or out of the handler.

## WHY `args` Is Passed as the Parsed Namespace

`propose` reads ten flags (`kind`, `folder`, `format`, `first_day`,
`min_days`, `template`, `anchor`, `template_frontmatter_ok`, `today`). A
keyword list of the same ten names would restate the argparse contract a
second time for no gain; the module docstring names the fields it reads. A
refactor that changes no behaviour does not also redesign the call.

## WHY the Config Readers Live Here Too

`str_value`, `str_list` and `review_section` read the vault config the way
`match` needs it (a blank string is no value, a list must hold strings, a
non-mapping section is empty). `configured_rule` is the one of them `start`
also uses: the rule the user configured orders the listing and parses the
argument. It lives beside the readers it shares a shape with, and the script
imports it; a second copy in the script would be two places for the rule that
decides which week a note belongs to.

## WHY `match_names` and `day_name` Are Public

They are module functions with no state, named so a test can call them
without a vault. `match_names` returns one entry per note, so a duplicated
stem is listed once per path (see "WHY Two Notes With the Same Stem Are Both
Listed" in docs/tomo/scripts/review-session.md); a dated note is matched only
when its own start date fits the proposal's rule.

## WHY the Default Format Is Looked Up by Kind

With no configured and no typed format, the proposal falls back to
`DEFAULT_FORMATS[kind]`; only the week has a special case (a non-ISO rule
gets `gggg-[W]ww`). The fallback had named the month's `YYYY-MM` for every
kind that is not a week; once the quarter became a kind (spec 046 T1.4) that
would have proposed a month format for quarterly notes.

## WHY the Section Mapping Is Proposed by `match` (spec 046 T2.1)

The section mapping rides the existing confirm step (no extra question turn),
so the one `match` call that proposes folder, format, template and place also
carries `sections`. The script part and the model part are split as ADR-9
draws them: `match` supplies the candidates (one per template heading of level
2..6, from `lib/review_mapping.analyse_template`), their keys, states, reasons
and flags, the defaults and the saved rows; the model only words descriptions,
keywords and group hints. A deterministic analysis is testable on the owner's
templates, and a wrong left-out cannot be undone by the user.

`sections` is always present. With no template, a template Tomo cannot read or
find, or a template without a heading a row may sit on, it carries
`candidates: []` and `mappable: false`: the skill says that no section can be
mapped (F2-AC9). An explicit `false` is an answer; a missing key would read
the same as an old script and could not be told apart from a no-op.

`mappable` counts an offered heading and a heading left out as `automatic`.
The second takes an analysis row (`placement: review`, F2-AC12): its text
lands in the "Tomo Review" section, never under the heading, so a template
whose only sections are query output still has something to map. With no
such heading the left-out list is dropped too, because nothing in it can be
chosen; the reasons matter only beside headings that can.

## WHY the Defaults Are What They Are

A saved row comes back as the defaults (its placement and cap) and as
`saved`, so a rerun of the setup shows what is stored, not a fresh guess. An
offered heading without a saved row defaults to `end` with the reader's cap of
8: the end of the section is after whatever the user wrote, so Tomo's block
never sits between the heading and the user's own words. A heading left out as
`automatic` defaults to `review`, the only placement it accepts (Data Storage
Changes). Every other left-out heading has `defaults: null`: no row may sit on
it, and a placement there would be a value the setup refuses.

Saved rows and off-limits rows are read for the resolved template
(`review.<g>.sections.<template>`, `review.<g>.off_limits.<template>`, through
`review_config.template_rows`), not only for the configured one: a Correct back
to a template that has rows stored shows them again. The off-limits rows feed
the analysis, so a heading the user protected comes back left out as
`off-limits`, and they are returned as `sections.off_limits` for the table.

## WHY `match` Writes `rows-<kind>.json` and Returns `dropped`

F7-AC3 asks Tomo to name the mapped headings a corrected template no longer
has. The earlier rows exist only in the dialogue; the model writes no state
file (CON-1, ADR-13). So `match` itself keeps the rows it showed in
`tomo-tmp/review/rows-<kind>.json` and, when the resolved template differs
from the one in that file, returns as `dropped` the rows whose (heading,
level, parent) the new template lacks (`review_mapping.dropped`). The same
template again drops nothing. One file per kind, because a week and a quarter
can be set up in one session and the week's rows are not the quarter's
earlier mapping.

The rows shown are the saved row of a heading when there is one, else a
default row for every offered heading: the setup proposes a row per suitable
heading (F2-AC1), so every offered heading is part of the earlier mapping.
The file holds setup text only — heading keys, descriptions, keywords,
placements, caps (CON-3). It never holds the anchor, a note heading or any
body line; ids and groups are left out because nothing reads them from it.

A template that is not found drops nothing and keeps the rows, the template
and the outline of the file: no proposal was shown for it, the question is
asked again, and the next answer is still compared against the rows the user
last saw. An unreadable template does the same, since its headings are
unknown and every earlier row would read as dropped. Only `resolved` changes
(below).

### WHY the Rows File Also Holds the Outline and `resolved` (T2.2)

`setup-input` stays offline (ADR-3) and checks a row's eligibility against
what `match` saw (docs/tomo/scripts/lib/review_setup_rows.md). The evidence
must come from a script, not from the model's confirmed file, so `match`
writes it next to the rows: `outline` — per template heading its key, line,
ancestors, body kind and structural reason, plus the level-1 lines, from
`review_mapping.outline` — and `resolved {template, kind}`, the template name
`match` tried last and its `template_kind` (`missing` when Kado did not find
it). `resolved` is written on every run, also when no rows are shown, so a
name that was not found is refused even when the model puts it back into the
confirmed setup. Off-limits and `automatic` verdicts are not stored: they
depend on the off-limits rows the user may change in the same step.

### WHY a Saved Row Whose Heading Is Gone Is in `dropped`

A row saved for the resolved template whose (heading, level, parent) the
template no longer has is shown nowhere else: it is no candidate and no shown
row. The skill builds the save from the confirm table, so `setup-input` would
remove it without the user ever seeing it (F2-AC10: saving changes no other
setup value without the user's confirmation). `dropped` already means "rows
the template lacks" and is what the skill names before the save, so such a
row is listed there too, on every run with the same template, not only after a
template change. The rows-file comparison (F7-AC3) still drops nothing for the
same template.

A rows file that cannot be written (`OSError` from `write_rows`) is not
caught: `match` exits 1 instead of degrading to `status ok`. The proposal
would still be usable, but the next correction would compare against stale or
missing rows and `dropped` would silently miss headings the user saw — F7-AC3
would fail without a sign. A failed run is the honest answer; the tmp dir is
Tomo's own and an unwritable one is an install fault, not a vault state.

## WHY a Template That Is Not Found Is `template_not_found` (F7-AC1, #267)

Before spec 046 a typed or configured name Kado did not find was proposed as
the template with `template_kind: missing`, and a Confirm saved the typo.
Prose rules in the skill did not hold. `match` now returns
`template_not_found {name, source: typed|configured}`, sets the template to
null and lists the candidates of the templates folder, so the skill names the
miss and asks again from the list (`setup-input` refuses a confirmed missing
template from `resolved` in the rows file, T2.2). `source` tells the skill whether the user mistyped or the
saved mapping points at a template that was renamed or deleted.

## WHY the Configured Anchor Counts Only for the Configured Template (F7-AC2)

The configured anchor is a heading of the configured template. After a
Correct to another template it named a heading that template may not have,
and the review place was not proposed anew. The anchor is therefore taken
from the config only while the resolved template equals the configured one
(both none counts as equal: a setup without a template keeps its anchor);
otherwise it is proposed from the new template's headings. `--anchor` still
wins over both, and the skill drops it when the template changes.

## WHY the Quarter's Format Follows Its Notes

F6-AC1 asks the proposed quarterly format to follow the existing notes, or
`YYYY-[Q]Q` when there are none. The week infers its rule from the notes'
dates; a quarterly note has no rule to infer, only a name. With neither a
`--format` nor a configured one, `match` tries a short list of quarter
formats (`QUARTER_FORMATS`) on the folder's names and takes the one that
parses the most, the default first on a tie; with no name that parses, the
default stands. The list is small on purpose: an unusual name stays
unmatched in `evidence` and the user corrects the format, as for a month.
