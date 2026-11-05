# WHY: template-outline.py

> Rationale for decisions in `tomo/scripts/template-outline.py`.
> Lists the points of one note template for `/note` (spec 044, issue #169, PRD F3,
> SDD F3-AC1).

## A script, not the model reading the template

WHY: which headings, frontmatter keys and tokens are points must be exact, and the
filled-note check later fails on any token left over. The model holds the
dialogue; the script reads the template through `lib/template_syntax.py`, the same
parser the check uses (ADR-4), so a point the outline offers is a point the check
enforces.

## Where the prefilled values come from

WHY a resolver in `lib/template_syntax.py`, not a subprocess call to
`token-render.py`: token-render replaces every token and blanks the ones it has no
value for, which would erase the points the model must fill, and it protects only
backtick fences. `resolve_prefilled()` replaces only the matches `tokens()` reports
as prefilled; its value rules are copies of token-render's, pinned by a parity test.
The full reasoning is in `docs/tomo/scripts/lib/template_syntax.md`.

WHY the script draws the clock and loads `config/vault-config.yaml` itself: the
library stays pure (no IO), and the config path is relative to the working
directory, which is the instance root inside the container. A missing config file
means no config values (each config token becomes empty text, as in token-render);
an unreadable one is reported on stderr by its error class only.

## Where has_source comes from

WHY `--stage` reads `source_path` from the stage's `meta.json`: `note-instructions.py
new` already recorded whether the material is an inbox note. Asking the skill to
pass a flag would be a second source of the same fact that could disagree. Without
`--stage` (the `--process` mode, `--out` only) there is no draft and no source, so
`source_path` and `source_link` are points. A stage whose `meta.json` is unusable is
a bad invocation (exit 2): the stem does not name a draft `new` created.

## Exit codes and error text

WHY exit 1 only for an unreadable template: the skill reads exit 1 as "the key may
lack read access" and offers another candidate. `frontmatter_ok: false` is still a
usable outline (exit 0); the skill drafts a frontmatter block anyway. A failure to
write `tomo-tmp/` is not a read-access problem, so it is exit 2.

WHY the error text names the error class and the Kado message only: the skill shows
it verbatim, and the template body is user content. No template text is put in an
error or on stderr.

## The output is the same object on stdout and in the files

WHY `outline.json` (and the `--out` file) hold exactly what stdout prints: later
steps (`note-process.py read --outline`) read the file instead of the conversation,
so the two must not differ. Line numbers refer to the template; prefilled values
never contain a newline, so they are valid for `template.md` too.

## --local

WHY: tests read a template from a local file instead of a fake Kado, so the parser
and the staging can be exercised without a Kado client.

## Version 0.1.0

WHY: initial implementation (spec 044 T2.1). `update-tomo.sh` skips unchanged
versions.
