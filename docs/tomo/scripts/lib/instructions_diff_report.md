# WHY: lib/instructions_diff_report.py

> Rationale for decisions in `tomo/scripts/lib/instructions_diff_report.py`.
> The suggestions-mode coverage report: `ACTION_ORDER` and `run_diff`. Split
> out of `instructions-diff.py` (#216). See
> `docs/tomo/scripts/instructions-diff.md` for the module map.

## Why the Report Is Its Own Module

WHY: `run_diff` is the orchestration step. It derives both sides, applies every
reconciliation in a fixed order, prints the report and returns the exit code.
The other modules each answer one question, and this module puts their answers
together into the text the conductor reads. Its printed lines are a contract:
`synthesis-conductor.md` relays the `RESULT:` line verbatim, and
`evals/_lib/stubs.sh` copies the wording. A change to any printed line here
means re-checking both.

WHY `ACTION_ORDER` lives here: it is the whitelist of kinds the count table
reconciles. A kind missing from it is counted but never compared, and the audit
passes green while those actions go unaudited (specs 031 and 032 both ran into
this). A new action kind must be added here.
