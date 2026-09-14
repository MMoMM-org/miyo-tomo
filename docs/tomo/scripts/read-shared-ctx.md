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

## Why containers serialize compact

The first version pretty-printed with `indent=2`. Measured against the live
context, `--field mocs` came to **44 KB — larger than catting the whole 40 KB
file**. Indentation grows with nesting depth, and `mocs` is 72% of the payload,
so the helper built to shrink a subagent's context was inflating it.

Containers now serialize with `separators=(",", ":")`. `--indent` exists for
the times a person is reading the output; nothing in the pipeline passes it.

## The saving that is available, and the one that is not

Step 1 now loads all six keys the contract names, compact: 40705 bytes against
40764 for the `cat`. That difference is `run_id` and `schema_version`, and it
is not the point. The point is that the step goes through a tool that can also
answer `--field`, which is what makes the inline-Python prohibition in the
analyst's Never-list enforceable.

The real saving is still on the table and was not taken. `candidate_mocs`
appears **only** on `create_atomic_note` actions — verified across a full run's
twelve result files, where the three pure `update_daily` items carry none. Those
three loaded 29 KB of MOC inventory and read none of it.

Capturing that requires the MOC match to run *after* the worthiness assessment,
and today it runs before: Step 4 matches MOCs, Step 7 decides worthiness. That
is a reorder of the documented step sequence, not a change to how a file is
loaded, and it has a hazard worth naming before anyone attempts it — Step 7.5
segments a long item into several threads, each scored on its own, and each
surviving thread becomes an atomic note. If MOC matching belongs per-thread
rather than per-item, then the current order may already be producing one match
for an item that needs several, and the reorder is a correctness question
wearing a performance question's clothes.

Left as an open question deliberately. A byte saving is not worth guessing at
that.
