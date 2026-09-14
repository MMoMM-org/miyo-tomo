# WHY: scripts/read-shared-ctx.py

The WHY layer for `tomo/scripts/read-shared-ctx.py`. Created 2026-09-14, after
measuring how Phase-B subagents actually reach the shared context.

## The measurement that produced it

Four runs, 48 subagents, 58 accesses to `shared-ctx.json`:

    45  cat (whole file)          — what the analyst contract's Step 1 prescribes
     9  inline python / heredoc   — reaching for one field
     4  Read tool (whole file)

And the file itself, on the live instance:

    31488  72.6%  mocs
     6497  15.0%  daily_notes
     3393   7.8%  placeholder_links
      962   2.2%  classification_keywords
      960   2.2%  tag_prefixes
       35   0.1%  asset_folder

Every subagent carries 40 KB. A subagent that only files a daily-note update —
the Laufrunde item is one — carries 31 KB of MOC inventory it never opens, and
the cost multiplies by the item count because each of the twelve loads its own
copy.

The nine inline reaches asked for `daily_notes`, `tag_prefixes`,
`placeholder_links`, `classification_keywords` and `asset_folder`: together
under 12 KB. They were the right instinct with the forbidden tool. Three of
them opened with `print(list(d.keys()))`, which is why `--keys` exists and why
it prints sizes rather than just names.

## Why this is the same defect as `read-routing-plan.py`

The conductor forbids `python3 -c` and, until yesterday, gave no way to turn
`routing-plan.json` into the list it needed. `read-routing-plan.py` closed
that. `inbox-analyst.md` has neither the prohibition nor an alternative, and
its subagents reached for inline Python in the same shape for the same reason.

A prohibition without a sanctioned alternative is a trap. This script is the
alternative; the prohibition can follow only once it exists.

## Interface decisions

**Scalars print bare, containers print JSON.** A scalar is usually captured
into a variable — `--field asset_folder` should not hand back a quoted string
the caller then has to unwrap.

**`--fields` always prints a JSON object, even for one name.** Otherwise a
caller that builds the field list dynamically gets a different shape depending
on how many names it happened to pass.

**Booleans render `true`/`false`, not `True`/`False`.** `trackers_enabled` is
branched on by the contract; Python's capitalisation matches neither a shell
comparison nor JSON.

**`null` is printed, absence is an error.** The contract distinguishes a key
holding `null` (configured off) from a missing key (an older artifact written
before the field existed). Collapsing both to `""` would erase that.

**An unknown field names its siblings.** An agent told only "not found" guesses
again; one told `['daily_log', 'date_formats', 'enabled', 'path_pattern',
'tracker_fields', 'trackers_enabled']` stops.

## Guard

`tests/test_read_shared_ctx.py`, including
`TestAgainstTheRealContract::test_every_contract_field_resolves` — it extracts
every `shared_ctx.<dotted.path>` that `inbox-analyst.md` names and resolves
each one against the fixture. It failed on first run over
`daily_notes.daily_log.time_extraction.{sources,fallback}`, which the fixture
had not modelled; the builder does emit them. That is the test doing its job in
the direction it was written for — a contract reference that no longer resolves
is the thing it exists to catch, and a fixture that drifts from the builder is
how that starts.
