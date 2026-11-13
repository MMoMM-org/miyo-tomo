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
