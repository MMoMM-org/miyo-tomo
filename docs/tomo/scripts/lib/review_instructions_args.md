# WHY: lib/review_instructions_args.py

> Rationale for decisions in `tomo/scripts/lib/review_instructions_args.py`.
> The module holds the argparse pieces of `review-instructions.py`: the
> `--stem` type and the flags `preview` and `deliver` share —
> `--place-anchor`, `--section-choice <key>=skip|review` and
> `--confirm-moved <key>` (spec 046 ADR-12, T5.5; split out at T6.2).

## WHY a Module of Its Own (spec 046 T6.2)

`review-instructions.py` stood at 536 lines against its 540-line cap. The
flag parsing is the one part of the script with no Kado, no plan and no
`Run`: it turns argv into `args.choices`. Moving it leaves the script its
four subcommands, the context of one run and `build_parser`, which stays
in the script because it names the script's defaults (profiles directory,
`tomo-tmp/review`) and because tests and the CLI contract read the parser
from there.

## WHY the Two Choice Flags Fill One Mapping

`--section-choice` and `--confirm-moved` answer the same stops, one key
each; `ChoiceFlag` collects both into one `{key: choice}` under `choices`,
so the planner gets one dict and a key answered twice — also across the
two flags — is caught where it is parsed. A malformed value, a key that is
no section key (`review_doc_parse.SECTION_KEY`) and a doubled key are a bad
invocation, exit 2: they are the skill's mistakes, not the vault's state
(docs/tomo/scripts/review-instructions.md, "WHY Every Section Stop Refuses
Until a Choice Answers It").
